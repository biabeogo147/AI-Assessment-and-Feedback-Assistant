"""Từ cái tên giáo viên gõ ra, về một dòng dữ liệu -- hoặc về một danh sách.

`classes.name` không có unique constraint, nên tên lớp không phải một identifier:
một giáo viên có thể dạy hai lớp cùng tên 12A ở hai năm khác nhau, và hai giáo
viên mỗi người cũng có thể có một lớp như thế. Mọi tool làm việc với một lớp đều
cần `class_id`, nên bước dịch này chính là chỗ mà toàn bộ bề mặt hướng về giáo
viên hoặc là hỏi lại, hoặc là đoán.

Nó hỏi lại -- nhưng **không hỏi ở đây**. Module này từng chứa `resolve_class`, một
hàm tự phân định một cái tên ra ba câu trả lời (`Resolved`, `Ambiguous`,
`NotFound`) và tự dựng sẵn câu hỏi lại. Từ 06/10/2026 việc ấy thuộc về model:
`list_class` liệt kê, model đọc rồi hỏi giáo viên (ADR-23). Một tool vừa tìm vừa
hỏi lại là một tool có bốn hình dạng trả về, và model phải đoán lần này nhận hình
nào. Ba kiểu kia đã xoá cùng hàm ấy; chúng chỉ còn test gọi tới, và một luật chỉ
còn test tin là một luật đã chết.

Còn lại ở đây ba thứ, mỗi thứ làm đúng một việc:

- `normalise` -- rút "Lớp: 12A" và "lớp12A" về cùng một string để đem đi so.
- `classes_with_counts` -- mọi lớp của **một** giáo viên, kèm số học sinh, một query.
- `capped` -- cắt danh sách xuống mức một câu hỏi chở được, và nói ra đã bỏ bao nhiêu.

Hai luật mà cả ba đều tuân theo:

**Một lớp của giáo viên khác đọc ra đúng y như một lớp không tồn tại** (ADR-22).
Không phải một message khác, không phải một type khác -- nó đơn giản không có
trong danh sách. Hai lời từ chối phân biệt được với nhau sẽ là một cái dò: gõ thử
các tên cho đến khi câu chữ đổi, thế là vẽ xong bản đồ cả trường. Cái filter
`teacher_id` trong `classes_with_counts` là toàn bộ ADR-22 ở đây.

**Mọi thứ trả về là giá trị, không phải row.** Cái vòng lặp gọi các hàm này
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


async def classes_with_counts(session: AsyncSession, asking: Asking) -> list[Candidate]:
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


def capped(matches: list[Candidate]) -> tuple[tuple[Candidate, ...], int]:
    """Cắt ngắn một danh sách candidate và báo lại đã bỏ ra bao nhiêu."""
    kept = tuple(matches[:_MOST_CANDIDATES])
    return kept, max(0, len(matches) - len(kept))
