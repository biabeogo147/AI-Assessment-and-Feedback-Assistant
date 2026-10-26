r"""Dựng lại dấu gạch chéo mà JSON đã nuốt mất trên đường từ model về.

JSON có **đúng tám** escape hợp lệ: `\" \\ \/ \b \f \n \r \t \uXXXX`. Model viết toán
bằng LaTeX, mà LaTeX thì bắt đầu mọi lệnh bằng `\`. Khi model đặt `\frac` vào một chuỗi
JSON mà không nhân đôi dấu gạch chéo, bộ giải mã đọc `\f` thành form-feed và **nuốt luôn
chữ `f`** -- cái còn lại là `0x0C` + `"rac"`.

Đo được trên database thật ngày 05/10/2026, phương án A của một câu vừa soạn:

    24 0c 72 61 63 7b 31 7d 7b 36 7d 24      ->  "$" 0x0C "rac{1}{6}" "$"

Năm ca có thể xảy ra, và chỉ năm: `\b \f \n \r \t`. `\int` sống sót nguyên vẹn vì `\i`
không nằm trong tám escape kia, nên bộ giải mã để cả hai ký tự lại.

**Hậu quả không giống nhau giữa các chỗ, và đó là lý do việc này khó thấy.** Đề bài thì
`MathText` vẫn nhận ra là toán và KaTeX in đỏ nguyên văn -- xấu nhưng đọc ra được. Còn
phương án thì tệ hơn hẳn: `0x0C` đứng ngay sau `$` **là khoảng trắng** theo `\s` của
regex, nên luật pandoc `\$(?![\s$])` từ chối nhận cả cụm là toán, và dấu đô la lọt thẳng
ra màn hình giáo viên.

**Vì sao ở đây mà không ở `packages/contracts`.** `contracts/AGENTS.md` nói "Data only",
và đây là hành vi. Quan trọng hơn: `be/teacher_routes.py` dựng lại chính `GeneratedQuestion`
cho đường PATCH của giáo viên, nên một validator đặt ở contract sẽ sửa luôn chữ **giáo
viên tự gõ** -- thứ không ai nhờ. Hỏng hóc sinh ra ở ranh giới structured-output, nên nó
được chữa ở đúng ranh giới ấy.

**Từ điển là một danh sách kinh nghiệm, và nó sẽ thiếu.** Đo được ngay lượt soạn đầu tiên
sau khi việc này xong: `\textstyle` bị bỏ sót, phải thêm vào. Thiếu một lệnh thì hậu quả
là *không chữa*, chứ không phải *chữa sai* -- ký tự ở lại nguyên chỗ, và `Field` ở FE in
nó ra bằng ký hiệu nhìn thấy được để giáo viên xử lý. Đó là hướng hỏng đúng: thà bỏ sót
còn hơn đoán bừa vào chữ của người khác.

Cũng trong lượt ấy, model viết `\bigint` -- **không phải lệnh LaTeX nào cả**. Chỗ này để
nguyên, và đúng là nên để nguyên: KaTeX cũng không dựng được `\bigint`, nên đoán ra một
lệnh ở đây chỉ đổi một lỗi nhìn thấy được thành một lỗi ẩn.

**Vì sao theo từ điển chứ không thay mù.** `0x0A` và `0x0D` là xuống dòng **thật** trong
lời giải -- thứ vừa được sửa cho hiển thị đúng. Một phép "thay mọi ký tự điều khiển" sẽ
phá đúng cái vừa sửa. Từ điển cho phép phân biệt: `0x0A` + `"abla"` là `\nabla` bị nuốt,
còn `0x0A` + `"2. Tính..."` là một lần xuống dòng thật.
"""

import re

__all__ = ["CONTROL_TO_LETTER", "LATEX_COMMANDS", "restore_latex_escapes"]


#: Ký tự điều khiển -> chữ cái mà bộ giải mã JSON đã ăn mất cùng với dấu gạch chéo.
CONTROL_TO_LETTER = {
    "\x08": "b",
    "\x09": "t",
    "\x0a": "n",
    "\x0c": "f",
    "\x0d": "r",
}

