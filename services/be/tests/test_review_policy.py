"""Luật định tuyến của Teacher Review.

Đây là nhóm test quan trọng nhất trong service này: review policy chính là cổng
teacher-in-the-loop, và một regression ở đây sẽ âm thầm ngừng đẩy việc cho giáo
viên chứ không hỏng ra tiếng.
"""

from be.review_policy import decide_review
from contracts import GradingCompleted, ReviewReason

THRESHOLD = 0.7


def _evidence(**overrides) -> GradingCompleted:
    payload = {
        "submission_id": "sub-1",
        "score": 1.0,
        "confidence": 0.95,
        "feedback_text": "Dung roi.",
    }
    payload.update(overrides)
    return GradingCompleted(**payload)


def test_confident_and_consistent_result_skips_review() -> None:
    decision = decide_review(_evidence(), THRESHOLD)
    assert decision.needs_teacher_review is False
    assert decision.reason is None


def test_low_confidence_routes_to_teacher() -> None:
    decision = decide_review(_evidence(confidence=0.4), THRESHOLD)
    assert decision.needs_teacher_review is True
    assert decision.reason is ReviewReason.LOW_CONFIDENCE


def test_threshold_comparison_is_inclusive() -> None:
    """Một confidence nằm đúng ngay tại threshold thì vẫn phải đưa cho Teacher xem lại."""
    decision = decide_review(_evidence(confidence=THRESHOLD), THRESHOLD)
    assert decision.needs_teacher_review is True


def test_missing_evidence_routes_to_teacher_even_when_confident() -> None:
    decision = decide_review(_evidence(has_sufficient_evidence=False), THRESHOLD)
    assert decision.reason is ReviewReason.INSUFFICIENT_EVIDENCE


def test_answer_explanation_conflict_wins_over_low_confidence() -> None:
    """Đáp án đúng nhưng lập luận sai là tín hiệu nói lên nhiều hơn."""
    decision = decide_review(
        _evidence(confidence=0.1, answer_explanation_conflict=True),
        THRESHOLD,
    )
    assert decision.reason is ReviewReason.ANSWER_EXPLANATION_CONFLICT


def test_correct_answer_does_not_exempt_a_submission_from_review() -> None:
    """Được điểm tối đa, chỉ riêng điều đó, không được phép đi tắt qua cổng xem lại."""
    decision = decide_review(_evidence(score=1.0, confidence=0.2), THRESHOLD)
    assert decision.needs_teacher_review is True
