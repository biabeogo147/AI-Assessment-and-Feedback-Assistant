"""Thước đo: so một trang engine đọc được với trang nhãn vàng.

Mọi phép so ở đây **thuần** -- không đĩa, không mạng, không model -- nên lưới của chúng chạy
được ở mọi máy và chạy trong `.\\dev.ps1 check`, trong khi chính bộ đo thì không.

Ba quyết định đáng nói ra, vì chúng đổi con số chứ không chỉ đổi code:

1. **Chuẩn hoá NFC trước mọi phép so.** `ế` dựng sẵn và `ế` tổ hợp hiện lên giống hệt nhau và
   khác từng byte. Không chuẩn hoá thì một engine đọc đúng hoàn toàn vẫn ăn một CER khác 0.
2. **Lỗi dấu đo bằng *hiệu* của hai CER**, không bằng một phép dóng từng ký tự. Lý do ở
   `diacritic_loss`. Nó là thứ phân biệt một engine *nhìn* kém với một engine *thủng từ điển* --
   đúng chỗ PaddleOCR hỏng, và một CER duy nhất không nói ra được.
3. **LaTeX được chuẩn hoá trước khi so.** `a+b` và `a + b` là cùng một công thức; phạt engine vì
   một dấu cách là đo cách viết chứ không đo chất lượng đọc.

Không dùng thư viện khoảng cách nào: env này không có `rapidfuzz`, `Levenshtein` hay
`editdistance`, và kéo một dependency về cho một thư mục công cụ không có `pyproject.toml` là
trả một cái giá thật cho một vòng lặp ba dòng.
"""

import re
import unicodedata
from collections import Counter

# `đ` không mang dấu phụ tổ hợp -- NFD không tách nó ra -- nên nó phải được gỡ bằng tay. Thiếu
# dòng này thì một engine đọc `d` thay cho `đ` bị tính là lỗi chữ chứ không phải lỗi dấu, và
# phép đo sẽ chỉ sai ở đúng những trang nói về *đường thẳng* hay *điểm*.
_D_WITH_STROKE = str.maketrans({"đ": "d", "Đ": "D"})

# Lệnh LaTeX chỉ vẽ khoảng trắng. Chúng không đổi nghĩa công thức, và không engine nào nhất quán
# về chúng -- PP-FormulaNet rải `\;` trong `27\;000` ở chỗ nhãn vàng viết `27 000`.
_LATEX_SPACING = re.compile(r"\\[,;:!]|\\quad|\\qquad|\\ |~")

# `\left(` và `\right)` chỉ nói về chiều cao dấu ngoặc.
#
# `(?![a-zA-Z])` **không bỏ được**. Thiếu nó thì regex cắt `\left` ra khỏi `\leftarrow` và
# `\right` ra khỏi `\rightarrow`, cả hai còn lại `arrow` -- và lúc ấy bộ đo chấm **điểm tối đa**
# cho một engine đọc mũi tên ngược chiều. Đo trên chính nhãn vàng (`L6T1_p026`, khối 27) ngày
# 10/10/2026: `latex_matches` trả `True` cho một bản đọc sai hoàn toàn.
_LATEX_SIZING = re.compile(r"\\(?:left|right)(?![a-zA-Z])")

# Khác nhau về cách gõ, không về nghĩa. Ba người đánh nhãn gõ ba kiểu -- đếm được trên 58 khối
# công thức: `^{3}` 21 lần và `^3` 33 lần, `\text` 20 lần và `\mathrm` 8 lần, `\le` 1 và `\leq` 0,
# `\dots` 1 và `\ldots` 2. Gom ở đây chứ không sửa trong nhãn, vì **engine cũng gõ lung tung** --
# một bảng gom ở bộ đo chữa cả hai phía, còn sửa nhãn chỉ chữa một.
_LATEX_SYNONYMS = (
    (re.compile(r"\\mathrm(?![a-zA-Z])"), r"\\text"),
    (re.compile(r"\\dots(?![a-zA-Z])"), r"\\ldots"),
    (re.compile(r"\\le(?![a-zA-Z])"), r"\\leq"),
    (re.compile(r"\\ge(?![a-zA-Z])"), r"\\geq"),
)

