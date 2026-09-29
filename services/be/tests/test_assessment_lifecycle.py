"""The four states of an assessment, and who owns one.

ADR-01 gives an assessment four states and two rules about them: approval
**locks the content**, and approval must be reversible because it is not the
last gate. Until now none of that existed in code -- ADR-01 said so itself, in
a line reading "Chưa có ở backend: không model, không endpoint, không test nào
biết tới bốn trạng thái này".

The first test here is the one `AGENTS.md` names in its invariant table as
"Teacher approves an assessment before release". It was in the group of rules
nothing enforced; this file is what moves it out.

Ownership is tested at the schema, not through a route, because no teacher
route exists yet. What can be proved today is that every class and every
assessment has an owner and that a query filtered by a different teacher comes
back empty -- which is the whole of what this change adds. The authorisation
that uses it arrives with the tool executor.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.assessment_state import AssessmentState, advance, assert_editable
from be.db import bind_sessions, prepare_schema
from be.models import Assessment, SchoolClass, Teacher
from be.seed import seed_if_empty


@pytest_asyncio.fixture
async def session():
    """A seeded in-memory database, session open."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as open_session:
        await seed_if_empty(open_session)
        yield open_session

    await engine.dispose()
    db_module._SESSION_MAKER = None


def _draft() -> Assessment:
    """An assessment with no questions yet, detached from any session."""
    return Assessment(
        title="Đề đang soạn",
        subject="Toán",
        grade="12",
        state=AssessmentState.EMPTY,
    )


def test_teacher_approves_an_assessment_before_release() -> None:
    """Publishing without approval is refused.

    This is the invariant `AGENTS.md` lists as needing a test when UC-02 is
    built. ADR-05 calls approval the first of three teacher-in-the-loop gates,
    and a gate that can be walked around is not a gate.
    """
    assessment = _draft()
    advance(assessment, AssessmentState.HAS_QUESTIONS)

    with pytest.raises(HTTPException) as refused:
        advance(assessment, AssessmentState.PUBLISHED)

    assert refused.value.status_code == 409
    assert assessment.state == AssessmentState.HAS_QUESTIONS


def test_an_assessment_walks_the_four_states_of_adr_01() -> None:
    """The whole path, in order: empty, has questions, approved, published."""
    assessment = _draft()

    for state in (
        AssessmentState.HAS_QUESTIONS,
        AssessmentState.APPROVED,
        AssessmentState.PUBLISHED,
    ):
        advance(assessment, state)
        assert assessment.state == state


def test_approval_locks_the_content() -> None:
    """Questions may not be edited once the assessment is approved.

    ADR-01: "Duyệt khoá nội dung". Without this, approving means nothing --
    which is the ADR's own argument for the rule.
    """
    assessment = _draft()
    advance(assessment, AssessmentState.HAS_QUESTIONS)
    assert_editable(assessment)  # still open, so this must not raise

    advance(assessment, AssessmentState.APPROVED)

    with pytest.raises(HTTPException) as refused:
        assert_editable(assessment)
    assert refused.value.status_code == 409


def test_unapproving_reopens_the_content() -> None:
    """Approval is reversible while the assessment is unpublished.

    ADR-01 requires the edge back to editing, because approval is not the last
    gate and a teacher who spots a bad question after approving must not be
    stuck with it.
    """
    assessment = _draft()
    advance(assessment, AssessmentState.HAS_QUESTIONS)
    advance(assessment, AssessmentState.APPROVED)

    advance(assessment, AssessmentState.HAS_QUESTIONS)

    assert assessment.state == AssessmentState.HAS_QUESTIONS
    assert_editable(assessment)


def test_a_published_assessment_never_returns_to_editing() -> None:
    """Publishing closes the door on editing, and only on editing.

    ADR-01 forbids the way back to authoring: changing a paper under the
    students sitting it is the one thing publishing must prevent.

    `APPROVED` is deliberately absent from this loop. ADR-02 says withdrawal
    returns an assessment to *đã duyệt* with its content still locked, so
    `published → approved` is a legitimate future edge. Asserting it illegal
    here would make this test a ratchet against a decision already taken.
    """
    assessment = _draft()
    advance(assessment, AssessmentState.HAS_QUESTIONS)
    advance(assessment, AssessmentState.APPROVED)
    advance(assessment, AssessmentState.PUBLISHED)

    for state in (AssessmentState.EMPTY, AssessmentState.HAS_QUESTIONS):
        with pytest.raises(HTTPException):
            advance(assessment, state)


