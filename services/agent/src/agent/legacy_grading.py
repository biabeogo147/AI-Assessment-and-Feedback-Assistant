"""The pre-ADR-20 grading path, kept alive and kept apart.

ADR-20 moved multiple-choice grading into BE, where the answer key lives and
where a comparison does not need a queue round trip. Nothing in the core flow
calls this module. It survives for one reason: the Teacher Review Queue (UC-05)
is still undesigned, and three invariants in `AGENTS.md` are guarded by tests
that exercise this code. Deleting it would quietly retire those guards.

It lives in its own module so nobody reads `handlers.py` and concludes that
AGENT still grades.
"""

import logging

from contracts import GradingCompleted, GradingRequested

logger = logging.getLogger(__name__)

# Placeholder answer key from before BE held one.
_CORRECT_OPTION_SUFFIX = "a"

# Below this length an explanation is treated as too thin to judge reasoning by.
_MIN_EXPLANATION_CHARS = 15


def grade(request: GradingRequested) -> GradingCompleted:
    """Grade one submission and report what was observed.

    Args:
        request: The submission to grade.

    Returns:
        Evidence for this submission. Never a routing decision -- that property
        is the reason this function is still under test.

    Side effects:
        Logs one line per graded submission.
    """
    is_correct = request.selected_option_id.endswith(_CORRECT_OPTION_SUFFIX)
    explanation = (request.student_explanation or "").strip()

    has_sufficient_evidence = True
    conflict = False

    if request.student_explanation is None:
        confidence = 0.55
        feedback = "Chua co phan giai thich nen he thong chi danh gia duoc dap an."
    elif not explanation:
        confidence = 0.30
        has_sufficient_evidence = False
        feedback = "Phan giai thich de trong nen chua du can cu de danh gia."
    elif is_correct and len(explanation) < _MIN_EXPLANATION_CHARS:
        confidence = 0.60
        conflict = True
        feedback = "Dap an dung nhung phan giai thich chua the hien duoc cach lam."
    elif is_correct:
        confidence = 0.92
        feedback = "Dap an dung va cach lam hop ly."
    else:
        confidence = 0.88
        feedback = "Dap an chua dung. Xem lai buoc quy dong mau so."

    result = GradingCompleted(
        submission_id=request.submission_id,
        score=1.0 if is_correct else 0.0,
        confidence=confidence,
        misconception_code=None if is_correct else f"mis-{request.selected_option_id}",
        feedback_text=feedback,
        answer_explanation_conflict=conflict,
        has_sufficient_evidence=has_sufficient_evidence,
    )

    logger.info(
        "graded submission=%s score=%.1f confidence=%.2f",
        result.submission_id,
        result.score,
        result.confidence,
    )
    return result


async def grade_submission(ctx: dict, payload: dict) -> dict:
    """arq entry point for the legacy grading task.

    Args:
        ctx: arq job context. Unused; arq passes it positionally.
        payload: A serialised GradingRequested.

    Returns:
        A serialised GradingCompleted.

    Side effects:
        Logs that a superseded path ran.
    """
    request = GradingRequested.model_validate(payload)
    logger.warning("legacy grading used for %s; ADR-20 moved grading to BE", request.submission_id)
    return grade(request).model_dump(mode="json")
