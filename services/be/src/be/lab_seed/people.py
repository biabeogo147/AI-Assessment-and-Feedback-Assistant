"""Người của seed lab: năm giáo viên viết tay, học sinh ghép tên theo họ, đệm, tên.

Họ tên ghép từ ba danh sách theo một `random.Random` đã gieo hạt, nên cùng một hạt cho cùng một lớp
học. Họ có trọng số: ba họ Nguyễn, Trần, Lê chiếm gần nửa, như một lớp thật.
"""

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Staff:
    """Một giáo viên của lab.

    Attributes:
        full_name: Họ tên, kèm *Cô*/*Thầy* như dữ liệu demo.
        phone: Số điện thoại đăng nhập, dạng chỉ chữ số.
        email: Email đăng nhập.
    """

    full_name: str
    phone: str
    email: str


STAFF = (
    Staff("Cô Nguyễn Thị Hồng Nhung", "0912000101", "nhung.nguyen@example.com"),
    Staff("Thầy Trần Quốc Bảo", "0912000102", "bao.tran@example.com"),
    Staff("Cô Lê Minh Thư", "0912000103", "thu.le@example.com"),
    Staff("Thầy Hoàng Văn Đức", "0912000104", "duc.hoang@example.com"),
    Staff("Cô Vũ Thanh Hà", "0912000105", "ha.vu@example.com"),
)

# (họ, trọng số)
_SURNAMES = (
    ("Nguyễn", 30),
    ("Trần", 11),
    ("Lê", 9),
    ("Phạm", 7),
    ("Hoàng", 5),
    ("Huỳnh", 4),
    ("Phan", 4),
    ("Vũ", 4),
    ("Võ", 3),
    ("Đặng", 3),
    ("Bùi", 3),
    ("Đỗ", 3),
    ("Hồ", 2),
    ("Ngô", 2),
    ("Dương", 2),
    ("Lý", 1),
)
_MIDDLE = {
    "nam": ("Văn", "Minh", "Đức", "Quang", "Hoàng", "Gia", "Anh", "Thành", "Hữu", "Tuấn"),
    "nữ": ("Thị", "Thu", "Ngọc", "Thanh", "Phương", "Minh", "Khánh", "Bảo", "Mai", "Hải"),
}
_GIVEN = {
    "nam": (
        "An", "Bảo", "Cường", "Dũng", "Duy", "Đạt", "Hiếu", "Hùng", "Huy", "Khang",
        "Khoa", "Kiên", "Long", "Lâm", "Minh", "Nam", "Nghĩa", "Phong", "Phúc", "Quân",
        "Sơn", "Tài", "Thắng", "Thịnh", "Toàn", "Trung", "Tùng", "Việt", "Vinh", "Vũ",
    ),
    "nữ": (
        "Anh", "Châu", "Chi", "Dung", "Giang", "Hà", "Hân", "Hằng", "Hoa", "Hương",
        "Lan", "Linh", "Ly", "Mai", "My", "Ngân", "Nhi", "Nhung", "Oanh", "Phương",
        "Quỳnh", "Tâm", "Thảo", "Trang", "Trâm", "Uyên", "Vân", "Vy", "Yến", "Thư",
    ),
}  # fmt: skip


def student_names(rng: random.Random, count: int) -> list[str]:
    """Ghép `count` họ tên học sinh, nam nữ xấp xỉ một nửa.

    Args:
        rng: Nguồn ngẫu nhiên đã gieo hạt.
        count: Bao nhiêu tên.

    Returns:
        Họ tên theo thứ tự ghép; có thể trùng nhau như ở trường thật -- tên đăng nhập vẫn khác nhau
        nhờ `be.accounts.usernames_for`.
    """
    surnames = [name for name, _ in _SURNAMES]
    weights = [weight for _, weight in _SURNAMES]
    names = []
    for _ in range(count):
        sex = rng.choice(("nam", "nữ"))
        surname = rng.choices(surnames, weights)[0]
        given = rng.choice(_GIVEN[sex])
        # "Hoàng Hoàng Khoa", "Lê Minh Minh": có thật nhưng hiếm, và người thử tay đọc ra lỗi.
        middle = rng.choice([m for m in _MIDDLE[sex] if m not in (surname, given)])
        names.append(f"{surname} {middle} {given}")
    return names
