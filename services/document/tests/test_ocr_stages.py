"""Ba chặng sau layout: cắt dòng, chốt kích thước, và gán dòng vào khối.

Không test nào ở đây nạp model. Ba model của đường OCR nặng gần 400 MB và mất tám giây để nạp;
thứ đang được canh là phần chạy **quanh** chúng, và phần ấy thuần.

Con số toạ độ lấy từ trang 18 của *Kết nối tri thức Lớp 6 tập 1*, render 200 DPI, đo ngày
10/10/2026.
"""

import numpy as np
import pytest
import torch

from document.ocr.model import BBox, BlockKind, PageBlock
from document.ocr.page import _fill, _text_inside
from document.ocr.recognize import (
    READERS,
    EasyOcrReader,
    VietnameseReader,
    make_line_reader,
    padded,
    too_small,
)
from document.ocr.textline import split_tall_lines


def _line(top: int, bottom: int, left: int = 100, right: int = 500) -> BBox:
    """Một hộp dòng.

    Args:
        top: Mép trên.
        bottom: Mép dưới.
        left: Mép trái.
        right: Mép phải.

    Returns:
        Hộp bao.
    """
    return BBox(left, top, right, bottom)


def _block(kind: BlockKind, box: BBox) -> PageBlock:
    """Một khối chưa có chữ.

    Args:
        kind: Loại khối.
        box: Hộp bao.

    Returns:
        Khối rỗng chữ.
    """
    # [CODE CHẾT 2026-10-11] công thức đọc bằng gpt-4.1-mini lúc ra đề — xem plan 3a
    # return PageBlock(kind=kind, box=box, text="", latex=None)
    return PageBlock(kind=kind, box=box, text="")


def test_two_lines_stuck_together_are_cut_apart() -> None:
    """Đây là lý do chặng cắt dòng tồn tại, và nó dựng trên một phép đo thật.

    VietOCR nhận **một dòng một lần**. Cho nó một khối hai dòng thì nó trả về
    `'Thuận - Thực hiện phép chia hai số tự nhiên (chia hết và chia)'` -- bịa một từ ở đầu, nuốt
    phần sau, và **không báo gì cả**. Một câu nghe xuôi tai và sai là thứ tốn công nhất để phát
    hiện về sau, nên nó phải chết ở đây.
    """
    boxes = [_line(0, 30), _line(40, 70), _line(80, 140), _line(150, 180)]
    out = split_tall_lines(boxes)
    assert len(out) == 5
    assert (out[2].top, out[2].bottom) == (80, 110)
    assert (out[3].top, out[3].bottom) == (110, 140)


def test_a_line_that_is_merely_a_bit_taller_is_left_alone() -> None:
    """Chữ tiêu đề cao hơn chữ thân bài, và nó vẫn là **một** dòng.

    Cặp với test trên: cắt một tiêu đề làm đôi cũng hỏng y như để hai dòng dính nhau.
    """
    boxes = [_line(0, 30), _line(40, 70), _line(80, 128), _line(140, 170)]
    assert len(split_tall_lines(boxes)) == 4


def test_too_few_lines_to_know_what_is_usual() -> None:
    """Trung vị của hai con số không nói lên điều gì về một trang.

    Một trang chỉ có một hai dòng -- bìa, trang phụ bản -- thì để nguyên, vì phép xấp xỉ ở đây
    dựa hoàn toàn vào việc chiều cao dòng trên một trang sách rất đều.
    """
    assert len(split_tall_lines([_line(0, 20), _line(30, 300)])) == 2
    assert split_tall_lines([]) == []


def test_a_box_too_thin_to_hold_a_letter_is_refused() -> None:
    """VietOCR **không bao giờ** trả về chuỗi rỗng: một crop trắng vẫn ra một từ.

    Nên khối không có chữ phải bị chặn **trước** khi tới model, không lọc sau. Lọc sau là lọc một
    câu nghe hợp lý khỏi một trang mà nó không có mặt.
    """
    assert too_small(BBox(10, 10, 12, 60))
    assert too_small(BBox(10, 10, 60, 12))
    assert not too_small(BBox(10, 10, 60, 60))


