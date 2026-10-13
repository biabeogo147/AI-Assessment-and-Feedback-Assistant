"""Nhận dạng chữ: một hộp dòng thành chữ tiếng Việt **có dấu**. Hai lựa chọn, cùng một giao diện.

Đây là nửa mà PaddleOCR không làm được, và lý do thì đo được ở mức byte ngày 10/10/2026:
PaddleOCR phát ra ă ũ ồ ư ê ô ơ đ nhưng **không bao giờ** phát ra tổ hợp hai dấu (ế ố ộ ớ ứ ợ),
nên `Kết nối tri thức với cuộc sống` ra `Kt ni tri thc vi cuc sng`. Đó là lỗ **từ điển ký tự**,
không phải lỗ phần nhìn, nên không ngưỡng nào và không ảnh rõ hơn nào chữa được.

Hai lựa chọn, benchmark 11/10/2026 trên 50 trang Lớp 6 tập 1 qua chính đường này
(`data/results/run-1`), 4 luồng, trung vị theo trang:

| `reader`               | thiếu từ (p90) | CER (p90)     | lỗi dấu | s/trang cả đường |
|------------------------|----------------|---------------|---------|------------------|
| `easyocr`              | 9,3% (16,6%)   | 11,9% (30,5%) | 9,8%    | 4,5              |
| `vietocr` `vgg_seq2seq`| 9,3% (18,3%)   | 15,7% (36,8%) | 12,9%   | 4,7              |

**EasyOCR bằng hoặc hơn ở mọi thước**, kể cả lỗi dấu -- nên nó là mặc định. VietOCR ở lại làm
lựa chọn vì người dùng muốn giữ nó, và vì hai bên hỏng **khác loại nhau**:

- **VietOCR lạc trên toán nằm trong dòng.** `Ư(18)`, `ƯCLN(24, 60)`, dãy `1, 3, 9` -- nó đọc sai
  rồi rơi vào vòng lặp (`1,3 1,3 1,3 ...`, `... nha nha nha`), vì bộ giải mã tự hồi quy đoán mỗi
  ký tự dựa trên ký tự trước. Dòng dài **không** phải nguyên nhân: dòng tỉ lệ 31:1 vẫn đọc gần
  hoàn hảo, đo trên p046.
- **EasyOCR là CTC**, đoán mọi vị trí cùng lúc từ ảnh, nên về cấu trúc nó không lặp được.

Một nhận định từng nằm ở đây -- *"VietOCR đọc dấu tốt hơn"* -- chưa bao giờ được đo đối đầu, và
benchmark 50 trang bác nó (12,9% so với 9,8%).

Số giây là chỉ dấu, không phải hằng số: cùng trang, cùng model, hai process trên máy này đo chênh
nhau tới 1,7 lần (review 11/10/2026).

Hai điều đúng với **cả hai** model, cả hai đo được:

- **Chúng nhận một dòng một lần.** Cho hai dòng thì chúng trả về một câu nghe xuôi tai và sai,
  không một lời cảnh báo. `textline.py` tồn tại vì điều này.
- **Crop phải được đệm.** Hộp của detector bám sát thân chữ, mà dấu tiếng Việt nằm **ngoài** thân
  chữ -- dấu thanh ở trên, dấu nặng ở dưới. Đệm 15% chiều cao cắt CER của VietOCR từ 11,1% xuống
  5,4% và lỗi dấu từ 8,3% xuống 2,3%; đệm 30% thì lỗi dấu xấu lại. Xem `padded`.

**Bẫy số luồng**, và nó đã làm sai mọi số giây trước 11/10/2026: torch và paddle dùng chung
runtime OpenMP, và **mỗi lần paddle `predict`, torch bị ép về một luồng.** Đo được bằng
`torch.get_num_threads()`: 4 sau `set_num_threads(4)`, vẫn 4 sau khi nạp predictor, **1** ngay
sau lời `predict` đầu tiên. Trong `read_page`, detect của paddle chạy ngay trước nhận dạng, nên
đặt số luồng một lần lúc khởi động là vô dụng: bộ nhận dạng **luôn** chạy đơn luồng. Cùng trang,
cùng hộp, cùng process, đặt lại 4 luồng ngay trước khi đọc: VietOCR nhanh lên chừng 2,5 lần,
EasyOCR chừng 1,5 lần.
Nên cả hai reader đặt lại số luồng **ở đầu `read_lines`** -- chỗ duy nhất chắc chắn không có lời
gọi paddle nào chen vào giữa.
"""

import logging
from typing import Protocol

import numpy as np
import torch
from PIL import Image

from document.ocr.model import BBox

logger = logging.getLogger(__name__)

# Hộp hẹp hơn ngần này điểm ảnh ở một chiều thì không có chữ nào trong đó. Cắt crop rỗng rồi đưa
# cho một model luôn luôn trả lời là cách chắc chắn nhất để sinh ra chữ không có trên trang.
_TOO_SMALL = 4

