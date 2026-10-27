"""Tên một đề kiểm tra (ADR-31): tối đa 60 ký tự, một chỗ cho luật ấy.

Hai đường đặt tên đi qua đây: hệ thống đặt lúc mở đề nháp (`teacher_tools._create_draft`), và giáo
viên đổi tên ở panel (`teacher_routes.rename_assessment`). Đường thứ nhất **cắt** cho vừa -- đó là
tên tự suy ra, không ai gõ nó --; đường thứ hai **từ chối** khi quá trần: chữ của giáo viên chỉ giáo
viên sửa.
"""

import re
import unicodedata

# Trần của tên đề (ADR-31). Thẻ *Đã tạo đề "…"* rộng 820px còn chỗ cho chừng 70 ký tự; mở panel thì
# cột chat hẹp lại, nên 60.
MOST_TITLE = 60

# Số trang cuối một nhãn bài hay một tên tệp: *"Bài 1. TẬP HỢP (tr. 5–9)"*, *"Kết nối tri thức
# Lớp 6 tập 1 (tr6-28).pdf"*. Tên đề không cần nó (plan `wave-2-time-marks-titles`): một cụm
# ngoặc mở bằng *tr* rồi một chữ số, có hay không dấu chấm và khoảng trắng.
_PAGES = re.compile(r"\s*\(tr\.?\s*\d[^)]*\)", re.IGNORECASE)


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
        `"Đề " + tên tệp bỏ đuôi và số trang` khi có sách, không thì `"Đề " + phạm vi` bỏ số
        trang; tối đa `MOST_TITLE` ký tự.
    """
    name = tidy(filename)
    if name:
        stem = name.rsplit(".", 1)[0] if "." in name else name
        return clipped(f"Đề {_PAGES.sub('', stem)}")
    return clipped(f"Đề {_PAGES.sub('', scope)}")


# Chữ đi liền sau *Đề* mà bỏ *Đề* thì đổi nghĩa: *"Đề cương ôn tập"* không phải đề *"Cương ôn tập"*.
# Cùng danh sách với FE `ActionCard.DE_IS_PART_OF_THE_WORD`.
_DE_IS_PART_OF_THE_WORD = ("cương", "án", "tài", "xuất", "nghị", "mục")

# Phần chữ đầu một từ, bỏ dấu câu đi liền (*"cương,"* là *cương*).
_LETTERS = re.compile(r"\w+")


def spoken_title(title: str) -> str:
    """Tên đề như đứng sau chữ *đề* trong một câu: *Đã tạo đề "Mệnh đề"*. Hàm thuần.

    Tên tự đặt mở bằng *Đề* (`default_title`), nên *đề "Đề mệnh đề"* lặp chữ (Tier 2 câu 38, người
    dùng chốt 27/10/2026). Bỏ chữ *Đề* đầu và viết hoa chữ đầu phần còn lại. Chỉ cho câu có chữ *đề*
    đứng trước; panel và các bảng vẫn in nguyên tên.

    Args:
        title: Tên đề đã lưu.

    Returns:
        Tên bỏ chữ *Đề* đầu; nguyên tên khi không mở bằng *Đề* + khoảng trắng, khi sau *Đề*
        không còn gì, hay khi *Đề* là một phần của từ (*Đề cương*, *Đề án*…).
    """
    head, _, rest = unicodedata.normalize("NFC", title).partition(" ")
    rest = rest.strip()
    if head.casefold() != "đề" or not rest:
        return title
    word = _LETTERS.match(rest)
    if word and word.group().casefold() in _DE_IS_PART_OF_THE_WORD:
        return title
    return rest[0].upper() + rest[1:]