# `^3` và `^{3}` là một. Bọc mọi mũ hay chỉ số một ký tự vào ngoặc để hai cách gõ gặp nhau.
_LATEX_SCRIPT = re.compile(r"([_^])([A-Za-z0-9])")

_WHITESPACE = re.compile(r"\s+")

# Dấu câu dính ở hai đầu một từ. `\w` của Python khớp cả chữ có dấu tiếng Việt, nên `"Số,"` còn
# lại `"Số"` chứ không mất chữ `ố`.
_WORD_EDGE = re.compile(r"^[^\w]+|[^\w]+$")

# Phải giống nhau **hơn** mức này thì mới là cùng một khối. Mẫu số là **độ dài khối dài hơn**, không
# phải độ dài nhãn: với mẫu số cũ, một khối dài 1--2 ký tự không chịu nổi một phép sửa nào, nên
# **cả 48 khối `number`** của bộ nhãn -- chính thứ dùng để nối trang PDF với trang in -- rơi khỏi
# mọi phép ghép mà không ô nào trong bảng điểm nói ra. Review 10/10/2026 bắt được.
_SAME_BLOCK_SIMILARITY = 0.5

# Khối ngắn hơn ngần này ký tự được ghép bằng một luật riêng: khoảng cách sửa tuyệt đối, không
# phải tỉ lệ. `'7'` và `'7 '` là cùng một số trang; `'7'` và `'9'` thì không.
_SHORT_BLOCK = 4
_SHORT_BLOCK_EDITS = 1


def nfc(text: str) -> str:
    """Chuẩn hoá Unicode về NFC.

    Args:
        text: Chuỗi bất kỳ.

    Returns:
        Chuỗi đã chuẩn hoá.
    """
    return unicodedata.normalize("NFC", text)


def without_marks(text: str) -> str:
    """Gỡ mọi dấu phụ, giữ nguyên chữ cái.

    `Kết nối` thành `Ket noi`. Dùng để tách *lỗi nhìn* khỏi *lỗi dấu*.

    Args:
        text: Chuỗi bất kỳ.

    Returns:
        Chuỗi không còn dấu phụ nào.
    """
    stripped = unicodedata.normalize("NFD", text.translate(_D_WITH_STROKE))
    return "".join(one for one in stripped if unicodedata.category(one) != "Mn")


def levenshtein(left: str, right: str) -> int:
    """Khoảng cách sửa giữa hai chuỗi.

    Hai hàng thay vì cả bảng: một trang sách khoảng 2 000 ký tự, nên cả bảng là 4 triệu ô mà ta
    chỉ cần con số cuối.

    Args:
        left: Chuỗi thứ nhất.
        right: Chuỗi thứ hai.

    Returns:
        Số phép chèn, xoá, thay tối thiểu để biến chuỗi này thành chuỗi kia.
    """
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for row, one in enumerate(left, start=1):
        current = [row]
        for column, other in enumerate(right, start=1):
            current.append(
                min(
                    previous[column] + 1,
                    current[column - 1] + 1,
                    previous[column - 1] + (one != other),
                )
            )
        previous = current
    return previous[-1]


def flatten(text: str) -> str:
    """Gom mọi chuỗi khoảng trắng thành một dấu cách, và cắt hai đầu.

    Cùng lập luận với `normalise_latex`: phạt một engine vì nó gõ một dấu cách thay vì ba là đo
    **cách trình bày**, không đo chất lượng đọc. Ở đây nó còn nặng hơn thế -- nhãn vàng do ba
    người gõ, và họ dùng số khoảng trắng khác nhau để căn cột. Đo ngày 10/10/2026, CER **sàn**
    mà một engine đọc đúng tuyệt đối vẫn phải trả chỉ vì khoảng trắng kép trong nhãn: lát A
    0,34%, lát B 0,42%, lát C 0,013%. Theo khối thì tệ hơn hẳn -- `L6T1_p013` khối 5 là
    `'a) 400;          b) 40;'`, sàn **47%**. Không gom thì mọi phép so giữa ba lát là so cách gõ
    của ba người.

    Args:
        text: Chuỗi bất kỳ.

    Returns:
        Chuỗi đã gom khoảng trắng.
    """
    return _WHITESPACE.sub(" ", text).strip()


