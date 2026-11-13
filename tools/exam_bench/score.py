"""Phép chấm thuần của `exam_bench`: đa số phiếu, độ đồng thuận, độ phủ, lỗi viết câu bằng code.

Không gọi model, không đọc đĩa -- `tools/tests/test_exam_bench.py` canh từng hàm. Thước đo phải
đúng trước khi con số của nó được tin.
"""

import re
import statistics
import unicodedata
from collections.abc import Iterable, Sequence


def majority(votes: Iterable[bool | None]) -> bool | None:
    """Kết luận của panel cho một tiêu chí có/không. Hàm thuần.

    Phiếu trống (`None`: rater từ chối, hỏng parse, hay tiêu chí không áp dụng) không tính. Hoà --
    chỉ xảy ra khi có phiếu trống -- là không kết luận.

    Args:
        votes: Phiếu của từng rater.

    Returns:
        `True`/`False` theo đa số phiếu có mặt, hay `None` khi không phiếu nào hoặc hoà.
    """
    cast = [vote for vote in votes if vote is not None]
    yes = sum(1 for vote in cast if vote)
    no = len(cast) - yes
    if yes == no:
        return None
    return yes > no


def fleiss_kappa(rows: Sequence[Sequence[bool | None]]) -> float | None:
    """Fleiss' kappa của một tiêu chí có/không trên nhiều mục, mỗi mục cùng số rater. Hàm thuần.

    Chỉ các mục **đủ** phiếu được tính (một phiếu trống làm số rater của mục ấy lệch). Mọi phiếu
    cùng một loại thì đồng thuận kỳ vọng bằng 1 và kappa không xác định: trả `None`, không trả 1 --
    một tiêu chí ai cũng nói *có* với mọi câu chưa cho biết rater có hiểu nó giống nhau không.

    Args:
        rows: Mỗi mục một dãy phiếu.

    Returns:
        Kappa, hay `None` khi không đủ dữ liệu.
    """
    full = [list(row) for row in rows if row and all(vote is not None for vote in row)]
    if not full:
        return None
    raters = len(full[0])
    full = [row for row in full if len(row) == raters]
    if raters < 2 or not full:
        return None
    agree = []
    yes_total = 0
    for row in full:
        yes = sum(1 for vote in row if vote)
        no = raters - yes
        yes_total += yes
        agree.append((yes * (yes - 1) + no * (no - 1)) / (raters * (raters - 1)))
    p_yes = yes_total / (len(full) * raters)
    expected = p_yes**2 + (1 - p_yes) ** 2
    if expected >= 1:
        return None
    return (statistics.fmean(agree) - expected) / (1 - expected)


def cohen_kappa(left: Sequence[bool | None], right: Sequence[bool | None]) -> float | None:
    """Cohen's kappa giữa hai rater trên cùng các mục; cặp có phiếu trống bị bỏ. Hàm thuần.

    Args:
        left: Phiếu của rater thứ nhất.
        right: Phiếu của rater thứ hai, cùng thứ tự mục.

    Returns:
        Kappa, hay `None` khi không xác định (không cặp nào, hay cả hai luôn cùng một phiếu).
    """
    pairs = [(a, b) for a, b in zip(left, right, strict=True) if a is not None and b is not None]
    if not pairs:
        return None
    observed = sum(1 for a, b in pairs if a == b) / len(pairs)
    left_yes = sum(1 for a, _ in pairs if a) / len(pairs)
    right_yes = sum(1 for _, b in pairs if b) / len(pairs)
    expected = left_yes * right_yes + (1 - left_yes) * (1 - right_yes)
    if expected >= 1:
        return None
    return (observed - expected) / (1 - expected)


def coverage(
    mapped: Sequence[Iterable[int]], gold_count: int, question_count: int
) -> tuple[float, int]:
    """Độ phủ của một dàn ý trên các dòng vàng, và số mục lạc phạm vi. Hàm thuần.

    Mẫu số là `min(số câu, số dòng vàng)`: một đề 3 câu cho bài có 4 dòng yêu cầu không thể phủ hết,
    và không bị phạt vì thế. Chỉ số dòng vàng hợp lệ (0 ≤ i < `gold_count`) được đếm.

    Args:
        mapped: Mỗi mục dàn ý một tập chỉ số dòng vàng nó phủ (đã qua đa số phiếu).
        gold_count: Số dòng vàng của bài.
        question_count: Số câu giáo viên xin.

    Returns:
        `(độ phủ trong [0, 1], số mục không phủ dòng nào)`.
    """
    covered: set[int] = set()
    off = 0
    for lines in mapped:
        kept = {line for line in lines if 0 <= line < gold_count}
        if not kept:
            off += 1
        covered |= kept
    room = min(question_count, gold_count)
    if room <= 0:
        return 0.0, off
    return min(1.0, len(covered) / room), off


def gwet_ac1(rows: Sequence[Sequence[bool | None]]) -> float | None:
    """Gwet's AC1 của một tiêu chí có/không, trên các mục đủ phiếu. Hàm thuần.

    Fleiss' kappa sụp khi gần như mọi phiếu cùng một phía (nghịch lý tỉ lệ): 95% *có* với rater gần
    như nhất trí vẫn ra kappa thấp hay âm. AC1 tính đồng thuận ngẫu nhiên là `2π(1-π)`, không sụp
    như vậy -- đọc cùng kappa để biết thấp là vì rater lệch nhau hay vì tiêu chí quá lệch một phía
    (review pha 3, plan `exam-quality-bench`).

    Args:
        rows: Mỗi mục một dãy phiếu.

    Returns:
        AC1, hay `None` khi không đủ dữ liệu.
    """
    agree = agreement(rows)
    full = [row for row in rows if row and all(vote is not None for vote in row)]
    if agree is None or not full:
        return None
    raters = len(full[0])
    full = [row for row in full if len(row) == raters]
    p_yes = sum(sum(1 for vote in row if vote) for row in full) / (len(full) * raters)
    expected = 2 * p_yes * (1 - p_yes)
    if expected >= 1:
        return None
    return (agree - expected) / (1 - expected)


