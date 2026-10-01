"""Drafting a set of questions: one job per question, one brief for all of them.

Two constraints shape this, and they pull in opposite directions.

A whole draft cannot be one job. `llm_timeout_seconds × llm_max_attempts` is
what `tools/check_contract.py` compares against BE's patience for a job, and
that arithmetic only holds for **one** model call's worth of retries. Ten
questions in one job is ten times that, fifty questions is fifty -- so the
shape that satisfies the invariant is one question per job, fired and collected
later.

But ten jobs running independently is exactly how a set of questions loses its
coherence: if the brief could change while they run, questions 1-4 come from
one understanding of the topic and 5-10 from another, and nobody reading the
questions one at a time would see it. So the brief is written down once,
before anything is fired, and every job reads that same row. Coherence is
guaranteed by structure rather than by timing.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import drafting
from be.assessment_state import AssessmentState
from be.config import get_settings
from be.db import bind_sessions, prepare_schema
from be.models import AnswerOption, Assessment, DraftBrief, DraftItem, Method, Question, Teacher
from be.seed import seed_if_empty
from contracts import DraftQuestionCompleted, GeneratedOption, GeneratedQuestion, SolutionMethod


class FakeQueue:
    """Records what was queued and hands back results on demand."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, str, dict]] = []
        self.results: dict[str, tuple[str, object]] = {}

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str):
        job_id = f"job-{len(self.jobs)}"
        self.jobs.append((job_id, name, payload))
        return type("Queued", (), {"job_id": job_id})()

    def payloads(self) -> list[dict]:
        return [payload for _, _, payload in self.jobs]

    def finish(self, job_id: str, question: GeneratedQuestion) -> None:
        """Say a job completed with this question."""
        self.results[job_id] = (
            "ready",
            DraftQuestionCompleted(request_id="r", question=question).model_dump(mode="json"),
        )

    def lose(self, job_id: str) -> None:
        """Say the job's result aged out of Redis."""
        self.results[job_id] = ("gone", None)

    def break_(self, job_id: str) -> None:
        """Say the job ran and raised."""
        self.results[job_id] = ("failed", None)


def _good(stem: str) -> GeneratedQuestion:
    """A question that satisfies ADR-18: one right answer, labelled distractors, two methods."""
    return GeneratedQuestion(
        stem=stem,
        options=(
            GeneratedOption(label="A", text="đúng", is_correct=True),
            GeneratedOption(label="B", text="sai", is_correct=False, error_label="lỗi B"),
            GeneratedOption(label="C", text="sai", is_correct=False, error_label="lỗi C"),
        ),
        methods=(
            SolutionMethod(title="Cách 1", body="..."),
            SolutionMethod(title="Cách 2", body="..."),
        ),
        learning_objective="đạo hàm",
    )


def _two_right() -> GeneratedQuestion:
    """Breaks ADR-18 the way a real model does: two options marked correct."""
    return _good("Câu hỏng").model_copy(
        update={
            "options": (
                GeneratedOption(label="A", text="đúng", is_correct=True),
                GeneratedOption(label="B", text="cũng đúng", is_correct=True),
            )
        }
    )


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """A seeded database plus an empty draft belonging to the seeded teacher."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        teacher = await session.scalar(select(Teacher))
        assert teacher is not None
        draft = Assessment(
            teacher_id=teacher.id,
            title="Nháp mới",
            subject="Toán",
            grade="12",
            state=AssessmentState.EMPTY,
            created_at=datetime.now(UTC),
        )
        session.add(draft)
        await session.flush()
        session.add(
            DraftBrief(
                assessment_id=draft.id,
                topic_scope="đạo hàm của đa thức",
                difficulty="cơ bản",
                question_count=3,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
        draft_id = draft.id

    queue = FakeQueue()

    async def collect(pool, settings, job_id):
        return queue.results.get(job_id, ("pending", None))

    monkeypatch.setattr(drafting, "collect_result", collect)

    yield maker, draft_id, queue

    await engine.dispose()
    from be import db as db_module

    db_module._SESSION_MAKER = None


@pytest.mark.asyncio
async def test_every_job_carries_the_same_brief(stack) -> None:
    """The brief is read once and copied into each job.

    This is the whole reason the brief is a stored row. Ten jobs that each
    re-derived their own instructions -- from a conversation that is still
    going -- would produce a set whose first half and second half answer
    different questions, and reading the questions one at a time would not
    show it.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id)

    scopes = {payload["topic_scope"] for payload in queue.payloads()}
    counts = {payload["of_total"] for payload in queue.payloads()}

    assert len(queue.jobs) == 3
    assert scopes == {"đạo hàm của đa thức"}
    assert counts == {3}


