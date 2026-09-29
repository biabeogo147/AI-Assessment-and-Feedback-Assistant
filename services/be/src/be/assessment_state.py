"""The lifecycle of an assessment, and the one door that changes it.

ADR-01 gives an assessment four states and two rules that matter more than the
states themselves: approval **locks the content**, and approval **is
reversible** while the assessment is unpublished. Before this module the state
was a free-form string with a default, so both rules were documentation.

Everything that moves an assessment goes through `advance`. A single door is
the point: a transition written inline somewhere else would be a fifth edge
nobody could find, and the first thing to go would be the approval gate, since
publishing straight from a draft is one assignment away.

`assert_editable` is the other half. ADR-01's argument for locking content is
that "nếu nội dung còn sửa được sau khi duyệt thì việc duyệt không có nghĩa gì"
-- so every path that writes a question calls this first.
"""

from fastapi import HTTPException

from be.models import Assessment, AssessmentState

# Re-exported so a caller needs one import to ask a question about the
# lifecycle. The vocabulary belongs to the schema and lives in `models`; the
# edges belong here.
__all__ = ["AssessmentState", "advance", "assert_editable"]


# The whole lifecycle, as data. Reading this table is the fastest way to answer
# "can a teacher do X now", which is a question the chat agent will ask on
# nearly every turn.
_ALLOWED: dict[AssessmentState, frozenset[AssessmentState]] = {
    AssessmentState.EMPTY: frozenset({AssessmentState.HAS_QUESTIONS}),
    AssessmentState.HAS_QUESTIONS: frozenset({AssessmentState.APPROVED}),
    # Both edges out of `approved`: forward to publishing, and back to editing.
    # The backward one is unapproval, which ADR-01 requires and which ADR-01
    # also singles out as the only action that lowers a state -- so it is the
    # one that most needs a record in the conversation.
    AssessmentState.APPROVED: frozenset({AssessmentState.PUBLISHED, AssessmentState.HAS_QUESTIONS}),
    # Deliberately empty. Withdrawal is ADR-02's edge, not an unapproval, and
    # it does not return the assessment to editing.
    AssessmentState.PUBLISHED: frozenset(),
}

_EDITABLE = frozenset({AssessmentState.EMPTY, AssessmentState.HAS_QUESTIONS})

# One sentence per refusal, in Vietnamese, because a teacher reads it. The
# state names are spelled the way the interface spells them rather than the way
# the database does.
_READABLE = {
    AssessmentState.EMPTY: "chưa có câu hỏi",
    AssessmentState.HAS_QUESTIONS: "đang soạn",
    AssessmentState.APPROVED: "đã duyệt",
    AssessmentState.PUBLISHED: "đã phát hành",
}


def _state_of(assessment: Assessment) -> AssessmentState:
    """Read an assessment's state, including before it has ever been saved.

    The column default is applied by the INSERT, so `Assessment(...)` leaves
    the attribute None until the flush. Any path that creates an assessment
    and writes its first question in one unit of work passes through that gap,
    and an assessment that has not been stored yet is empty by definition --
    which is exactly what the default says, one statement later.

    Args:
        assessment: The row, saved or not.

    Returns:
        The current state, treating "not set yet" as `EMPTY`.
    """
    return AssessmentState.EMPTY if assessment.state is None else AssessmentState(assessment.state)


def advance(assessment: Assessment, to: AssessmentState) -> None:
    """Move an assessment to another state, or refuse.

    Args:
        assessment: The row to move. Its `state` is written in place; the
            caller owns the commit.
        to: The state being asked for.

    Raises:
        HTTPException: 409 when no edge of ADR-01 joins the current state to
            the requested one, carrying a sentence naming both.

    Side effects:
        Sets `assessment.state` when the edge exists.
    """
    current = _state_of(assessment)
    if to not in _ALLOWED[current]:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Đề đang ở trạng thái {_READABLE[current]}, "
                f"không chuyển sang {_READABLE[to]} được."
            ),
        )
    assessment.state = to


def assert_editable(assessment: Assessment) -> None:
    """Refuse when the assessment's content is locked.

    Every path that adds, changes or removes a question calls this. ADR-01
    locks content at approval, and the refusal says how to get the lock off,
    because a teacher told only "no" would reasonably conclude the question is
    stuck forever.

    Args:
        assessment: The row being written to.

    Raises:
        HTTPException: 409 when the assessment is approved or published.
    """
    current = _state_of(assessment)
    if current not in _EDITABLE:
        raise HTTPException(
            status_code=409,
            detail=(f"Đề {_READABLE[current]} nên nội dung đã khoá. Muốn sửa thì bỏ duyệt trước."),
        )