def test_an_assessment_starts_empty_before_it_is_ever_saved() -> None:
    """A newly built assessment is in the empty state, not in no state at all.

    A column default is applied by the INSERT, so between `Assessment(...)`
    and the flush the attribute is None. Every path that creates an assessment
    and adds its first question in one unit of work goes through that gap, and
    the state machine has to answer there too -- with a refusal in Vietnamese
    when the edge is wrong, never with a `ValueError` about None.
    """
    fresh = Assessment(teacher_id="whoever", title="Chưa lưu", subject="Toán", grade="12")

    advance(fresh, AssessmentState.HAS_QUESTIONS)

    assert fresh.state == AssessmentState.HAS_QUESTIONS


@pytest.mark.asyncio
async def test_a_state_outside_the_lifecycle_cannot_be_stored(session) -> None:
    """The database refuses a state ADR-01 does not define.

    `advance` is the only door, but a door is only a door while everyone uses
    it. One stray assignment -- `state = "draft"`, the value this column used
    to default to -- would otherwise be written happily and then raise on the
    next read of the table, in a route that has nothing to do with whoever
    wrote it.
    """
    assessment = await session.scalar(select(Assessment))
    assert assessment is not None

    assessment.state = "draft"

    with pytest.raises(StatementError):
        await session.flush()


@pytest.mark.asyncio
async def test_a_class_cannot_exist_without_an_owner(session) -> None:
    """A class with no teacher is refused by the schema.

    ADR-22 calls the column not-nullable; this is the test that makes the
    claim checkable rather than a sentence in a document.
    """
    session.add(SchoolClass(name="Lớp không chủ"))

    with pytest.raises(IntegrityError):
        await session.flush()


def test_skipping_a_state_is_refused() -> None:
    """An empty assessment cannot be approved.

    ADR-01 gives the empty state its own rule: it blocks publishing. Approving
    an assessment with no questions would let a teacher accept responsibility
    for content that does not exist.
    """
    assessment = _draft()

    with pytest.raises(HTTPException) as refused:
        advance(assessment, AssessmentState.APPROVED)

    assert refused.value.status_code == 409


@pytest.mark.asyncio
async def test_every_class_and_assessment_has_an_owner(session) -> None:
    """Seeded rows name the teacher they belong to.

    ADR-13 says a class belongs to a teacher. The rule had no column to live
    in, so nothing could enforce it and nothing could even be asked about it.
    """
    teacher = await session.scalar(select(Teacher))
    assert teacher is not None

    classes = (await session.scalars(select(SchoolClass))).all()
    assessments = (await session.scalars(select(Assessment))).all()
    assert classes and assessments

    assert all(row.teacher_id == teacher.id for row in classes)
    assert all(row.teacher_id == teacher.id for row in assessments)


@pytest.mark.asyncio
async def test_owner_partitions_the_data_both_ways(session) -> None:
    """Each teacher's query returns all of theirs and none of anyone else's.

    Both directions matter. A test that only checks the stranger sees nothing
    passes when `teacher_id` is filled in wrongly, when the filter reads the
    wrong column, and when the column partitions nothing at all -- it proves
    only that a query for an empty set comes back empty. So the stranger here
    owns rows of their own, and the assertion is that the two sets are
    disjoint and complete.
    """
    mine = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
    assert mine is not None

    stranger = Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002")
    session.add(stranger)
    await session.flush()

    their_class = SchoolClass(teacher_id=stranger.id, name="11B")
    their_assessment = Assessment(
        teacher_id=stranger.id,
        title="Đề của người khác",
        subject="Toán",
        grade="11",
        state=AssessmentState.EMPTY,
        created_at=datetime.now(UTC),
    )
    session.add_all([their_class, their_assessment])
    await session.flush()

    async def classes_of(teacher: Teacher) -> set[str]:
        query = select(SchoolClass).where(SchoolClass.teacher_id == teacher.id)
        return {row.id for row in await session.scalars(query)}

    async def assessments_of(teacher: Teacher) -> set[str]:
        rows = await session.scalars(select(Assessment).where(Assessment.teacher_id == teacher.id))
        return {row.id for row in rows}

    assert their_class.id in await classes_of(stranger)
    assert their_class.id not in await classes_of(mine)
    assert await classes_of(mine)  # the seeded class is still theirs to see

    assert their_assessment.id in await assessments_of(stranger)
    assert their_assessment.id not in await assessments_of(mine)
    assert await assessments_of(mine)
