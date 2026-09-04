"""Grading handlers.

Everything in this module is a placeholder standing in for an LLM call. The
grading rules below are deliberately trivial and deterministic so the end-to-end
path can be exercised without a model, and so each Teacher Review condition has
a reproducible way to fire.

What is NOT a placeholder is the shape of the output. This handler reports
evidence and stops there. It does not compare confidence against a threshold and
does not decide that a Teacher should look at the result -- that belongs to
be/review_policy.py, per business-workflows.md Workflow 3.
"""

import logging

from contracts import GradingCompleted, GradingRequested

logger = logging.getLogger(__name__)

# Placeholder answer key. A real implementation resolves this from the question.
_CORRECT_OPTION_SUFFIX = "a"

# Below this length an explanation is treated as too thin to judge reasoning by.
_MIN_EXPLANATION_CHARS = 15


def grade(request: GradingRequested) -> GradingCompleted:
    """Grade one submission and report what was observed.

    Placeholder rules, chosen so every downstream review path is reachable:
      - The option whose id ends in "a" is correct.
      - A submission with no explanation yields low confidence, because the
        multiple-choice answer alone says little about the student's reasoning.
      - A blank explanation is reported as insufficient evidence.
      - A correct answer defended by a very short explanation is flagged as a
        possible answer/explanation conflict, the guessing case.

    Args:
        request: The submission to grade.

    Returns:
        Evidence for this submission. Never a routing decision.

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
    """arq task entry point for grading one submission.

    Args:
        ctx: arq job context. Unused; kept because arq passes it positionally.
        payload: A serialised GradingRequested as written by BE.

    Returns:
        A serialised GradingCompleted, which arq stores for BE to read back.

    Raises:
        pydantic.ValidationError: If the payload does not match the contract,
            which means the two services are running different contract versions.

    Side effects:
        None beyond logging. AGENT writes to no database.
    """
    request = GradingRequested.model_validate(payload)
    return grade(request).model_dump(mode="json")
