"""The tool loop, and the two things that must never depend on the model.

BE owns this loop. AGENT is asked what to do next, once per step, and BE
decides whether to do it. That arrangement exists so two properties hold no
matter how the model behaves:

- **Authorisation runs where the session is.** A proposal naming another
  teacher's class is refused by the executor, not by the prompt.
- **The loop stops.** A model that keeps asking for tools is cut off by a
  ceiling, and the teacher is told, rather than being left with a request that
  never returns.

Every test here scripts AGENT rather than calling it, the same way
`test_core_flow.py` does: the boundary is the gateway, and a test that reached
into the worker would be the first crack in the wall between the services.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import teacher_chat
from be.config import get_settings
from be.db import bind_sessions, prepare_schema
from be.identity import Asking
from be.models import Assessment, AssessmentState, SchoolClass, Student, Teacher
from be.seed import seed_if_empty
from be.teacher_chat import router as teacher_router
from be.teacher_tools import UnknownTool, catalog_for, execute
from contracts import NextStepCompleted

TEACHER = {"X-Actor": "teacher:GV-001"}
STRANGER = {"X-Actor": "teacher:GV-002"}


class ScriptedAgent:
    """Answer each step of the loop with a queued proposal.

    Records what it was asked, because the history BE sends is the only way
    the model learns what a tool returned -- and a loop that forgot to send it
    would spin to the ceiling on every turn while looking correct from outside.
    """

    def __init__(self, *steps: NextStepCompleted) -> None:
        self.steps = list(steps)
        self.asked: list[dict] = []

    async def __call__(self, pool, settings, task_name, payload) -> dict:
        self.asked.append(payload)
        step = (
            self.steps.pop(0)
            if self.steps
            else NextStepCompleted(
                request_id=payload["request_id"], kind="say", text="hết kịch bản"
            )
        )
        return step.model_copy(update={"request_id": payload["request_id"]}).model_dump(mode="json")


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """An app with a second teacher, so "not mine" is a case that exists."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        stranger = Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002")
        session.add(stranger)
        await session.flush()
        session.add(SchoolClass(teacher_id=stranger.id, name="11B"))
        session.add(
            Assessment(
                teacher_id=stranger.id,
                title="Đề của người khác",
                subject="Toán",
                grade="11",
                state=AssessmentState.PUBLISHED,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

    app = FastAPI()
    app.include_router(teacher_router)
    app.state.queue_pool = object()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker, monkeypatch

    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _teacher(maker, code: str) -> Teacher:
    async with maker() as session:
        found = await session.scalar(select(Teacher).where(Teacher.teacher_code == code))
        assert found is not None
        return found


@pytest.mark.asyncio
async def test_a_turn_runs_a_tool_and_then_answers(stack) -> None:
    """The ordinary path: ask, run, ask again, answer.

    The assertion that matters is the second one -- the tool's result reaching
    the second question. That is what stops the model repeating itself, and it
    is invisible from the reply.
    """
    client, _, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x", kind="call_tool", tool_name="find_class", tool_args={"name": "12A"}
        ),
        NextStepCompleted(request_id="x", kind="say", text="Lớp 12A có 40 học sinh."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12A thế nào"}, headers=TEACHER
    )

    assert reply.status_code == 200
    body = reply.json()
    assert body["kind"] == "say"
    assert body["text"] == "Lớp 12A có 40 học sinh."

    kinds = [turn["kind"] for turn in body["turns"]]
    assert kinds == ["teacher", "tool_call", "tool_result", "assistant"]

    second_question = agent.asked[1]
    results = [turn for turn in second_question["history"] if turn["kind"] == "tool_result"]
    assert results and results[0]["tool_result"]["name"] == "12A"


@pytest.mark.asyncio
async def test_the_loop_stops_at_its_ceiling_and_says_so(stack) -> None:
    """A model that only ever asks for tools is cut off, out loud.

    Silence would be the worse failure: the teacher would be left with a
    request that never came back, and nothing in the logs would name a cause.
    """
    client, _, monkeypatch = stack
    forever = ScriptedAgent(
        *[
            NextStepCompleted(
                request_id="x", kind="call_tool", tool_name="find_class", tool_args={"name": "12A"}
            )
            for _ in range(20)
        ]
    )
    monkeypatch.setattr(teacher_chat, "run_task", forever)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12A thế nào"}, headers=TEACHER
    )

    assert reply.status_code == 200
    body = reply.json()
    assert body["kind"] == "say"
    # The ceiling's own sentence, not merely some sentence. `ScriptedAgent`
    # falls back to saying "hết kịch bản" when its script runs out, so a test
    # that only checked for non-empty text would report "the ceiling works"
    # after a run where the ceiling was never reached.
    assert body["text"] == teacher_chat._CEILING_REACHED
    # Exactly the configured number, read from the config. `<= 8` would pass a
    # loop that ran once, and a hard 8 would go quietly green for anyone who
    # lowered the setting.
    assert len(forever.asked) == get_settings().max_tool_steps


