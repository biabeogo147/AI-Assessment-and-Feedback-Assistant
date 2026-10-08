"""Mở một tệp ra xem có đọc được chữ không, và đếm số trang.

Module **duy nhất** được import `pymupdf`, và `tools/check_contract.py` canh đúng điều đó. Lý do
không phải gọn gàng: PyMuPDF là sync và CPU-bound, còn arq chạy tới `max_jobs` job đồng thời
trên một event loop, nên một lời gọi quên `asyncio.to_thread` chặn cả những job kia -- và nó
không ném gì cả, chỉ làm mọi thứ chậm đi trong lúc ai đó tải một cuốn sách lên. Gom vào một
module biến luật *"nhớ bọc thread"* thành luật *"nhớ đừng import"*, và luật thứ hai thì grep
được.

Không có lời gọi model nào ở đây và sẽ không bao giờ có. Đây là phép đếm, không phải phép đọc
hiểu: việc cắt chương và phân loại đoạn thuộc plan sau.
"""

import logging
from typing import NamedTuple

import pymupdf

from contracts import DocumentState

logger = logging.getLogger(__name__)

# Một trang được coi là **có chữ** khi nó mang từ bấy nhiêu ký tự trở lên.
#
# Vì sao 100 mà không phải 1: trang mỏng nhất của một PDF chữ thật -- `docs/report/report.pdf`,
# 29 trang tiếng Việt -- chỉ có **39** ký tự, và đó là một trang bìa. Một luật "mọi trang phải
# có chữ" sẽ từ chối một tài liệu đọc được hoàn toàn. Ngưỡng 100 nằm trên mức một dòng tiêu đề
# và dưới mức một đoạn văn.
_MIN_CHARS_PER_PAGE = 100

# Tài liệu được coi là **đọc được chữ** khi từ bấy nhiêu phần trang trở lên có chữ.
#
# Đo ngày 08/10/2026, PyMuPDF 1.28.2, trên hai đầu của thang:
#
#     docs/report/report.pdf (PDF chữ thật)     29 trang   32 455 ký tự   27/29 trang = 93%
#     PDF scan (render trang ấy thành ảnh)       1 trang        0 ký tự    0/1  trang =  0%
#
# Khoảng cách 93% <-> 0% rộng gấp chín lần ngưỡng, nên 10% không phải một chỗ cân bằng mong manh.
#
# Hai luật khác đã bị loại, và lý do đáng giữ lại:
#
# - *"có ít nhất một ký tự"* vỡ vì một bản scan có một trang bìa chữ, hoặc một watermark, là có
#   ít nhất một ký tự.
# - *"trung bình ký tự mỗi trang"* vỡ ở một ca rất thật: một cuốn 400 trang scan kèm **một**
#   trang mục lục 50 000 ký tự cho trung bình 125 ký tự/trang và **qua cổng**, trong khi 399
#   trang kia không đọc được chữ nào. Luật này đếm **trang**, không cộng ký tự, nên nó không vỡ
#   theo hình dạng ấy.
#
# Cái **chưa** đo, nói ra để lần sau đừng ai tưởng con số này đã được cân ở mọi chỗ: một bản SGK
# scan **có lớp OCR mỏng**. Đó là ca duy nhất nằm giữa hai dòng trên, và nếu con số phải sửa thì
# nó sửa vì ca ấy.
_MIN_READABLE_PAGE_RATIO = 0.10

# Chữ là toàn bộ tệp, nên không có bài toán text layer và cũng không có khái niệm trang.
_PLAIN_TEXT_SUFFIXES = (".txt", ".md")


class Finding(NamedTuple):
    """Những gì đọc được từ một tệp.

    Attributes:
        state: Phán quyết. Không bao giờ là `PROCESSING` -- hàm này chỉ trả về khi đã xong.
        page_count: Số trang, hoặc `None` khi con số **không tồn tại** (tệp văn bản thuần),
            không phải khi nó chưa biết.
        fault: Một câu tiếng Việt cho giáo viên đọc, vì nó đi thẳng lên chip. Rỗng khi `READY`.
    """

    state: DocumentState
    page_count: int | None
    fault: str


