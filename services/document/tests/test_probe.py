"""Cổng text layer, đo trên những tệp dựng ngay lúc chạy.

**Không có file nhị phân nào trong git.** Đo ngày 08/10/2026 rằng `pymupdf` tự dựng được cả hai
đầu của thang: một trang `insert_text` cho 16 ký tự; render chính trang ấy thành pixmap rồi
`insert_image` vào một PDF mới cho **0** ký tự. Nên một bản scan không cần ai đi tìm, và test
không phụ thuộc vào một tệp mà người sau có thể thay mà không ai biết.
"""

import pymupdf
import pytest

from contracts import DocumentState
from document.probe import probe

# Chữ đủ dài để vượt ngưỡng 100 ký tự mỗi trang mà không phải đếm bằng tay.
_PARAGRAPH = (
    "Chương 1. Mệnh đề và tập hợp. Trong bài này học sinh nhận biết được mệnh đề, "
    "mệnh đề chứa biến, và xác định được tính đúng sai của một mệnh đề."
)


def _pdf_with_text(pages: int, text_on: int) -> bytes:
    """Một PDF `pages` trang, trong đó `text_on` trang đầu có chữ, còn lại trắng.

    Args:
        pages: Tổng số trang.
        text_on: Bao nhiêu trang đầu mang chữ.

    Returns:
        Byte của tệp PDF.
    """
    with pymupdf.open() as book:
        for ordinal in range(pages):
            page = book.new_page()
            if ordinal < text_on:
                page.insert_text((72, 72), _PARAGRAPH, fontsize=11)
        return book.tobytes()


def _pdf_that_is_a_scan() -> bytes:
    """Một PDF chỉ có ảnh: đúng hình dạng của một cuốn sách chụp lại.

    Dựng bằng cách render một trang có chữ thành pixmap rồi nhúng pixmap ấy vào một trang mới.
    Chữ biến thành điểm ảnh, nên `get_text()` trả về rỗng -- đo được là **0** ký tự.

    Returns:
        Byte của tệp PDF chỉ chứa ảnh.
    """
    with pymupdf.open(stream=_pdf_with_text(1, 1), filetype="pdf") as source:
        shot = source[0].get_pixmap(dpi=72)
    with pymupdf.open() as book:
        page = book.new_page(width=shot.width, height=shot.height)
        page.insert_image(pymupdf.Rect(0, 0, shot.width, shot.height), pixmap=shot)
        return book.tobytes()


def test_a_pdf_with_text_is_ready_and_counts_its_pages() -> None:
    """Đường thường: có chữ thì dùng được, và số trang là con số thật của tệp."""
    found = probe(_pdf_with_text(5, 5), "sach.pdf")
    assert found.state is DocumentState.READY
    assert found.page_count == 5
    assert found.fault == ""


def test_a_scanned_pdf_has_no_text_layer() -> None:
    """Một cuốn sách chụp lại không dùng được, và lý do nói bằng lời giáo viên hiểu.

    ADR-27: *"một tệp không đọc được chữ thì không bao giờ dùng được"*, và nó phải biết điều ấy
    trong vài giây chứ không phải ba tuần sau lúc đem ra dùng.
    """
    found = probe(_pdf_that_is_a_scan(), "sgk-chup-lai.pdf")
    assert found.state is DocumentState.NO_TEXT_LAYER
    assert "scan" in found.fault


def test_one_thick_page_among_nineteen_blank_ones_is_not_readable() -> None:
    """Ca nghịch của luật ngưỡng, và lý do luật ấy đếm **trang** chứ không cộng ký tự.

    Một cuốn scan kèm đúng một trang mục lục dày chữ qua được luật *"trung bình ký tự mỗi
    trang"* trong khi 19 trang kia không đọc được chữ nào. 1/20 = 5%, dưới ngưỡng 10%.
    """
    found = probe(_pdf_with_text(20, 1), "mot-trang-muc-luc.pdf")
    assert found.state is DocumentState.NO_TEXT_LAYER
    assert found.page_count == 20


def test_two_pages_of_text_in_twenty_are_enough() -> None:
    """Và ngưỡng phải nhận một tài liệu chỉ vừa đủ: 2/20 = 10%.

    Cặp với test trên, hai cái kẹp đúng con số `_MIN_READABLE_PAGE_RATIO` giữa chúng. Đổi hằng
    số theo chiều nào thì một trong hai đỏ.
    """
    assert probe(_pdf_with_text(20, 2), "vua-du.pdf").state is DocumentState.READY


def test_a_broken_pdf_fails_instead_of_raising() -> None:
    """Một tệp hỏng là một kết quả, không phải một exception.

    `probe` không được ném: người gọi phải có một `DocumentProbed` để gửi đi trong mọi trường
    hợp, nếu không chip đứng mãi ở *đang xử lý*. Và trạng thái là `FAILED`, không phải
    `NO_TEXT_LAYER` -- tệp có thể vẫn tốt, chỉ là lần này không mở được, nên thử lại là việc có
    nghĩa.
    """
    found = probe(b"khong phai pdf gi ca", "rac.pdf")
    assert found.state is DocumentState.FAILED
    assert found.page_count is None


