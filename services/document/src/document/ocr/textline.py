"""Detector của PaddleOCR: một trang thành các hộp **từng dòng**.

Chặng này tồn tại vì VietOCR nhận **một dòng một lần**. Đo ngày 10/10/2026, cho nó đúng một khối
layout hai dòng thì nó trả về rác -- crop *KIẾN THỨC, KĨ NĂNG* hai dòng ra
`'Thuận - Thực hiện phép chia hai số tự nhiên (chia hết và chia)'`, tức nó bịa một từ ở đầu và
nuốt phần sau. Cùng crop ấy cắt thành từng dòng thì nó đọc đúng.

Chạy detector **một lần cho cả trang**, không phải một lần cho mỗi khối. Hai lý do: một lời gọi
thay vì hai mươi, và không có hiệu ứng biên -- một dòng nằm vắt qua mép khối sẽ bị cắt làm đôi
nếu detector chỉ nhìn thấy phần trong khối. Dòng nào thuộc khối nào thì quyết sau, bằng tâm của
hộp.

Đây là phần paddle **không** thủng: nó nhìn rất tốt. Cái nó không làm được là đọc chữ tiếng Việt
-- xem `recognize.py`.
"""

import logging
from statistics import median
from typing import Any

import numpy as np
from paddleocr import TextDetection

from document.ocr.model import BBox

logger = logging.getLogger(__name__)

# Dòng cao hơn ngần này lần chiều cao dòng trung vị của trang thì gần như chắc chắn là **hai
# dòng dính nhau**. Cho một hộp như vậy sang VietOCR là cho nó đúng thứ nó không đọc được, và nó
# sẽ không báo lỗi -- nó trả về một câu nghe xuôi tai và sai.
_TOO_TALL = 1.8

# Dưới mức này thì bỏ. Detector trả về cả vệt nhiễu trên bản scan.
_MIN_SCORE = 0.50


class TextLineFinder:
    """Giữ detector đã nạp.

    Attributes:
        _model: Predictor của PaddleOCR.
        _min_score: Ngưỡng điểm tin cậy.
    """

    def __init__(
        self,
        use_mkldnn: bool = False,
        min_score: float = _MIN_SCORE,
        model: str = "PP-OCRv5_mobile_det",
        threads: int = 4,
    ):
        """Nạp detector.

        Args:
            model: Tên model. Bản `mobile` chứ không `PP-OCRv6_medium_det` (mặc định của thư
                viện): đo 11/10/2026 ở 4 luồng, mobile 0,5 s/trang và medium 4,0 s/trang, cho
                cùng một tỉ lệ thiếu từ (7,3% và 7,1%).
            threads: Số luồng CPU. Xem `page.PageReader`.
            use_mkldnn: Bật oneDNN. Mặc định tắt -- xem `layout.LayoutReader`.
            min_score: Ngưỡng điểm tin cậy.
        """
        self._model = TextDetection(model_name=model, enable_mkldnn=use_mkldnn, cpu_threads=threads)
        self._min_score = min_score

    def find(self, image: np.ndarray) -> list[BBox]:
        """Tìm mọi dòng chữ trên một ảnh trang.

        Args:
            image: Ảnh trang, dạng mảng `numpy` RGB.

        Returns:
            Hộp bao của từng dòng, đã tách những hộp dính hai dòng. Thứ tự chưa có nghĩa gì --
            việc gán dòng vào khối và sắp thứ tự thuộc `page.py`.
        """
        found: list[BBox] = []
        for one in self._model.predict(image):
            payload: dict[str, Any] = one.json["res"]
            polys = payload.get("dt_polys", [])
            scores = payload.get("dt_scores", [1.0] * len(polys))
            for poly, score in zip(polys, scores, strict=False):
                if score >= self._min_score:
                    found.append(_bounding(poly))
        split = split_tall_lines(found)
        logger.info("detector found %s lines, %s after splitting tall ones", len(found), len(split))
        return split


def _bounding(poly: Any) -> BBox:
    """Hộp bao của một đa giác bốn đỉnh.

    Detector trả về đa giác chứ không hình chữ nhật, vì một dòng chữ trên bản scan có thể nghiêng.
    Cắt crop theo hộp bao là chấp nhận lấy thừa một ít nền ở hai góc -- rẻ hơn hẳn việc xoay ảnh,
    và VietOCR chịu được nền thừa.

    Args:
        poly: Bốn đỉnh, mỗi đỉnh là cặp toạ độ.

    Returns:
        Hộp bao.
    """
    xs = [int(point[0]) for point in poly]
    ys = [int(point[1]) for point in poly]
    return BBox(min(xs), min(ys), max(xs), max(ys))


def split_tall_lines(boxes: list[BBox]) -> list[BBox]:
    """Cắt đôi -- hoặc làm ba, làm tư -- những hộp cao bất thường.

    Chiều cao dòng trên một trang sách rất đều, nên một hộp cao gấp đôi phần còn lại là hai dòng
    dính nhau chứ không phải một dòng chữ to. Cắt đều theo chiều cao trung vị là phép xấp xỉ, và
    nó đúng vì khoảng cách dòng trong một đoạn văn cũng đều.

    Không có chặng này thì lỗi đi tiếp vào VietOCR, và **VietOCR không báo gì cả** -- nó trả về
    một câu nghe xuôi tai và sai, thứ tốn công nhất để phát hiện về sau.

    Args:
        boxes: Hộp từng dòng, thứ tự nào cũng được.

    Returns:
        Hộp sau khi cắt. Danh sách ngắn hơn ba hộp thì trả về nguyên: trung vị của hai con số
        không nói lên điều gì về một trang.
    """
    if len(boxes) < 3:
        return list(boxes)

    usual = median(box.height for box in boxes)
    if usual <= 0:
        return list(boxes)

    out: list[BBox] = []
    for box in boxes:
        rows = int(box.height / usual + 0.5)
        if box.height <= usual * _TOO_TALL or rows < 2:
            out.append(box)
            continue
        step = box.height / rows
        for row in range(rows):
            top = box.top + int(row * step)
            bottom = box.top + int((row + 1) * step)
            out.append(BBox(box.left, top, box.right, bottom))
        logger.info("split a line box %s px tall into %s rows", box.height, rows)
    return out