def probe(raw: bytes, filename: str) -> Finding:
    """Đọc một tệp và nói nó dùng được hay không.

    Hàm **thuần** và **sync**: không mạng, không database, không trạng thái toàn cục. Người gọi
    có trách nhiệm đặt nó vào một thread (`asyncio.to_thread`), vì nó CPU-bound.

    Không bao giờ ném. Một tệp hỏng là một kết quả, không phải một lỗi của hệ thống: người gọi
    phải có một `DocumentProbed` để gửi đi trong mọi trường hợp, nếu không chip đứng mãi ở *đang
    xử lý*.

    Args:
        raw: Toàn bộ byte của tệp.
        filename: Tên tệp. Phần mở rộng quyết định đường đọc.

    Returns:
        Phán quyết, số trang nếu có, và lý do nếu không dùng được.
    """
    lowered = filename.lower()
    if lowered.endswith(_PLAIN_TEXT_SUFFIXES):
        return _probe_plain_text(raw)
    if lowered.endswith(".pdf"):
        return _probe_pdf(raw)
    # BE đã lọc theo đuôi tệp trước khi cất, nên tới được đây là hai lớp lọc đã lệch nhau. Nói ra
    # bằng một phán quyết chứ không bằng một exception: giáo viên vẫn cần một câu trả lời.
    logger.warning("no reader for %s", filename)
    return Finding(DocumentState.FAILED, None, "Chưa đọc được loại tệp này.")


def _probe_plain_text(raw: bytes) -> Finding:
    """Một tệp văn bản thuần: chữ **là** toàn bộ tệp.

    Giải mã với `errors="replace"` thay vì đoán bảng mã. Một tệp không phải UTF-8 vẫn ra chữ --
    sai dấu, nhưng đủ để biết nó **có** chữ, và đó là câu hỏi duy nhất ở vòng này. Đoán bảng mã
    là việc của bước cắt đoạn, nơi nội dung thật sự được dùng.

    Args:
        raw: Toàn bộ byte của tệp.

    Returns:
        `READY` khi có ký tự không-trắng, `page_count` luôn là `None`.
    """
    if not raw.decode("utf-8", errors="replace").strip():
        return Finding(DocumentState.NO_TEXT_LAYER, None, "Tệp này không có chữ nào.")
    return Finding(DocumentState.READY, None, "")


def _probe_pdf(raw: bytes) -> Finding:
    """Một PDF: đếm xem bao nhiêu trang thật sự mang chữ.

    Args:
        raw: Toàn bộ byte của tệp.

    Returns:
        `READY` kèm số trang khi đủ phần trăm trang có chữ; `NO_TEXT_LAYER` khi không;
        `FAILED` khi không mở được tệp.
    """
    try:
        with pymupdf.open(stream=raw, filetype="pdf") as book:
            pages = book.page_count
            with_text = sum(
                1 for page in book if len(page.get_text().strip()) >= _MIN_CHARS_PER_PAGE
            )
    except Exception:
        # `pymupdf` ném nhiều loại khác nhau cho một tệp hỏng, và không loại nào đáng đoán trước.
        # Bắt rộng rồi dịch sang một phán quyết là đúng việc ở đây, vì mọi nhánh phải trả về một
        # thứ gửi đi được. Stack trace vào log để còn chẩn đoán được.
        logger.exception("could not open a pdf of %s bytes", len(raw))
        return Finding(DocumentState.FAILED, None, "Không mở được tệp PDF này.")

    if pages == 0:
        # Một phán quyết, không phải một lần hỏng: tải lại đúng tệp ấy cho đúng kết quả ấy.
        return Finding(DocumentState.NO_TEXT_LAYER, 0, "Tệp PDF này không có trang nào.")

    if with_text / pages < _MIN_READABLE_PAGE_RATIO:
        return Finding(
            DocumentState.NO_TEXT_LAYER,
            pages,
            "Tệp này là ảnh scan, chưa đọc được chữ.",
        )

    return Finding(DocumentState.READY, pages, "")
