"""The first tools that write, and the gate in front of them.

Two rules decide everything here.

**Agent writes content; teacher decides status.** Creating a draft and filling
it with questions are reversible while the paper is unapproved, so the
assistant may do them. Approving and publishing are where a teacher takes
responsibility -- ADR-01 for the first, ADR-02 for the second -- so no tool
reaches them, and `tools/check_contract.py` now refuses a `teacher_tools.py`
that mentions `advance` or `withdraw` at all.

**Enough context before anything is written.** The teacher's rule, and it is
about coherence rather than tidiness: the questions are written by independent
jobs, so a brief that is still being assembled produces a set whose halves
answer different questions. `create_draft` therefore refuses an incomplete
brief and says which fields are missing, which is what turns "ask first" from
a line in a prompt into something the model cannot skip.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import drafting
from be.assessment_state import AssessmentState
from be.db import bind_sessions, prepare_schema
from be.identity import Asking
from be.models import Assessment, DraftBrief, DraftItem, Teacher
from be.seed import seed_if_empty
from be.teacher_tools import catalog_for, execute
from contracts import DraftQuestionCompleted, GeneratedOption, GeneratedQuestion, SolutionMethod


class FakeQueue:
    """Records what was queued, and answers for the jobs a test finishes."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, dict]] = []
        self.results: dict[str, tuple[str, object]] = {}

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str):
        self.jobs.append((name, payload))
        return type("Queued", (), {"job_id": f"job-{len(self.jobs)}"})()

    def finish(self, job_id: str, question: GeneratedQuestion) -> None:
        """Say a job completed with this question."""
        self.results[job_id] = (
            "ready",
            DraftQuestionCompleted(request_id="r", question=question).model_dump(mode="json"),
        )


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """A seeded database, the asking teacher, and a queue that records.

    Result collection is stubbed because the write tools now harvest before
    they decide anything, and arq's `Job` wants a real Redis to ask. A job no
    test has finished reads as still running, which is what a freshly queued
    round actually is.
    """
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)

    queue = FakeQueue()

    async def collect(_pool, _settings, job_id):
        return queue.results.get(job_id, ("pending", None))

    monkeypatch.setattr(drafting, "collect_result", collect)

    yield maker, queue

    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _asking(session) -> Asking:
    teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
    assert teacher is not None
    return Asking.of(teacher)


_FULL = {
    "subject": "Toán",
    "grade": "12",
    "topic_scope": "đạo hàm của đa thức",
    "question_count": 3,
    "difficulty": "cơ bản",
}


@pytest.mark.asyncio
async def test_a_complete_brief_creates_an_empty_draft(stack) -> None:
    """The draft exists, belongs to the asking teacher, and holds no questions yet.

    `EMPTY` rather than `HAS_QUESTIONS`, because ADR-01 gives the empty state
    its own rule: it is what blocks publishing a paper with nothing on it.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        answer = await execute(session, asking, "create_draft", dict(_FULL), pool=queue)

        draft = await session.get(Assessment, answer["assessment_id"])
        brief = await session.get(DraftBrief, answer["assessment_id"])

    assert answer["created"] is True
    assert draft is not None
    assert draft.teacher_id == asking.teacher_id
    assert draft.state == AssessmentState.EMPTY
    assert brief is not None
    assert brief.topic_scope == "đạo hàm của đa thức"
    assert brief.question_count == 3
    assert brief.version == 1


@pytest.mark.asyncio
async def test_an_incomplete_brief_names_what_is_missing_and_writes_nothing(stack) -> None:
    """The refusal is the mechanism, not a courtesy.

    A model told in a prompt to gather context first can forget; a tool that
    will not run without the fields cannot be forgotten. And naming the
    missing fields is what lets the assistant ask a useful question instead of
    guessing -- ADR-05's input gate, in the shape ADR-23 already uses for an
    ambiguous class name.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        answer = await execute(
            session,
            asking,
            "create_draft",
            {"subject": "Toán", "topic_scope": "đạo hàm"},
            pool=queue,
        )
        drafts = (await session.scalars(select(Assessment))).all()

    assert answer["created"] is False
    assert set(answer["missing"]) == {"grade", "question_count"}
    # Only the seeded assessment; nothing was written.
    assert len(drafts) == 1


