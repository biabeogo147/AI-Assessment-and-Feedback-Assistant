"""Hai việc PP-DocLayout **không** làm, và `layout.py` phải làm thay: gỡ trùng và sắp thứ tự đọc.

Không test nào ở đây nạp model. Model nặng 200 MB, mất bốn giây mỗi trang, và nó không phải thứ
đang được canh -- thứ đang được canh là phần chạy **sau** nó, và phần ấy thuần.

Mọi con số toạ độ dưới đây lấy từ trang 18 của *Kết nối tri thức Lớp 6 tập 1*, render 200 DPI,
đo ngày 10/10/2026. Dùng số thật chứ không số bịa, vì hai thuật toán ở đây chỉ sai ở những hình
dạng mà một ca bịa ra sẽ không có.
"""

from document.ocr.layout import blocks_from_boxes, in_reading_order
from document.ocr.model import BlockKind


def _box(label: str, left: int, top: int, right: int, bottom: int, score: float = 0.9) -> dict:
    """Một phần tử `boxes` như model trả về.

    Args:
        label: Nhãn PP-DocLayout.
        left: Mép trái.
        top: Mép trên.
        right: Mép phải.
        bottom: Mép dưới.
        score: Điểm tin cậy.

    Returns:
        Một dict cùng hình dạng với đầu ra thật.
    """
    return {"label": label, "coordinate": [left, top, right, bottom], "score": score}


def test_two_panels_side_by_side_are_read_one_after_the_other() -> None:
    """Ca đã làm hỏng bản đầu, và nó mở đầu **mọi** bài trong sách.

    Hai hộp *KHÁI NIỆM, THUẬT NGỮ* và *KIẾN THỨC, KĨ NĂNG* đặt cạnh nhau. Phép gom theo hàng --
    bản đầu của module này -- trả về dòng trái, dòng phải, dòng trái, dòng phải, trong khi người
    đọc hết hộp trái rồi mới sang hộp phải. Một phép sắp thuần theo mép trên cũng hỏng y vậy.

    XY-cut chọn đúng vì nó **so hai khe với nhau**: khe dọc giữa hai cột là 66 điểm ảnh, khe
    ngang rộng nhất giữa hai dòng là 19, nên nó cắt dọc.
    """
    boxes = [
        _box("paragraph_title", 167, 346, 426, 378),
        _box("paragraph_title", 666, 346, 889, 377),
        _box("text", 160, 397, 472, 426),
        _box("text", 657, 399, 1150, 428),
        _box("text", 158, 437, 590, 497),
        _box("text", 657, 441, 1350, 503),
    ]
    lefts = [one["coordinate"][0] for one in in_reading_order(boxes)]
    assert lefts == [167, 160, 158, 666, 657, 657]


def test_a_single_column_still_reads_top_to_bottom() -> None:
    """Cùng một luật phải cho thứ tự đúng ở bố cục một cột, nếu không nó chỉ chữa được một trang."""
    boxes = [
        _box("text", 132, 1293, 1376, 1363),
        _box("doc_title", 349, 128, 1068, 244),
        _box("number", 1394, 2001, 1428, 2029),
        _box("text", 133, 763, 1375, 831),
    ]
    tops = [one["coordinate"][1] for one in in_reading_order(boxes)]
    assert tops == [128, 763, 1293, 2001]


def test_overlapping_boxes_crowded_together_still_come_back_in_an_order() -> None:
    """Không có khe nào đáng tin thì vẫn phải trả về đủ số hộp, không được rơi cái nào.

    Đường lùi này không bao giờ đúng hơn XY-cut; việc của nó chỉ là **kết thúc**. Thiếu nó thì
    phép đệ quy cắt ra một nửa rỗng và lặp vô hạn trên đúng nửa kia.
    """
    boxes = [
        _box("text", 100, 100, 500, 200),
        _box("text", 110, 105, 510, 205),
        _box("text", 120, 110, 520, 210),
    ]
    assert len(in_reading_order(boxes)) == 3


def test_one_box_and_no_box_are_both_fine() -> None:
    """Trang trắng và trang một khối là hai ca thật, và cả hai không được ném."""
    assert in_reading_order([]) == []
    assert len(in_reading_order([_box("text", 1, 2, 3, 4)])) == 1