def error_rate(truth: str, read: str) -> float:
    """Khoảng cách sửa chia cho độ dài nhãn, sau khi gom khoảng trắng cả hai phía.

    Có thể **vượt 1,0**, và đó là chủ ý: một engine nhả ra gấp ba lượng chữ cần đọc thì tệ hơn
    một engine im lặng, và một con số bị chặn ở 1,0 nói rằng hai ca ấy như nhau.

    Args:
        truth: Chuỗi nhãn vàng.
        read: Chuỗi engine đọc được.

    Returns:
        Tỉ lệ lỗi. `0,0` khi nhãn rỗng và engine cũng im; `1,0` khi nhãn rỗng mà engine bịa chữ.
    """
    truth, read = flatten(nfc(truth)), flatten(nfc(read))
    if not truth:
        return 0.0 if not read else 1.0
    return levenshtein(truth, read) / len(truth)


def cer(truth: str, read: str) -> float:
    """Tỉ lệ lỗi ký tự.

    Args:
        truth: Chuỗi nhãn vàng.
        read: Chuỗi engine đọc được.

    Returns:
        Tỉ lệ lỗi tính trên từng ký tự.
    """
    return error_rate(truth, read)


def missing_words(truth: str, read: str) -> float:
    """Tỉ lệ từ của nhãn vàng **không** có mặt đúng nguyên dạng trong bản đọc, bỏ qua thứ tự.

    Đây là thước gần nhất với câu hỏi sản phẩm thật đặt ra: chữ đọc ra đi vào LLM làm ngữ cảnh,
    và với LLM thì *một từ có ở đó hay không* quan trọng hơn *nó đứng đúng chỗ không*. CER và WER
    đều trừng phạt thứ tự -- hai khung đặt cạnh nhau đọc đan xen là CER vọt lên dù không một chữ
    nào sai -- nên chúng không trả lời được câu này.

    So theo **túi từ có đếm**: từ xuất hiện ba lần trong nhãn mà bản đọc chỉ có hai thì thiếu một.
    Không phân biệt hoa thường, và gỡ dấu câu ở hai đầu mỗi từ: `"nhau."` và `"nhau"` là một từ.
    Dấu tiếng Việt thì **giữ**: `"so"` không phải `"số"`.

    Args:
        truth: Chuỗi nhãn vàng.
        read: Chuỗi engine đọc được.

    Returns:
        Từ 0,0 (đủ mọi từ) tới 1,0 (không còn từ nào). Nhãn rỗng cho 0,0.
    """
    expected, found = _bag(truth), _bag(read)
    total = sum(expected.values())
    if not total:
        return 0.0
    return 1.0 - sum((expected & found).values()) / total


def _bag(text: str) -> Counter[str]:
    """Túi từ của một chuỗi, theo luật của `missing_words`.

    Args:
        text: Chuỗi bất kỳ.

    Returns:
        Số lần xuất hiện của từng từ.
    """
    out: Counter[str] = Counter()
    for raw in nfc(text).lower().split():
        word = _WORD_EDGE.sub("", raw)
        if word:
            out[word] += 1
    return out


def wer(truth: str, read: str) -> float:
    """Tỉ lệ lỗi từ, cắt từ bằng khoảng trắng.

    Đi cạnh CER chứ không thay nó: một engine đánh rơi đúng một ký tự giữa mỗi từ có CER rất
    thấp và WER gần 1,0, và chỉ con số thứ hai nói rằng không câu nào còn đọc được.

    Args:
        truth: Chuỗi nhãn vàng.
        read: Chuỗi engine đọc được.

    Returns:
        Tỉ lệ lỗi tính trên từng từ.
    """
    left, right = nfc(truth).split(), nfc(read).split()
    if not left:
        return 0.0 if not right else 1.0
    # Dóng theo **từ**: mỗi từ thành một ký tự riêng để dùng lại đúng một phép Levenshtein.
    alphabet: dict[str, str] = {}
    for word in left + right:
        alphabet.setdefault(word, chr(len(alphabet) + 0x100))
    return levenshtein(
        "".join(alphabet[word] for word in left), "".join(alphabet[word] for word in right)
    ) / len(left)