#: Các lệnh LaTeX bắt đầu bằng một trong năm chữ cái trên, giới hạn ở toán phổ thông
#: Việt Nam. Chỉ cần những lệnh **có thể** bị nuốt: lệnh bắt đầu bằng chữ khác (`\int`,
#: `\sum`, `\alpha`) không bao giờ đi qua đây vì JSON không đụng tới chúng.
LATEX_COMMANDS = frozenset(
    {
        # b
        "backslash",
        "begin",
        "beta",
        "big",
        "bigg",
        "biggl",
        "biggr",
        "bigl",
        "bigcap",
        "bigcirc",
        "bigcup",
        "bigoplus",
        "bigotimes",
        "bigr",
        "bigsqcup",
        "bigtriangledown",
        "bigtriangleup",
        "bigvee",
        "bigwedge",
        "binom",
        "bmatrix",
        "bmod",
        "boldsymbol",
        "bot",
        "brace",
        "bracket",
        "bullet",
        # f
        "fbox",
        "frac",
        "frak",
        "forall",
        "frown",
        # n
        "nabla",
        "natural",
        "ne",
        "nearrow",
        "neg",
        "neq",
        "newline",
        "nexists",
        "ni",
        "nmid",
        "norm",
        "notin",
        "nparallel",
        "nsubseteq",
        "nu",
        "nwarrow",
        # r
        "rangle",
        "rbrace",
        "rbrack",
        "rceil",
        "rfloor",
        "rho",
        "right",
        "rightarrow",
        "rightleftharpoons",
        "rm",
        "rvert",
        # t
        "tan",
        "tanh",
        "tau",
        "tbinom",
        "text",
        "textbf",
        "textit",
        "textnormal",
        "textrm",
        "textsc",
        "textsf",
        "textstyle",
        "texttt",
        "tfrac",
        "therefore",
        "theta",
        "tilde",
        "times",
        "tiny",
        "to",
        "top",
        "triangle",
        "triangleq",
        "trianglelefteq",
    }
)

#: Ký tự được phép đứng ngay sau một lệnh. Không có luật này thì một từ tiếng Việt bắt
#: đầu bằng `rac` cũng kéo theo cả cụm vào.
_BOUNDARY = re.compile(r"[\s{}()\[\]|^_\\$0-9,.;:!?+\-*/=<>'\"]")

#: Chuỗi chữ cái ASCII ngay sau ký tự điều khiển -- phần còn lại của tên lệnh.
_LETTERS = re.compile(r"[A-Za-z]+")

#: Độ dài tối thiểu của một lệnh khi ký tự bị nuốt là xuống dòng. Xuống dòng thật đứng
#: trước một token hai chữ cái (`to`, `ne`) là chuyện thường ngày trong lời giải đánh số;
#: đứng trước `abla` hay `ightarrow` thì không. Con số này mua bằng đúng ca ấy.
_MIN_LENGTH_AFTER_NEWLINE = 4


def _command_at(text: str, start: int, letter: str) -> str | None:
    """Tên lệnh dài nhất bắt đầu tại `start`, hoặc `None` khi không có lệnh nào.

    Args:
        text: Cả chuỗi đang xét.
        start: Vị trí ngay **sau** ký tự điều khiển.
        letter: Chữ cái mà bộ giải mã JSON đã ăn mất.

    Returns:
        Tên lệnh đầy đủ gồm cả `letter`, hoặc `None`.
    """
    found = _LETTERS.match(text, start)
    tail = found.group(0) if found is not None else ""

    # Đi từ dài xuống ngắn cho dễ đọc, **không** phải vì thứ tự quyết định kết quả: thứ
    # loại được bản ngắn là luật ranh giới ngay dưới. Với hai lệnh mà cái ngắn là tiền tố
    # của cái dài (`right` trong `rightarrow`), ký tự ngay sau bản ngắn luôn là một chữ
    # cái -- phần còn lại của bản dài -- nên bản ngắn không bao giờ qua được ranh giới.
    # Đã đo: đảo chiều vòng lặp này không làm đỏ test nào.
    for size in range(len(tail), -1, -1):
        name = letter + tail[:size]
        if name not in LATEX_COMMANDS:
            continue
        after = start + size
        if after < len(text) and _BOUNDARY.match(text[after]) is None:
            continue
        return name
    return None


def restore_latex_escapes(text: str) -> str:
    r"""Trả lại dấu gạch chéo cho những lệnh LaTeX mà JSON đã nuốt.

    Ký tự điều khiển nào không ghép thành một lệnh có thật thì **để nguyên**. Đó là chủ
    ý: một lần xuống dòng thật trong lời giải phải đi qua đây không suy suyển, và một
    ký tự hỏng không đoán được thì thà để giáo viên nhìn thấy còn hơn đoán bừa.

    Args:
        text: Chuỗi model vừa viết, đã qua bộ giải mã JSON.

    Returns:
        Chuỗi với các lệnh đã dựng lại.

    Examples:
        >>> restore_latex_escapes("$\x0crac{1}{2}$")
        '$\\frac{1}{2}$'
        >>> restore_latex_escapes("1. Tính\n2. Kết luận")
        '1. Tính\n2. Kết luận'
    """
    if not text:
        return text

    out: list[str] = []
    at = 0
    while at < len(text):
        letter = CONTROL_TO_LETTER.get(text[at])
        if letter is None:
            out.append(text[at])
            at += 1
            continue

        name = _command_at(text, at + 1, letter)
        newline = text[at] in "\n\r"
        if name is None or (newline and len(name) < _MIN_LENGTH_AFTER_NEWLINE):
            out.append(text[at])
            at += 1
            continue

        out.append("\\" + name)
        at += len(name)  # ký tự điều khiển cộng phần đuôi đã tiêu thụ

    return "".join(out)
