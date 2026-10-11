"""Từ các quyết định tới **cây ba cấp**. Hàm thuần: Jev và luật quyết từng ứng viên, code dựng cây.

Tách khỏi Jev vì ba việc ở đây là việc Jev làm kém (jaggedness 1.13: đếm, thứ tự, số), và vì chúng
phải **đúng mọi lần**, không đúng theo xác suất:

- **Gộp bậc sâu** -- một quyết định cấp 4 (`DEEPER`) không thành nút; nội dung của nó nằm trong
  chunk của nút cha (người dùng chốt ba cấp, 11/10/2026).
- **Không nhảy cấp** -- một nút không sâu hơn nút đang mở quá một cấp: cấp 3 ngay sau cấp 1 thành
  cấp 2, và nút đầu tiên của tài liệu luôn là cấp 1. Một cây có lỗ hổng làm tool lần xuống lạc.
- **Chương từ banner** (D9) -- tên chương của SGK nằm trong ảnh, nên nút cấp 1 đến từ `Banner`,
  không từ một ứng viên chữ.
"""

from dataclasses import dataclass

from contracts import MAX_LEVEL, BlockRef, IndexNode, TitleSource
from document.index.features import Candidate, fold
from document.index.rules import Decision

# Nhãn số nào được giữ làm `numbering` của nút. *"Bài tập cuối chương II"* thì không: cả dòng
# là tên.
_SHOWN_SCHEMES = frozenset({"chapter", "lesson", "dotted", "roman", "letter", "number"})


@dataclass(frozen=True)
class Banner:
    """Một banner mở chương, đã đọc bằng `gpt-5.6-luna` hoặc chỉ biết số thứ tự.

    Attributes:
        ref: Khối hình của banner -- mỏ neo của nút.
        chapter_label: Nhãn chương như in (*"Chương II"*), hoặc *"Chương N"* đếm theo thứ tự cổng.
        chapter_title: Tên chương luna đọc được, `None` khi không đọc được.
        lesson_label: Nhãn bài in ngay dưới banner (*"Bài 8"*), `None` khi không có.
        lesson_title: Tên bài ấy.
    """

    ref: BlockRef
    chapter_label: str
    chapter_title: str | None = None
    lesson_label: str | None = None
    lesson_title: str | None = None


@dataclass(frozen=True)
class _Heading:
    ref: BlockRef
    order: int
    level: int
    numbering: str | None
    title: str
    source: TitleSource
    confidence: float


def headings(decided: list[tuple[Candidate, Decision]], banners: list[Banner]) -> list[_Heading]:
    """Mọi tiêu đề sẽ thành nút, theo thứ tự đọc, **trước** khi chỉnh cấp.

    Args:
        decided: Ứng viên và quyết định, theo thứ tự đọc.
        banners: Các banner mở chương.

    Returns:
        Các tiêu đề.
    """
    out: list[_Heading] = []
    for banner in banners:
        title = banner.chapter_title or banner.chapter_label
        source = TitleSource.BANNER if banner.chapter_title else TitleSource.NUMBERING
        out.append(_Heading(banner.ref, 0, 1, banner.chapter_label, title, source, 1.0))
        if banner.lesson_title:
            out.append(
                _Heading(
                    banner.ref,
                    1,
                    2,
                    banner.lesson_label,
                    banner.lesson_title,
                    TitleSource.BANNER,
                    1.0,
                )
            )

    banner_pages = {banner.ref.page: banner for banner in banners}
    for candidate, decision in decided:
        if not decision.is_node or decision.level is None:
            continue
        page = candidate.unit.ref.page
        banner = banner_pages.get(page)
        # Một trang mở chương đã có nút cấp 1 (và có thể cấp 2) từ banner: chữ cùng cấp trên chính
        # trang ấy là bản lặp của cùng tên -- hoặc tên bài mà luna đã đọc.
        if banner and (decision.level == 1 or (decision.level == 2 and banner.lesson_title)):
            continue
        found = candidate.numbering
        shown = found.label if found and found.scheme in _SHOWN_SCHEMES else None
        if found and found.scheme == "chapter_end" and found.value:
            # Dựng tên từ nhãn đã tách, không giữ rác OCR (*"BÀl TẬP CUỐl CHƯƠNG |"*).
            title = f"BÀI TẬP CUỐI {found.label.upper()}"
        else:
            # `bare` chứ không `unit.text`: một dòng `.md` không mang dấu `#` vào tên nút.
            title = (candidate.title if shown else candidate.bare or candidate.unit.text).strip()
        out.append(
            _Heading(
                candidate.unit.ref,
                2,
                decision.level,
                shown,
                title,
                TitleSource.TEXT,
                decision.confidence,
            )
        )
    return sorted(out, key=_reading_order)


def _reading_order(heading: _Heading) -> tuple[int, int, int, int]:
    ref = heading.ref
    return (ref.page, ref.block, ref.line or 0, heading.order)


def assemble(
    document_id: str,
    found: list[_Heading],
    page_count: int,
    printed: dict[int, int],
    offset: int | None,
) -> list[IndexNode]:
    """Dựng cây: chỉnh cấp, gán cha, tính trang.

    Args:
        document_id: Id tài liệu.
        found: Kết quả của `headings`.
        page_count: Số trang của tài liệu.
        printed: Trang tệp → trang in.
        offset: Độ lệch phổ biến giữa trang tệp và trang in.

    Returns:
        Các nút, thứ tự preorder.
    """
    kept: list[tuple[_Heading, int]] = []
    depth = 0
    for heading in found:
        level = min(heading.level, depth + 1, MAX_LEVEL)
        if kept:
            last, last_level = kept[-1]
            # Cùng một tên, cùng cấp, liền nhau: một tiêu đề OCR thấy hai lần (hai khối chồng nhau).
            if last_level == level and fold(last.title) == fold(heading.title):
                continue
        kept.append((heading, level))
        depth = level

    nodes: list[IndexNode] = []
    open_at: dict[int, int] = {}
    for ordinal, (heading, level) in enumerate(kept):
        open_at = {key: value for key, value in open_at.items() if key < level}
        parent = open_at.get(level - 1)
        open_at[level] = ordinal
        start = heading.ref.page
        end = page_count
        for later, later_level in kept[ordinal + 1 :]:
            if later_level <= level:
                end = max(start, later.ref.page)
                break
        nodes.append(
            IndexNode(
                document_id=document_id,
                ordinal=ordinal,
                parent_ordinal=parent,
                level=level,
                numbering=heading.numbering,
                title=heading.title,
                title_source=heading.source,
                anchor=heading.ref,
                page_start=start,
                page_end=end,
                printed_start=_printed(start, printed, offset),
                printed_end=_printed(end, printed, offset),
                confidence=heading.confidence,
            )
        )
    return nodes


def _printed(page: int, printed: dict[int, int], offset: int | None) -> int | None:
    """Số trang in của một trang tệp: đọc được thì dùng, không thì suy từ độ lệch phổ biến.

    Args:
        page: Trang tệp.
        printed: Trang tệp → trang in đọc được.
        offset: Độ lệch phổ biến.

    Returns:
        Trang in, `None` khi không biết hoặc suy ra số không dương.
    """
    if page in printed:
        return printed[page]
    if offset is None or page - offset < 1:
        return None
    return page - offset
