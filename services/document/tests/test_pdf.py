"""Module chạm PyMuPDF: đếm chữ, dựng ảnh, và dịch mọi tệp hỏng thành một lỗi có kiểu.

Cùng quy ước với `test_probe.py`: **không file nhị phân nào trong git.** Mọi tệp ở đây dựng ngay
lúc chạy, nên không ai thay được một fixture mà không ai biết.

`import pymupdf` trong một test là hợp lệ, và seam check nói ra điều đó: luật *"đúng một module
được import"* nói về việc chặn một event loop lúc chạy, mà một test thì sync và không có event
loop nào để chặn.
"""

import struct

import pymupdf
import pytest

from document.pdf import POINTS_PER_INCH, PdfUnreadable, open_pdf

# Khổ A4 theo điểm, đúng mặc định của `pymupdf.Document.new_page()`. Mọi phép tính DPI dưới đây
# neo vào con số này, nên nó phải là một hằng số có tên chứ không phải một số lạc trong assert.
_A4_WIDTH_POINTS = 595
_A4_HEIGHT_POINTS = 842

_PARAGRAPH = "Chương 1. Hàm số bậc hai. Học sinh nhận biết được đồ thị của hàm số bậc hai."


def _one_page_pdf() -> bytes:
    """Một PDF A4 đúng một trang, có chữ.

    Returns:
        Byte của tệp PDF.
    """
    with pymupdf.open() as book:
        book.new_page().insert_text((72, 72), _PARAGRAPH, fontsize=11)
        return book.tobytes()


def _png_size(raw: bytes) -> tuple[int, int]:
    """Đọc chiều rộng và chiều cao từ chunk IHDR của một tệp PNG.

    Tự đọc header thay vì tin `pymupdf`: phép đo này tồn tại để chứng minh `render` trả về một
    **tệp PNG thật**, nên nó không được hỏi chính thư viện vừa sinh ra tệp ấy.

    Args:
        raw: Byte của tệp PNG.

    Returns:
        Cặp (rộng, cao) theo điểm ảnh.
    """
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", "không phải một tệp PNG"
    assert raw[12:16] == b"IHDR", "chunk đầu của một PNG phải là IHDR"
    width, height = struct.unpack(">II", raw[16:24])
    return width, height


def test_text_lengths_gives_one_number_per_page_in_order() -> None:
    """Một số mỗi trang, đúng thứ tự trang, và `len()` của nó là số trang.

    Hình dạng ấy là cả lý do hàm này không trả về một tổng: luật cổng text layer đếm **trang**,
    nên nó cần biết trang nào dày trang nào mỏng, không chỉ cần tổng.
    """
    with pymupdf.open() as book:
        book.new_page().insert_text((72, 72), _PARAGRAPH, fontsize=11)
        book.new_page()
        book.new_page().insert_text((72, 72), "ngắn", fontsize=11)
        raw = book.tobytes()

    with open_pdf(raw) as pages:
        lengths = pages.text_lengths()

    assert len(lengths) == 3
    assert lengths[0] > 50
    assert lengths[1] == 0
    assert lengths[2] == len("ngắn")


def test_render_turns_a_page_into_a_real_png_sized_by_dpi() -> None:
    """Ảnh ra đúng khổ trang nhân hệ số DPI, và nó là một tệp PNG thật.

    Ở 72 DPI thì một điểm của PDF thành đúng một điểm ảnh, nên kích thước ảnh **là** khổ trang
    theo điểm. Đó là phép kiểm trực tiếp nhất cho việc `dpi` được hiểu đúng là *điểm ảnh mỗi
    inch* chứ không phải một hệ số phóng.
    """
    with open_pdf(_one_page_pdf()) as pages:
        shot = pages.render(0, dpi=POINTS_PER_INCH)

    width, height = _png_size(shot)
    assert abs(width - _A4_WIDTH_POINTS) <= 1
    assert abs(height - _A4_HEIGHT_POINTS) <= 1


def test_doubling_the_dpi_doubles_both_sides() -> None:
    """Và `dpi` phải tỉ lệ thuận, không chỉ "lớn hơn".

    Cặp với test trên. Một bản cài `dpi` thành một hệ số phóng cố định sẽ qua được test kia --
    ở 72 nó vẫn đúng -- và đỏ ở đây. Sai một điểm ảnh là phép làm tròn của `pymupdf`, nên biên
    độ cho phép là 1 chứ không phải 0.
    """
    with open_pdf(_one_page_pdf()) as pages:
        small = _png_size(pages.render(0, dpi=72))
        large = _png_size(pages.render(0, dpi=144))

    assert abs(large[0] - small[0] * 2) <= 1
    assert abs(large[1] - small[1] * 2) <= 1


