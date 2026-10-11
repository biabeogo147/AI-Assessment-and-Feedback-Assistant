"""Từ bản thô tới **ứng viên**: khối nào có thể là một mục, và nó trông thế nào.

Mọi thứ ở đây là hàm thuần trên `RawPage`. Không gọi mạng, không gọi model: phần này quyết **ai
được hỏi** và **hỏi kèm thông tin gì**, còn quyết định là việc của Jev (`jev.py`) hoặc của luật
(`rules.py`).

Ba điều đo được trên Lớp 6 tập 1 (plan 3c, *Dữ liệu thật đổi thiết kế*) định hình module này:

- **Nhãn số bị OCR làm lệch** -- *"1, HÌNH CHỮ NHẬT"*, *"2 HÌNH VUÔNG"*, *"1.sỐ NGUYÊN TỐ"*, *"BÀl
  TẬP CUỐl CHƯƠNG"*. Nên mọi mẫu chạy trên chữ đã **gấp** (bỏ dấu, viết hoa, `l`/`|` thành `I`
  trong số La Mã), và phép gấp giữ nguyên độ dài để phần tên lấy lại được từ chữ gốc.
- **Jev không đọc số tốt** (jaggedness của 1.13), nên vị trí và cỡ chữ được **kể bằng lời**
  (*"top of page, centered"*), không đưa toạ độ.
- **Khối hình không bao giờ là ứng viên** (D2): hộp layout chồng nhau, nên chữ của nó có thể lặp chữ
  của khối bên cạnh. Chữ ấy chỉ dùng cho cổng banner (`banner_gates`).
"""

import re
import statistics
import unicodedata
from collections import Counter
from dataclasses import dataclass

from contracts import BlockRef, RawPage, RawSource

# Nhãn khối của PP-DocLayout mà OCR có thể gán cho một tiêu đề.
_TITLE_KINDS = frozenset({"doc_title", "paragraph_title"})
# Nhãn khối không bao giờ là ứng viên và không bao giờ là nội dung của một chunk.
NOT_CONTENT = frozenset({"image", "header", "footer", "number", "table"})

# Trần độ dài của một tiêu đề, tính bằng ký tự. Tiêu đề dài nhất của Lớp 6 tập 1 là 62 ký tự
# (*"CHU VI, DIỆN TÍCH CỦA HÌNH VUÔNG, HÌNH CHỮ NHẬT, HÌNH THANG"*); 120 chừa chỗ cho sách khác
# mà vẫn loại được một đoạn văn.
_MAX_TITLE_CHARS = 120
# Một khối `text` (không phải nhãn tiêu đề) chỉ thành ứng viên khi nó **ngắn hơn** thế này và mang
# nhãn số: OCR đôi khi gán `text` cho chính dòng mục *"1. HỆ THẬP PHÂN"*.
_MAX_TEXT_CANDIDATE_CHARS = 90
# Tỉ lệ chữ in hoa trên tổng chữ cái để một dòng được coi là *viết hoa*.
_UPPER_RATIO = 0.6
# Độ dài đoạn chữ kế tiếp gửi kèm làm ngữ cảnh.
_NEXT_TEXT_CHARS = 120
# Số dòng tối đa của một khối text layer còn được coi là tiêu đề: số mục một dòng, tên một dòng.
_TEXT_LAYER_LINES = 2
# Một dòng ngắn hơn thế này đứng ngay sau *"Chương N"* trơ trọi là tên của chương ấy.
_CHAPTER_NAME_CHARS = 80


