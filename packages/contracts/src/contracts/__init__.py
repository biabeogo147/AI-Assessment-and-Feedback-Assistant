"""Shared message contract between BE and AGENT.

Three families live here. The authoring messages carry the core two-phase flow:
BE asks AGENT to write questions, to write the question of a remediation round,
and to take one turn in the tutoring conversation.

`teacher_chat` carries one turn of thinking for the teacher's chat, where the
work is not decided in advance. Its reply is a *proposal* -- BE owns the loop
and performs every step -- which is what keeps authorisation and ADR-05's
publish gate on the side of the wall that has the database and the identity.

`GradingRequested` and `GradingCompleted` are the older grading pair. They are
**legacy**: ADR-20 moved multiple-choice grading into BE, so nothing in the core
flow enqueues them. They stay until the Teacher Review Queue (UC-05) is designed
and can say what it actually needs. Do not add fields to them.
"""

from contracts.authoring import (
    EXPLAIN_TURN_TASK,
    GENERATE_RETRY_QUESTION_TASK,
    WRITE_DRAFT_QUESTION_TASK,
    ChatTurn,
    DraftQuestionCompleted,
    DraftQuestionRequested,
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
from contracts.teacher_chat import (
    PROPOSE_NEXT_STEP_TASK,
    NextStepCompleted,
    NextStepRequested,
    ToolSpec,
    TurnRecord,
)

__all__ = [
    "EXPLAIN_TURN_TASK",
    "GENERATE_RETRY_QUESTION_TASK",
    "GRADE_SUBMISSION_TASK",
    "PROPOSE_NEXT_STEP_TASK",
    "SCHEMA_VERSION",
    "WRITE_DRAFT_QUESTION_TASK",
    "ChatTurn",
    "DraftQuestionCompleted",
    "DraftQuestionRequested",
    "ExplainTurnCompleted",
    "ExplainTurnRequested",
    "GeneratedOption",
    "GeneratedQuestion",
    "GradingCompleted",
    "GradingRequested",
    "NextStepCompleted",
    "NextStepRequested",
    "ReviewReason",
    "RetryQuestionCompleted",
    "RetryQuestionRequested",
    "SolutionMethod",
    "ToolSpec",
    "TurnRecord",
]
