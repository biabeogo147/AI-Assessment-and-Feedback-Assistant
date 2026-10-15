"""Đọc cây mục lục của một tài liệu: nhãn một nút, cây con của một phạm vi, và phép gộp phạm vi
thành các phần đọc (`draft-outline`, ADR-29). Hàm thuần: không database, không mạng.

Kriky đọc phạm vi trước khi viết dàn ý, và một lượt chat chỉ có chừng ấy bước. Nên phạm vi được
**gộp** -- không bao giờ chặt một nút -- thành tối đa bao nhiêu phần bằng số câu giáo viên xin:
xin 8 câu thì đọc nhiều nhất 8 lần; phạm vi ít nút hơn thì ít phần hơn, và dàn ý cho vài câu chung
một đoạn nhưng khác cách làm. Người dùng chốt 15/10/2026.
"""

from collections.abc import Iterable

from contracts import IndexNode


def heading(node: IndexNode) -> str:
    """Nhãn số và tên một nút: *"Bài 3. Phép cộng"*, *"1. HỆ THẬP PHÂN"*.

    Nhãn số kiểu *"1."*, *"I."*, *"A."* đã mang sẵn dấu chấm (`document/index/features.py`), nên chỉ
    thêm dấu chấm khi nhãn chưa có -- không thì ra *"1.. HỆ THẬP PHÂN"* (review B7,
    `draft-from-document`).

    Args:
        node: Nút cây.

    Returns:
        Nhãn số và tên, hoặc tên trần.
    """
    if not node.numbering:
        return node.title
    joiner = " " if node.numbering.endswith(".") else ". "
    return f"{node.numbering}{joiner}{node.title}"


def scope_of(nodes: Iterable[IndexNode], scope: Iterable[int]) -> set[int]:
    """`ordinal` mọi nút trong cây con của phạm vi, kể cả chính các nút phạm vi.

    Args:
        nodes: Mọi nút của cây.
        scope: `ordinal` các nút giáo viên chọn.

    Returns:
        Tập `ordinal`; nút lạ trong `scope` bị bỏ qua.
    """
    known = {node.ordinal for node in nodes}
    children: dict[int, list[int]] = {}
    for node in nodes:
        if node.parent_ordinal is not None:
            children.setdefault(node.parent_ordinal, []).append(node.ordinal)
    inside: set[int] = set()
    waiting = [one for one in scope if one in known]
    while waiting:
        current = waiting.pop()
        if current not in inside:
            inside.add(current)
            waiting.extend(children.get(current, []))
    return inside


def title_path(nodes: Iterable[IndexNode], ordinal: int) -> str:
    """Đường dẫn tiêu đề từ gốc tới một nút: *"Chương I. X › Bài 2. Y"*.

    Args:
        nodes: Mọi nút của cây.
        ordinal: Nút cần đường dẫn.

    Returns:
        Các nhãn nối bằng *"›"*; rỗng khi nút không có.
    """
    by_ordinal = {node.ordinal: node for node in nodes}
    path = []
    current: int | None = ordinal
    while current is not None and current in by_ordinal:
        path.append(heading(by_ordinal[current]))
        current = by_ordinal[current].parent_ordinal
    return " › ".join(reversed(path))


def parts(weights: list[int], questions: int) -> list[list[int]]:
    """Gộp các đơn vị liên tiếp thành `min(questions, len(weights))` phần, cân theo độ dài.

    Chỉ gộp, không tách: mỗi đơn vị nằm trọn trong một phần, và thứ tự đọc giữ nguyên. Một phần
    được đóng khi nó đã đủ phần của nó trên tổng độ dài, hoặc khi số đơn vị còn lại vừa đủ cho số
    phần còn thiếu -- không phần nào rỗng.

    Args:
        weights: Độ dài từng đơn vị, thứ tự đọc.
        questions: Số câu giáo viên xin -- trần số phần.

    Returns:
        Các phần, mỗi phần là danh sách chỉ số vào `weights`. Rỗng khi không có đơn vị nào.
    """
    if not weights or questions <= 0:
        return []
    count = min(questions, len(weights))
    total = sum(max(one, 1) for one in weights)
    out: list[list[int]] = [[]]
    seen = 0
    for index, weight in enumerate(weights):
        left = len(weights) - index
        need = count - len(out)
        if out[-1] and need > 0 and (seen >= total * len(out) / count or left == need):
            out.append([])
        out[-1].append(index)
        seen += max(weight, 1)
    return out
