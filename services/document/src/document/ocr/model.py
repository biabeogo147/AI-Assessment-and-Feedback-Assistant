"""Hình dạng của một trang đã đọc, và nó là **nguồn sự thật duy nhất** cho tên nhãn khối.

`tools/ocr_bench/gold.py` import `BlockKind` từ đây chứ không khai một bản sao. Hai bản sao của
một bảng nhãn là một chỗ để lệch nhau, và nó sẽ lệch đúng vào lúc ai đó thêm một nhãn mới ở đúng
một phía -- lúc ấy bộ đo im lặng so hai thứ khác nhau và chấm engine 0 điểm cho một khối nó đọc
đúng.

Giá trị của `BlockKind` **trùng từng chữ** với nhãn PP-DocLayout phát ra, nên dựng một khối từ
đầu ra của model là một phép ép kiểu chứ không phải một bảng tra.

Ở đây **không** có message nào của `packages/contracts`, và đó là chủ ý của
`document-ocr-text-and-latex`: trong đợt này chưa có gì rời service, nên chưa có ranh giới nào để
một hợp đồng phải canh. Khi đường job per-trang được dựng ở `mongo-content-store`, hình dạng ấy mới
sinh ra -- và lúc ấy nó sinh ra từ cái cây mục lục quyết định, không phải từ cái bảng này.
"""

from enum import StrEnum
from typing import NamedTuple


class BlockKind(StrEnum):
    """Loại của một khối trên trang.

    Attributes:
        DOC_TITLE: Tiêu đề lớn của cả trang hoặc cả bài.
        PARAGRAPH_TITLE: Tiêu đề một mục hay tiểu mục.
        TEXT: Đoạn văn. Toán **nội dòng** nằm trong đây, không tách ra.
        FORMULA: Công thức đứng riêng, không nằm trong một câu văn.
        FIGURE_TITLE: Chú thích của một hình.
        IMAGE: Hình minh hoạ. Mang chữ của các dòng nằm trong nó (`document-agent-hierarchy`, D2) --
            với banner mở chương là chữ *CHƯƠNG*, còn lại phần lớn là rác nhãn hình.
        TABLE: Một bảng.
        TABLE_TITLE: Tiêu đề của một bảng.
        NUMBER: Số trang **in trong sách**. Khác số thứ tự trang của tệp PDF, và chính chỗ lệch
            ấy là thứ bước dựng mục lục cần -- đo trên 50 trang Lớp 6 tập 1 thì nó lệch đúng 1 ở
            cả 48 trang có số, còn hai trang bìa không in số nào.
        HEADER: Dòng chạy đầu trang.
        FOOTER: Dòng chạy cuối trang.
        FOOTNOTE: Chú thích chân trang.
        ASIDE_TEXT: Chữ trong một khung phụ bên lề.
    """

    DOC_TITLE = "doc_title"
    PARAGRAPH_TITLE = "paragraph_title"
    TEXT = "text"
    FORMULA = "formula"
    FIGURE_TITLE = "figure_title"
    IMAGE = "image"
    TABLE = "table"
    TABLE_TITLE = "table_title"
    NUMBER = "number"
    HEADER = "header"
    FOOTER = "footer"
    FOOTNOTE = "footnote"
    ASIDE_TEXT = "aside_text"


# Nhãn PP-DocLayout phát ra mà bảng trên không có tên riêng. Gom chúng về `TEXT` thay vì ném:
# một nhãn lạ là một khối **có chữ thật** trên trang, và bỏ nó đi là đánh rơi nội dung vì một lý
# do thuộc về bảng tra chứ không thuộc về trang.
_FALLBACK = BlockKind.TEXT


def kind_from_label(label: str) -> BlockKind:
    """Đổi nhãn PP-DocLayout thành `BlockKind`.

    Args:
        label: Chuỗi nhãn model trả về.

    Returns:
        Loại khối. Nhãn không có trong bảng ra `TEXT`.
    """
    try:
        return BlockKind(label)
    except ValueError:
        return _FALLBACK


class BBox(NamedTuple):
    """Hộp bao của một khối, theo điểm ảnh của **ảnh đã render**, không theo điểm của PDF.

    Attributes:
        left: Mép trái.
        top: Mép trên.
        right: Mép phải.
        bottom: Mép dưới.
    """

    left: int
    top: int
    right: int
    bottom: int

    @property
    def height(self) -> int:
        """Chiều cao.

        Returns:
            Số điểm ảnh. Có thể là 0 với một hộp suy biến -- model trả về được một hộp như vậy.
        """
        return max(0, self.bottom - self.top)

    @property
    def width(self) -> int:
        """Chiều rộng.

        Returns:
            Số điểm ảnh.
        """
        return max(0, self.right - self.left)


class PageBlock(NamedTuple):
    """Một khối đã đọc.

    Attributes:
        kind: Loại khối.
        box: Hộp bao trên ảnh.
        text: Chữ đọc được, chuẩn hoá NFC. Rỗng với hình và với khối chưa đọc được. Khối
            `FORMULA` cũng chỉ mang chữ OCR: công thức không được đọc lúc upload nữa.
    """

    kind: BlockKind
    box: BBox
    text: str


class PageRead(NamedTuple):
    """Một trang đã đọc xong.

    Attributes:
        page: Số thứ tự trang trong tệp PDF, đếm từ 1.
        width: Chiều rộng ảnh đã render, theo điểm ảnh.
        height: Chiều cao ảnh đã render.
        blocks: Các khối theo thứ tự đọc model trả về.
        seconds: Thời gian từng chặng, khoá là tên chặng (`render`, `layout`, `detect`, `recognize`,
            `assign`; trước 11/10/2026 còn có `formula`). Tách theo chặng chứ không một con số tổng,
            vì câu hỏi đang treo của `document-ocr-text-and-latex` là *chặng nào đắt* -- 1 561 trang
            ở nhịp đo được là nhiều giờ, và một con số tổng không nói được cắt chỗ nào.
    """

    page: int
    width: int
    height: int
    blocks: tuple[PageBlock, ...]
    seconds: dict[str, float]
