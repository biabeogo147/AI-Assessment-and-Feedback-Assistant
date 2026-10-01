"""The teacher's chat, where BE runs the loop and AGENT only advises.

One turn is several model calls. BE asks AGENT what to do next, does it or
refuses it, and asks again with the result attached, until AGENT answers in
words or the ceiling stops it. AGENT never runs anything: it holds no database
credentials, and authorisation belongs in the process that has the session and
knows who is calling.

Three properties come out of that arrangement rather than out of a prompt:

- **A proposal is not an action.** ADR-05 keeps irreversible work out of the
  chat flow. Here that is structural: BE decides which proposals run, and the
  tools it offers can only do reversible things. Approving and publishing have
  no tool at all, and `tools/check_contract.py` keeps it that way.
- **The loop ends.** `max_tool_steps` bounds it, and hitting the bound is said
  out loud. A request that never comes back is the worse failure -- nothing in
  the logs names a cause for it.
- **Each step is one model call**, so the invariant that an AGENT job times out
  before BE stops waiting is true of this path.

The conversation is durable, and that is what makes `ask_clarify` answerable.
A message carries the whole thread with it, so when the assistant asks "which
class?" and the teacher answers "12A", the model sees its own question. While
nothing was stored, that answer arrived with no trace of what had been asked
and the input gate of ADR-05 existed with no second half.

Every step is committed on its own. A worker dying mid-turn therefore costs
the step it was on rather than the conversation, and the pooled connection is
released before each wait on AGENT. The cost is that half a turn is a state
the table can hold: a failed turn leaves the teacher's message stored with no
answer under it, and a retry stores the message again.

One rule the whole file obeys, learned three times over: **work with values,
never with rows.** `rollback` expires every ORM object in the session, and
this loop rolls back between tool steps, so an attribute read on a row loaded
earlier is database IO from a place SQLAlchemy's async bridge cannot reach --
`MissingGreenlet`, raised far from its cause.
"""

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from be.agent_gateway import AgentError, run_task
from be.config import Settings, get_settings
from be.db import get_session
from be.identity import Asking, current_teacher
from be.models import Teacher, TeacherConversation, TeacherTurn
from be.teacher_tools import UnknownTool, catalog_for, execute
from contracts import (
    PROPOSE_NEXT_STEP_TASK,
    NextStepCompleted,
    NextStepRequested,
    ToolSpec,
    TurnRecord,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["teacher-chat"])

# Said when the loop runs out of steps. It names the cause, because a teacher
# who is told only "something went wrong" will ask the same question again and
# spend the same budget reaching the same ceiling.
_CEILING_REACHED = (
    "Mình tra mãi mà chưa ra câu trả lời gọn cho câu này. Bạn thử hỏi cụ thể hơn giúp mình nhé, "
    "ví dụ nói rõ tên lớp và tên bài kiểm tra."
)

_AGENT_UNAVAILABLE = "Trợ lý chưa trả lời được. Bạn thử lại sau một chút nhé."


class Said(BaseModel):
    """What the teacher typed."""

    text: str = Field(min_length=1, max_length=2000)


class Turn(BaseModel):
    """One step of a turn, as the client should render it.

    Mirrors `TurnRecord` rather than reusing it: that type crosses the queue to
    AGENT, and adding a field here for the interface's sake would put it into
    a payload AGENT has no use for. The last four fields are exactly that
    case -- the subject of the step and what it cost are for the screen and
    for whoever debugs it, and mean nothing to the model.

    `tool_args` is deliberately absent. The arguments are stored, because a
    trace without them cannot answer what was asked; they are not sent,
    because nothing on a screen is built from them.
    """

    kind: str
    text: str = ""
    tool_name: str = ""
    tool_result: dict = Field(default_factory=dict)
    entity_kind: str = ""
    entity_id: str = ""
    model_tokens: int = 0
    duration_ms: int = 0


