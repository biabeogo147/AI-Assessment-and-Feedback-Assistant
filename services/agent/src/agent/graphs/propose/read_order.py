"""Luật thứ tự đọc: đề nghị đúng việc mà sai bước thì thành một lời gọi tool đọc."""

import logging
import re
import unicodedata

from agent.graphs.propose.ask_again import WrongQuestion
from agent.graphs.propose.books import DOCUMENT_READS, book_in_view, opens_library
from agent.graphs.propose.history import (
    called_since_plan,
    listed_documents,
    picked_document,
    since_plan,
    tables_read,
)
from contracts import NextStepCompleted, NextStepRequested, TurnRecord

logger = logging.getLogger("agent.graphs.propose")


# Câu hỏi lại ngay sau `list_documents` (`unbiased-model-text` T5, review T5 hướng ii). Nút của câu
# ấy luôn là tên tài liệu -- BE coi câu hỏi đến sau một danh sách `candidates` là câu hỏi về dòng
# (ADR-23) -- mà chữ model viết lệch nút 5--17/24 lượt (*"phần mệnh đề nằm ở mục nào?"*, run-83,
# run-87).
# Câu hỏi hỏi **tài liệu nào**: *"bạn soạn theo tài liệu nào?"*, *"cuốn sách giáo khoa nào?"*,
# *"tài liệu Toán 10 gì?"* -- tối đa ba chữ chen giữa. Chữ "sách" một mình thì không: *"phần mệnh
# đề nằm ở mục nào của cuốn sách?"* là đúng ca lệch đã đo (run-83, run-87). Dấu Markdown bỏ trước
# khi so (review pha 5, `kriky-writes-every-word`): từ ADR-30 *"**tài liệu** nào"* là chữ hợp lệ.
_ASKS_WHICH_BOOK = re.compile(
    r"\b(?:tài liệu|giáo trình|cuốn|quyển|sách|tệp|file)(?:\s+\S+){0,3}?\s+(?:nào|gì)\b", re.I
)


_MARKUP = re.compile(r"[*_`]")


