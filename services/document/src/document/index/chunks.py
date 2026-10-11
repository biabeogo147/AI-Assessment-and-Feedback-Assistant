"""Cắt nội dung thành chunk, mỗi chunk thuộc đúng một nút. Hàm thuần.

Một chunk là một dải đơn vị đọc **liên tiếp** dưới cùng một nút, cắt ở `max_chars`. Nút nào đang mở
thì đổi ở mỏ neo của nó: tới khối tiêu đề của một nút, mọi thứ sau đó thuộc nút ấy cho tới mỏ neo
kế.
Tiêu đề sâu hơn cấp 3 không có mỏ neo -- chữ của nó nằm luôn trong chunk của nút cha, đúng nghĩa
*"gộp vào cha"* mà người dùng chốt.

Khối hình, bảng, dòng chạy đầu trang và số trang không vào chunk (`features.NOT_CONTENT`): chunk là
thứ đi vào ngữ cảnh LLM, và chữ của khối hình phần lớn là rác nhãn hình.
"""

from contracts import BlockRef, IndexChunk, IndexNode
from document.index.features import NOT_CONTENT, Unit

# Trần ký tự của một chunk. Một mục SGK trung bình vài nghìn ký tự; 1 500 giữ một chunk vừa một
# đoạn ngữ cảnh mà vẫn không cắt vụn từng hoạt động.
MAX_CHUNK_CHARS = 1500


def build_chunks(
    document_id: str, units: list[Unit], nodes: list[IndexNode], max_chars: int = MAX_CHUNK_CHARS
) -> list[IndexChunk]:
    """Cắt chunk.

    Args:
        document_id: Id tài liệu.
        units: Mọi đơn vị đọc, theo thứ tự đọc.
        nodes: Các nút của cây.
        max_chars: Trần ký tự một chunk.

    Returns:
        Các chunk, theo thứ tự đọc. Phần trước nút đầu tiên có `node_ordinal = None`.
    """
    # Hai nút cùng một mỏ neo (chương và bài đầu, cùng đọc từ một banner): nút sau -- sâu hơn --
    # là nút đang mở cho nội dung theo sau.
    anchors: dict[BlockRef, int] = {}
    for node in nodes:
        anchors[node.anchor] = node.ordinal

    out: list[IndexChunk] = []
    current: int | None = None
    refs: list[BlockRef] = []
    texts: list[str] = []
    pages: list[int] = []

    def flush() -> None:
        if not refs:
            return
        text = "\n".join(texts)
        out.append(
            IndexChunk(
                document_id=document_id,
                ordinal=len(out),
                node_ordinal=current,
                blocks=tuple(refs),
                text=text,
                page_start=min(pages),
                page_end=max(pages),
                char_count=len(text),
            )
        )
        refs.clear()
        texts.clear()
        pages.clear()

    for unit in units:
        if unit.ref in anchors and anchors[unit.ref] != current:
            flush()
            current = anchors[unit.ref]
        text = unit.text.strip()
        if unit.kind in NOT_CONTENT or not text:
            continue
        if texts and sum(len(one) + 1 for one in texts) + len(text) > max_chars:
            flush()
        refs.append(unit.ref)
        texts.append(text)
        pages.append(unit.ref.page)
    flush()
    return out


def node_text(chunks: list[IndexChunk], ordinal: int, limit: int) -> str:
    """Chữ của riêng một nút (không gồm nút con), cắt ở `limit` ký tự -- đầu vào của tóm tắt.

    Args:
        chunks: Mọi chunk.
        ordinal: Nút.
        limit: Trần ký tự.

    Returns:
        Chữ nối lại.
    """
    text = "\n".join(chunk.text for chunk in chunks if chunk.node_ordinal == ordinal)
    return text[:limit]
