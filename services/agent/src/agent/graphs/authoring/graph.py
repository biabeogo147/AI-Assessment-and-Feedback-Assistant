"""Vòng viết, kiểm, thử lại của một câu hỏi, và cửa vào công khai `write_question`."""

import logging
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from agent import llm
from agent.config import get_settings
from agent.graphs.authoring.checks import faults
from agent.graphs.authoring.prompt import SYSTEM
from agent.graphs.authoring.repair import parsed, unmangled
from contracts import GeneratedQuestion

logger = logging.getLogger("agent.graphs.authoring")


class WriteState(TypedDict):
    """Những gì chảy qua loop.

    Attributes:
        brief: Phải viết gì, bằng những lời model đọc được.
        banned: Các stem câu này không được lặp lại, đã normalise.
        question: Lần thử gần nhất, hoặc None khi chưa thử lần nào.
        complaints: Vì sao lần thử trước bị loại. Được đưa trở lại cho model, và đó
            là chỗ khác nhau giữa retry và gieo lại xúc xắc.
        malformed: Lỗi giải mã của lần thử trước khi model trả về sai hình dạng -- thiếu
            `options`, `methods` là một chuỗi JSON --, rỗng khi lần thử đọc được.
        attempts: Model đã được hỏi bao nhiêu lần.
    """

    brief: str
    banned: Annotated[frozenset[str], lambda old, new: new]
    question: GeneratedQuestion | None
    complaints: Annotated[list[str], lambda old, new: new]
    malformed: str
    attempts: int


async def write_question(brief: str, banned: frozenset[str] = frozenset()) -> GeneratedQuestion:
    """Viết một câu hỏi thoả ADR-18.

    Args:
        brief: Câu hỏi nên nói về cái gì, bằng lời dành cho model.
        banned: Các stem nó không được lặp lại.

    Returns:
        Câu hỏi.

    Raises:
        ValueError: Nếu mọi lần thử đều trả về một câu sai hình dạng. Bên gọi để job hỏng; BE
            ghi `last_fault` rồi hỏi lại có trần -- không lùi về một câu soạn sẵn.
    """
    final = await _GRAPH.ainvoke(
        {
            "brief": brief,
            "banned": banned,
            "question": None,
            "malformed": "",
            "complaints": [],
            "attempts": 0,
        }
    )
    if final["complaints"] or final["question"] is None:
        raise ValueError(f"model could not write a usable question: {final['complaints']}")
    return final["question"]


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


async def _write(state: WriteState) -> dict:
    """Hỏi model một câu hỏi, kèm theo chuyện lần trước đã sai ở đâu.

    Câu trả về **sai hình dạng** không ném ra ngoài: nó thành một lời phàn nàn và loop hỏi lại
    (plan `backlog-tier-1`, pha 1: *Tool soạn câu trả sai hình dạng rồi câu mock vào đề*). Trước
    đây lỗi giải mã thoát khỏi graph, và handler lùi về một câu Toán soạn sẵn -- câu lạc đề vào đề
    thật của giáo viên.

    Args:
        state: Mang theo brief và mọi lời phàn nàn về lần thử trước.

    Returns:
        Các mảnh `question`, `malformed` và `attempts` của state.
    """
    messages = [SystemMessage(SYSTEM), HumanMessage(state["brief"])]
    if state["complaints"]:
        messages.append(
            HumanMessage(
                "Câu vừa rồi chưa đạt vì:\n- "
                + "\n- ".join(state["complaints"])
                + "\nViết lại một câu khác, sửa đúng những điểm trên."
            )
        )

    model = llm.with_fallback(
        lambda chat: chat.with_structured_output(GeneratedQuestion, include_raw=True)
    )
    question, malformed = parsed(await model.ainvoke(messages))
    return {
        "question": None if question is None else unmangled(question),
        "malformed": malformed,
        "attempts": state["attempts"] + 1,
    }


def _check(state: WriteState) -> dict:
    """Phán xét lần thử gần nhất.

    Args:
        state: Mang theo lần thử và các stem bị cấm.

    Returns:
        Mảnh `complaints` của state.
    """
    question = state["question"]
    if question is None:
        # Nói cho model biết hình dạng sai ở đâu, cắt gọn: lỗi pydantic dài và lặp.
        why = state.get("malformed", "")[:300]
        return {
            "complaints": [
                "Câu vừa rồi sai hình dạng nên không đọc được"
                + (f" ({why})" if why else "")
                + ". options và methods phải là DANH SÁCH các đối tượng (không phải một chuỗi "
                "JSON), và phải có đủ stem, options, methods, learning_objective."
            ]
        }
    return {"complaints": faults(question, state["banned"])}


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


_GRAPH = _build()
