"""Từ thứ giáo viên gõ ra, đến một row, hoặc đến một câu hỏi.

`classes.name` không có unique constraint, nên tên lớp không phải một
identifier: một giáo viên có thể dạy hai lớp cùng tên 12A ở hai năm khác nhau, và
hai giáo viên mỗi người cũng có thể có một lớp như thế. Mọi tool làm việc với một
lớp đều cần `class_id`, nên bước dịch này chính là chỗ mà toàn bộ bề mặt hướng về
giáo viên hoặc là hỏi lại, hoặc là đoán.

Nó hỏi lại. Ba câu trả lời và không có câu thứ tư:

- `Resolved` -- đúng một lớp của giáo viên này khớp.
- `Ambiguous` -- có nhiều lớp có thể là lớp được nói tới, và chúng được trả về
  dưới dạng candidate để trợ lý hỏi lại. ADR-05 cấm đánh dấu một trong số chúng
  là lớp nên chọn; module này trả chúng về theo một thứ tự ổn định và không nói
  gì về việc lớp nào khả năng cao hơn.
- `NotFound` -- không lớp nào của giáo viên này khớp, và câu trả lời mang theo
  danh sách những lớp thực sự có, vì chỉ nói "không có lớp nào tên đó" thì giáo
  viên không phân biệt được một lỗi gõ sai với chuyện dữ liệu đã mất.

Hai luật mà các câu trả lời đều tuân theo:

**Một lớp của giáo viên khác được trả lời đúng y như một lớp không tồn tại**
(ADR-22). Không phải một message khác, không phải một type khác -- cùng một
`NotFound` mang theo cùng một danh sách. Hai lời từ chối phân biệt được với nhau
sẽ là một cái dò: gõ thử các tên cho đến khi câu chữ đổi, thế là vẽ xong bản đồ
cả trường.

**Mọi thứ trả về là giá trị, không phải row.** Cái vòng lặp gọi hàm này
rollback session của nó giữa các bước, và việc đó làm các object ORM hết hạn; một
`SchoolClass` đưa lên trên sẽ nổ `MissingGreenlet` ở lần đọc attribute tiếp theo,
ở một chỗ rất xa đây.
"""

import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from be.identity import Asking
from be.models import SchoolClass, Student

# Một lời từ chối hay một câu hỏi lại sẽ nêu tên bao nhiêu lớp. Giáo viên có ba
# mươi lớp thì nhận được một câu hỏi họ trả lời được, không phải một danh sách họ
# phải đọc: trợ lý sẽ đề nghị họ nói cụ thể hơn.
_MOST_CANDIDATES = 6

# "lớp 12A", "Lop 12a", "12 A" đều chỉ cùng một lớp. Cắt bỏ tiền tố chứ không
# khớp lỏng, vì khớp lỏng chính là thứ biến một cái tên khớp chính xác thành một
# cái tên nhập nhằng.
#
# Nguyên âm được liệt kê ra hết vì "ơ" (U+01A1) và "ớ" (U+1EDB) là hai ký tự khác
# nhau, và "lớp" dùng ký tự thứ hai. Một character class `[oơ]` trông như đã phủ
# hết cái từ đó nhưng lặng lẽ không phủ -- và đó đúng là cách nó được viết ở lần
# đầu tiên.
#
# Phần đuôi là tuỳ chọn và cho phép dấu câu, vì giáo viên viết "Lớp: 12A" và
# "lớp12A" dễ dàng như viết "lớp 12A". Bắt buộc phải có dấu cách thì cả ba cách
# viết đó đều thành câu trả lời không-tìm-thấy, đọc lên như thể hệ thống đã làm
# mất một lớp mà giáo viên đang đứng trước mặt.
_PREFIX = re.compile(r"^\s*l[oơớờởỡợôốồổỗộóòỏõọ]p\s*[:.\-–—]?\s*", re.IGNORECASE)
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True)
class Candidate:
    """Một lớp mà cái tên có thể đang nói tới, dưới dạng giá trị.

    Attributes:
        class_id: Thứ mọi tool khác cần.
        name: Theo đúng cách đã lưu, không phải sau khi normalise -- đây là thứ
            được hiện ra cho giáo viên.
        student_count: Số học sinh trong lớp, và đó là cách giáo viên phân biệt
            hai lớp cùng tên. Nó đi kèm vì không có nó thì một câu hỏi lại đưa ra
            "12A" và "12A" là một câu không thể trả lời.
    """

    class_id: str
    name: str
    student_count: int