class Answered(BaseModel):
    """The result of one turn.

    Attributes:
        kind: How the turn ended: `say` or `ask_clarify`.
        text: The words to show. Written by the model.
        choices: Options for `ask_clarify`, written by **BE** from the rows a
            tool returned (ADR-23). Whatever the model put in its own
            `choices` is ignored: BE holds the rows, so a list the model wrote
            is at best a copy of them and at worst an invented class name
            arriving in front of a teacher with the system's authority behind
            it. Empty when no tool produced candidates this turn, which makes
            the question an open one rather than a broken list.
        more_choices: How many further candidates were cut from `choices`, so
            the interface can say the list is partial. A teacher with thirty
            classes shown six of them and told nothing reads it as lost data.
        turns: Every step, in order, so the interface can show what was done
            and not only what was said.
    """

    kind: str
    text: str
    choices: list[str] = Field(default_factory=list)
    more_choices: int = 0
    turns: list[Turn] = Field(default_factory=list)


async def _ask_agent(
    request: Request,
    settings: Settings,
    teacher_name: str,
    catalog: tuple[ToolSpec, ...],
    history: list[TurnRecord],
) -> NextStepCompleted:
    """Ask AGENT for one proposal.

    Args:
        request: Carries the queue pool on `app.state`.
        settings: Process settings.
        teacher_name: How the assistant should address the person. A plain
            string, not the row: this is called between tool steps, and each
            step rolls the session back to release its connection, which
            expires every ORM object attached to it. Reading an attribute off
            an expired row here would be database IO from a place SQLAlchemy's
            async bridge cannot reach -- `MissingGreenlet`, far from its cause.
            No id travels either way, because AGENT resolves nothing.
        catalog: The tools this teacher may use, resolved once before the loop.
        history: Everything so far, oldest first.

    Returns:
        The proposal.

    Raises:
        AgentError: When the queue refuses the job or the worker does not
            finish in time.
    """
    asked = NextStepRequested(
        request_id=str(uuid.uuid4()),
        teacher_name=teacher_name,
        history=tuple(history),
        catalog=catalog,
    )
    answer = await run_task(
        getattr(request.app.state, "queue_pool", None),
        settings,
        PROPOSE_NEXT_STEP_TASK,
        asked.model_dump(mode="json"),
    )
    return NextStepCompleted.model_validate(answer)


def _offered(result: dict) -> tuple[list[str], int]:
    """Render the options for a clarifying question from a tool's own result.

    BE writes these, not the model. Filtering what a model wrote was the first
    attempt and it leaked both ways, measured rather than guessed: "12A-1"
    passed on the strength of a real "12A", "12A (45 học sinh)" passed with a
    roster nobody counted, and a perfectly good "12A 3 học sinh" was thrown
    away. Every one of those holes closes at once when there is no free text
    to inspect -- the model writes the question, BE writes the answers.

    Args:
        result: One tool's return value. Only `candidates` is read: a
            not-found list is context for the assistant to mention, not a set
            of options to click.

    Returns:
        The options, and how many further candidates were cut. The count
        travels so the question can admit the list is partial -- a teacher
        with thirty classes shown six of them, told nothing, reads it as lost
        data.
    """
    listed = result.get("candidates")
    if not isinstance(listed, list):
        return [], 0

    options = [
        f"{entry['name']} ({entry['student_count']} học sinh)"
        for entry in listed
        if isinstance(entry, dict)
        and isinstance(entry.get("name"), str)
        and isinstance(entry.get("student_count"), int)
    ]
    more = result.get("more")
    return options, more if isinstance(more, int) and more > 0 else 0


# How many past steps travel to the model. The transcript is resent on every
# step of every turn, so an unbounded history makes a long-running
# conversation quadratically expensive -- and the oldest turns are the least
# likely to matter. A constant rather than a setting: nothing an operator
# would tune yet, and a setting nobody reads is a promise the config does not
# keep.
_HISTORY_STEPS = 40

