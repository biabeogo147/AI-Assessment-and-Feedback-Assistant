"""One assessment, several classes, several clocks.

Publishing used to be one row per assessment, and the model said so on
purpose: two live sets of deadlines for one assessment was called a state
nobody could explain to a student. That reasoning was wrong in a specific
way -- it conflated *one assessment* with *one class*. Two sets of deadlines
for two different classes explain themselves perfectly, because a student only
ever sees their own: 12A has the lesson in the morning and opens in the
morning, 12B has it after lunch and opens after lunch.

So a publication is now one row per (assessment, class), and the tests here
pin the two things that follow. Each class reads its own terms. And an attempt
records the class it was started in, because otherwise a student who changes
class would have the deadlines of work they already did silently replaced by
another class's.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import agent_gateway
from be import db as db_module
from be.db import bind_sessions, prepare_schema
from be.models import Assessment, Attempt, Publication, SchoolClass, Student
from be.seed import seed_if_empty
from be.student_routes import router as student_router

MORNING = {"X-Actor": "student:HS2026-1204"}
AFTERNOON = {"X-Actor": "student:HS2026-9101"}


async def _fake_run_task(pool, settings, task_name, payload) -> dict:
    return {"schema_version": 1, "request_id": payload["request_id"], "text": "Trả lời mẫu."}


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """A seeded database, plus a second class holding the same assessment later."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)

        assessment = await session.scalar(select(Assessment))
        first = await session.scalar(select(Publication))
        assert assessment is not None and first is not None

        # The afternoon class: same paper, same teacher, a clock of its own.
        afternoon = SchoolClass(teacher_id=assessment.teacher_id, name="12B")
        session.add(afternoon)
        await session.flush()
        session.add(
            Student(class_id=afternoon.id, full_name="Bùi Thị Chiều", student_code="HS2026-9101")
        )
        now = datetime.now(UTC)
        session.add(
            Publication(
                assessment_id=assessment.id,
                class_id=afternoon.id,
                opens_at=now + timedelta(hours=4),
                closes_at=now + timedelta(hours=9),
                phase1_minutes=15,
                phase2_minutes_per_question=5,
                remediation_deadline=now + timedelta(hours=20),
                published_at=now,
            )
        )
        await session.commit()

    monkeypatch.setattr(agent_gateway, "run_task", _fake_run_task)

    app = FastAPI()
    app.include_router(student_router)
    app.state.queue_pool = object()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker

    await engine.dispose()
    db_module._SESSION_MAKER = None


@pytest.mark.asyncio
async def test_one_assessment_can_hold_two_sets_of_terms(stack) -> None:
    """Two rows, one paper. The old primary key made this impossible."""
    _, maker = stack

    async with maker() as session:
        published = (await session.scalars(select(Publication))).all()

    assert len(published) == 2
    assert len({row.assessment_id for row in published}) == 1
    assert len({row.class_id for row in published}) == 2
    # Different clocks is the whole point; identical ones would prove nothing.
    assert len({row.opens_at for row in published}) == 2


@pytest.mark.asyncio
async def test_each_class_reads_its_own_clock(stack) -> None:
    """The morning class may start; the afternoon class may not yet.

    Same assessment, same moment, two answers -- which is exactly what a
    single row per assessment could not express.
    """
    client, _ = stack

    morning = (await client.get("/api/me/assignments", headers=MORNING)).json()
    afternoon = (await client.get("/api/me/assignments", headers=AFTERNOON)).json()

    assert len(morning) == 1
    assert len(afternoon) == 1
    assert morning[0]["assignment_id"] == afternoon[0]["assignment_id"]
    assert morning[0]["opens_at"] != afternoon[0]["opens_at"]
    assert morning[0]["status"] != afternoon[0]["status"]


@pytest.mark.asyncio
async def test_an_attempt_remembers_the_class_it_started_in(stack) -> None:
    """The row records which set of terms governs it."""
    client, maker = stack

    assignments = (await client.get("/api/me/assignments", headers=MORNING)).json()
    started = await client.post(
        f"/api/assignments/{assignments[0]['assignment_id']}/attempts", headers=MORNING
    )
    assert started.status_code == 201

    async with maker() as session:
        attempt = await session.scalar(select(Attempt))
        student = await session.scalar(select(Student).where(Student.student_code == "HS2026-1204"))

    assert attempt is not None and student is not None
    assert attempt.class_id == student.class_id


@pytest.mark.asyncio
async def test_changing_class_does_not_lock_a_student_out_of_work_in_progress(stack) -> None:
    """Resuming reads the attempt's class, not the student's class today.

    `start_attempt` looked the publication up before it looked the attempt up,
    so the entry gate was applied with today's class every time. A student who
    moved from the morning class to the afternoon one was then told "chưa tới
    giờ mở" about a paper they were halfway through -- and if the new class had
    no publication at all, "bài này chưa được phát hành".

    ADR-03 already forbids this from the other direction: *"Học sinh đã vào
    rồi thì không bị dừng giữa chừng."* The entry gate guards entering, not
    continuing.
    """
    client, maker = stack

    assignments = (await client.get("/api/me/assignments", headers=MORNING)).json()
    assessment_id = assignments[0]["assignment_id"]
    started = await client.post(f"/api/assignments/{assessment_id}/attempts", headers=MORNING)
    assert started.status_code == 201

    async with maker() as session:
        student = await session.scalar(select(Student).where(Student.student_code == "HS2026-1204"))
        afternoon = await session.scalar(select(SchoolClass).where(SchoolClass.name == "12B"))
        assert student is not None and afternoon is not None
        student.class_id = afternoon.id
        await session.commit()

    again = await client.post(f"/api/assignments/{assessment_id}/attempts", headers=MORNING)

    # 201 for a request that created nothing is a small untruth this route
    # told before this change and still tells: the status code is fixed on the
    # decorator while the handler has two outcomes. Asserted as it is rather
    # than as it should be, so this test stays about the class change.
    assert again.status_code == 201
    assert again.json()["attempt_id"] == started.json()["attempt_id"]


@pytest.mark.asyncio
async def test_the_phase_two_deadline_follows_the_attempt_not_the_student(stack) -> None:
    """The deadline is re-read on every request, so this one can actually fail.

    The first version of this test compared `ends_at` across a class change --
    but `ends_at` is a column written once at start, and the route that serves
    it never loads a publication at all. It would have stayed green with every
    call site reverted to the student's current class.

    `remediation_deadline` is different: `/result` reads it from the
    publication each time. The morning class has it at +8h and the afternoon
    class at +20h, so reading the wrong class's terms moves it by twelve
    hours.
    """
    client, maker = stack

    assignments = (await client.get("/api/me/assignments", headers=MORNING)).json()
    assessment_id = assignments[0]["assignment_id"]
    started = await client.post(f"/api/assignments/{assessment_id}/attempts", headers=MORNING)
    attempt_id = started.json()["attempt_id"]
    await client.post(f"/api/attempts/{attempt_id}/submit", headers=MORNING)

    before = (await client.get(f"/api/attempts/{attempt_id}/result", headers=MORNING)).json()

    async with maker() as session:
        student = await session.scalar(select(Student).where(Student.student_code == "HS2026-1204"))
        afternoon = await session.scalar(select(SchoolClass).where(SchoolClass.name == "12B"))
        assert student is not None and afternoon is not None
        student.class_id = afternoon.id
        await session.commit()

    after = (await client.get(f"/api/attempts/{attempt_id}/result", headers=MORNING)).json()

    assert after["remediation_deadline"] == before["remediation_deadline"]