def agreement(rows: Sequence[Sequence[bool | None]]) -> float | None:
    """Tỉ lệ cặp rater đồng ý, trung bình trên các mục đủ phiếu (đồng thuận thô). Hàm thuần."""
    full = [list(row) for row in rows if row and all(vote is not None for vote in row)]
    if not full:
        return None
    raters = len(full[0])
    full = [row for row in full if len(row) == raters]
    if raters < 2 or not full:
        return None
    shares = []
    for row in full:
        yes = sum(1 for vote in row if vote)
        no = raters - yes
        shares.append((yes * (yes - 1) + no * (no - 1)) / (raters * (raters - 1)))
    return statistics.fmean(shares)


def full_rows(rows: Sequence[Sequence[bool | None]]) -> int:
    """Số mục đủ phiếu -- `n` thật của kappa, AC1 và đồng thuận thô. Hàm thuần."""
    return sum(1 for row in rows if row and all(vote is not None for vote in row))


# Những lỗi viết câu đọc được bằng mắt máy (rubric 19 lỗi của Haladyna, bản Moore et al. 2023): luật
# code bắt chúng chắc hơn một judge LLM, nên không giao cho rater. Chỉ bắt cụm **nói về các phương
# án** -- *"Tất cả học sinh lớp 10A đều…"* là một phương án nhiễu kinh điển của bài phủ định ∀,
# không phải lỗi (review pha 3).
_ALL_OF_ABOVE = re.compile(
    r"\b(?:tất cả|cả)\s+(?:các\s+)?(?:phương án|đáp án|câu)\s+(?:trên|đều|kia)"
    r"|\bcả\s+[A-D](?:\s*,\s*[A-D])*\s*(?:và|,)\s*[A-D]\b"
    r"|\bkhông có\s+(?:phương án|đáp án|câu)\s+nào\b"
    r"|\b(?:các|mọi)\s+(?:phương án|đáp án)\s+(?:trên|kia)\b",
    re.IGNORECASE,
)

# Chữ trích trong ngoặc kép -- *"Câu 'Bạn có học bài không?' có phải mệnh đề?"* -- không phải câu
# hỏi thứ hai của đề.
_QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”|'[^']*'|‘[^’]*’")


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    # Ngoặc nhọn **thoát** (`\{6\}`) là chữ toán -- tập $\{6\}$ khác số $6$, một phương án nhiễu
    # chính đáng của bài tập hợp (review pha 1, plan `agent-split-bench`: cả ba lần bắt ở `run-130`
    # là bắt nhầm như vậy). Chỉ ngoặc nhóm của LaTeX bị bỏ.
    text = text.replace("\\{", "⦃").replace("\\}", "⦄")
    text = re.sub(r"[\s$\\{}]+", "", text)
    return text


def code_flaws(question: dict) -> list[str]:
    """Các lỗi viết câu luật code bắt được trên một câu đã dump (`GeneratedQuestion`). Hàm thuần.

    - `phuong-an-trung`: hai phương án cùng chữ sau khi bỏ khoảng trắng và dấu LaTeX.
    - `tat-ca-deu-dung`: phương án nói về các phương án khác -- *"tất cả các phương án trên đều
      đúng"*, *"cả A và B"*, *"không có đáp án nào"*.
    - `dap-an-dai-bat-thuong`: phương án đúng dài nhất và dài hơn 1,5 lần trung vị các phương án sai
      -- gợi ý đáp án cho học sinh đoán.
    - `hai-cau-hoi`: đề bài có từ hai dấu `?` ngoài chữ trích trong ngoặc kép.
    - `de-chep-phuong-an`: đề bài chép lại nguyên văn từ hai phương án trở lên.

    Args:
        question: Câu hỏi đã dump: `stem`, `options` (`text`, `is_correct`).

    Returns:
        Mã các lỗi, theo thứ tự trên; rỗng khi không có.
    """
    flaws: list[str] = []
    options = list(question.get("options") or [])
    texts = [str(one.get("text") or "") for one in options]
    plain = [_plain(text) for text in texts]
    stem = str(question.get("stem") or "")
    if len(set(plain)) < len(plain):
        flaws.append("phuong-an-trung")
    if any(_ALL_OF_ABOVE.search(unicodedata.normalize("NFC", text)) for text in texts):
        flaws.append("tat-ca-deu-dung")
    right = [len(plain[at]) for at, one in enumerate(options) if one.get("is_correct")]
    wrong = [len(plain[at]) for at, one in enumerate(options) if not one.get("is_correct")]
    if (
        len(right) == 1
        and wrong
        and right[0] > max(wrong)
        and right[0] > 1.5 * statistics.median(wrong)
        and right[0] >= 12
    ):
        flaws.append("dap-an-dai-bat-thuong")
    if _QUOTED.sub("", unicodedata.normalize("NFC", stem)).count("?") >= 2:
        flaws.append("hai-cau-hoi")
    plain_stem = _plain(stem)
    if sum(1 for body in plain if len(body) >= 6 and body in plain_stem) >= 2:
        flaws.append("de-chep-phuong-an")
    return flaws


def share(values: Iterable[bool | None]) -> tuple[int, int]:
    """Số `True` và số phần tử có kết luận (bỏ `None`). Hàm thuần."""
    cast = [value for value in values if value is not None]
    return sum(1 for value in cast if value), len(cast)
