"""Graph một lượt kèm học: dựng message, stream câu trả lời, và cửa vào công khai `speak`."""

from collections.abc import Awaitable, Callable

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from agent import llm
from agent.graphs.explain.compose import ExplainState, compose
from contracts import ExplainTurnRequested

Publish = Callable[[str], Awaitable[None]]


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


def _build() -> object:
    """Lắp graph.

    Returns:
        Một graph đã compile, nhận `ExplainState` và điền vào `text`.
    """
    graph = StateGraph(ExplainState)
    graph.add_node("compose", compose)
    graph.add_node("speak", _speak)
    graph.set_entry_point("compose")
    graph.add_edge("compose", "speak")
    graph.add_edge("speak", END)
    return graph.compile()


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


_GRAPH = _build()
