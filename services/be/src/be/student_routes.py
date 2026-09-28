"""Every HTTP surface a student touches.

Three rules shape this module and are worth stating once rather than at each
route.

The correct option never leaves BE while a student could still act on it. It
appears after submission, where ADR-16 makes the phase 1 score a floor and the
retry question is a different question anyway.

No response carries `confidence`, `misconception_code` or a review reason
(ADR-08). The authored error label does appear, but only inside the solution
dialog and the tutoring context -- as teaching material, never as a number.

Every deadline is decided here. The countdown on screen is decoration; the
server clock is what refuses a late answer and what stops a round (ADR-15).
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from be.agent_gateway import (
    AgentError,
    ask_for_retry_question,
    stream_task,
)
from be.config import get_settings
from be.db import get_session
from be.identity import current_student
from be.models import (
    Answer,
    AnswerOption,
    Assessment,
    Attempt,
    ChatMessage,
    Publication,
    Question,
    QuestionOutcome,
    RemediationRound,
    Report,
    RoundItem,
    Student,
)
from be.remediation import round_budget_minutes, round_ends_at, will_be_cut
from be.scoring import (
    MAX_ROUNDS_PER_QUESTION,
    MarkReason,
    mark_after_round,
    mark_for_phase_one,
    total,
)
from contracts import (
    EXPLAIN_TURN_TASK,
    ChatTurn,
    ExplainTurnCompleted,
    ExplainTurnRequested,
    GeneratedOption,
    GeneratedQuestion,
    RetryQuestionRequested,
    SolutionMethod,
)

router = APIRouter(prefix="/api", tags=["student"])


def _now() -> datetime:
    """Return the server clock, timezone aware.

    Returns:
        The current UTC time. Every deadline comparison in this module goes
        through here so a test can reason about one source of time.
    """
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    """Attach UTC to a timestamp that lost its offset in storage.

    SQLite drops timezone information, so a value read back is naive while the
    same value on Postgres is not. Comparing the two shapes raises.

    Args:
        value: Timestamp from the database.

    Returns:
        The same instant, guaranteed timezone aware.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class OptionOut(BaseModel):
    """One option as a student may see it before submitting."""

    option_id: str
    label: str
    text: str


class QuestionOut(BaseModel):
    """One question of the running attempt."""

    question_id: str
    order: int
    stem: str
    options: list[OptionOut]
    chosen_option_id: str | None = None


class AssignmentOut(BaseModel):
    """One row of the student's assignment list."""

    assignment_id: str
    attempt_id: str | None
    title: str
    subject: str
    question_count: int
    phase1_minutes: int
    opens_at: datetime
    closes_at: datetime
    remediation_deadline: datetime
    status: str
    wrong_count: int | None
    actions: list[str]


class AttemptOut(BaseModel):
    """A freshly started or resumed phase 1 attempt."""

    attempt_id: str
    title: str
    started_at: datetime
    ends_at: datetime
    questions: list[QuestionOut]


class SubmitOut(BaseModel):
    """What ending phase 1 produced."""

    attempt_id: str
    submitted_at: datetime
    phase1_score: float
    question_count: int
    wrong_question_ids: list[str]


class RoundOut(BaseModel):
    """One entry in a question's remediation history."""

    index: int
    stem: str
    outcome: str


class ResultItemOut(BaseModel):
    """One question on the score sheet."""

    question_id: str
    order: int
    stem: str
    mark: float
    mark_reason: str
    rounds: list[RoundOut]


class ResultOut(BaseModel):
    """The score sheet, in the shape both result screens read."""

    attempt_id: str
    title: str
    state: str
    total_score: float
    question_count: int
    submitted_at: datetime | None
    remediation_deadline: datetime
    items: list[ResultItemOut]


class ChosenOut(BaseModel):
    """An option named by label and text, for the remediation panel."""

    label: str
    text: str


class RemediationItemOut(BaseModel):
    """One question the student got wrong in phase 1, as the panel shows it.

    Closed questions stay in the list. The panel is what a student reads back
    after the attempt ends -- dropping a question the moment it settles would
    empty the screen that the result page sends them to.
    """

    question_id: str
    order: int
    stem: str
    chosen: ChosenOut | None
    correct: ChosenOut
    rounds_used: int
    rounds_max: int
    mark: float
    closed: bool


class RemediationOut(BaseModel):
    """Everything the tutoring screen needs besides the conversation.

    `items` holds every question that was wrong at the end of phase 1, closed
    or not; `open_count` is how many still need a round. The interface needs
    both: one to draw the list, the other to label the button that opens a
    round and to count what is left.
    """

    attempt_id: str
    state: str
    deadline: datetime
    minutes_per_question: int
    round_budget_minutes: int
    open_count: int
    can_start_round: bool
    warn_cut: bool
    open_round_id: str | None
    items: list[RemediationItemOut]


class SolutionOptionOut(BaseModel):
    """One option inside the solution dialog, with its authored mistake."""

    label: str
    text: str
    is_correct: bool
    error_label: str | None


class SolutionMethodOut(BaseModel):
    """One worked solution."""

    title: str
    body: str


class SolutionOut(BaseModel):
    """The solution dialog for one question."""

    question_id: str
    stem: str
    methods: list[SolutionMethodOut]
    options: list[SolutionOptionOut]


class ChatMessageOut(BaseModel):
    """One stored turn of the conversation."""

    message_id: str
    role: str
    text: str
    created_at: datetime


class ChatHistoryOut(BaseModel):
    """The conversation, plus whether it still accepts input."""

    attempt_id: str
    locked: bool
    messages: list[ChatMessageOut]


class ChatPostIn(BaseModel):
    """A student's message."""

    text: str


class ChatPostOut(BaseModel):
    """Where to read the reply from."""

    message_id: str
    stream_url: str