@dataclass(frozen=True)
class Numbering:
    """Nhãn số đầu một dòng, như code tách được.

    Attributes:
        scheme: Loại nhãn: `chapter` (*Chương/Phần + số*), `lesson` (*Bài N*), `chapter_end`
            (*Bài tập cuối chương N*), `dotted` (*I.1*, *A.I.1*, *1.2*), `roman` (*I.*), `letter`
            (*A.*), `number` (*1.*), `sub` (*a)*).
        label: Nhãn chuẩn hoá để in và so: *"Chương II"*, *"Bài 8"*, *"1."*, *"I.1"*.
        depth: Số tầng của nhãn: *"I"* là 1, *"I.1"* là 2, *"I.1.1"* là 3.
        value: Số cuối của nhãn, để code so thứ tự (*Bài 3 sau Bài 2*) -- việc Jev làm không tốt.
        all_digits: Mọi tầng đều là chữ số Ả Rập. *"1.1"* trong SGK là **bài tập**, không phải mục.
        rest: Phần chữ sau nhãn, lấy từ chữ gốc (giữ dấu).
    """

    scheme: str
    label: str
    depth: int
    value: int | None
    all_digits: bool
    rest: str


@dataclass(frozen=True)
class Unit:
    """Một đơn vị đọc: một khối của bản thô, hoặc một dòng của tệp văn bản thuần.

    Attributes:
        ref: Vị trí trong bản thô. Với tệp thuần, `ref.line` là số dòng.
        kind: Nhãn khối của bản thô.
        text: Chữ.
        box: Hộp đã chuẩn hoá về 0..1 theo trang, `None` khi không có.
    """

    ref: BlockRef
    kind: str
    text: str
    box: tuple[float, float, float, float] | None


@dataclass(frozen=True)
class Candidate:
    """Một đơn vị có thể là tiêu đề của một mục, kèm mọi thứ người quyết cần biết.

    Attributes:
        unit: Đơn vị gốc.
        numbering: Nhãn số tách được, `None` khi không có.
        title: Chữ bỏ nhãn số.
        position: Vị trí và cỡ chữ kể bằng lời.
        repeated: *only here* / *on a few pages* / *on many pages* -- dòng lặp lại nhiều trang là
            nhãn hoạt động hoặc dòng chạy đầu trang, không phải mục.
        markdown_level: Số dấu `#` đầu dòng của một tệp `.md`, `None` ở mọi đường khác.
        next_text: Chữ của đơn vị kế tiếp, cắt ngắn.
        page_count: Tổng số trang của tài liệu.
        bare: Chữ của dòng (các dòng của khối nối bằng dấu cách), đã bỏ dấu `#` của markdown --
            tên của nút khi dòng không có nhãn số.
        source: Đường đọc của tài liệu. Luật cần nó: *"1.1."* trong SGK đọc bằng OCR là bài tập,
            còn trong một báo cáo có text layer là một mục.
    """

    unit: Unit
    numbering: Numbering | None
    title: str
    position: str
    repeated: str
    markdown_level: int | None
    next_text: str
    page_count: int
    bare: str = ""
    source: RawSource = RawSource.OCR


def fold(text: str) -> str:
    """Gấp chữ để so mẫu: bỏ dấu, viết hoa, `Đ` thành `D`. **Giữ nguyên độ dài**.

    Giữ độ dài là thứ cho phép tìm mẫu trên chữ đã gấp rồi cắt phần tên từ chữ gốc ở đúng vị trí ấy.
    Vì thế mỗi ký tự được gấp **riêng**: NFD của một ký tự NFC rồi lấy ký tự gốc đầu tiên.

    Args:
        text: Chữ NFC.

    Returns:
        Chữ cùng độ dài, chỉ còn chữ không dấu viết hoa (và các ký tự khác giữ nguyên).
    """
    out = []
    for char in text:
        if char in "đĐ":
            out.append("D")
            continue
        base = unicodedata.normalize("NFD", char)[0] if char.isalpha() else char
        out.append(base.upper() if len(base.upper()) == 1 else base)
    return "".join(out)


_ROMAN = {"I": 1, "V": 5, "X": 10}


def roman_value(token: str) -> int | None:
    """Giá trị một số La Mã nhỏ (I..XXXIX), đã sửa lỗi OCR `l`, `|`, `1` thành `I`.

    Args:
        token: Chuỗi đã gấp.

    Returns:
        Giá trị, `None` khi không phải số La Mã.
    """
    cleaned = token.replace("|", "I").replace("L", "I").replace("1", "I")
    if not cleaned or any(char not in _ROMAN for char in cleaned):
        return None
    total = 0
    for index, char in enumerate(cleaned):
        value = _ROMAN[char]
        following = _ROMAN[cleaned[index + 1]] if index + 1 < len(cleaned) else 0
        total += -value if value < following else value
    return total if total > 0 else None


