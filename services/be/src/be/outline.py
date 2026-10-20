"""Dàn ý đề (ADR-29, `draft-outline`): BE kiểm các mục Kriky viết. Hàm thuần: không database, không
mạng.

Từ ADR-30 (`kriky-writes-every-word`), chữ trên màn hình **do Kriky viết** (Markdown), không do BE
dựng; các mục có cấu trúc là thứ duy nhất đi vào job. Từ hậu ký 20/10/2026 của ADR-30, BE **không
đụng vào lời ấy**: không đối chiếu lời với các mục, không bắt hình dạng công thức. Lời Kriky lên
khung chat nguyên vẹn. BE chỉ kiểm thứ một job soạn câu cần: tổng số câu, mục có nội dung, bài nguồn
có thật.
"""

from collections.abc import Iterable, Sequence

from contracts import OutlineItem

# Trần số câu một lần xin (ADR-29): cũng là trần số phần đọc của `read_section`.
MOST_QUESTIONS_ASKED = 10
# Trần chữ của một mục. Một mục là thứ giáo viên đọc từng dòng; dài hơn thế là một bài giảng, không
# phải một mục dàn ý -- và mười mục phải còn đọc hết được trong một lượt chat.
_MOST_KNOWLEDGE = 600
_MOST_APPROACH = 600
_MOST_FORMULAS = 6
_MOST_FORMULA = 200


def validate(
    items: Sequence[OutlineItem],
    known_nodes: Iterable[int] | None,
    *,
    most: int = MOST_QUESTIONS_ASKED,
) -> str | None:
    """Lý do một dàn ý không dùng được, bằng lời model đọc rồi sửa được; `None` khi dùng được.

    Hình dạng đã do `OutlineItem` kiểm; ở đây là luật của việc soạn, cần cây để so. Chữ của công
    thức thì không: một công thức có chữ ngoài cặp `$` (*"$f'(x)>0 \\Rightarrow f$ đồng biến"*) vẫn
    đọc được trong prompt soạn câu, nơi duy nhất nó đi tới. Luật *đúng một cặp `$`* từng làm 50
    trong 59 lần trả về dàn ý ở thử tay đầu-cuối 20/10/2026, nên đã bỏ.

    Args:
        items: Các mục Kriky viết.
        known_nodes: `ordinal` mọi nút của tài liệu đang gắn; `None` khi đề không có tài liệu -- khi
            ấy mục không được trỏ về nút nào.
        most: Trần tổng số câu: `MOST_QUESTIONS_ASKED`, hay ít hơn khi đề đã gần đủ năm mươi câu.

    Returns:
        Lời từ chối, hoặc `None`.
    """
    if not items:
        return "dàn ý chưa có mục nào"
    total = sum(item.questions for item in items)
    if not 1 <= total <= most:
        return f"tổng số câu của dàn ý là {total}; mỗi lần chỉ soạn 1 đến {most} câu"
    known = set(known_nodes) if known_nodes is not None else None
    for index, item in enumerate(items, start=1):
        if not item.knowledge.strip() or not item.approach.strip():
            return f"mục {index} thiếu kiến thức hoặc cách làm"
        if len(item.knowledge) > _MOST_KNOWLEDGE or len(item.approach) > _MOST_APPROACH:
            return f"mục {index} dài quá: kiến thức và cách làm mỗi phần tối đa 600 ký tự"
        if len(item.formulas) > _MOST_FORMULAS:
            return f"mục {index} có quá {_MOST_FORMULAS} công thức"
        if any(len(formula) > _MOST_FORMULA for formula in item.formulas):
            return f"mục {index}: một công thức dài quá {_MOST_FORMULA} ký tự"
        if known is None and item.source_nodes:
            return f"mục {index} trỏ về tài liệu, nhưng đề này không có tài liệu"
        if known is not None:
            if not item.source_nodes:
                return f"mục {index} chưa nói dựa vào bài nào của tài liệu (source_nodes)"
            stray = [one for one in item.source_nodes if one not in known]
            if stray:
                return f"mục {index} trỏ về node {stray} không có trong tài liệu"
    return None


def stored(
    items: Sequence[OutlineItem], *, version: int, first: int, document_id: str
) -> dict[str, object]:
    """`tool_result` của lượt dàn ý: các mục, đúng như sẽ được đóng băng khi giáo viên đồng ý.

    Args:
        items: Các mục, đã qua `validate`.
        version: Bản thứ mấy.
        first: Số câu đầu tiên dàn ý phủ.
        document_id: Tài liệu đang gắn, rỗng khi không có.

    Returns:
        Dict lưu trên `TeacherTurn.tool_result`.
    """
    return {
        "version": version,
        "first": first,
        "total": sum(item.questions for item in items),
        "document_id": document_id,
        "items": [item.model_dump(mode="json") for item in items],
    }