def align(truth: str, read: str) -> list[tuple[str | None, str | None]]:
    """Dóng hai chuỗi theo phép sửa rẻ nhất, và trả về từng cặp ký tự.

    `None` ở một phía nghĩa là chèn hoặc xoá. Bảng hướng đi dùng `bytearray`, một byte mỗi ô: một
    trang sách khoảng 2 000 ký tự nên bảng là 4 MB, trong khi một list lồng list cùng kích thước
    là hơn 150 MB. Đó là khác biệt giữa chạy được và không.

    Args:
        truth: Chuỗi nhãn vàng.
        read: Chuỗi engine đọc được.

    Returns:
        Các cặp `(ký tự nhãn, ký tự engine)` theo thứ tự, mỗi phía có thể là `None`.
    """
    truth, read = nfc(truth), nfc(read)
    rows, columns = len(truth) + 1, len(read) + 1
    # 0 = thay (hoặc khớp), 1 = xoá khỏi nhãn, 2 = chèn vào nhãn.
    how = bytearray(rows * columns)
    previous = list(range(columns))
    for column in range(1, columns):
        how[column] = 2
    for row in range(1, rows):
        current = [row]
        how[row * columns] = 1
        for column in range(1, columns):
            substitute = previous[column - 1] + (truth[row - 1] != read[column - 1])
            delete = previous[column] + 1
            insert = current[column - 1] + 1
            best = min(substitute, delete, insert)
            current.append(best)
            how[row * columns + column] = 0 if best == substitute else (1 if best == delete else 2)
        previous = current

    pairs: list[tuple[str | None, str | None]] = []
    row, column = rows - 1, columns - 1
    while row or column:
        step = how[row * columns + column]
        if step == 0:
            row, column = row - 1, column - 1
            pairs.append((truth[row], read[column]))
        elif step == 1:
            row -= 1
            pairs.append((truth[row], None))
        else:
            column -= 1
            pairs.append((None, read[column]))
    pairs.reverse()
    return pairs


def has_mark(one: str) -> bool:
    """Ký tự này có mang dấu phụ không.

    Args:
        one: Một ký tự.

    Returns:
        True khi gỡ dấu làm nó đổi, tức nó mang ít nhất một dấu -- kể cả `đ`.
    """
    return without_marks(one) != one


def diacritic_error_rate(truth: str, read: str) -> float:
    """Tỉ lệ ký tự **có dấu** của nhãn bị đọc sai hoặc đánh rơi.

    Vì sao cần một thước riêng cạnh CER: một trang sách tiếng Việt có khoảng một phần tư ký tự
    mang dấu, nên một engine đánh rơi **toàn bộ** dấu vẫn chỉ ăn CER chừng 0,25 -- một con số
    trông như *"hơi kém"* trong khi chữ nó trả về không đọc được. Thước này chỉ cho ngay rằng
    phần hỏng nằm trọn ở một chỗ.

    Một giả định đã bị chính lưới của nó bác bỏ, ghi lại để không ai dựng lại: bản đầu đo bằng
    **hiệu** của CER và CER-sau-khi-gỡ-dấu, với lập luận rằng engine thủng từ điển sẽ nhả ra chữ
    trần. Đo thật thì PaddleOCR **xoá hẳn** nguyên âm có dấu -- `Kết nối` ra `Kt ni`, không phải
    `Ket noi` -- nên gỡ dấu ở cả hai phía không làm chúng gần nhau, và hiệu ấy bằng 0 ở đúng ca
    nó sinh ra để bắt. Phép dóng từng ký tự thì không có chỗ cho giả định nào cả.

    Đếm ký tự có dấu ở **cả hai** phía, không chỉ phía nhãn. Bản đầu chỉ duyệt phía nhãn, và
    review 10/10/2026 chỉ ra nó mù với lỗi ngược lại: `diacritic_error_rate("Toan hoc", "Toán
    học")` trả **0,0**. Bịa dấu lên chữ trần là lỗi kinh điển thứ hai của OCR tiếng Việt, đứng
    ngay cạnh lỗi rụng dấu, nên một thước bỏ qua nó thì chỉ đo được nửa chiều nó mang tên.

    Args:
        truth: Chuỗi nhãn vàng.
        read: Chuỗi engine đọc được.

    Returns:
        Một số từ 0,0 tới 1,0. `0,0` khi không phía nào có ký tự mang dấu -- không có gì để hỏng.
    """
    marked = [
        (left, right)
        for left, right in align(truth, read)
        if (left is not None and has_mark(left)) or (right is not None and has_mark(right))
    ]
    if not marked:
        return 0.0
    return sum(1 for left, right in marked if left != right) / len(marked)


