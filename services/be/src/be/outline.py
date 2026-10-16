"""Dàn ý đề (ADR-29, `draft-outline`): BE kiểm các mục Kriky viết, và đối chiếu chúng với lời Kriky
trình bày dàn ý. Hàm thuần: không database, không mạng.

Từ ADR-30 (`kriky-writes-every-word`), chữ trên màn hình **do Kriky viết** (Markdown), không do BE
dựng; các mục có cấu trúc vẫn là thứ duy nhất đi vào job. BE không chứng minh được lời và mục giống
nhau từng chữ, nên nó chỉ đối chiếu **nhẹ** (`check_message`): số câu, công thức, một câu hỏi xin
đồng ý.
"""

import re
import unicodedata
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
# Một công thức nằm trong cặp `$` (`MathText` dựng phần ở giữa), và không gì khác.
_FORMULA = re.compile(r"^\$[^$]+\$$")


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


# *"Câu 3"*, *"câu 1–2"*, *"Câu hỏi 1"*, *"câu số 2"*, *"câu thứ 2"*: số câu lời Kriky nhắc tới.
# Không bắt *"5 câu"* -- đó là một con số đếm, không phải một câu.
_QUESTION_NUMBER = re.compile(
    r"\bcâu\s+(?:hỏi\s+)?(?:số\s+|thứ\s+)?(\d+)(?:\s*[–—-]\s*(\d+))?", re.IGNORECASE
)
# Những thứ hai cách viết cùng một công thức hay khác nhau (review pha 4): ngoặc nhóm, cỡ ngoặc,
# kiểu dựng, dấu nhân. `a^2` và `a^{2}`, `\dfrac` và `\frac`, `(n-1)d` và `(n-1) \cdot d` là một.
_NOISE = re.compile(r"\\(?:left|right|displaystyle|cdot|times)|[{}$\s]")


def _flat(formula: str) -> str:
    """Một công thức bỏ những gì chỉ là cách viết, để so mà không vấp."""
    plain = formula.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    return _NOISE.sub("", plain)


def check_message(text: str, items: Sequence[OutlineItem], *, first: int = 1) -> str | None:
    """Lời Kriky trình bày dàn ý có khớp các mục không -- **đối chiếu nhẹ** (ADR-30). Hàm thuần.

    Nhẹ có chủ ý (ADR-30): lời được diễn đạt lại, nên chỉ bắt những lệch làm giáo viên duyệt nhầm
    một đề khác -- sai đánh số, mất hẳn công thức. Bốn tiêu chí:

    - lời nhắc tới **Câu m** -- câu đầu của mỗi mục -- nên giáo viên đọc được câu nào hỏi gì;
    - lời không nhắc câu nào **sau** câu cuối của dàn ý. Câu trước câu đầu thì được: soạn thêm hay
      thay câu nói về câu đã có của đề (*"đề đang có câu 1–5"*);
    - mỗi mục có công thức thì lời có ít nhất **một** công thức của nó;
    - lời có ít nhất một câu hỏi, để giáo viên biết mình đang được hỏi ý.

    Kiến thức, cách làm và tên bài không bị so: lời được diễn đạt lại.

    Args:
        text: Lời Kriky, Markdown.
        items: Các mục, đã qua `validate`.
        first: Số của câu đầu tiên dàn ý phủ.

    Returns:
        Lý do model đọc rồi viết lại được, hoặc `None` khi khớp.
    """
    if not text.strip():
        return "lời dàn ý trống: viết lời trình bày dàn ý cho giáo viên"
    text = unicodedata.normalize("NFC", text)
    mentioned: set[int] = set()
    for found in _QUESTION_NUMBER.finditer(text):
        low = int(found.group(1))
        high = int(found.group(2) or low)
        mentioned.update(range(low, high + 1) if low <= high <= low + 50 else (low,))
    last = first + sum(item.questions for item in items) - 1
    number = first
    for index, item in enumerate(items, start=1):
        if number not in mentioned:
            return (
                f"lời chưa nhắc tới Câu {number}, câu đầu của mục {index}; dàn ý này bắt đầu từ "
                f"Câu {first}"
            )
        number += item.questions
    stray = sorted(one for one in mentioned if one > last)
    if stray:
        span = f"Câu {first}" if first == last else f"Câu {first}–{last}"
        return f"lời nhắc Câu {stray[0]}, ngoài dàn ý ({span})"
    flat = _flat(text)
    for index, item in enumerate(items, start=1):
        if item.formulas and not any(_flat(one) in flat for one in item.formulas):
            return f"lời chưa có công thức nào của mục {index}; nêu ít nhất một, trong cặp $"
    if "?" not in text:
        return "lời chưa hỏi giáo viên có đồng ý dàn ý không"
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
