"""Seed lab (plan `lab-deploy-aws`): đủ người, đủ chặng, và không dựng một trạng thái mà đường thật
không bao giờ để lại.

Một database seed một lần cho cả file (`scope="module"`): seed một nghìn học sinh tốn vài giây, và
mọi test ở đây chỉ đọc.
"""

import time
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.account_routes import router as account_router
from be.accounts import check_password, hash_password
from be.agent_gateway import validate_question, validate_retry
from be.db import bind_sessions
from be.lab_seed import seed_lab
from be.lab_seed.__main__ import main as lab_seed_main
from be.lab_seed.papers import TOPICS
from be.lab_seed.retries import twins
from be.scoring import MarkReason
from be.student_routes import router as student_router
from be.teacher_board import router as board_router
from be.teacher_reads import router as reads_router
from be.teacher_routes import router as teacher_router
from contracts import GeneratedOption, GeneratedQuestion, SolutionMethod
from schema.ddl import prepare_schema
from schema.models import (
    AnswerOption,
    Assessment,
    AssessmentState,
    Attempt,
    BankQuestion,
    Publication,
    Question,
    QuestionOutcome,
    RemediationRound,
    Report,
    RoundItem,
    SchoolClass,
    Student,
    Teacher,
)

PASSWORD = "lab-chung-2026"


