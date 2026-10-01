"""Lượt kèm học sinh: trợ lý nói gì tiếp theo, viết ra ngay lúc được đọc.

Hai luật từ các decision record định hình prompt này nhiều hơn bất kỳ lựa chọn câu
chữ nào:

- **Trợ lý giải thích, nó không bao giờ kết luận.** Không điểm, không "em đã hiểu
  rồi", không phán xét xem việc chữa lỗi có nên dừng. Những thứ đó là điểm, và điểm
  thuộc về BE (ADR-16, ADR-20). Một lượt mà đi chấm sẽ đặt cùng một quyết định ở hai
  chỗ.
- **Cái lỗi đã có tên sẵn.** Mỗi distractor mang một error label do người soạn viết
  (ADR-18). Trợ lý dùng đúng cái label ấy chứ không tự chẩn đoán lại từ đầu, nhờ vậy
  học sinh nghe đúng lời giải thích giáo viên đã viết, và hai học sinh mắc cùng một
  lỗi thì nghe cùng một điều.

Graph có hai node vì phần dựng prompt đáng được đọc riêng: những gì trợ lý được cho
biết về học sinh chính là phần một con người sẽ muốn sửa, và nó không nên bị chôn bên
trong lời gọi lo việc stream.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from agent import llm
from contracts import ExplainTurnRequested, GeneratedQuestion

Publish = Callable[[str], Awaitable[None]]

_SYSTEM = """Bạn là Kriky, trợ lý học tập của một học sinh trung học Việt Nam vừa nộp bài kiểm tra.

Việc của bạn là giải thích, không phải chấm. Tuyệt đối không nói điểm, không nói được mấy phần,
không kết luận rằng người hỏi đã hiểu rồi hay chưa — những điều đó do hệ thống quyết định.

Cách nói:
- Xưng "mình", gọi người đối diện là "bạn". Không gọi là "em". Thân mật, ngắn, không lên lớp.
- Mỗi lượt trả lời tối đa khoảng năm câu. Người đọc đang nhìn màn hình, không đọc sách giáo khoa.
- Gọi đúng số câu như trong đề. Nếu bạn ấy hỏi "câu 5" thì nói về câu 5.
- Khi bạn ấy hỏi vì sao sai, hãy dùng đúng cái tên lỗi đã ghi sẵn cho phương án bạn ấy chọn,
  rồi mới giảng. Đừng tự chẩn đoán một lỗi khác.
- Viết toán bằng ký hiệu Unicode thông thường: y = x³ − 3x, (−∞; −1), √2. Tuyệt đối không dùng
  LaTeX, không dùng \\( \\), không dùng $ $ — màn hình hiển thị chữ thuần và ký hiệu LaTeX sẽ hiện
  ra nguyên xi.
- Viết văn xuôi thuần, không Markdown: không **in đậm**, không *nghiêng*, không `mã`, không đầu
  dòng bằng - hay *. Cùng một lý do — màn hình in đúng những ký tự bạn gõ.
- Không bịa thêm câu hỏi mới, không hứa hẹn điểm số."""


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


def _compose(state: ExplainState) -> dict:
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

    messages: list[BaseMessage] = [SystemMessage(_SYSTEM), HumanMessage(briefing)]
    for turn in request.history:
        messages.append(HumanMessage(turn.text) if turn.role == "student" else AIMessage(turn.text))

    # Không còn nhánh nào cho lịch sử rỗng nữa: BE tự viết lượt mở đầu và không bao
    # giờ đẩy một job cho nó, vì làm vậy là trả tiền cho một model để sinh ra một câu
    # gần như không thay đổi.
    if request.student_text:
        messages.append(HumanMessage(request.student_text))

    return {"messages": messages}


async def _speak(state: ExplainState, config: RunnableConfig) -> dict:
    """Gọi model và publish câu trả lời từng mẩu một.

    Args:
        state: Mang theo các message đã dựng.
        config: `configurable.publish` là một awaitable nhận một mẩu chữ. Nó đi theo
            đường này chứ không đi trong state, vì nó là một connection đang sống, còn
            state thì vốn để chứa dữ liệu.

    Returns:
        Mảnh `text` của state: cả câu trả lời, đã nối lại.
    """
    publish: Publish | None = (config.get("configurable") or {}).get("publish")
    model = llm.with_fallback(lambda chat: chat)

    pieces: list[str] = []
    async for chunk in model.astream(state["messages"]):
        piece = chunk.text if isinstance(chunk.text, str) else str(chunk.content)
        if not piece:
            continue
        pieces.append(piece)
        if publish is not None:
            await publish(piece)

    return {"text": "".join(pieces)}


def _build() -> object:
    """Lắp graph.

    Returns:
        Một graph đã compile, nhận `ExplainState` và điền vào `text`.
    """
    graph = StateGraph(ExplainState)
    graph.add_node("compose", _compose)
    graph.add_node("speak", _speak)
    graph.set_entry_point("compose")
    graph.add_edge("compose", "speak")
    graph.add_edge("speak", END)
    return graph.compile()


_GRAPH = _build()


async def speak(request: ExplainTurnRequested, publish: Publish | None = None) -> str:
    """Viết lượt nói tiếp theo của trợ lý.

    Args:
        request: Mọi thứ trợ lý được phép biết.
        publish: Được gọi với từng mẩu chữ ngay khi mẩu đó tới. None khi không ai
            đang xem, và đó là trường hợp bình thường của một job mà client đã bỏ đi.

    Returns:
        Cả câu trả lời. Bên gọi lưu thứ này; các mẩu chỉ dành cho mắt học sinh trong
        lúc chờ.
    """
    final = await _GRAPH.ainvoke(
        {"request": request, "messages": [], "text": ""},
        config={"configurable": {"publish": publish}},
    )
    return final["text"]
