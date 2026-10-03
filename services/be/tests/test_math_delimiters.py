r"""Công thức toán phải được đánh dấu, và chỗ ràng buộc là code chứ không phải prompt.

Bốn prompt cấm LaTeX suốt một thời gian dài và **không dòng code nào thi hành**, nên model
cứ viết. Đo được trên panel thật, nguyên văn trước mặt giáo viên: `\int_{0}^{1}(3x^2 - 2x +
1)\, dx` và `\(\frac{1}{3}\)`.

Nay hướng đã đổi — toán **được** viết bằng LaTeX và màn hình dựng hình nó — nên câu hỏi cần
canh cũng đổi: không phải *"có LaTeX không"* mà là *"LaTeX có được đánh dấu không"*. Một
công thức không đánh dấu thì màn hình in nguyên xi, đúng như hôm nay; và một luật chỉ sống
trong prompt thì đã chứng minh được là không đủ, bốn lần.
"""

import pytest

from be.agent_gateway import AgentError, _math_is_loose, validate_question
from contracts import GeneratedOption, GeneratedQuestion, SolutionMethod


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        # Không toán thì không phải kiểm gì.
        ("Cho hàm số y = x mũ ba, hỏi gì đó", True),
        # Đánh dấu đủ.
        (r"Tính $\int_0^1 x\,dx$ rồi so sánh", True),
        (r"$\frac{1}{3}$ và $\sqrt{2}$", True),
        # Ca đã đo trên màn hình thật: lệnh trần, không cặp `$` nào.
        (r"Tính tích phân xác định \int_{0}^{1}(3x^2 - 2x + 1)\, dx.", False),
        # Ca thứ hai đã đo: dấu ngoặc LaTeX thay vì `$`.
        (r"Tính giá trị của \(I = \int_0^1 x\,dx\)", False),
        (r"\[\frac{1}{3}\]", False),
        # Một dấu `$` lẻ nghĩa là có một cặp chưa đóng — phần sau nó sẽ dựng hình nhầm.
        (r"Kết quả là $\frac{1}{3}", False),
        # Lệnh nằm **ngoài** trong khi một cặp khác đã đóng: lát chẵn mới là phần ngoài.
        (r"$x^2$ rồi \frac{1}{2}", False),
    ],
)
def test_math_outside_the_dollars_is_refused(text, ok) -> None:
    """Sáu ca, trong đó hai ca đầu của nhóm hỏng là hai ca đã thấy trên panel thật."""
    assert (_math_is_loose(text) == "") is ok


def _a_question(stem: str) -> GeneratedQuestion:
    """Một câu hỏi hợp lệ về mọi mặt khác, để phép kiểm toán là thứ duy nhất có thể đỏ."""
    return GeneratedQuestion(
        stem=stem,
        options=(
            GeneratedOption(label="A", text="đúng", is_correct=True),
            GeneratedOption(label="B", text="sai", is_correct=False, error_label="lỗi B"),
            GeneratedOption(label="C", text="sai", is_correct=False, error_label="lỗi C"),
        ),
        methods=(
            SolutionMethod(title="Cách 1", body="..."),
            SolutionMethod(title="Cách 2", body="..."),
        ),
        learning_objective="tích phân",
    )


def test_a_question_with_loose_math_never_reaches_the_database() -> None:
    """Phép kiểm đứng ở `validate_question`, tức **trước** khi câu hỏi được lưu.

    Chặn sau khi lưu thì công thức hỏng đã nằm trong đề, và đường duy nhất gỡ nó ra là sửa
    tay từng câu.
    """
    with pytest.raises(AgentError, match="not delimited"):
        validate_question(_a_question(r"Tính \int_0^1 x\,dx"))


def test_a_question_whose_math_is_delimited_passes() -> None:
    """Và một câu viết đúng thì đi qua — phép kiểm không được chặn cả hướng đúng."""
    validate_question(_a_question(r"Tính $\int_0^1 x\,dx$"))
