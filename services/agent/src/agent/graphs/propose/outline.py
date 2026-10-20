"""Dàn ý (ADR-29): giáo viên đồng ý dàn ý, đúng việc, đếm số câu."""

import logging
import re
import unicodedata

from agent.graphs.propose.history import _since_plan
from contracts import NextStepCompleted, NextStepRequested, PlanStep

logger = logging.getLogger("agent.graphs.propose")

_COUNT_IN_KNOWN = re.compile(r"question_count\s*=\s*(\d+)")
# Số câu giáo viên tự nói: *"tầm 5 câu"*, *"Số câu: 5 câu"* (tin gộp của thẻ hỏi lại). Không khớp
# *"câu 3"* -- đó là số thứ tự, không phải số câu.
_COUNT_SAID = re.compile(r"(\d+)\s*câu\b", re.I)
# Lời giáo viên nói rõ việc của dàn ý: *"thay câu 3 …"*, *"soạn thêm 3 câu"* (`draft-outline`).
_REPLACES = re.compile(r"\b(?:thay|đổi|làm lại|soạn lại)\s+(?:câu|câu hỏi)\s*(?:số\s*)?(\d+)", re.I)
_ADDS = re.compile(r"\b(?:soạn|ra|làm|viết)\s+thêm\b|\bthêm\s+\d+\s+câu\b", re.I)
# *"soạn thêm một đề mới"* là đề khác, không phải câu thêm vào đề đang có (review đợt 6).
_ANOTHER_PAPER = re.compile(r"\bđề\s+(?:mới|khác|nữa)\b", re.I)
# Câu đồng ý của giáo viên ngay sau một dàn ý (`draft-outline`): **cả câu** chỉ là lời đồng ý, cùng
# vài tiếng đệm. Review đợt 6: khớp đầu câu thì *"ok nhưng câu 2 đổi sang tự luận"*, *"được không?"*
# thành đồng ý, và câu hỏi được soạn theo dàn ý giáo viên vừa xin đổi.
_AGREE_WORD = r"(?:ok|oke|okay|được|đồng ý|duyệt|chốt|ừ|vâng|soạn đi|làm đi)"
_AGREES = re.compile(
    rf"^\s*{_AGREE_WORD}(?:[\s,]+(?:{_AGREE_WORD}|nhé|nha|nhá|luôn|đi|rồi|ạ|vậy))*\s*[.!]*\s*$",
    re.IGNORECASE,
)
# Một mục trong `known`: `subject=Toán «Toán»` -- giá trị đứng trước «, hay trước `; mục=` kế tiếp.
# Dấu phẩy ở trong giá trị: *"tỉ lệ thuận, tỉ lệ nghịch"* là một phạm vi (review đợt 6).
_KNOWN_FIELD = re.compile(r"\b(subject|grade|topic_scope)\s*=\s*(.+?)\s*(?=«|;\s*\w+\s*=|;?\s*$)")


def _brief_in(known: str) -> dict[str, str]:
    """Môn, khối, phạm vi model đã ghi trong `known`, bỏ mục ghi `?`. Hàm thuần."""
    found: dict[str, str] = {}
    for key, value in _KNOWN_FIELD.findall(known):
        if value.strip() and value.strip() != "?":
            found.setdefault(key, value.strip())
    return found


