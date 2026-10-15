"""BE kiểm dàn ý Kriky viết và dựng chữ giáo viên đọc (`draft-outline`, ADR-29). Hàm thuần.

Hai loại khẳng định. `validate` từ chối thứ giáo viên không duyệt được -- quá mười câu, mục rỗng,
công thức ngoài cặp `$`, bài nguồn bịa -- bằng lời model sửa được. Và `render` dựng **đúng từng ký
tự**: chữ trên màn hình là thứ job nhận, nên một chữ lệch là một lời hứa sai.
"""

import pytest

from be.outline import CLOSING, render, stored, validate
from contracts import OutlineItem


def _item(**overrides: object) -> OutlineItem:
    fields: dict[str, object] = {
        "questions": 1,
        "knowledge": "Thứ tự thực hiện phép tính",
        "formulas": ("$a + b \\cdot c$",),
        "approach": "Cho một biểu thức, chọn kết quả đúng",
        "source_nodes": (2,),
    }
    fields.update(overrides)
    return OutlineItem.model_validate(fields)


# ------------------------------------------------------------------ validate


def test_a_sound_outline_passes() -> None:
    assert validate([_item(), _item(questions=2, source_nodes=(3, 4))], {2, 3, 4}) is None


def test_more_than_ten_questions_in_one_go_is_refused() -> None:
    refusal = validate([_item(questions=6), _item(questions=5)], {2})

    assert refusal is not None and "11" in refusal


def test_the_cap_can_be_lower_when_the_draft_is_nearly_full() -> None:
    assert validate([_item(questions=3)], {2}, most=2) is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {"knowledge": "   "},
        {"approach": " "},
        {"knowledge": "x" * 601},
        {"approach": "x" * 601},
        {"formulas": ("$" + "x" * 200 + "$",)},
        {"formulas": ("a + b",)},
        {"formulas": ("$a$ và $b$",)},
        {"formulas": tuple(f"${n}$" for n in range(7))},
    ],
)
def test_an_item_a_teacher_cannot_review_is_refused(overrides: dict[str, object]) -> None:
    assert validate([_item(**overrides)], {2}) is not None


def test_a_book_outline_must_say_which_lesson_and_only_real_ones() -> None:
    assert "source_nodes" in (validate([_item(source_nodes=())], {2}) or "")
    assert "[99]" in (validate([_item(source_nodes=(2, 99))], {2}) or "")


def test_a_bookless_outline_points_at_no_lesson() -> None:
    assert validate([_item(source_nodes=())], None) is None
    assert validate([_item(source_nodes=(2,))], None) is not None


def test_an_item_without_formulas_is_fine() -> None:
    assert validate([_item(formulas=())], {2}) is None


# ------------------------------------------------------------------ render


def test_the_outline_shown_is_what_be_rendered_from_stored_items() -> None:
    items = [
        _item(),
        _item(
            questions=2,
            knowledge="Lũy thừa với số mũ tự nhiên",
            formulas=("$a^m \\cdot a^n = a^{m+n}$", "$a^m : a^n = a^{m-n}$"),
            approach="Rút gọn rồi so sánh hai lũy thừa",
            source_nodes=(3, 4),
        ),
    ]
    labels = {2: "Bài 2. Thứ tự (tr. 9–10)", 3: "Bài 3. Lũy thừa (tr. 11)", 4: "Luyện tập (tr. 12)"}

    shown = render("Mình đã đọc chương I.", items, labels, version=2)

    assert shown == "\n".join(
        [
            "Mình đã đọc chương I.",
            "",
            "Dàn ý — 3 câu (bản 2)",
            "",
            "Câu 1 · Thứ tự thực hiện phép tính",
            "  Công thức Kriky đề xuất: $a + b \\cdot c$",
            "  Cách làm: Cho một biểu thức, chọn kết quả đúng",
            "  Theo: Bài 2. Thứ tự (tr. 9–10)",
            "",
            "Câu 2–3 · Lũy thừa với số mũ tự nhiên",
            "  Công thức Kriky đề xuất: $a^m \\cdot a^n = a^{m+n}$; $a^m : a^n = a^{m-n}$",
            "  Cách làm: Rút gọn rồi so sánh hai lũy thừa",
            "  Theo: Bài 3. Lũy thừa (tr. 11); Luyện tập (tr. 12)",
            "",
            CLOSING,
        ]
    )


def test_an_outline_for_more_questions_counts_on_from_the_draft() -> None:
    shown = render("", [_item(questions=3, source_nodes=())], {}, version=1, first=11)

    assert shown.startswith("Dàn ý — 3 câu (bản 1)\n\nCâu 11–13 · ")
    assert "Theo:" not in shown


def test_formulas_are_always_called_kriky_s_never_the_book_s() -> None:
    shown = render("", [_item()], {2: "Bài 2"}, version=1)

    assert "Công thức Kriky đề xuất:" in shown
    assert "Công thức của sách" not in shown


def test_what_is_stored_is_exactly_the_items_shown() -> None:
    items = [_item(), _item(questions=2)]

    kept = stored(items, version=3, first=1, document_id="book")

    assert kept["total"] == 3
    assert [OutlineItem.model_validate(one) for one in kept["items"]] == items
    assert (kept["version"], kept["first"], kept["document_id"]) == (3, 1, "book")
