"""Graph đặt tên đoạn chat, và cửa vào công khai `name_it`."""

from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from agent import llm
from agent.graphs.naming.prompt import SYSTEM
from contracts import ConversationNameRequested


class NamingState(TypedDict):
    """Những gì chảy qua graph.

    Attributes:
        said: Câu mở đầu của giáo viên.
        title: Cái tên model trả về.
    """

    said: str
    title: str


async def name_it(request: ConversationNameRequested) -> str:
    """Đặt tên cho một đoạn chat.

    Args:
        request: Câu mở đầu của đoạn chat ấy.

    Returns:
        Cái tên, nguyên văn như model trả về. Việc cắt và dọn là của BE — nó biết chuỗi
        này sẽ nằm ở đâu, còn ở đây thì không.
    """
    final = await _GRAPH.ainvoke({"said": request.said, "title": ""})
    return final["title"]


def _build() -> object:
    """Lắp graph.

    Returns:
        Một graph đã compile, nhận `NamingState` và điền vào `title`.
    """
    graph = StateGraph(NamingState)
    graph.add_node("name", _name)
    graph.set_entry_point("name")
    graph.add_edge("name", END)
    return graph.compile()


async def _name(state: NamingState) -> dict:
    """Hỏi model một cái tên.

    Args:
        state: Mang câu mở đầu.

    Returns:
        Mảnh `title` của state.
    """
    model = llm.with_fallback(lambda chat: chat)
    answer = await model.ainvoke(
        [SystemMessage(content=SYSTEM), HumanMessage(content=state["said"])]
    )
    text = answer.text if isinstance(answer.text, str) else str(answer.content)
    return {"title": text}


_GRAPH = _build()
