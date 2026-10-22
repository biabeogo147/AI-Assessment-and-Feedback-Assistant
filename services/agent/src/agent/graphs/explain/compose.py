"""Dựng những message model đọc từ một lượt kèm học."""

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from agent.graphs.explain.prompt import SYSTEM
from contracts import ExplainTurnRequested, GeneratedQuestion


class ExplainState(TypedDict):
    """Những gì chảy qua graph.

    Attributes:
        request: Toàn bộ yêu cầu, mang theo để node dựng prompt có đủ mọi thứ.
        messages: Những gì model được đưa, sau khi đã dựng xong.
        text: Câu trả lời, dồn lại dần theo dòng stream.
    """

    request: ExplainTurnRequested
    messages: Annotated[list[BaseMessage], lambda old, new: new]
    text: str


def compose(state: ExplainState) -> dict:
    """Biến request thành những message model thấy.

    Args:
        state: Mang theo request.

    Returns:
        Mảnh `messages` của state.
    """
    request = state["request"]
    numbers = request.question_numbers or tuple(range(1, len(request.questions) + 1))

    blocks = [
        _describe(
            question,
            number,
            request.chosen_labels.get(question.stem, ""),
            request.error_labels.get(question.stem, ""),
        )
        for question, number in zip(request.questions, numbers, strict=False)
    ]
    briefing = "Những câu em làm sai trong bài vừa rồi:\n\n" + "\n\n".join(blocks)

    messages: list[BaseMessage] = [SystemMessage(SYSTEM), HumanMessage(briefing)]
    for turn in request.history:
        messages.append(HumanMessage(turn.text) if turn.role == "student" else AIMessage(turn.text))

    # Không còn nhánh nào cho lịch sử rỗng nữa: BE tự viết lượt mở đầu và không bao
    # giờ đẩy một job cho nó, vì làm vậy là trả tiền cho một model để sinh ra một câu
    # gần như không thay đổi.
    if request.student_text:
        messages.append(HumanMessage(request.student_text))

    return {"messages": messages}


def _describe(question: GeneratedQuestion, number: int, chosen: str, mistake: str) -> str:
    """Viết một câu làm sai ra để trợ lý đọc.

    Args:
        question: Câu hỏi, kèm các phương án và các cách giải.
        number: Số câu mà đề gọi nó, để trợ lý nói "câu 5" chứ không nói "câu 1" (các
            câu làm sai hiếm khi được đánh số từ một).
        chosen: Nhãn phương án học sinh đã chọn, rỗng khi em không chọn gì.
        mistake: Tên của lỗi đó do người soạn viết, rỗng khi không rõ.

    Returns:
        Một khối chữ thuần.
    """
    correct = next((option for option in question.options if option.is_correct), None)
    lines = [f"Câu {number}: {question.stem}"]
    for option in question.options:
        lines.append(f"  {option.label}. {option.text}")
    if chosen:
        lines.append(f"  Em đã chọn: {chosen}" + (f" — lỗi: {mistake}" if mistake else ""))
    else:
        lines.append("  Em không chọn phương án nào.")
    if correct is not None:
        lines.append(f"  Đáp án đúng: {correct.label}. {correct.text}")
    for method in question.methods:
        lines.append(f"  Cách giải — {method.title}: {method.body}")
    return "\n".join(lines)