@pytest.mark.asyncio
async def test_a_brief_asking_for_too_many_questions_is_refused_at_the_door(stack) -> None:
    """The cap is part of the brief being valid, not a surprise later.

    Discovering it while firing jobs meant fifty model calls had already been
    spent before anything complained.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        answer = await execute(
            session, asking, "create_draft", dict(_FULL, question_count=60), pool=queue
        )

    assert answer["created"] is False
    # Not `missing`: the field was filled, it was filled with a number out of
    # range. Answering "chưa đủ thông tin" for a field the model already filled
    # sends it round to supply the same value again.
    assert answer["missing"] == []
    assert answer["unreadable"] == ["question_count"]


@pytest.mark.asyncio
async def test_drafting_starts_one_job_per_question(stack) -> None:
    """The jobs go out and nothing waits for them."""
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        made = await execute(session, asking, "create_draft", dict(_FULL), pool=queue)

    async with maker() as session:
        asking = await _asking(session)
        started = await execute(
            session, asking, "start_drafting", {"assessment_id": made["assessment_id"]}, pool=queue
        )

    assert started["started"] is True
    assert started["queued"] == 3
    assert len(queue.jobs) == 3
    assert {name for name, _ in queue.jobs} == {"write_draft_question"}


@pytest.mark.asyncio
async def test_drafting_twice_does_not_start_a_second_round(stack) -> None:
    """One round at a time, so two sets of instructions never share a paper.

    Overlapping rounds is the failure the frozen brief exists to prevent, and
    the cheapest way to prevent it is to refuse while anything is still
    running.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        made = await execute(session, asking, "create_draft", dict(_FULL), pool=queue)
        again = await execute(
            session, asking, "start_drafting", {"assessment_id": made["assessment_id"]}, pool=queue
        )
        assert again["started"] is True

        second = await execute(
            session, asking, "start_drafting", {"assessment_id": made["assessment_id"]}, pool=queue
        )

    assert second["started"] is False
    assert len(queue.jobs) == 3


@pytest.mark.asyncio
async def test_no_tool_writes_into_an_approved_paper(stack) -> None:
    """ADR-01: approval locks the content.

    This is the first caller of `assert_editable`, and the lock is the whole
    reason approving means anything -- if questions could still change
    afterwards, the teacher approved something else.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        made = await execute(session, asking, "create_draft", dict(_FULL), pool=queue)
        draft = await session.get(Assessment, made["assessment_id"])
        assert draft is not None
        # Set by hand only because nothing else can yet: the approve endpoint
        # arrives in phase 4, and this line becomes a call to it then. Allowed
        # here and nowhere in `teacher_tools.py`, where `tools-decide-nothing`
        # refuses exactly this assignment.
        draft.state = AssessmentState.APPROVED
        await session.commit()

        locked = await execute(
            session, asking, "start_drafting", {"assessment_id": made["assessment_id"]}, pool=queue
        )

    assert locked["started"] is False
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_a_tool_cannot_draft_into_another_teachers_paper(stack) -> None:
    """ADR-22, on the write side.

    The refusal reads the same as for a paper that does not exist, because two
    distinguishable answers would let anyone probe for what other teachers
    have.
    """
    maker, queue = stack

    async with maker() as session:
        stranger = Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002")
        session.add(stranger)
        await session.flush()
        theirs = Assessment(
            teacher_id=stranger.id,
            title="Đề của người khác",
            subject="Toán",
            grade="11",
            state=AssessmentState.EMPTY,
            created_at=datetime.now(UTC),
        )
        session.add(theirs)
        await session.flush()
        session.add(
            DraftBrief(
                assessment_id=theirs.id,
                topic_scope="của người khác",
                question_count=2,
                version=1,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
        stranger_draft = theirs.id

    async with maker() as session:
        asking = await _asking(session)
        refused = await execute(
            session, asking, "start_drafting", {"assessment_id": stranger_draft}, pool=queue
        )
        absent = await execute(
            session, asking, "start_drafting", {"assessment_id": "không-tồn-tại"}, pool=queue
        )

    assert refused == absent
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_the_catalog_offers_only_reversible_writes(stack) -> None:
    """A tool described to the model is a tool it will try, so the list is the contract.

    Nothing here approves or publishes. That is not an omission: ADR-05 keeps
    those behind a form and a confirmation, and the cheapest way to honour it is
    for the chat flow to have no such verb at all. ADR-05's line is about
    actions that **cannot be taken back**, not about writing -- which is why
    three writing tools sit here without crossing it: every one of them is
    reversible while the paper is unapproved.
    """
    maker, _ = stack

    async with maker() as session:
        asking = await _asking(session)
        offered = {tool.name for tool in catalog_for(asking)}

    # The durable half: no name here releases work to students, however many
    # tools get added later.
    assert not any(
        word in name
        for name in offered
        for word in ("approve", "publish", "release", "withdraw", "duyet", "phat_hanh")
    )
    # And the tripwire: a sixth tool makes this red and has to argue for itself.
    assert offered == {
        "find_class",
        "class_assessment_summary",
        "create_draft",
        "start_drafting",
        "draft_progress",
    }


@pytest.mark.asyncio
async def test_a_started_round_is_visible_as_pending_work(stack) -> None:
    """Approval needs to know whether questions are still being written.

    Approving a half-written paper would approve questions the teacher has
    never seen, so the count has to be readable before the approval endpoint
    exists to use it.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        made = await execute(session, asking, "create_draft", dict(_FULL), pool=queue)
        await execute(
            session, asking, "start_drafting", {"assessment_id": made["assessment_id"]}, pool=queue
        )

    async with maker() as session:
        rows = (
            await session.scalars(
                select(DraftItem).where(DraftItem.assessment_id == made["assessment_id"])
            )
        ).all()

    assert len(rows) == 3
    assert {row.status for row in rows} == {"pending"}
    assert {row.brief_version for row in rows} == {1}