def test_a_line_belongs_to_the_block_holding_its_centre() -> None:
    """Gán theo **tâm**, không theo phần giao.

    Một dòng thò ra ngoài khối vài điểm ảnh vẫn thuộc khối ấy; một dòng của khối bên cạnh thò
    vào thì không. Phép giao không phân biệt được hai ca đó.
    """
    block = _block(BlockKind.TEXT, BBox(100, 100, 600, 300))
    lines = [_line(110, 140), _line(150, 180, left=90, right=620), _line(400, 430)]
    texts = ["dòng một", "dòng hai thò ra hai bên", "dòng của khối khác"]
    assert _text_inside(block, lines, texts) == "dòng một dòng hai thò ra hai bên"


def test_lines_inside_a_block_are_joined_top_down_then_left_to_right() -> None:
    """Thứ tự dòng trong một khối là thứ tự đọc, không phải thứ tự detector trả về."""
    block = _block(BlockKind.TEXT, BBox(0, 0, 1000, 1000))
    lines = [_line(200, 230, 500, 700), _line(100, 130), _line(200, 230, 100, 300)]
    texts = ["phải", "trên", "trái"]
    assert _text_inside(block, lines, texts) == "trên trái phải"


def test_an_empty_read_does_not_leave_a_double_space() -> None:
    """Dòng engine không đọc được bị bỏ qua, không được biến thành một khoảng trắng.

    Khoảng trắng thừa đi thẳng vào CER, và nó đo cách ghép chuỗi chứ không đo chất lượng đọc.
    """
    block = _block(BlockKind.TEXT, BBox(0, 0, 1000, 1000))
    lines = [_line(100, 130), _line(200, 230), _line(300, 330)]
    assert _text_inside(block, lines, ["một", "", "ba"]) == "một ba"


def test_a_block_with_no_lines_inside_it_reads_as_empty() -> None:
    """Một khối hình hay một khối model đoán nhầm: chữ rỗng, không phải một exception."""
    block = _block(BlockKind.IMAGE, BBox(0, 0, 100, 100))
    assert _text_inside(block, [_line(500, 530)], ["ở chỗ khác"]) == ""
    assert _text_inside(block, [], []) == ""


def test_a_line_box_is_padded_so_the_marks_fit_inside() -> None:
    """Dấu tiếng Việt nằm **ngoài** thân chữ, mà hộp detector bám sát thân chữ.

    Đo 11/10/2026: đệm 15% chiều cao cắt CER của VietOCR từ 11,1% xuống 5,4%. Hộp cao 40 điểm
    ảnh thì nới 6 trên và 6 dưới, và 2 mỗi bên.
    """
    assert padded(BBox(100, 200, 500, 240), width=1000, height=2000) == BBox(98, 194, 502, 246)


def test_padding_never_reaches_past_the_page() -> None:
    """Dòng sát mép ảnh: nới ra ngoài là cắt một vùng không tồn tại."""
    assert padded(BBox(0, 0, 1000, 40), width=1000, height=40) == BBox(0, 0, 1000, 40)


def test_an_unknown_reader_fails_before_any_model_loads() -> None:
    """Gõ sai tên trong cấu hình phải chết ngay, không phải sau tám giây nạp model."""
    with pytest.raises(ValueError, match="tesseract"):
        make_line_reader("tesseract")
    assert set(READERS) == {"easyocr", "vietocr"}


class _FakeEasyOcr:
    """Đứng thay `easyocr.Reader`: ghi lại số luồng torch lúc được gọi."""

    def __init__(self, answers: list[list[str]]):
        self.answers = list(answers)
        self.threads_seen: list[int] = []
        self.boxes_seen: list[list[int]] = []

    def recognize(self, grey, horizontal_list, free_list, detail, reformat):  # noqa: ANN001
        self.threads_seen.append(torch.get_num_threads())
        self.boxes_seen.append(horizontal_list[0])
        return self.answers.pop(0)


class _FakeVietOcr:
    """Đứng thay `Predictor` của VietOCR."""

    def __init__(self) -> None:
        self.threads_seen: list[int] = []

    def predict_batch(self, crops):  # noqa: ANN001
        self.threads_seen.append(torch.get_num_threads())
        return [f"dòng {at}" for at in range(len(crops))]


def _bare(kind: type, model: object, threads: int):
    """Một reader thật mà không nạp model thật: chỉ thay đúng phần model."""
    reader = object.__new__(kind)
    reader._reader = model
    reader._threads = threads
    return reader


