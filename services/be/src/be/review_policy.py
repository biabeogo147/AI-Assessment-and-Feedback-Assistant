"""Teacher Review Queue routing.

This module is the teacher-in-the-loop gate. It lives in BE on purpose:
business-workflows.md separates the step where the system produces a result from
the step where the system decides that a Teacher must look at it, and
project-overview.md requires that the second step stay outside the AI service.

AGENT reports evidence. Nothing here runs inside AGENT.
"""

from pydantic import BaseModel

from contracts import GradingCompleted, ReviewReason


class ReviewDecision(BaseModel):
    """Outcome of applying the review policy to one graded submission.

    Attributes:
        needs_teacher_review: Whether the submission enters the Teacher Review Queue.
        reason: Which control point triggered it, or None when no review is needed.
    """

    needs_teacher_review: bool
    reason: ReviewReason | None = None


def decide_review(result: GradingCompleted, confidence_threshold: float) -> ReviewDecision:
    """Decide whether a graded submission needs a Teacher to look at it.

    Implements three of the four control points in business-workflows.md
    Workflow 4. The fourth, ReviewReason.ANOMALY, needs a student's history to
    detect and is therefore not reachable until submissions are persisted; it
    stays in the enum so adding it later does not change the contract.

    Conditions are checked most specific first: a correct answer backed by wrong
    reasoning is more informative to a Teacher than a merely low confidence
    score, so it wins when both apply.

    Args:
        result: Evidence produced by AGENT for one submission.
        confidence_threshold: Confidence at or below which review is required.
            Comparison is inclusive so that a threshold of 0.0 still reviews a
            result the model had no confidence in at all.

    Returns:
        A ReviewDecision naming the triggering condition, or one with
        needs_teacher_review set to False when none applies.

    Side effects:
        None. The caller is responsible for acting on the decision.
    """
    if result.answer_explanation_conflict:
        return ReviewDecision(
            needs_teacher_review=True,
            reason=ReviewReason.ANSWER_EXPLANATION_CONFLICT,
        )

    if not result.has_sufficient_evidence:
        return ReviewDecision(
            needs_teacher_review=True,
            reason=ReviewReason.INSUFFICIENT_EVIDENCE,
        )

    if result.confidence <= confidence_threshold:
        return ReviewDecision(
            needs_teacher_review=True,
            reason=ReviewReason.LOW_CONFIDENCE,
        )

    return ReviewDecision(needs_teacher_review=False)