def to_roman(value: int) -> str:
    """Số Ả Rập nhỏ thành La Mã, để in nhãn chương.

    Args:
        value: Từ 1 tới 39.

    Returns:
        Chuỗi La Mã.
    """
    out = ""
    for size, mark in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while value >= size:
            out += mark
            value -= size
    return out


# Mọi mẫu chạy trên chữ đã gấp, sau khi bỏ rác đầu dòng (`~`, `'`, `(`, `.`, `0 ` của OCR).
_LEADING_NOISE = re.compile(r"^[\s~'\"(.,:;\-–•*#]+")
_CHAPTER_END = re.compile(r"^BA[I1L|]?\s*TAP\s+CUO[I1L|]?\s+CHU?O?NG\s*([IVXL1|]+)(?![A-Z])")
_CHAPTER = re.compile(r"^(CHUONG|PHAN)\s+([IVXL1|]+|\d{1,2})(?![A-Z0-9])[.:]?\s*")
_LESSON = re.compile(r"^BA[IL1]\s+(\d{1,3})\b[.:]?\s*")
_DOTTED = re.compile(
    r"^((?:\d{1,2}|[IVX]{1,4}|[A-E])(?:\.(?:\d{1,2}|[IVX]{1,4})){1,3})\.?(?=\s|$)\s*"
)
_ROMAN_HEAD = re.compile(r"^([IVX]{1,4})[.)]\s+")
_LETTER_HEAD = re.compile(r"^([A-E])[.)]\s+")
_NUMBER_HEAD = re.compile(r"^(\d{1,2})(?:[.,]\s*|\s+)(?=[A-Z])")
_SUB_HEAD = re.compile(r"^([a-e])\)\s+")


def numbering(text: str) -> Numbering | None:
    """Tách nhãn số đầu một dòng.

    Thứ tự thử là có chủ ý: *"Bài tập cuối chương II"* phải thắng *"Bài N"*; *"1.1"* (nhiều tầng)
    phải thắng *"1."*.

    Args:
        text: Chữ NFC của dòng.

    Returns:
        Nhãn tách được, `None` khi dòng không bắt đầu bằng một nhãn số.
    """
    noise = _LEADING_NOISE.match(text)
    start = noise.end() if noise else 0
    folded = fold(text)[start:]
    original = text[start:]

    found = _CHAPTER_END.match(folded)
    if found:
        value = roman_value(found.group(1))
        label = f"Chương {to_roman(value)}" if value else "Chương"
        return Numbering("chapter_end", label, 1, value, False, original.strip())

    found = _CHAPTER.match(folded)
    if found:
        token = found.group(2)
        value = int(token) if token.isdigit() else roman_value(token)
        if value is not None:
            word = "Chương" if found.group(1) == "CHUONG" else "Phần"
            shown = token if token.isdigit() else to_roman(value)
            rest = original[found.end() :].strip()
            return Numbering("chapter", f"{word} {shown}", 1, value, token.isdigit(), rest)

    found = _LESSON.match(folded)
    if found:
        value = int(found.group(1))
        rest = original[found.end() :].strip()
        return Numbering("lesson", f"Bài {value}", 1, value, True, rest)

    found = _DOTTED.match(folded)
    if found:
        parts = found.group(1).split(".")
        last = parts[-1]
        value = int(last) if last.isdigit() else roman_value(last)
        digits = all(part.isdigit() for part in parts)
        rest = original[found.end() :].strip()
        return Numbering("dotted", found.group(1), len(parts), value, digits, rest)

    for scheme, pattern in (("roman", _ROMAN_HEAD), ("letter", _LETTER_HEAD)):
        found = pattern.match(folded)
        # Gấp chữ viết hoa mọi thứ, nên *"a) Tính"* cũng khớp *"A."*: nhãn phải in hoa ở chữ gốc.
        if found and original[:1].isupper():
            token = found.group(1)
            value = roman_value(token) if scheme == "roman" else ord(token) - ord("A") + 1
            rest = original[found.end() :].strip()
            return Numbering(scheme, f"{token}.", 1, value, False, rest)

    found = _NUMBER_HEAD.match(folded)
    if found:
        value = int(found.group(1))
        rest = original[found.end() :].strip()
        return Numbering("number", f"{value}.", 1, value, True, rest)

    found = _SUB_HEAD.match(text[start:])
    if found:
        rest = original[found.end() :].strip()
        return Numbering("sub", f"{found.group(1)})", 2, None, False, rest)
    return None