@dataclass(frozen=True)
class Resolved:
    """Đúng một lớp khớp.

    Attributes:
        class_id: Cái id mà các tool nhận.
        name: Theo đúng cách đã lưu.
        student_count: Số học sinh trong lớp.
    """

    class_id: str
    name: str
    student_count: int


@dataclass(frozen=True)
class Ambiguous:
    """Có nhiều lớp có thể là lớp được nói tới.

    Attributes:
        candidates: Từng lớp đã khớp, theo một thứ tự ổn định. Không field nào
            nói nên ưu tiên lớp nào, vì ADR-05 để lựa chọn đó cho giáo viên.
        more: Có bao nhiêu lớp khớp đã bị để ngoài `candidates`, để trợ lý nói
            được rằng danh sách này chưa đủ thay vì ngụ ý nó là đủ.
    """

    candidates: tuple[Candidate, ...]
    more: int = 0


@dataclass(frozen=True)
class NotFound:
    """Không lớp nào của giáo viên này khớp.

    Attributes:
        available: Các lớp của giáo viên này, để lời từ chối trả lời luôn câu hỏi
            hiển nhiên tiếp theo. Có giới hạn số lượng, và `more` đếm phần còn lại.
        more: Có bao nhiêu lớp đã bị để ngoài.
    """

    available: tuple[Candidate, ...]
    more: int = 0


def normalise(name: str) -> str:
    """Rút một tên lớp được gõ vào về đúng cái nó có nghĩa.

    Chuẩn hoá dạng Unicode trước. "lớp" gõ trên máy Mac đến đây ở dạng tách rời --
    "l", "o", U+031B, "p" -- và so sánh ra khác với dạng ghép đang lưu trong
    database, nên không có bước này thì một giáo viên dùng macOS nhận
    không-tìm-thấy với mọi lớp họ gọi tên.

    Args:
        name: Theo đúng cách giáo viên viết, có thể có "lớp" ở trước và có thể có
            dấu câu ở sau chữ đó.

    Returns:
        Dạng ghép, chữ thường, đã bỏ từ "lớp" và bỏ hết khoảng trắng. Rỗng khi đầu
        vào không mang theo tên nào, và caller phải coi đó là "không gọi tên gì
        cả", không bao giờ được coi là "khớp với tất cả".
    """
    composed = unicodedata.normalize("NFC", name)
    return _SPACES.sub("", _PREFIX.sub("", composed)).casefold()


async def _candidates(session: AsyncSession, asking: Asking) -> list[Candidate]:
    """Mọi lớp giáo viên này sở hữu, kèm số học sinh, trong một query.

    Args:
        session: Session của database.
        asking: Lớp của ai. Cái filter này chính là toàn bộ ADR-22 ở đây.

    Returns:
        Các candidate sắp theo name rồi đến id, để hai lớp cùng một tên lần nào
        cũng trở về theo cùng một thứ tự -- một câu hỏi lại mà các phương án tự
        đổi chỗ giữa hai lần hỏi là câu hỏi mà giáo viên không trả lời được đến
        lần thứ hai.
    """
    counted = (
        select(SchoolClass.id, SchoolClass.name, func.count(Student.id))
        .outerjoin(Student, Student.class_id == SchoolClass.id)
        .where(SchoolClass.teacher_id == asking.teacher_id)
        .group_by(SchoolClass.id, SchoolClass.name)
        .order_by(SchoolClass.name, SchoolClass.id)
    )
    rows = await session.execute(counted)
    return [
        Candidate(class_id=class_id, name=name, student_count=count)
        for class_id, name, count in rows.all()
    ]