class RoundItemOut(BaseModel):
    """One question inside a running round.

    `origin_order` is the number the question carries on the paper, and it is
    what the screen shows. Numbering a round 1..n instead would tell a student
    who got questions 5 and 6 wrong that they are now on "câu 1" -- and the
    conversation beside it says câu 5.
    """

    round_item_id: str
    origin_question_id: str
    origin_order: int
    order: int
    stem: str
    options: list[OptionOut]
    chosen_label: str | None


class RoundOpenOut(BaseModel):
    """A round the student may now answer."""

    round_id: str
    index: int
    ends_at: datetime
    items: list[RoundItemOut]


class RoundResultItemOut(BaseModel):
    """What one question ended at after this round."""

    question_id: str
    outcome: str
    new_mark: float
    rounds_used: int
    rounds_left: int


class RoundResultOut(BaseModel):
    """The verdict on a submitted round."""

    round_id: str
    per_question: list[RoundResultItemOut]
    attempt_state: str


class AnswerIn(BaseModel):
    """One saved choice."""

    option_id: str


class RoundAnswerIn(BaseModel):
    """One saved choice inside a round, addressed by label."""

    label: str


class SavedOut(BaseModel):
    """Acknowledgement that a choice was stored."""

    saved_at: datetime


class ReportIn(BaseModel):
    """An optional note attached to a report."""

    note: str | None = None


class ReportOut(BaseModel):
    """Acknowledgement that a report was filed."""

    report_id: str


class MeOut(BaseModel):
    """Identity for the top bar."""

    student_id: str
    full_name: str
    class_name: str
    student_code: str


async def _load_assessment(session: AsyncSession, assessment_id: str) -> Assessment:
    """Load an assessment with its questions, options and methods.

    Args:
        session: Database session.
        assessment_id: Which assessment.

    Returns:
        The assessment.

    Raises:
        HTTPException: 404 when it does not exist.
    """
    found = await session.scalar(
        select(Assessment)
        .where(Assessment.id == assessment_id)
        .options(
            selectinload(Assessment.questions).selectinload(Question.options),
            selectinload(Assessment.questions).selectinload(Question.methods),
        )
    )
    if found is None:
        raise HTTPException(status_code=404, detail=f"No assessment {assessment_id}")
    return found


async def _owned_attempt(session: AsyncSession, attempt_id: str, student: Student) -> Attempt:
    """Load an attempt and refuse it to anybody else's owner.

    Args:
        session: Database session.
        attempt_id: Which attempt.
        student: The caller.

    Returns:
        The attempt.

    Raises:
        HTTPException: 404 when it does not exist or belongs to someone else.
            Not 403: telling a stranger that an id is real is already a leak.
    """
    found = await session.get(Attempt, attempt_id)
    if found is None or found.student_id != student.id:
        raise HTTPException(status_code=404, detail=f"No attempt {attempt_id}")
    return found


