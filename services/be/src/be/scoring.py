"""Marking rules. BE owns them; AGENT never sees them.

Grading a multiple-choice answer is a comparison, so it lives here rather than
behind a queue (ADR-20). The three-level mark and the floor rule are ADR-16:
phase 1 sets the lowest a question can end at, and remediation may only lift it.
"""

from enum import StrEnum

# ADR-17 caps remediation at three rounds per question.
MAX_ROUNDS_PER_QUESTION = 3

MARK_CORRECT = 1.0
MARK_REMEDIATED = 0.5
MARK_WRONG = 0.0


class MarkReason(StrEnum):
    """Why a question sits at the mark it does.

    An enum rather than a sentence: the wording shown on hover differs between
    the "still open" and "already closed" states of phase 2, and ADR-16 keeps
    that wording in the interface. Sending prose from here would freeze it.
    """

    CORRECT_FIRST_TRY = "đúng-ngay"
    REMEDIATED = "chữa-được"
    NOT_YET_REMEDIATED = "chưa-chữa"
    ROUNDS_EXHAUSTED = "hết-vòng"


def mark_for_phase_one(is_correct: bool) -> tuple[float, MarkReason, bool]:
    """Mark one question at the end of phase 1.

    Args:
        is_correct: Whether the chosen option was the correct one.

    Returns:
        The mark, why it stands, and whether the question is closed. A correct
        answer closes immediately; a wrong one stays open because phase 2 can
        still lift it.
    """
    if is_correct:
        return MARK_CORRECT, MarkReason.CORRECT_FIRST_TRY, True
    return MARK_WRONG, MarkReason.NOT_YET_REMEDIATED, False


def mark_after_round(is_correct: bool, rounds_used: int) -> tuple[float, MarkReason, bool]:
    """Mark one question after a remediation round was submitted.

    Args:
        is_correct: Whether this round's answer was correct.
        rounds_used: Rounds spent on this question including the one just
            submitted.

    Returns:
        The mark, why it stands, and whether the question is closed. Getting it
        right closes the question at half credit; running out of rounds closes
        it at zero; anything else leaves it open for another round.
    """
    if is_correct:
        return MARK_REMEDIATED, MarkReason.REMEDIATED, True
    if rounds_used >= MAX_ROUNDS_PER_QUESTION:
        return MARK_WRONG, MarkReason.ROUNDS_EXHAUSTED, True
    return MARK_WRONG, MarkReason.NOT_YET_REMEDIATED, False


def total(marks: list[float]) -> float:
    """Sum a list of per-question marks.

    Args:
        marks: One mark per question of the assessment.

    Returns:
        The total, rounded to one decimal so 0.5 + 0.5 does not surface as
        0.9999999999999999 on a score sheet.
    """
    return round(sum(marks), 1)
