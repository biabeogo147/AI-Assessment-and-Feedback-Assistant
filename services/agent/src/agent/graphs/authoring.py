"""Writing a question, and refusing to hand over one that is malformed.

A loop, because this is the task that can fail its own check: the model is
asked for a question shaped a particular way and sometimes writes one that is
not. The graph tries again with the complaint attached, which is a different
thing from trying again and hoping.

**This is not where ADR-18 is enforced.** BE re-checks everything that arrives,
and `packages/contracts` says why: a generator that judged its own output would
be marking its own homework. The check here is self-QC -- it saves a round trip
and a wasted queue job, and if it ever disagreed with BE's, BE's is the one that
counts.

What the model is told about shape comes from the decision records, not from
taste: exactly one correct option, every distractor carrying the name of the
mistake it stands for, and more than one worked solution (ADR-18); and for a
remediation round, a question that tests the same thing without being the same
question (ADR-17).
"""

import logging
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from agent import llm
from contracts import DraftAssessmentRequested, GeneratedQuestion, RetryQuestionRequested

logger = logging.getLogger(__name__)

# Two tries after the first. A third has never turned a model that misread the
# shape twice into one that reads it correctly, and every attempt is a student
# waiting.
_MAX_ATTEMPTS = 3

_SYSTEM = """Bạn soạn câu hỏi trắc nghiệm cho học sinh trung học Việt Nam.

Mỗi câu bạn viết phải thoả đúng ba điều sau, không thương lượng:
- Có đúng MỘT phương án đúng. Đánh dấu nó bằng is_correct = true, các phương án còn lại là false.
- MỖI phương án sai phải kèm error_label: tên ngắn gọn của lỗi tư duy dẫn tới việc chọn nó. Ví dụ
  "đọc ngược chiều biến thiên", "quên nhân số mũ khi hạ bậc". Phương án đúng để error_label rỗng.
- Có ÍT NHẤT HAI cách giải khác nhau trong methods, mỗi cách có title ngắn và body là các bước.

Cách viết:
- Tiếng Việt, đúng văn phong đề kiểm tra phổ thông.
- Toán viết bằng ký hiệu Unicode: y = x³ − 3x, (−∞; −1), √2, ≥, ≤, →. Tuyệt đối KHÔNG dùng LaTeX,
  không \\( \\), không $ $, không \\frac.
- KHÔNG dùng Markdown: không **in đậm**, không *nghiêng*, không `mã`.
- Số liệu phải tính ra được và đáp án đánh dấu đúng phải thật sự đúng."""


class WriteState(TypedDict):
    """What flows through the loop.

    Attributes:
        brief: What to write, in words the model reads.
        banned: Stems this question must not repeat, normalised.
        question: The latest attempt, or None before the first.
        complaints: Why the previous attempt was rejected. Fed back to the
            model, which is the difference between retrying and re-rolling.
        attempts: How many times the model has been asked.
    """

    brief: str
    banned: Annotated[frozenset[str], lambda old, new: new]
    question: GeneratedQuestion | None
    complaints: Annotated[list[str], lambda old, new: new]
    attempts: int


def normalise(stem: str) -> str:
    """Collapse whitespace so two stems compare by their words.

    Args:
        stem: A question stem.

    Returns:
        The stem with runs of whitespace reduced to single spaces.
    """
    return " ".join(stem.split())


def _faults(question: GeneratedQuestion, banned: frozenset[str]) -> list[str]:
    """List everything wrong with one attempt, in words the model can act on.

    Args:
        question: What the model wrote.
        banned: Stems it must not have repeated.

    Returns:
        One complaint per fault, empty when there is nothing to complain about.
    """
    faults = []

    correct = [option for option in question.options if option.is_correct]
    if len(correct) != 1:
        faults.append(f"Phải có đúng một phương án đúng, bạn đánh dấu {len(correct)} phương án.")

    unlabelled = [
        option.label
        for option in question.options
        if not option.is_correct and not option.error_label
    ]
    if unlabelled:
        faults.append(f"Các phương án sai {unlabelled} chưa có error_label.")

    if len(question.methods) < 2:
        faults.append(f"Cần ít nhất hai cách giải, bạn viết {len(question.methods)}.")

    if normalise(question.stem) in banned:
        faults.append("Đề này trùng với một đề đã dùng. Phải là câu khác, cùng dạng.")

    return faults


