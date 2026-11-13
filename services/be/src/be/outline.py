"""Dàn ý đề (ADR-29, ADR-38): thứ BE kiểm của một dàn ý Kriky viết. Hàm thuần: không database,
không mạng.

Từ ADR-38, dàn ý là **lời Markdown** của Kriky, in nguyên văn ra chat (ADR-30) -- BE không đọc nội
dung của nó. Đi kèm lời chỉ có một con số số câu và các bài nguồn khi có sách. BE kiểm đúng hai
thứ ấy: số câu trong trần mỗi lần xin (và trần cả đề), bài nguồn có thật trong cây của tài liệu.
Khi giáo viên đồng ý, chính AGENT chia lời ấy thành câu (`NextStepCompleted.split`).
"""

from collections.abc import Iterable, Sequence

# Trần số câu một lần xin (ADR-29): cũng là trần số phần đọc của `read_section`.
MOST_QUESTIONS_ASKED = 10


def validate(
    questions: int,
    nodes: Sequence[int],
    known_nodes: Iterable[int] | None,
    *,
    most: int = MOST_QUESTIONS_ASKED,
    replacing: bool = False,
) -> str | None:
    """Lý do một dàn ý không dùng được, bằng lời model đọc rồi sửa được; `None` khi dùng được.

    Args:
        questions: Số câu Kriky ghi cho dàn ý.
        nodes: Các bài nguồn Kriky ghi (`ordinal` trong cây tài liệu).
        known_nodes: `ordinal` mọi nút của tài liệu đang gắn; `None` khi đề không có tài liệu -- khi
            ấy dàn ý không được trỏ về nút nào.
        most: Trần số câu: `MOST_QUESTIONS_ASKED`, ít hơn khi đề đã gần đủ năm mươi câu, và 1 khi
            dàn ý là để thay một câu.
        replacing: Dàn ý là để thay một câu -- lời từ chối nói đúng việc ấy. Không suy từ `most`:
            soạn thêm khi đề còn đúng một chỗ cũng có `most` là 1 (review pha 2).

    Returns:
        Lời từ chối, hoặc `None`.
    """
    if not 1 <= questions <= most:
        if replacing:
            return f"dàn ý thay câu chỉ có 1 câu, không phải {questions}"
        return f"dàn ý có {questions} câu; mỗi lần chỉ soạn 1 đến {most} câu"
    known = set(known_nodes) if known_nodes is not None else None
    if known is None and nodes:
        return "dàn ý trỏ về tài liệu, nhưng đề này không có tài liệu"
    if known is not None:
        if not nodes:
            return "dàn ý chưa nói dựa vào bài nào của tài liệu (outline_nodes)"
        stray = sorted({one for one in nodes if one not in known})
        if stray:
            return f"dàn ý trỏ về node {stray} không có trong tài liệu"
    return None


def stored(
    questions: int, nodes: Sequence[int], *, version: int, first: int, document_id: str
) -> dict[str, object]:
    """`tool_result` của lượt dàn ý: thứ BE giữ lại để cổng duyệt so plan với nó (ADR-38).

    Args:
        questions: Số câu của dàn ý, đã qua `validate`.
        nodes: Bài nguồn, đã qua `validate`.
        version: Bản thứ mấy.
        first: Số câu đầu tiên dàn ý phủ.
        document_id: Tài liệu đang gắn, rỗng khi không có.

    Returns:
        Dict lưu trên `TeacherTurn.tool_result`.
    """
    return {
        "version": version,
        "first": first,
        "total": questions,
        "document_id": document_id,
        "nodes": sorted(set(nodes)),
    }