def _approved_plan(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Giáo viên đồng ý dàn ý vừa hiện: plan dựng từ chính dàn ý, kể cả khi model nêu plan khác. Hàm
    thuần.

    Thử tay 15/10/2026: sau *"oke"* model dựng lại `known` từ câu vừa gõ, mất phạm vi, rồi hỏi
    lại khối -- lỗi *lời đáp ngắn làm model quên lượt trước* (`backlog.md`), rơi đúng vào bước duyệt
    của ADR-29. Lượt thử sau đó: *"oke"* cho một dàn ý soạn thêm ra plan `create_draft` khối 6 --
    plan của model cũng quên như vậy, nên không giữ nó. Mọi thứ plan cần đã nằm trong lượt dàn ý:
    việc (`for`), đề, câu bị thay, và môn, khối, phạm vi ghi lúc nêu dàn ý (`brief`); nút và tài
    liệu BE điền từ dàn ý. Thiếu một mục thì để model tự xoay.

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.

    Returns:
        Plan soạn theo dàn ý, hoặc `step` nguyên.
    """
    if len(request.history) < 2 or request.history[-1].kind != "teacher":
        return step
    said = request.history[-1]
    # Câu giáo viên gõ mà lượt hỏng trước khi đáp (hàng mồ côi) không chen giữa dàn ý và lời đồng ý:
    # giáo viên gõ lại *"oke"* là đúng việc nên làm (review đợt 6).
    # Thông báo hệ thống cũng vậy: model hỏng sau *"oke"* thì giáo viên được dặn gửi lại, và lần gửi
    # lại ấy vẫn là lời đáp dàn ý (review pha 5, `kriky-writes-every-word`).
    earlier = list(request.history[:-1])
    while earlier and earlier[-1].kind in {"teacher", "notice"}:
        earlier.pop()
    if not earlier:
        return step
    shown = earlier[-1]
    if shown.kind != "outline" or not shown.tool_result.get("items"):
        return step
    if not _AGREES.search(unicodedata.normalize("NFC", said.text)):
        return step
    kept = shown.tool_result
    purpose = str(kept.get("for") or "new")
    if purpose == "replace":
        steps: tuple[PlanStep, ...] = (
            PlanStep(
                tool_name="replace_question",
                args={"assessment_id": "", "question_number": ""},
                title=f"Thay câu {kept.get('first')}",
            ),
        )
    elif purpose == "more":
        steps = (
            PlanStep(
                tool_name="start_drafting",
                args={"assessment_id": "", "question_count": ""},
                title="Soạn thêm câu hỏi",
            ),
        )
    else:
        brief = dict(kept.get("brief") or {})
        if not all(
            str(brief.get(key) or "").strip() for key in ("subject", "grade", "topic_scope")
        ):
            return step
        steps = (
            PlanStep(
                tool_name="create_draft",
                # Sách và các nút để trống: cổng duyệt của BE điền chúng từ chính dàn ý.
                args={
                    **{key: str(brief[key]) for key in ("subject", "grade", "topic_scope")},
                    "document_id": "",
                    "nodes": "",
                },
                title="Tạo đề trống",
            ),
            PlanStep(
                tool_name="start_drafting",
                args={"assessment_id": "{1.assessment_id}", "question_count": ""},
                title="Soạn câu hỏi theo dàn ý",
            ),
        )
    logger.info(
        "teacher agreed to outline %s; planning it (model chose %s)", kept.get("version"), step.kind
    )
    return NextStepCompleted(
        request_id=step.request_id,
        kind="plan",
        # Lời của chính model khi nó vừa nêu plan -- `_choose` chở nó trong một `say` -- không thì
        # không lời mở nào (ADR-30): câu hỏi lại model vừa viết không phải lời mở của plan này.
        text=step.text if step.kind in {"plan", "say"} else "",
        steps=steps,
        model_tokens=step.model_tokens,
    )


# Kết quả tool nói đoạn chat đã có một đề.
_HAS_DRAFT = frozenset({"create_draft", "start_drafting", "replace_question"})


def _right_purpose(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Dàn ý đúng việc giáo viên vừa nói, khi lời họ nói rõ việc ấy. Hàm thuần.

    Thử tay 15/10/2026 (H4) và bench run-98 (`dan-y-thay-cau` 2/6): *"thay câu 3 bằng …"* ra một
    dàn ý **cả đề** `for=new` -- giáo viên gõ *"oke"* là mở một đề mới thay vì thay câu 3. Model
    viết lại cả dàn ý, chỉ mục chứa câu ấy đổi, nên phép sửa không phải đoán: lấy đúng mục chứa câu
    N, một câu, `for=replace`. Tương tự *"soạn thêm"* trong đoạn chat đã có đề mà dàn ý là
    `for=new` thì việc là `for=more`.

    Lời nói rõ việc là câu **gần nhất** nói rõ một việc, kể từ plan gần nhất -- không chỉ câu
    cuối: thử tay sau review đợt 6, *"soạn thêm 1 câu về số La Mã"* rồi hai lần bấm lựa chọn Kriky
    hỏi lại, và dàn ý ra `for=new` vì câu cuối là tên một bài. Câu nhắc *"đề mới"* thì dừng dò:
    việc là đề mới.

    Args:
        step: Dàn ý model nêu.
        request: Lượt đang hỏi.

    Returns:
        Dàn ý đã đúng việc, hoặc `step` nguyên khi lời giáo viên không nói rõ việc gì.
    """
    if step.kind != "outline":
        return step
    said = ""
    for turn in reversed(_since_plan(request)):
        if turn.kind != "teacher":
            continue
        text = unicodedata.normalize("NFC", turn.text)
        if _ANOTHER_PAPER.search(text) or _REPLACES.search(text) or _ADDS.search(text):
            said = text
            break
    purpose = str(step.tool_args.get("for") or "new")
    has_draft = any(
        turn.kind == "tool_result"
        and turn.tool_name in _HAS_DRAFT
        and (turn.tool_result.get("created") or turn.tool_result.get("started"))
        for turn in request.history
    )
    replaces = _REPLACES.search(said)
    if replaces and has_draft and purpose != "replace":
        number = int(replaces.group(1))
        seen = 0
        for item in step.outline:
            seen += item.questions
            if number <= seen:
                logger.info("outline for %s rewritten to replace question %d", purpose, number)
                return step.model_copy(
                    update={
                        "outline": (item.model_copy(update={"questions": 1}),),
                        "tool_args": {**step.tool_args, "for": "replace", "question": str(number)},
                    }
                )
        return step
    if _ADDS.search(said) and not _ANOTHER_PAPER.search(said) and has_draft and purpose == "new":
        logger.info("outline for new on a turn asking for more -- for=more")
        return step.model_copy(update={"tool_args": {**step.tool_args, "for": "more"}})
    return step


def _count_said(request: NextStepRequested) -> int | None:
    """Số câu giáo viên nói gần nhất kể từ plan gần nhất, hay None. Hàm thuần.

    Bỏ câu *"thay câu 3 …"*: con số ấy là số thứ tự (`_REPLACES`). Bỏ số đứng sau *lớp*, *khối*:
    *"ra đề cho lớp 7 câu hỏi …"* không xin bảy câu. Lời *"thêm 2 câu"*, *"bớt 1 câu"* nói **sau**
    một dàn ý là lời sửa dàn ý ấy, không phải tổng mới: gặp nó thì không đối chiếu nữa -- BE vẫn
    chặn quá mười câu (review code pha 5, plan `backlog-tier-1`).
    """
    if _count_revised(request):
        return None
    for turn in reversed(_since_plan(request)):
        if turn.kind != "teacher" or _REPLACES.search(turn.text):
            continue
        said = _COUNT_SAID.findall(_GRADE_NUMBER.sub("", turn.text))
        if said:
            return int(said[-1])
    return None


def _count_revised(request: NextStepRequested) -> bool:
    """Lời giáo viên **gần nhất mang một con số hay một lời *soạn thêm*** kể từ plan là lời
    *thêm/bớt* (`_ADDS`, `_TRIMS`) nói **sau** một dàn ý. Hàm thuần.

    Lời không con số mà cũng không *soạn thêm* (*"câu 3 khó hơn nhé"*) và lời thay câu thì bỏ qua,
    duyệt tiếp về trước. Khi ấy tổng mới là dàn ý cũ cộng trừ lời sửa -- không con số nào đã ghi
    (lời giáo viên trước đó, hay `known` của model) còn là tổng đúng (review code vòng 2, plan
    `backlog-tier-1`).
    """
    since = _since_plan(request)
    # Duyệt ngược **mọi** lời giáo viên tới lời đầu tiên mang một con số hay một lời *soạn thêm*:
    # *"thêm 2 câu"* rồi
    # *"câu 3 khó hơn nhé"* vẫn là dàn ý đã sửa -- chỉ xét lời cuối thì đọc ra tổng 2 (review code
    # vòng 3).
    for at in range(len(since) - 1, -1, -1):
        turn = since[at]
        if turn.kind != "teacher" or _REPLACES.search(turn.text):
            continue
        if (_ADDS.search(turn.text) or _TRIMS.search(turn.text)) and any(
            earlier.kind == "outline" for earlier in since[:at]
        ):
            return True
        if _COUNT_SAID.search(_GRADE_NUMBER.sub("", turn.text)):
            return False
    return False


# *"lớp 7"*, *"khối 11"*: số ấy là khối, không phải số câu (`_count_said`).
_GRADE_NUMBER = re.compile(r"\b(?:lớp|khối)\s*\d+", re.IGNORECASE)
# Lời bớt câu khỏi một dàn ý: *"bớt 1 câu"*, *"bỏ 2 câu"* (`_count_said`).
_TRIMS = re.compile(r"\b(?:bớt|bỏ)\s+\d+\s+câu\b", re.IGNORECASE)


def _miscounted(step: NextStepCompleted, known: str, request: NextStepRequested) -> str:
    """Vì sao số câu của một dàn ý không khớp việc được nhờ; rỗng khi khớp. Hàm thuần.

    Đối chiếu với chính thứ model đã ghi: `question_count=N` trong `known` (quy trình `soan-de` bắt
    ghi nó). `known` không có số câu -- Haiku hay để trống nó từ lượt thứ hai -- thì đối chiếu với
    số câu giáo viên đã nói kể từ plan gần nhất (plan `backlog-tier-1`, pha 1: *Mất số câu sau một
    lượt hỏi lại*: xin 5
    câu, hỏi lại một lượt, dàn ý ra 10). Không ai nói thì không đối chiếu -- BE vẫn chặn quá mười
    câu. Thay câu thì đúng một mục một câu, vì dàn ý ấy chỉ dành cho đúng câu bị thay.

    Args:
        step: Dàn ý model nêu.
        known: Ghi chú `known` của lần trả lời ấy.
        request: Lượt đang hỏi, để đọc lời giáo viên.

    Returns:
        Lý do, hoặc chuỗi rỗng.
    """
    total = sum(item.questions for item in step.outline)
    if str(step.tool_args.get("for") or "") == "replace":
        if len(step.outline) != 1 or total != 1:
            return f"replace outline has {len(step.outline)} item(s), {total} question(s)"
        return ""
    if _count_revised(request):
        return ""
    found = _COUNT_IN_KNOWN.search(known)
    if found:
        if int(found.group(1)) != total:
            return f"outline totals {total}, known says {found.group(1)}"
        return ""
    said = _count_said(request)
    if said is not None and said != total:
        return f"outline totals {total}, the teacher asked for {said}"
    return ""