async def _write(state: WriteState) -> dict:
    """Ask the model for a question, telling it what went wrong last time.

    Args:
        state: Carries the brief and any complaints about the last attempt.

    Returns:
        The `question` and `attempts` slices of the state.
    """
    messages = [SystemMessage(_SYSTEM), HumanMessage(state["brief"])]
    if state["complaints"]:
        messages.append(
            HumanMessage(
                "Câu vừa rồi chưa đạt vì:\n- "
                + "\n- ".join(state["complaints"])
                + "\nViết lại một câu khác, sửa đúng những điểm trên."
            )
        )

    model = llm.with_fallback(lambda chat: chat.with_structured_output(GeneratedQuestion))
    question = await model.ainvoke(messages)
    return {"question": question, "attempts": state["attempts"] + 1}


def _check(state: WriteState) -> dict:
    """Judge the latest attempt.

    Args:
        state: Carries the attempt and the banned stems.

    Returns:
        The `complaints` slice of the state.
    """
    question = state["question"]
    if question is None:
        return {"complaints": ["Không nhận được câu nào."]}
    return {"complaints": _faults(question, state["banned"])}


def _again(state: WriteState) -> str:
    """Decide whether to ask once more.

    Args:
        state: Carries the complaints and the attempt count.

    Returns:
        "write" to try again, END to stop either way.
    """
    if not state["complaints"]:
        return END
    if state["attempts"] >= _MAX_ATTEMPTS:
        logger.warning("gave up after %d attempts: %s", state["attempts"], state["complaints"])
        return END
    return "write"


def _build() -> object:
    """Assemble the write-check-retry loop.

    Returns:
        A compiled graph.
    """
    graph = StateGraph(WriteState)
    graph.add_node("write", _write)
    graph.add_node("check", _check)
    graph.set_entry_point("write")
    graph.add_edge("write", "check")
    graph.add_conditional_edges("check", _again, {"write": "write", END: END})
    return graph.compile()


_GRAPH = _build()


async def write_question(brief: str, banned: frozenset[str] = frozenset()) -> GeneratedQuestion:
    """Write one question that satisfies ADR-18.

    Args:
        brief: What the question should be about, in words for the model.
        banned: Stems it must not repeat.

    Returns:
        The question.

    Raises:
        ValueError: If every attempt came back malformed. The caller falls back
            to prepared content; raising rather than returning something broken
            keeps that decision at the caller, where the alternatives are.
    """
    final = await _GRAPH.ainvoke(
        {"brief": brief, "banned": banned, "question": None, "complaints": [], "attempts": 0}
    )
    if final["complaints"] or final["question"] is None:
        raise ValueError(f"model could not write a usable question: {final['complaints']}")
    return final["question"]


def draft_brief(request: DraftAssessmentRequested, index: int) -> str:
    """Describe one question of a teacher's draft.

    Args:
        request: Subject, grade and the scope the teacher limited it to.
        index: Which question of the set this is, so the model varies rather
            than writing the same question `question_count` times.

    Returns:
        The brief.
    """
    return "\n".join(
        [
            f"Viết câu hỏi số {index} trong bộ {request.question_count} câu.",
            f"Môn: {request.subject}. Lớp: {request.grade}.",
            f"Phạm vi giáo viên giới hạn: {request.topic_scope}",
            "",
            "Mỗi câu trong bộ phải hỏi một khía cạnh khác nhau của phạm vi trên.",
        ]
    )


def retry_brief(request: RetryQuestionRequested) -> str:
    """Describe the question one remediation round needs.

    ADR-17 is specific about what a retry is for: it asks whether the student
    fixed the mistake, not whether they remember the answer. So the brief
    insists on the same shape with different content, and names the mistake the
    new question has to give the student another chance to make.

    Args:
        request: The origin question, what was picked, which round this is.

    Returns:
        The brief.
    """
    origin = request.origin
    lines = [
        "Viết MỘT câu hỏi mới để kiểm tra lại đúng kiến thức của câu dưới đây.",
        "",
        f"Câu gốc: {origin.stem}",
    ]
    for option in origin.options:
        mark = " (đáp án đúng)" if option.is_correct else ""
        lines.append(f"  {option.label}. {option.text}{mark}")
    lines.append(f"Mục tiêu học tập: {origin.learning_objective}")

    if request.wrong_option_label:
        lines.append(f"Học sinh đã chọn {request.wrong_option_label}.")
    if request.error_label:
        lines.append(f"Lỗi của em là: {request.error_label}.")

    lines += [
        "",
        "Yêu cầu:",
        "- Cùng DẠNG và cùng cách làm với câu gốc, nhưng số liệu và ngữ cảnh phải KHÁC.",
        "- Độ khó tương đương, không dễ hơn.",
        "- Phải có một phương án nhiễu ứng với đúng lỗi trên, để biết em đã sửa được chưa.",
    ]
    if request.previous_stems:
        lines.append("- KHÔNG được trùng bất kỳ đề nào sau đây:")
        lines += [f"  · {stem}" for stem in request.previous_stems]

    return "\n".join(lines)
