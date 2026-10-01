"""Những bảo đảm về schema mà hai service dựa vào.

Mấy test này tồn tại để bắt một thay đổi hợp đồng có thể âm thầm làm hỏng phía bên
kia của queue, không phải để kiểm tra chính pydantic.
"""

import pytest
from pydantic import ValidationError

from contracts import (
    GradingCompleted,
    GradingRequested,
    ReviewReason,
)


def _requested(**overrides) -> GradingRequested:
    payload = {
        "submission_id": "sub-1",
        "assessment_id": "asm-1",
        "question_id": "q-1",
        "student_id": "stu-1",
        "selected_option_id": "opt-b",
        "learning_objective": "fraction-addition",
    }
    payload.update(overrides)
    return GradingRequested(**payload)


def test_requested_round_trips_through_json() -> None:
    original = _requested(student_explanation="Em quy dong mau so truoc.")
    restored = GradingRequested.model_validate_json(original.model_dump_json())
    assert restored == original


def test_explanation_is_optional_because_not_every_question_asks_for_one() -> None:
    assert _requested().student_explanation is None


def test_completed_carries_no_routing_decision() -> None:
    """AGENT báo bằng chứng; quyết định xem lại thuộc về BE."""
    fields = set(GradingCompleted.model_fields)
    assert "needs_teacher_review" not in fields
    assert "review_reason" not in fields


def test_review_reason_covers_all_four_workflow_4_conditions() -> None:
    assert {reason.value for reason in ReviewReason} == {
        "low_confidence",
        "answer_explanation_conflict",
        "insufficient_evidence",
        "anomaly",
    }


@pytest.mark.parametrize("bad_value", [-0.1, 1.1])
def test_confidence_stays_within_zero_and_one(bad_value: float) -> None:
    with pytest.raises(ValidationError):
        GradingCompleted(
            submission_id="sub-1",
            score=1.0,
            confidence=bad_value,
            feedback_text="x",
        )