# Phần đệm trên và dưới, tính theo chiều cao hộp. Đo 11/10/2026 trên ba trang: 0% / 15% / 30%
# cho CER 0,111 / 0,054 / 0,049 và lỗi dấu 0,083 / 0,023 / 0,029. Lấy 15% vì nó tốt nhất ở lỗi
# dấu, và chênh CER với 30% nằm trong nhiễu của ba trang.
_PAD_RATIO = 0.15

# Đệm ngang cố định, vài điểm ảnh: đủ cho nét cuối của một chữ in nghiêng, không đủ chạm chữ của
# cột bên cạnh.
_PAD_SIDE = 2

READERS = ("easyocr", "vietocr")


def too_small(box: BBox) -> bool:
    """Hộp này có nhỏ tới mức không thể chứa chữ không.

    Hàm riêng, không phải một dòng `if` trong thân lớp, vì nó là **luật** chứ không phải chi
    tiết: cắt một crop rỗng rồi đưa cho một model luôn luôn trả lời là cách chắc chắn nhất để
    sinh ra chữ không có trên trang. Luật đáng canh thì phải chạm được mà không nạp 150 MB model.

    Args:
        box: Hộp đang xét.

    Returns:
        True khi một chiều của hộp hẹp hơn ngưỡng.
    """
    return box.width < _TOO_SMALL or box.height < _TOO_SMALL


def padded(box: BBox, width: int, height: int) -> BBox:
    """Nới một hộp dòng cho dấu tiếng Việt lọt vào, không vượt ra ngoài trang.

    Args:
        box: Hộp detector trả về, bám sát thân chữ.
        width: Chiều rộng ảnh trang.
        height: Chiều cao ảnh trang.

    Returns:
        Hộp đã nới, kẹp trong biên ảnh.
    """
    grow = round(_PAD_RATIO * box.height)
    return BBox(
        max(0, box.left - _PAD_SIDE),
        max(0, box.top - grow),
        min(width, box.right + _PAD_SIDE),
        min(height, box.bottom + grow),
    )


class LineReader(Protocol):
    """Thứ đọc được một loạt hộp dòng. Cả hai lựa chọn đều mang hình dạng này."""

    def read_lines(self, image: np.ndarray, boxes: list[BBox]) -> list[str]:
        """Đọc từng hộp.

        Args:
            image: Ảnh trang, dạng mảng `numpy` RGB.
            boxes: Hộp từng dòng.

        Returns:
            Một chuỗi cho mỗi hộp, **đúng thứ tự đã truyền vào**.
        """
        ...


def make_line_reader(name: str, vietocr_model: str = "vgg_seq2seq", threads: int = 4) -> LineReader:
    """Nạp một bộ nhận dạng theo tên.

    Tên sai thì ném **trước khi** nạp bất cứ model nào: một lỗi gõ trong cấu hình không được
    phép tốn tám giây nạp model rồi mới nói ra.

    Args:
        name: Một trong `READERS`.
        vietocr_model: Cấu hình VietOCR, chỉ dùng khi `name == "vietocr"`.
        threads: Số luồng torch, đặt lại ở mỗi lần đọc.

    Returns:
        Bộ nhận dạng đã nạp.

    Raises:
        ValueError: Khi `name` không thuộc `READERS`.
    """
    if name == "easyocr":
        return EasyOcrReader(threads=threads)
    if name == "vietocr":
        return VietnameseReader(model=vietocr_model, threads=threads)
    raise ValueError(f"unknown line reader {name!r}, expected one of {READERS}")