def test_the_same_rectangle_under_two_labels_counts_once() -> None:
    """Model trả về đúng một hình chữ nhật hai lần, mang hai nhãn khác nhau -- đo trên trang 18.

    `[322, 1130, 777, 1164]` ra một `text` và một `formula`. Giữ cả hai là đếm một khối hai lần:
    chữ của nó vào bảng điểm hai lượt, và phép đo thứ tự đọc thì đếm một cặp nghịch thế không có
    thật. Điểm cao hơn thắng.

    Cả hai điểm phải **trên** `_MIN_SCORE`. Bản đầu dùng 0,63 và 0,56, mà 0,56 dưới ngưỡng -- nên
    hộp thứ hai bị phép lọc điểm loại từ trước và **chưa bao giờ** tới được phép gỡ trùng. Review
    10/10/2026 chứng minh: đặt `_COVERED` thành 1,01, thành 0,05, hay đảo chiều sắp điểm, cả mười
    test vẫn xanh.
    """
    blocks = blocks_from_boxes(
        [_box("text", 322, 1130, 777, 1164, 0.63), _box("formula", 322, 1130, 777, 1164, 0.61)]
    )
    assert len(blocks) == 1
    assert blocks[0].kind is BlockKind.TEXT


def test_a_box_below_the_threshold_is_dropped() -> None:
    """Ngưỡng phải thật sự cắt, và nó cắt **trước** khi gỡ trùng.

    Cặp số dưới đây kẹp `_MIN_SCORE` giữa chúng. Ngưỡng từng là 0,60 và hạ về 0,50 ngày
    10/10/2026: review đo trên mười trang và thấy 0,60 cắt mất **chữ thật** -- chữ *"Giải"* ở
    p040 (0,550), *"Vì 18 ⋮ 6 nên ta có"* ở p046 (0,521) -- mà không chặn được khối rác nào.
    """
    assert blocks_from_boxes([_box("text", 10, 10, 100, 50, 0.49)]) == []
    assert len(blocks_from_boxes([_box("text", 10, 10, 100, 50, 0.51)])) == 1


def test_a_page_with_no_boxes_gives_no_blocks_instead_of_raising() -> None:
    """Trang nhiễu hay trang trắng: model trả về rỗng, và đường đi tiếp phải sống.

    Nếu nó ném thì một trang trắng giữa cuốn sách giết cả lượt đọc, và lỗi ấy sẽ trông như một
    tệp hỏng chứ không như một trang không có gì.
    """
    assert blocks_from_boxes([]) == []


def test_an_unknown_label_becomes_text_instead_of_disappearing() -> None:
    """PP-DocLayout có 23 nhãn, bảng của ta có 13.

    Một nhãn lạ là một khối **có chữ thật** trên trang. Bỏ nó đi là đánh rơi nội dung vì một lý
    do thuộc về bảng tra chứ không thuộc về trang.
    """
    blocks = blocks_from_boxes([_box("abstract", 10, 10, 100, 50)])
    assert len(blocks) == 1
    assert blocks[0].kind is BlockKind.TEXT


def test_blocks_come_back_without_text_yet() -> None:
    """Chặng này chỉ nói *ở đâu* và *là gì*. Chữ là việc của hai chặng sau."""
    blocks = blocks_from_boxes([_box("text", 10, 10, 100, 50)])
    assert blocks[0].text == ""
    # [CODE CHẾT 2026-10-11] công thức đọc bằng gpt-4.1-mini lúc ra đề — xem
    # `document-ocr-text-and-latex`
    # assert blocks[0].latex is None
    assert blocks[0].box.width == 90
    assert blocks[0].box.height == 40


