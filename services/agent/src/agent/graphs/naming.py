"""Đặt tên cho một đoạn chat, từ đúng câu mở đầu của nó.

Task nhỏ nhất trong cả AGENT, và nó nhỏ vì nó **được phép** nhỏ: nó không đọc lịch sử,
không gọi tool, không quyết định gì. Nó nhận một chuỗi và trả về một chuỗi ngắn hơn.

Một graph một node thì gần như chỉ là một lời gọi model bọc giấy. Nó vẫn là graph, vì luật
của repo nói graph là nơi **duy nhất** gọi model — handler không bao giờ chạm `llm`. Giữ
đúng ranh giới ấy đáng giá hơn việc tiết kiệm mười lăm dòng: ngày task này cần thêm một
bước, chỗ thêm vào đã có sẵn.

Cái tên là thứ giáo viên đọc trên một hàng rộng 228px, nên prompt đòi ngắn. Nhưng prompt
chỉ là một lời nhờ: BE cắt và dọn lại, vì một model trả ba trăm ký tự hay bọc câu trả lời
trong dấu ngoặc kép là chuyện thường.
"""

from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from agent import llm
from contracts import ConversationNameRequested

_SYSTEM = """Bạn đặt tên cho một đoạn chat giữa giáo viên và một trợ lý soạn đề.

Đọc câu mở đầu của giáo viên rồi trả về MỘT tiêu đề ngắn gọi tên công việc đó.

Luật:
- Tối đa sáu từ. Ngắn hơn thì tốt hơn.
- Tiếng Việt, viết thường trừ tên riêng và tên lớp: "Đề 15 phút — Hàm số 12A".
- Gọi tên VIỆC, không chào hỏi, không thêm chủ ngữ: "Tạo đề đạo hàm", không phải
  "Giáo viên muốn tạo đề đạo hàm".
- Chỉ trả về tiêu đề. Không dấu ngoặc kép, không dấu chấm cuối, không giải thích."""


class NamingState(TypedDict):
    """Những gì chảy qua graph.

    Attributes:
        said: Câu mở đầu của giáo viên.
        title: Cái tên model trả về.
    """

    said: str
    title: str


async def _name(state: NamingState) -> dict:
    """Hỏi model một cái tên.

    Args:
        state: Mang câu mở đầu.

    Returns:
        Mảnh `title` của state.
    """
    model = llm.with_fallback(lambda chat: chat)
    answer = await model.ainvoke(
        [SystemMessage(content=_SYSTEM), HumanMessage(content=state["said"])]
    )
    text = answer.text if isinstance(answer.text, str) else str(answer.content)
    return {"title": text}


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


_GRAPH = _build()


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