class VietnameseReader:
    """Giữ VietOCR đã nạp.

    Tải weights từ `vocr.vn` ở lần nạp đầu, khoảng 150 MB vào thư mục tạm. Một job đi tải giữa
    chừng là một job hết hạn, nên worker phải nạp sẵn trong `on_startup`.

    Attributes:
        _reader: `Predictor` của VietOCR.
        _threads: Số luồng torch.
    """

    def __init__(self, model: str = "vgg_seq2seq", threads: int = 4):
        """Nạp model trên CPU.

        Args:
            model: Tên cấu hình VietOCR. Mặc định `vgg_seq2seq` chứ không `vgg_transformer`, đo
                11/10/2026 ở 4 luồng: seq2seq 4,3 s/trang thiếu 7,3% từ, transformer 11,1 s/trang
                thiếu 9,2%. Bản lớn hơn vừa chậm hơn vừa sai nhiều hơn trên sách này. (Hai số
                giây ấy đo khi torch còn bị ép một luồng, nên chỉ đáng tin ở **tỉ lệ** giữa chúng.)
            threads: Số luồng torch, đặt lại ở mỗi lần đọc -- xem *bẫy số luồng* ở đầu module.
        """
        from vietocr.tool.config import Cfg
        from vietocr.tool.predictor import Predictor

        config = Cfg.load_config_from_name(model)
        # Mặc định của VietOCR là `cuda:0`. Server không có GPU, và để nguyên thì nó chết ở lời
        # gọi đầu tiên chứ không ở lúc nạp -- tức chết giữa một job, không phải lúc khởi động.
        config["device"] = "cpu"
        # Không tải weights ImageNet cho phần CNN: bản `.pth` của VietOCR đã chứa trọng số đầy
        # đủ, nên dòng này chỉ thêm một lần tải mạng cho một thứ bị ghi đè ngay sau đó.
        config["cnn"]["pretrained"] = False
        self._reader = Predictor(config)
        self._threads = threads

    def read_lines(self, image: np.ndarray, boxes: list[BBox]) -> list[str]:
        """Đọc nhiều dòng trong một lượt.

        Gọi theo lô chứ không từng dòng một: VietOCR xếp chúng vào một batch, và trên CPU phần
        lớn thời gian một lời gọi là chi phí cố định chứ không phải phép tính.

        Args:
            image: Ảnh trang, dạng mảng `numpy` RGB.
            boxes: Hộp từng dòng.

        Returns:
            Một chuỗi cho mỗi hộp, **đúng thứ tự đã truyền vào**. Hộp quá nhỏ cho chuỗi rỗng chứ
            không bị bỏ đi -- người gọi đang dựa vào việc hai danh sách khớp từng vị trí.
        """
        if not boxes:
            return []

        # Paddle vừa chạy detect và đã ép torch về một luồng. Xem *bẫy số luồng*.
        torch.set_num_threads(self._threads)
        height, width = image.shape[:2]
        page = Image.fromarray(image)
        crops, where = [], []
        for at, box in enumerate(boxes):
            if too_small(box):
                continue
            crops.append(page.crop(padded(box, width, height)))
            where.append(at)

        out = [""] * len(boxes)
        if not crops:
            return out

        for at, text in zip(where, self._reader.predict_batch(crops), strict=True):
            out[at] = text
        return out


class EasyOcrReader:
    """Giữ bộ nhận dạng của EasyOCR đã nạp, **không** kèm detector của nó.

    Detector là của paddle, dùng chung cho cả hai lựa chọn, để hai lựa chọn khác nhau đúng ở một
    chỗ. Nạp thêm CRAFT là tốn 80 MB cho một thứ không ai gọi.

    Tải weights `latin_g2.pth` từ GitHub vào `~/.EasyOCR` ở lần nạp đầu -- cùng lý do như VietOCR
    để nạp sẵn trong `on_startup`.

    Attributes:
        _reader: `easyocr.Reader` chỉ có phần nhận dạng.
        _threads: Số luồng torch.
    """

    def __init__(self, threads: int = 4) -> None:
        """Nạp model tiếng Việt trên CPU.

        Args:
            threads: Số luồng torch, đặt lại ở mỗi lần đọc -- xem *bẫy số luồng* ở đầu module.
        """
        import easyocr

        self._reader = easyocr.Reader(["vi"], gpu=False, detector=False, verbose=False)
        self._threads = threads

    def read_lines(self, image: np.ndarray, boxes: list[BBox]) -> list[str]:
        """Đọc nhiều dòng.

        **Từng hộp một**, và đó không phải sơ suất. Trên CPU, `recognize` của EasyOCR vốn đã đi
        từng hộp một bên trong, nên gọi theo lô không nhanh hơn. Nhưng với nhiều hộp, đường gom
        lô của nó (`get_image_list(..., sort_output=True)`, `easyocr/utils.py` bản 1.7.2) **sắp
        lại kết quả theo trục y** -- tức trả về đủ chuỗi nhưng sai chỗ, và người gọi thì ghép chữ
        vào khối theo vị trí. Gọi từng hộp thì không còn gì để sắp.

        Đọc mã nguồn 1.7.2, mỗi hộp luôn cho đúng một chuỗi khi `too_small` đã chặn hộp suy biến.
        Vẫn ghép bằng `" ".join` chứ không lấy phần tử đầu, để một phiên bản sau trả về hai mẩu
        cho một hộp thì mất khoảng trắng chứ không mất chữ.

        Args:
            image: Ảnh trang, dạng mảng `numpy` RGB.
            boxes: Hộp từng dòng.

        Returns:
            Một chuỗi cho mỗi hộp, **đúng thứ tự đã truyền vào**.
        """
        if not boxes:
            return []

        # Paddle vừa chạy detect và đã ép torch về một luồng. Xem *bẫy số luồng*.
        torch.set_num_threads(self._threads)
        height, width = image.shape[:2]
        # Chuyển xám **một lần** rồi truyền `reformat=False`. Để mặc định thì EasyOCR chuyển cả
        # trang ở mỗi lời gọi, tức sáu mươi lần mỗi trang cho cùng một kết quả.
        grey = np.asarray(Image.fromarray(image).convert("L"))

        out = [""] * len(boxes)
        for at, box in enumerate(boxes):
            if too_small(box):
                continue
            wide = padded(box, width, height)
            pieces = self._reader.recognize(
                grey,
                horizontal_list=[[wide.left, wide.right, wide.top, wide.bottom]],
                free_list=[],
                detail=0,
                reformat=False,
            )
            out[at] = " ".join(piece for piece in pieces if piece)
        return out
