"""BE kiểm các mục của dàn ý Kriky viết (`draft-outline`, ADR-29, ADR-30). Hàm thuần.

`validate` từ chối thứ một job soạn câu không dùng được -- quá mười câu, mục rỗng, bài nguồn bịa --
bằng lời model sửa được. Lời Kriky thì BE không kiểm (hậu ký 20/10/2026 của ADR-30), và chữ của một
công thức cũng không.
"""

import pytest

from be.outline import stored, validate
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
        {"formulas": tuple(f"${n}$" for n in range(7))},
    ],
)
def test_an_item_a_teacher_cannot_review_is_refused(overrides: dict[str, object]) -> None:
    assert validate([_item(**overrides)], {2}) is not None


@pytest.mark.parametrize(
    "formula",
    [
        "Nếu $a<b$ và $b<c$ thì $a<c$",
        "$f'(x)>0 \\Rightarrow f(x)$ đồng biến trên khoảng đó",
        "a + b",
    ],
)
def test_a_formula_with_words_around_it_is_not_refused(formula: str) -> None:
    """Thử tay đầu-cuối 20/10/2026: luật *đúng một cặp `$`* trả về 50 trong 59 dàn ý. Công thức
    chỉ đi vào prompt soạn câu, nơi chữ quanh nó vẫn đọc được, nên BE không bắt hình dạng của nó."""
    assert validate([_item(formulas=(formula,))], {2}) is None


def test_a_book_outline_must_say_which_lesson_and_only_real_ones() -> None:
    assert "source_nodes" in (validate([_item(source_nodes=())], {2}) or "")
    assert "[99]" in (validate([_item(source_nodes=(2, 99))], {2}) or "")


def test_a_bookless_outline_points_at_no_lesson() -> None:
    assert validate([_item(source_nodes=())], None) is None
    assert validate([_item(source_nodes=(2,))], None) is not None


def test_an_item_without_formulas_is_fine() -> None:
    assert validate([_item(formulas=())], {2}) is None


def test_what_is_stored_is_exactly_the_items_shown() -> None:
    items = [_item(), _item(questions=2)]

    kept = stored(items, version=3, first=1, document_id="book")

    assert kept["total"] == 3
    assert [OutlineItem.model_validate(one) for one in kept["items"]] == items
    assert (kept["version"], kept["first"], kept["document_id"]) == (3, 1, "book")
