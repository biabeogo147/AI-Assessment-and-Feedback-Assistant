"""Writing a set of questions: fire the jobs, collect them later.

Two rules pull against each other here, and the shape of this module is what
satisfies both.

**One job per question.** `tools/check_contract.py` compares
`LLM_TIMEOUT_SECONDS × LLM_MAX_ATTEMPTS` against BE's patience for a single
job. That arithmetic holds for one question's worth of retries and no more, so
a task that wrote a whole set in one job -- which is what this replaced -- made
the check quietly wrong about the handler that spent the most model calls.

**One brief for every job.** The jobs run independently and cannot see each
other, so if the instructions could still change while they run, questions
1-4 would come from one understanding of the topic and 5-10 from another. That
is a defect nobody finds by reading the questions one at a time. The brief is
therefore a stored row with a version, every job records the version it was
fired under, and a question written for an older brief is **discarded** rather
than merged. Re-briefing starts a round; it does not edit work in flight.

Nothing here waits. A teacher who asks for ten questions gets an answer at
once and the questions appear as they land -- the same trade the student side
makes when it writes a remediation question ahead of time.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from be.agent_gateway import collect_result, enqueue_task, validate_question
from be.assessment_state import AssessmentState, advance, assert_editable
from be.config import Settings
from be.models import AnswerOption, Assessment, DraftBrief, DraftItem, Method, Question
from contracts import (
    WRITE_DRAFT_QUESTION_TASK,
    DraftQuestionCompleted,
    DraftQuestionRequested,
    GeneratedQuestion,
)

logger = logging.getLogger(__name__)

# The contract bounds `of_total` at fifty, and that bound has to be checked
# before the first job rather than discovered at the fifty-first: firing job by
# job meant a brief asking for sixty queued fifty jobs and then raised, leaving
# fifty model calls running with no rows to collect them by.
_MOST_QUESTIONS = 50

# How many jobs one position may cost. Three, because two of the three ways a
# question is refused are chance -- a duplicate stem from parallel jobs, a
# model marking two options correct -- and the third try is where chance stops
# being the explanation.
_MOST_ATTEMPTS = 3

# Statuses `fire` will pick back up. A position that is `pending` has a job
# running, `ready` is done, and `failed` has given up.
_RETRYABLE = frozenset({"retry"})


def _comparable(stem: str) -> str:
    """Reduce a stem to what makes two questions the same question.

    Whitespace and case only. Deliberately **not** `be.resolve.normalise`,
    which was written for class names: it strips a leading "lớp" and removes
    every space, so "Lớp 12A có 30 học sinh..." and "12A có 30 học sinh..."
    would compare equal -- two different questions called one.

    This does not need to match AGENT's own rule, because the stems BE sends
    in `banned_stems` travel **raw** and AGENT normalises them with its own
    function on arrival. Two normalisers that had to agree across a service
    boundary would be, in the words of AGENT's own docstring, a disagreement
    with a date on it.

    Args:
        stem: A question stem as stored.

    Returns:
        The stem with runs of whitespace collapsed, case-folded.
    """
    return " ".join(stem.split()).casefold()


async def _stems(session: AsyncSession, assessment_id: str) -> list[str]:
    """Every stem already in the draft, as stored."""
    written = await session.scalars(
        select(Question.stem).where(Question.assessment_id == assessment_id)
    )
    return list(written)


async def fire(session: AsyncSession, pool: object, settings: Settings, assessment_id: str) -> int:
    """Queue one job per question the brief still needs.

    A position is queued when it has no row or its row is `retry`. `pending`,
    `ready` and `failed` are all left alone, so calling this twice does not
    double-queue and a position that gave up stays given up.

    Args:
        session: Database session. Committed per row.
        pool: The arq pool, or None when the queue was unreachable.
        settings: Process settings supplying the queue name.
        assessment_id: Which draft.

    Returns:
        How many jobs were queued.

    Raises:
        HTTPException: 409 when the assessment's content is locked (ADR-01).

    Side effects:
        Writes jobs onto the queue and a `DraftItem` row for each, committing
        after each one.
    """
    brief = await session.get(DraftBrief, assessment_id)
    if brief is None:
        # No brief means nothing was agreed yet, and a half-specified set
        # should not be written at all.
        logger.warning("nothing queued for %s: no brief", assessment_id)
        return 0

    assessment = await session.get(Assessment, assessment_id)
    if assessment is None:
        logger.warning("nothing queued for %s: no such assessment", assessment_id)
        return 0

    # ADR-01: approval locks content, and writing questions into an approved
    # paper is exactly what the lock is for.
    assert_editable(assessment)

    if not 1 <= brief.question_count <= _MOST_QUESTIONS:
        logger.warning(
            "nothing queued for %s: brief asks for %d, allowed 1..%d",
            assessment_id,
            brief.question_count,
            _MOST_QUESTIONS,
        )
        return 0

    rows = {
        row.ordinal: row
        for row in await session.scalars(
            select(DraftItem).where(DraftItem.assessment_id == assessment_id)
        )
    }
    banned = tuple(await _stems(session, assessment_id))
    now = datetime.now(UTC)
    queued = 0

    for ordinal in range(1, brief.question_count + 1):
        row = rows.get(ordinal)
        if row is not None and row.status not in _RETRYABLE:
            continue

        asked = DraftQuestionRequested(
            request_id=f"{assessment_id}:{ordinal}:{brief.version}",
            subject=assessment.subject,
            grade=assessment.grade,
            topic_scope=brief.topic_scope,
            difficulty=brief.difficulty,
            ordinal=ordinal,
            of_total=brief.question_count,
            banned_stems=banned,
        )
        job_id = await enqueue_task(
            pool, settings, WRITE_DRAFT_QUESTION_TASK, asked.model_dump(mode="json")
        )
        if job_id is None:
            # The queue is down. No row written, so the next call tries again.
            continue

        if row is None:
            session.add(
                DraftItem(
                    assessment_id=assessment_id,
                    ordinal=ordinal,
                    job_id=job_id,
                    status="pending",
                    attempts=1,
                    brief_version=brief.version,
                    created_at=now,
                )
            )
        else:
            row.job_id = job_id
            row.status = "pending"
            row.attempts += 1
            row.brief_version = brief.version

        try:
            # Committed per row, following `_write_ahead` on the student side:
            # two callers can both get past the check above, and the loser of
            # the unique index must not take the jobs that are already running
            # down with it.
            await session.commit()
        except IntegrityError:
            await session.rollback()
            logger.info("position %d of %s was taken by another caller", ordinal, assessment_id)
            continue
        queued += 1

    logger.info("queued %d question(s) for draft %s", queued, assessment_id)
    return queued


async def rebrief(
    session: AsyncSession,
    assessment_id: str,
    *,
    topic_scope: str,
    question_count: int,
    difficulty: str = "",
) -> int:
    """Replace the brief, starting a new round of generation.

    Bumping the version is what discards work in flight: a job fired under the
    old brief still finishes and still returns a question, and `harvest` drops
    it rather than letting it share a paper with questions written to
    different instructions.

    Args:
        session: Database session. Committed by this function.
        assessment_id: Which draft.
        topic_scope: The new scope, in the teacher's words.
        question_count: How many questions the set should have now.
        difficulty: How hard, in the teacher's words.

    Returns:
        The new version number.

    Side effects:
        Writes or replaces the brief row and commits.
    """
    brief = await session.get(DraftBrief, assessment_id)
    now = datetime.now(UTC)

    if brief is None:
        brief = DraftBrief(
            assessment_id=assessment_id,
            topic_scope=topic_scope,
            difficulty=difficulty,
            question_count=question_count,
            version=1,
            created_at=now,
        )
        session.add(brief)
    else:
        brief.topic_scope = topic_scope
        brief.difficulty = difficulty
        brief.question_count = question_count
        brief.version += 1

    version = brief.version
    await session.commit()
    logger.info("draft %s is now on brief version %d", assessment_id, version)
    return version


async def _write(
    session: AsyncSession, assessment_id: str, order_index: int, question: GeneratedQuestion
) -> None:
    """Store one question with its options and its worked solutions.

    Args:
        session: Database session. Not committed here.
        assessment_id: Which draft.
        order_index: The number the question carries on the paper, which is the
            position the teacher asked for rather than the order it arrived in.
        question: The validated question.

    Side effects:
        Adds a `Question` and its `AnswerOption` and `Method` rows.
    """
    stored = Question(
        assessment_id=assessment_id,
        order_index=order_index,
        stem=question.stem,
        learning_objective=question.learning_objective,
    )
    session.add(stored)
    await session.flush()

    for option in question.options:
        session.add(
            AnswerOption(
                question_id=stored.id,
                label=option.label,
                text=option.text,
                is_correct=option.is_correct,
                error_label=option.error_label,
            )
        )
    for index, method in enumerate(question.methods, start=1):
        session.add(
            Method(
                question_id=stored.id,
                order_index=index,
                title=method.title,
                body=method.body,
            )
        )


def _give_up_or_retry(row: DraftItem, why: str) -> None:
    """Mark a position for another try, or stop spending on it.

    Args:
        row: The item whose job produced nothing usable.
        why: What went wrong, for the log.

    Side effects:
        Sets `row.status`.
    """
    if row.attempts >= _MOST_ATTEMPTS:
        row.status = "failed"
        logger.warning(
            "position %d of %s gave up after %d attempt(s): %s",
            row.ordinal,
            row.assessment_id,
            row.attempts,
            why,
        )
        return
    row.status = "retry"
    logger.info("position %d of %s will be asked again: %s", row.ordinal, row.assessment_id, why)


async def harvest(
    session: AsyncSession, pool: object, settings: Settings, assessment_id: str
) -> int:
    """Move finished jobs into the draft, and decide what to do with the rest.

    Called from wherever the draft is read, because BE has no background
    worker and a result nobody collects is a result that expires.

    **Everything is checked here, on the way in.** AGENT checks its own output
    and falls back to prepared content, but this is the check that counts: the
    draft is what a teacher approves and a student sits, so a question that
    breaks ADR-18 has to be refused at this door or not at all. Two jobs
    returning the same stem is an ordinary outcome rather than a bug -- nothing
    coordinates them -- and a paper with one question twice is worse than a
    paper with one question fewer.

    A question written for an older brief is dropped here too. That is the
    mechanism behind "re-briefing starts a round": the old job still finishes,
    and its answer still arrives, and it still does not enter this paper.

    Args:
        session: Database session. Committed by this function.
        pool: The arq pool, or None.
        settings: Process settings.
        assessment_id: Which draft.

    Returns:
        How many questions entered the draft on this call.

    Side effects:
        Writes questions, marks or deletes rows, and moves the assessment out
        of `EMPTY` on the first question to land.
    """
    brief = await session.get(DraftBrief, assessment_id)
    waiting = list(
        await session.scalars(
            select(DraftItem).where(
                DraftItem.assessment_id == assessment_id, DraftItem.status == "pending"
            )
        )
    )
    if not waiting or brief is None:
        return 0

    seen = {_comparable(stem) for stem in await _stems(session, assessment_id)}
    taken = set(
        await session.scalars(
            select(Question.order_index).where(Question.assessment_id == assessment_id)
        )
    )
    landed = 0

    for row in sorted(waiting, key=lambda item: item.ordinal):
        if row.brief_version != brief.version or row.ordinal > brief.question_count:
            # Written for instructions that no longer apply, or for a position
            # a shorter brief no longer has. Deleted rather than marked, so the
            # bookkeeping of the old round does not follow the new one.
            logger.info("dropping stale position %d of %s", row.ordinal, assessment_id)
            await session.delete(row)
            continue

        state, raw = await collect_result(pool, settings, row.job_id)
        if state == "pending":
            continue
        if state == "gone":
            # Ordinary, not exceptional: results live an hour and a teacher may
            # come back tomorrow. Retryable, and bounded like the rest.
            _give_up_or_retry(row, "kết quả đã hết hạn trong Redis")
            continue
        if state == "failed":
            # The job itself raised. Asking again gets the same failure, so
            # this one does not go through the attempt counter.
            row.status = "failed"
            logger.warning("job for position %d of %s raised", row.ordinal, assessment_id)
            continue

        try:
            question = DraftQuestionCompleted.model_validate(raw).question
            validate_question(question)
        except Exception:
            _give_up_or_retry(row, "câu trả về sai hình dạng ADR-18")
            continue

        if _comparable(question.stem) in seen:
            _give_up_or_retry(row, "đề trùng một câu đã có")
            continue

        if row.ordinal in taken:
            # The position already holds a question, which means a duplicate
            # job for one ordinal got through. Keep the first and stop.
            _give_up_or_retry(row, "vị trí này đã có câu")
            continue

        # The position the teacher asked for, not the order it arrived in. The
        # jobs finish in whatever order the model answers, so numbering by a
        # running count put questions on the paper in arrival order -- a
        # teacher who asked for 1, 2, 3 got 2, 3, 1, with no constraint to
        # trip on the way.
        await _write(session, assessment_id, row.ordinal, question)
        seen.add(_comparable(question.stem))
        taken.add(row.ordinal)
        row.status = "ready"
        landed += 1

    if landed:
        assessment = await session.get(Assessment, assessment_id)
        if assessment is not None and AssessmentState(assessment.state) is AssessmentState.EMPTY:
            # Through the one door, because ADR-01's empty state is what blocks
            # publishing and the moment it stops being true is a lifecycle
            # event rather than an assignment.
            advance(assessment, AssessmentState.HAS_QUESTIONS)

    await session.commit()
    return landed


async def pending_count(session: AsyncSession, assessment_id: str) -> int:
    """How many positions still have a job running.

    Approving a draft while questions are still being written would approve a
    paper the teacher has not seen, so the approval endpoint asks this first.

    Args:
        session: Database session.
        assessment_id: Which draft.

    Returns:
        The number of `pending` positions.
    """
    return (
        await session.scalar(
            select(func.count())
            .select_from(DraftItem)
            .where(DraftItem.assessment_id == assessment_id, DraftItem.status == "pending")
        )
        or 0
    )
