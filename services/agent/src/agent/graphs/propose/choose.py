"""Node 2 của graph: gọi model một lần, rồi áp các luật lên đề nghị của nó."""

import contextlib
import json
import logging

from pydantic import ValidationError

from agent import llm
from agent.graphs.propose.ask_again import (
    AnsweredUnread,
    AskedWhatWasKnown,
    FewChoices,
    IncompletePlan,
    NoOutline,
    NothingToSay,
    PlanOverRevision,
    TooManyQuestions,
    UncountedOutline,
    Unparsed,
)
from agent.graphs.propose.clarify import answers, choices_wanted, row_names
from agent.graphs.propose.compose import ProposeState
from agent.graphs.propose.history import telling
from agent.graphs.propose.outline import (
    approved_plan,
    brief_in,
    knows_everything,
    miscounted,
    right_purpose,
)
from agent.graphs.propose.plan_checks import drafts_over_a_revision, garbled, lacking
from agent.graphs.propose.proposal import _Proposal, nfc, unmangled
from agent.graphs.propose.read_order import (
    answered_unread,
    just_listed,
    library_first,
    misfiled_read,
    picked_book_first,
    read_before_outline,
    reads_first,
    toc_first,
    which_book,
)
from contracts import MOST_CLARIFY_QUESTIONS, NextStepCompleted

logger = logging.getLogger("agent.graphs.propose")