class _Queue:
    """Queue nhận job mà không chạy; trang HS có thể đẩy job viết trước câu vòng chữa."""

    def __init__(self) -> None:
        self.jobs: list[str] = []

    async def enqueue_job(self, name: str, *_args, **_kwargs):
        self.jobs.append(name)
        return SimpleNamespace(job_id=f"job-{len(self.jobs)}")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def lab():
    engine = create_async_engine("sqlite+aiosqlite://")
    # Khoá ngoại bật như Postgres: SQLite mặc định bỏ qua chúng, và seed từng insert `answers`
    # trước `attempts` mà ở đây vẫn xanh.
    event.listen(engine.sync_engine, "connect", _foreign_keys_on)
    await prepare_schema(engine)
    bind_sessions(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    began = time.monotonic()
    async with maker() as session:
        summary = await seed_lab(session, hash_password(PASSWORD), datetime.now(UTC))
    took = time.monotonic() - began
    app = FastAPI()
    for router in (account_router, student_router, teacher_router, reads_router, board_router):
        app.include_router(router)
    # Màn chi tiết đề gom câu đang soạn qua queue; đề seed không có câu nào đang chờ.
    app.state.queue_pool = _Queue()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker, summary, took
    await engine.dispose()
    db_module._SESSION_MAKER = None


def _foreign_keys_on(connection, _record) -> None:
    connection.execute("PRAGMA foreign_keys=ON")


async def _count(maker, model, *where) -> int:
    async with maker() as session:
        return await session.scalar(select(func.count()).select_from(model).where(*where))


@pytest.mark.asyncio(loop_scope="module")
async def test_people_add_up(lab):
    _, maker, summary, took = lab
    assert await _count(maker, Teacher) == 5
    assert await _count(maker, SchoolClass) == 30
    assert await _count(maker, Student) == 1000
    assert (summary.classes, summary.students) == (30, 1000)
    async with maker() as session:
        sizes = Counter(await session.scalars(select(Student.class_id)))
        assert set(sizes.values()) <= {33, 34}
        usernames = list(await session.scalars(select(Student.username)))
        assert len(set(usernames)) == 1000 and None not in usernames
    assert took < 60


@pytest.mark.asyncio(loop_scope="module")
async def test_every_stage_is_there(lab):
    _, maker, summary, _ = lab
    assert summary.papers == Counter(
        {
            "nháp": 5,
            "đang soạn": 5,
            "đã duyệt": 5,
            "sắp mở": 5,
            "thu hồi một lớp": 5,
            "đang làm": 5,
            "đang chữa": 5,
            "đã xong": 10,
        }
    )
    async with maker() as session:
        states = Counter(await session.scalars(select(Assessment.state)))
    assert states == {
        AssessmentState.EMPTY: 5,
        AssessmentState.HAS_QUESTIONS: 5,
        AssessmentState.APPROVED: 5,
        AssessmentState.PUBLISHED: 30,
    }
    assert await _count(maker, Publication, Publication.recalled_at.is_not(None)) == 5
    # Mọi đề đã duyệt có bản trong ngân hàng (ADR-28): 35 đề, sáu câu mỗi đề.
    assert await _count(maker, BankQuestion) == 35 * 6


@pytest.mark.asyncio(loop_scope="module")
async def test_marks_are_what_scoring_would_give(lab):
    _, maker, _, _ = lab
    async with maker() as session:
        outcomes = list(await session.scalars(select(QuestionOutcome)))
    assert outcomes
    allowed = {
        MarkReason.CORRECT_FIRST_TRY.value: {(1.0, True)},
        MarkReason.REMEDIATED.value: {(0.5, True)},
        MarkReason.NOT_YET_REMEDIATED.value: {(0.0, False)},
        MarkReason.ROUNDS_EXHAUSTED.value: {(0.0, True)},
    }
    for outcome in outcomes:
        assert (outcome.mark, outcome.closed) in allowed[outcome.reason]
        assert 0 <= outcome.rounds_used <= 3
        if outcome.reason == MarkReason.CORRECT_FIRST_TRY.value:
            assert outcome.rounds_used == 0
        if outcome.reason == MarkReason.ROUNDS_EXHAUSTED.value:
            assert outcome.rounds_used == 3
    reasons = Counter(outcome.reason for outcome in outcomes)
    assert all(reasons[reason] for reason in allowed)


@pytest.mark.asyncio(loop_scope="module")
async def test_rounds_keep_the_database_rules(lab):
    _, maker, _, _ = lab
    now = datetime.now(UTC)
    async with maker() as session:
        rounds = list(await session.scalars(select(RemediationRound)))
        attempts = {a.id: a for a in await session.scalars(select(Attempt))}
    open_per_attempt = Counter(r.attempt_id for r in rounds if r.submitted_at is None)
    assert open_per_attempt and max(open_per_attempt.values()) == 1
    for rnd in rounds:
        submitted = attempts[rnd.attempt_id].submitted_at
        assert submitted is not None
        assert _aware(rnd.started_at) > _aware(submitted)
        assert _aware(rnd.started_at) < _aware(rnd.ends_at)
        if rnd.submitted_at is not None:
            assert _aware(rnd.submitted_at) <= now
    # Pha 1 đang làm dở: còn giờ, chưa nộp.
    running = [a for a in attempts.values() if a.submitted_at is None]
    assert running and all(_aware(a.ends_at) > now for a in running)
    assert await _count(maker, Report) > 0


@pytest.mark.asyncio(loop_scope="module")
async def test_main_screens_read_the_seed(lab):
    http, maker, _, _ = lab
    async with maker() as session:
        teacher = await session.scalar(select(Teacher).order_by(Teacher.teacher_code))
        finished = await session.scalar(
            select(Publication)
            .join(Assessment, Assessment.id == Publication.assessment_id)
            .where(
                Assessment.teacher_id == teacher.id, Publication.remediation_deadline < func.now()
            )
        )
        student = await session.scalar(select(Student).where(Student.class_id == finished.class_id))
    actor = {"X-Actor": f"teacher:{teacher.teacher_code}"}
    for path in (
        "/api/teacher/board",
        "/api/teacher/assessments",
        "/api/teacher/classes",
        f"/api/teacher/classes/{finished.class_id}",
        f"/api/teacher/classes/{finished.class_id}/assessments/{finished.assessment_id}/results",
        f"/api/teacher/classes/{finished.class_id}/assessments/{finished.assessment_id}/results.xlsx",
        f"/api/teacher/assessments/{finished.assessment_id}",
    ):
        assert (await http.get(path, headers=actor)).status_code == 200, path
    board = (await http.get("/api/teacher/board", headers=actor)).json()
    assert {row["kind"] for row in board["queue"]} == {"reports", "wrong_rate"}
    assert board["classes"]

    signed = await http.post(
        "/api/sign-in", json={"username": student.username, "password": PASSWORD}
    )
    assert signed.status_code == 204
    assignments = (await http.get("/api/me/assignments")).json()
    assert assignments
    for assignment in assignments:
        if assignment["attempt_id"]:
            path = f"/api/attempts/{assignment['attempt_id']}/result"
            assert (await http.get(path)).status_code in (200, 409), path


@pytest.mark.asyncio(loop_scope="module")
async def test_one_password_opens_every_account(lab):
    _, maker, _, _ = lab
    async with maker() as session:
        hashes = set(await session.scalars(select(Teacher.password_hash)))
        hashes |= set(await session.scalars(select(Student.password_hash)))
    assert len(hashes) == 1
    assert check_password(PASSWORD, hashes.pop())


def _aware(moment: datetime) -> datetime:
    """SQLite trả giờ không kèm múi; seed chỉ ghi UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


# --- dòng lệnh ------------------------------------------------------------------------------------


class _Stdin:
    def __init__(self, text: str):
        self._text = text

    def isatty(self) -> bool:
        return False

    def readline(self) -> str:
        return self._text


@pytest.fixture
def cli(monkeypatch, tmp_path):
    """`main` của `python -m be.lab_seed` trên một SQLite tệp, bucket giả."""
    import be.lab_seed.__main__ as main_module

    url = f"sqlite+aiosqlite:///{tmp_path / 'lab.db'}"
    cleared = []

    class _Store:
        async def ensure_ready(self):
            pass

        async def clear(self):
            cleared.append(True)

    monkeypatch.setattr(main_module, "create_store", lambda settings: _Store())
    monkeypatch.setattr(main_module, "create_engine", lambda settings: create_async_engine(url))
    # Trả lại session maker của fixture `lab` (cả module dùng chung): `main` đã bind cái của nó.
    bound = db_module._SESSION_MAKER
    yield main_module, cleared
    db_module._SESSION_MAKER = bound


@pytest.mark.asyncio
async def test_cli_refuses_short_password(cli, monkeypatch, capsys):
    main_module, _ = cli
    monkeypatch.setattr("sys.stdin", _Stdin("ngan\n"))
    assert await lab_seed_main([]) == 2
    assert "ít nhất 8" in capsys.readouterr().err


@pytest.mark.asyncio
async def test_cli_refuses_a_used_database_without_reset(cli, monkeypatch, capsys):
    main_module, cleared = cli
    monkeypatch.setattr("sys.stdin", _Stdin(PASSWORD + "\n"))
    assert await lab_seed_main(["--reset"]) == 0
    out = capsys.readouterr().out
    assert "1000 học sinh" in out and PASSWORD not in out
    assert cleared == [True]
    monkeypatch.setattr("sys.stdin", _Stdin(PASSWORD + "\n"))
    assert await lab_seed_main([]) == 1
    assert "--reset" in capsys.readouterr().err
    assert cleared == [True]


# --- câu hỏi viết tay qua đúng lưới của đường thật -----------------------------------------------


def _generated(stem, objective, options, methods) -> GeneratedQuestion:
    return GeneratedQuestion(
        stem=stem,
        learning_objective=objective,
        options=tuple(
            GeneratedOption(label=label, text=text, is_correct=correct, error_label=error)
            for label, text, correct, error in options
        ),
        methods=tuple(SolutionMethod(title=title, body=body) for title, body in methods),
    )


@pytest.mark.parametrize(
    "item", [item for pair in TOPICS.values() for t in pair for item in t.items]
)
def test_every_question_and_retry_passes_the_real_checks(item):
    """Mỗi câu và ba đề vòng chữa của nó qua `validate_question`; vòng k không lặp câu gốc hay
    một vòng trước (`validate_retry`, ADR-17) -- đúng lưới AGENT phải qua ở đường thật."""
    validate_question(_generated(item.stem, item.objective, item.options, item.methods))
    spent: list[str] = []
    for twin in twins(item):
        retry = _generated(twin.stem, item.objective, twin.options, twin.methods or item.methods)
        validate_question(retry)
        validate_retry(retry, item.stem, spent)
        spent.append(twin.stem)


@pytest.mark.asyncio(loop_scope="module")
async def test_seeded_rounds_never_repeat_a_stem(lab):
    _, maker, _, _ = lab
    async with maker() as session:
        rows = (
            await session.execute(
                select(RemediationRound.attempt_id, RoundItem.origin_question_id, RoundItem.stem)
                .join(RoundItem, RoundItem.round_id == RemediationRound.id)
                .order_by(RemediationRound.attempt_id, RemediationRound.index)
            )
        ).all()
        stems = dict((await session.execute(select(Question.id, Question.stem))).all())
    seen: dict[tuple[str, str], list[str]] = {}
    for attempt_id, question_id, stem in rows:
        spent = seen.setdefault((attempt_id, question_id), [])
        assert stem != stems[question_id] and stem not in spent
        spent.append(stem)
    assert max(len(spent) for spent in seen.values()) == 3


@pytest.mark.asyncio(loop_scope="module")
async def test_remediation_and_review_screens_read_the_seed(lab):
    """Màn chữa bài, vòng đang làm dở, chat của học sinh, và ba màn soi của bảng theo dõi.

    Màn pha 1 và màn một vòng **đã nộp** trả 409 ở đường thật, nên không có ở đây."""
    http, maker, _, _ = lab
    async with maker() as session:
        rnd = await session.scalar(
            select(RemediationRound).where(RemediationRound.submitted_at.is_(None))
        )
        attempt = await session.get(Attempt, rnd.attempt_id)
        student = await session.get(Student, attempt.student_id)
        paper = await session.get(Assessment, attempt.assessment_id)
        teacher = await session.get(Teacher, paper.teacher_id)
        report = await session.scalar(
            select(Report)
            .join(Attempt, Attempt.id == Report.attempt_id)
            .join(Assessment, Assessment.id == Attempt.assessment_id)
            .where(Assessment.teacher_id == teacher.id)
        )
        reported = await session.get(Attempt, report.attempt_id)
        question = await session.scalar(
            select(Question).where(Question.assessment_id == attempt.assessment_id)
        )
    signed = await http.post(
        "/api/sign-in", json={"username": student.username, "password": PASSWORD}
    )
    assert signed.status_code == 204
    for path in (
        f"/api/attempts/{attempt.id}/result",
        f"/api/attempts/{attempt.id}/remediation",
        f"/api/attempts/{attempt.id}/chat",
        f"/api/rounds/{rnd.id}",
    ):
        assert (await http.get(path)).status_code == 200, path
    actor = {"X-Actor": f"teacher:{teacher.teacher_code}"}
    for path in (
        f"/api/teacher/board/reports/{reported.assessment_id}",
        f"/api/teacher/board/questions/{question.id}",
        f"/api/teacher/board/chat/{report.id}",
    ):
        assert (await http.get(path, headers=actor)).status_code == 200, path


@pytest.mark.asyncio(loop_scope="module")
async def test_answers_are_not_always_a_and_nothing_happens_at_night(lab):
    """Đáp án đúng rải đều A–D, ở câu gốc lẫn câu vòng chữa; báo cáo không gửi lúc nửa đêm."""
    _, maker, _, _ = lab
    async with maker() as session:
        first = Counter(
            await session.scalars(select(AnswerOption.label).where(AnswerOption.is_correct))
        )
        retry = Counter(
            next(o["label"] for o in options if o["is_correct"])
            for options in await session.scalars(select(RoundItem.options))
        )
        reports = list(await session.scalars(select(Report.created_at)))
    for counts in (first, retry):
        assert set(counts) == {"A", "B", "C", "D"}
        assert max(counts.values()) < 0.5 * sum(counts.values())
    vn = timezone(timedelta(hours=7))
    for created in reports:
        local = _aware(created).astimezone(vn)
        assert 6 * 60 + 30 <= local.hour * 60 + local.minute < 22 * 60 + 30
