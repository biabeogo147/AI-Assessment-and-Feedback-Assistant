"""Dàn ý đề (ADR-29, `draft-outline`): BE kiểm các mục Kriky viết, rồi dựng chữ giáo viên đọc. Hàm
thuần: không database, không mạng.

Chữ trên màn hình **do BE dựng** từ các mục đã lưu, không do model kể lại: thứ giáo viên duyệt và
thứ các job soạn câu nhận phải là một. Cùng tinh thần với phương án hỏi lại do BE viết từ hàng nó
đọc (ADR-23) -- model đề xuất, BE in.

Bản đọc của sách hiện chỉ có chữ (OCR), nên không công thức nào chép được từ sách: chữ dựng ở đây
luôn gọi chúng là công thức **Kriky đề xuất** (ADR-29).
"""

import re
from collections.abc import Iterable, Mapping, Sequence

from contracts import OutlineItem

# Trần số câu một lần xin (ADR-29): cũng là trần số phần đọc của `read_section`.
MOST_QUESTIONS_ASKED = 10
# Trần chữ của một mục. Một mục là thứ giáo viên đọc từng dòng; dài hơn thế là một bài giảng, không
# phải một mục dàn ý -- và mười mục phải còn đọc hết được trong một lượt chat.
_MOST_KNOWLEDGE = 600
_MOST_APPROACH = 600
_MOST_FORMULAS = 6
_MOST_FORMULA = 200
# Một công thức nằm trong cặp `$` (`MathText` dựng phần ở giữa), và không gì khác.
_FORMULA = re.compile(r"^\$[^$]+\$$")

CLOSING = (
    'Bạn đồng ý với dàn ý này chứ? Muốn đổi câu nào, cứ nói, ví dụ: "câu 2 đổi sang …". '
    "Câu hỏi chỉ được soạn sau khi bạn đồng ý."
)


def validate(
    items: Sequence[OutlineItem],
    known_nodes: Iterable[int] | None,
    *,
    most: int = MOST_QUESTIONS_ASKED,
) -> str | None:
    """Lý do một dàn ý không dùng được, bằng lời model đọc rồi sửa được; `None` khi dùng được.

    Hình dạng đã do `OutlineItem` kiểm; ở đây là luật nội dung, cần cây để so.

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
        for formula in item.formulas:
            if len(formula) > _MOST_FORMULA or not _FORMULA.match(formula.strip()):
                return f"mục {index}: mỗi công thức là một biểu thức trong một cặp $, như $a+b$"
        if known is None and item.source_nodes:
            return f"mục {index} trỏ về tài liệu, nhưng đề này không có tài liệu"
        if known is not None:
            if not item.source_nodes:
                return f"mục {index} chưa nói dựa vào bài nào của tài liệu (source_nodes)"
            stray = [one for one in item.source_nodes if one not in known]
            if stray:
                return f"mục {index} trỏ về node {stray} không có trong tài liệu"
    return None


def _questions(first: int, count: int) -> str:
    return f"Câu {first}" if count == 1 else f"Câu {first}–{first + count - 1}"


def render(
    intro: str,
    items: Sequence[OutlineItem],
    labels: Mapping[int, str],
    *,
    version: int,
    first: int = 1,
) -> str:
    """Chữ dàn ý giáo viên đọc trong chat: lời mở của Kriky, các mục, câu kết của BE.

    Chữ thường, không Markdown -- ô trả lời chỉ dựng toán trong `$`. Bài nguồn hiện bằng nhãn BE
    dựng (`teacher_tools.node_label`), không bằng số nút.

    Args:
        intro: Câu mở đầu Kriky viết; rỗng thì không có.
        items: Các mục, đã qua `validate`.
        labels: `ordinal` → nhãn bài, cho mọi nút các mục trỏ tới.
        version: Bản thứ mấy của dàn ý trong đoạn chat này.
        first: Số của câu đầu tiên dàn ý phủ -- 1 cho đề mới, câu kế tiếp khi soạn thêm, chính câu
            bị thay khi thay một câu.

    Returns:
        Chữ hiện ra, đúng như sẽ lưu.
    """
    total = sum(item.questions for item in items)
    lines = [intro.strip(), ""] if intro.strip() else []
    lines.append(f"Dàn ý — {total} câu (bản {version})")
    number = first
    for item in items:
        lines += ["", f"{_questions(number, item.questions)} · {item.knowledge.strip()}"]
        if item.formulas:
            formulas = "; ".join(one.strip() for one in item.formulas)
            lines.append(f"  Công thức Kriky đề xuất: {formulas}")
        lines.append(f"  Cách làm: {item.approach.strip()}")
        sources = [labels[one] for one in item.source_nodes if one in labels]
        if sources:
            lines.append(f"  Theo: {'; '.join(sources)}")
        number += item.questions
    lines += ["", CLOSING]
    return "\n".join(lines)


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
