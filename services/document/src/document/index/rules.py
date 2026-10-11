"""Đường luật: vai trò và cấp của một ứng viên, suy bằng code từ nhãn OCR, nhãn số và vị trí.

**Lưới, không phải đường chính** (D5 của plan 3c). Ba chỗ dùng nó:

- Jev trả lời với `confidence` dưới ngưỡng -- luật quyết thay;
- Jev không với tới được sau retry của SDK -- cả cây đi đường luật, `IndexHeader.method = "rules"`;
- bộ đo so luật với Jev trên cây vàng, để biết Jev đáng tiền tới đâu.

Luật được chỉnh trên **SGK Kết nối tri thức** (nhãn PP-DocLayout: tên bài là `doc_title`, mục là
*"1. HỆ THẬP PHÂN"* viết hoa). Sách có cấu trúc khác thì luật đoán kém -- và đó là lý do Jev đứng
trước nó, không phải sau.

Cấp **4** ở đây nghĩa là *sâu hơn cấp 3*: ứng viên là một tiêu đề nhỏ, nội dung của nó gộp vào nút
cha. Hằng `DEEPER` gọi tên nó.
"""

import re
from dataclasses import dataclass, field, replace

from contracts import MAX_LEVEL, DecidedBy, RawSource
from document.index.features import Candidate, fold, upper_ratio

# Các vai trò, **đúng thứ tự gửi Jev** (D1): lựa chọn an toàn đứng đầu, vì Jev 1.13 nghiêng về lựa
# chọn đầu tiên -- bỏ sót một mục chỉ gộp nội dung vào cha, còn một mục giả làm rách cây.
NOT_HEADING = "not_heading"
ACTIVITY_LABEL = "activity_label"
NUMBERED_EXERCISE = "numbered_exercise"
RUNNING_HEADER = "running_header"
BOOK_SECTION = "book_section"
ROLES = (NOT_HEADING, ACTIVITY_LABEL, NUMBERED_EXERCISE, RUNNING_HEADER, BOOK_SECTION)

# Cấp "sâu hơn cấp 3".
DEEPER = MAX_LEVEL + 1

# Nhãn hoạt động lặp lại trong mọi bài của SGK -- không phải mục. Chạy trên chữ đã gấp; `[IL1]` vì
# OCR đọc chữ *I* in hoa thành *l* (*"KHÁl NIỆM"*, *"BÀl TẬP"*).
_ACTIVITY = re.compile(
    r"^(V[IL1] DU|LUYEN TAP\s*\d|LUYEN TAP$|VAN DUNG|HD\s*\d|HD\)|G[IL1]A[IL1]$|CHU Y|NHAN XET|"
    r"THUC HANH|TRANH LUAN|THU THACH|EM CO B[IL1]ET|KHA[IL1] ?N[IL1]EM|THUAT NGU|K[IL1]EN THUC|"
    r"BA[IL1] TAP$|MUC ?T[IL1]EU|CHUAN B[IL1]|GO[IL1] Y|CAU HO[IL1]|HOAT DONG \d)"
)
# Phần đầu và cuối sách: không phải mục của nội dung. `[IL1]`: OCR đọc *"LỜI"* thành *"LỜl"*.
_FRONT_BACK = re.compile(r"LO[IL1] NOI DAU|HUONG DAN SU DUNG|MUC LUC|BANG TRA CU|BANG SO NGUYEN TO")
# Ruy băng *"BÀI TẬP"* cuối mỗi bài, thường kèm rác OCR ở hai đầu (*"ÀFÂE BÀl TẬP"*, *"BAI IAP"*).
_EXERCISES = re.compile(r"\bBA[IL1]?\s*[TI]AP")
# Watermark của bộ sách in chìm trên trang, mà PP-DocLayout đôi khi gán `paragraph_title`.
_WATERMARK = re.compile(r"KET NO|VOI CUOC|V01 C|NOTTRT")
# Một dòng mà quá nửa số từ chỉ có một ký tự là rác OCR (*"161@ U LÔ @ €5 ... U UU U J U"*).
_SHORT_TOKENS = 0.4
# Bài ôn trong SGK: cùng cấp với một bài, dù không mang số.
_REVIEW = re.compile(r"^LUYEN TAP CHUNG")