def test_a_page_outside_the_file_is_the_callers_mistake() -> None:
    """`IndexError`, **không** `PdfUnreadable`: tệp không có lỗi gì, người gọi mới có.

    Gộp hai cái lại là làm một lỗi lập trình trông như một tệp xấu, và lúc ấy đường xử của nó
    trở thành *"báo cho giáo viên rằng sách của họ hỏng"* -- sai hẳn chỗ.
    """
    with open_pdf(_one_page_pdf()) as pages, pytest.raises(IndexError):
        pages.render(7, dpi=72)


def test_opening_something_that_is_not_a_pdf_raises_the_typed_error() -> None:
    """Mọi loại exception của `pymupdf` phải ra một lỗi duy nhất có kiểu.

    Đây là lý do module này tồn tại chứ không phải một tiện nghi: thiếu nó thì người gọi phải
    `except Exception`, và một `except Exception` nuốt luôn cả lỗi lập trình của chính nó.
    """
    with pytest.raises(PdfUnreadable), open_pdf(b"khong phai pdf gi ca"):
        pass


def test_a_pdf_with_no_pages_opens_and_counts_zero() -> None:
    """Một PDF không trang nào **mở được**, và `len()` trả `0`.

    Phán quyết cho ca ấy thuộc `probe.py`; ở đây nó chỉ không được là một exception. Tệp dưới
    phải viết bằng tay vì `tobytes()` từ chối một tài liệu rỗng (*"cannot save with zero
    pages"*).
    """
    empty = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
        b"trailer<</Root 1 0 R>>\n"
    )
    with open_pdf(empty) as pages:
        assert len(pages) == 0
        assert pages.text_lengths() == []


def _pdf_whose_page_tree_lies() -> bytes:
    """Một PDF mà `/Pages` khai `Count 5` trong khi `Kids` rỗng.

    Không phải một ca bày ra: 14 cuốn SGK trong `data/` do `3-Heights PDF Optimization Shell` và
    `Acrobat Image Conversion Plug-in` sinh ra, và một page tree lệch `Count` là đúng hình dạng
    một dây chuyền máy quét để lại. `pymupdf` mở được tệp này và chỉ ném lúc ai đó hỏi số trang.

    Returns:
        Byte của tệp PDF.
    """
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[]/Count 5>>endobj\n"
        b"trailer<</Root 1 0 R>>\n"
    )


def test_a_lying_page_tree_becomes_the_typed_error_not_a_raw_one() -> None:
    """Lưới cho một hồi quy thật, tìm ra ngày 10/10/2026.

    Bản đầu của `text_lengths` gọi `len(self)` trong chính `except` của nó -- tức gọi lại đúng
    phép toán vừa hỏng. Exception mới thay chỗ exception cũ, `PdfUnreadable` không bao giờ được
    dựng, `probe()` ném ra ngoài, và chip đứng mãi ở *đang xử lý*: đúng thứ ADR-27 gọi là một
    chip nói dối, qua hết lượt thử lại của arq.
    """
    raw = _pdf_whose_page_tree_lies()
    with open_pdf(raw) as pages, pytest.raises(PdfUnreadable):
        len(pages)
    with open_pdf(raw) as pages, pytest.raises(PdfUnreadable):
        pages.text_lengths()


def _escaped_pages():
    """Một `PdfPages` còn sống sau khi `open_pdf` đã đóng tài liệu của nó.

    Docstring của `PdfPages` nói thẳng là chuyện này xảy ra được (*"lớp này không tự đóng"*),
    nên nó phải có một hành vi được định nghĩa thay vì một `ValueError` của `pymupdf`.

    Returns:
        Một `PdfPages` trỏ vào một tài liệu đã đóng.
    """
    with open_pdf(_one_page_pdf()) as pages:
        return pages


def test_using_pages_after_the_file_closed_is_the_typed_error() -> None:
    """Và nó cũng là lưới duy nhất canh việc `open_pdf` **có đóng** tài liệu.

    Bỏ `book.close()` đi thì tài liệu còn sống, ba lời gọi dưới chạy ngon lành, và test này đỏ.
    Không có nó thì hành vi duy nhất mà `open_pdf` tồn tại để làm không được canh bởi gì cả.
    """
    escaped = _escaped_pages()
    with pytest.raises(PdfUnreadable):
        len(escaped)
    with pytest.raises(PdfUnreadable):
        escaped.text_lengths()
    with pytest.raises(PdfUnreadable):
        escaped.render(0, dpi=72)


