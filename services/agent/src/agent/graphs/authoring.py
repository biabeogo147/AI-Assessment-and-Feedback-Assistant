"""Viết một câu hỏi, và từ chối giao ra một câu sai hình dạng.

Một loop, vì đây là việc có thể không qua được check của chính nó: model được yêu
cầu một câu hỏi có hình dạng nhất định và đôi khi viết ra một câu không như vậy.
Graph thử lại kèm theo lời phàn nàn, và đó là một việc khác với thử lại rồi hy vọng.

**Đây không phải nơi ADR-18 được thi hành.** BE check lại mọi thứ tới tay nó, và
`packages/contracts` nói rõ vì sao: một bộ sinh tự phán xét đầu ra của mình là tự
chấm bài của mình. Check ở đây là tự QC -- nó tiết kiệm một vòng đi về và một job
queue bỏ đi, và nếu nó có bao giờ không đồng ý với check của BE thì check của BE mới
là cái được tính.

Những gì model được dặn về hình dạng đến từ các decision record, không đến từ sở
thích: đúng một phương án đúng, mỗi distractor mang tên của lỗi mà nó đại diện, và
nhiều hơn một cách giải (ADR-18); còn với một lượt chữa lỗi thì là một câu hỏi kiểm
tra cùng một thứ mà không phải cùng một câu (ADR-17).
"""

import logging
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from agent import llm
from agent.config import get_settings
from contracts import DraftQuestionRequested, GeneratedQuestion, RetryQuestionRequested

logger = logging.getLogger(__name__)


_SYSTEM = r"""Bạn soạn câu hỏi trắc nghiệm cho học sinh trung học Việt Nam.

Mỗi câu bạn viết phải thoả đúng ba điều sau, không thương lượng:
- Có đúng MỘT phương án đúng. Đánh dấu nó bằng is_correct = true, các phương án còn lại là false.
- MỖI phương án sai phải kèm error_label: tên ngắn gọn của lỗi tư duy dẫn tới việc chọn nó. Ví dụ
  "đọc ngược chiều biến thiên", "quên nhân số mũ khi hạ bậc". Phương án đúng để error_label rỗng.
- Có ÍT NHẤT HAI cách giải khác nhau trong methods, mỗi cách có title ngắn và body là các bước.

Cách viết:
- Tiếng Việt, đúng văn phong đề kiểm tra phổ thông.
- Toán viết trong cặp `$`: `$y = x^3 - 3x$`, `$\int_0^1 (3x^2 - 2x + 1)\,dx$`, `$\frac{1}{3}$`.
  Màn hình dựng hình phần nằm giữa hai dấu `$`. Chữ thường thì viết thường, **đừng** bọc
  cả câu trong `$`. Và đừng dùng dấu ngoặc kiểu \( \) hay \[ \] — chỉ `$`.
- KHÔNG dùng Markdown: không **in đậm**, không *nghiêng*, không `mã`.
- Số liệu phải tính ra được và đáp án đánh dấu đúng phải thật sự đúng."""


class WriteState(TypedDict):
    """Những gì chảy qua loop.

    Attributes:
        brief: Phải viết gì, bằng những lời model đọc được.
        banned: Các stem câu này không được lặp lại, đã normalise.
        question: Lần thử gần nhất, hoặc None khi chưa thử lần nào.
        complaints: Vì sao lần thử trước bị loại. Được đưa trở lại cho model, và đó
            là chỗ khác nhau giữa retry và gieo lại xúc xắc.
        attempts: Model đã được hỏi bao nhiêu lần.
    """

    brief: str
    banned: Annotated[frozenset[str], lambda old, new: new]
    question: GeneratedQuestion | None
    complaints: Annotated[list[str], lambda old, new: new]
    attempts: int


def normalise(stem: str) -> str:
    """Gộp khoảng trắng lại để hai stem được so sánh theo từ ngữ của chúng.

    Chỉ một bản cài đặt: `handlers` import hàm này chứ không giữ bản riêng. Hai hàm
    buộc phải khớp nhau, nằm trong hai file, là một lần lệch nhau đã hẹn trước ngày
    -- và ở đây hai bên sẽ lệch nhau về chuyện một câu hỏi có lặp lại câu học sinh
    đã gặp hay không.

    Args:
        stem: Một stem câu hỏi.

    Returns:
        Stem đó với mọi chuỗi khoảng trắng liền nhau rút về một dấu cách.
    """
    return " ".join(stem.split())


