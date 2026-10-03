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

**Bản prompt đầu ép model bịa.** Nó nói *"gọi tên VIỆC, không chào hỏi"* và không cho một
đường ra nào cho một câu không chứa việc nào — nên với *"Chào bạn"*, model buộc phải nghĩ
ra một việc, và nguồn chữ duy nhất trong tầm với là chính hai ví dụ của prompt. Đo được
trên trình duyệt thật: *"Chào bạn"* ra *"Tạo đề kiểm tra 15 phút"*, đúng phép trộn hai ví
dụ `"Đề 15 phút — Hàm số 12A"` và `"Tạo đề đạo hàm"`. Cái tên sai ấy **tuân thủ** mọi luật
còn lại — sáu từ, viết thường, không ngoặc kép — nên không có khâu dọn nào bắt được nó.

Nay prompt có đường ra cho câu không nhờ việc gì, và các ví dụ là **cặp vào–ra** chứ không
phải những cái tên đứng một mình: một cái tên đứng một mình là chữ cho sẵn để model mượn
lúc bí. Và BE có một chốt kiểm thật (`teacher_chat._echoes`), vì một prompt vẫn chỉ là một
lời nhờ.

Hai thứ cố ý ở đây, cả hai do review chỉ ra. **Luật nói đúng cái đang được thi hành**: bản
đầu viết *"mọi từ trong tiêu đề phải bắt nguồn từ câu vào"* trong khi `_echoes` chỉ đòi
**một** từ chung — và chính ba ví dụ ngay dưới nó đều thêm chữ mới (*"đề"*, *"Kết quả"*),
tức luật bị ví dụ của mình phủ định, mà model đọc ví dụ chặt hơn đọc luật. **Và ví dụ cho
câu không nhờ việc gì không được là `Chào bạn`**: đó đúng là ca đã đo hỏng, nên để nó ở đây
là in sẵn đáp án — chạy lại ca ấy sau đó chỉ chứng minh model biết nhớ, không chứng minh nó
biết theo luật.
"""

from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from agent import llm
from contracts import ConversationNameRequested

_SYSTEM = """Bạn đặt tên cho một đoạn chat giữa giáo viên và một trợ lý soạn đề.

Đọc câu mở đầu của giáo viên rồi trả về MỘT tiêu đề ngắn.

Luật:
- Tiêu đề phải nói về CHÍNH câu ấy, và dùng lại chữ của câu ấy. Đừng thêm môn học, tên
  lớp, số câu hay thời lượng mà giáo viên chưa hề nói.
- Câu ấy có nhờ một việc thì gọi tên việc đó, không chào hỏi, không thêm chủ ngữ.
- Câu ấy KHÔNG nhờ việc gì — một lời chào, một câu hỏi xã giao, một câu bỏ lửng — thì rút
  gọn chính câu ấy làm tiêu đề. ĐỪNG bịa ra một việc nào: một đoạn chat mở đầu bằng lời
  chào thì tên của nó là lời chào.
- Tối đa sáu từ. Ngắn hơn thì tốt hơn.
- Tiếng Việt, viết thường trừ tên riêng và tên lớp.
- Chỉ trả về tiêu đề. Không dấu ngoặc kép, không dấu chấm cuối, không giải thích.

Vài cặp "câu giáo viên gõ" → "tiêu đề":
- Soạn giúp mình 10 câu về đạo hàm cho 12A1 → Soạn đề đạo hàm 12A1
- Lớp 11B làm bài vừa rồi thế nào → Kết quả lớp 11B
- Chào buổi sáng nhé → Chào buổi sáng"""


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
