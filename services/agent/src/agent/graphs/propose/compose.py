"""Node 1 của graph: dựng các message gửi model từ lịch sử và skill."""

import json
from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from agent import skills
from agent.graphs.propose.books import book_in_view, opens_library
from agent.graphs.propose.prompt import BOOK_PROCEDURE, CORE, LIBRARY, LIBRARY_SLOT
from contracts import NextStepCompleted, NextStepRequested, ToolSpec, TurnRecord


class ProposeState(TypedDict):
    """Những gì chảy qua hai node.

    Attributes:
        request: Cuộc hội thoại và danh mục tool.
        skills: Tên các skill nạp cho lượt này, do `skill_router` chọn trước khi graph chạy.
        messages: Những gì model thấy, do `compose` điền.
        step: Đề nghị, do `choose` điền.
        hint: Lý do của lần hỏi lại, `compose` đặt nó cuối cùng như một ghi chú hệ thống; rỗng ở
            lần đầu (`AskAgain.hint`).
    """

    request: NextStepRequested
    skills: tuple[str, ...]
    messages: Annotated[list[BaseMessage], lambda old, new: new]
    step: NextStepCompleted | None
    hint: NotRequired[str]


def compose(state: ProposeState) -> dict:
    """Biến request thành những message model thấy.

    Lịch sử hội thoại trở thành các message theo đúng thứ tự. Một lần gọi tool và kết
    quả của nó là nước đi của chính trợ lý và thứ nhận lại được từ nước đi đó, nên
    chúng được render thành một lượt assistant và một lượt human -- đó là hình dạng
    một chat model mong đợi, và là lý do model không đề nghị cùng một tool hai lần.

    Args:
        state: Mang theo request.

    Returns:
        Mảnh `messages` của state.
    """
    request = state["request"]

    # Lõi trước, rồi skill, rồi tên giáo viên: phần đứng đầu càng ít đổi giữa hai lượt thì prompt
    # cache của provider càng dùng lại được nhiều. Skill nằm **sau** lõi, nên không skill nào nói
    # trước được một luật an toàn.
    opening = [CORE]
    library = opens_library(request, state["skills"])
    # Một hàm chứ không một chuỗi thay thế: `re.sub` đọc `\` trong chuỗi thay thế như escape, và một
    # ngày `LIBRARY` có dấu `\` (LaTeX) thì chuỗi ấy hỏng lặng lẽ (review T2b,
    # `unbiased-model-text`).
    for skill in skills.named(state["skills"]):
        opening.append(
            LIBRARY_SLOT.sub(
                lambda slot: f"{slot.group(1)}{LIBRARY}\n" if library else "", skill.body
            )
        )
    if request.teacher_name:
        opening.append(f"Bạn đang nói với {request.teacher_name}.")
    if request.attached_document is not None:
        # `draft-from-document`: tài liệu của đoạn chat -- chip của câu này, hoặc chip gần nhất. Id
        # viết ra nguyên văn vì model gửi lại nó làm tham số `document_id`.
        document = request.attached_document
        if document.state == "ready":
            opening.append(
                f"Tài liệu giáo viên đính kèm: {document.filename} "
                f"(document_id = {document.document_id})."
            )
        elif document.state == "processing":
            # Tệp vừa tải lên, còn đang xử lý (review B6, `draft-from-document`): chưa có mục lục để
            # đọc. Nói ra, thay vì soạn như thể không có chip -- giáo viên đang nghĩ đề sẽ theo sách
            # này.
            opening.append(
                f"Tài liệu giáo viên đính kèm: {document.filename} -- đang xử lý, chưa đọc "
                "được. Nếu giáo viên nhờ soạn đề từ tài liệu này, nói rằng cần chờ tài liệu "
                "sẵn sàng rồi gửi lại; đừng soạn đề không tài liệu thay cho nó."
            )
        else:
            # Hỏng, hay không đọc được chữ (review B7, `draft-from-document`): chờ cũng không ra gì
            # -- bảo chờ là kẹt đoạn chat ở một lời hứa không ai giữ.
            opening.append(
                f"Tài liệu giáo viên đính kèm: {document.filename} -- KHÔNG đọc được nội dung. "
                "Nếu giáo viên nhờ soạn đề từ tài liệu này, nói rằng tài liệu này không dùng "
                "được và nhờ họ đính tài liệu khác; đừng soạn đề không tài liệu thay cho nó."
            )
    if book_in_view(request):
        opening.append(BOOK_PROCEDURE)
    if request.catalog:
        catalog = "\n".join(_describe_tool(tool) for tool in request.catalog)
        opening.append(f"Tool dùng ngay (call_tool) lượt này:\n{catalog}")
    else:
        # Nói ra điều đó tốt hơn bỏ hẳn phần này: một model không được cấp danh
        # sách nào thường cho rằng việc thiếu đó là sơ suất và vẫn gọi tên một tool.
        opening.append("Lượt này bạn không có tool dùng ngay nào.")
    if request.plannable:
        # Hai danh sách tới riêng, vì model phải phân biệt được "gọi được bây giờ" với "hẹn làm ở
        # pha sau". Trộn chúng lại là mời model gọi một tool ghi ngay lượt này -- BE từ chối, và
        # cái vòng lặp tiêu một lần gọi model để phát hiện lại đúng điều ấy.
        planning = "\n".join(_describe_tool(tool) for tool in request.plannable)
        opening.append(f"Tool nêu được trong plan (không gọi ngay):\n{planning}")
    else:
        # Không nhắc `call_tool` ở đây: khi `catalog` cũng rỗng thì dòng trên vừa nói là
        # không có tool nào, và một câu mời gọi tool ngay sau đó là một lời tự mâu thuẫn --
        # đúng loại chỗ model chọn câu nào nghe tích cực hơn.
        can_also = ", call_tool" if request.catalog else ""
        opening.append(f"Lượt này bạn không nêu plan được. Chỉ say{can_also} hoặc ask_clarify.")

    messages: list[BaseMessage] = [SystemMessage("\n\n".join(opening))]
    for turn in request.history:
        if turn.kind == "teacher":
            messages.append(HumanMessage(turn.text))
        elif turn.kind == "assistant":
            messages.append(AIMessage(_asked_back(turn)))
        elif turn.kind == "tool_call":
            args = json.dumps(turn.tool_args, ensure_ascii=False, sort_keys=True)
            messages.append(AIMessage(f"Mình xin gọi {turn.tool_name} với {args}."))
        elif turn.kind == "notice":
            # Thông báo của hệ thống (ADR-30, ngoại lệ 1): không phải lời model đã nói.
            messages.append(HumanMessage(f"(Ghi chú của hệ thống, giáo viên đã thấy: {turn.text})"))
        elif turn.kind == "outline":
            messages.append(AIMessage(turn.text))
            items = _outline_items(turn)
            if items:
                messages.append(HumanMessage(items))
        else:
            messages.append(HumanMessage(_describe_result(turn)))
    if state.get("hint"):
        messages.append(HumanMessage(f"(Ghi chú của hệ thống: {state['hint']})"))

    return {"messages": messages}