async def _publication(session: AsyncSession, assessment_id: str) -> Publication:
    """Load the release terms of an assessment.

    Args:
        session: Database session.
        assessment_id: Which assessment.

    Returns:
        Its publication row.

    Raises:
        HTTPException: 404 when the assessment was never published, which for a
            student is indistinguishable from not existing.
    """
    found = await session.get(Publication, assessment_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Bài này chưa được phát hành")
    return found


async def _open_round(session: AsyncSession, attempt_id: str) -> RemediationRound | None:
    """Return the attempt's unsubmitted round, if it has one.

    Uses `scalar_one_or_none` rather than `scalar`: at most one round may be
    open, a partial unique index enforces it, and if that ever fails this must
    raise instead of quietly picking a row and hiding the other.

    Args:
        session: Database session.
        attempt_id: Which attempt.

    Returns:
        The open round, or None.

    Raises:
        MultipleResultsFound: If two rounds are open at once, which means the
            index is missing from this database.
    """
    found = await session.scalars(
        select(RemediationRound).where(
            RemediationRound.attempt_id == attempt_id, RemediationRound.submitted_at.is_(None)
        )
    )
    return found.one_or_none()


async def _outcomes(session: AsyncSession, attempt_id: str) -> dict[str, QuestionOutcome]:
    """Read the score ledger of one attempt, keyed by question.

    Args:
        session: Database session.
        attempt_id: Which attempt.

    Returns:
        Outcome rows by question id.
    """
    rows = await session.scalars(
        select(QuestionOutcome).where(QuestionOutcome.attempt_id == attempt_id)
    )
    return {row.question_id: row for row in rows}


def _attempt_state(
    outcomes: dict[str, QuestionOutcome],
    submitted: bool,
    deadline: datetime,
    now: datetime,
) -> str:
    """Decide which shape of the result screen applies.

    Args:
        outcomes: The score ledger.
        submitted: Whether phase 1 has ended.
        deadline: The phase 2 deadline.
        now: Server time.

    Returns:
        "đang-làm", "cần-chữa", "đã-hoàn-thành" or "hết-hạn-chữa". ADR-14 makes
        these different shapes rather than one shape with empty fields.
    """
    if not submitted:
        return "đang-làm"
    if all(outcome.closed for outcome in outcomes.values()):
        return "đã-hoàn-thành"
    if now > deadline:
        return "hết-hạn-chữa"
    return "cần-chữa"


def _attempt_payload(attempt: Attempt, assessment: Assessment, saved: dict[str, str]) -> AttemptOut:
    """Shape one attempt for the sitting screen.

    Shared by starting and resuming so the two cannot drift into showing
    different things -- and in particular so neither ever grows an
    `is_correct`.

    Args:
        attempt: The attempt row.
        assessment: Its assessment, with questions and options loaded.
        saved: Chosen option id per question id.

    Returns:
        The payload, with every option stripped of the answer key.
    """
    return AttemptOut(
        attempt_id=attempt.id,
        title=assessment.title,
        started_at=_aware(attempt.started_at),
        ends_at=_aware(attempt.ends_at),
        questions=[
            QuestionOut(
                question_id=question.id,
                order=question.order_index,
                stem=question.stem,
                options=[
                    OptionOut(option_id=option.id, label=option.label, text=option.text)
                    for option in question.options
                ],
                chosen_option_id=saved.get(question.id),
            )
            for question in assessment.questions
        ],
    )


@router.get("/me", response_model=MeOut)
async def me(
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    """Report who the caller is, for the identity strip every screen carries.

    Args:
        student: The caller.
        session: Database session.

    Returns:
        Name, class and student code -- the three things ADR-13 requires on a
        shared classroom machine.
    """
    loaded = await session.scalar(
        select(Student).where(Student.id == student.id).options(selectinload(Student.school_class))
    )
    assert loaded is not None
    return MeOut(
        student_id=loaded.id,
        full_name=loaded.full_name,
        class_name=loaded.school_class.name,
        student_code=loaded.student_code,
    )


@router.get("/me/assignments", response_model=list[AssignmentOut])
async def my_assignments(
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> list[AssignmentOut]:
    """List the assignments of the caller's class.

    Status is computed here from the server clock rather than sent as raw dates
    for the client to interpret: two machines with different clocks would
    otherwise show two different states for one assignment.

    Args:
        student: The caller.
        session: Database session.

    Returns:
        One row per published assessment for this class, newest first.
    """
    now = _now()
    publications = await session.scalars(
        select(Publication).where(Publication.class_id == student.class_id)
    )

    rows: list[AssignmentOut] = []
    for publication in publications:
        assessment = await _load_assessment(session, publication.assessment_id)
        attempt = await session.scalar(
            select(Attempt).where(
                Attempt.assessment_id == assessment.id, Attempt.student_id == student.id
            )
        )
        opens_at = _aware(publication.opens_at)
        closes_at = _aware(publication.closes_at)
        deadline = _aware(publication.remediation_deadline)

        wrong_count: int | None = None
        actions: list[str] = []

        if attempt is None:
            if now < opens_at:
                status = "chưa-tới-giờ-mở"
            elif now > closes_at:
                status = "đã-đóng"
            else:
                status = "đang-mở"
                actions = ["start"]
        elif attempt.submitted_at is None:
            status = "đang-làm"
            actions = ["continue"]
        else:
            outcomes = await _outcomes(session, attempt.id)
            wrong_count = sum(1 for outcome in outcomes.values() if not outcome.closed)
            status = _attempt_state(outcomes, True, deadline, now)
            actions = ["result", "remediate"] if status == "cần-chữa" else ["result"]

        rows.append(
            AssignmentOut(
                assignment_id=assessment.id,
                attempt_id=attempt.id if attempt else None,
                title=assessment.title,
                subject=assessment.subject,
                question_count=len(assessment.questions),
                phase1_minutes=publication.phase1_minutes,
                opens_at=opens_at,
                closes_at=closes_at,
                remediation_deadline=deadline,
                status=status,
                wrong_count=wrong_count,
                actions=actions,
            )
        )

    rows.sort(key=lambda row: row.opens_at, reverse=True)
    return rows


@router.post("/assignments/{assessment_id}/attempts", response_model=AttemptOut, status_code=201)
async def start_attempt(
    assessment_id: str,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> AttemptOut:
    """Start phase 1, or hand back the attempt already in progress.

    Args:
        assessment_id: Which assessment.
        student: The caller.
        session: Database session.

    Returns:
        The attempt with its questions, options stripped of the answer key.

    Raises:
        HTTPException: 409 before the opening time, after the closing time, or
            once phase 1 has been submitted.

    Side effects:
        Creates an attempt row on first call.
    """
    publication = await _publication(session, assessment_id)
    assessment = await _load_assessment(session, assessment_id)
    now = _now()

    if now < _aware(publication.opens_at):
        raise HTTPException(status_code=409, detail="Chưa tới giờ mở")
    if now > _aware(publication.closes_at):
        raise HTTPException(status_code=409, detail="Đã quá hạn vào làm bài")

    attempt = await session.scalar(
        select(Attempt).where(
            Attempt.assessment_id == assessment_id, Attempt.student_id == student.id
        )
    )
    if attempt is not None and attempt.submitted_at is not None:
        raise HTTPException(status_code=409, detail="Bài này đã nộp")

    if attempt is None:
        attempt = Attempt(
            assessment_id=assessment_id,
            student_id=student.id,
            started_at=now,
            ends_at=min(
                now + timedelta(minutes=publication.phase1_minutes),
                _aware(publication.closes_at) + timedelta(minutes=publication.phase1_minutes),
            ),
        )
        session.add(attempt)
        try:
            await session.commit()
        except IntegrityError:
            # Two tabs pressed start together. The unique constraint kept the
            # data right; this turns the collision into the answer the second
            # tab wanted anyway -- the attempt that already exists.
            await session.rollback()
            attempt = await session.scalar(
                select(Attempt).where(
                    Attempt.assessment_id == assessment_id, Attempt.student_id == student.id
                )
            )
            if attempt is None:
                raise

    saved = {
        row.question_id: row.option_id
        for row in await session.scalars(select(Answer).where(Answer.attempt_id == attempt.id))
    }

    return _attempt_payload(attempt, assessment, saved)


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
async def resume_attempt(
    attempt_id: str,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> AttemptOut:
    """Read back an attempt in progress, with the choices already saved.

    Reloading the page must not cost anything. Starting an attempt is a POST
    because it creates one; coming back to it is this GET, so a refresh cannot
    be mistaken for a second start.

    Args:
        attempt_id: Which attempt.
        student: The caller.
        session: Database session.

    Returns:
        The attempt with its questions, options stripped of the answer key.

    Raises:
        HTTPException: 404 when the attempt is not the caller's; 409 once phase
            1 has been submitted, because the paper is no longer answerable.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is not None:
        raise HTTPException(status_code=409, detail="Bài này đã nộp")

    assessment = await _load_assessment(session, attempt.assessment_id)
    saved = {
        row.question_id: row.option_id
        for row in await session.scalars(select(Answer).where(Answer.attempt_id == attempt.id))
    }
    return _attempt_payload(attempt, assessment, saved)


@router.put("/attempts/{attempt_id}/answers/{question_id}", response_model=SavedOut)
async def save_answer(
    attempt_id: str,
    question_id: str,
    body: AnswerIn,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> SavedOut:
    """Store one phase 1 choice.

    Args:
        attempt_id: Which attempt.
        question_id: Which question.
        body: The chosen option.
        student: The caller.
        session: Database session.

    Returns:
        When the choice was stored.

    Raises:
        HTTPException: 409 after the attempt's own deadline or once submitted;
            400 when the option belongs to another question.

    Side effects:
        Inserts or updates one answer row.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is not None:
        raise HTTPException(status_code=409, detail="Bài đã nộp")
    now = _now()
    if now > _aware(attempt.ends_at):
        raise HTTPException(status_code=409, detail="Hết giờ làm bài")

    option = await session.get(AnswerOption, body.option_id)
    if option is None or option.question_id != question_id:
        raise HTTPException(status_code=400, detail="Phương án không thuộc câu này")

    existing = await session.scalar(
        select(Answer).where(Answer.attempt_id == attempt_id, Answer.question_id == question_id)
    )
    if existing is None:
        session.add(
            Answer(
                attempt_id=attempt_id,
                question_id=question_id,
                option_id=body.option_id,
                saved_at=now,
            )
        )
    else:
        existing.option_id = body.option_id
        existing.saved_at = now
    await session.commit()
    return SavedOut(saved_at=now)


@router.post("/attempts/{attempt_id}/submit", response_model=SubmitOut)
async def submit_attempt(
    attempt_id: str,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> SubmitOut:
    """End phase 1 and mark every question.

    Marking is a comparison and runs inline (ADR-20), so there is no "being
    graded" state between this call and the score sheet.

    Args:
        attempt_id: Which attempt.
        student: The caller.
        session: Database session.

    Returns:
        The floor score and which questions are still open.

    Raises:
        HTTPException: 409 when phase 1 was already submitted.

    Side effects:
        Writes the score ledger and stamps the attempt as submitted.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is not None:
        raise HTTPException(status_code=409, detail="Bài này đã nộp")

    assessment = await _load_assessment(session, attempt.assessment_id)
    chosen = {
        row.question_id: row.option_id
        for row in await session.scalars(select(Answer).where(Answer.attempt_id == attempt_id))
    }

    now = _now()
    wrong: list[str] = []
    marks: list[float] = []
    for question in assessment.questions:
        correct_id = next(option.id for option in question.options if option.is_correct)
        is_correct = chosen.get(question.id) == correct_id
        mark, reason, closed = mark_for_phase_one(is_correct)
        marks.append(mark)
        if not closed:
            wrong.append(question.id)
        session.add(
            QuestionOutcome(
                attempt_id=attempt_id,
                question_id=question.id,
                mark=mark,
                reason=reason.value,
                rounds_used=0,
                closed=closed,
            )
        )

    attempt.submitted_at = now
    await session.commit()

    return SubmitOut(
        attempt_id=attempt_id,
        submitted_at=now,
        phase1_score=total(marks),
        question_count=len(assessment.questions),
        wrong_question_ids=wrong,
    )


@router.get("/attempts/{attempt_id}/result", response_model=ResultOut)
async def attempt_result(
    attempt_id: str,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> ResultOut:
    """Return the score sheet, including the question of every retry round.

    A round's own question is printed because it is a different question from
    the original (ADR-17); a sheet showing only the phase 1 stem would credit a
    student 0.5 without saying what they got right.

    Args:
        attempt_id: Which attempt.
        student: The caller.
        session: Database session.

    Returns:
        One row per question, each with its rounds.

    Raises:
        HTTPException: 409 while phase 1 is still running.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is None:
        raise HTTPException(status_code=409, detail="Bài chưa nộp")

    assessment = await _load_assessment(session, attempt.assessment_id)
    publication = await _publication(session, attempt.assessment_id)
    outcomes = await _outcomes(session, attempt_id)

    rounds = await session.scalars(
        select(RemediationRound)
        .where(RemediationRound.attempt_id == attempt_id)
        .options(selectinload(RemediationRound.items))
        .order_by(RemediationRound.index)
    )
    history: dict[str, list[RoundOut]] = {}
    for rnd in rounds:
        if rnd.submitted_at is None:
            continue
        for item in rnd.items:
            history.setdefault(item.origin_question_id, []).append(
                RoundOut(index=rnd.index, stem=item.stem, outcome=item.outcome or "chưa-trả-lời")
            )

    items = [
        ResultItemOut(
            question_id=question.id,
            order=question.order_index,
            stem=question.stem,
            mark=outcomes[question.id].mark,
            mark_reason=outcomes[question.id].reason,
            rounds=history.get(question.id, []),
        )
        for question in assessment.questions
        if question.id in outcomes
    ]

    return ResultOut(
        attempt_id=attempt_id,
        title=assessment.title,
        state=_attempt_state(outcomes, True, _aware(publication.remediation_deadline), _now()),
        total_score=total([item.mark for item in items]),
        question_count=len(items),
        submitted_at=_aware(attempt.submitted_at),
        remediation_deadline=_aware(publication.remediation_deadline),
        items=items,
    )


@router.get("/attempts/{attempt_id}/remediation", response_model=RemediationOut)
async def remediation_panel(
    attempt_id: str,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> RemediationOut:
    """Return every still-open question, with what was picked and what was right.

    `warn_cut` is computed here rather than by the client: comparing the round
    budget against the remaining time is the rule of ADR-15, and it selects
    which form of the round gate appears.

    Args:
        attempt_id: Which attempt.
        student: The caller.
        session: Database session.

    Returns:
        The panel payload for the tutoring screen.

    Raises:
        HTTPException: 409 while phase 1 is still running.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is None:
        raise HTTPException(status_code=409, detail="Bài chưa nộp")

    assessment = await _load_assessment(session, attempt.assessment_id)
    publication = await _publication(session, attempt.assessment_id)
    outcomes = await _outcomes(session, attempt_id)
    chosen = {
        row.question_id: row.option_id
        for row in await session.scalars(select(Answer).where(Answer.attempt_id == attempt_id))
    }

    items: list[RemediationItemOut] = []
    for question in assessment.questions:
        outcome = outcomes.get(question.id)
        if outcome is None or outcome.reason == MarkReason.CORRECT_FIRST_TRY:
            continue
        picked = next((o for o in question.options if o.id == chosen.get(question.id)), None)
        correct = next(o for o in question.options if o.is_correct)
        items.append(
            RemediationItemOut(
                question_id=question.id,
                order=question.order_index,
                stem=question.stem,
                chosen=ChosenOut(label=picked.label, text=picked.text) if picked else None,
                correct=ChosenOut(label=correct.label, text=correct.text),
                rounds_used=outcome.rounds_used,
                rounds_max=MAX_ROUNDS_PER_QUESTION,
                mark=outcome.mark,
                closed=outcome.closed,
            )
        )

    open_count = sum(1 for item in items if not item.closed)
    now = _now()
    deadline = _aware(publication.remediation_deadline)
    budget = round_budget_minutes(publication.phase2_minutes_per_question, open_count)
    open_round = await _open_round(session, attempt_id)

    return RemediationOut(
        attempt_id=attempt_id,
        state=_attempt_state(outcomes, True, deadline, now),
        deadline=deadline,
        minutes_per_question=publication.phase2_minutes_per_question,
        round_budget_minutes=budget,
        open_count=open_count,
        can_start_round=open_count > 0 and now < deadline and open_round is None,
        warn_cut=open_count > 0 and will_be_cut(now, budget, deadline),
        open_round_id=open_round.id if open_round else None,
        items=items,
    )


@router.get("/questions/{question_id}/solution", response_model=SolutionOut)
async def question_solution(
    question_id: str,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> SolutionOut:
    """Return the worked solutions and the authored distractor mapping.

    Args:
        question_id: Which question.
        student: The caller.
        session: Database session.

    Returns:
        The solution dialog payload.

    Raises:
        HTTPException: 404 when the question is not in an assessment this
            student has an attempt on; 409 while that attempt is unsubmitted,
            because the correct answer is in this payload.
    """
    question = await session.scalar(
        select(Question)
        .where(Question.id == question_id)
        .options(selectinload(Question.options), selectinload(Question.methods))
    )
    if question is None:
        raise HTTPException(status_code=404, detail=f"No question {question_id}")

    attempt = await session.scalar(
        select(Attempt).where(
            Attempt.assessment_id == question.assessment_id, Attempt.student_id == student.id
        )
    )
    if attempt is None:
        raise HTTPException(status_code=404, detail=f"No question {question_id}")
    if attempt.submitted_at is None:
        raise HTTPException(status_code=409, detail="Lời giải chỉ mở sau khi nộp bài")

    return SolutionOut(
        question_id=question.id,
        stem=question.stem,
        methods=[SolutionMethodOut(title=m.title, body=m.body) for m in question.methods],
        options=[
            SolutionOptionOut(
                label=o.label, text=o.text, is_correct=o.is_correct, error_label=o.error_label
            )
            for o in question.options
        ],
    )


async def _chat_context(
    session: AsyncSession, attempt: Attempt
) -> tuple[list[GeneratedQuestion], list[int], dict[str, str], dict[str, str]]:
    """Build what AGENT needs to talk about this attempt.

    The payload is self-contained: AGENT holds no database credentials, so the
    questions, the authored error labels and the student's picks all travel
    with the job.

    Args:
        session: Database session.
        attempt: The attempt being discussed.

    Returns:
        The still-open questions, the number each carries on the paper, the
        chosen option label per stem, and the authored error label per stem.
        The numbers travel because the assistant says "câu 5" out loud, and it
        has no other way to know the question is the fifth one.
    """
    assessment = await _load_assessment(session, attempt.assessment_id)
    outcomes = await _outcomes(session, attempt.id)
    chosen = {
        row.question_id: row.option_id
        for row in await session.scalars(select(Answer).where(Answer.attempt_id == attempt.id))
    }

    questions: list[GeneratedQuestion] = []
    numbers: list[int] = []
    chosen_labels: dict[str, str] = {}
    error_labels: dict[str, str] = {}

    for question in assessment.questions:
        outcome = outcomes.get(question.id)
        if outcome is None or outcome.closed:
            continue
        questions.append(
            GeneratedQuestion(
                stem=question.stem,
                options=tuple(
                    GeneratedOption(
                        label=o.label,
                        text=o.text,
                        is_correct=o.is_correct,
                        error_label=o.error_label,
                    )
                    for o in question.options
                ),
                methods=tuple(SolutionMethod(title=m.title, body=m.body) for m in question.methods),
                learning_objective=question.learning_objective,
            )
        )
        numbers.append(question.order_index)
        picked = next((o for o in question.options if o.id == chosen.get(question.id)), None)
        if picked is not None:
            chosen_labels[question.stem] = picked.label
            if picked.error_label:
                error_labels[question.stem] = picked.error_label

    return questions, numbers, chosen_labels, error_labels


async def _history(session: AsyncSession, attempt_id: str) -> list[ChatMessage]:
    """Read the stored conversation in order.

    Args:
        session: Database session.
        attempt_id: Which attempt.

    Returns:
        Messages oldest first.
    """
    rows = await session.scalars(
        select(ChatMessage)
        .where(ChatMessage.attempt_id == attempt_id)
        .order_by(ChatMessage.sequence)
    )
    return list(rows)


async def _is_locked(session: AsyncSession, attempt: Attempt) -> bool:
    """Tell whether the conversation still accepts input.

    Args:
        session: Database session.
        attempt: The attempt.

    Returns:
        True once every question is closed or the phase 2 deadline has passed.
        A locked conversation is still readable -- that is the whole point of
        the finished form of the tutoring screen.
    """
    publication = await _publication(session, attempt.assessment_id)
    outcomes = await _outcomes(session, attempt.id)
    state = _attempt_state(
        outcomes, attempt.submitted_at is not None, _aware(publication.remediation_deadline), _now()
    )
    return state in {"đã-hoàn-thành", "hết-hạn-chữa"}


@router.get("/attempts/{attempt_id}/chat", response_model=ChatHistoryOut)
async def chat_history(
    attempt_id: str,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> ChatHistoryOut:
    """Return the conversation and whether it is still open.

    Args:
        attempt_id: Which attempt.
        student: The caller.
        session: Database session.

    Returns:
        Stored messages, oldest first, plus the lock flag the finished screen
        reads.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    messages = await _history(session, attempt_id)
    return ChatHistoryOut(
        attempt_id=attempt_id,
        locked=await _is_locked(session, attempt),
        messages=[
            ChatMessageOut(
                message_id=m.id, role=m.role, text=m.text, created_at=_aware(m.created_at)
            )
            for m in messages
        ],
    )


@router.post("/attempts/{attempt_id}/chat/messages", response_model=ChatPostOut, status_code=202)
async def post_chat_message(
    attempt_id: str,
    body: ChatPostIn,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> ChatPostOut:
    """Store the student's turn and say where the reply will arrive.

    Args:
        attempt_id: Which attempt.
        body: The message text. Empty is allowed exactly once, to pull the
            assistant's opening turn.
        student: The caller.
        session: Database session.

    Returns:
        The stored message id and the stream to read the reply from.

    Raises:
        HTTPException: 409 while phase 1 is unsubmitted or once the attempt is
            finished.

    Side effects:
        Inserts one chat row.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is None:
        raise HTTPException(status_code=409, detail="Phần chữa mở sau khi nộp bài")
    if await _is_locked(session, attempt):
        raise HTTPException(status_code=409, detail="Bài đã kết thúc")

    history = await _history(session, attempt_id)
    text = body.text.strip()
    if text:
        message = ChatMessage(
            attempt_id=attempt_id,
            sequence=len(history) + 1,
            role="student",
            text=text,
            created_at=_now(),
        )
        session.add(message)
        await session.commit()
        message_id = message.id
    else:
        message_id = "opening"

    return ChatPostOut(
        message_id=message_id,
        stream_url=f"/api/attempts/{attempt_id}/chat/stream",
    )


def _event(name: str, text: str) -> str:
    """Write one server-sent event.

    A `data:` line cannot contain a newline, and a model writing prose produces
    plenty of them. The wire format for that is not ours to invent: SSE says
    repeat the field, and the reader joins the lines back with newlines between
    them.

    Args:
        name: Event name -- `chunk`, `done` or `error`.
        text: Payload, newlines and all.

    Returns:
        One complete event, terminated by a blank line.
    """
    body = "\n".join(f"data: {line}" for line in text.split("\n"))
    return f"event: {name}\n{body}\n\n"


def _sse(text: str, message_id: str) -> AsyncIterator[str]:
    """Turn one whole turn into a server-sent event stream.

    Used when the answer arrived in one piece: a replayed turn, or a model that
    did not stream. The words are doled out here so both paths look the same to
    a reader.

    Args:
        text: The assistant's words.
        message_id: The stored message, sent with the closing event so the
            client can reconcile with the history it reloads.

    Returns:
        An async iterator yielding one `chunk` event per word, then `done`.
    """

    async def events() -> AsyncIterator[str]:
        for word in text.split(" "):
            yield _event("chunk", word + " ")
        yield _event("done", message_id)

    return events()


def _replay(message: ChatMessage) -> AsyncIterator[str]:
    """Stream a turn that already exists instead of asking for a new one.

    Args:
        message: The assistant turn last stored.

    Returns:
        The same event stream a fresh turn would produce.
    """
    return _sse(message.text, message.id)


@router.get("/attempts/{attempt_id}/chat/stream")
async def stream_reply(
    attempt_id: str,
    request: Request,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Stream the assistant's next turn word by word.

    The turn is asked for, **stored**, and only then streamed. Server-sent
    events are an accelerant for how the answer feels, not a second source of
    truth: a dropped connection costs the animation, never the message.

    Args:
        attempt_id: Which attempt.
        request: Used to reach the shared arq pool.
        student: The caller.
        session: Database session.

    Returns:
        A text/event-stream of `chunk` events followed by `done`.

    Raises:
        HTTPException: 409 while phase 1 is unsubmitted or once the attempt is
            finished; 503 when AGENT cannot be reached.

    Side effects:
        Enqueues one AGENT job and inserts one chat row.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is None:
        raise HTTPException(status_code=409, detail="Phần chữa mở sau khi nộp bài")
    if await _is_locked(session, attempt):
        raise HTTPException(status_code=409, detail="Bài đã kết thúc")

    history = await _history(session, attempt_id)
    # Whose turn it is, decided server side. A client that opens the stream
    # twice -- a double-rendered effect, an impatient refresh -- would otherwise
    # store two greetings, and the conversation would read as if the assistant
    # said hello and then said hello again.
    if history and history[-1].role != "student":
        return StreamingResponse(_replay(history[-1]), media_type="text/event-stream")

    questions, numbers, chosen_labels, error_labels = await _chat_context(session, attempt)
    last_student = next((m.text for m in reversed(history) if m.role == "student"), "")

    pool = request.app.state.queue_pool
    if pool is None:
        # The one failure knowable before the stream opens, so it still gets a
        # status code rather than an event nobody styled.
        raise HTTPException(
            status_code=503, detail="Trợ lý chưa trả lời được: hàng đợi chưa sẵn sàng"
        )

    channel = f"aiafa:stream:{uuid4().hex}"
    payload = ExplainTurnRequested(
        request_id=attempt_id,
        questions=tuple(questions),
        question_numbers=tuple(numbers),
        chosen_labels=chosen_labels,
        error_labels=error_labels,
        history=tuple(ChatTurn(role=m.role, text=m.text) for m in history),
        student_text=last_student if history and history[-1].role == "student" else "",
        stream_channel=channel,
    )
    settings = get_settings()

    async def events() -> AsyncIterator[str]:
        """Forward the answer as it is written, then store it.

        Storing happens when the reply is complete, which is after the last
        piece has gone out. A student who closes the tab mid-answer therefore
        costs one model call and gets a fresh turn next time -- the turn is
        never half-saved, and never saved twice.
        """
        spoke = False
        reply: ExplainTurnCompleted | None = None
        try:
            async for kind, value in stream_task(
                pool, settings, EXPLAIN_TURN_TASK, payload.model_dump(mode="json"), channel
            ):
                if kind == "chunk":
                    spoke = True
                    yield _event("chunk", str(value))
                else:
                    reply = ExplainTurnCompleted.model_validate(value)
        except AgentError as exc:
            # Too late for a 503: the response started the moment this
            # generator did. The client is told in the stream instead.
            yield _event("error", f"Trợ lý chưa trả lời được: {exc}")
            return

        if reply is None:
            yield _event("error", "Trợ lý chưa trả lời được")
            return

        stored = ChatMessage(
            attempt_id=attempt_id,
            sequence=len(history) + 1,
            role="assistant",
            text=reply.text,
            created_at=_now(),
        )
        session.add(stored)
        await session.commit()

        if not spoke:
            # Nothing was published -- prepared content, or a provider that
            # does not stream. Say the whole thing now. Doing this after any
            # piece had already gone out would show the same words twice.
            async for event in _sse(reply.text, stored.id):
                yield event
            return

        yield _event("done", stored.id)

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/attempts/{attempt_id}/rounds", response_model=RoundOpenOut, status_code=201)
async def start_round(
    attempt_id: str,
    request: Request,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> RoundOpenOut:
    """Open one remediation round covering every still-open question.

    Args:
        attempt_id: Which attempt.
        request: Used to reach the shared arq pool.
        student: The caller.
        session: Database session.

    Returns:
        The round with one generated question per open question.

    Raises:
        HTTPException: 409 past the phase 2 deadline, with nothing left to fix,
            or while another round is open; 503 when AGENT cannot be reached or
            returns a question that breaks ADR-18.

    Side effects:
        Enqueues one AGENT job per open question and writes the round.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is None:
        raise HTTPException(status_code=409, detail="Bài chưa nộp")

    publication = await _publication(session, attempt.assessment_id)
    deadline = _aware(publication.remediation_deadline)
    now = _now()
    if now >= deadline:
        raise HTTPException(status_code=409, detail="Đã hết hạn chữa bài")

    if await _open_round(session, attempt_id) is not None:
        raise HTTPException(status_code=409, detail="Đang có một lượt chưa nộp")

    assessment = await _load_assessment(session, attempt.assessment_id)
    outcomes = await _outcomes(session, attempt_id)
    open_questions = [q for q in assessment.questions if not outcomes[q.id].closed]
    if not open_questions:
        raise HTTPException(status_code=409, detail="Không còn câu nào phải làm lại")

    index = (
        1
        + (
            await session.scalar(
                select(RemediationRound)
                .where(RemediationRound.attempt_id == attempt_id)
                .order_by(RemediationRound.index.desc())
                .limit(1)
            )
            or RemediationRound(index=0)
        ).index
    )

    budget = round_budget_minutes(publication.phase2_minutes_per_question, len(open_questions))
    rnd = RemediationRound(
        attempt_id=attempt_id,
        index=index,
        started_at=now,
        ends_at=round_ends_at(now, budget, deadline),
    )
    session.add(rnd)
    try:
        await session.flush()
    except IntegrityError as exc:
        # The check above passed for both tabs; the index let only one through.
        # Two clocks for one student is a state ADR-15 gives no meaning to.
        await session.rollback()
        raise HTTPException(status_code=409, detail="Đang có một lượt chưa nộp") from exc

    previous = await session.scalars(
        select(RoundItem)
        .join(RemediationRound, RoundItem.round_id == RemediationRound.id)
        .where(RemediationRound.attempt_id == attempt_id)
    )
    spent: dict[str, list[str]] = {}
    for item in previous:
        spent.setdefault(item.origin_question_id, []).append(item.stem)

    items: list[RoundItemOut] = []
    for order, question in enumerate(open_questions, start=1):
        picked_label = None
        answer = await session.scalar(
            select(Answer).where(Answer.attempt_id == attempt_id, Answer.question_id == question.id)
        )
        if answer is not None:
            picked = next((o for o in question.options if o.id == answer.option_id), None)
            picked_label = picked.label if picked else None

        origin = GeneratedQuestion(
            stem=question.stem,
            options=tuple(
                GeneratedOption(
                    label=o.label, text=o.text, is_correct=o.is_correct, error_label=o.error_label
                )
                for o in question.options
            ),
            methods=tuple(SolutionMethod(title=m.title, body=m.body) for m in question.methods),
            learning_objective=question.learning_objective,
        )
        error_label = next(
            (o.error_label for o in question.options if o.label == picked_label), None
        )
        ask = RetryQuestionRequested(
            request_id=f"{attempt_id}:{question.id}:{index}",
            origin=origin,
            wrong_option_label=picked_label or "",
            error_label=error_label,
            round_index=outcomes[question.id].rounds_used + 1,
            previous_stems=tuple(spent.get(question.id, ())),
        )
        try:
            generated = await ask_for_retry_question(
                request.app.state.queue_pool,
                get_settings(),
                ask,
                question.stem,
                spent.get(question.id, []),
            )
        except AgentError as exc:
            raise HTTPException(
                status_code=503, detail=f"Chưa sinh được đề lượt này: {exc}"
            ) from exc

        item = RoundItem(
            round_id=rnd.id,
            origin_question_id=question.id,
            order_index=order,
            stem=generated.stem,
            options=[o.model_dump() for o in generated.options],
            methods=[m.model_dump() for m in generated.methods],
        )
        session.add(item)
        await session.flush()
        items.append(
            RoundItemOut(
                round_item_id=item.id,
                origin_question_id=question.id,
                origin_order=question.order_index,
                order=order,
                stem=generated.stem,
                options=[
                    OptionOut(option_id=o.label, label=o.label, text=o.text)
                    for o in generated.options
                ],
                chosen_label=None,
            )
        )

    await session.commit()
    return RoundOpenOut(round_id=rnd.id, index=rnd.index, ends_at=_aware(rnd.ends_at), items=items)


async def _owned_round(
    session: AsyncSession, round_id: str, student: Student
) -> tuple[RemediationRound, Attempt]:
    """Load a round and the attempt it belongs to, refusing other students'.

    Args:
        session: Database session.
        round_id: Which round.
        student: The caller.

    Returns:
        The round and its attempt.

    Raises:
        HTTPException: 404 when the round does not exist or is not the
            caller's.
    """
    rnd = await session.scalar(
        select(RemediationRound)
        .where(RemediationRound.id == round_id)
        .options(selectinload(RemediationRound.items))
    )
    if rnd is None:
        raise HTTPException(status_code=404, detail=f"No round {round_id}")
    attempt = await _owned_attempt(session, rnd.attempt_id, student)
    return rnd, attempt


@router.put("/rounds/{round_id}/answers/{item_id}", response_model=SavedOut)
async def save_round_answer(
    round_id: str,
    item_id: str,
    body: RoundAnswerIn,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> SavedOut:
    """Store one choice inside a running round.

    Args:
        round_id: Which round.
        item_id: Which question of that round.
        body: The chosen label.
        student: The caller.
        session: Database session.

    Returns:
        When the choice was stored.

    Raises:
        HTTPException: 409 once the round is submitted or its clock has run
            out; 404 when the item is not part of this round.

    Side effects:
        Updates one round item.
    """
    rnd, _ = await _owned_round(session, round_id, student)
    if rnd.submitted_at is not None:
        raise HTTPException(status_code=409, detail="Lượt đã nộp")
    now = _now()
    if now > _aware(rnd.ends_at):
        raise HTTPException(status_code=409, detail="Lượt đã DỪNG vì hết giờ")

    item = next((i for i in rnd.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"No item {item_id}")

    item.chosen_label = body.label
    await session.commit()
    return SavedOut(saved_at=now)


@router.post("/rounds/{round_id}/submit", response_model=RoundResultOut)
async def submit_round(
    round_id: str,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> RoundResultOut:
    """Mark a round and move each question's ledger entry.

    A question answered correctly closes at half credit; one that runs out of
    rounds closes at zero; anything else stays open for another round. A mark
    never falls, because phase 1 set the floor (ADR-16).

    Args:
        round_id: Which round.
        student: The caller.
        session: Database session.

    Returns:
        What each question ended at, and the state of the attempt.

    Raises:
        HTTPException: 409 when the round was already submitted.

    Side effects:
        Stamps the round, writes outcomes on its items, updates the ledger.
    """
    rnd, attempt = await _owned_round(session, round_id, student)
    if rnd.submitted_at is not None:
        raise HTTPException(status_code=409, detail="Lượt này đã nộp")

    outcomes = await _outcomes(session, attempt.id)
    now = _now()
    results: list[RoundResultItemOut] = []

    for item in rnd.items:
        correct_label = next((o["label"] for o in item.options if o.get("is_correct")), None)
        is_correct = item.chosen_label is not None and item.chosen_label == correct_label
        item.outcome = "đúng" if is_correct else "sai"

        outcome = outcomes[item.origin_question_id]
        if outcome.closed:
            # Already settled by an earlier round. Re-marking it could reopen a
            # closed question, and a question closes once.
            continue
        outcome.rounds_used += 1
        mark, reason, closed = mark_after_round(is_correct, outcome.rounds_used)
        outcome.mark = max(outcome.mark, mark)
        outcome.reason = reason.value
        outcome.closed = closed

        results.append(
            RoundResultItemOut(
                question_id=item.origin_question_id,
                outcome=item.outcome,
                new_mark=outcome.mark,
                rounds_used=outcome.rounds_used,
                rounds_left=max(0, MAX_ROUNDS_PER_QUESTION - outcome.rounds_used),
            )
        )

    rnd.submitted_at = now
    await session.commit()

    publication = await _publication(session, attempt.assessment_id)
    return RoundResultOut(
        round_id=round_id,
        per_question=results,
        attempt_state=_attempt_state(outcomes, True, _aware(publication.remediation_deadline), now),
    )


@router.post("/attempts/{attempt_id}/reports", response_model=ReportOut, status_code=201)
async def file_report(
    attempt_id: str,
    body: ReportIn,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> ReportOut:
    """File one "the assistant was hard to follow" report.

    The report is scoped to the attempt, not to a message: the assistant works
    across the whole assessment, so pointing at one turn would promise the
    teacher something narrower than what happened (ADR-19). It blocks nothing.

    Args:
        attempt_id: Which attempt.
        body: An optional note.
        student: The caller.
        session: Database session.

    Returns:
        The stored report id.

    Side effects:
        Inserts one report row.
    """
    await _owned_attempt(session, attempt_id, student)
    report = Report(attempt_id=attempt_id, note=body.note, created_at=_now())
    session.add(report)
    await session.commit()
    return ReportOut(report_id=report.id)
