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
            if len(formula) > _MOST_FORMULA:
                return f"mục {index}: một công thức dài quá {_MOST_FORMULA} ký tự"
            if not _FORMULA.match(formula.strip()):
                # Nêu đúng công thức hỏng và cách sửa. Thử tay 17/10/2026 (plan `backlog-tier-1`,
                # pha 6): lời chung *"mỗi công thức là một biểu thức trong một cặp $"* không chỉ
                # chỗ nào sai, model viết lại cả dàn ý, sửa mục này thì hỏng mục khác, bảy lần
                # liền -- *"Nếu $a<b$ và $b<c$ thì $a<c$"*, *"$a=bq+r$, $0\le r<b$"*.
                return (
                    f'mục {index}: công thức "{formula.strip()[:80]}" không phải một biểu thức '
                    "trong đúng một cặp $. Mỗi phần tử của formulas là một cặp $ bao cả công "
                    "thức, không có chữ nào ngoài cặp $ (không *Nếu*, *và*, *với*, dấu phẩy): "
                    "viết điều kiện bằng ký hiệu trong cùng cặp $, như "
                    "$a<b,\\ b<c \\Rightarrow a<c$, hoặc tách thành hai phần tử"
                )
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
# Số node là định danh máy (luật 7 của bộ thử tay): *"(node 1, 3, 6, 17)"*, *"node 5"*. Thử tay
# 17/10/2026 (`kriky-writes-every-word`): từ khi Kriky tự viết lời dàn ý, model chép `source_nodes`
# vào lời ở cả ba lượt dàn ý theo sách -- trước ADR-30, dòng `Theo:` BE dựng in nhãn bài, không số.
# Cả *"node số 5"*, *"nodes 14, 15"* và *"source_nodes: [5]"* -- `_` liền trước làm `\b` không khớp
# (review cuối plan).
_NODE_NUMBER = re.compile(r"(?<![a-z])nodes?\s*(?:số\s*)?[:#=]?\s*\[?\s*\d", re.IGNORECASE)


# Chỗ nối giữa các vế của một công thức gộp: dấu phẩy, chấm phẩy, khoảng trắng LaTeX (`\ `, `\,`,
# `\:`, `\;`), `\quad`, và chữ trong `\text{…}` (*"với"*, *"và"*). Mục buộc phải viết
# `$a = bq + r,\ 0 \le r < b$` trong một cặp `$` (`validate`), còn lời thì tự nhiên viết
# *"$a = bq + r$ với $0 \le r < b$"*. Dấu phẩy, chấm phẩy **giữa hai chữ số** thì không tách:
# `2,5` là số thập phân, `\{1;2;3\}` là một tập hợp (review của bản sửa này).
_JOINT = re.compile(r"\\q?quad|\\text\{[^{}]*\}|\\[ ,:;]|(?<!\d)[,;]|[,;](?!\d)")


def _flat(formula: str) -> str:
    """Một công thức bỏ những gì chỉ là cách viết, để so mà không vấp."""
    plain = formula.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    return _NOISE.sub("", plain)


def _shown(formula: str, flat: str) -> bool:
    """Lời (đã `_flat`) có nêu công thức này không: nguyên vẹn, hay đủ mọi vế khi lời tách nó ra.

    Thử tay 17/10/2026 (quay GIF, sau plan `backlog-tier-1`): luật *một cặp `$`* của pha 6 làm mục
    ghi điều kiện chung một cặp với biểu thức, lời thì tách hai cặp có chữ ở giữa, nên phép so cả
    chuỗi không khớp và dàn ý bị trả về ba lần. Đủ **mọi** vế mới tính -- nêu một nửa là thiếu.
    Mọi vế phải dài từ ba ký tự: một vế như `2` hay `r` khớp với bất kỳ chữ nào của lời, kể cả
    *"Câu 1–3"*, nên công thức có vế ngắn chỉ được so nguyên vẹn.
    """
    if _flat(formula) in flat:
        return True
    parts = [one for one in (_flat(part) for part in _JOINT.split(formula)) if one]
    return (
        len(parts) > 1 and all(len(one) >= 3 for one in parts) and all(one in flat for one in parts)
    )


def check_message(text: str, items: Sequence[OutlineItem], *, first: int = 1) -> str | None:
    """Lời Kriky trình bày dàn ý có khớp các mục không -- **đối chiếu nhẹ** (ADR-30). Hàm thuần.

    Nhẹ có chủ ý (ADR-30): lời được diễn đạt lại, nên chỉ bắt những lệch làm giáo viên duyệt nhầm
    một đề khác -- sai đánh số, mất hẳn công thức, lộ định danh máy. Năm tiêu chí:

    - lời nhắc tới **Câu m** -- câu đầu của mỗi mục -- nên giáo viên đọc được câu nào hỏi gì;
    - lời không nhắc câu nào **sau** câu cuối của dàn ý. Câu trước câu đầu thì được: soạn thêm hay
      thay câu nói về câu đã có của đề (*"đề đang có câu 1–5"*);
    - mỗi mục có công thức thì lời có ít nhất **một** công thức của nó;
    - lời có ít nhất một câu hỏi, để giáo viên biết mình đang được hỏi ý;
    - lời không in số node: bài nguồn gọi bằng tên của nó.

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
        if item.formulas and not any(_shown(one, flat) for one in item.formulas):
            return f"lời chưa có công thức nào của mục {index}; nêu ít nhất một, trong cặp $"
    if "?" not in text:
        return "lời chưa hỏi giáo viên có đồng ý dàn ý không"
    if _NODE_NUMBER.search(text):
        return "lời in số node: giáo viên không đọc được số ấy, gọi bài nguồn bằng tên bài"
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