async def choose(state: ProposeState) -> dict:
    """Hỏi model một đề nghị, và ghi lại nó tốn bao nhiêu.

    `include_raw` là thứ làm cho chi phí biết được. Structured output một mình chỉ
    trả lại đối tượng đã parse rồi bỏ đi cái response nó đi trong, mà báo cáo usage
    thì nằm trên chính response đó -- nên lời khẳng định trong plan rằng ghi lại số
    token là "gần như miễn phí" đã sai: nó cần argument này và một field trong hợp
    đồng.

    Args:
        state: Mang theo các message đã dựng.

    Returns:
        Mảnh `step` của state, với `model_tokens` điền từ provider chứ không điền từ
        model.

    Raises:
        Unparsed: Đầu ra không đọc được thành một đề nghị (ví dụ tên tool ghi vào `kind`).
        NothingToSay: `say`, `ask_clarify` hay `outline` mà `text` rỗng.
        FewChoices: `ask_clarify` ít lựa chọn hơn `choices_wanted`; mang theo câu hỏi ấy.
        IncompletePlan: Plan có bước thiếu tham số bắt buộc; mang theo plan ấy, để `propose`
            còn dùng được nó khi lần hỏi lại hỏng.
    """
    model = llm.with_fallback(lambda chat: chat.with_structured_output(_Proposal, include_raw=True))
    answered = await model.ainvoke(state["messages"])

    # Một provider không làm được `include_raw` -- hoặc một fake bỏ qua nó -- trả
    # thẳng lại đối tượng đã parse. Cả hai hình dạng đều được hỗ trợ, vì số token chỉ là
    # thứ có thì tốt còn đề nghị thì không.
    if isinstance(answered, dict):
        parsed = answered["parsed"]
        if parsed is None:
            # `include_raw` biến một lần parse thất bại thành `parsed=None` cộng với
            # exception nằm dưới `parsing_error`, trong khi `include_raw=False` thì
            # đã raise nó kèm luôn đầu ra có vấn đề. Để nó đi qua là đổi một thông
            # báo gọi tên đầu ra xấu lấy một `AttributeError` trên None, mà cái đó
            # chẳng gọi tên gì cả. Hỏi lại một lần (`Unparsed`): ở case 04 model ghi tên tool
            # vào `kind`, và lần hỏi lại nói đúng chỗ sai. Nhưng giáo viên vừa đồng ý dàn ý thì
            # plan dựng từ dàn ý trước, như mọi lần hỏi lại khác: nó không cần lời model nào.
            agreed = approved_plan(
                NextStepCompleted(
                    request_id="",
                    kind="say",
                    text="",
                    model_tokens=_spent(answered.get("raw")),
                ),
                state["request"],
            )
            if agreed.kind == "plan":
                return {"step": agreed}
            raise Unparsed(
                f"model did not produce a usable proposal: {answered.get('parsing_error')}",
                _raw_kind(answered.get("raw")),
                frozenset(tool.name for tool in state["request"].catalog),
            )
        proposal: _Proposal = parsed
        spent = _spent(answered.get("raw"))
    else:
        proposal, spent = answered, 0

    logger.info("known before choosing %s: %s", proposal.kind, proposal.known)
    # Giáo viên vừa đồng ý dàn ý: plan dựng từ dàn ý, **trước** mọi lần hỏi lại -- một câu trả lời
    # rỗng hay hỏng sau *"oke"* mà thành câu trung tính thì lời duyệt mất, và lần gõ lại không còn
    # đứng ngay sau dàn ý (review đợt 6).
    # Lời mở là lời model vừa viết cho plan, hay không có lời mở nào (ADR-30): không câu cố định.
    agreed = approved_plan(
        NextStepCompleted(
            request_id="",
            kind="say",
            # Qua bước sửa chữ như mọi lời khác (`_Proposal.completed`): `\frac` bị bộ giải mã JSON
            # nuốt thành form-feed thì trả lại, rồi NFC.
            text=nfc(unmangled(proposal).text.strip()) if proposal.kind == "plan" else "",
            model_tokens=spent,
        ),
        state["request"],
    )
    if agreed.kind == "plan":
        return {"step": agreed}
    # Lượt hỏi lại mà mọi chữ nằm trong các câu là một lượt có chữ (review pha 6): `asked()` gộp
    # một câu duy nhất vào `text`, còn nhiều câu thì FE vẽ chúng, không cần lời mở.
    questioned = proposal.kind == "ask_clarify" and any(
        one.text.strip() or one.label.strip() for one in proposal.questions
    )
    # Lượt kể lại được phép im (`soan-de` bước 6: không có gì đáng nói thì không cần nói): một `say`
    # rỗng ở đó là lựa chọn, không phải đầu ra hỏng -- hỏi lại nó chỉ đẻ ra một câu *chưa hiểu ý
    # bạn* sai chỗ (review plan `report-into-propose`).
    silent = proposal.kind == "say" and telling(state["request"])
    if (
        proposal.kind in {"say", "ask_clarify", "outline"}
        and not proposal.text.strip()
        and not questioned
        and not silent
    ):
        # Đo được khi thêm `known`: model viết câu hỏi vào ghi chú rồi để `text` rỗng. Một bong
        # bóng rỗng không bao giờ được tới màn hình; `propose` hỏi lại một lần. Dàn ý cũng vậy
        # từ ADR-30: lời trình bày dàn ý là lời Kriky viết, không còn khuôn BE dựng thay.
        raise NothingToSay(f"model chose {proposal.kind} with nothing to say")
    if proposal.kind == "outline" and not proposal.outline:
        raise NoOutline("model chose outline with no item")
    if proposal.kind == "call_tool" and proposal.tool_name.strip() == "outline":
        # Thử tay 15/10/2026: `outline` là một kind, không phải tool; BE từ chối lời gọi ấy và
        # giáo viên thấy *"không có tool nào tên outline"* trong bằng chứng. Hỏi lại một lần.
        raise NoOutline("model called a tool named outline")

    # `request_id` do `propose` điền, vì đó là chỗ duy nhất biết nó. Để rỗng ở đây sẽ
    # là một lời nói dối nếu nó còn ở lại, nên nó không ở lại.
    request = state["request"]
    try:
        step = unmangled(proposal).completed(request_id="", model_tokens=spent)
    except ValidationError as unusable:
        # Một mục dàn ý sai hình dạng (số câu ngoài 1–10, chữ rỗng): hỏi lại một lần, như một
        # câu rỗng -- không có gì để giáo viên đọc (`draft-outline`).
        if proposal.kind != "outline":
            raise
        raise NoOutline(f"unusable outline item: {unusable.errors()[0]['msg']}") from unusable
    # Luật thứ tự đọc (`unbiased-model-text` T5): đề nghị đúng việc mà sai bước thì thành **một lời
    # gọi tool đọc**; ở bước kế trong cùng vòng gọi tool của BE, model nêu lại với kết quả trong
    # tay. Bước nào đã đọc rồi thì không gọi lại -- mỗi luật tự kiểm, không thì BE hỏi tới trần rồi
    # báo lỗi.
    step = reads_first(step, request)
    step = picked_book_first(step, request)
    step = misfiled_read(step, request)
    step = toc_first(step, request)
    step = library_first(step, request, state["skills"])
    step = which_book(step, request)
    step = read_before_outline(step, request)
    step = right_purpose(step, request)
    if step.kind == "outline":
        # Môn, khối, phạm vi đi cùng dàn ý, cho lượt duyệt (`approved_plan`).
        step = step.model_copy(update={"tool_args": {**brief_in(proposal.known), **step.tool_args}})
    if step.kind == "plan":
        flaw = lacking(step.steps, state["request"]) or garbled(step.steps)
        if flaw:
            raise IncompletePlan(flaw, step)
        if drafts_over_a_revision(step, state["request"]):
            raise PlanOverRevision("plan drafts right after the teacher asked to change", step)
    if step.kind == "outline":
        flaw = miscounted(step, proposal.known, request)
        if flaw:
            raise UncountedOutline(flaw, step)
    if answered_unread(step, request, state["skills"]):
        raise AnsweredUnread("answered a question about the book without opening it", step)
    if step.kind == "ask_clarify" and step.questions:
        # ADR-32: mỗi câu một bộ nút, cùng lưới với câu hỏi thường -- từng câu đủ lựa chọn thật.
        kept = tuple(
            one.model_copy(update={"choices": answers(one.choices, one.text)})
            for one in step.questions
        )
        step = step.model_copy(update={"questions": kept})
        # Đếm câu **thật** -- câu trống đã bị `asked()` bỏ: ba câu hợp lệ cộng một câu trống không
        # phải lý do hỏi lại model (review code 17/10, plan `backlog-tier-1`).
        real = sum(1 for one in proposal.questions if one.text.strip() or one.label.strip())
        if real > MOST_CLARIFY_QUESTIONS:
            raise TooManyQuestions(f"{real} questions", step)
        # Câu về **dòng** (lựa chọn gọi tên một `candidate`) theo số dòng có thật -- chỉ có hai lớp
        # thì đòi ba là mời model bịa lớp thứ ba. Câu về **tham số** vẫn đòi ba (review code 17/10:
        # bản trước áp số dòng cho mọi câu, nên *Khối* hai nút cũng lọt).
        rows = row_names(state["request"])
        wanted = choices_wanted(state["request"])
        few = [
            one.label
            for one in kept
            if len(one.choices)
            < (
                wanted
                if any(" ".join(choice.split()).casefold() in rows for choice in one.choices)
                else 3
            )
        ]
        if few:
            raise FewChoices(f"too few choices for {few}", step)
    elif step.kind == "ask_clarify":
        # Chỉ đếm câu trả lời thật: câu hỏi, tên mục và "Khác" bị bỏ trước (`answers`) -- bấm
        # chúng là gửi đi một thứ không trả lời gì.
        choices = answers(step.choices, step.text)
        step = step.model_copy(update={"choices": choices})
        # Câu 33 = A (21/10/2026), đúng ca thử tay V6: `known` đủ bốn mục mà model hỏi lại **không
        # câu hỏi, không nút nào** -- giáo viên kẹt. Chỉ ca ấy: hỏi lại có nút (mục nào trong nhiều
        # mục khớp, lớp nào, bao nhiêu câu sau lời sửa) vẫn hợp lệ dù `known` đủ (review vòng 1).
        if not choices and knows_everything(proposal.known) and not just_listed(request):
            raise AskedWhatWasKnown("asked again with nothing to ask though known is full", step)
        wanted = choices_wanted(state["request"])
        if len(choices) < wanted:
            raise FewChoices(f"{len(choices)} choice(s), wanted {wanted}", step)
    return {"step": step}