def test_easyocr_keeps_every_box_in_its_place() -> None:
    """Người gọi ghép chữ vào khối theo **vị trí**, nên một hộp rơi mất là lệch mọi dòng sau nó.

    Hộp quá nhỏ thì không được gọi tới model, và vẫn giữ chỗ bằng một chuỗi rỗng. Lời gọi thứ
    hai trả về `[]` là ca **phòng thủ**: review 11/10/2026 đọc mã nguồn 1.7.2 và thấy nó không xảy
    ra khi `too_small` đã chặn trước -- nhưng nếu một phiên bản sau trả về rỗng thì hộp ấy vẫn phải
    giữ đúng chỗ của nó.
    """
    fake = _FakeEasyOcr([["một"], [], ["ba"]])
    reader = _bare(EasyOcrReader, fake, threads=2)
    image = np.zeros((300, 600, 3), dtype=np.uint8)
    boxes = [_line(10, 40), BBox(5, 5, 7, 60), _line(50, 80), _line(90, 120)]
    assert reader.read_lines(image, boxes) == ["một", "", "", "ba"]
    assert len(fake.boxes_seen) == 3


def test_both_readers_take_back_the_threads_paddle_took() -> None:
    """Mỗi lời `predict` của paddle ép torch về **một** luồng, đo 11/10/2026.

    Detect chạy ngay trước nhận dạng, nên reader phải đặt lại số luồng **trong** `read_lines`.
    Thiếu dòng ấy thì nhận dạng chậm 1,5 tới 3 lần mà không gì báo.
    """
    before = torch.get_num_threads()
    image = np.zeros((300, 600, 3), dtype=np.uint8)
    try:
        easy = _FakeEasyOcr([["a"]])
        torch.set_num_threads(1)
        _bare(EasyOcrReader, easy, threads=3).read_lines(image, [_line(10, 40)])
        assert easy.threads_seen == [3]

        viet = _FakeVietOcr()
        torch.set_num_threads(1)
        out = _bare(VietnameseReader, viet, threads=3).read_lines(
            image, [_line(10, 40), BBox(5, 5, 7, 60), _line(50, 80)]
        )
        assert viet.threads_seen == [3]
        assert out == ["dòng 0", "", "dòng 1"]
    finally:
        torch.set_num_threads(before)


def test_a_formula_block_now_carries_the_ocr_text() -> None:
    """Từ 11/10/2026 công thức không được đọc lúc upload: khối `FORMULA` nhận chữ OCR như khối chữ.

    Đây là thay đổi hành vi duy nhất của bước bỏ PP-FormulaNet. Khối ấy vẫn ở lại -- nhãn của nó là
    gợi ý *trang này có toán* -- và chữ OCR của nó, dù lỗi với ký hiệu toán, vẫn vào ngữ cảnh LLM.
    """
    block = _block(BlockKind.FORMULA, BBox(0, 0, 1000, 1000))
    assert _fill(block, [_line(100, 130)], ["a : b = c"]).text == "a : b = c"


# [CODE CHẾT 2026-10-11] khối hình giữ chữ của các dòng nằm trong nó — plan 3c, D2
# def test_pictures_and_tables_stay_empty() -> None:
#     """Nhận dạng chữ **không bao giờ** trả về rỗng, nên một hình mà nhận chữ là chữ bịa."""
#     lines, texts = [_line(100, 130)], ["chữ của một dòng nằm đè lên hình"]
#     for kind in (BlockKind.IMAGE, BlockKind.TABLE):
#         assert _fill(_block(kind, BBox(0, 0, 1000, 1000)), lines, texts).text == ""


def test_tables_stay_empty() -> None:
    """Nhận dạng chữ **không bao giờ** trả về rỗng, nên một bảng mà nhận chữ là chữ bịa."""
    lines, texts = [_line(100, 130)], ["chữ của một dòng nằm đè lên bảng"]
    assert _fill(_block(BlockKind.TABLE, BBox(0, 0, 1000, 1000)), lines, texts).text == ""


def test_a_picture_keeps_the_lines_found_inside_it() -> None:
    """Banner mở chương là một khối hình, và chữ *CHƯƠNG* trong nó là cổng của D9 (plan 3c).

    Không crop nào được đưa cho bộ nhận dạng: dòng đã được detect và đọc từ trước, `_fill` chỉ thôi
    vứt nó. Dòng nằm ngoài hình vẫn không lọt vào.
    """
    picture = _block(BlockKind.IMAGE, BBox(0, 0, 1000, 500))
    lines, texts = [_line(100, 130), _line(800, 830)], ["CHƯƠNG", "dòng ở đoạn dưới"]
    assert _fill(picture, lines, texts).text == "CHƯƠNG"
