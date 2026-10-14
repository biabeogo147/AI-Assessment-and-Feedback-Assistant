"""Hình dạng của **cây mục lục** một tài liệu, như nó nằm trong kho nội dung (MongoDB).

Cùng lệ với `contracts.content`: Mongo là nơi lưu, không phải nơi định nghĩa. Bên ghi là *document
agent* của `document-agent-hierarchy` (`services/document/src/document/index/`); bên đọc sau này là
ba tool `list_chapters` → `get_chapter` → `get_chunk` -- kiểu PageIndex, lần xuống cây bằng tiêu đề
và tóm tắt, không vector.

**Cây có đúng ba cấp** (người dùng chốt 11/10/2026): cấp 1 là chương hoặc phần (I, A, ...), cấp 2
là A.I hoặc I.1, cấp 3 là A.I.1 hoặc I.1.1. Bậc sâu hơn **không thành nút** -- nội dung của nó nằm
trong chunk của nút cấp 3 chứa nó. Nhờ vậy số lời gọi tóm tắt tỉ lệ với số mục thật, không với số
đề mục nhỏ nhặt.

**Cây dựng trên một lần đọc.** `IndexHeader.raw_started_at` chép `RawDocument.started_at` của bản
thô đã dùng; đọc lại tài liệu là xoá cây (`ContentStore.begin`), và một cây mà mốc ấy lệch là cây
cũ.

**Mọi tham chiếu về bản thô là `(page, block)`**: số trang đếm từ 1 như `RawPage.page`, vị trí khối
trong `RawPage.blocks` đếm từ 0. Không sao chép khối -- trừ `IndexChunk.text`, một bản sao có chủ ý
để tool trả chữ mà không phải nối lại.

Module này chỉ là dữ liệu, như mọi module khác của `contracts`.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# Phiên bản riêng của họ này, như `contracts.content` có số của nó.
# 2 (14/10/2026): `IndexHeader.summary_tokens` thôi cộng token đọc banner -- nay ở `banner_tokens`.
# Đổi nghĩa một trường thì nâng số (`packages/contracts/AGENTS.md`); chưa reader nào kiểm nó.
SCHEMA_VERSION = 2

# Số cấp của cây. Một hằng chứ không một con số rải rác: bên dựng gộp mọi thứ sâu hơn vào đây.
MAX_LEVEL = 3


class IndexMethod(StrEnum):
    """Cây được dựng bằng đường nào.

    `RULES` là đường lùi khi Jev không với tới được (D5 của `document-agent-hierarchy`). Tài liệu
    vẫn *sẵn sàng*, nhưng bên đọc -- và người đo -- phải biết cây nào chỉ do luật dựng.
    """

    JEV = "jev"
    RULES = "rules"


class TitleSource(StrEnum):
    """Tên của một nút đến từ đâu.

    Attributes:
        TEXT: Chữ của khối heading, đọc từ OCR hoặc text layer.
        BANNER: `gpt-5.6-luna` đọc trên ảnh banner mở chương (D9, `document-agent-hierarchy`) -- OCR
            không đọc nổi chữ trang trí. Luna chỉ **đọc** tên in trên ảnh.
        NUMBERING: Không có tên đọc được; tên là nhãn số (*"Chương III"*). Không model nào **bịa**
            ra một cái tên.
    """

    TEXT = "text"
    BANNER = "banner"
    NUMBERING = "numbering"


class DecidedBy(StrEnum):
    """Ai quyết vai trò và cấp của một ứng viên."""

    JEV = "jev"
    RULES = "rules"


class BlockRef(BaseModel):
    """Một khối của bản thô.

    Attributes:
        page: Số trang, đếm từ 1.
        block: Vị trí trong `RawPage.blocks`, đếm từ 0.
        line: Số dòng trong khối, đếm từ 0 -- chỉ với tệp văn bản thuần, nơi cả tệp là **một** khối
            và mỗi dòng được hỏi riêng (D8, `document-agent-hierarchy`). `None` ở mọi đường khác.
    """

    model_config = ConfigDict(frozen=True)

    page: int = Field(ge=1)
    block: int = Field(ge=0)
    line: int | None = Field(default=None, ge=0)


class IndexHeader(BaseModel):
    """Đầu mục cây của một tài liệu. Một document trong collection `indexes`, `_id` là id.

    Có mặt nghĩa là cây đã ghi xong: `put_index` ghi đầu mục **cuối cùng**. Nhưng câu *"tài liệu
    sẵn sàng chưa"* vẫn chỉ Postgres trả lời (*"chunk trước, `state` sau"*).

    Attributes:
        document_id: Id tài liệu.
        raw_started_at: `RawDocument.started_at` của bản thô đã dùng để dựng.
        raw_pipeline: `RawDocument.pipeline` của bản thô ấy.
        method: Đường dựng.
        jev_model: Phiên bản Jev đã trả lời, `None` khi đi đường luật.
        summary_model: Model viết tóm tắt.
        node_count: Số nút.
        chunk_count: Số chunk.
        low_confidence: Số ứng viên mà `confidence` của Jev dưới ngưỡng, phải nhờ luật.
        page_offset: Trang tệp trừ trang in, giá trị phổ biến nhất. `None` khi sách không in số
            trang (hoặc OCR không thấy).
        jev_tokens: Tổng token vào của Jev.
        summary_tokens: Tổng token (vào + ra) của các lời gọi tóm tắt. Với `schema_version` 1
            con số này gồm cả token đọc banner (`banner_tokens` của chúng là 0).
        banner_model: Model đọc banner, `None` khi không có khoá OpenAI.
        banner_tokens: Tổng token (vào + ra) của các lời gọi đọc banner. Tách khỏi
            `summary_tokens` vì hai model khác giá: cộng chung thì không tính được tiền.
        built_at: Lúc ghi xong.
        schema_version: Phiên bản hình dạng.
    """

    model_config = ConfigDict(frozen=True)

    document_id: str
    raw_started_at: datetime
    raw_pipeline: str | None = None
    method: IndexMethod
    jev_model: str | None = None
    summary_model: str | None = None
    node_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    low_confidence: int = Field(default=0, ge=0)
    page_offset: int | None = None
    jev_tokens: int = Field(default=0, ge=0)
    summary_tokens: int = Field(default=0, ge=0)
    banner_model: str | None = None
    banner_tokens: int = Field(default=0, ge=0)
    built_at: datetime
    schema_version: int = SCHEMA_VERSION


class IndexNode(BaseModel):
    """Một nút cây. Một document trong collection `nodes`, `_id` là `node_key(...)`.

    Attributes:
        document_id: Tài liệu chứa nút.
        ordinal: Thứ tự **preorder**, đếm từ 0 -- đọc lần lượt là đúng thứ tự trong sách.
        parent_ordinal: `ordinal` của nút cha, `None` với nút cấp 1.
        level: 1, 2 hoặc 3.
        numbering: Nhãn số như in (*"Chương I"*, *"Bài 2"*, *"1."*), `None` khi không có.
        title: Tên, không kèm nhãn số.
        title_source: Tên đến từ đâu.
        anchor: Khối heading sinh ra nút -- hoặc khối banner, với tên đọc bằng luna.
        page_start: Trang tệp của heading.
        page_end: Trang tệp cuối cùng trước nút kế cùng cấp hoặc cao hơn.
        printed_start: Số trang in tương ứng `page_start`, `None` khi không biết.
        printed_end: Số trang in tương ứng `page_end`.
        summary: Tóm tắt ngắn để model lần xuống cây. `None` khi lời gọi tóm tắt hỏng.
        confidence: `confidence` thấp nhất trong các quyết định Jev sinh ra nút; 1 với đường luật.
        schema_version: Phiên bản hình dạng.
    """

    model_config = ConfigDict(frozen=True)

    document_id: str
    ordinal: int = Field(ge=0)
    parent_ordinal: int | None = None
    level: int = Field(ge=1, le=MAX_LEVEL)
    numbering: str | None = None
    title: str
    title_source: TitleSource
    anchor: BlockRef
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    printed_start: int | None = None
    printed_end: int | None = None
    summary: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    schema_version: int = SCHEMA_VERSION


class IndexChunk(BaseModel):
    """Một đoạn nội dung, thuộc đúng một nút. Một document trong collection `chunks`.

    Attributes:
        document_id: Tài liệu.
        ordinal: Thứ tự trong tài liệu, đếm từ 0.
        node_ordinal: Nút sâu nhất chứa đoạn này. `None` với phần đứng trước nút đầu tiên (bìa, lời
            nói đầu).
        blocks: Các khối của bản thô tạo nên đoạn, theo thứ tự đọc.
        text: Chữ của các khối ấy nối lại.
        page_start: Trang tệp đầu.
        page_end: Trang tệp cuối.
        char_count: Số ký tự của `text`.
        schema_version: Phiên bản hình dạng.
    """

    model_config = ConfigDict(frozen=True)

    document_id: str
    ordinal: int = Field(ge=0)
    node_ordinal: int | None = None
    blocks: tuple[BlockRef, ...]
    text: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    char_count: int = Field(ge=0)
    schema_version: int = SCHEMA_VERSION


class BlockLabel(BaseModel):
    """Quyết định về một ứng viên heading. Một document trong collection `block_labels`.

    Không ai đọc nó để dựng thứ gì: nó ở đây để **gỡ lỗi** một cây sai và để **đo** Jev so với cây
    vàng -- một cây chỉ cho biết kết quả, không cho biết vì sao.

    Attributes:
        document_id: Tài liệu.
        ref: Khối được hỏi.
        ocr_kind: Nhãn của khối trong bản thô.
        text: Chữ đã gửi đi, cắt ngắn.
        numbering: Nhãn số code tách được, `None` khi không có.
        role: Vai trò được chọn (khoá lựa chọn tiếng Anh, xem `index/jev.py`).
        role_probabilities: Phân phối Jev trả cho `role`. Rỗng với đường luật.
        level: Cấp được chọn, `None` khi khối không phải mục.
        level_probabilities: Phân phối Jev trả cho `level`.
        confidence: `confidence` thấp hơn trong hai câu của Jev; 1 với đường luật.
        decided_by: Ai quyết cuối cùng.
        schema_version: Phiên bản hình dạng.
    """

    model_config = ConfigDict(frozen=True)

    document_id: str
    ref: BlockRef
    ocr_kind: str
    text: str
    numbering: str | None = None
    role: str
    role_probabilities: dict[str, float] = Field(default_factory=dict)
    level: int | None = Field(default=None, ge=1, le=MAX_LEVEL)
    level_probabilities: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0, le=1)
    decided_by: DecidedBy
    schema_version: int = SCHEMA_VERSION


def node_key(document_id: str, ordinal: int) -> str:
    """Khoá `_id` của một nút -- ở đây vì bên đọc phải dựng đúng khoá ấy, như `page_key`.

    Args:
        document_id: Id tài liệu.
        ordinal: Thứ tự preorder.

    Returns:
        `"<document_id>:n<ordinal>"`.
    """
    return f"{document_id}:n{ordinal}"


def chunk_key(document_id: str, ordinal: int) -> str:
    """Khoá `_id` của một chunk.

    Args:
        document_id: Id tài liệu.
        ordinal: Thứ tự chunk.

    Returns:
        `"<document_id>:c<ordinal>"`.
    """
    return f"{document_id}:c{ordinal}"


def label_key(document_id: str, ref: BlockRef) -> str:
    """Khoá `_id` của nhãn một ứng viên: một khối chỉ được hỏi một lần mỗi lần dựng.

    Args:
        document_id: Id tài liệu.
        ref: Khối.

    Returns:
        `"<document_id>:<page>:<block>"`, thêm `":<line>"` với tệp văn bản thuần.
    """
    key = f"{document_id}:{ref.page}:{ref.block}"
    return key if ref.line is None else f"{key}:{ref.line}"
