"""BE kiểm dàn ý Kriky viết và đối chiếu nó với lời Kriky (`draft-outline`, ADR-29, ADR-30).

Hàm thuần.

Hai loại khẳng định. `validate` từ chối thứ giáo viên không duyệt được -- quá mười câu, mục rỗng,
công thức ngoài cặp `$`, bài nguồn bịa -- bằng lời model sửa được. Và `check_message` đối chiếu
**nhẹ** lời Kriky với các mục: số câu, công thức, một câu hỏi -- không so từng chữ
(`kriky-writes-every-word`).
"""

import pytest

from be.outline import check_message, stored, validate
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


def test_a_loose_formula_is_named_in_the_refusal() -> None:
    """Thử tay 17/10/2026: lời chung không chỉ chỗ sai, model sửa mục này thì hỏng mục khác."""
    refusal = validate([_item(), _item(formulas=("Nếu $a<b$ và $b<c$ thì $a<c$",))], {2}) or ""

    assert refusal.startswith("mục 2:")
    assert "Nếu $a<b$ và $b<c$ thì $a<c$" in refusal


def test_a_book_outline_must_say_which_lesson_and_only_real_ones() -> None:
    assert "source_nodes" in (validate([_item(source_nodes=())], {2}) or "")
    assert "[99]" in (validate([_item(source_nodes=(2, 99))], {2}) or "")


def test_a_bookless_outline_points_at_no_lesson() -> None:
    assert validate([_item(source_nodes=())], None) is None
    assert validate([_item(source_nodes=(2,))], None) is not None


def test_an_item_without_formulas_is_fine() -> None:
    assert validate([_item(formulas=())], {2}) is None


# ------------------------------------------------------------ check_message (ADR-30)

_TWO = [
    _item(),
    _item(
        questions=2,
        knowledge="Lũy thừa với số mũ tự nhiên",
        formulas=("$a^m \\cdot a^n = a^{m+n}$", "$a^m : a^n = a^{m-n}$"),
        approach="Rút gọn rồi so sánh hai lũy thừa",
        source_nodes=(3, 4),
    ),
]


def test_a_message_in_kriky_s_own_words_passes() -> None:
    """Diễn đạt khác chữ các mục vẫn qua: tiêu chí là số câu, công thức, một câu hỏi."""
    said = (
        "Mình đã đọc chương I, đề xuất thế này:\n\n"
        "- **Câu 1:** tính giá trị biểu thức theo đúng thứ tự, kiểu $a+b\\cdot c$.\n"
        "- **Câu 2–3:** lũy thừa — nhân hai lũy thừa cùng cơ số $a^m\\cdot a^n=a^{m+n}$.\n\n"
        "Bạn thấy ổn không?"
    )

    assert check_message(said, _TWO) is None


_SPLIT = [_item(formulas=("$a = bq + r,\\ 0 \\le r < b$",))]


@pytest.mark.parametrize(
    ("formula", "said"),
    [
        ("$a = bq + r,\\ 0 \\le r < b$", "$a = b\\cdot q + r$ với $0 \\le r < b$"),
        ("$x + y = 5;\\; x - y = 1$", "$x+y=5$ và $x-y=1$"),
        ("$x + y = 5 \\quad x - y = 1$", "$x+y=5$ và $x-y=1$"),
        ("$x + y = 5 \\text{ và } x - y = 1$", "$x+y=5$ và $x-y=1$"),
        ("$x + y = 5,\\, x - y = 1$", "$x+y=5$ và $x-y=1$"),
        # Vế ngắn (`a`, `b)`) của danh sách biến hay khoảng kiểu Việt Nam không làm hỏng phép tách.
        ("$f'(x) \\ge 0,\\ \\forall x \\in (a; b)$", "$f'(x) \\ge 0$ với $\\forall x \\in (a; b)$"),
        (
            "$\\frac{a+b}{2} \\ge \\sqrt{ab},\\ a, b \\ge 0$",
            "$\\frac{a+b}{2} \\ge \\sqrt{ab}$ với $a, b \\ge 0$",
        ),
        ("$x, y > 0,\\ x+y=1$", "$x+y=1$ với $x, y > 0$"),
        # Toàn vế ngắn thì chỉ so nguyên vẹn được, và `\ ` chỉ là cách viết.
        ("$a,\\ b,\\ c,\\ d \\ge 0$", "$a, b, c, d \\ge 0$"),
    ],
)
def test_a_formula_the_message_splits_around_a_word_still_counts(formula: str, said: str) -> None:
    """Thử tay 17/10/2026 (quay GIF): mục gộp các vế vào một cặp `$` như `validate` đòi, lời tách
    thành nhiều cặp có chữ ở giữa -- vẫn là công thức ấy, không trả dàn ý về."""
    message = f"**Câu 1:** hệ thức {said}. Bạn thấy ổn không?"

    assert check_message(message, [_item(formulas=(formula,))]) is None


@pytest.mark.parametrize(
    ("formula", "said"),
    [
        # Chấm phẩy giữa hai chữ số không phải chỗ nối: tập hợp phải so nguyên vẹn.
        ("$A = \\{0;1;2;3;4\\}$", "$A = \\{0;1;2;4\\}$"),
        ("$A = \\{100;200;300\\}$", "$A = \\{100;2000;300\\}$"),
        # Dấu phẩy thập phân không phải chỗ nối: `2,5` không phải `25`.
        ("$m = 2,5\\ \\text{kg}$", "$m = 25$"),
        # Vế dài phải phủ phần lớn công thức: `d \ge 0` không thay được cho `a, b, c, d \ge 0`.
        ("$a, b, c, d \\ge 0$", "$d \\ge 0$"),
    ],
)
def test_a_short_or_decimal_part_is_not_a_joint(formula: str, said: str) -> None:
    message = f"**Câu 1–3:** {said}. Bạn thấy ổn không?"
    items = [_item(questions=3, formulas=(formula,))]

    assert "công thức nào của mục 1" in (check_message(message, items) or "")