# Which entity a tool result is about, for the row that records the step. The
# subject is what the interface draws and what a later question links to; the
# sentence announcing it is not.
#
# `assessment_id` was taken out of here once, when a review pointed out that
# no tool returned one and the branch was unreachable. `create_draft` returns
# one now, so it is back -- and this is the first turn whose subject is a paper
# rather than a class, which is what an `Action result card` needs to draw
# anything about drafting.
_ENTITY_KEYS = (("class_id", "class"), ("assessment_id", "assessment"))


def _subject(result: dict) -> tuple[str, str]:
    """Name the entity a tool result is about, when it is about one.

    A class from `find_class`, or a draft from `create_draft` and
    `start_drafting`. The columns hold whatever the tools actually return, so
    they grow as the tools do.

    A result is about something when it says it succeeded, and the tools say
    that three ways: `found` for a lookup, `created` for a new draft,
    `started` for a round of generation. Listing the three beats inspecting
    the tool name, because the name is not what carries the id.

    Args:
        result: One tool's return value.

    Returns:
        The kind and the id, or two empty strings. Only a success has a
        subject: a refusal is about nothing, and recording its arguments as an
        entity would create links to rows that were never found.
    """
    if not any(result.get(flag) for flag in ("found", "created", "started")):
        return "", ""
    for key, kind in _ENTITY_KEYS:
        value = result.get(key)
        if isinstance(value, str) and value:
            return kind, value
    return "", ""


async def _latest_conversation(session: AsyncSession, asking: Asking) -> str | None:
    """Find the id of this teacher's running conversation, if they have one.

    Ordered by `started_at` **and then by id**. Without the second key, two
    conversations created inside the same clock tick tie, and the row this
    returns is then whichever the database felt like -- so a teacher would
    watch their history flip between two threads on consecutive messages, a
    bug that never reproduces.

    Args:
        session: Database session.
        asking: Whose conversation.

    Returns:
        The id, or None when the teacher has never spoken.
    """
    return await session.scalar(
        select(TeacherConversation.id)
        .where(TeacherConversation.teacher_id == asking.teacher_id)
        .order_by(TeacherConversation.started_at.desc(), TeacherConversation.id.desc())
        .limit(1)
    )


async def _conversation(session: AsyncSession, asking: Asking) -> str:
    """Find this teacher's running conversation, or start one.

    The most recent one, because starting a fresh thread is not a thing a
    teacher can ask for yet. When it becomes one, this is the only function
    that changes.

    Args:
        session: Database session.
        asking: Whose conversation.

    Returns:
        Its id, as a string. Not the row: callers commit between steps and
        `rollback` expires ORM objects, so a row handed out here would raise
        `MissingGreenlet` on its next attribute read.

    Side effects:
        Inserts a row when the teacher has never spoken before.
    """
    for attempt in range(2):
        found = await _latest_conversation(session, asking)
        if found is not None:
            return found

        started = TeacherConversation(teacher_id=asking.teacher_id, started_at=datetime.now(UTC))
        session.add(started)
        try:
            # Committed, not flushed. Two of this teacher's requests arrive
            # together routinely -- a screen loading while they type -- and the
            # loser recovers by reading the winner's row. A flush leaves that
            # row invisible outside its own transaction, so the loser would
            # find nothing and give up: the recovery path would exist and never
            # work. Found by a test that fired two requests at once, not by
            # reading this function.
            await session.commit()
        except IntegrityError:
            await session.rollback()
            if attempt:
                raise
            continue
        return started.id

    raise AssertionError("unreachable: the loop returns or raises")


async def _stored_turns(session: AsyncSession, conversation_id: str) -> list[TeacherTurn]:
    """Read a conversation back, oldest first."""
    rows = await session.scalars(
        select(TeacherTurn)
        .where(TeacherTurn.conversation_id == conversation_id)
        .order_by(TeacherTurn.sequence)
    )
    return list(rows)