def _capped(matches: list[Candidate]) -> tuple[tuple[Candidate, ...], int]:
    """Cắt ngắn một danh sách candidate và báo lại đã bỏ ra bao nhiêu."""
    kept = tuple(matches[:_MOST_CANDIDATES])
    return kept, max(0, len(matches) - len(kept))


async def resolve_class(
    session: AsyncSession, asking: Asking, typed: str
) -> Resolved | Ambiguous | NotFound:
    """Tìm ra một cái tên đang nói tới lớp nào trong các lớp của giáo viên này.

    Khớp chính xác trước, rồi mới khớp chuỗi con. Đúng thứ tự đó là thứ làm cả hai
    nửa đều an toàn: khớp chuỗi con là thứ cho "12" nghĩa là "một trong 12A và
    12B", và cũng chính nó là thứ sẽ làm "12A" thành nhập nhằng ngay khi có một
    lớp 12A1.

    Args:
        session: Session của database.
        asking: Ai đang hỏi. Chỉ các lớp của người đó được xét tới, và một lớp của
            người khác thì không phân biệt được với một lớp không có ở đó
            (ADR-22).
        typed: Cái tên theo đúng cách giáo viên viết.

    Returns:
        `Resolved` khi khớp một lớp, `Ambiguous` khi khớp nhiều lớp, `NotFound`
        khi không khớp lớp nào. Không bao giờ là một phỏng đoán: không có nhánh
        code nào chọn một lớp trong nhiều lớp.
    """
    owned = await _candidates(session, asking)
    wanted = normalise(typed)
    if not wanted:
        # Một tham số model bỏ trống thì đến đây dưới dạng "". Đem nó đi khớp
        # chuỗi con thì sẽ khớp mọi lớp, và trợ lý sẽ resolve ra lớp nào đứng
        # trước thì lấy lớp đó.
        available, more = _capped(owned)
        return NotFound(available=available, more=more)

    # Cách viết đang lưu trước đã, trước khi có gì bị normalise mất đi. "12A" và
    # "12 A" là hai row khác nhau nhưng normalise về cùng một string, nên nếu chỉ
    # có phép so sánh trên bản normalise thì chúng nhập nhằng mãi mãi và không
    # string nào giáo viên gõ được sẽ chọn ra nổi một trong hai. Bước này cho mỗi
    # lớp một đường vào mà không làm yếu đi lời từ chối đoán: nó chỉ khớp khi giáo
    # viên viết cái tên đúng y như nó đang được lưu.
    literal = unicodedata.normalize("NFC", typed).strip()
    verbatim = [
        candidate for candidate in owned if unicodedata.normalize("NFC", candidate.name) == literal
    ]
    if len(verbatim) == 1:
        only = verbatim[0]
        return Resolved(class_id=only.class_id, name=only.name, student_count=only.student_count)

    exact = [candidate for candidate in owned if normalise(candidate.name) == wanted]
    if len(exact) == 1:
        only = exact[0]
        return Resolved(class_id=only.class_id, name=only.name, student_count=only.student_count)
    if len(exact) > 1:
        candidates, more = _capped(exact)
        return Ambiguous(candidates=candidates, more=more)

    partial = [candidate for candidate in owned if wanted in normalise(candidate.name)]
    if len(partial) == 1:
        only = partial[0]
        return Resolved(class_id=only.class_id, name=only.name, student_count=only.student_count)
    if len(partial) > 1:
        candidates, more = _capped(partial)
        return Ambiguous(candidates=candidates, more=more)

    available, more = _capped(owned)
    return NotFound(available=available, more=more)
