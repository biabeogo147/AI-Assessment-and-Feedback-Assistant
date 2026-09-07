"""Messages exchanged between BE and AGENT.

This module is data only. It holds no scoring rule, no threshold and no routing
decision, because both services import it and anything placed here would become
shared behaviour that neither service owns.
"""

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

# The arq task name. It lives here so BE can enqueue work by string and never
# needs to import the AGENT package -- the boundary holds at design time, not
# only at lint time.
GRADE_SUBMISSION_TASK = "grade_submission"


class GradingRequested(BaseModel):
    """Work item BE sends to AGENT for one submitted answer.

    Carries everything AGENT needs to grade without reading any database, which
    is what lets AGENT stay free of database credentials.

    `learning_objective` is present before anything consumes it: Adaptive
    Practice (Workflow 5) will need it to generate a variant of the same
    objective, and adding it later would mean versioning the contract.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    submission_id: str
    assessment_id: str
    question_id: str
    student_id: str
    selected_option_id: str
    student_explanation: str | None = None
    learning_objective: str


class GradingCompleted(BaseModel):
    """Evidence AGENT produces for one graded submission.

    Deliberately contains no `needs_teacher_review` field. AGENT reports what it
    observed; BE applies the threshold and decides routing. Putting the decision
    here would move the teacher-in-the-loop gate inside the AI service, which
    project-overview.md rules out.

    The two boolean flags map onto Workflow 4 review conditions that confidence
    alone cannot express: an answer that is correct while the reasoning is not,
    and a case where AGENT had too little to go on.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    submission_id: str
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    misconception_code: str | None = None
    feedback_text: str
    answer_explanation_conflict: bool = False
    has_sufficient_evidence: bool = True
