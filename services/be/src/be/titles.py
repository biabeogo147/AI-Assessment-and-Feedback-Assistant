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


def tidy(title: str) -> str:
    """Một dòng, khoảng trắng gọn, không ngoặc kép bao ngoài. Hàm thuần."""
    return " ".join(title.split()).strip().strip('"').strip("'").strip()


def clipped(title: str) -> str:
    """Tên vừa `MOST_TITLE`: cắt ở ranh giới từ, kèm `…`. Hàm thuần."""
    title = tidy(title)
    if len(title) <= MOST_TITLE:
        return title
    head = title[: MOST_TITLE - 1]
    cut = head.rsplit(" ", 1)[0] if " " in head else head
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
