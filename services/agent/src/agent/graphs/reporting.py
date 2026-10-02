"""Kể lại cho giáo viên những gì một plan vừa làm.

Một graph một node, như `naming`, và nhỏ vì nó **được phép** nhỏ: nó không gọi tool,
không quyết định gì, không đọc catalog. Nó nhận kết quả của từng bước và trả về một câu.

Vì sao nó là một task riêng chứ không phải một vòng nữa của `propose_next_step`: đầu vào
khác hẳn. Pha 1 đọc một cuộc hội thoại và một danh mục tool để quyết việc gì nên xảy ra;
chỗ này đọc những việc **đã** xảy ra và chỉ viết lời. Nhập hai thứ ấy vào một prompt là
đưa cho model một danh mục tool ở đúng lúc không còn gì để gọi, và mời nó đề nghị thêm
một bước nữa (ADR-25).

Prompt ở đây có một luật nặng hơn cả: **không nói quá kết quả**. Model chỉ thấy một dãy
`ok` và một dòng chi tiết; nó không thấy đề, không thấy câu hỏi nào. Nên một câu kể
"mình đã soạn xong 10 câu rất hay" là một câu bịa — việc soạn chạy ngầm và chưa ai đọc
thứ gì.

Và luật ấy **chỉ** đứng trong prompt: câu model viết đi thẳng ra bong bóng chat, y như mọi
lời nói khác của Kriky. BE chỉ `.strip()` rồi lùi về câu ghép của mình khi lời gọi hỏng
(`teacher_chat._report`); nó không cắt, không dọn Markdown, và không kiểm lại con số nào.
Thứ **có** lưới là các con số trên thẻ kết quả và dưới từng bước: chúng do BE tự đọc từ
database (`_said_about`), nên một lời kể nói quá vẫn không làm con số trên màn hình sai
theo.
"""

from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from agent import llm
from contracts import PlanReportRequested

_SYSTEM = """Bạn là trợ lý Kriky, vừa làm xong một việc cho giáo viên phổ thông Việt Nam.

Hệ thống đưa bạn câu giáo viên đã nhờ và kết quả từng bước đã chạy. Viết MỘT đoạn ngắn
kể lại cho họ.

Luật:
- Chỉ nói những gì kết quả nói. Bạn KHÔNG thấy đề, không thấy câu hỏi nào, nên TUYỆT ĐỐI
  không nhận xét về chất lượng và không nói một con số không có trong kết quả.
- Có bước hỏng thì nói thẳng là chưa làm được tới đâu, và nói phần đã làm được là gì.
  Đừng xin lỗi dài, đừng hứa làm lại.
- Dòng "Tiến độ soạn" là sự thật về cái đề, và bạn PHẢI theo nó:
  - nó nói "đã đủ" → đề đã soạn XONG. Nói xong, rồi mời giáo viên xem và duyệt. TUYỆT ĐỐI
    không nói "đang soạn", "sẽ soạn", "đang viết nội dung" — những câu ấy sai.
  - nó nói "còn N câu đang soạn" → nói đang soạn, và nói đúng con số.
  - nó nói "DỪNG ở k/n" → đề **chưa đủ câu** và không còn gì đang chạy. Nói thẳng con số còn
    thiếu, và ĐỪNG mời duyệt: duyệt một đề thiếu câu là phát hành một bài kiểm tra dở.
  - không có dòng ấy → lượt này không soạn đề, đừng nhắc gì tới số câu.
- Hai tới ba câu. Tiếng Việt, gọn, như nói với đồng nghiệp. Tự gọi mình là "mình", gọi
  giáo viên là "bạn".
- KHÔNG dùng Markdown: không **in đậm**, không *nghiêng*, không `mã`, không bảng.
- Toán viết bằng ký hiệu Unicode: y = x³ − 3x, ≥, →. Không LaTeX."""


class ReportState(TypedDict):
    """Những gì chảy qua graph.

    Attributes:
        said: Câu giáo viên đã gõ.
        outcomes: Các bước đã chạy, đã dọn thành từng dòng.
        progress: Một dòng về số câu, hoặc rỗng khi lượt này không soạn đề.
        text: Lời kể model trả về.
    """

    said: str
    outcomes: str
    progress: str
    text: str


