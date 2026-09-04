"""Grading handler behaviour.

The scoring rules under test are placeholders and will be replaced by a real
model call. The boundary property they encode is not a placeholder, so it is
tested explicitly: AGENT must never emit a routing decision.
"""

import pytest

from agent.handlers import grade, grade_submission
from contracts import AssessmentType, GradingRequested


def _request(**overrides) -> GradingRequested:
    payload = {
        "submission_id": "sub-1",
        "assessment_id": "asm-1",
        "question_id": "q-1",
        "student_id": "stu-1",
        "assessment_type": AssessmentType.ROUTINE,
        "selected_option_id": "opt-a",
        "student_explanation": "Em quy dong mau so roi cong tu so.",
        "learning_objective": "fraction-addition",
    }
    payload.update(overrides)
    return GradingRequested(**payload)


def test_agent_emits_no_routing_decision() -> None:
    """The teacher-in-the-loop gate must stay outside the AI service."""
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
    """Without reasoning the multiple-choice answer alone is weak evidence."""
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