def normalise_latex(latex: str) -> str:
    """Bỏ những thứ LaTeX chỉ dùng để trình bày.

    Gỡ lệnh khoảng trắng (`\\;`, `\\quad`, ...), gỡ `\\left`/`\\right`, gom những lệnh khác tên
    mà cùng nghĩa (`\\mathrm` với `\\text`, `\\le` với `\\leq`, ...), bọc mũ một ký tự vào ngoặc
    (`^3` thành `^{3}`), rồi bỏ **mọi** khoảng trắng. Bỏ hết thay vì gom lại một dấu cách, vì
    `a+b` và `a + b` là cùng một công thức còn không engine nào nhất quán về chỗ đặt dấu cách.

    Args:
        latex: Chuỗi LaTeX.

    Returns:
        Chuỗi đã chuẩn hoá, so sánh được.
    """
    bare = _LATEX_SIZING.sub("", _LATEX_SPACING.sub(" ", nfc(latex)))
    for pattern, instead in _LATEX_SYNONYMS:
        bare = pattern.sub(instead, bare)
    bare = _LATEX_SCRIPT.sub(r"\1{\2}", bare)
    return _WHITESPACE.sub("", bare)


def latex_matches(truth: str, read: str) -> bool:
    """Hai công thức có khớp đúng từng ký tự sau chuẩn hoá không.

    Args:
        truth: LaTeX nhãn vàng.
        read: LaTeX engine đọc được.

    Returns:
        True khi khớp.
    """
    return normalise_latex(truth) == normalise_latex(read)


def latex_distance(truth: str, read: str) -> float:
    """Khoảng cách sửa chuẩn hoá giữa hai công thức.

    Đi cạnh `latex_matches` vì khớp-hay-không là một cánh cửa đóng: nó không phân biệt một công
    thức sai một ký tự với một công thức đọc hỏng hoàn toàn, mà bước sửa bằng sympy ở plan sau
    chỉ cứu được loại thứ nhất.

    Args:
        truth: LaTeX nhãn vàng.
        read: LaTeX engine đọc được.

    Returns:
        Tỉ lệ lỗi trên chuỗi đã chuẩn hoá.
    """
    return error_rate(normalise_latex(truth), normalise_latex(read))


