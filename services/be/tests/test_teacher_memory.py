"""The conversation that survives the request, and what that buys.

Until this table existed the endpoint took one sentence and forgot it. The
obvious cost was a reload losing the turn. The real cost was larger: a teacher
answering the assistant's own clarifying question sent that answer with no
trace of what had been asked, so the input gate of ADR-05 existed without a
way to be answered.

So the tests here are not really about storage. They are about a conversation
being one thing across several requests, and about the row being complete
enough afterwards to answer "what did it actually do" -- which, with an agent
that picks its own steps, is not answerable from the words alone.
"""

import asyncio
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import teacher_chat
from be.db import bind_sessions, prepare_schema
from be.identity import Asking
from be.models import SchoolClass, Student, Teacher, TeacherConversation, TeacherTurn
from be.seed import seed_if_empty
from be.teacher_chat import router as teacher_router
from contracts import NextStepCompleted, TurnRecord

TEACHER = {"X-Actor": "teacher:GV-001"}


class ScriptedAgent:
    """Answer each step with a queued proposal, recording what it was asked.

    `takes` is how long each answer pretends to need. A fake that answers
    instantly makes `duration_ms` round to zero, which is indistinguishable
    from a duration nobody measured -- so a test about the measurement has to
    give it something to measure.
    """

    def __init__(self, *steps: NextStepCompleted, takes: float = 0.0) -> None:
        self.steps = list(steps)
        self.takes = takes
        self.asked: list[dict] = []

    async def __call__(self, pool, settings, task_name, payload) -> dict:
        self.asked.append(payload)
        if self.takes:
            await asyncio.sleep(self.takes)
        step = (
            self.steps.pop(0)
            if self.steps
            else NextStepCompleted(request_id=payload["request_id"], kind="say", text="xong")
        )
        return step.model_copy(update={"request_id": payload["request_id"]}).model_dump(mode="json")


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """An app on a seeded in-memory database, with a second class to be vague about."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        teacher = await session.scalar(select(SchoolClass))
        assert teacher is not None
        second = SchoolClass(teacher_id=teacher.teacher_id, name="12B")
        session.add(second)
        await session.flush()
        session.add(Student(class_id=second.id, full_name="Đỗ Văn Ba", student_code="HS2026-8001"))
        await session.commit()

    app = FastAPI()
    app.include_router(teacher_router)
    app.state.queue_pool = object()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker, monkeypatch

    await engine.dispose()
    db_module._SESSION_MAKER = None


@pytest.mark.asyncio
async def test_a_second_message_carries_the_first_one_with_it(stack) -> None:
    """The clarifying question becomes answerable.

    This is the whole point of the table. The assistant asks "which class?",
    the teacher answers "12A", and the model has to see its own question to
    make sense of that word. Before the conversation was stored, the second
    request arrived holding only "12A".
    """
    client, _, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="ask_clarify", text="Bạn muốn xem lớp nào?"),
        NextStepCompleted(request_id="x", kind="say", text="Lớp 12A nhé."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    await client.post("/api/teacher/chat/messages", json={"text": "xem điểm"}, headers=TEACHER)
    await client.post("/api/teacher/chat/messages", json={"text": "12A"}, headers=TEACHER)

    second = agent.asked[1]["history"]
    said = [turn["text"] for turn in second]
    assert "xem điểm" in said
    assert "Bạn muốn xem lớp nào?" in said
    assert "12A" in said


@pytest.mark.asyncio
async def test_the_conversation_reads_back_after_the_request_is_gone(stack) -> None:
    """A reload shows the same conversation, in the same order."""
    client, _, monkeypatch = stack
    monkeypatch.setattr(
        teacher_chat,
        "run_task",
        ScriptedAgent(NextStepCompleted(request_id="x", kind="say", text="Chào bạn.")),
    )

    await client.post("/api/teacher/chat/messages", json={"text": "chào"}, headers=TEACHER)

    read = await client.get("/api/teacher/chat", headers=TEACHER)

    assert read.status_code == 200
    turns = read.json()["turns"]
    assert [turn["kind"] for turn in turns] == ["teacher", "assistant"]
    assert turns[0]["text"] == "chào"
    assert turns[1]["text"] == "Chào bạn."


@pytest.mark.asyncio
async def test_a_tool_step_stores_what_it_ran_and_what_came_back(stack) -> None:
    """The trace is the transcript, so one SELECT answers "what did it do".

    Storing only the words would leave the middle of every turn invisible: a
    teacher reports "nó trả lời sai" and the tool call that produced the
    answer would be nowhere.
    """
    client, maker, monkeypatch = stack
    monkeypatch.setattr(
        teacher_chat,
        "run_task",
        ScriptedAgent(
            NextStepCompleted(
                request_id="x",
                kind="call_tool",
                tool_name="find_class",
                tool_args={"name": "12B"},
            ),
            NextStepCompleted(request_id="x", kind="say", text="Lớp 12B có 1 học sinh."),
        ),
    )

    await client.post("/api/teacher/chat/messages", json={"text": "lớp 12B"}, headers=TEACHER)

    async with maker() as session:
        stored = (await session.scalars(select(TeacherTurn).order_by(TeacherTurn.sequence))).all()

    assert [turn.kind for turn in stored] == ["teacher", "tool_call", "tool_result", "assistant"]

    ran = stored[1]
    assert ran.tool_name == "find_class"
    assert ran.tool_args == {"name": "12B"}

    came_back = stored[2]
    assert came_back.tool_result["found"] is True
    assert came_back.tool_result["name"] == "12B"
    # The subject of the step, which is what the interface draws and what a
    # later question links to -- not the sentence announcing it.
    assert came_back.entity_kind == "class"
    assert came_back.entity_id == came_back.tool_result["class_id"]


@pytest.mark.asyncio
async def test_what_a_call_cost_travels_from_agent_into_the_row(stack) -> None:
    """The token count AGENT reported is the one stored.

    The first version of this test asserted `model_tokens >= 0` on a fake that
    never set it -- a column defaulting to 0 compared against 0, which stayed
    green with the whole field deleted. It bought a feeling of safety and sold
    nothing back. This one names a number and follows it through AGENT, the
    contract, BE and the table.
    """
    client, maker, monkeypatch = stack
    monkeypatch.setattr(
        teacher_chat,
        "run_task",
        ScriptedAgent(
            NextStepCompleted(request_id="x", kind="say", text="rồi", model_tokens=1234),
            takes=0.05,
        ),
    )

    await client.post("/api/teacher/chat/messages", json={"text": "chào"}, headers=TEACHER)

    async with maker() as session:
        spoken = await session.scalar(select(TeacherTurn).where(TeacherTurn.kind == "assistant"))

    assert spoken is not None
    assert spoken.model_tokens == 1234
    # The fake took 50ms and the assertion allows 30, because `int()` on the
    # elapsed milliseconds truncates and a loaded machine rounds the sleep
    # down. The claim being made is "this was measured", not "this was exactly
    # 50" -- a flat zero is what a step recorded outside the timed region
    # would give. Asserting the sleep exactly is how this test failed once
    # before being loosened.
    assert spoken.duration_ms >= 30


@pytest.mark.asyncio
async def test_two_steps_cannot_claim_the_same_position(stack) -> None:
    """The uniqueness that stopped the student being greeted twice.

    Two requests can reach the same position holding the same count, because
    reading the count and inserting the row are two statements with a gap in
    between.
    """
    _, maker, _ = stack

    async with maker() as session:
        conversation = TeacherConversation(teacher_id="whoever", started_at=datetime.now(UTC))
        session.add(conversation)
        await session.flush()

        for _ in range(2):
            session.add(
                TeacherTurn(
                    conversation_id=conversation.id,
                    sequence=0,
                    kind="teacher",
                    text="cùng một chỗ",
                    created_at=datetime.now(UTC),
                )
            )

        with pytest.raises(IntegrityError):
            await session.flush()


@pytest.mark.asyncio
async def test_one_teacher_never_sees_another_conversation(stack) -> None:
    """Reading back is scoped by owner like everything else (ADR-22).

    The first version of this test asked as `GV-404`, a code belonging to
    nobody, and asserted 401 -- which `current_teacher` returns before this
    endpoint runs at all. It would have stayed green with the owner filter
    deleted. So the second teacher here exists, and what is asserted is that
    a real teacher sees an empty conversation rather than someone else's.
    """
    client, maker, monkeypatch = stack
    async with maker() as session:
        session.add(Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002"))
        await session.commit()

    monkeypatch.setattr(
        teacher_chat,
        "run_task",
        ScriptedAgent(NextStepCompleted(request_id="x", kind="say", text="của GV-001")),
    )
    await client.post("/api/teacher/chat/messages", json={"text": "riêng tôi"}, headers=TEACHER)

    mine = await client.get("/api/teacher/chat", headers=TEACHER)
    theirs = await client.get("/api/teacher/chat", headers={"X-Actor": "teacher:GV-002"})

    assert [turn["text"] for turn in mine.json()["turns"]] == ["riêng tôi", "của GV-001"]
    assert theirs.json()["turns"] == []


@pytest.mark.asyncio
async def test_a_step_aimed_at_a_taken_position_moves_to_the_next_free_one(stack) -> None:
    """The recovery half of the lesson `chat_messages` taught.

    Reading the position and inserting at it are two statements with a gap
    between them, so two of a teacher's requests can both aim at the same
    one -- React's StrictMode fires twice by design, and so does an impatient
    teacher. The unique index decides; the loser takes the next free position
    instead of failing.

    Tested by aiming twice on purpose rather than by racing. A race is not
    observable here: in-memory SQLite runs on a `StaticPool`, one connection
    shared by every session, so two concurrent requests have no transaction
    isolation between them and the result says more about the pool than about
    this code. Aiming twice exercises the same branch and says something true.
    """
    _, maker, _ = stack

    async with maker() as session:
        teacher = await session.scalar(select(Teacher))
        assert teacher is not None
        asking = Asking.of(teacher)

        thread = await teacher_chat._conversation(session, asking)

        first = await teacher_chat._record(
            session, thread, 0, TurnRecord(kind="teacher", text="một")
        )
        # Same position again, as a second request holding a stale count would.
        second = await teacher_chat._record(
            session, thread, 0, TurnRecord(kind="teacher", text="hai")
        )

        stored = (await session.scalars(select(TeacherTurn).order_by(TeacherTurn.sequence))).all()

    assert first == 1
    assert second == 2
    assert [turn.sequence for turn in stored] == [0, 1]
    assert [turn.text for turn in stored] == ["một", "hai"]


@pytest.mark.asyncio
async def test_a_teacher_keeps_one_conversation_across_messages(stack) -> None:
    """Asking again returns the running thread, not a new one.

    The schema says one per teacher, so a second insert is refused rather
    than tolerated -- and this is the path that must never be the thing that
    refuses a message.
    """
    _, maker, _ = stack

    async with maker() as session:
        teacher = await session.scalar(select(Teacher))
        assert teacher is not None
        asking = Asking.of(teacher)

        first = await teacher_chat._conversation(session, asking)
        again = await teacher_chat._conversation(session, asking)

        started = (await session.scalars(select(TeacherConversation))).all()

    assert first == again
    assert len(started) == 1


@pytest.mark.asyncio
async def test_a_teacher_who_only_reads_starts_no_conversation(stack) -> None:
    """A GET does not write.

    `_conversation` creates a thread when there is none, which is right for a
    message and wrong for a read: a browser prefetch, a HEAD probe or a retry
    would each leave a row, and two of them racing a POST is the easiest way
    to end up with two threads for one teacher.
    """
    client, maker, _ = stack

    read = await client.get("/api/teacher/chat", headers=TEACHER)

    assert read.status_code == 200
    assert read.json()["turns"] == []

    async with maker() as session:
        started = (await session.scalars(select(TeacherConversation))).all()

    assert started == []
