"""Shared vocabulary for the BE/AGENT contract.

Naming follows the Phase 1 glossary in docs/overview/project-overview.md so the
code and the business documentation stay readable against each other.
"""

from enum import StrEnum


class AssessmentType(StrEnum):
    """Kind of assessment a submission belongs to.

    business-workflows.md distinguishes routine practice from high-stakes work,
    because the two justify different amounts of Teacher involvement.
    """

    ROUTINE = "routine"
    HIGH_STAKES = "high_stakes"


class ReviewReason(StrEnum):
    """Why a graded submission was routed into the Teacher Review Queue.

    The four members mirror the four control points listed in
    business-workflows.md Workflow 4. Confidence is only one of them, so a
    boolean flag alone would lose information the Teacher needs.
    """

    LOW_CONFIDENCE = "low_confidence"
    ANSWER_EXPLANATION_CONFLICT = "answer_explanation_conflict"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ANOMALY = "anomaly"