def upper_ratio(text: str) -> float:
    """Tỉ lệ chữ in hoa trên tổng chữ cái.

    Args:
        text: Chữ bất kỳ.

    Returns:
        0..1, 0 khi không có chữ cái nào.
    """
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    return sum(char.isupper() for char in letters) / len(letters)


def units(pages: list[RawPage]) -> list[Unit]:
    """Mọi đơn vị đọc của tài liệu, theo thứ tự đọc.

    Tệp văn bản thuần có đúng một khối; nó được tách thành **dòng trong bộ nhớ** (D8) -- bản thô
    không bị sửa, và `BlockRef.line` giữ số dòng để chunk trỏ ngược về được.

    Args:
        pages: Các trang, trang 1 trước.

    Returns:
        Các đơn vị.
    """
    out: list[Unit] = []
    for page in pages:
        for index, block in enumerate(page.blocks):
            if page.source is RawSource.PLAIN:
                for line_no, line in enumerate(block.text.split("\n")):
                    ref = BlockRef(page=page.page, block=index, line=line_no)
                    out.append(Unit(ref, block.kind, unicodedata.normalize("NFC", line), None))
                continue
            ref = BlockRef(page=page.page, block=index)
            # NFC ở đây chứ không tin bản thô: mọi mẫu chạy trên chữ đã gấp từng ký tự, và một chữ
            # NFD (text layer của vài PDF) làm *"BÀI 3"* thành *"BÀI 3"* -- không mẫu nào khớp.
            text = unicodedata.normalize("NFC", block.text)
            out.append(Unit(ref, block.kind, text, _normalised(page, block.box)))
    return out


def _normalised(
    page: RawPage, box: tuple[float, float, float, float] | None
) -> tuple[float, float, float, float] | None:
    """Hộp theo tỉ lệ trang, để OCR (điểm ảnh) và text layer (điểm PDF) nói cùng một ngôn ngữ.

    Args:
        page: Trang chứa hộp.
        box: Hộp gốc.

    Returns:
        Hộp trong 0..1, `None` khi thiếu hộp hoặc thiếu kích thước trang.
    """
    if box is None or not page.width or not page.height:
        return None
    left, top, right, bottom = box
    return (left / page.width, top / page.height, right / page.width, bottom / page.height)


def is_candidate(unit: Unit, source: RawSource) -> bool:
    """Đơn vị này có đáng hỏi *"có phải tiêu đề một mục không"*.

    Args:
        unit: Đơn vị.
        source: Đường đọc của tài liệu.

    Returns:
        True khi đáng hỏi.
    """
    text = unit.text.strip()
    if unit.kind in NOT_CONTENT or sum(char.isalpha() for char in text) < 2:
        return False
    if len(text) > _MAX_TITLE_CHARS:
        return False
    if source is RawSource.OCR:
        if unit.kind in _TITLE_KINDS:
            return True
        found = numbering(text)
        return (
            len(text) <= _MAX_TEXT_CANDIDATE_CHARS
            and found is not None
            and found.scheme in {"chapter", "lesson", "chapter_end", "number", "roman", "dotted"}
            and upper_ratio(text) >= _UPPER_RATIO
        )
    if source is RawSource.PLAIN and text.startswith("#"):
        return True
    # [CODE CHẾT 2026-10-11] text layer xếp số mục và tên mục thành hai dòng của một khối
    # one_line = "\n" not in text
    # return one_line and (numbering(text) is not None or upper_ratio(text) >= _UPPER_RATIO)
    #
    # Tối đa **hai** dòng: PyMuPDF trả *"1.1\nBối cảnh"* là một khối -- số mục một dòng, tên một
    # dòng. Bản đầu đòi một dòng và loại mất mọi mục của `report.pdf` (thử đầu-cuối, Task 4).
    lines = [line for line in text.split("\n") if line.strip()]
    joined = " ".join(line.strip() for line in lines)
    short = len(lines) <= _TEXT_LAYER_LINES
    return short and (numbering(joined) is not None or upper_ratio(joined) >= _UPPER_RATIO)