def test_ocr_loads_torch_before_anything_else() -> None:
    """Thứ tự nạp là một ràng buộc thật, đo trên Windows: `import paddle, torch` ném WinError 127.

    Canh bằng cây cú pháp, không bằng `"torch" in sys.modules`. Bản đầu dùng phép kiểm kia và nó
    **không canh gì**: `paddleocr` tự kéo torch về, nên mệnh đề ấy đúng ngay cả khi dòng cần canh
    đã bị xoá. Review 10/10/2026 chứng minh bằng cách xoá hẳn dòng ấy -- cả mười test vẫn xanh.

    Thứ phải canh là **thứ tự**, và thứ tự thì đọc được từ chính file.
    """
    import ast
    from pathlib import Path

    import document.ocr

    source = Path(document.ocr.__file__).read_text(encoding="utf-8")
    imports = [
        node for node in ast.parse(source).body if isinstance(node, ast.Import | ast.ImportFrom)
    ]
    assert imports, "`document/ocr/__init__.py` phải nạp torch, và nó đang không nạp gì cả"
    first = imports[0]
    assert isinstance(first, ast.Import)
    assert [alias.name for alias in first.names] == ["torch"]


def test_a_formula_nested_inside_a_sentence_survives() -> None:
    """Ca review 10/10/2026 bắt được trên p041 và p046, và nó mất **im lặng**.

    Model trả về một khối `formula` nằm **trọn trong** khối `text` của câu chứa nó. Luật gỡ trùng
    cũ chỉ hỏi *"A có nằm trong B không"*, và một hộp con luôn cho 1,0 -- nên công thức bị xoá,
    và nó bị hạ cấp thành chữ. Từ 11/10/2026 công thức không được đọc lúc upload nữa, nhưng
    khối `FORMULA` vẫn phải sống: nó là gợi ý *trang này có toán* cho bước đọc công thức lúc ra đề.
    """
    blocks = blocks_from_boxes(
        [
            _box("text", 134, 549, 920, 581, 0.885),
            _box("formula", 778, 550, 912, 580, 0.641),
        ]
    )
    assert [one.kind for one in blocks] == [BlockKind.TEXT, BlockKind.FORMULA]


def test_the_higher_score_wins_a_duplicate() -> None:
    """Và luật ấy phải canh được, không chỉ được viết trong docstring.

    Đảo chiều sắp điểm ở `blocks_from_boxes` thì test này đỏ. Trước review thì nó không đỏ ở đâu.
    """
    blocks = blocks_from_boxes(
        [_box("text", 10, 10, 200, 60, 0.61), _box("formula", 10, 10, 200, 60, 0.92)]
    )
    assert [one.kind for one in blocks] == [BlockKind.FORMULA]


def test_the_page_number_is_read_last_even_when_it_sits_on_the_left() -> None:
    """Số trang là đồ nội thất, không phải một cột.

    Đo trên p041: một vết cắt dọc chia nửa dưới trang làm trái/phải, số trang nằm ở nửa **trái**,
    nên XY-cut trả nó ra **trước** một sơ đồ ở nửa phải. Người đọc không đọc số trang ở giữa
    trang. Toạ độ dưới đây lấy từ đúng trang ấy.
    """
    blocks = blocks_from_boxes(
        [
            _box("number", 86, 2002, 123, 2030, 0.78),
            _box("image", 1091, 1794, 1378, 1972, 0.90),
            _box("text", 133, 224, 622, 368, 0.90),
        ]
    )
    assert [one.kind for one in blocks][-1] is BlockKind.NUMBER


def test_a_running_header_is_read_first() -> None:
    """Cặp với test trên, ở đầu kia của trang."""
    blocks = blocks_from_boxes(
        [
            _box("text", 133, 900, 1300, 1000, 0.90),
            _box("header", 81, 70, 316, 305, 0.80),
        ]
    )
    assert [one.kind for one in blocks][0] is BlockKind.HEADER


def test_a_thousand_boxes_do_not_blow_the_stack() -> None:
    """Mỗi vết cắt có thể chỉ bóc một hộp, nên độ sâu đệ quy là O(n).

    Review 10/10/2026 dựng 1 200 hộp xếp bậc thang và nhận `RecursionError`. Một trang sách thật
    dưới 40 khối, nên chốt này không chạy trên dữ liệu thật -- nó có mặt để một trang nhiễu làm
    hỏng một trang chứ không giết cả lượt đọc một cuốn sách.
    """
    stair = [_box("text", at * 20, at * 20, at * 20 + 5, at * 20 + 5) for at in range(1200)]
    assert len(blocks_from_boxes(stair)) == 1200
