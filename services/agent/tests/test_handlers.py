"""Hành vi của handler chấm bài cũ.

ADR-20 đã chuyển việc chấm trắc nghiệm vào BE. Các test này còn ở đây vì những invariant
chúng canh -- trên hết là "AGENT không phát ra quyết định định tuyến nào" -- sống lâu hơn
cái đường mà chúng chạy trên.

Các luật tính điểm đang được test chỉ là tạm và sẽ được thay bằng một lần gọi model thật.
Tính chất về ranh giới mà chúng mã hoá thì không phải thứ tạm, nên nó được test một cách
tường minh: AGENT không bao giờ được phát ra một quyết định định tuyến.
"""

import pytest

from agent.legacy_grading import grade, grade_submission
from contracts import GradingRequested


def _request(**overrides) -> GradingRequested:
    payload = {
        "submission_id": "sub-1",
        "assessment_id": "asm-1",
        "question_id": "q-1",
        "student_id": "stu-1",
        "selected_option_id": "opt-a",
        "student_explanation": "Em quy dong mau so roi cong tu so.",
        "learning_objective": "fraction-addition",
    }
    payload.update(overrides)
    return GradingRequested(**payload)


def test_agent_emits_no_routing_decision() -> None:
    """Cổng teacher-in-the-loop phải nằm ngoài service AI."""
    result = grade(_request()).model_dump()
    assert "needs_teacher_review" not in result
    assert "review_reason" not in result


def test_correct_answer_with_reasoning_scores_full_and_is_confident() -> None:
    result = grade(_request())
    assert result.score == 1.0
    assert result.confidence > 0.9
    assert result.misconception_code is None


def test_wrong_answer_reports_a_misconception_code() -> None:
    result = grade(_request(selected_option_id="opt-c"))
    assert result.score == 0.0
    assert result.misconception_code == "mis-opt-c"


def test_missing_explanation_lowers_confidence() -> None:
    """Không có lập luận thì một đáp án trắc nghiệm đứng một mình là bằng chứng yếu."""
    result = grade(_request(student_explanation=None))
    assert result.confidence < 0.7
    assert result.has_sufficient_evidence is True


def test_blank_explanation_is_reported_as_insufficient_evidence() -> None:
    result = grade(_request(student_explanation="   "))
    assert result.has_sufficient_evidence is False


def test_correct_answer_with_a_thin_explanation_is_flagged_as_conflict() -> None:
    result = grade(_request(student_explanation="doan"))
    assert result.answer_explanation_conflict is True


@pytest.mark.asyncio
async def test_task_round_trips_dicts_for_the_queue() -> None:
    payload = _request().model_dump(mode="json")
    result = await grade_submission({}, payload)
    assert result["submission_id"] == "sub-1"
    assert isinstance(result, dict)
