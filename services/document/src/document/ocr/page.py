"""Ghép các chặng: một trang PDF thành một `PageRead` -- **chỉ chữ**.

Thứ tự bị ép bởi phụ thuộc, không bởi sở thích:

1. `render` -- PDF thành ảnh (`document/pdf.py`).
2. `layout` -- ảnh thành khối có nhãn, hộp bao, thứ tự đọc.
3. `detect` một lần cho **cả trang**, rồi gán từng dòng vào khối chứa tâm của nó. Gọi detector
   trên từng khối sẽ rẻ hơn một chút và sai ở mép: một dòng vắt qua biên khối bị cắt làm đôi.
4. `recognize` cho mọi khối có chữ -- kể cả khối `FORMULA`.

**Công thức không được đọc ở đây nữa** (người dùng chốt 11/10/2026). Benchmark 50 trang cho thấy
PP-FormulaNet trên CPU không cứu được: trên 58 công thức nhãn vàng, layout làm hỏng 24 và model
hỏng 21. Công thức được đọc **lúc ra đề**, chỉ ở phần tài liệu được tham chiếu, bằng
gpt-4.1-mini qua API (sẽ nằm ở `services/agent/src/agent/vision.py`, chưa viết). Khối `FORMULA`
vẫn ở lại: nó nhận chữ OCR như mọi khối chữ, và nhãn của nó là gợi ý *trang này có toán*.

**Model nạp một lần, ở `on_startup` của worker.** Lớp này giữ chúng, và nó cố ý không tự nạp
trong `read_page`: nạp ba model mất vài giây, và trả cái giá ấy cho mỗi trang của một cuốn bốn
trăm trang là trả nó bốn trăm lần.
"""

import logging
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import numpy as np
from PIL import Image

from document.ocr.layout import LayoutReader
from document.ocr.model import BlockKind, PageBlock, PageRead
from document.ocr.recognize import make_line_reader
from document.ocr.textline import TextLineFinder
from document.pdf import open_pdf

logger = logging.getLogger(__name__)

# Khối thuộc những loại này để chữ rỗng: `_fill` không gán dòng nào vào chúng.
# Từ `document-agent-hierarchy` (D2), khối **hình** giữ chữ của những dòng detector đã tìm thấy bên
# trong nó. Không một crop nào được đưa cho bộ nhận dạng -- dòng đã được detect và đọc từ trước,
# `_fill` chỉ thôi vứt chúng -- nên không tốn thêm giây nào. Lý do: banner mở chương của SGK là
# **một khối hình**, và chữ *"CHƯƠNG"* trong nó là tín hiệu duy nhất OCR có cho *"trang này mở một
# chương"* (đo trên 5/5 chương của Lớp 6 tập 1). Tên chương thì không đọc nổi -- chữ trang trí --
# nên `gpt-5.6-luna` đọc nó, chỉ ở trang qua cổng ấy (D9). Phần lớn chữ trong hình còn lại là rác
# nhãn hình (`'a) b)'`, `'4v 12'`), nên `probe.raw_ocr_page` không nối nó vào chữ của trang.
#
# Bảng thì vẫn rỗng như ở `document-ocr-text-and-latex`: `document-agent-hierarchy` không cần chữ
# của bảng, nên không đổi thứ bộ đo đã đo mà không có lý do. Lưu ý: hộp layout có thể chồng nhau,
# nên một dòng có thể nằm trong cả khối hình lẫn một khối chữ -- bên dựng cây không bao giờ lấy khối
# hình làm ứng viên heading.
_WITHOUT_TEXT = frozenset({BlockKind.TABLE})


