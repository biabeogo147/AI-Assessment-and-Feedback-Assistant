"""Mỗi câu một mục kiến thức (plan 4b, hậu ký ADR-27). Hàm thuần: không database, không mạng.

Phạm vi một đề (các nút giáo viên chọn) được chia thành **đơn vị**: mỗi nút trong cây con của
phạm vi mà **có đoạn nội dung của riêng nó** -- một bài, một mục, hay phần mở đầu của một chương
trước bài đầu tiên. Rồi:

- số câu ≤ số đơn vị → mỗi câu một đơn vị khác nhau, ưu tiên đơn vị dài hơn (rải theo độ dài nội
  dung), giữ thứ tự đọc;
- số câu > số đơn vị → mọi đơn vị ít nhất một câu, phần dư rải theo độ dài; một đơn vị có k câu thì
  tách các đoạn của nó thành k nhóm **liên tiếp** -- hai câu chung một bài vẫn đứng trên hai đoạn
  khác nhau. Chỉ khi một đơn vị nhận nhiều câu hơn số đoạn của nó thì hai câu mới chung một đoạn.

Gán **một lần**: câu đã có ô giữ ô của nó; câu mới nhận những ô còn trống của phép chia cho tổng mới
(`assign`). Đó là điều `DraftItem` đóng băng -- soạn thêm câu không xáo câu đã xong.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from contracts import IndexChunk, IndexNode

# Trần chữ của `focus_text` gửi một job: đủ một bài SGK (vài đoạn 1 500 ký tự), không đủ để prompt
# một câu hỏi thành cả cuốn sách.
FOCUS_CHARS = 4000
# Trần số tiêu đề `other_foci`: một đề 50 câu không cần cả 49 tiêu đề kia để biết tránh gì.
OTHER_FOCI = 30


@dataclass(frozen=True)
class Unit:
    """Một đơn vị kiến thức: một nút có đoạn nội dung của riêng nó.

    Attributes:
        node: `ordinal` của nút.
        title: Đường dẫn tiêu đề từ gốc tới nút -- *"Chương I. X › Bài 2. Y"*.
        chunks: `(ordinal, char_count)` các đoạn của nút, thứ tự đọc.
    """

    node: int
    title: str
    chunks: tuple[tuple[int, int], ...]

    @property
    def weight(self) -> int:
        """Độ dài nội dung, ít nhất 1."""
        return max(1, sum(chars for _, chars in self.chunks))


@dataclass(frozen=True)
class Slot:
    """Ô của một câu: một đơn vị, và nhóm đoạn trong đơn vị ấy.

    Attributes:
        node: `ordinal` của đơn vị.
        chunks: `ordinal` các đoạn của nhóm.
    """

    node: int
    chunks: tuple[int, ...]


def heading(node: IndexNode) -> str:
    """Nhãn số và tên một nút: *"Bài 3. Phép cộng"*, *"1. HỆ THẬP PHÂN"*.

    Nhãn số kiểu *"1."*, *"I."*, *"A."* đã mang sẵn dấu chấm (`document/index/features.py`),
    nên chỉ thêm dấu chấm khi nhãn chưa có -- không thì ra *"1.. HỆ THẬP PHÂN"* (review B7).

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


def units_in_scope(
    nodes: Iterable[IndexNode], chunks: Iterable[IndexChunk], scope: Iterable[int]
) -> list[Unit]:
    """Các đơn vị kiến thức trong cây con của phạm vi, thứ tự đọc.

    Args:
        nodes: Mọi nút của cây.
        chunks: Các đoạn (ít nhất của mọi nút trong phạm vi).
        scope: `ordinal` các nút giáo viên chọn.

    Returns:
        Các đơn vị có ít nhất một đoạn.
    """
    nodes = list(nodes)
    by_ordinal = {node.ordinal: node for node in nodes}
    inside = scope_of(nodes, scope)

    owned: dict[int, list[tuple[int, int]]] = {}
    for chunk in sorted(chunks, key=lambda one: one.ordinal):
        if chunk.node_ordinal in inside:
            owned.setdefault(chunk.node_ordinal, []).append((chunk.ordinal, chunk.char_count))

    def title(ordinal: int) -> str:
        path = []
        current: int | None = ordinal
        while current is not None and current in by_ordinal:
            path.append(heading(by_ordinal[current]))
            current = by_ordinal[current].parent_ordinal
        return " › ".join(reversed(path))

    return [
        Unit(node=ordinal, title=title(ordinal), chunks=tuple(owned[ordinal]))
        for ordinal in sorted(owned)
    ]


