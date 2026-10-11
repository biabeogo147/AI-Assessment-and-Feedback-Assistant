"""Bản ghi mỗi lượt benchmark: `data/run-<n>/<model>/`.

Chỉ hai luật thuần được canh ở đây -- đánh số và đặt tên. Phần ghi file không có test vì
`tmp_path` không dùng được trên máy dev này (thư mục tạm của pytest bị khoá), và một test chạm
`data/` thật thì sẽ để lại rác trong đúng chỗ đang giữ bản ghi.
"""

from ocr_bench.run import model_tag, next_run


def test_the_first_run_is_number_one() -> None:
    """`data/` chỉ có sách, nhãn và cache: chưa lượt nào được ghi."""
    assert next_run(["gold", "cache"]) == 1


def test_a_new_run_goes_after_the_largest() -> None:
    """So **theo số**, không theo chữ: `run-10` lớn hơn `run-9`."""
    assert next_run(["run-9", "run-10", "run-2"]) == 11


def test_a_gap_is_never_filled() -> None:
    """`run-2` đã bị xoá vẫn có thể đang được plan nhắc tới; dùng lại số ấy là gán hai lượt chạy
    khác nhau cho cùng một cái tên."""
    assert next_run(["run-1", "run-3"]) == 4


def test_only_exact_run_folders_count() -> None:
    """Thư mục tình cờ bắt đầu bằng `run-` không được làm nhảy số."""
    assert next_run(["run-x", "run-5-old", "rerun-7", "run-2"]) == 3


def test_each_reader_gets_its_own_folder() -> None:
    """Hai lựa chọn nằm cạnh nhau trong một lượt; cấu hình VietOCR là một phần của tên, vì đổi
    nó là đổi chữ đọc ra."""
    assert model_tag("easyocr", "vgg_seq2seq") == "easyocr"
    assert model_tag("vietocr", "vgg_seq2seq") == "vietocr-vgg_seq2seq"
    assert model_tag("vietocr", "vgg_transformer") == "vietocr-vgg_transformer"


def test_text_inside_a_picture_is_not_scored() -> None:
    """Từ đường `text2` (plan 3c, D2), khối hình mang chữ OCR nằm trong nó, còn nhãn vàng để khối
    hình rỗng. Chấm chữ ấy thì CER của đường mới tăng âm thầm, và bảng số không còn so được với các
    lượt trước."""
    from document.ocr.model import BlockKind
    from ocr_bench.gold import GoldBlock, GoldPage
    from ocr_bench.run import _score_page

    gold = GoldPage(
        "L6T1",
        6,
        (
            GoldBlock(BlockKind.IMAGE, "", None),
            GoldBlock(BlockKind.TEXT, "Khi tính toán", None),
        ),
    )
    read = {
        "blocks": [
            {"kind": "image", "text": "CHƯƠNG sấ HỌc 4v 12"},
            {"kind": "text", "text": "Khi tính toán"},
        ],
        "seconds": {"layout": 1.0},
    }
    assert _score_page(gold, read)["cer"] == 0