# Dấu nhân: sách in `2 . 3`, nhãn vàng gõ `\,.\,`, model gõ `\cdot` hay `\times`; dấu trừ in thành
# gạch nối dài. Cùng nghĩa trong sách Toán phổ thông, nên thước lỏng gom chúng (khảo sát VLM
# 11/10/2026 và đo lại 26/10/2026 đều chấm tay theo luật này).
_LOOSE_SYNONYMS = (
    (re.compile(r"\\mathrm(?![a-zA-Z])"), r"\\text"),
    # `\text{?}`, `\text{( )}`, `\text{\{\ \}}`: chữ thường bọc quanh một ký hiệu không có chữ cái
    # nào. Chạy **trước** khi gom dấu nhân, vì `\cdot` mang chữ cái.
    (re.compile(r"\\text\{((?:[^{}A-Za-zÀ-ỹ\\]|\\[{} ])*)\}"), r"\1"),
    (re.compile(r"\\,\.\\,|\\times(?![a-zA-Z])|×|·"), r"\\cdot "),
    (re.compile(r"[–−]"), "-"),
    (re.compile(r"\{\\([{}])\}"), r"\\\1"),
)
# Vỏ `aligned` và dấu `&` chỉ là cách dàn dòng. Xuống dòng thành `;` chứ không thành khoảng trắng:
# khoảng trắng bị bỏ hết, và hai dòng `…\cdot 3` rồi `60 = …` dính thành `\cdot360` -- mất ranh giới
# mà phép *nằm trong* cần.
_LOOSE_LAYOUT = re.compile(r"\\begin\{aligned\}|\\end\{aligned\}|&")
_LOOSE_NEWLINE = re.compile(r"\\\\")
# Ranh giới của phép *nằm trong*: đầu, cuối, hay một dấu ngăn công thức.
_FORMULA_EDGES = "=;,"
# Chỗ một ô nhãn vàng nối hai công thức: `;`, khoảng `\quad`, hay chữ *và*, *hoặc* giữa hai vế --
# chỉ ở **ngoài** mọi ngoặc, vì `;` cũng ngăn phần tử trong tập hợp `\{a; b\}`.
_GOLD_JOINS = re.compile(r";|\\q?quad|\\text\{\s*(?:và|hoặc)\s*\}")
_BRACES = re.compile(r"\\[{}]|[{}()\[\]]")
# Ngưỡng của phép chấm công thức (khảo sát VLM 26/10/2026, plan `formulas-on-demand`).
_FORMULA_SAME = 0.05
_FORMULA_NEAR = 0.08
_FORMULA_FAR = 0.6
# Một ô vàng ngắn hơn ngần này ký tự (sau chuẩn hoá) không được tính là *nằm trong* một bản đọc dài
# hơn: `a^{n}` nằm trong gần mọi bản đọc của trang luỹ thừa.
_FORMULA_MIN_INSIDE = 8


def normalise_latex_loose(latex: str) -> str:
    """`normalise_latex`, cộng gom dấu nhân, dấu trừ, ngoặc `{\\{}` và vỏ `aligned`.

    Đây là thước để **so model với model** khi chấm đọc công thức từ ảnh: nó bỏ những khác biệt
    về cách gõ mà sách và người đánh nhãn không thống nhất. `normalise_latex` giữ nguyên, vì bảng
    điểm OCR cũ dựa vào nó.

    Args:
        latex: Chuỗi LaTeX.

    Returns:
        Chuỗi đã chuẩn hoá, bỏ dấu chấm, chấm phẩy, phẩy ở cuối.
    """
    loose = latex
    for pattern, instead in _LOOSE_SYNONYMS:
        loose = pattern.sub(instead, loose)
    loose = _LOOSE_NEWLINE.sub(";", _LOOSE_LAYOUT.sub(" ", loose))
    return normalise_latex(loose).strip(".;,")


def _inside(short: str, long: str) -> bool:
    """`short` đứng trọn trong `long`, giữa hai ranh giới (`_FORMULA_EDGES` hay hai đầu). Hàm thuần.

    Không có ranh giới thì `12345678` *nằm trong* `912345678` (review pha 1, `formulas-on-demand`).
    """
    start = long.find(short)
    while start >= 0:
        end = start + len(short)
        before = start == 0 or long[start - 1] in _FORMULA_EDGES
        after = end == len(long) or long[end] in _FORMULA_EDGES
        if before and after:
            return True
        start = long.find(short, start + 1)
    return False


def _gold_parts(truth: str) -> list[str]:
    """Các công thức một ô vàng nối lại, tách ở `_GOLD_JOINS` nằm ngoài mọi ngoặc. Hàm thuần."""
    depth = 0
    cuts: list[tuple[int, int]] = []
    at = 0
    while at < len(truth):
        brace = _BRACES.match(truth, at)
        if brace:
            # Ngoặc lệch số (`a) x=1; b) x=2`) không được làm depth âm và nuốt mọi chỗ nối sau.
            depth = depth + 1 if brace.group()[-1] in "{([" else max(0, depth - 1)
            at = brace.end()
            continue
        join = _GOLD_JOINS.match(truth, at)
        if join and depth == 0:
            cuts.append(join.span())
            at = join.end()
            continue
        at += 1
    parts, start = [], 0
    for begin, end in cuts:
        parts.append(truth[start:begin])
        start = end
    parts.append(truth[start:])
    return [part for part in parts if normalise_latex_loose(part)]


