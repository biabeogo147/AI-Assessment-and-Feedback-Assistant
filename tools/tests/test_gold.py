"""Bộ kiểm nhãn vàng: mọi hình dạng hỏng phải thành một `GoldInvalid` nói rõ chỗ sai.

Hai thứ không có ở đây, cả hai có lý do:

- **Không đụng `data/`.** Nhãn thật nằm ngoài git, nên một lưới phụ thuộc vào nó sẽ xanh trên
  máy này và đỏ ở mọi nơi khác -- tức là không phải một lưới.
- **Không đụng filesystem**, kể cả `tmp_path`. Luật về hình dạng một trang nhãn không cần một
  cái file nào để phát biểu, và `gold.py` tách `parse_page` khỏi `load_page` đúng vì thế. Phép
  đo ngày 10/10/2026 còn cho một lý do thứ hai: trên máy này `tmp_path` ném `PermissionError`
  trước khi chạy một dòng test nào.
"""

import pytest

from ocr_bench.gold import BlockKind, GoldInvalid, collect, parse_page


def _page(blocks: list[dict], page: int = 5) -> dict:
    """Một trang nhãn hợp lệ, trừ những gì người gọi cố ý làm hỏng.

    Args:
        blocks: Danh sách khối.
        page: Số thứ tự trang.

    Returns:
        Payload của một trang.
    """
    return {"book": "L6T1", "page": page, "blocks": blocks}


def test_a_well_formed_page_keeps_its_blocks_in_order() -> None:
    """Thứ tự của `blocks` **là** nhãn cho phép đo thứ tự đọc, nên nó phải đi qua nguyên vẹn."""
    found = parse_page(
        _page(
            [
                {"kind": "doc_title", "text": "TẬP HỢP"},
                {"kind": "text", "text": "Gọi S là tập các hành tinh."},
                {"kind": "formula", "text": "C = A ∩ B", "latex": "C = A \\cap B"},
                {"kind": "number", "text": "8"},
            ]
        ),
        "L6T1_p005.json",
    )
    assert found.book == "L6T1"
    assert found.page == 5
    assert [one.kind for one in found.blocks] == [
        BlockKind.DOC_TITLE,
        BlockKind.TEXT,
        BlockKind.FORMULA,
        BlockKind.NUMBER,
    ]
    assert found.blocks[2].latex == "C = A \\cap B"


def test_text_is_normalised_to_nfc() -> None:
    """Hai cách viết cùng một chữ phải ra cùng một chuỗi.

    Đây là lỗi tốn kém nhất mà một bộ đo chữ Việt có thể mắc: `ế` dựng sẵn và `ế` tổ hợp hiện lên
    màn hình giống hệt nhau nhưng khác từng byte, nên một engine đọc đúng hoàn toàn vẫn ăn một
    CER khác 0 và không ai nhìn ra vì sao.
    """
    # Đúng ca **hai dấu** -- mũ cộng sắc -- chứ không phải một dấu: `ế` là `e` + U+0302 + U+0301.
    # Một dấu thì NFC cũng gộp, nhưng nó không phải chỗ tiếng Việt khác các thứ tiếng Latinh khác,
    # và nó cũng không phải chỗ PaddleOCR thủng từ điển.
    combining = "Kết nối tri thức"
    found = parse_page(_page([{"kind": "text", "text": combining}], 1), "x.json")
    assert found.blocks[0].text == "Kết nối tri thức"
    assert found.blocks[0].text != combining


def test_an_image_block_may_carry_no_text() -> None:
    """Hình và bảng không mang chữ, nên rỗng ở đó là hợp lệ."""
    found = parse_page(
        _page([{"kind": "image", "text": ""}, {"kind": "table", "text": ""}], 9), "x.json"
    )
    assert len(found.blocks) == 2


def test_an_empty_paragraph_is_a_half_finished_label() -> None:
    """Một khối chữ rỗng là một lần đánh nhãn bỏ dở, không phải một trang trắng.

    Để nó lọt qua thì bộ đo sẽ chấm engine 0 điểm ở đúng khối ấy, và con số đó trông y hệt một
    engine tệ. Lỗi của người đánh nhãn phải kêu ở đây, không phải nằm im trong bảng điểm.
    """
    with pytest.raises(GoldInvalid, match="bỏ dở"):
        parse_page(_page([{"kind": "text", "text": "   "}]), "x.json")


