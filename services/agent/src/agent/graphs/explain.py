"""The tutoring turn: what the assistant says next, written as it is read.

Two rules from the decision records shape the prompt more than any wording
choice does:

- **The assistant explains, it never concludes.** No score, no "em đã hiểu
  rồi", no verdict on whether remediation should end. Those are marks, and
  marks belong to BE (ADR-16, ADR-20). A turn that graded would put the same
  decision in two places.
- **The mistake already has a name.** Every distractor carries an authored
  error label (ADR-18). The assistant uses that label rather than diagnosing
  from scratch, so the student hears the same explanation the teacher wrote
  and two students who made the same mistake hear the same thing.

The graph is two nodes because the composing is worth reading on its own: what
the assistant is told about the student is the part a person will want to
change, and it should not be buried inside the call that streams.
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

Việc của bạn là giải thích, không phải chấm. Tuyệt đối không nói điểm, không nói em được mấy phần,
không kết luận rằng em đã hiểu rồi hay chưa — những điều đó do hệ thống quyết định, không phải bạn.

Cách nói:
- Xưng "mình", gọi người đối diện là "bạn". Không gọi là "em". Thân mật, ngắn, không lên lớp.
- Mỗi lượt trả lời tối đa khoảng năm câu. Em đang đọc trên màn hình, không đọc sách giáo khoa.
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
    """What flows through the graph.

    Attributes:
        request: The whole ask, carried so the composing node has everything.
        messages: What the model is given, once composed.
        text: The answer, accumulated as it streams.
    """

    request: ExplainTurnRequested
    messages: Annotated[list[BaseMessage], lambda old, new: new]
    text: str


def _describe(question: GeneratedQuestion, number: int, chosen: str, mistake: str) -> str:
    """Write one wrong question out for the assistant to read.

    Args:
        question: The question, with its options and worked solutions.
        number: What the paper calls it, so the assistant says "câu 5" and not
            "câu 1" (the wrong questions are rarely numbered from one).
        chosen: Label the student picked, empty when they answered nothing.
        mistake: The authored name of that mistake, empty when unknown.

    Returns:
        A block of plain text.
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
    """Turn the request into the messages the model sees.

    Args:
        state: Carries the request.

    Returns:
        The `messages` slice of the state.
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

    if not request.history:
        # The opening turn. It says hello and names what it can help with, then
        # stops: ADR-14 gives the student the next move, and an assistant that
        # launches into explaining question five has taken it away.
        opening = (
            "Hãy chào em bằng đúng câu này, không thêm không bớt, rồi liệt kê các câu em làm sai "
            "và mời em hỏi câu nào trước cũng được. Không giải thích gì thêm ở lượt này: "
            "'Mình là trợ lý Kriky, bạn có thể hỏi mình để giải đáp các thắc mắc trong bài làm "
            "vừa rồi.'"
        )
        messages.append(HumanMessage(opening))
    elif request.student_text:
        messages.append(HumanMessage(request.student_text))

    return {"messages": messages}


async def _speak(state: ExplainState, config: RunnableConfig) -> dict:
    """Call the model and publish the answer piece by piece.

    Args:
        state: Carries the composed messages.
        config: `configurable.publish` is an awaitable taking one piece of
            text. It travels here rather than in the state because it is a live
            connection, and state is meant to be data.

    Returns:
        The `text` slice of the state: the whole answer, joined.
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
    """Assemble the graph.

    Returns:
        A compiled graph taking `ExplainState` and filling in `text`.
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
    """Write the assistant's next turn.

    Args:
        request: Everything the assistant is allowed to know.
        publish: Called with each piece of text as it arrives. None when
            nobody is watching, which is the normal case for a job whose
            client has gone away.

    Returns:
        The whole answer. The caller stores this; the pieces were only for the
        student's eyes while waiting.
    """
    final = await _GRAPH.ainvoke(
        {"request": request, "messages": [], "text": ""},
        config={"configurable": {"publish": publish}},
    )
    return final["text"]