def test_half_a_formula_in_the_message_is_still_missing() -> None:
    said = "**Câu 1:** phép chia có dư $a = bq + r$. Bạn thấy ổn không?"

    assert "công thức nào của mục 1" in (check_message(said, _SPLIT) or "")


@pytest.mark.parametrize(
    ("said", "why"),
    [
        ("Câu 1 về thứ tự $a + b \\cdot c$, rồi lũy thừa $a^m : a^n = a^{m-n}$. Ổn chứ?", "Câu 2"),
        ("Câu 1: $a + b \\cdot c$. Câu 2–4: $a^m : a^n = a^{m-n}$. Ổn chứ?", "Câu 4"),
        (
            "Câu 1: thứ tự phép tính. Câu 2–3: $a^m : a^n = a^{m-n}$. Ổn chứ?",
            "công thức nào của mục 1",
        ),
        ("Câu 1: $a + b \\cdot c$. Câu 2–3: $a^m : a^n = a^{m-n}$.", "hỏi"),
        ("   ", "trống"),
        # Thử tay 17/10/2026: số node chép từ `source_nodes` vào lời (luật 7).
        (
            "Câu 1: $a + b \\cdot c$. Câu 2–3: $a^m : a^n = a^{m-n}$. Bài nguồn: mục 2 (node 5). "
            "Ổn chứ?",
            "số node",
        ),
        (
            "Câu 1: $a + b \\cdot c$. Câu 2–3: $a^m : a^n = a^{m-n}$ (nodes 14, 15). Ổn chứ?",
            "số node",
        ),
        (
            "Câu 1: $a + b \\cdot c$. Câu 2–3: $a^m : a^n = a^{m-n}$, node số 5. Ổn chứ?",
            "số node",
        ),
        (
            "Câu 1: $a + b \\cdot c$. Câu 2–3: $a^m : a^n = a^{m-n}$ (source_nodes: [5]). Ổn?",
            "số node",
        ),
    ],
)
def test_a_message_that_drifts_from_its_items_goes_back_to_the_model(said: str, why: str) -> None:
    """Thiếu câu đầu của một mục, nhắc câu ngoài khoảng, mất hết công thức của một mục, hay không
    hỏi giáo viên: lý do về model, model viết lại trong cùng lượt."""
    wrong = check_message(said, _TWO)

    assert wrong is not None and why in wrong


def test_an_outline_for_more_questions_counts_on_from_the_draft() -> None:
    """Soạn thêm thì câu đầu là câu kế tiếp của đề: lời phải nói *Câu 11*, không *Câu 1*."""
    item = [_item(questions=3, source_nodes=())]

    assert check_message("Câu 11–13: $a + b \\cdot c$. Được không?", item, first=11) is None
    assert "Câu 11" in (
        check_message("Câu 1–3: $a + b \\cdot c$. Được không?", item, first=11) or ""
    )


def test_one_formula_written_another_way_still_counts() -> None:
    """Review pha 4: cùng một công thức, hai cách viết -- `a^2` và `a^{2}`, `\\dfrac` và `\\frac`,
    `(n-1)d` và `(n-1) \\cdot d` -- không bắt model viết lại."""
    items = [
        _item(formulas=("$x^{2} = \\frac{a}{b}$",)),
        _item(formulas=("$u_n = u_1 + (n-1) \\cdot d$",)),
    ]
    said = "Câu 1: $x^2 = \\dfrac{a}{b}$. Câu 2: $u_n=u_1+(n-1)d$. Ổn không?"

    assert check_message(said, items) is None


def test_more_and_replace_may_talk_about_questions_already_in_the_draft() -> None:
    """Câu **trước** câu đầu là câu đã có của đề: soạn thêm hay thay câu nói về nó là thường."""
    more = [_item(questions=3, source_nodes=())]
    replace = [_item(questions=1, source_nodes=())]

    assert (
        check_message(
            "Đề đang có câu 1–5, mình thêm Câu 6–8: $a + b \\cdot c$. Được không?", more, first=6
        )
        is None
    )
    assert (
        check_message("Câu 3 mới khác câu 2: $a + b \\cdot c$. Ổn không?", replace, first=3) is None
    )


@pytest.mark.parametrize(
    "said", ["Câu hỏi 1: $a + b \\cdot c$. Ổn không?", "Câu số 1: $a+b c$. Ổn không?"]
)
def test_other_common_ways_of_naming_a_question_are_heard(said: str) -> None:
    assert check_message(said, [_item()]) is None


def test_a_count_of_questions_is_not_a_question_number() -> None:
    """*"5 câu"* là một con số đếm: không bị đọc thành *Câu 5* ngoài khoảng."""
    said = "Dàn ý 5 câu, mình bắt đầu từ Câu 1: $a + b \\cdot c$ nhé, được không?"

    assert check_message(said, [_item()]) is None


def test_what_is_stored_is_exactly_the_items_shown() -> None:
    items = [_item(), _item(questions=2)]

    kept = stored(items, version=3, first=1, document_id="book")

    assert kept["total"] == 3
    assert [OutlineItem.model_validate(one) for one in kept["items"]] == items
    assert (kept["version"], kept["first"], kept["document_id"]) == (3, 1, "book")
