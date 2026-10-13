"""Thước đo cây mục lục: test của **thước**, thứ duy nhất `check` canh được mà không cần `data/`."""

from pageindex_bench.score import TreeNode, score


def _row(rows, level):
    return next(row for row in rows if row.level == level)


def test_an_ocr_spelling_error_is_not_a_tree_error() -> None:
    """*"PHÉP CÔNG"* cho *"PHÉP CỘNG"* là lỗi của OCR; thước của cây không được tính nó."""
    gold = [TreeNode(2, "PHÉP CỘNG VÀ PHÉP TRỪ SỐ TỰ NHIÊN", 16)]
    built = [TreeNode(2, "PHÉP CÔNG VÀ PHÉP TRỪ SỐ TƯ NHIÊN", 16)]
    assert _row(score(gold, built), 2).matched == 1


def test_a_node_on_the_wrong_level_is_both_missing_and_extra() -> None:
    gold = [TreeNode(3, "HỆ THẬP PHÂN", 10)]
    built = [TreeNode(2, "HỆ THẬP PHÂN", 10)]
    rows = score(gold, built)
    assert (_row(rows, 3).recall, _row(rows, 2).precision) == (0.0, 0.0)


def test_a_lost_node_cannot_steal_its_neighbour() -> None:
    """Bài 1 thật: OCR mất mục 1, còn mục 2 ở cùng trang. Ghép theo thứ tự cây vàng thì mục 1 giành
    nút của mục 2, và thước báo sai **cả hai**."""
    gold = [
        TreeNode(3, "TẬP HỢP VÀ PHẦN TỬ CỦA TẬP HỢP", 7),
        TreeNode(3, "MÔ TẢ MỘT TẬP HỢP", 7),
    ]
    built = [TreeNode(3, "MÔ TÀ MỘT TẬP HỢP", 7)]
    row = _row(score(gold, built), 3)
    assert (row.matched, row.precision) == (1, 1.0)


def test_pages_may_slip_by_one_but_not_more() -> None:
    gold = [TreeNode(2, "LUYỆN TẬP CHUNG", 21)]
    assert _row(score(gold, [TreeNode(2, "LUYỆN TẬP CHUNG", 22)]), 2).matched == 1
    assert _row(score(gold, [TreeNode(2, "LUYỆN TẬP CHUNG", 23)]), 2).matched == 0


def test_an_unscored_range_is_left_out_on_both_sides() -> None:
    gold = [TreeNode(1, "HOẠT ĐỘNG THỰC HÀNH TRẢI NGHIỆM", 112)]
    built = [TreeNode(3, "MỘT SỐ PHÍM CHỨC NĂNG CHÍNH", 120)]
    row = _row(score(gold, built, [(3, 112, 125)]), 3)
    assert (row.gold, row.built) == (0, 0)
