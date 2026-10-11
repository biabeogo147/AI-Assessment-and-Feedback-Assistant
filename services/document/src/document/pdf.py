"""Mọi lời gọi PyMuPDF của service này, gom vào một module.

Module **duy nhất** được import `pymupdf`, và `tools/check_contract.py` canh đúng điều đó. Lý do
không phải gọn gàng: PyMuPDF là sync và CPU-bound, còn arq chạy tới `max_jobs` job đồng thời
trên một event loop, nên một lời gọi quên `asyncio.to_thread` chặn cả những job kia -- và nó
không ném gì cả, chỉ làm mọi thứ chậm đi trong lúc ai đó tải một cuốn sách lên. Gom vào một
module biến luật *"nhớ bọc thread"* thành luật *"nhớ đừng import"*, và luật thứ hai thì grep
được.

Trước ngày 10/10/2026 chỗ này là `probe.py`, vì nó là người duy nhất cần đọc một tệp. Đường OCR
cần thêm một việc nữa -- **dựng ảnh một trang** -- và nhét việc ấy vào `probe.py` là bắt một
module chính sách gánh một phép biến đổi. Nên hai thứ tách: ở đây là **cách** chạm tệp, ở
`probe.py` là **luật** phán quyết một tệp dùng được hay không.

Một quy ước nữa, và nó là lý do module này có `PdfUnreadable`: `pymupdf` ném nhiều loại khác
nhau cho một tệp hỏng, và không loại nào đáng đoán trước. Việc dịch đống ấy thành **một** lỗi có
kiểu thuộc về đây, để người gọi không phải `except Exception` -- thứ sẽ nuốt cả lỗi lập trình
của chính nó.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import NamedTuple

import pymupdf

logger = logging.getLogger(__name__)

# Một điểm (point) của PDF là 1/72 inch. Hằng số này sống ở đây vì nó là đơn vị của **tệp**,
# không phải một lựa chọn của ta: `dpi` mà người gọi xin được đổi sang hệ số phóng bằng nó.
POINTS_PER_INCH = 72


class TextBlock(NamedTuple):
    """Một khối chữ của text layer.

    Attributes:
        box: Hộp bao `(trái, trên, phải, dưới)` theo điểm của trang.
        text: Chữ của khối, như PyMuPDF trả -- chưa chuẩn hoá, có thể còn xuống dòng bên trong.
    """

    box: tuple[float, float, float, float]
    text: str


class PageText(NamedTuple):
    """Chữ của một trang, kèm hệ toạ độ của các hộp.

    Attributes:
        width: Bề rộng trang, theo điểm.
        height: Bề cao trang, theo điểm.
        blocks: Các khối chữ, theo thứ tự trong content stream của trang.
    """

    width: float
    height: float
    blocks: list[TextBlock]


class PdfUnreadable(RuntimeError):
    """Không mở hoặc không đọc nổi một PDF.

    Tách khỏi exception thô của `pymupdf` để người gọi không phải import `pymupdf` chỉ để bắt
    lỗi -- đó chính là thứ seam check cấm. Cùng hình dạng với `StorageUnavailable` của
    `storage.py`.
    """


class PdfPages:
    """Các trang của một PDF đã mở. Lấy qua `open_pdf`, không dựng trực tiếp.

    Mở một lần rồi dùng nhiều lần là cả lý do lớp này tồn tại: đường OCR render từng trang của
    một cuốn 400 trang, và mở lại tệp cho mỗi trang là trả giá phân tích cú pháp 400 lần.

    Attributes:
        _book: Tài liệu `pymupdf` đang mở. `open_pdf` đóng nó; lớp này không tự đóng, vì một
            đối tượng vừa cho mượn vừa thu hồi thì không ai biết lúc nào nó còn sống.
    """

    def __init__(self, book: pymupdf.Document):
        """Bọc một tài liệu đã mở.

        Args:
            book: Tài liệu `pymupdf`, do `open_pdf` mở và đóng.
        """
        self._book = book

    def __len__(self) -> int:
        """Số trang.

        Dịch lỗi **ở đây** chứ không để `pymupdf` ném thô, vì đọc số trang không phải một phép
        tra rẻ và an toàn như cái tên `len()` gợi ra: nó phân tích page tree, nên nó ném với một
        tệp mà `/Pages` khai `Count` lệch với `Kids` -- đúng hình dạng một dây chuyền máy quét
        sinh ra -- và nó ném `ValueError` trên một tài liệu đã đóng.

        Returns:
            Số trang của tệp. `0` là một con số hợp lệ -- một PDF không trang nào vẫn mở được.

        Raises:
            PdfUnreadable: Khi page tree hỏng, hoặc tài liệu đã bị đóng.
        """
        try:
            return self._book.page_count
        except Exception as exc:
            raise PdfUnreadable(f"Could not count pages: {exc}") from exc

    def text_lengths(self) -> list[int]:
        """Đếm ký tự không-trắng của **từng** trang.

        Trả về một danh sách chứ không phải một tổng, vì luật cổng text layer đếm **trang** chứ
        không cộng ký tự: một cuốn scan kèm đúng một trang mục lục dày chữ phải bị từ chối, và
        một con số tổng thì không phân biệt được ca ấy. Xem `probe.py`.

        Returns:
            Một số cho mỗi trang, theo đúng thứ tự trang. `len()` của nó là số trang.

        Raises:
            PdfUnreadable: Khi tệp hỏng tới mức không đọc nổi một trang nào đó.
        """
        try:
            return [len(page.get_text().strip()) for page in self._book]
        except Exception as exc:
            # **Không** gọi `len(self)` ở đây. Đó chính là phép toán vừa hỏng, nên nó ném lần
            # nữa, exception mới thay chỗ exception cũ, và `PdfUnreadable` không bao giờ được
            # dựng -- `probe()` ném ra ngoài và chip đứng mãi ở *đang xử lý*. Đã xảy ra thật
            # ngày 10/10/2026, và review bắt được; bản vá là dòng log này không chạm `_book`.
            logger.exception("could not read the page text of a pdf")
            raise PdfUnreadable(f"Could not read page text: {exc}") from exc

    def page_text(self, index: int) -> PageText:
        """Đọc text layer của một trang thành từng khối có hộp.

        Đây là bản thô của một PDF có chữ (plan 3b): cùng hình dạng *khối + hộp* với đường OCR,
        chỉ khác là không ai gán nhãn khối. Thứ tự là thứ tự trong content stream, **không** sắp
        lại theo toạ độ: với PDF sinh từ trình soạn thảo, đó là thứ tự đọc; còn sắp theo trục dọc
        thì cắt ngang một trang hai cột.

        Không lọc khối ảnh: với cờ mặc định, `get_text("blocks")` không trả chúng (đo 11/10/2026,
        `test_page_text_leaves_pictures_out` canh). Thêm cờ ảnh vào đây thì chữ của khối ảnh là
        `"<image: ...>"` -- rác trông như chữ.

        Args:
            index: Số thứ tự trang, đếm từ 0.

        Returns:
            Kích thước trang và các khối chữ. Một trang không chữ cho danh sách rỗng.

        Raises:
            IndexError: Khi `index` nằm ngoài số trang -- lỗi của người gọi, cùng lý do như
                `render`.
            PdfUnreadable: Khi tệp hỏng hoặc tài liệu đã đóng.
        """
        pages = len(self)
        if not 0 <= index < pages:
            raise IndexError(f"page {index} is outside a pdf of {pages} pages")
        try:
            page = self._book[index]
            found = page.get_text("blocks")
            width, height = page.rect.width, page.rect.height
        except Exception as exc:
            logger.exception("could not read the text blocks of page %s", index)
            raise PdfUnreadable(f"Could not read the text of page {index}: {exc}") from exc
        blocks = [
            TextBlock((left, top, right, bottom), text)
            for left, top, right, bottom, text, _number, _kind in found
        ]
        return PageText(width, height, blocks)

    def render(self, index: int, dpi: int) -> bytes:
        """Dựng một trang thành ảnh PNG.

        Đây là đầu vào duy nhất của đường OCR: 14 cuốn sách giáo khoa trong `data/` không có một
        ký tự nào, nên `text_lengths` trả toàn số 0 và chữ chỉ còn một đường để ra -- qua điểm
        ảnh.

        Args:
            index: Số thứ tự trang, đếm từ 0.
            dpi: Số điểm ảnh mỗi inch. Bản scan trong `data/` ở khoảng 144 DPI, nên xin cao hơn
                mức ấy chỉ phóng to điểm ảnh có sẵn chứ không thêm chi tiết nào.

        Returns:
            Byte của một tệp PNG.

        Raises:
            IndexError: Khi `index` nằm ngoài số trang. Đây là lỗi của người gọi, không phải của
                tệp, nên nó **không** bị dịch thành `PdfUnreadable` -- gộp hai cái lại là làm
                một lỗi lập trình trông như một tệp xấu. Số âm cũng vào đây: `pymupdf` nhận
                `book[-1]` và trả về trang cuối, nên không chặn thì một lỗi đếm ngược âm thầm
                dựng **đúng một trang khác** thay vì kêu lên.
            ValueError: Khi `dpi` không dương. Cùng loại lỗi với số trang âm, và đo được ngày
                10/10/2026: `get_pixmap(dpi=0)` trả về một ảnh ở cỡ mặc định còn `dpi=-10` trả
                về một ảnh 531 byte -- cả hai **không kêu gì**, chúng chỉ trả về một thứ sai mà
                trông như một thứ đúng.
            PdfUnreadable: Khi tệp hỏng, tài liệu đã đóng, hoặc trang có đó nhưng không dựng
                được thành ảnh -- ví dụ `dpi` lớn tới mức MuPDF từ chối cấp bộ nhớ.
        """
        if dpi <= 0:
            raise ValueError(f"dpi must be positive, got {dpi}")
        pages = len(self)
        if not 0 <= index < pages:
            raise IndexError(f"page {index} is outside a pdf of {pages} pages")
        try:
            shot = self._book[index].get_pixmap(dpi=dpi)
            return shot.tobytes("png")
        except Exception as exc:
            logger.exception("could not render page %s at %s dpi", index, dpi)
            raise PdfUnreadable(f"Could not render page {index}: {exc}") from exc


@contextmanager
def open_pdf(raw: bytes) -> Iterator[PdfPages]:
    """Mở một PDF từ byte, và đóng nó khi xong.

    Args:
        raw: Toàn bộ byte của tệp.

    Yields:
        Các trang của tệp.

    Raises:
        PdfUnreadable: Khi không mở được. Một PDF **không trang nào** thì mở được bình thường và
            `len()` trả `0`; phán quyết cho ca ấy thuộc `probe.py`, không thuộc đây.
    """
    try:
        book = pymupdf.open(stream=raw, filetype="pdf")
    except Exception as exc:
        logger.exception("could not open a pdf of %s bytes", len(raw))
        raise PdfUnreadable(f"Could not open the pdf: {exc}") from exc
    try:
        yield PdfPages(book)
    finally:
        book.close()