def _unwrapped(latex: str) -> str:
    """Bỏ một cặp ngoặc tròn bao trọn công thức: `(n \\in A)` là `n \\in A`."""
    bare = normalise_latex_loose(latex)
    if bare.startswith("(") and bare.endswith(")") and bare.count("(") == 1:
        return bare[1:-1]
    return bare


def _loose_distance(truth: str, read: str) -> float:
    return error_rate(_unwrapped(truth), _unwrapped(read))


def formula_verdicts(gold: list[str], read: list[str]) -> list[str]:
    """Chấm từng công thức vàng của một trang theo danh sách công thức model đọc ra.

    Mỗi ô vàng nhận một nhãn:

    - `khop`: một bản đọc trùng nó sau chuẩn hoá lỏng, hay chứa trọn nó (model gộp hai ô làm một);
    - `tach`: ô vàng nối nhiều công thức, và mỗi mảnh khớp một bản đọc riêng -- đủ nội dung;
    - `gan`: bản đọc gần nhất lệch không quá `_FORMULA_NEAR`;
    - `lech`: có bản đọc tương ứng nhưng sai;
    - `thieu`: không bản đọc nào đủ gần.

    Bản đọc dư (công thức nội dòng nhãn vàng không ghi) không bị phạt: nhãn vàng chỉ ghi khối công
    thức, còn lời dặn VLM xin mọi biểu thức trên trang.

    Hai luật về việc **dùng lại** bản đọc: nhãn `khop` theo phép *nằm trong* và nhãn `tach` không
    giữ bản đọc lại -- một bản đọc gộp hai ô phải phục vụ được cả hai ô; chỉ phép ghép theo khoảng
    cách tiêu bản đọc, để hai ô không cùng ăn một bản đọc gần đúng. Ô vàng ngắn hơn
    `_FORMULA_MIN_INSIDE` ký tự không bao giờ được nhận là nằm trong một bản đọc gộp.

    Args:
        gold: LaTeX nhãn vàng của trang, theo thứ tự đọc.
        read: LaTeX model đọc ra.

    Returns:
        Một nhãn cho mỗi ô vàng, cùng thứ tự.
    """
    verdicts: list[str] = []
    free = list(range(len(read)))
    for truth in gold:
        loose = normalise_latex_loose(truth)
        parts = _gold_parts(truth)
        if len(loose) >= _FORMULA_MIN_INSIDE and any(
            _inside(loose, normalise_latex_loose(one)) for one in read
        ):
            verdicts.append("khop")
            continue
        if len(parts) > 1 and all(
            any(_loose_distance(part, one) <= _FORMULA_SAME for one in read) for part in parts
        ):
            verdicts.append("tach")
            continue
        best = min(free, key=lambda index: _loose_distance(truth, read[index]), default=None)
        far = 1.0 if best is None else _loose_distance(truth, read[best])
        if best is None or far > _FORMULA_FAR:
            verdicts.append("thieu")
            continue
        free.remove(best)
        verdicts.append(
            "khop" if far <= _FORMULA_SAME else "gan" if far <= _FORMULA_NEAR else "lech"
        )
    return verdicts


def label_accuracy(truth: list[str], read: list[str]) -> float:
    """Chuỗi nhãn khối engine đoán được, so với chuỗi nhãn thật.

    Đo bằng khoảng cách sửa trên **dãy** chứ không bằng phép so từng vị trí: engine gộp hai đoạn
    văn làm một thì mọi nhãn sau đó lệch đi một ô, và một phép so theo vị trí sẽ báo gần như sai
    hết cho một lỗi duy nhất.

    Args:
        truth: Nhãn khối thật, theo thứ tự đọc.
        read: Nhãn khối engine đoán, theo thứ tự nó trả về.

    Returns:
        Một số từ 0,0 tới 1,0.
    """
    if not truth:
        return 1.0 if not read else 0.0
    alphabet: dict[str, str] = {}
    for label in truth + read:
        alphabet.setdefault(label, chr(len(alphabet) + 0x100))
    distance = levenshtein(
        "".join(alphabet[one] for one in truth), "".join(alphabet[one] for one in read)
    )
    return max(0.0, 1.0 - distance / len(truth))