def test_a_negative_page_is_refused_instead_of_quietly_meaning_the_last_one() -> None:
    """`pymupdf` nhận `book[-1]` và trả về trang cuối, nên không chặn thì một lỗi đếm im lặng.

    Hình dạng tệ nhất của một lỗi: nó không kêu, nó chỉ trả về **đúng một trang khác**.
    """
    with open_pdf(_one_page_pdf()) as pages, pytest.raises(IndexError):
        pages.render(-1, dpi=72)


def test_rendering_two_different_pages_gives_two_different_images() -> None:
    """`index` phải thật sự chọn trang, không phải luôn luôn dựng trang đầu.

    Mọi test render khác ở trên đều dùng `index=0`, nên một bản cài bỏ qua `index` hoàn toàn vẫn
    qua được hết chúng.
    """
    with pymupdf.open() as book:
        book.new_page().insert_text((72, 72), "Trang mot", fontsize=40)
        book.new_page().insert_text((72, 72), "Trang hai", fontsize=40)
        raw = book.tobytes()

    with open_pdf(raw) as pages:
        assert pages.render(0, dpi=72) != pages.render(1, dpi=72)


def test_a_dpi_that_is_not_positive_is_refused() -> None:
    """`dpi=0` và `dpi` âm **không kêu** ở `pymupdf`, chúng chỉ trả về một ảnh sai.

    Đo ngày 10/10/2026: `get_pixmap(dpi=0)` ra một ảnh cỡ mặc định, `dpi=-10` ra một ảnh 531
    byte. Cùng loại lỗi với số trang âm -- một thứ sai mà trông như một thứ đúng -- nên nó cũng
    phải kêu ở biên chứ không đi tiếp vào engine OCR.
    """
    with open_pdf(_one_page_pdf()) as pages:
        for dpi in (0, -10):
            with pytest.raises(ValueError, match="dpi must be positive"):
                pages.render(0, dpi=dpi)


def test_a_dpi_too_large_to_fit_in_memory_is_the_typed_error() -> None:
    """Nhánh dịch lỗi của `render`: trang có đó, tệp lành, nhưng ảnh không dựng nổi.

    Đây là lưới duy nhất cho nhánh ấy, và nó cần một ca thật chứ không phải một mock -- đo ngày
    10/10/2026, 20 000 DPI làm MuPDF từ chối với *"Overly large image"*. Không có test này thì
    xoá cả `try/except` của `render` đi cũng không gì đỏ.
    """
    with open_pdf(_one_page_pdf()) as pages, pytest.raises(PdfUnreadable, match="Could not render"):
        pages.render(0, dpi=20000)


def test_page_text_gives_each_block_with_a_box_inside_the_page() -> None:
    """Text layer thành từng khối có hộp, theo thứ tự trong trang -- bản thô của một PDF có chữ.

    Hộp phải nằm trong trang và theo **điểm** của trang (không theo điểm ảnh):
    `document-agent-hierarchy` dựa vào `width`/`height` của bản thô để biết hộp đo bằng hệ nào.
    """
    with pymupdf.open() as book:
        page = book.new_page()
        page.insert_text((72, 72), "first block", fontsize=11)
        page.insert_text((72, 400), "second block", fontsize=11)
        book.new_page()
        raw = book.tobytes()

    with open_pdf(raw) as pages:
        first = pages.page_text(0)
        blank = pages.page_text(1)

    assert (first.width, first.height) == (_A4_WIDTH_POINTS, _A4_HEIGHT_POINTS)
    assert [block.text.strip() for block in first.blocks] == ["first block", "second block"]
    for block in first.blocks:
        left, top, right, bottom = block.box
        assert 0 <= left < right <= first.width
        assert 0 <= top < bottom <= first.height
    assert blank.blocks == []


def test_page_text_outside_the_file_is_the_callers_mistake() -> None:
    """Cùng luật với `render`: số trang sai là lỗi lập trình, không phải một tệp xấu."""
    with open_pdf(_one_page_pdf()) as pages:
        with pytest.raises(IndexError):
            pages.page_text(1)
        with pytest.raises(IndexError):
            pages.page_text(-1)


def test_page_text_leaves_pictures_out() -> None:
    """Hình trên trang không thành khối chữ: `page_text` dựa vào cờ mặc định của `pymupdf` cho
    điều này, và test này là chỗ duy nhất nói ra nếu một bản `pymupdf` mới đổi mặc định ấy.
    """
    with pymupdf.open() as book:
        page = book.new_page()
        page.insert_text((72, 72), "caption", fontsize=11)
        dots = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10))
        page.insert_image(pymupdf.Rect(100, 400, 200, 500), pixmap=dots)
        raw = book.tobytes()

    with open_pdf(raw) as pages:
        found = pages.page_text(0)

    assert [block.text.strip() for block in found.blocks] == ["caption"]