def _describe_tool(tool: ToolSpec) -> str:
    """Viết một tool ra để model chọn.

    Args:
        tool: Tool đúng như BE mô tả nó.

    Returns:
        Một khối gọi tên tool chính xác như cách BE dispatch, rồi tới việc nó làm,
        rồi tới các argument của nó.
    """
    lines = [f"- {tool.name}: {tool.description}"]
    for argument, meaning in tool.arguments.items():
        mark = " (tùy chọn)" if argument in tool.optional else ""
        lines.append(f"    {argument}{mark}: {meaning}")
    return "\n".join(lines)


def _asked_back(turn: TurnRecord) -> str:
    """Lời của một lượt Kriky trong lịch sử, kèm các câu nếu đó là lượt hỏi nhiều câu (ADR-32).
    Hàm thuần.

    Câu trả lời gộp của giáo viên (*"Khối: Khối 7 · Số câu: 5 câu"*) chỉ đọc được khi model thấy lại
    chính các câu nó đã hỏi; lời mở một mình không nói câu nào hỏi gì.
    """
    asked = (turn.tool_result or {}).get("questions")
    if not isinstance(asked, list) or not asked:
        return turn.text
    lines = [turn.text.strip()] if turn.text.strip() else []
    for index, one in enumerate(asked, start=1):
        if not isinstance(one, dict):
            continue
        choices = "; ".join(str(choice) for choice in one.get("choices") or [])
        lines.append(
            f"{index}. {one.get('label', '')}: {one.get('text', '')} (lựa chọn: {choices})"
        )
    return "\n".join(lines)


def _outline_items(turn: TurnRecord) -> str:
    """Các mục của một lượt dàn ý trong lịch sử, như một ghi chú của hệ thống (`draft-outline`). Hàm
    thuần.

    Sửa dàn ý là nêu lại **đủ** mục, và `source_nodes` chỉ chép lại được khi nó còn nằm đâu đó. Ghi
    chú đi **riêng** khỏi lời Kriky -- một tin nhắn của phía người dùng, không nối vào lời của chính
    model: từ ADR-30 lời ấy là cả dàn ý, và một khối JSON nằm trong lời mình vừa nói là thứ model dễ
    chép lại vào lời sau (review pha 4, `kriky-writes-every-word`). Dàn ý đã bị thay thì BE chỉ gửi
    số bản (`teacher_chat._shrunk`), và không có ghi chú nào.

    Returns:
        Ghi chú các mục, hoặc chuỗi rỗng khi lượt không còn mục.
    """
    kept = turn.tool_result or {}
    if not kept.get("items"):
        return ""
    compact = json.dumps(
        {key: kept.get(key) for key in ("version", "for", "first", "items")},
        ensure_ascii=False,
        sort_keys=True,
    )
    return f"(Ghi chú của hệ thống, giáo viên không thấy: các mục của dàn ý vừa rồi — {compact})"


def _describe_result(turn: TurnRecord) -> str:
    """Viết kết quả tool ra dưới dạng dữ liệu, không phải một câu kể về dữ liệu.

    JSON chứ không phải văn xuôi, vì model phải đọc các giá trị ra từ đó -- một id nó
    sẽ truyền cho tool tiếp theo, một con số nó sẽ dẫn lại cho giáo viên. Văn xuôi mời
    gọi việc làm tròn và mời gọi việc bịa.

    Args:
        turn: Một lượt `tool_result`.

    Returns:
        Một dòng gọi tên tool, rồi kết quả của nó dưới dạng JSON.
    """
    body = json.dumps(turn.tool_result, ensure_ascii=False, sort_keys=True)
    return f"Kết quả của {turn.tool_name}:\n{body}"