@pytest.mark.asyncio
async def test_each_job_knows_which_question_of_the_set_it_is(stack) -> None:
    """Ordinals are distinct and cover the set.

    The jobs run independently, so nothing coordinates them. Telling each one
    its position is the cheapest nudge towards variety, and it is what lets
    the harvest write them back in the order the teacher asked for.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id)

    assert sorted(payload["ordinal"] for payload in queue.payloads()) == [1, 2, 3]


@pytest.mark.asyncio
async def test_harvest_writes_a_finished_question_in_full(stack) -> None:
    """A question arrives as a question, with its options and its solutions.

    ADR-18 says a question carries its answer key and its worked methods, so a
    harvest that wrote only the stem would produce a paper the tutoring phase
    cannot teach from.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id)

    queue.finish("job-0", _good("Đạo hàm của y = x² là gì?"))

    async with maker() as session:
        landed = await drafting.harvest(session, queue, get_settings(), draft_id)

    assert landed == 1

    async with maker() as session:
        question = await session.scalar(select(Question).where(Question.assessment_id == draft_id))
        assert question is not None
        options = (
            await session.scalars(
                select(AnswerOption).where(AnswerOption.question_id == question.id)
            )
        ).all()
        methods = (
            await session.scalars(select(Method).where(Method.question_id == question.id))
        ).all()

    assert question.stem == "Đạo hàm của y = x² là gì?"
    assert len(options) == 3
    assert sum(1 for option in options if option.is_correct) == 1
    assert all(option.error_label for option in options if not option.is_correct)
    assert len(methods) == 2


@pytest.mark.asyncio
async def test_the_first_question_moves_the_draft_out_of_empty(stack) -> None:
    """`EMPTY → HAS_QUESTIONS` happens through `advance`, not by assignment.

    ADR-01's empty state is what blocks publishing, so the moment it stops
    being true has to go through the one door that knows the lifecycle.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id)
        before = await session.get(Assessment, draft_id)
        assert before is not None and before.state == AssessmentState.EMPTY

    queue.finish("job-0", _good("Câu một"))

    async with maker() as session:
        await drafting.harvest(session, queue, get_settings(), draft_id)
        after = await session.get(Assessment, draft_id)

    assert after is not None
    assert after.state == AssessmentState.HAS_QUESTIONS


@pytest.mark.asyncio
async def test_a_question_that_breaks_adr_18_never_reaches_the_draft(stack) -> None:
    """Checked on the way in, and ours is not trusted for being ours.

    AGENT self-checks and falls back to prepared content, but the check that
    counts is this one: the draft is what a teacher will approve and a student
    will sit, so a malformed question has to be refused here or not at all.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id)

    queue.finish("job-0", _two_right())

    async with maker() as session:
        landed = await drafting.harvest(session, queue, get_settings(), draft_id)
        questions = (
            await session.scalars(select(Question).where(Question.assessment_id == draft_id))
        ).all()
        item = await session.scalar(
            select(DraftItem).where(DraftItem.assessment_id == draft_id, DraftItem.ordinal == 1)
        )

    assert landed == 0
    assert questions == []
    # `retry`, not `failed`: two options marked correct is chance rather than
    # a fixed fault, so the position is worth one more job. What stops it
    # looping is the attempt counter, not this status.
    assert item is not None and item.status == "retry"
    assert item.attempts == 1


@pytest.mark.asyncio
async def test_two_jobs_returning_the_same_stem_yield_one_question(stack) -> None:
    """Independent jobs can collide, and the draft must not show it twice.

    Nothing coordinates the jobs, so two of them writing the same question is
    an ordinary outcome rather than a bug -- and a paper with the same question
    twice is worse than a paper with one question fewer.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id)

    same = "Đạo hàm của y = x² là gì?"
    queue.finish("job-0", _good(same))
    queue.finish("job-1", _good(same))

    async with maker() as session:
        landed = await drafting.harvest(session, queue, get_settings(), draft_id)
        questions = (
            await session.scalars(select(Question).where(Question.assessment_id == draft_id))
        ).all()

    assert landed == 1
    assert len(questions) == 1


@pytest.mark.asyncio
async def test_a_result_that_aged_out_is_asked_again(stack) -> None:
    """A lost answer is retryable; a job that raised is not.

    Job results live an hour, so a teacher who starts a draft and comes back
    tomorrow finds them gone -- ordinary, and worth one more job. A job that
    ran and *raised* is different: asking again gets the same failure, so it
    does not pass through the attempt counter at all.

    And the assertion that matters is the second `fire`: a status nobody acts
    on would prove nothing, so this checks the position actually gets a new
    job while the failed one does not.
    """
    maker, draft_id, queue = stack
    settings = get_settings()

    async with maker() as session:
        await drafting.fire(session, queue, settings, draft_id)

    queue.lose("job-0")
    queue.break_("job-1")

    async with maker() as session:
        await drafting.harvest(session, queue, settings, draft_id)
        rows = {
            row.ordinal: row.status
            for row in await session.scalars(
                select(DraftItem).where(DraftItem.assessment_id == draft_id)
            )
        }

    assert rows == {1: "retry", 2: "failed", 3: "pending"}

    before = len(queue.jobs)
    async with maker() as session:
        requeued = await drafting.fire(session, queue, settings, draft_id)
        after = {
            row.ordinal: (row.status, row.attempts)
            for row in await session.scalars(
                select(DraftItem).where(DraftItem.assessment_id == draft_id)
            )
        }

    assert requeued == 1
    assert len(queue.jobs) == before + 1
    assert after[1] == ("pending", 2)
    assert after[2] == ("failed", 1)


@pytest.mark.asyncio
async def test_a_question_keeps_the_position_it_was_asked_for(stack) -> None:
    """`order_index` comes from the position, not from arrival order.

    The jobs run in parallel and finish in whatever order the model answers,
    which the first real run showed plainly: three jobs, three different
    completion times. Numbering questions by a running count therefore put
    them on the paper in arrival order -- a teacher who asked for 1, 2, 3 got
    2, 3, 1, silently, with no constraint to trip.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id)

    # The middle and last jobs answer first; the first one is still running.
    queue.finish("job-1", _good("Câu hai"))
    queue.finish("job-2", _good("Câu ba"))

    async with maker() as session:
        await drafting.harvest(session, queue, get_settings(), draft_id)

    queue.finish("job-0", _good("Câu một"))

    async with maker() as session:
        await drafting.harvest(session, queue, get_settings(), draft_id)
        numbered = {
            question.order_index: question.stem
            for question in await session.scalars(
                select(Question).where(Question.assessment_id == draft_id)
            )
        }

    assert numbered == {1: "Câu một", 2: "Câu hai", 3: "Câu ba"}


