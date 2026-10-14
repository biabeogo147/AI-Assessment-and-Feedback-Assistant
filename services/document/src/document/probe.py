"""Mở một tệp ra xem có đọc được chữ không, và đếm số trang.

Đây là **luật**, không phải cách chạm tệp: hai ngưỡng dưới đây và phép suy từ chúng ra một
`DocumentState`. Việc gọi PyMuPDF thì ở `pdf.py`, module duy nhất được import nó -- xem docstring
của module ấy để biết vì sao ranh giới này tồn tại, và vì sao `probe.py` từng đứng ở cả hai phía
của nó tới ngày 10/10/2026.

Từ `mongo-content-store`, module này còn dựng **bản thô** của một tệp có chữ (`raw_pages`) -- chữ đi
vào kho nội dung y như nó nằm trong tệp, chia trang và khối. Vẫn là luật chứ không là cách chạm tệp:
*chữ của một trang là gì, chia khối ra sao, chuẩn hoá thế nào*.

Không có lời gọi model nào ở đây và sẽ không bao giờ có. Đây là phép đếm, không phải phép đọc
hiểu: việc cắt chương và phân loại đoạn thuộc plan sau.
"""

import logging
import unicodedata
from datetime import datetime
from typing import TYPE_CHECKING, NamedTuple

from contracts import DocumentState, RawBlock, RawPage, RawSource
from document.pdf import PdfUnreadable, open_pdf

if TYPE_CHECKING:
    # Chỉ để khai kiểu. Import thật kéo theo `document.ocr`, mà `__init__` của nó nạp torch -- vài
    # giây và vài trăm MB cho mỗi process chỉ muốn đếm chữ của một tệp `.md`.
    from document.ocr.model import PageRead

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