class PageReader:
    """Ba model đã nạp, dùng lại cho mọi trang.

    Attributes:
        _layout: PP-DocLayout.
        _lines: Detector dòng của PaddleOCR.
        _words: Bộ nhận dạng chữ -- EasyOCR hoặc VietOCR, xem `recognize.py`.
        _dpi: Số điểm ảnh mỗi inch khi dựng ảnh trang.
    """

    def __init__(
        self,
        dpi: int = 200,
        use_mkldnn: bool = False,
        reader: str = "easyocr",
        vietocr_model: str = "vgg_seq2seq",
        threads: int = 4,
    ):
        """Nạp cả ba model.

        Args:
            dpi: Độ phân giải dựng ảnh. Bản scan trong `data/` ở khoảng 144 DPI, nên xin cao hơn
                hẳn mức ấy chỉ phóng to điểm ảnh có sẵn.
            use_mkldnn: Bật oneDNN cho hai model paddle (layout và detector). Mặc định tắt -- xem
                `layout.LayoutReader`.
            reader: Bộ nhận dạng chữ, `"easyocr"` hoặc `"vietocr"`. Mặc định `easyocr` vì sản
                phẩm ưu tiên tốc độ: chữ đọc ra đi vào LLM, và vài chữ sai không đổi nghĩa của
                ngữ cảnh. Bảng so sánh nằm ở docstring của `recognize.py`.
            vietocr_model: Cấu hình VietOCR, chỉ dùng khi `reader="vietocr"`.
            threads: Số luồng CPU cho **mọi** model, torch lẫn paddle. Đích chạy là VPS chỉ có
                CPU, nên đặt bằng số vCPU của nó. Phía torch phải được đặt **lại** ở mỗi lần
                đọc, vì mỗi lời `predict` của paddle ép nó về một luồng -- xem `recognize.py`.

        Raises:
            ValueError: Khi `reader` không thuộc `recognize.READERS` -- ném trước khi nạp model.
        """
        # Đi trước mọi lần nạp: tên reader sai phải chết ngay, không phải sau tám giây.
        self._words = make_line_reader(reader, vietocr_model=vietocr_model, threads=threads)
        self._layout = LayoutReader(use_mkldnn=use_mkldnn, threads=threads)
        self._lines = TextLineFinder(use_mkldnn=use_mkldnn, threads=threads)
        self._dpi = dpi

    def read_page(self, raw: bytes, index: int) -> PageRead:
        """Đọc một trang của một tệp PDF.

        Args:
            raw: Toàn bộ byte của tệp.
            index: Số thứ tự trang, đếm từ 0.

        Returns:
            Trang đã đọc. `blocks` rỗng là một kết quả hợp lệ -- một trang trắng hay một trang
            chỉ có một bức ảnh không có khối chữ nào, và người gọi phải đi tiếp được.

        Raises:
            PdfUnreadable: Khi không mở hoặc không dựng được ảnh trang.
            IndexError: Khi `index` nằm ngoài số trang.
        """
        seconds: dict[str, float] = {}

        with _timed(seconds, "render"), open_pdf(raw) as pages:
            png = pages.render(index, dpi=self._dpi)

        with _as_png_file(png) as path:
            image = np.array(Image.open(path).convert("RGB"))
            height, width = image.shape[:2]

            with _timed(seconds, "layout"):
                blocks = self._layout.read(path)

        with _timed(seconds, "detect"):
            lines = self._lines.find(image)

        with _timed(seconds, "recognize"):
            texts = self._words.read_lines(image, lines)

        # Chặng này giờ chỉ gán dòng vào khối; đổi tên để cột giây không còn nói "formula".
        with _timed(seconds, "assign"):
            filled = [_fill(block, lines, texts) for block in blocks]

        logger.info(
            "read page %s: %s blocks, %s lines, %.1fs",
            index + 1,
            len(filled),
            len(lines),
            sum(seconds.values()),
        )
        return PageRead(index + 1, width, height, tuple(filled), seconds)


def _fill(block: PageBlock, lines: list, texts: list[str]) -> PageBlock:
    """Đổ chữ vào một khối còn rỗng. Khối `FORMULA` cũng chỉ nhận chữ OCR.

    Args:
        block: Khối từ chặng layout, chữ còn rỗng.
        lines: Hộp từng dòng của cả trang.
        texts: Chữ của từng dòng, khớp vị trí với `lines`.

    Returns:
        Khối đã có chữ. Bảng giữ nguyên chữ rỗng; hình mang chữ của các dòng nằm trong nó (D2 của
        `document-agent-hierarchy`).
    """
    if block.kind in _WITHOUT_TEXT:
        return block
    return block._replace(text=_text_inside(block, lines, texts))


def _text_inside(block: PageBlock, lines: list, texts: list[str]) -> str:
    """Gom chữ của những dòng có tâm nằm trong một khối.

    Gán theo **tâm** chứ không theo phần giao: một dòng chỉ thò ra ngoài khối vài điểm ảnh vẫn
    thuộc khối ấy, còn một dòng của khối bên cạnh thò vào thì không.

    Args:
        block: Khối đang xét.
        lines: Hộp từng dòng của cả trang.
        texts: Chữ của từng dòng.

    Returns:
        Chữ các dòng nối bằng dấu cách, theo thứ tự trên xuống rồi trái sang.
    """
    mine = [
        (box.top, box.left, text)
        for box, text in zip(lines, texts, strict=True)
        if text and _centre_inside(block, box)
    ]
    return " ".join(text for _, _, text in sorted(mine)).strip()


def _centre_inside(block: PageBlock, line) -> bool:
    """Tâm của một dòng có nằm trong một khối không.

    Args:
        block: Khối đang xét.
        line: Hộp của dòng.

    Returns:
        True khi tâm nằm trong hộp của khối.
    """
    middle_x = (line.left + line.right) // 2
    middle_y = (line.top + line.bottom) // 2
    return (
        block.box.left <= middle_x <= block.box.right
        and block.box.top <= middle_y <= block.box.bottom
    )


@contextmanager
def _as_png_file(png: bytes) -> Iterator[str]:
    """Ghi byte PNG ra một tệp tạm, cho mượn đường dẫn, rồi xoá.

    PP-DocLayout nhận đường dẫn; `PIL` và detector thì nhận mảng. Ghi **một** tệp rồi dùng chung
    cho cả hai, và xoá nó trong `finally`: một cuốn bốn trăm trang để lại bốn trăm tệp 1,5 MB
    nếu bước xoá nằm ở đường đi thành công thay vì ở đây.

    Args:
        png: Byte của tệp PNG.

    Yields:
        Đường dẫn tới tệp tạm.
    """
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
        handle.write(png)
        where = handle.name
    try:
        yield where
    finally:
        Path(where).unlink(missing_ok=True)


@contextmanager
def _timed(into: dict[str, float], stage: str) -> Iterator[None]:
    """Đo thời gian một chặng và cộng vào bảng.

    Cộng chứ không gán: một chặng có thể chạy nhiều lần trong một trang, và lúc ấy con số đáng
    quan tâm là tổng của nó.

    Args:
        into: Bảng thời gian theo chặng.
        stage: Tên chặng.

    Yields:
        Không gì cả.
    """
    start = time.monotonic()
    try:
        yield
    finally:
        into[stage] = into.get(stage, 0.0) + time.monotonic() - start