def _as_records(turns: list[TeacherTurn]) -> list[TurnRecord]:
    """Turn stored steps into the history AGENT reads.

    Only the tail travels. See `_HISTORY_STEPS` for why, and note the cut is
    from the front: the model needs the question it just asked far more than
    it needs last week's.

    Args:
        turns: Stored steps, oldest first.

    Returns:
        The last `_HISTORY_STEPS` of them as contract records.
    """
    return [
        TurnRecord(
            kind=turn.kind,
            text=turn.text,
            tool_name=turn.tool_name,
            tool_args=turn.tool_args or {},
            tool_result=turn.tool_result or {},
        )
        for turn in turns[-_HISTORY_STEPS:]
    ]


async def _record(
    session: AsyncSession,
    conversation_id: str,
    sequence: int,
    record: TurnRecord,
    *,
    duration_ms: int = 0,
    model_tokens: int = 0,
) -> int:
    """Append one step to the conversation and commit it.

    Committed per step rather than per turn, so a worker dying mid-loop costs
    the step it was on and not the conversation. It is also what releases the
    pooled connection before the next wait on AGENT.

    Reading the position and inserting at it are two statements with a gap in
    between, so two of a teacher's requests can both aim at the same one. The
    unique index decides, and the loser takes the next free position rather
    than failing: `chat_messages` sets the precedent for the constraint, and
    `student_routes` sets it for the recovery -- copying only the first half
    would turn an ordinary double-click into a 500 with no Vietnamese in it.

    Args:
        session: Database session.
        conversation_id: Which conversation.
        sequence: Position to aim for. Advisory: the returned value is where
            the step actually landed.
        record: The step.
        duration_ms: How long the model call that produced it took.
        model_tokens: What that call spent.

    Returns:
        The position after this step, which the caller uses for the next one.

    Raises:
        IntegrityError: If the position is still taken after re-reading, which
            would mean something other than a race.

    Side effects:
        Inserts and commits. Rolls back once on a collision.
    """
    kind, entity_id = _subject(record.tool_result)

    for attempt in range(2):
        session.add(
            TeacherTurn(
                conversation_id=conversation_id,
                sequence=sequence,
                kind=record.kind,
                text=record.text,
                tool_name=record.tool_name,
                tool_args=dict(record.tool_args),
                tool_result=dict(record.tool_result),
                entity_kind=kind,
                entity_id=entity_id,
                duration_ms=duration_ms,
                model_tokens=model_tokens,
                created_at=datetime.now(UTC),
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            if attempt:
                raise
            taken = await session.scalar(
                select(func.max(TeacherTurn.sequence)).where(
                    TeacherTurn.conversation_id == conversation_id
                )
            )
            sequence = (taken or 0) + 1
            continue
        return sequence + 1

    raise AssertionError("unreachable: the loop returns or raises")


def _visible(turn: TeacherTurn) -> Turn:
    """Project one stored step onto what the client is shown."""
    return Turn(
        kind=turn.kind,
        text=turn.text,
        tool_name=turn.tool_name,
        tool_result=turn.tool_result or {},
        entity_kind=turn.entity_kind,
        entity_id=turn.entity_id,
        model_tokens=turn.model_tokens,
        duration_ms=turn.duration_ms,
    )


async def _rendered(session: AsyncSession, conversation_id: str, since: int) -> list[Turn]:
    """Read back the steps of one turn, for the reply that reports it.

    Read from the table rather than rendered from the in-memory history, for
    two reasons. The history holds the whole conversation -- the model needs
    that context -- so building the reply from it returned every earlier step
    as though it had just happened, and a client appending them would redraw
    the conversation on top of itself. And the stored row is the only place
    the subject and the cost live.

    Args:
        session: Database session.
        conversation_id: Which conversation.
        since: First position belonging to this turn.

    Returns:
        This turn's steps, in order.
    """
    rows = await session.scalars(
        select(TeacherTurn)
        .where(TeacherTurn.conversation_id == conversation_id, TeacherTurn.sequence >= since)
        .order_by(TeacherTurn.sequence)
    )
    return [_visible(turn) for turn in rows]


@router.post("/teacher/chat/messages", response_model=Answered)
async def say_something(
    said: Said,
    request: Request,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Answered:
    """Take one turn of the teacher's conversation.

    Args:
        said: What the teacher typed.
        request: Carries the queue pool.
        teacher: Resolved from the actor header (ADR-13).
        session: Database session every tool runs on.
        settings: Supplies `max_tool_steps`.

    Returns:
        How the turn ended, plus the steps of **this turn** read back from the
        table. Not the whole conversation: a client appending these to what it
        already shows would otherwise redraw the thread on top of itself.

    Raises:
        HTTPException: 503 when AGENT cannot be reached at all. No tool failure
            reaches here: every one of them, unknown name or broken query
            alike, becomes a result the model reads and recovers from. That is
            the difference between the assistant being broken and the
            assistant being told no.

    Side effects:
        Appends every step of the turn to the teacher's conversation and
        commits each one. Enqueues one AGENT job per step, and runs read-only
        tools against the database.
    """
    # Identity and catalog read once, as values. Each tool step rolls the
    # session back to release its connection, and that expires every ORM
    # object attached to it -- so nothing below may touch the `teacher` row
    # again.
    asking = Asking.of(teacher)
    catalog = catalog_for(asking)

    # The id as a plain string, read once -- see the module docstring for the
    # rule. Worth naming the mechanism precisely, because the first version of
    # this comment blamed `commit` and that is wrong: `bind_sessions` builds
    # sessions with `expire_on_commit=False`, so commits here leave objects
    # usable. What expires them is the `rollback` between tool steps, which
    # ignores that setting. Same defence, different cause -- and a lesson
    # recorded with the wrong cause gets applied in the wrong place next time.
    thread = await _conversation(session, asking)
    stored = await _stored_turns(session, thread)
    position = len(stored)
    # Where this turn starts, so the reply can report its own steps and not
    # the whole conversation.
    began = position

    # The whole conversation, not just this message. Before it was stored, a
    # teacher answering the assistant's own clarifying question sent that
    # answer with no trace of what had been asked -- so the input gate of
    # ADR-05 existed with no way to be answered.
    history = _as_records(stored)
    history.append(TurnRecord(kind="teacher", text=said.text))
    position = await _record(session, thread, position, history[-1])

    # Options for a clarifying question, rendered by BE from the last tool
    # result that produced candidates. A question may offer these and nothing
    # else (ADR-05, ADR-23).
    offered: list[str] = []
    offered_more = 0
    deadline = asyncio.get_running_loop().time() + settings.turn_budget_seconds

    for _ in range(settings.max_tool_steps):
        if asyncio.get_running_loop().time() >= deadline:
            # The step ceiling alone is not a promise about waiting: eight
            # steps times the job timeout is over nine minutes, and a browser
            # or a proxy would cut the connection long before that while BE
            # logged a success. This is the bound the teacher actually feels.
            logger.warning("turn budget spent for %s", asking.teacher_code)
            break

        started = time.monotonic()
        try:
            step = await _ask_agent(request, settings, asking.full_name, catalog, history)
        except AgentError as unreachable:
            logger.warning("agent unreachable for %s: %s", asking.teacher_code, unreachable)
            raise HTTPException(status_code=503, detail=_AGENT_UNAVAILABLE) from unreachable

        spent_ms = int((time.monotonic() - started) * 1000)

        if step.kind in {"say", "ask_clarify"}:
            history.append(TurnRecord(kind="assistant", text=step.text))
            position = await _record(
                session,
                thread,
                position,
                history[-1],
                duration_ms=spent_ms,
                model_tokens=step.model_tokens,
            )
            if step.choices:
                # Ignored, not filtered. BE has the rows; whatever the model
                # wrote here is at best a copy and at worst an invention.
                logger.info(
                    "ignored %d model-written choice(s) for %s",
                    len(step.choices),
                    asking.teacher_code,
                )
            return Answered(
                kind=step.kind,
                text=step.text,
                choices=offered,
                more_choices=offered_more,
                turns=await _rendered(session, thread, began),
            )

        history.append(
            TurnRecord(kind="tool_call", tool_name=step.tool_name, tool_args=step.tool_args)
        )
        position = await _record(
            session,
            thread,
            position,
            history[-1],
            duration_ms=spent_ms,
            model_tokens=step.model_tokens,
        )

        try:
            result = await execute(
                session,
                asking,
                step.tool_name,
                step.tool_args,
                # The writing tools queue work; the reading ones never touch
                # this. A dead queue therefore costs drafting and nothing else.
                pool=getattr(request.app.state, "queue_pool", None),
                settings=settings,
            )
        except UnknownTool:
            # Back to the model as data, not as an exception. It proposed
            # something that does not exist -- often a tool it half-remembers
            # from another context -- and the recovery is for it to read the
            # refusal and choose from the catalog it was actually given.
            logger.info("refused tool %r for %s", step.tool_name, asking.teacher_code)
            result = {"error": f"không có tool nào tên {step.tool_name}"}
        except Exception:
            # Every other failure too, and for the same reason. A tool that
            # breaks is not the assistant breaking: the model can say "mình
            # chưa tra được" and the teacher can ask something else, which is
            # a better turn than a 500 with no Vietnamese in it. The cause
            # goes to the log, not to the prompt -- a stack trace in the
            # history is text the model would try to act on.
            logger.exception("tool %r failed for %s", step.tool_name, asking.teacher_code)
            result = {"error": f"tool {step.tool_name} chạy không xong"}
        finally:
            # Release the connection between steps. Without this, one session
            # holds a pooled connection -- and an idle Postgres transaction --
            # across every `run_task` wait in the turn. The pool is 15 wide, so
            # a handful of teachers chatting would stall every other request in
            # the process, including the ones students poll on.
            await session.rollback()

        # Replaced, not merged. Keeping the previous tool's candidates meant a
        # question about something else arrived with them still attached: ask
        # about a class, then ask how many questions, and the second question
        # came back offering two class names as its answers.
        offered, offered_more = _offered(result)
        history.append(TurnRecord(kind="tool_result", tool_name=step.tool_name, tool_result=result))
        position = await _record(session, thread, position, history[-1])

    # The ceiling. Reached, not crashed into: the teacher gets a sentence that
    # names the cause and suggests the one thing that helps.
    logger.warning("tool loop hit %d steps for %s", settings.max_tool_steps, asking.teacher_code)
    history.append(TurnRecord(kind="assistant", text=_CEILING_REACHED))
    await _record(session, thread, position, history[-1])
    return Answered(
        kind="say",
        text=_CEILING_REACHED,
        turns=await _rendered(session, thread, began),
    )


@router.get("/teacher/chat", response_model=Answered)
async def read_conversation(
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> Answered:
    """Read this teacher's conversation back.

    Scoped by owner like everything else (ADR-22): the conversation is found
    through `teacher_id`, so there is no id a caller could pass to reach
    someone else's.

    Args:
        teacher: Resolved from the actor header.
        session: Database session.

    Returns:
        Every step so far. `kind` is "say" and `text` is empty, because
        reading is not a turn -- nothing was said by answering this.
    """
    asking = Asking.of(teacher)
    # Deliberately not `_conversation`: that one starts a thread when there is
    # none, and a GET that writes is a GET that a browser prefetch, a HEAD
    # probe or a retry can multiply. A teacher who has never spoken has an
    # empty conversation, which is exactly what an empty list says.
    thread = await _latest_conversation(session, asking)
    if thread is None:
        return Answered(kind="say", text="", turns=[])

    stored = await _stored_turns(session, thread)
    return Answered(kind="say", text="", turns=[_visible(turn) for turn in stored])