@pytest.mark.asyncio
async def test_a_refused_question_is_asked_again_but_not_forever(stack) -> None:
    """A malformed answer costs a retry, not the position.

    Two of the three refusals are chance rather than a fixed fault: a model
    marking two options correct, and two parallel jobs writing the same stem.
    Marking those `failed` for good left the draft permanently short, and
    nothing -- not even firing again -- could fill the gap. But deleting the
    row unconditionally is the other failure: a question the model cannot get
    right would be re-queued on every read, spending the budget forever.
    """
    maker, draft_id, queue = stack
    settings = get_settings()

    async with maker() as session:
        await drafting.fire(session, queue, settings, draft_id)

    queue.finish("job-0", _two_right())

    async with maker() as session:
        await drafting.harvest(session, queue, settings, draft_id)
        # Firing again picks the position back up, because it is retryable.
        requeued = await drafting.fire(session, queue, settings, draft_id)

    assert requeued == 1

    # Same answer twice more, and the position gives up rather than looping.
    for job in ("job-3", "job-4"):
        queue.finish(job, _two_right())
        async with maker() as session:
            await drafting.harvest(session, queue, settings, draft_id)
            await drafting.fire(session, queue, settings, draft_id)

    async with maker() as session:
        item = await session.scalar(
            select(DraftItem).where(DraftItem.assessment_id == draft_id, DraftItem.ordinal == 1)
        )
        again = await drafting.fire(session, queue, settings, draft_id)

    assert item is not None and item.status == "failed"
    assert again == 0


@pytest.mark.asyncio
async def test_firing_twice_does_not_queue_the_same_position_twice(stack) -> None:
    """Two tool calls arriving together cost one set of jobs, not two.

    Reading the taken positions and inserting rows are two statements with a
    gap. The unique index decides, and the loser must not take its own three
    jobs down with it -- they are already on the queue and already spending
    model calls.
    """
    maker, draft_id, queue = stack
    settings = get_settings()

    async with maker() as session:
        first = await drafting.fire(session, queue, settings, draft_id)

    async with maker() as session:
        second = await drafting.fire(session, queue, settings, draft_id)
        rows = (
            await session.scalars(select(DraftItem).where(DraftItem.assessment_id == draft_id))
        ).all()

    assert first == 3
    assert second == 0
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_a_brief_asking_for_more_than_the_contract_allows_fires_nothing(stack) -> None:
    """The cap is checked before the first job, not discovered at the 51st.

    `of_total` is bounded at 50 in the contract. Firing job by job meant a
    brief asking for 60 queued fifty jobs and then raised, leaving fifty model
    calls running, no rows to collect them by, and the same thing happening on
    every retry.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        brief = await session.get(DraftBrief, draft_id)
        assert brief is not None
        brief.question_count = 60
        await session.commit()

    async with maker() as session:
        queued = await drafting.fire(session, queue, get_settings(), draft_id)

    assert queued == 0
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_a_new_brief_discards_questions_written_for_the_old_one(stack) -> None:
    """Re-briefing starts a round; it does not edit work in flight.

    This is the claim the whole design rests on -- that a set of questions is
    written against one understanding of the topic. Without it, "make them
    harder" would let jobs fired under the old scope land in the same draft as
    jobs fired under the new one, and the paper would be half one thing and
    half another with nothing on any single question looking wrong.
    """
    maker, draft_id, queue = stack
    settings = get_settings()

    async with maker() as session:
        await drafting.fire(session, queue, settings, draft_id)

    async with maker() as session:
        await drafting.rebrief(session, draft_id, topic_scope="tích phân", question_count=2)

    # The job fired under the old brief answers after the new brief is written.
    queue.finish("job-0", _good("Câu của brief cũ"))

    async with maker() as session:
        landed = await drafting.harvest(session, queue, settings, draft_id)
        questions = (
            await session.scalars(select(Question).where(Question.assessment_id == draft_id))
        ).all()

    assert landed == 0
    assert questions == []
