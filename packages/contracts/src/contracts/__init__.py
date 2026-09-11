"""Shared message contract between BE and AGENT.

Two families live here. The authoring messages carry the core two-phase flow:
BE asks AGENT to write questions, to write the question of a remediation round,
and to take one turn in the tutoring conversation.

`GradingRequested` and `GradingCompleted` are the older grading pair. They are
**legacy**: ADR-20 moved multiple-choice grading into BE, so nothing in the core
flow enqueues them. They stay until the Teacher Review Queue (UC-05) is designed
and can say what it actually needs. Do not add fields to them.
"""

from contracts.authoring import (
    DRAFT_ASSESSMENT_TASK,
    EXPLAIN_TURN_TASK,
    GENERATE_RETRY_QUESTION_TASK,
    ChatTurn,
    DraftAssessmentCompleted,
    DraftAssessmentRequested,
    ExplainTurnCompleted,
    ExplainTurnRequested,
    GeneratedOption,
    GeneratedQuestion,
    RetryQuestionCompleted,
    RetryQuestionRequested,
    SolutionMethod,
)
from contracts.enums import ReviewReason
from contracts.messages import (
    GRADE_SUBMISSION_TASK,
    SCHEMA_VERSION,
    GradingCompleted,
    GradingRequested,
)

__all__ = [
    "DRAFT_ASSESSMENT_TASK",
    "EXPLAIN_TURN_TASK",
    "GENERATE_RETRY_QUESTION_TASK",
    "GRADE_SUBMISSION_TASK",
    "SCHEMA_VERSION",
    "ChatTurn",
    "DraftAssessmentCompleted",
    "DraftAssessmentRequested",
    "ExplainTurnCompleted",
    "ExplainTurnRequested",
    "GeneratedOption",
    "GeneratedQuestion",
    "GradingCompleted",
    "GradingRequested",
    "ReviewReason",
    "RetryQuestionCompleted",
    "RetryQuestionRequested",
    "SolutionMethod",
]