def _as_lines(request: PlanReportRequested) -> str:
    """Viết các bước đã chạy ra cho model đọc.

    Mỗi bước một dòng, có dấu cho biết xong hay hỏng. Không phải JSON như `propose`:
    ở đó model phải đọc một id ra để truyền tiếp, còn ở đây nó chỉ kể lại, nên một
    dòng tiếng Việt vừa đủ và không mời gọi việc nhắc lại tên field.

    Args:
        request: Câu đã nhờ và các bước đã chạy.

    Returns:
        Các dòng, theo thứ tự chạy.
    """
    lines = []
    for index, one in enumerate(request.outcomes, start=1):
        mark = "xong" if one.ok else "HỎNG"
        tail = f" — {one.detail}" if one.detail else ""
        lines.append(f"{index}. {one.title}: {mark}{tail}")
    return "\n".join(lines)


def _progress(request: PlanReportRequested) -> str:
    """Một dòng về số câu, lấy từ **con số BE đếm trong database**.

    Nó thay cho một câu cứng trong prompt. Trước đây prompt dặn *"nói đang soạn chứ đừng nói
    đã xong"* — đúng chừng nào báo cáo còn chạy trước lúc soạn xong, và sai ngược lại từ khi
    đường SSE đợi hết câu rồi mới kể (ADR-25). Một luật phụ thuộc thời điểm thì phải là dữ
    liệu, không phải một dòng prompt.

    Con số đếm từ database chứ không từ số tiếng chuông: chuông có thể mất, và một vị trí
    thử lại rung hai lần.

    Args:
        request: Yêu cầu, mang theo ba con số.

    Returns:
        Dòng để đưa model đọc, hoặc rỗng khi lượt này không soạn đề nào.
    """
    if request.asked_for == 0 and request.written == 0:
        return ""
    if request.still_drafting > 0:
        return (
            f"Tiến độ soạn: đã có {request.written}/{request.asked_for} câu, "
            f"còn {request.still_drafting} câu đang soạn."
        )
    if request.written < request.asked_for:
        # Không còn job nào chạy mà vẫn thiếu câu: vòng soạn đã **dừng**, không phải đã
        # xong. Bản đầu chỉ xét `still_drafting == 0` và nói "đã đủ 0/10 câu" cho một đề
        # chưa có câu nào — rồi prompt bảo model mời giáo viên duyệt nó. Đó đúng là cái
        # hại ADR-01 khoá nội dung để chặn, chỉ đi bằng đường lời nói.
        return (
            f"Tiến độ soạn: DỪNG ở {request.written}/{request.asked_for} câu, "
            "không còn câu nào đang chạy — đề CHƯA đủ."
        )
    return (
        f"Tiến độ soạn: đã đủ {request.written}/{request.asked_for} câu, "
        "không còn câu nào đang soạn."
    )


async def _tell(state: ReportState) -> dict:
    """Hỏi model một lời kể.

    Args:
        state: Mang câu đã nhờ và các bước đã chạy.

    Returns:
        Mảnh `text` của state.
    """
    model = llm.with_fallback(lambda chat: chat)
    answer = await model.ainvoke(
        [
            SystemMessage(content=_SYSTEM),
            HumanMessage(
                content=(
                    f"Giáo viên nhờ: {state['said']}\n\n"
                    f"Các bước đã chạy:\n{state['outcomes']}"
                    + (f"\n\n{state['progress']}" if state["progress"] else "")
                )
            ),
        ]
    )
    text = answer.text if isinstance(answer.text, str) else str(answer.content)
    return {"text": text}


def _build() -> object:
    """Lắp graph.

    Returns:
        Một graph đã compile, nhận `ReportState` và điền vào `text`.
    """
    graph = StateGraph(ReportState)
    graph.add_node("tell", _tell)
    graph.set_entry_point("tell")
    graph.add_edge("tell", END)
    return graph.compile()


_GRAPH = _build()


async def tell_about(request: PlanReportRequested) -> str:
    """Kể lại một plan đã chạy.

    Args:
        request: Câu giáo viên đã nhờ và kết quả từng bước.

    Returns:
        Lời kể, nguyên văn như model trả về. BE lùi về một câu dự phòng khi lời gọi này
        hỏng, nhưng nó **không** cắt và không dọn chuỗi — khác đường đặt tên đoạn chat, nơi
        có một hàm dọn thật. Luật về độ dài và về Markdown vì thế chỉ nằm trong prompt.
    """
    final = await _GRAPH.ainvoke(
        {
            "said": request.said,
            "outcomes": _as_lines(request),
            "progress": _progress(request),
            "text": "",
        }
    )
    return final["text"]
