"""`validate_retry` (ADR-17): câu của một lượt chữa lỗi không được là câu gốc, kể cả khi có đuôi.

Plan `backlog-tier-1`: AGENT từng trả câu gốc kèm *"(đề thay số cho lượt N)"* khi không có biến thể;
phép so khớp nguyên văn cho nó qua, và học sinh làm lại đúng câu cũ.
"""

import pytest

from be.agent_gateway import AgentError, validate_retry
from contracts import GeneratedOption, GeneratedQuestion, SolutionMethod

ORIGIN = "Cho hàm số y = x³ − 3x. Hàm số đồng biến trên khoảng nào?"


def _question(stem: str) -> GeneratedQuestion:
    return GeneratedQuestion(
        stem=stem,
        options=(
            GeneratedOption(label="A", text="(−∞; −1)", is_correct=True),
            GeneratedOption(label="B", text="(−1; 1)", error_label="đọc ngược khoảng"),
        ),
        methods=(SolutionMethod(title="Một", body="..."), SolutionMethod(title="Hai", body="...")),
        learning_objective="đơn điệu",
    )


@pytest.mark.parametrize(
    "stem",
    [
        ORIGIN,
        f"{ORIGIN} (đề thay số cho lượt 2)",
        f"  {ORIGIN.upper()}   ",
    ],
)
def test_the_origin_with_or_without_a_tail_is_refused(stem: str) -> None:
    with pytest.raises(AgentError, match="repeats the question it replaces"):
        validate_retry(_question(stem), ORIGIN, [])


def test_an_earlier_round_with_a_tail_is_refused() -> None:
    earlier = "Cho hàm số y = x³ − 12x. Hàm số nghịch biến trên khoảng nào?"
    with pytest.raises(AgentError, match="earlier round"):
        validate_retry(_question(f"{earlier} (lượt 3)"), ORIGIN, [earlier])


def test_a_genuinely_new_question_passes() -> None:
    validate_retry(
        _question("Cho hàm số y = x³ − 12x. Hàm số nghịch biến trên khoảng nào?"), ORIGIN, []
    )