def test_a_formula_without_latex_is_refused() -> None:
    """`latex` là thước cho bước đọc công thức bằng VLM lúc ra đề, nên thiếu nó là vô dụng."""
    with pytest.raises(GoldInvalid, match="phải có `latex`"):
        parse_page(_page([{"kind": "formula", "text": "x + 1"}]), "x.json")


def test_only_a_formula_may_carry_latex() -> None:
    """Toán **nội dòng** ở lại trong `text`, không được lén thành một trường `latex`.

    Luật này tồn tại vì nó là chỗ hai người đánh nhãn dễ làm khác nhau nhất, và lúc ấy bộ đo
    không còn so cùng một thứ nữa.
    """
    with pytest.raises(GoldInvalid, match="chỉ khối `formula`"):
        parse_page(_page([{"kind": "text", "text": "Tập X", "latex": "X"}]), "x.json")


def test_an_unknown_kind_names_the_ones_that_exist() -> None:
    """Báo lỗi phải liệt kê các nhãn hợp lệ: người đọc nó vừa đánh nhãn xong và cần sửa ngay."""
    with pytest.raises(GoldInvalid, match="paragraph_title"):
        parse_page(_page([{"kind": "tieu_de", "text": "x"}]), "x.json")


def test_an_error_names_the_file_and_the_block() -> None:
    """Năm mươi file nhân mười khối: thông báo phải chỉ đúng một chỗ, không phải "ở đâu đó"."""
    with pytest.raises(GoldInvalid, match=r"L6T1_p042\.json: blocks\[1\]"):
        parse_page(
            _page([{"kind": "text", "text": "ổn"}, {"kind": "text", "text": ""}]),
            "L6T1_p042.json",
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"page": 1, "blocks": [{"kind": "text", "text": "x"}]},
        {"book": "L6T1", "blocks": [{"kind": "text", "text": "x"}]},
        {"book": "L6T1", "page": 0, "blocks": [{"kind": "text", "text": "x"}]},
        {"book": "L6T1", "page": 1, "blocks": []},
        ["khong phai object"],
    ],
    ids=["thiếu book", "thiếu page", "page bằng 0", "blocks rỗng", "gốc là list"],
)
def test_a_page_missing_its_frame_is_refused(payload: object) -> None:
    """Năm cách một trang nhãn có thể thiếu khung, và cả năm phải đỏ."""
    with pytest.raises(GoldInvalid):
        parse_page(payload, "x.json")


def test_pages_come_back_sorted_by_number_not_by_file_name() -> None:
    """Sắp theo con số thật là thứ duy nhất đúng với cả hai cách đặt tên file.

    Tên có đệm 0 thì hai cách sắp trùng nhau; tên không đệm thì `p10` đứng trước `p2`.
    """
    pages = [
        ("L6T1_p10.json", parse_page(_page([{"kind": "text", "text": "mười"}], 10), "a")),
        ("L6T1_p2.json", parse_page(_page([{"kind": "text", "text": "hai"}], 2), "b")),
    ]
    assert [one.page for one in collect(pages)] == [2, 10]


def test_two_files_about_one_page_is_refused() -> None:
    """Hai file cùng nói về một trang là dấu của một lần chép tay, và nó đếm trang ấy hai lần."""
    one = parse_page(_page([{"kind": "text", "text": "a"}], 11), "a")
    two = parse_page(_page([{"kind": "text", "text": "b"}], 11), "b")
    with pytest.raises(GoldInvalid, match="cùng nói về trang 11"):
        collect([("L6T1_p011.json", one), ("L6T1_p011_ban_sao.json", two)])


def test_an_empty_set_is_refused_not_silently_empty() -> None:
    """Không file nhãn nào phải là một lỗi, không phải một bảng điểm trống trên không trang nào.

    Đây đúng là hình dạng xảy ra trên một máy sạch, nơi `data/` chưa bao giờ tồn tại.
    """
    with pytest.raises(GoldInvalid, match="không có file nhãn nào"):
        collect([])