# Nhãn khối khi không ai gán nhãn: text layer và tệp thuần. Đường OCR dùng nhãn của PP-DocLayout.
_UNLABELLED = "text"


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

    Trước `mongo-content-store`, hàm này giải mã với `errors="replace"` và để việc đoán bảng mã cho
    bước cắt đoạn. Từ `mongo-content-store` thì không còn bước nào sau đó đọc lại byte: chữ đi
    thẳng vào kho nội dung, và bản thô là bất biến (D6). Nên một tệp không đọc đúng được thì **từ
    chối ở đây**, bằng một câu giáo viên sửa được, thay vì đóng băng rác vào kho (người dùng chốt
    11/10/2026).

    Args:
        raw: Toàn bộ byte của tệp.

    Returns:
        `READY` khi có ký tự không-trắng; `NO_TEXT_LAYER` khi không; `FAILED` khi bảng mã không
        đọc được. `page_count` luôn là `None`.
    """
    text = _decode_plain_text(raw)
    if text is None:
        return Finding(
            DocumentState.FAILED,
            None,
            "Tệp không lưu ở dạng UTF-8. Lưu lại dưới dạng UTF-8 rồi tải lên lần nữa.",
        )
    if not text.strip():
        return Finding(DocumentState.NO_TEXT_LAYER, None, "Tệp này không có chữ nào.")
    return Finding(DocumentState.READY, None, "")


def _decode_plain_text(raw: bytes) -> str | None:
    """Giải mã một tệp văn bản thuần, hoặc nói rằng không giải mã đúng được.

    Nhận UTF-8 (có hoặc không BOM -- BOM bị bỏ, `strip()` không bỏ nó) và UTF-16 **có BOM** (thứ
    Notepad gọi là *"Unicode"*). Mọi thứ khác bị từ chối chứ không đoán: cp1252 hay TCVN3 đoán
    sai thì ra chữ trông như chữ mà sai dấu, và bên đọc không có cách nào biết.

    Args:
        raw: Toàn bộ byte của tệp.

    Returns:
        Chữ đã giải mã, hoặc `None` khi tệp không phải hai dạng trên. Một ký tự NUL cũng là
        `None`: UTF-16 **không BOM** của chữ ASCII là UTF-8 hợp lệ, xen NUL giữa từng ký tự.
    """
    try:
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            text = raw.decode("utf-16")
        else:
            text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None
    if "\x00" in text:
        return None
    return text


def _probe_pdf(raw: bytes) -> Finding:
    """Một PDF: đếm xem bao nhiêu trang thật sự mang chữ.

    Args:
        raw: Toàn bộ byte của tệp.

    Returns:
        `READY` kèm số trang khi đủ phần trăm trang có chữ; `NO_TEXT_LAYER` khi không;
        `FAILED` khi không mở được tệp.
    """
    try:
        with open_pdf(raw) as pages_of:
            lengths = pages_of.text_lengths()
    except PdfUnreadable:
        # Một tệp hỏng là một **phán quyết**, không phải một lỗi của hệ thống: mọi nhánh phải trả
        # về một thứ gửi đi được, nếu không chip đứng mãi ở *đang xử lý*. `pdf.py` đã ghi stack
        # trace và đã dịch mọi loại exception của `pymupdf` thành một lỗi có kiểu, nên ở đây chỉ
        # còn việc chọn câu nói với giáo viên.
        return Finding(DocumentState.FAILED, None, "Không mở được tệp PDF này.")

    pages = len(lengths)
    with_text = sum(1 for chars in lengths if chars >= _MIN_CHARS_PER_PAGE)

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


def raw_pages(raw: bytes, filename: str, document_id: str, at: datetime) -> list[RawPage]:
    """Dựng bản thô của một tệp **có chữ**: một `RawPage` mỗi trang, theo thứ tự trang.

    Chỉ gọi khi `probe` đã trả `READY`: một PDF scan không có chữ để dựng, bản thô của nó đi
    đường OCR. Hàm **thuần** và **sync** như `probe`, người gọi đặt nó vào một thread.

    Mọi chữ được chuẩn hoá NFC: text layer của PDF tiếng Việt hay mang dấu tách rời (NFD), và bên
    đọc ở `document-agent-hierarchy` so khớp chữ -- `"ệ"` hai dạng là hai chuỗi khác nhau.

    Args:
        raw: Toàn bộ byte của tệp.
        filename: Tên tệp. Phần mở rộng quyết định đường đọc, cùng luật với `probe`.
        document_id: Id tài liệu.
        at: Lúc đọc, có múi giờ.

    Returns:
        Các trang. Tệp văn bản thuần cho đúng một trang, một khối, không hộp. Trang PDF không có
        khối chữ nào vẫn có mặt, rỗng -- số trang trong kho phải khớp `page_count`.

    Raises:
        PdfUnreadable: Khi PDF không đọc nổi. `probe` vừa mở được nó nên chuyện này gần như không
            xảy ra, nhưng người gọi vẫn phải xử như một tệp hỏng.
        ValueError: Khi tệp không phải loại có chữ mà hàm biết dựng, hoặc là tệp thuần mà bảng
            mã không đọc được -- cả hai đều là ca `probe` không trả `READY`.
    """
    lowered = filename.lower()
    if lowered.endswith(_PLAIN_TEXT_SUFFIXES):
        decoded = _decode_plain_text(raw)
        if decoded is None:
            raise ValueError(f"{filename} is not utf-8; probe should not have said ready")
        text = _clean(decoded)
        return [
            RawPage(
                document_id=document_id,
                page=1,
                source=RawSource.PLAIN,
                blocks=(RawBlock(kind=_UNLABELLED, text=text),),
                text=text,
                read_at=at,
            )
        ]
    if lowered.endswith(".pdf"):
        return _raw_pdf_pages(raw, document_id, at)
    raise ValueError(f"no raw reader for {filename}")


def _raw_pdf_pages(raw: bytes, document_id: str, at: datetime) -> list[RawPage]:
    """Bản thô của một PDF có text layer.

    Args:
        raw: Toàn bộ byte của tệp.
        document_id: Id tài liệu.
        at: Lúc đọc.

    Returns:
        Một trang mỗi trang của tệp. Khối không còn chữ sau khi chuẩn hoá bị bỏ.

    Raises:
        PdfUnreadable: Khi tệp không đọc nổi.
    """
    out: list[RawPage] = []
    with open_pdf(raw) as pages_of:
        for index in range(len(pages_of)):
            found = pages_of.page_text(index)
            cleaned = ((block.box, _clean(block.text)) for block in found.blocks)
            blocks = tuple(
                RawBlock(kind=_UNLABELLED, box=box, text=text) for box, text in cleaned if text
            )
            out.append(
                RawPage(
                    document_id=document_id,
                    page=index + 1,
                    source=RawSource.TEXT_LAYER,
                    width=found.width,
                    height=found.height,
                    blocks=blocks,
                    text="\n".join(block.text for block in blocks),
                    read_at=at,
                )
            )
    return out


# Nhãn khối hình như nó nằm trong bản thô. Một chuỗi chứ không `BlockKind.IMAGE`: `document.ocr`
# chỉ được nhìn thấy dưới `TYPE_CHECKING` ở module chính sách này.
_IMAGE = "image"


def raw_ocr_page(read: "PageRead", document_id: str, at: datetime) -> RawPage:
    """Bản thô của một trang đọc bằng OCR.

    Khác text layer ở hai chỗ, và cả hai là thứ `document-agent-hierarchy` cần: nhãn khối là nhãn
    **thật** của PP-DocLayout (`paragraph_title`, `formula`, `number`, ...) chứ không phải `text`,
    và mỗi trang mang số giây từng chặng -- số đo của đường OCR trong worker thật nằm ở đây, không ở
    bộ đo.

    Khối không có chữ (hình, bảng) **vẫn ở lại**, với chữ rỗng: một hình giữa hai đoạn là tín hiệu
    bố cục, và bỏ nó là bỏ thông tin mà không ai yêu cầu bỏ. Chỉ `text` của trang bỏ qua chúng.

    Từ `document-agent-hierarchy` (D2), khối **hình** mang chữ của các dòng nằm trong nó -- để bên
    dựng cây thấy chữ *"CHƯƠNG"* trên banner. `text` của trang vẫn bỏ qua khối hình: phần lớn chữ ấy
    là rác nhãn hình, và `text` là thứ đi vào ngữ cảnh của LLM.

    Args:
        read: Trang `PageReader.read_page` trả về.
        document_id: Id tài liệu.
        at: Lúc đọc, có múi giờ.

    Returns:
        Trang, `source` là `OCR`, hộp theo điểm ảnh của ảnh đã dựng.
    """
    blocks = tuple(
        RawBlock(kind=str(block.kind), box=tuple(block.box), text=_clean(block.text))
        for block in read.blocks
    )
    return RawPage(
        document_id=document_id,
        page=read.page,
        source=RawSource.OCR,
        width=read.width,
        height=read.height,
        blocks=blocks,
        text="\n".join(block.text for block in blocks if block.text and block.kind != _IMAGE),
        seconds=dict(read.seconds),
        read_at=at,
    )


def _clean(text: str) -> str:
    """NFC và bỏ khoảng trắng hai đầu. Xuống dòng bên trong khối được giữ: nó là ranh giới dòng.

    Args:
        text: Chữ thô.

    Returns:
        Chữ đã chuẩn hoá.
    """
    return unicodedata.normalize("NFC", text).strip()