def match_blocks(truth: list[str], read: list[str]) -> list[int | None]:
    """Nối mỗi khối engine đọc được với khối nhãn vàng giống nó nhất.

    Tham lam, không tối ưu toàn cục: trên một trang sách hai khối khác nhau hiếm khi giống nhau
    tới một nửa, nên phép ghép tối ưu và phép ghép tham lam cho cùng kết quả ở gần hết các ca --
    và phép tham lam thì đọc hiểu được khi nó sai.

    Args:
        truth: Chữ của từng khối nhãn vàng, theo thứ tự đọc.
        read: Chữ của từng khối engine trả về, theo thứ tự nó trả về.

    Returns:
        Một phần tử cho mỗi khối của `read`: chỉ số khối nhãn vàng tương ứng, hoặc `None` khi
        không khối nào đủ giống -- tức engine bịa ra một khối không có trên trang.
    """
    taken: set[int] = set()
    matched: list[int | None] = []
    for one in read:
        best, score = None, _SAME_BLOCK_SIMILARITY
        for at, other in enumerate(truth):
            if at in taken:
                continue
            similarity = similar(other, one)
            if similarity > score:
                best, score = at, similarity
        if best is not None:
            taken.add(best)
        matched.append(best)
    return matched


def similar(truth: str, read: str) -> float:
    """Hai khối giống nhau tới đâu, trên thang 0,0 -- 1,0.

    Mẫu số là **khối dài hơn**, không phải khối nhãn. Với mẫu số cũ, một khối nhãn dài 1--2 ký
    tự không chịu nổi một phép sửa nào, nên `'7'` và `'7.'` bị coi là hai khối khác nhau -- và
    **cả 48 khối `number`** của bộ nhãn, chính thứ dùng để nối trang PDF với trang in trong
    sách, rơi khỏi mọi phép ghép mà không ô nào trong bảng điểm nói ra. Review 10/10/2026 bắt
    được.

    Khối rất ngắn có luật riêng, vì một tỉ lệ không nói được gì trên hai ký tự: cho phép đúng
    một phép sửa, và **không** cho phép nếu chuỗi chỉ dài một ký tự -- `'7'` và `'9'` là hai số
    trang khác nhau, không phải một số trang đọc lệch.

    Args:
        truth: Chữ của khối nhãn vàng.
        read: Chữ của khối engine đọc được.

    Returns:
        Độ giống. `1,0` khi cả hai cùng rỗng -- hai khối hình hay hai khối bảng không có chữ để
        so, nên chúng ghép được với nhau.
    """
    left, right = flatten(nfc(truth)), flatten(nfc(read))
    longest = max(len(left), len(right))
    if longest == 0:
        return 1.0
    distance = levenshtein(left, right)
    if longest < _SHORT_BLOCK:
        near = distance <= _SHORT_BLOCK_EDITS and longest > distance
        return 1.0 if distance == 0 or near else 0.0
    return max(0.0, 1.0 - distance / longest)


def order_inversions(matched: list[int | None]) -> int:
    """Đếm số cặp khối engine trả về **sai thứ tự** so với thứ tự đọc thật.

    Không phạt khối thiếu hay khối bịa -- hai thứ ấy đã bị `label_accuracy` và `cer` phạt rồi.
    Con số này chỉ trả lời một câu: những khối engine **có** đọc được, nó có xếp đúng thứ tự
    không? Đó là câu quyết định bước dựng mục lục ở plan sau, vì một cây dựng trên thứ tự đọc
    sai là một cây sai mà mọi khối trong nó đều đúng.

    Args:
        matched: Kết quả của `match_blocks`.

    Returns:
        Số cặp nghịch thế. `0` là thứ tự hoàn hảo.
    """
    order = [one for one in matched if one is not None]
    return sum(1 for at, one in enumerate(order) for other in order[at + 1 :] if other < one)
