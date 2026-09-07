"""Shared message contract between BE and AGENT."""

from contracts.enums import ReviewReason
from contracts.messages import (
    GRADE_SUBMISSION_TASK,
    SCHEMA_VERSION,
    GradingCompleted,
    GradingRequested,
)

__all__ = [
    "GRADE_SUBMISSION_TASK",
    "SCHEMA_VERSION",
    "GradingCompleted",
    "GradingRequested",
    "ReviewReason",
]