def _faults(question: GeneratedQuestion, banned: frozenset[str]) -> list[str]:
    """Liệt kê mọi thứ sai trong một lần thử, bằng lời model làm được gì với nó.

    Args:
        question: Thứ model đã viết.
        banned: Các stem nó không được lặp lại.

    Returns:
        Một lời phàn nàn cho mỗi lỗi, rỗng khi không có gì để phàn nàn.
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
    """Hỏi model một câu hỏi, kèm theo chuyện lần trước đã sai ở đâu.

    Args:
        state: Mang theo brief và mọi lời phàn nàn về lần thử trước.

    Returns:
        Hai mảnh `question` và `attempts` của state.
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
    """Phán xét lần thử gần nhất.

    Args:
        state: Mang theo lần thử và các stem bị cấm.

    Returns:
        Mảnh `complaints` của state.
    """
    question = state["question"]
    if question is None:
        return {"complaints": ["Không nhận được câu nào."]}
    return {"complaints": _faults(question, state["banned"])}


def _again(state: WriteState) -> str:
    """Quyết định có hỏi thêm một lần nữa hay không.

    Args:
        state: Mang theo các lời phàn nàn và số lần đã thử.

    Returns:
        "write" để thử lại, END để dừng trong cả hai trường hợp còn lại.
    """
    if not state["complaints"]:
        return END
    if state["attempts"] >= get_settings().llm_max_attempts:
        logger.warning("gave up after %d attempts: %s", state["attempts"], state["complaints"])
        return END
    return "write"


def _build() -> object:
    """Lắp loop write-check-retry.

    Returns:
        Một graph đã compile.
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
    """Viết một câu hỏi thoả ADR-18.

    Args:
        brief: Câu hỏi nên nói về cái gì, bằng lời dành cho model.
        banned: Các stem nó không được lặp lại.

    Returns:
        Câu hỏi.

    Raises:
        ValueError: Nếu mọi lần thử đều trả về một câu sai hình dạng. Bên gọi sẽ
            lùi về nội dung dọn trước; raise thay vì trả về một thứ hỏng giữ quyết
            định đó ở bên gọi, nơi có sẵn các lựa chọn thay thế.
    """
    final = await _GRAPH.ainvoke(
        {"brief": brief, "banned": banned, "question": None, "complaints": [], "attempts": 0}
    )
    if final["complaints"] or final["question"] is None:
        raise ValueError(f"model could not write a usable question: {final['complaints']}")
    return final["question"]


def draft_brief(request: DraftQuestionRequested) -> str:
    """Mô tả đúng một câu hỏi mà job này viết.

    Mọi thứ ở đây đến từ một brief BE đã lưu trước khi có job nào được đẩy vào
    queue, nên mọi câu trong bộ đề đều được viết theo cùng một bộ chỉ dẫn. Vị trí
    câu được đưa vào vì các job chạy độc lập và không thấy nhau: nói với một job
    rằng nó là câu thứ ba trong mười câu là sự phối hợp duy nhất có thể, và đó là
    một lời nhắc chứ không phải một bảo đảm -- BE kiểm tra trùng lặp lúc harvest.

    Args:
        request: Môn, lớp, phạm vi giáo viên giới hạn lại, mức độ khó họ yêu cầu, và
            đây là câu thứ mấy trong bộ đề.

    Returns:
        Brief.
    """
    lines = [
        f"Viết câu hỏi số {request.ordinal} trong bộ {request.of_total} câu.",
        f"Môn: {request.subject}. Lớp: {request.grade}.",
        f"Phạm vi giáo viên giới hạn: {request.topic_scope}",
    ]
    if request.difficulty:
        lines.append(f"Mức độ giáo viên yêu cầu: {request.difficulty}")
    lines += [
        "",
        "Mỗi câu trong bộ phải hỏi một khía cạnh khác nhau của phạm vi trên.",
    ]
    return "\n".join(lines)


def retry_brief(request: RetryQuestionRequested) -> str:
    """Mô tả câu hỏi mà một lượt chữa lỗi cần.

    ADR-17 nói rất cụ thể về chuyện một lượt làm lại dùng để làm gì: nó hỏi xem học
    sinh đã sửa được lỗi chưa, không hỏi xem em có nhớ đáp án hay không. Vì thế brief
    đòi cùng một hình dạng với nội dung khác, và gọi tên cái lỗi mà câu hỏi mới phải
    cho học sinh một cơ hội nữa để mắc lại.

    Args:
        request: Câu gốc, phương án đã chọn, đây là lượt thứ mấy.

    Returns:
        Brief.
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