def candidates(pages: list[RawPage]) -> list[Candidate]:
    """Mọi ứng viên tiêu đề của tài liệu, theo thứ tự đọc.

    Args:
        pages: Các trang, trang 1 trước. Không rỗng.

    Returns:
        Các ứng viên.
    """
    if not pages:
        return []
    source = pages[0].source
    every = units(pages)
    chosen = [index for index, unit in enumerate(every) if is_candidate(unit, source)]
    seen_on = _pages_per_text(every[index] for index in chosen)
    heights = [every[index].box[3] - every[index].box[1] for index in chosen if every[index].box]
    usual = statistics.median(heights) if heights else None

    out = []
    for index in chosen:
        unit = every[index]
        text = " ".join(line.strip() for line in unit.text.split("\n") if line.strip())
        marks = len(text) - len(text.lstrip("#")) if source is RawSource.PLAIN else 0
        bare = text.lstrip("#").strip() if marks else text
        found = numbering(bare)
        title = found.rest if found and found.rest else bare
        if found and found.scheme == "chapter" and not found.rest:
            # *"Chương 1"* một khối, *"Đặt vấn đề"* khối kế (text layer của `report.pdf`): tên
            # chương là dòng ngắn đứng ngay sau, nếu có.
            following = _next_text(every, index)
            # Không lấy một dòng mang nhãn số (*"1.1 Bối cảnh"* là mục đầu, không phải tên chương).
            if (
                following
                and "\n" not in following
                and len(following) <= _CHAPTER_NAME_CHARS
                and numbering(following) is None
            ):
                title = following
        out.append(
            Candidate(
                unit=unit,
                numbering=found,
                title=title,
                bare=bare,
                source=source,
                position=_describe(unit.box, usual),
                repeated=_how_often(seen_on[fold(bare).strip()]),
                markdown_level=marks or None,
                next_text=_next_text(every, index),
                page_count=len(pages),
            )
        )
    return out


def _pages_per_text(chosen) -> Counter:
    """Mỗi chữ (đã gấp) xuất hiện trên bao nhiêu trang khác nhau.

    Args:
        chosen: Các đơn vị ứng viên.

    Returns:
        Bộ đếm chữ đã gấp → số trang.
    """
    pages: dict[str, set[int]] = {}
    for unit in chosen:
        key = fold(unit.text.lstrip("#").strip()).strip()
        pages.setdefault(key, set()).add(unit.ref.page)
    return Counter({key: len(found) for key, found in pages.items()})


def _how_often(count: int) -> str:
    """Kể số lần lặp bằng lời -- Jev không đọc số tốt.

    Args:
        count: Số trang chứa cùng chữ.

    Returns:
        Một trong ba cụm cố định.
    """
    if count <= 1:
        return "only here"
    return "on a few pages" if count <= 3 else "on many pages"