@dataclass(frozen=True)
class Decision:
    """Vai trò và cấp của một ứng viên, từ Jev hoặc từ luật.

    Attributes:
        role: Một trong `ROLES`.
        level: 1..3, `DEEPER`, hoặc `None` khi `role` không phải `BOOK_SECTION`.
        confidence: `confidence` thấp hơn trong hai câu của Jev; 1 với luật.
        decided_by: Ai quyết.
        role_probabilities: Phân phối Jev trả cho vai trò, rỗng với luật.
        level_probabilities: Phân phối Jev trả cho cấp, rỗng với luật.
    """

    role: str
    level: int | None
    confidence: float = 1.0
    decided_by: DecidedBy = DecidedBy.RULES
    role_probabilities: dict[str, float] = field(default_factory=dict)
    level_probabilities: dict[str, float] = field(default_factory=dict)

    @property
    def is_node(self) -> bool:
        """Ứng viên này có thành một nút cây không."""
        return self.role == BOOK_SECTION and self.level is not None and self.level <= MAX_LEVEL


def combine(asked: Decision, ruled: Decision, threshold: float) -> Decision:
    """Jev quyết khi đủ chắc; dưới ngưỡng thì luật quyết (D5).

    Phân phối và `confidence` của Jev **giữ lại** trên quyết định của luật: `BlockLabel` là thứ để
    đo, và một ca luật quyết thay là đúng ca cần nhìn xem Jev đã phân vân giữa những gì.

    Args:
        asked: Quyết định của Jev.
        ruled: Quyết định của luật cho cùng ứng viên.
        threshold: `jev_min_confidence`.

    Returns:
        Quyết định cuối.
    """
    if asked.confidence >= threshold:
        return asked
    return replace(
        ruled,
        confidence=asked.confidence,
        role_probabilities=asked.role_probabilities,
        level_probabilities=asked.level_probabilities,
    )


def _garbled(text: str) -> bool:
    """Dòng này là rác OCR chứ không phải chữ.

    Args:
        text: Chữ của ứng viên.

    Returns:
        True khi quá `_SHORT_TOKENS` số từ chỉ dài một ký tự (tính từ 4 từ trở lên).
    """
    tokens = text.split()
    if len(tokens) < 4:
        return False
    return sum(len(token) == 1 for token in tokens) / len(tokens) > _SHORT_TOKENS


def _section(level: int) -> Decision:
    return Decision(BOOK_SECTION, min(level, DEEPER))


def decide(candidate: Candidate) -> Decision:
    """Vai trò và cấp của một ứng viên, chỉ bằng luật.

    Args:
        candidate: Ứng viên.

    Returns:
        Quyết định, `decided_by = RULES`.
    """
    found = candidate.numbering
    title = fold(candidate.title).strip()
    whole = fold(candidate.unit.text).strip()

    if candidate.markdown_level:
        return _section(candidate.markdown_level)
    if _FRONT_BACK.search(whole) or _WATERMARK.search(whole):
        return Decision(RUNNING_HEADER, None)
    if _garbled(candidate.unit.text):
        return Decision(NOT_HEADING, None)
    if found and found.scheme == "chapter_end":
        return _section(2)
    if _EXERCISES.search(whole):
        return Decision(ACTIVITY_LABEL, None)
    if _REVIEW.match(whole):
        return _section(2)
    if found and found.scheme == "chapter":
        return _section(1)
    if found and found.scheme == "lesson":
        return _section(2)
    if _ACTIVITY.match(whole) or _ACTIVITY.match(title):
        return Decision(ACTIVITY_LABEL, None)
    if candidate.repeated == "on many pages":
        return Decision(RUNNING_HEADER, None)
    if found and found.scheme == "dotted":
        # *"1.1. Cho hai tập hợp"* trong SGK là bài tập; *"I.1"*, *"A.I.1"* là mục. Trong một báo
        # cáo có text layer, *"1.1 Bối cảnh"* lại là mục (`report.pdf`, thử đầu-cuối Task 4).
        if found.all_digits and candidate.source is RawSource.OCR:
            return Decision(NUMBERED_EXERCISE, None)
        return _section(found.depth)
    if found and found.scheme in {"roman", "letter"}:
        return _section(1)
    if found and found.scheme == "number":
        return _section(3) if upper_ratio(found.rest) >= 0.6 else Decision(NOT_HEADING, None)
    if found and found.scheme == "sub":
        return Decision(NOT_HEADING, None)

    upper = upper_ratio(candidate.title) >= 0.6
    if candidate.unit.kind == "doc_title" and upper:
        return _section(2)
    if candidate.unit.kind == "paragraph_title" and upper:
        # Tên bài nằm ở `paragraph_title` khi nó đứng dưới banner chương (Bài 13, Bài 21 của Lớp 6
        # tập 1) -- cao hơn hẳn các tiêu đề khác. Còn lại là tiêu đề nhỏ trong một mục.
        tall = "taller than most headings" in candidate.position
        return _section(2) if tall else _section(DEEPER)
    if candidate.unit.kind in {"doc_title", "paragraph_title"}:
        return _section(DEEPER)
    return Decision(NOT_HEADING, None)
