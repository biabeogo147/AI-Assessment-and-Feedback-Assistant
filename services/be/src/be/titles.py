"""Tên một đề kiểm tra (ADR-31): tối đa 60 ký tự, một chỗ cho luật ấy.

Hai đường đặt tên đi qua đây: hệ thống đặt lúc mở đề nháp (`teacher_tools._create_draft`), và giáo
viên đổi tên ở panel (`teacher_routes.rename_assessment`). Đường thứ nhất **cắt** cho vừa -- đó là
tên tự suy ra, không ai gõ nó --; đường thứ hai **từ chối** khi quá trần: chữ của giáo viên chỉ giáo
viên sửa.
"""

import re

# Trần của tên đề (ADR-31). Thẻ *Đã tạo đề "…"* rộng 820px còn chỗ cho chừng 70 ký tự; mở panel thì
# cột chat hẹp lại, nên 60.
MOST_TITLE = 60

# Số trang cuối một nhãn bài: *"Bài 1. TẬP HỢP (tr. 5–9)"*. Tên đề không cần nó.
_PAGES = re.compile(r"\s*\(tr\.[^)]*\)")


# Cặp ngoặc model hay bọc quanh cả tên nó đặt.
_WRAPPERS = (('"', '"'), ("'", "'"), ("“", "”"))


def tidy(title: str) -> str:
    """Một dòng, khoảng trắng gọn. Hàm thuần.

    Chỉ thế: đây là cả phần dọn chữ giáo viên gõ. Một dấu ngoặc ở đầu hay cuối tên -- *Ôn tập chương
    "Số nguyên"* -- là của tên (review pha 6).
    """
    return " ".join(title.split())


def _unquoted(title: str) -> str:
    """Bỏ **một** cặp ngoặc khi nó bọc cả tên, như model hay viết. Hàm thuần."""
    for opening, closing in _WRAPPERS:
        if len(title) >= 2 and title.startswith(opening) and title.endswith(closing):
            return title[1:-1].strip()
    return title


def clipped(title: str) -> str:
    """Tên vừa `MOST_TITLE`: cắt ở ranh giới từ, kèm `…`. Hàm thuần.

    Chỉ cho tên hệ thống hay model đặt; tên giáo viên gõ quá trần thì bị từ chối, không bị cắt.
    """
    title = _unquoted(tidy(title))
    if len(title) <= MOST_TITLE:
        return title
    head = title[: MOST_TITLE - 1]
    # Ký tự ngay sau phần giữ là khoảng trắng thì phần giữ đã trọn từ: không bỏ thêm từ nào.
    whole = title[MOST_TITLE - 1] == " " or " " not in head
    cut = head if whole else head.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:.-–—") + "…"


def default_title(scope: str, filename: str = "") -> str:
    """Tên hệ thống đặt cho một đề nháp (ADR-31). Hàm thuần.

    Args:
        scope: Phạm vi model ghi (`topic_scope`).
        filename: Tên tệp sách khi đề soạn từ sách; rỗng khi không.

    Returns:
        `"Đề " + tên tệp bỏ đuôi` khi có sách, không thì `"Đề " + phạm vi` bỏ số trang; tối đa
        `MOST_TITLE` ký tự.
    """
    name = tidy(filename)
    if name:
        stem = name.rsplit(".", 1)[0] if "." in name else name
        return clipped(f"Đề {stem}")
    return clipped(f"Đề {_PAGES.sub('', scope)}")