def _raw_kind(raw: object) -> str:
    """`kind` model đã viết trong một response thô không parse được, hay rỗng.

    Structured output của LangChain đi qua tool call, nên `kind` nằm ở `args` của tool call đầu;
    provider trả JSON trong chữ thì đọc chữ ấy.

    Args:
        raw: Response thô `include_raw` trả kèm.

    Returns:
        Chuỗi `kind` model viết, rỗng khi không đọc ra.
    """
    for call in getattr(raw, "tool_calls", None) or ():
        args = call.get("args") if isinstance(call, dict) else None
        if isinstance(args, dict) and isinstance(args.get("kind"), str):
            return args["kind"].strip()
    content = getattr(raw, "content", None)
    if isinstance(content, str):
        with contextlib.suppress(ValueError):
            body = json.loads(content)
            if isinstance(body, dict) and isinstance(body.get("kind"), str):
                return body["kind"].strip()
    return ""


def _spent(raw: object) -> int:
    """Đọc số token mà provider báo, lấy từ một response thô.

    Args:
        raw: Bất cứ thứ gì provider trả về kèm theo đối tượng đã parse.

    Returns:
        Tổng số token, hoặc 0 khi provider không báo gì. Số 0 nghĩa là "không được
        cho biết", không phải "miễn phí": một model giả trong test không báo gì, và
        một số provider cũng vậy.
    """
    usage = getattr(raw, "usage_metadata", None)
    if isinstance(usage, dict):
        total = usage.get("total_tokens")
        if isinstance(total, int):
            return total
    return 0
