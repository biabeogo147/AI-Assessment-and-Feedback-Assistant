"""Hình dạng của bản thô một tài liệu, như nó nằm trong kho nội dung (MongoDB).

**Mongo là nơi lưu, không phải nơi định nghĩa.** Decision Record *"byte sang MinIO, chunk sang
MongoDB"* của plan ô đặt điều kiện ấy là *không thương lượng*: thiếu nó, ranh giới giữa
`services/document` (bên ghi bản thô) và *document agent* của plan 3c (bên đọc bản thô rồi dựng cây)
âm thầm thành không kiểu -- hai bên nói chuyện qua một dict mà không ai khai.

**Bản thô là bất biến.** Chỉ đường đọc tệp của `services/document` ghi nó, và ghi bằng upsert theo
`_id`, nên arq chạy lại một job không nhân đôi trang nào. Plan 3c ghi cây và chunk vào collection
**của riêng nó**, trỏ về `document_id` + số trang -- không sửa `pages`. Đọc lại một tài liệu là ghi
đè bản thô của nó, và mọi thứ dựng trên bản thô phải dựng lại.

Module này chỉ là dữ liệu, như mọi module khác của `contracts`.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

# Phiên bản của họ này, như mọi họ khác của `contracts` tự khai số của mình. Nhích khi một trường
# đổi nghĩa hoặc bị bỏ, để bên đọc biết bản nào cũ.
#
# 2 (plan 3c, D2): `RawBlock.text` của khối **hình** thôi luôn rỗng -- nó mang chữ của các dòng OCR
# nằm trong hình. Bên đọc canh nó là bên dựng cây (`document/index/`): chữ ấy chỉ được dùng làm
# cổng *"trang này mở một chương"* (D9), và một bản thô số 1 thì không có cổng nào mở -- cây vẫn
# dựng được, chỉ không có tên chương đọc từ banner. `RawPage.text` không đổi nghĩa: nó vẫn bỏ khối
# hình.
SCHEMA_VERSION = 2


class RawSource(StrEnum):
    """Chữ của một tài liệu đến từ đâu.

    Ba đường, và bên đọc cần biết đường nào: chữ OCR có lỗi (thiếu từ trung vị 9,3% trên 50 trang
    SGK, đo ở plan 3a) và có nhãn layout thật; chữ text layer thì đúng từng ký tự nhưng mọi khối
    mang nhãn `text`; tệp văn bản thuần không có trang, không có hộp.
    """

    OCR = "ocr"
    TEXT_LAYER = "text_layer"
    PLAIN = "plain"


class RawBlock(BaseModel):
    """Một khối trên một trang, theo thứ tự đọc.

    Attributes:
        kind: Nhãn khối. Với OCR là nhãn PP-DocLayout (`paragraph_title`, `formula`, `number`, ...)
            -- tín hiệu cấu trúc mà plan 3c dựng cây từ đó. Với text layer và tệp thuần luôn là
            `text`: không có ai gán nhãn.
        box: Hộp bao `[trái, trên, phải, dưới]` theo điểm ảnh của ảnh đã dựng (OCR) hoặc theo điểm
            của trang PDF (text layer). `None` với tệp văn bản thuần.
        text: Chữ của khối, NFC. Rỗng với bảng. Với hình (từ `SCHEMA_VERSION` 2) là chữ của các
            dòng OCR nằm trong nó -- phần lớn là rác nhãn hình, chỉ dùng làm tín hiệu.
    """

    model_config = ConfigDict(frozen=True)

    kind: str
    box: tuple[float, float, float, float] | None = None
    text: str = ""


class RawPage(BaseModel):
    """Một trang đã đọc. Một document trong collection `pages`, `_id` là `page_key(...)`.

    Attributes:
        document_id: Tài liệu chứa trang này -- cùng id với hàng `documents` của Postgres.
        page: Số thứ tự trang trong tệp, đếm từ 1. Tệp văn bản thuần có đúng một trang.
        source: Chữ đến từ đường nào.
        width: Bề rộng hệ toạ độ của `box`. `None` khi không có hộp.
        height: Bề cao hệ toạ độ của `box`.
        blocks: Các khối theo thứ tự đọc.
        text: Chữ của mọi khối nối lại, để bên đọc không phải tự nối -- **trừ khối hình**: chữ của
            nó không vào ngữ cảnh LLM.
        seconds: Thời gian từng chặng OCR, khoá là tên chặng. `None` khi không qua OCR.
        read_at: Lúc trang được đọc.
        schema_version: Phiên bản hình dạng.
    """

    model_config = ConfigDict(frozen=True)

    document_id: str
    page: int
    source: RawSource
    width: float | None = None
    height: float | None = None
    blocks: tuple[RawBlock, ...] = ()
    text: str = ""
    seconds: dict[str, float] | None = None
    read_at: datetime
    schema_version: int = SCHEMA_VERSION


class RawDocument(BaseModel):
    """Đầu mục bản thô của một tài liệu. Một document trong collection `documents`, `_id` là id.

    **Không** mang trạng thái *đã xong chưa* -- câu ấy chỉ Postgres trả lời (`documents.state`), và
    Decision Record *"chunk trước, `state` sau"* cấm hỏi Mongo câu ấy. `finished_at` chỉ nói đường
    đọc đã ghi xong trang cuối; một tài liệu có `finished_at` mà Postgres vẫn `processing` là một
    tài liệu mà kết quả chưa về tới BE.

    Attributes:
        document_id: Id tài liệu.
        source: Chữ đến từ đường nào.
        page_count: Số trang. `None` với tệp văn bản thuần, đúng như `DocumentProbed.page_count`.
        reader: Bộ nhận dạng chữ đã dùng (`easyocr`, `vietocr`), `None` khi không qua OCR.
        pipeline: Phiên bản đường OCR (`text1`), cùng nghĩa với `_PIPELINE` của bộ đo -- đọc lại
            bằng một đường khác là một bản thô khác. `None` khi không qua OCR, như `reader`.
        started_at: Lúc bắt đầu đọc.
        finished_at: Lúc ghi xong trang cuối, `None` khi đang đọc dở.
        schema_version: Phiên bản hình dạng.
    """

    model_config = ConfigDict(frozen=True)

    document_id: str
    source: RawSource
    page_count: int | None = None
    reader: str | None = None
    pipeline: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    schema_version: int = SCHEMA_VERSION


def page_key(document_id: str, page: int) -> str:
    """Khoá `_id` của một trang trong collection `pages`.

    Ở đây chứ không trong `content_store.py`, vì bên đọc ở plan 3c phải dựng đúng khoá ấy để lấy một
    trang -- hai bên tự dựng khoá là hai sơ đồ đặt tên có thể lệch nhau.

    Args:
        document_id: Id tài liệu.
        page: Số trang, đếm từ 1.

    Returns:
        `"<document_id>:<page>"`.
    """
    return f"{document_id}:{page}"
