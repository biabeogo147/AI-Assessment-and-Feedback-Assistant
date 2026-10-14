"""Hai lời gọi model sinh chữ của document agent. Module duy nhất trong `services/document` import
`langchain`.

- **Đọc banner** (D9): `gpt-5.6-luna` nhìn phần trên của một trang mở chương và đọc **số và tên
  chương, cùng tên bài in ngay dưới** -- OCR không đọc nổi chữ trang trí (5/5 chương của Lớp 6 tập 1
  ra rác, `document-agent-hierarchy` Status). Chỉ được gọi ở trang qua cổng `features.banner_gates`:
  đo trên trang 7, luna nhận nhầm một trang bài thường là *"phần mở đầu"*.
- **Tóm tắt** (D6): `gpt-4o-mini`, một lời gọi mỗi nút, để model ở plan sau lần xuống cây bằng tiêu
  đề và tóm tắt (PageIndex).

Cùng khuôn với `agent/llm.py`, và cùng hai bài học: **credential được truyền vào** (`.env` của repo
không bao giờ tới `os.environ`), và mọi lời gọi qua đúng một module -- đổi model là sửa `.env`, test
thay builder ở đây là không gì chạm mạng.
"""

import base64
import json
import logging
from dataclasses import dataclass

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

_BANNER_PROMPT = (
    "Ảnh là phần trên của một trang sách giáo khoa tiếng Việt. Nếu đây là trang MỞ ĐẦU một chương "
    "hoặc một phần lớn của sách, đọc chính xác số và tên của nó như in trên ảnh. Nếu ngay dưới đó "
    "có tên bài đầu tiên (ví dụ một dải ghi BÀI 8 kèm tên bài) thì đọc cả số bài và tên bài. "
    "Trả về "
    'đúng một object JSON: {"la_mo_dau": true|false, "loai": "chương"|"phần"|null, '
    '"so": "<số như in, ví dụ I, II, 3>"|null, '
    '"ten": "<tên như in, giữ dấu, viết hoa như in>"|null, '
    '"so_bai": "<số bài>"|null, "ten_bai": "<tên bài như in>"|null}. '
    "Không đoán: chữ nào không đọc được thì để null."
)

_SUMMARY_SYSTEM = (
    "Bạn tóm tắt một phần của một tài liệu học tập tiếng Việt, để một trợ lý soạn đề sau này đọc "
    "tiêu đề và tóm tắt mà quyết định có mở phần ấy ra hay không.\n"
    "Luật:\n"
    "- Hai tới bốn câu, tiếng Việt, không gạch đầu dòng.\n"
    "- Nói phần ấy dạy kiến thức gì, có những dạng bài hay ví dụ nào.\n"
    "- Chỉ dùng điều có trong đoạn được đưa. Chữ đến từ OCR nên có lỗi chính tả: hiểu theo nghĩa, "
    "đừng chép lỗi, đừng bịa thêm khái niệm không có trong đoạn.\n"
    "- Không mở đầu bằng 'Phần này' hay nhắc lại tiêu đề."
)


@dataclass(frozen=True)
class BannerReading:
    """Thứ luna đọc được trên một banner.

    Attributes:
        is_opening: Luna cho rằng trang mở một chương hay một phần.
        kind: *"chương"* hoặc *"phần"*.
        number: Số như in (*"II"*).
        title: Tên như in.
        lesson_number: Số bài in ngay dưới banner.
        lesson_title: Tên bài ấy.
        tokens: Token vào + ra của lời gọi.
    """

    is_opening: bool
    kind: str | None
    number: str | None
    title: str | None
    lesson_number: str | None
    lesson_title: str | None
    tokens: int


@dataclass(frozen=True)
class Summary:
    """Một tóm tắt và giá của nó.

    Attributes:
        text: Tóm tắt.
        tokens: Token vào + ra.
    """

    text: str
    tokens: int


def chat_model(model: str, api_key: str, timeout: float, **extra: object) -> BaseChatModel:
    """Dựng một chat model OpenAI với khoá truyền vào.

    Args:
        model: Id model.
        api_key: Khoá OpenAI, từ `Settings`.
        timeout: Trần giây.
        **extra: Tham số riêng của model (`reasoning_effort` cho luna).

    Returns:
        Một chat model gọi được ngay.
    """
    return init_chat_model(
        model, model_provider="openai", api_key=api_key, timeout=timeout, **extra
    )


def parse_banner(raw: str, tokens: int) -> BannerReading:
    """Đọc JSON luna trả về. Hàm thuần.

    Luna đôi khi bọc JSON trong ```` ``` ````; một câu trả lời không phải JSON thì coi như không đọc
    được gì -- tên chương lùi về nhãn số (D6, `document-agent-hierarchy`), không bao giờ bịa.

    Args:
        raw: Chữ model trả.
        tokens: Token của lời gọi.

    Returns:
        Kết quả đọc; mọi trường `None` khi không parse được.
    """
    body = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("banner reader returned no json: %r", raw[:200])
        return BannerReading(False, None, None, None, None, None, tokens)

    def text(key: str) -> str | None:
        value = data.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else None

    return BannerReading(
        is_opening=bool(data.get("la_mo_dau")),
        kind=text("loai"),
        number=text("so"),
        title=text("ten"),
        lesson_number=text("so_bai"),
        lesson_title=text("ten_bai"),
        tokens=tokens,
    )


def _tokens(message: object) -> int:
    usage = getattr(message, "usage_metadata", None) or {}
    return int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))


async def read_banner(model: BaseChatModel, png: bytes) -> BannerReading:
    """Hỏi luna tên chương (và tên bài đầu) trên ảnh banner.

    Args:
        model: Chat model của `banner_model`.
        png: Ảnh phần trên của trang.

    Returns:
        Kết quả đọc.
    """
    image = "data:image/png;base64," + base64.b64encode(png).decode()
    message = HumanMessage(
        content=[
            {"type": "text", "text": _BANNER_PROMPT},
            {"type": "image_url", "image_url": {"url": image}},
        ]
    )
    answer = await model.ainvoke([message])
    return parse_banner(str(answer.content), _tokens(answer))


async def summarise(model: BaseChatModel, title: str, body: str) -> Summary:
    """Tóm tắt một nút cây.

    Args:
        model: Chat model của `summary_model`.
        title: Tiêu đề nút, kèm nhãn số.
        body: Chữ của nút -- hoặc, với nút có con, tóm tắt của các con.

    Returns:
        Tóm tắt.
    """
    answer = await model.ainvoke(
        [
            SystemMessage(content=_SUMMARY_SYSTEM),
            HumanMessage(content=f"Tiêu đề: {title}\n\nNội dung:\n{body}"),
        ]
    )
    return Summary(str(answer.content).strip(), _tokens(answer))