def reads_first(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Plan mở đầu bằng một tool chỉ gọi được ngay -- không nêu được trong plan -- là lời gọi tool
    ấy, chưa phải plan. Hàm thuần.

    Đo ở `unbiased-model-text` T5: giáo viên nhắc sách mà không đính kèm và nói đủ bốn mục (*"Lấy
    cuốn Toán 10 mình mới tải lên, ra 8 câu phần mệnh đề"*) thì nhánh *"không còn ? → nêu plan
    ngay"* thắng dòng mở thư viện: 16/24 lượt model nêu plan `list_documents → create_draft →
    start_drafting` -- biết phải mở thư viện, chỉ chọn sai `kind` -- và BE từ chối cả plan
    (`list_documents` không có trong catalog pha thực hiện), giáo viên nhận câu lùi. Bản đã commit
    12/24 gọi tool, bản hiện tại trước luật này 4/24. Đổi chữ đã thua nhiều lần ở chính chỗ này
    (T2b, T3); đây là cấu trúc. Các bước sau bị bỏ: ở bước kế trong cùng vòng gọi tool của BE, model
    đọc kết quả rồi nêu lại plan.

    Args:
        step: Đề nghị model vừa nêu.
        request: Request lượt này, mang hai danh sách tool.

    Returns:
        `call_tool` cho bước đầu khi bước ấy là tool `catalog` mà không phải tool `plannable`, và
        chưa được gọi với đúng tham số ấy từ plan gần nhất (review T5: không thì BE hỏi lại tới trần
        `max_tool_steps` rồi báo lỗi); không thì chính `step`.
    """
    if step.kind != "plan":
        return step
    first = step.steps[0]
    callable_now = {tool.name for tool in request.catalog}
    plannable = {tool.name for tool in request.plannable}
    if first.tool_name not in callable_now or first.tool_name in plannable:
        return step
    if called_since_plan(request, first.tool_name, first.args):
        return step
    logger.info("plan opens with %s, a read -- calling it first", first.tool_name)
    return NextStepCompleted(
        request_id=step.request_id,
        kind="call_tool",
        tool_name=first.tool_name,
        tool_args=dict(first.args),
        model_tokens=step.model_tokens,
    )


def picked_book_first(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Giáo viên vừa chọn một tài liệu trong danh sách: đọc mục lục của nó, bằng code. Hàm thuần.

    Đo ở `unbiased-model-text` T5: sau khi giáo viên bấm tên cuốn, model tự gọi `list_chapters` 0/24
    lượt (run-87; 20/24 lượt đạt đều do `toc_first`), còn lại nêu plan -- có lúc `nodes` bịa, có
    lúc không `document_id` (âm thầm soạn đề không sách). Giáo viên đã chọn, nên đây không phải chọn
    hộ; và không còn phụ thuộc model ở đúng bước model hỏng (review T5, hướng iii).

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.

    Returns:
        `call_tool list_chapters` cho tài liệu vừa chọn khi mục lục của nó chưa đọc và `step` chưa
        tự đọc nó; không thì chính `step`.
    """
    if request.attached_document is not None:
        return step
    if not any(tool.name == "list_chapters" for tool in request.catalog):
        return step
    picked = picked_document(request)
    if not picked or picked in tables_read(request):
        return step
    if (
        step.kind == "call_tool"
        and step.tool_name in {"list_chapters", "get_chapter"}
        and str(step.tool_args.get("document_id") or "").strip() == picked
    ):
        return step
    logger.info("teacher picked %s -- reading its chapters", picked)
    return NextStepCompleted(
        request_id=step.request_id,
        kind="call_tool",
        tool_name="list_chapters",
        tool_args={"document_id": picked},
        model_tokens=step.model_tokens,
    )


def misfiled_read(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Câu hỏi lại ngay sau `list_documents` mà mang `list_chapters` của một tài liệu trong danh
    sách là lời gọi ấy, nộp nhầm `kind`. Hàm thuần.

    Đo ở `unbiased-model-text` T5 (run-88): ngay sau `list_documents`, 16/24 lượt model chọn
    `ask_clarify` mà điền `tool_name=list_chapters` với `document_id` của một tài liệu trong danh
    sách (15 lượt là cuốn Lớp 10 giáo viên nhắc) -- nó đã chọn sách, chỉ chọn sai `kind`. Bản đã
    commit tự gọi `list_chapters` 17/24: đây là trả lại đúng lựa chọn của model, không phải code
    chọn hộ. Hẹp có chủ ý: câu hỏi về khối mang `tool_name=list_class` (`thieu-khoi-co-so-cau`, 9
    lượt đúng) và câu hỏi chương mang `list_chapters` **sau** khi đã đọc mục lục
    (`tai-lieu-khong-khop`, 36 lượt đúng) là câu hỏi thật.

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.

    Returns:
        `call_tool list_chapters` khi điều kiện trên đúng và tài liệu ấy chưa đọc mục lục; không thì
        chính `step`.
    """
    if step.kind != "ask_clarify" or step.tool_name != "list_chapters":
        return step
    if request.attached_document is not None:
        return step
    if not any(tool.name == "list_chapters" for tool in request.catalog):
        return step
    listed = listed_documents(request) or []
    document = str(step.tool_args.get("document_id") or "").strip()
    if not document or document not in {str(one.get("document_id") or "") for one in listed}:
        return step
    if document in tables_read(request):
        return step
    logger.info("question names list_chapters of %s -- calling it", document)
    return NextStepCompleted(
        request_id=step.request_id,
        kind="call_tool",
        tool_name="list_chapters",
        tool_args={"document_id": document},
        model_tokens=step.model_tokens,
    )


def toc_first(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Plan tạo đề theo một tài liệu chưa đọc mục lục là lời gọi `list_chapters` của tài liệu ấy.
    Hàm thuần.

    Đo ở `unbiased-model-text` T5: không chip, giáo viên nhắc sách -- `list_documents`, hỏi *"cuốn
    này chứ?"*, giáo viên bấm tên cuốn -- rồi model nêu `create_draft` với `document_id` mà không
    đọc mục lục bao giờ. Thiếu `nodes` thì BE dừng ở bước 1; có `nodes` thì đó là số **bịa**
    (*"1,2,3"*, *"5"*: 4/24 lượt, run-87) mà BE nhận -- không chip thì `nodes` tuỳ chọn,
    `_document_scope` chỉ kiểm nút có trong cây -- và đề soạn trên mục sai. Điều kiện vì thế là
    *chưa đọc mục lục*, không phải *thiếu `nodes`* (review T5); đọc rồi thì không gọi lại, plan đi
    tiếp cho BE xét. Chỉ lượt không chip: có chip thì thủ tục sách đọc mục lục từ trước, và
    `bind_book` điền `nodes`.

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.

    Returns:
        `call_tool list_chapters` cho tài liệu của `create_draft` khi mục lục của nó chưa được đọc
        từ plan gần nhất và `list_chapters` gọi được lượt này; không thì chính `step`.
    """
    if step.kind != "plan" or request.attached_document is not None:
        return step
    if not any(tool.name == "list_chapters" for tool in request.catalog):
        return step
    read = tables_read(request)
    for one in step.steps:
        if one.tool_name != "create_draft":
            continue
        document = str(one.args.get("document_id") or "").strip()
        # `{1.document_id}` là tham chiếu tới kết quả một bước trước (ADR-25), chưa phải một id.
        if document and not document.startswith("{") and document not in read:
            logger.info("plan drafts from %s before reading its chapters -- reading them", document)
            return NextStepCompleted(
                request_id=step.request_id,
                kind="call_tool",
                tool_name="list_chapters",
                tool_args={"document_id": document},
                model_tokens=step.model_tokens,
            )
    return step


def library_first(
    step: NextStepCompleted, request: NextStepRequested, chosen: tuple[str, ...]
) -> NextStepCompleted:
    """Ở lượt có dòng mở thư viện, một câu hỏi lại hay một đề mở không tài liệu thành lời gọi
    `list_documents`. Hàm thuần.

    Dòng ấy dặn đúng điều này, và chữ không giữ được nó (`unbiased-model-text` T5): nhánh *"còn ? →
    hỏi lại"* thắng mỗi khi model suy được thêm một mục -- *"cụm suy ra môn vẫn là phạm vi"* chữa
    *"kiểm tra nhanh phần logarit"* (5 → 24/24) mà kéo `tai-lieu-khong-dinh` 24 → 16/24, model hỏi
    khối thay vì mở thư viện nơi khối nằm sẵn trong tên tài liệu.

    Chỉ hai hình dạng ấy (review T5): `_BOOK_WORDS` có lúc báo nhầm -- *"soạn thêm 5 câu, bám sát
    sách giáo khoa"* là plan `start_drafting` hợp lệ, *"xuất file Word"* không nhờ soạn theo sách --
    nên lời nói (`say`), plan không mở đề mới, và mọi lời gọi tool (`list_class`…) để nguyên.

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.
        chosen: Tên các skill Jev chọn cho lượt này.

    Returns:
        `call_tool list_documents` khi lượt mở thư viện mà `step` là `ask_clarify`, hay plan có
        `create_draft` không `document_id`; không thì `step`.
    """
    unbooked = step.kind == "plan" and any(
        one.tool_name == "create_draft" and not str(one.args.get("document_id") or "").strip()
        for one in step.steps
    )
    # Từ ADR-29 nước đi đầu là dàn ý, không phải plan: một dàn ý không trỏ về bài nào ở lượt mở thư
    # viện là dàn ý soạn không sách -- cùng lỗi, hình dạng mới (review đợt 4, `draft-outline`).
    unbooked = unbooked or (
        step.kind == "outline" and not any(item.source_nodes for item in step.outline)
    )
    if not (step.kind == "ask_clarify" or unbooked) or not opens_library(request, chosen):
        return step
    logger.info("model chose %s on a turn that opens the library -- listing first", step.kind)
    return NextStepCompleted(
        request_id=step.request_id,
        kind="call_tool",
        tool_name="list_documents",
        model_tokens=step.model_tokens,
    )


def which_book(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Câu hỏi lại ngay sau một danh sách tài liệu hỏi đúng điều nút của nó trả lời. Hàm thuần.

    Từ ADR-30 (`kriky-writes-every-word`) code không đè chữ câu hỏi bằng một câu cố định nữa: model
    hỏi sai điều thì được hỏi lại một lần, và lần hai vẫn vậy thì câu của model đi tiếp. Chỉ soi
    câu hỏi **ngay sau** danh sách: review chung sau T5 (`unbiased-model-text`) thấy bản đầu đè mọi
    câu hỏi cho tới khi đọc mục lục, kể cả sau khi giáo viên đã ghi *"thôi, không dùng sách"* qua
    lối "Khác".

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.

    Returns:
        Chính `step`.

    Raises:
        WrongQuestion: Khi `step` là `ask_clarify`, không chip, lượt **ngay trước** nó là kết quả
            một `list_documents` có ít nhất một tài liệu, mà câu hỏi không nhắc tài liệu hay sách.
    """
    if step.kind != "ask_clarify" or request.attached_document is not None:
        return step
    listed = listed_documents(request)
    if not listed:
        return step
    spoken = [turn for turn in since_plan(request) if turn.kind in {"teacher", "tool_result"}]
    last = spoken[-1] if spoken else None
    if last is None or last.kind != "tool_result" or last.tool_name != "list_documents":
        return step
    if _asks_which_book(" ".join([step.text, *(one.text for one in step.questions)]), listed):
        return step
    raise WrongQuestion("asked something else right after listing the documents", step)


def _asks_which_book(text: str, listed: list[dict]) -> bool:
    """Câu hỏi có hỏi giáo viên soạn theo tài liệu nào không. Hàm thuần.

    Hai cách hỏi đúng: một cụm *"tài liệu nào"* (`_ASKS_WHICH_BOOK`), hay nêu thẳng tên các tài liệu
    -- *"bạn dùng Toán 10.pdf hay Đại số.pdf?"*, cách hỏi tự nhiên khi nút là tên tệp.

    Args:
        text: Câu hỏi model viết.
        listed: `candidates` của `list_documents` (`label` là tên tệp).

    Returns:
        True khi câu hỏi hỏi tài liệu nào.
    """
    plain = _MARKUP.sub("", unicodedata.normalize("NFC", text))
    if _ASKS_WHICH_BOOK.search(plain):
        return True
    lowered = plain.casefold()
    names = [unicodedata.normalize("NFC", str(one.get("label") or "")).casefold() for one in listed]
    stems = [name.rsplit(".", 1)[0] if "." in name else name for name in names]
    return any(stem and stem in lowered for stem in stems)


def read_before_outline(step: NextStepCompleted, request: NextStepRequested) -> NextStepCompleted:
    """Ở lượt có sách, một dàn ý nêu khi chưa đọc chữ phạm vi thành lời gọi `read_section`.

    Hàm thuần.

    `BOOK_PROCEDURE` dặn đọc trước khi nêu dàn ý, và chữ không giữ được model (review đợt 4,
    `draft-outline`): nó chép `source_nodes` từ mục lục, BE nhận vì nút có thật, và dàn ý viết từ
    tóm tắt chứ không từ bài. Phạm vi đọc là chính các nút dàn ý trỏ tới, số câu là tổng của dàn
    ý -- model nêu lại với chữ trong tay. Đã đọc từ plan gần nhất thì để nguyên.

    Args:
        step: Đề nghị model vừa nêu.
        request: Lượt đang hỏi.

    Returns:
        `call_tool read_section` khi lượt có sách mà chưa đọc chữ; không thì `step`.
    """
    if step.kind != "outline" or not book_in_view(request):
        return step
    since = since_plan(request)
    reads = [turn for turn in since if turn.tool_name == "read_section"]
    results = [turn for turn in reads if turn.kind == "tool_result"]
    if results:
        # Đọc dở (`more`): thử tay 15/10/2026 đọc phần 1/5 của chương rồi viết dàn ý, nên dàn ý chỉ
        # phủ đầu chương. Còn phần chưa đọc thì đọc phần kế, cùng phạm vi, trước khi nêu dàn ý.
        # Chỉ phần đọc **của lượt này**, và chỉ khi dàn ý trỏ vào phạm vi ấy: một lần ngó mục khác,
        # hay lần đọc của lượt trước, không bắt đọc hết phần còn lại (review đợt 6).
        asked_at = max((at for at, turn in enumerate(since) if turn.kind == "teacher"), default=-1)
        current = [turn for turn in since[asked_at + 1 :] if turn.tool_name == "read_section"]
        calls = [turn for turn in current if turn.kind == "tool_call"]
        done = [turn.tool_result for turn in current if turn.kind == "tool_result"]
        last = done[-1] if done else {}
        sources = {node for item in step.outline for node in item.source_nodes}

        # **Cả** phạm vi đã đọc trong lượt -- mọi phần, mọi lời gọi --, không chỉ phần cuối: đọc
        # phần 3/5 xong mà dàn ý trỏ nút của phần 1–2 thì so với phần cuối không giao nhau, và
        # AGENT thôi bắt đọc tiếp dù còn hai phần (thử tay 17/10, case 04; plan `backlog-tier-1`).
        # Chỉ các lần đọc **cùng phạm vi** với lần cuối (cùng tham số, trừ `part`): đọc trọn mục B
        # rồi ngó phần 1 của mục A thì dàn ý trỏ vào B không bắt đọc tiếp A (review code pha 5).
        def scope(call: TurnRecord) -> dict:
            # Chuẩn hoá: `"1, 2"` và `"2,1"` là cùng một phạm vi (review code vòng 2).
            return {
                key: frozenset(int(one) for one in re.findall(r"\d+", str(value)))
                if key == "nodes"
                else str(value).strip()
                for key, value in call.tool_args.items()
                if key != "part"
            }

        same = [at for at, call in enumerate(calls) if calls and scope(call) == scope(calls[-1])]
        read = {int(node) for at in same if at < len(done) for node in done[at].get("nodes") or ()}
        for at in same:
            read |= {
                int(node) for node in re.findall(r"\d+", str(calls[at].tool_args.get("nodes")))
            }
        if (
            last.get("found") is True
            and last.get("more") is True
            and calls
            and (not sources or sources & read)
        ):
            asked = dict(calls[-1].tool_args)
            next_part = int(last.get("part") or 1) + 1
            logger.info(
                "model outlined after part %d of %s -- reading on", next_part - 1, last.get("parts")
            )
            return NextStepCompleted(
                request_id=step.request_id,
                kind="call_tool",
                tool_name="read_section",
                tool_args={
                    **{key: str(value) for key, value in asked.items()},
                    "part": str(next_part),
                },
                model_tokens=step.model_tokens,
            )
        return step
    nodes = sorted({node for item in step.outline for node in item.source_nodes})
    attached = request.attached_document
    document = attached.document_id if attached is not None else ""
    if not document:
        reads = [
            str(turn.tool_args.get("document_id") or "")
            for turn in since
            if turn.kind == "tool_call" and turn.tool_name in DOCUMENT_READS
        ]
        document = next((one for one in reversed(reads) if one), "")
    if not nodes or not document:
        return step
    total = min(10, sum(item.questions for item in step.outline))
    logger.info("model outlined before reading -- reading %s first", nodes)
    return NextStepCompleted(
        request_id=step.request_id,
        kind="call_tool",
        tool_name="read_section",
        tool_args={
            "document_id": document,
            "nodes": ",".join(str(node) for node in nodes),
            "questions": str(total),
            "part": "1",
        },
        model_tokens=step.model_tokens,
    )