def _good(stem: str) -> GeneratedQuestion:
    """A question satisfying ADR-18: one right answer, labelled distractors, two methods."""
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


@pytest.mark.asyncio
async def test_no_job_is_fired_for_a_draft_without_a_brief(stack) -> None:
    """The gate is about jobs, not about rows.

    The refusal test above proves no draft is created from an incomplete brief.
    This one proves the part that costs money: a paper with no brief at all
    spends nothing, because the brief is what every job is written from.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        bare = Assessment(
            teacher_id=asking.teacher_id,
            title="Đề không có brief",
            subject="Toán",
            grade="12",
            state=AssessmentState.EMPTY,
            created_at=datetime.now(UTC),
        )
        session.add(bare)
        await session.commit()

        refused = await execute(
            session, asking, "start_drafting", {"assessment_id": bare.id}, pool=queue
        )

    assert refused["started"] is False
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_asking_twice_opens_two_drafts_rather_than_reusing_one(stack) -> None:
    """Two requests are two papers.

    Pinned because both alternatives are worse: reusing the first draft would
    quietly merge two briefs into one paper, and refusing the second would stop
    a teacher preparing two papers in one sitting. The cost is that a turn
    failing after this point leaves an empty draft behind, which `backlog.md`
    records, because clearing one needs a delete path that does not exist yet.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        first = await execute(session, asking, "create_draft", dict(_FULL), pool=queue)
        second = await execute(session, asking, "create_draft", dict(_FULL), pool=queue)

    assert first["created"] is True
    assert second["created"] is True
    assert first["assessment_id"] != second["assessment_id"]


@pytest.mark.asyncio
async def test_progress_collects_a_finished_question_into_the_draft(stack) -> None:
    """The only path by which a question written by a job reaches the paper.

    BE runs no background worker, so a finished job sits in Redis until
    something asks for it. Nothing did until this tool existed: the answers aged
    out after an hour, the draft stayed empty, and no new round could start
    because the old one was pending forever.
    """
    maker, queue = stack

    async with maker() as session:
        asking = await _asking(session)
        made = await execute(session, asking, "create_draft", dict(_FULL), pool=queue)
        await execute(
            session, asking, "start_drafting", {"assessment_id": made["assessment_id"]}, pool=queue
        )

    queue.finish("job-1", _good("Đạo hàm của y = x² là gì?"))

    async with maker() as session:
        asking = await _asking(session)
        progress = await execute(
            session, asking, "draft_progress", {"assessment_id": made["assessment_id"]}, pool=queue
        )

    assert progress["found"] is True
    assert progress["just_landed"] == 1
    assert progress["written"] == ["Đạo hàm của y = x² là gì?"]
    assert progress["asked_for"] == 3
    assert progress["still_drafting"] == 2
    # The first harvested question is what moves the paper off `EMPTY`, and
    # `advance()` is the only door it can go through.
    assert progress["state"] == AssessmentState.HAS_QUESTIONS