@pytest.mark.asyncio
async def test_the_options_are_written_by_be_not_by_the_model(stack) -> None:
    """BE renders the options from the rows it read; the model's are ignored.

    ADR-05 requires the options in a clarifying question to come from data the
    system supplied, and this is the only way to get that property rather than
    approximate it. Filtering what the model wrote was the first attempt, and
    it leaked in both directions: "12A-1" passed on the strength of a real
    "12A", while a legitimate "12A 3 học sinh" was thrown away. Both were
    measured, not imagined.

    So the model writes the question and BE writes the answers. There is no
    text to filter, and an invented class name has no path to the screen.
    """
    client, maker, monkeypatch = stack
    async with maker() as session:
        mine = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        assert mine is not None
        second = SchoolClass(teacher_id=mine.id, name="12B")
        session.add(second)
        await session.flush()
        session.add(
            Student(class_id=second.id, full_name="Ngô Thị Hai", student_code="HS2026-7001")
        )
        await session.commit()

    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x", kind="call_tool", tool_name="find_class", tool_args={"name": "12"}
        ),
        NextStepCompleted(
            request_id="x",
            kind="ask_clarify",
            text="Bạn muốn xem lớp nào?",
            # Every one of these is wrong in a different way: a real name with
            # a wrong roster, a name one character off a real one, and a class
            # that never existed. None of them reaches the teacher, because
            # none of them is consulted.
            choices=("12A (45 học sinh)", "12A-1", "11C"),
        ),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12 thế nào"}, headers=TEACHER
    )

    assert reply.status_code == 200
    body = reply.json()
    assert body["kind"] == "ask_clarify"
    # Both rows that matched "12", with the roster sizes BE counted -- not the
    # 45 the model claimed, and without the two classes it invented.
    assert body["choices"] == ["12A (3 học sinh)", "12B (1 học sinh)"]
    assert body["more_choices"] == 0
    # The question is still the model's words. It writes the sentence; BE
    # writes the answers.
    assert body["text"] == "Bạn muốn xem lớp nào?"


@pytest.mark.asyncio
async def test_a_tool_outside_the_catalog_is_refused(stack) -> None:
    """The catalog is a convenience; the executor is the gate.

    The model reads the catalog, and a model reads things wrongly. A proposal
    naming a tool that was never offered must not run just because it arrived
    in the right shape.
    """
    client, _, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x", kind="call_tool", tool_name="delete_everything", tool_args={}
        ),
        NextStepCompleted(request_id="x", kind="say", text="Mình chưa làm được việc đó."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "xoá hết đi"}, headers=TEACHER
    )

    assert reply.status_code == 200
    results = [turn for turn in reply.json()["turns"] if turn["kind"] == "tool_result"]
    assert results and "error" in results[0]["tool_result"]


@pytest.mark.asyncio
async def test_a_tool_cannot_reach_another_teachers_class(stack) -> None:
    """Scoping happens at execution, with the row in hand.

    ADR-22: the answer for a class that belongs to someone else is the same as
    for a class that does not exist. Two different answers would let anyone
    map the school's classes by watching which sentence comes back.
    """
    _, maker, _ = stack
    mine = await _teacher(maker, "GV-001")

    async with maker() as session:
        theirs = await session.scalar(select(SchoolClass).where(SchoolClass.name == "11B"))
        assert theirs is not None

        me = Asking.of(mine)
        my_own = await execute(session, me, "find_class", {"name": "12A"})
        by_name = await execute(session, me, "find_class", {"name": "11B"})
        missing = await execute(session, me, "find_class", {"name": "lớp nào tên này"})

    # Without this first assertion the test would pass against a `find_class`
    # that found nothing ever: the two refusals below are the same constant,
    # so comparing them to each other proves only that a constant equals
    # itself.
    assert my_own["found"] is True
    assert my_own["name"] == "12A"

    assert by_name == missing


@pytest.mark.asyncio
async def test_the_catalog_only_offers_read_tools(stack) -> None:
    """Nothing in this version can change anything.

    ADR-05 puts publishing behind a gate that is not the chat flow. The
    cheapest way to honour that in a first version is to ship no tool that
    writes, so there is no irreversible action for a gate to guard.
    """
    _, maker, _ = stack
    mine = await _teacher(maker, "GV-001")

    offered = {tool.name for tool in catalog_for(Asking.of(mine))}

    assert offered == {"find_class", "class_assessment_summary"}


@pytest.mark.asyncio
async def test_an_unknown_tool_raises_rather_than_returning_nothing(stack) -> None:
    """`execute` distinguishes "no such tool" from "nothing found".

    The loop turns the first into a result the model can read and recover
    from. Conflating them would let a typo look like an empty class.
    """
    _, maker, _ = stack
    mine = await _teacher(maker, "GV-001")

    async with maker() as session:
        with pytest.raises(UnknownTool):
            await execute(session, Asking.of(mine), "no_such_tool", {})