def test_a_pdf_with_no_pages_is_a_verdict_not_a_failure() -> None:
    """Một PDF không trang nào mở được nhưng không bao giờ dùng được, nên nó là phán quyết.

    Nhánh này **phải** có test, vì không có nó thì `with_text / pages` chia cho không. Và nó
    không dựng được bằng `pymupdf`: `tobytes()` từ chối một tài liệu rỗng
    (*"cannot save with zero pages"*), nên tệp phải viết bằng tay. Đo rồi: `pymupdf` mở được
    bốn dòng dưới và báo `page_count == 0`.
    """
    empty = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
        b"trailer<</Root 1 0 R>>\n"
    )
    found = probe(empty, "rong.pdf")
    assert found.state is DocumentState.NO_TEXT_LAYER
    assert found.page_count == 0


@pytest.mark.parametrize("name", ["ghi-chu.txt", "giao-an.md"])
def test_plain_text_is_ready_and_claims_no_page_count(name: str) -> None:
    """Văn bản thuần không có trang, nên `page_count` là `None`, không phải `0`.

    Một số `0` hợp lệ về kiểu và sai về nghĩa: chip sẽ in "0 trang", và giáo viên sẽ tin.
    """
    found = probe(_PARAGRAPH.encode("utf-8"), name)
    assert found.state is DocumentState.READY
    assert found.page_count is None


def test_a_text_file_of_only_whitespace_has_no_text() -> None:
    """Một tệp chỉ có khoảng trắng là một lần chọn nhầm, không phải một tài liệu."""
    assert probe(b"   \n\t\r\n  ", "trong.txt").state is DocumentState.NO_TEXT_LAYER


def test_a_text_file_that_is_not_utf8_still_counts_as_having_text() -> None:
    """Sai bảng mã vẫn là **có chữ**, và đó là câu hỏi duy nhất ở vòng này.

    Đoán bảng mã thuộc bước cắt đoạn, nơi nội dung thật sự được dùng. Từ chối ở đây là từ chối
    một tài liệu vì một lý do mà vòng này không có quyền phán.
    """
    # cp1252, không phải UTF-8: `\xe8` một mình là một byte không hợp lệ trong UTF-8, nên
    # `errors="replace"` biến nó thành một ký tự thay thế và phần còn lại vẫn là chữ.
    found = probe(b"Chuong mot, bai tap v\xe8 nha cho ca lop muoi hai A", "cu.txt")
    assert found.state is DocumentState.READY


def test_an_extension_nobody_reads_fails_loudly_in_the_result() -> None:
    """Hai lớp lọc lệch nhau phải thành một câu trả lời, không thành một exception.

    BE lọc theo đuôi tệp trước khi cất, nên tới được đây là nó và module này đã lệch. Giáo viên
    vẫn cần một câu trả lời cho tệp của họ.
    """
    found = probe(b"PK\x03\x04", "bai-giang.docx")
    assert found.state is DocumentState.FAILED


def _pdf_with_a_running_header(pages: int) -> bytes:
    """Một PDF mà **mọi** trang chỉ có một dòng ngắn, như số trang hay tên chương.

    Đúng hình dạng của một bản scan có lớp OCR mỏng: chữ có mặt ở mọi trang, nhưng không trang
    nào mang nội dung.

    Args:
        pages: Số trang.

    Returns:
        Byte của tệp PDF.
    """
    with pymupdf.open() as book:
        for ordinal in range(pages):
            book.new_page().insert_text((72, 40), f"Trang {ordinal + 1} — Giải tích", fontsize=9)
        return book.tobytes()


def test_a_scan_with_only_page_numbers_on_every_page_is_not_readable() -> None:
    """Chữ ở **mọi** trang vẫn không phải một tài liệu đọc được.

    Đây là test duy nhất chạm tới `_MIN_CHARS_PER_PAGE`, và nó tồn tại vì một phép đột biến tìm
    ra chỗ trống: hạ hằng số ấy từ 100 về 1 chạy qua toàn bộ suite mà không một test nào đỏ.
    Lý do là mấy fixture kia để trang trắng mang **0** ký tự, nên không ngưỡng nào giữa 1 và 100
    phân biệt được chúng.

    Tệp dưới lấp đúng khoảng ấy: mỗi trang khoảng hai mươi ký tự — trên 1, dưới 100. Ở ngưỡng
    100 thì 0/20 trang có chữ và tệp bị từ chối, đúng; ở ngưỡng 1 thì 19/20 và nó qua cổng, sai.

    Và nó là ca thật, không phải một ca bày ra cho test: một bản SGK chụp lại có lớp OCR mỏng in
    được số trang mà không đọc được một đoạn nào.
    """
    found = probe(_pdf_with_a_running_header(20), "scan-co-so-trang.pdf")
    assert found.state is DocumentState.NO_TEXT_LAYER
    assert found.page_count == 20
