"""Đọc lịch sử đoạn chat từ plan gần nhất: đã gọi gì, đã đọc bảng nào, tài liệu nào."""

from agent.graphs.propose.proposal import nfc
from contracts import NextStepRequested, TurnRecord


def called_since_plan(request: NextStepRequested, tool: str, args: dict[str, object]) -> bool:
    """`tool` đã được gọi với đúng `args` (so bằng chữ) từ plan gần nhất chưa. Hàm thuần."""
    wanted = {key: str(value) for key, value in args.items()}
    return any(
        turn.kind == "tool_call"
        and turn.tool_name == tool
        and {key: str(value) for key, value in turn.tool_args.items()} == wanted
        for turn in since_plan(request)
    )


def picked_document(request: NextStepRequested) -> str:
    """`document_id` của tài liệu giáo viên vừa chọn: câu mới nhất của họ, đến **sau** kết quả
    `list_documents`, trùng đúng một `label` trong đó (nút BE bày gửi đúng chữ ấy). Rỗng khi
    không. Hàm thuần."""
    listed = listed_documents(request)
    if not listed:
        return ""
    turns = since_plan(request)
    answered = next(
        (turn for turn in reversed(turns) if turn.kind in {"teacher", "tool_result"}), None
    )
    if answered is None or answered.kind != "teacher":
        return ""
    said = nfc(answered.text).strip().casefold()
    matched = [
        str(one.get("document_id") or "")
        for one in listed
        if nfc(str(one.get("label") or "")).strip().casefold() == said
    ]
    return matched[0] if len(matched) == 1 and matched[0] else ""


def listed_documents(request: NextStepRequested) -> list[dict] | None:
    """`candidates` của `list_documents` gần nhất từ plan gần nhất, khi sau nó **chưa** đọc mục
    lục nào; `None` khi không có hay đã đọc. Hàm thuần."""
    for turn in reversed(since_plan(request)):
        if turn.kind == "tool_result" and turn.tool_name in {"list_chapters", "get_chapter"}:
            return None
        if turn.kind == "tool_result" and turn.tool_name == "list_documents":
            listed = turn.tool_result.get("candidates")
            if not isinstance(listed, list):
                return []
            return [one for one in listed if isinstance(one, dict)]
    return None


def tables_read(request: NextStepRequested) -> set[str]:
    """`document_id` của các tài liệu đã đọc mục lục (`list_chapters`, `get_chapter`) từ plan gần
    nhất. Đọc lượt `tool_call`: lượt `tool_result` không chở tham số. Một lời gọi trả lỗi
    (`document_id` bịa) vẫn tính -- gọi lại cũng ra đúng lỗi ấy. Hàm thuần."""
    return {
        str(turn.tool_args.get("document_id") or "").strip()
        for turn in since_plan(request)
        if turn.kind == "tool_call" and turn.tool_name in {"list_chapters", "get_chapter"}
    }


def telling(request: NextStepRequested) -> bool:
    """Lần hỏi này là lượt kể lại sau plan (ADR-25, hậu ký 22/10/2026). Hàm thuần.

    BE hỏi lượt ấy với `plannable` rỗng, ngay sau các bước pha 2 của **chính lượt này**: có một dòng
    `plan` sau lời giáo viên gần nhất. Pha 1 thì luôn có `plannable`.
    """
    if request.plannable:
        return False
    for turn in reversed(request.history):
        if turn.kind == "teacher":
            return False
        if turn.kind == "plan":
            return True
    return False


# Skill kể lại một plan, theo tool plan ấy đã chạy (plan `tao-lop`, 27/10/2026). Tool không có ở đây
# thì kể theo `soan-de`, như trước khi có tool ghi nào khác ngoài soạn đề.
_TELLS = {"create_class": "lop-va-ket-qua"}
_DRAFTING = "soan-de"


def telling_skills(request: NextStepRequested) -> frozenset[str]:
    """Các skill dặn cách kể lại plan vừa chạy: skill của mọi tool trong plan ấy. Hàm thuần.

    Lượt kể lại từng luôn nạp `soan-de`, vì đó là skill duy nhất nêu plan. Plan tạo lớp mà kể bằng
    bước 6 của `soan-de` thì model nói về đề và câu đang soạn cho một việc không có đề nào. Plan vừa
    tạo lớp vừa soạn đề thì cần cả hai (review plan `tao-lop`).

    Args:
        request: Lượt kể lại (`telling` đúng).

    Returns:
        Tên các skill; `soan-de` khi plan chưa có bước nào chạy.
    """
    told = {
        _TELLS.get(turn.tool_name, _DRAFTING)
        for turn in since_plan(request)
        if turn.kind == "tool_result"
    }
    return frozenset(told or {_DRAFTING})


def since_plan(request: NextStepRequested) -> list[TurnRecord]:
    """Các lượt từ sau plan gần nhất, cũ nhất trước. Hàm thuần."""
    turns: list[TurnRecord] = []
    for turn in reversed(request.history):
        if turn.kind == "plan":
            break
        turns.append(turn)
    return turns[::-1]