def _describe(box: tuple[float, float, float, float] | None, usual: float | None) -> str:
    """Kể vị trí và cỡ chữ của một khối bằng lời.

    Args:
        box: Hộp đã chuẩn hoá.
        usual: Chiều cao trung vị của các ứng viên trong tài liệu.

    Returns:
        Ví dụ *"top of page, centered, taller than most headings"*.
    """
    if box is None:
        return "no layout information"
    left, top, right, bottom = box
    if top < 0.12:
        vertical = "top of page"
    elif top < 0.4:
        vertical = "upper part of page"
    elif top < 0.7:
        vertical = "middle of page"
    else:
        vertical = "lower part of page"
    centre = (left + right) / 2
    horizontal = "centered" if abs(centre - 0.5) < 0.08 and right - left < 0.85 else "left-aligned"
    parts = [vertical, horizontal]
    if usual:
        ratio = (bottom - top) / usual
        if ratio > 1.3:
            parts.append("taller than most headings")
        elif ratio < 0.8:
            parts.append("smaller than most headings")
    return ", ".join(parts)


def _next_text(every: list[Unit], index: int) -> str:
    """Chữ của đơn vị có chữ kế tiếp, bỏ qua hình và dòng chạy đầu trang.

    Args:
        every: Mọi đơn vị.
        index: Vị trí của ứng viên.

    Returns:
        Chữ cắt ngắn, rỗng khi hết tài liệu.
    """
    for unit in every[index + 1 :]:
        if unit.kind not in NOT_CONTENT and unit.text.strip():
            return unit.text.strip()[:_NEXT_TEXT_CHARS]
    return ""


def banner_gates(pages: list[RawPage]) -> list[BlockRef]:
    """Các khối hình là **banner mở chương**: cổng của D9.

    Ba điều kiện, cả ba đo được trên Lớp 6 tập 1: khối hình, **ở đầu trang** và **rộng gần trọn
    trang** (banner), và chữ OCR trong nó có *CHƯƠNG* hoặc *PHẦN*. Bỏ điều kiện hình học thì
    trang 63 -- một hình minh hoạ có chữ *"Phần dấu, Phần số tự nhiên"* -- lọt cổng.

    Args:
        pages: Các trang.

    Returns:
        Một khối mỗi trang qua cổng, theo thứ tự trang.
    """
    gates = []
    for page in pages:
        if page.source is not RawSource.OCR:
            continue
        for index, block in enumerate(page.blocks):
            box = _normalised(page, block.box)
            if block.kind != "image" or box is None:
                continue
            wide, at_top = box[2] - box[0] >= 0.6, box[1] < 0.1
            # *CHƯƠNG* trên chữ đã gấp; *PHẦN* trên chữ **chưa** gấp -- gấp làm *PHẦN* và *PHÂN*
            # (phân số, thập phân) thành một. Bản đầu khớp `CHU?O?NG`, tức cả *CHUNG* (ước chung,
            # bội chung) -- chỉ điều kiện hình học đang chặn nó (review Task 3).
            opens = re.search(r"\bCHUONG\b", fold(block.text)) or re.search(
                r"\bPHẦN\b", block.text.upper()
            )
            if wide and at_top and opens:
                gates.append(BlockRef(page=page.page, block=index))
                break
    return gates


def printed_pages(pages: list[RawPage]) -> dict[int, int]:
    """Số trang **in trong sách** của từng trang tệp, đọc từ khối `number`.

    Args:
        pages: Các trang.

    Returns:
        Trang tệp → trang in, chỉ cho trang có một khối `number` đọc được thành số.
    """
    out = {}
    for page in pages:
        for block in page.blocks:
            digits = block.text.strip()
            # `isdecimal`, không `isdigit`: *"²"* là digit mà `int()` thì từ chối.
            if block.kind == "number" and digits.isdecimal() and len(digits) <= 4:
                out[page.page] = int(digits)
                break
    return out


def page_offset(printed: dict[int, int]) -> int | None:
    """Độ lệch phổ biến nhất giữa trang tệp và trang in.

    Args:
        printed: Kết quả của `printed_pages`.

    Returns:
        Trang tệp trừ trang in, `None` khi không có số trang in nào.
    """
    if not printed:
        return None
    return Counter(page - shown for page, shown in printed.items()).most_common(1)[0][0]
