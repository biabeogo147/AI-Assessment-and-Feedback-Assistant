"""Ô câu soạn hỏng: panel thấy nó đúng vị trí, giáo viên bấm *Thử lại*, duyệt thì nó biến mất.

Việc 12 của plan `wave-3-draft-panel`. Trước đây một ô `failed` không có đường nào hồi lại -- `fire`
để yên nó -- và panel không vẽ nó, nên đề hiện *Câu 1, 2, 3, 5* mà không nói câu 4 đi đâu. Ba luật
được canh ở đây:

- **Ô hỏng đọc ra đúng vị trí** (`AssessmentDetail.failed_slots`), cùng dãy số với các câu.
- **Thử lại trả ô đủ ba lượt**, chỉ cho ô thật sự hỏng, chỉ cho tác giả của một đề còn mở.
- **Duyệt bỏ ô hỏng và dồn số**: đề đã khoá không mang lỗ số.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import drafting
from be.db import bind_sessions
from be.seed import seed_if_empty
from be.teacher_routes import router as assessment_router
from schema.ddl import prepare_schema
from schema.models import (
    AnswerOption,
    Assessment,
    AssessmentState,
    DraftBrief,
    DraftItem,
    Method,
    Question,
    Teacher,
)

TEACHER = {"X-Actor": "teacher:GV-001"}
STRANGER = {"X-Actor": "teacher:GV-002"}


class FakeQueue:
    """Ghi lại job được đẩy vào queue; `dead` thì từ chối mọi job, như Redis đang tắt."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, dict]] = []
        self.dead = False

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str):
        if self.dead:
            raise ConnectionError("redis is down")
        job_id = f"job-{len(self.jobs)}"
        self.jobs.append((name, payload))
        return type("Queued", (), {"job_id": job_id})()


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """Một app có hai giáo viên, SQLite **bật khoá ngoại**, mọi job đang chạy dở."""
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    await prepare_schema(engine)
    bind_sessions(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        session.add(Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002"))
        await session.commit()

    queue = FakeQueue()

    async def collect(_pool, _settings, _job_id):
        return ("pending", None)

    monkeypatch.setattr(drafting, "collect_result", collect)

    app = FastAPI()
    app.include_router(assessment_router)
    app.state.queue_pool = queue

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker, queue

    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _draft(maker, positions: int, hole: int | tuple[int, ...]) -> str:
    """Một đề nháp `positions` ô; mọi ô có câu, trừ các ô `hole` đã hỏng hết ba lượt.

    Mỗi ô trỏ một mục dàn ý riêng (`outline_item = vị trí - 1`), để *Thử lại* có mục mà soạn theo.
    """
    holes = hole if isinstance(hole, tuple) else (hole,)
    async with maker() as session:
        owner = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        draft = Assessment(
            teacher_id=owner.id,
            title="Đề nháp hàm số",
            subject="Toán",
            grade="12",
            state=AssessmentState.HAS_QUESTIONS,
            created_at=datetime.now(UTC),
        )
        session.add(draft)
        await session.flush()
        session.add(
            DraftBrief(
                assessment_id=draft.id,
                topic_scope="hàm số",
                question_count=positions,
                version=1,
                outline=[
                    {"knowledge": f"kiến thức {n}", "approach": f"cách {n}", "questions": 1}
                    for n in range(1, positions + 1)
                ],
                created_at=datetime.now(UTC),
            )
        )
        for index in range(1, positions + 1):
            failed = index in holes
            session.add(
                DraftItem(
                    assessment_id=draft.id,
                    ordinal=index,
                    job_id=f"seeded-{index}",
                    status="failed" if failed else "ready",
                    brief_version=1,
                    attempts=3 if failed else 1,
                    last_fault="model không soạn được câu này" if failed else "",
                    outline_item=index - 1,
                    created_at=datetime.now(UTC),
                )
            )
            if failed:
                continue
            question = Question(
                assessment_id=draft.id,
                order_index=index,
                stem=f"Câu số {index}?",
                learning_objective="hàm số",
            )
            session.add(question)
            await session.flush()
            session.add(
                AnswerOption(question_id=question.id, label="A", text="đúng", is_correct=True)
            )
            session.add(Method(question_id=question.id, order_index=1, title="Cách 1", body="."))
        await session.commit()
        return draft.id


async def _slot(maker, draft: str, order: int) -> DraftItem:
    async with maker() as session:
        found = await session.scalar(
            select(DraftItem).where(DraftItem.assessment_id == draft, DraftItem.ordinal == order)
        )
        assert found is not None
        return found


# ------------------------------------------------------------------ đọc


@pytest.mark.asyncio
async def test_a_failed_slot_reads_out_at_its_own_position(stack) -> None:
    """Panel nhận ô hỏng ở vị trí 3 giữa câu 1, 2, 4, 5 -- không phải ở cuối, không biến mất."""
    http, maker, _queue = stack
    draft = await _draft(maker, positions=5, hole=3)

    body = (await http.get(f"/api/teacher/assessments/{draft}", headers=TEACHER)).json()

    assert [one["order"] for one in body["questions"]] == [1, 2, 4, 5]
    assert body["failed_slots"] == [{"order": 3, "redrafting": False}]


@pytest.mark.asyncio
async def test_a_slot_that_failed_once_but_now_holds_a_question_is_not_listed(stack) -> None:
    """Ô `ready` mang lỗi của một lượt trước (thử lại rồi đạt) có câu ở vị trí của nó: không vẽ."""
    http, maker, _queue = stack
    draft = await _draft(maker, positions=3, hole=())
    async with maker() as session:
        row = await session.scalar(
            select(DraftItem).where(DraftItem.assessment_id == draft, DraftItem.ordinal == 2)
        )
        row.last_fault = "đề trùng một câu đã có"
        await session.commit()

    body = (await http.get(f"/api/teacher/assessments/{draft}", headers=TEACHER)).json()

    assert body["failed_slots"] == []


@pytest.mark.asyncio
async def test_a_retry_slot_the_queue_dropped_reads_as_failed_and_can_be_tried_again(
    stack,
) -> None:
    """Ô `retry` không job (queue chết lúc bắn lại) không vẽ *đang soạn lại* mãi (review pha 1)."""
    http, maker, queue = stack
    draft = await _draft(maker, positions=3, hole=2)
    async with maker() as session:
        row = await session.scalar(
            select(DraftItem).where(DraftItem.assessment_id == draft, DraftItem.ordinal == 2)
        )
        row.status = "retry"
        await session.commit()

    before = (await http.get(f"/api/teacher/assessments/{draft}", headers=TEACHER)).json()
    tried = await http.post(f"/api/teacher/assessments/{draft}/slots/2/redraft", headers=TEACHER)

    assert before["failed_slots"] == [{"order": 2, "redrafting": False}]
    assert tried.status_code == 202
    assert len(queue.jobs) == 1


@pytest.mark.asyncio
async def test_a_slot_drafting_for_the_first_time_is_not_a_failed_slot(stack) -> None:
    """Ô đang soạn lần đầu không hỏng lần nào: panel không vẽ nó, như trước việc 12."""
    http, maker, _queue = stack
    draft = await _draft(maker, positions=3, hole=())
    async with maker() as session:
        session.add(
            DraftItem(
                assessment_id=draft,
                ordinal=4,
                job_id="fresh",
                status="pending",
                brief_version=1,
                attempts=1,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

    body = (await http.get(f"/api/teacher/assessments/{draft}", headers=TEACHER)).json()

    assert body["failed_slots"] == []


# ------------------------------------------------------------------ thử lại


@pytest.mark.asyncio
async def test_trying_again_sends_one_job_and_gives_the_slot_three_more_tries(stack) -> None:
    """Một cú *Thử lại* là đúng một job, theo mục dàn ý của ô, và ô có lại đủ ba lượt."""
    http, maker, queue = stack
    draft = await _draft(maker, positions=4, hole=2)

    tried = await http.post(f"/api/teacher/assessments/{draft}/slots/2/redraft", headers=TEACHER)

    assert tried.status_code == 202
    assert len(queue.jobs) == 1
    assert queue.jobs[0][1]["ordinal"] == 2
    # Đúng mục dàn ý của ô, không phải một câu soạn theo `topic_scope`.
    assert queue.jobs[0][1]["item_knowledge"] == "kiến thức 2"
    slot = await _slot(maker, draft, 2)
    assert (slot.status, slot.attempts) == ("pending", 1)
    body = (await http.get(f"/api/teacher/assessments/{draft}", headers=TEACHER)).json()
    assert body["failed_slots"] == [{"order": 2, "redrafting": True}]


@pytest.mark.asyncio
async def test_only_a_failed_slot_can_be_tried_again(stack) -> None:
    """Vị trí đã có câu, hay chưa từng có ô, thì không có gì để thử lại."""
    http, maker, queue = stack
    draft = await _draft(maker, positions=3, hole=2)

    on_a_question = await http.post(
        f"/api/teacher/assessments/{draft}/slots/1/redraft", headers=TEACHER
    )
    past_the_end = await http.post(
        f"/api/teacher/assessments/{draft}/slots/9/redraft", headers=TEACHER
    )

    assert on_a_question.status_code == 409
    assert past_the_end.status_code == 409
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_trying_again_is_the_authors_and_only_while_the_draft_is_open(stack) -> None:
    """Người khác thấy 404 (ADR-22); đề đã duyệt thì nội dung đã khoá (ADR-01)."""
    http, maker, queue = stack
    draft = await _draft(maker, positions=3, hole=2)

    stranger = await http.post(
        f"/api/teacher/assessments/{draft}/slots/2/redraft", headers=STRANGER
    )
    async with maker() as session:
        row = await session.get(Assessment, draft)
        row.state = AssessmentState.APPROVED
        await session.commit()
    locked = await http.post(f"/api/teacher/assessments/{draft}/slots/2/redraft", headers=TEACHER)

    assert stranger.status_code == 404
    assert locked.status_code == 409
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_a_queue_that_takes_nothing_leaves_the_slot_failed(stack) -> None:
    """Queue chết thì ô về `failed`: để nó `retry` là vẽ *đang soạn lại* cho một ô không ai soạn."""
    http, maker, queue = stack
    draft = await _draft(maker, positions=3, hole=2)
    queue.dead = True

    tried = await http.post(f"/api/teacher/assessments/{draft}/slots/2/redraft", headers=TEACHER)

    assert tried.status_code == 503
    slot = await _slot(maker, draft, 2)
    assert (slot.status, slot.attempts) == ("failed", 3)
    body = (await http.get(f"/api/teacher/assessments/{draft}", headers=TEACHER)).json()
    assert body["failed_slots"] == [{"order": 2, "redrafting": False}]


# ------------------------------------------------------------------ duyệt


@pytest.mark.asyncio
async def test_approving_drops_the_failed_slot_and_closes_the_gap(stack) -> None:
    """Duyệt đề có ô hỏng ở vị trí 2: đề đã khoá mang câu 1, 2, 3 liền nhau, không còn ô nào."""
    http, maker, _queue = stack
    draft = await _draft(maker, positions=4, hole=2)

    approved = await http.post(f"/api/teacher/assessments/{draft}/approve", headers=TEACHER)

    assert approved.status_code == 200
    async with maker() as session:
        rows = await session.execute(
            select(Question.order_index, Question.stem)
            .where(Question.assessment_id == draft)
            .order_by(Question.order_index)
        )
        stems = [(order, stem) for order, stem in rows]
        slots = sorted(
            await session.scalars(select(DraftItem.ordinal).where(DraftItem.assessment_id == draft))
        )
        brief = await session.get(DraftBrief, draft)
    assert stems == [(1, "Câu số 1?"), (2, "Câu số 3?"), (3, "Câu số 4?")]
    assert slots == [1, 2, 3]
    assert brief.question_count == 3


@pytest.mark.asyncio
async def test_approving_with_two_failed_slots_closes_both_gaps(stack) -> None:
    """Hai lỗ ở vị trí 2 và 4: dồn từ lỗ cao xuống, nên câu 3 và câu 5 đều về đúng chỗ."""
    http, maker, _queue = stack
    draft = await _draft(maker, positions=5, hole=(2, 4))

    approved = await http.post(f"/api/teacher/assessments/{draft}/approve", headers=TEACHER)

    assert approved.status_code == 200
    async with maker() as session:
        rows = await session.execute(
            select(Question.order_index, Question.stem)
            .where(Question.assessment_id == draft)
            .order_by(Question.order_index)
        )
        stems = [(order, stem) for order, stem in rows]
    assert stems == [(1, "Câu số 1?"), (2, "Câu số 3?"), (3, "Câu số 5?")]