def _groups(chunks: tuple[tuple[int, int], ...], count: int) -> list[tuple[int, ...]]:
    """Tách các đoạn thành `count` nhóm liên tiếp, không nhóm nào rỗng, độ dài gần bằng nhau.

    Nhiều nhóm hơn số đoạn thì mỗi đoạn một nhóm rồi lặp lại đoạn cuối -- trường hợp duy nhất hai
    câu chung một đoạn.
    """
    if count > len(chunks):
        every = [(ordinal,) for ordinal, _ in chunks]
        return every + [every[-1]] * (count - len(every))
    total = sum(max(chars, 1) for _, chars in chunks)
    groups: list[list[int]] = [[]]
    seen = 0
    for index, (ordinal, chars) in enumerate(chunks):
        left = len(chunks) - index
        need = count - len(groups)
        # Mở nhóm mới khi nhóm này đã đủ phần của nó, hoặc khi số đoạn còn lại vừa đủ cho số nhóm
        # còn thiếu -- không bao giờ để một nhóm rỗng.
        if groups[-1] and need > 0 and (seen >= total * len(groups) / count or left == need):
            groups.append([])
        groups[-1].append(ordinal)
        seen += max(chars, 1)
    return [tuple(group) for group in groups]


def slots(units: list[Unit], total: int) -> list[Slot]:
    """Chia `total` câu lên các đơn vị, thứ tự đọc.

    Args:
        units: Các đơn vị, thứ tự đọc.
        total: Tổng số câu của đề.

    Returns:
        Đúng `total` ô (rỗng khi không có đơn vị nào).
    """
    if not units or total <= 0:
        return []
    if total <= len(units):
        # Đơn vị dài hơn trước; hoà thì theo thứ tự đọc. Rồi trả lại thứ tự đọc.
        chosen = sorted(range(len(units)), key=lambda index: (-units[index].weight, index))[:total]
        return [
            Slot(units[index].node, tuple(ordinal for ordinal, _ in units[index].chunks))
            for index in sorted(chosen)
        ]

    counts = [1] * len(units)
    for _ in range(total - len(units)):
        # Câu kế đi vào đơn vị có độ dài *trên mỗi câu* lớn nhất, ưu tiên đơn vị còn đoạn chưa chia.
        def share(index: int) -> tuple[bool, float, int]:
            room = counts[index] < len(units[index].chunks)
            return (room, units[index].weight / (counts[index] + 1), -index)

        counts[max(range(len(units)), key=share)] += 1

    out: list[Slot] = []
    for unit, count in zip(units, counts, strict=True):
        out.extend(Slot(unit.node, group) for group in _groups(unit.chunks, count))
    return out


def assign(
    units: list[Unit], total: int, taken: Mapping[int, Slot], wanted: Iterable[int]
) -> dict[int, Slot]:
    """Ô cho những câu chưa có ô, giữ nguyên ô của câu đã có.

    Ô của phép chia cho tổng mới bị **trừ** dần bởi các câu đã có: mỗi câu cũ lấy đi một ô cùng đơn
    vị, ưu tiên ô trùng đúng nhóm đoạn. Câu mới nhận những ô còn lại theo thứ tự đọc.

    Args:
        units: Các đơn vị, thứ tự đọc.
        total: Tổng số câu của đề sau lần soạn này.
        taken: `ordinal` câu → ô đã đóng băng.
        wanted: `ordinal` các câu cần ô.

    Returns:
        `ordinal` → ô, cho mọi câu trong `wanted`. Rỗng khi không có đơn vị nào.
    """
    free = slots(units, total)
    if not free:
        return {}
    for slot in taken.values():
        same = [index for index, one in enumerate(free) if one == slot] or [
            index for index, one in enumerate(free) if one.node == slot.node
        ]
        if same:
            free.pop(same[0])
    full = slots(units, total)
    out: dict[int, Slot] = {}
    for position, ordinal in enumerate(sorted(wanted)):
        # Hết ô trống (giáo viên soạn thêm vượt phép chia cũ): quay vòng trên phép chia đầy đủ.
        out[ordinal] = free.pop(0) if free else full[position % len(full)]
    return out
