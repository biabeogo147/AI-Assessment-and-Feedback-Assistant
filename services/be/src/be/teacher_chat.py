"""The teacher's chat, where BE runs the loop and AGENT only advises.

One turn is several model calls. BE asks AGENT what to do next, does it or
refuses it, and asks again with the result attached, until AGENT answers in
words or the ceiling stops it. AGENT never runs anything: it holds no database
credentials, and authorisation belongs in the process that has the session and
knows who is calling.

Three properties come out of that arrangement rather than out of a prompt:

- **A proposal is not an action.** ADR-05 keeps irreversible work out of the
  chat flow. Here that is structural: the only writing path is the one BE
  builds, and this version builds none.
- **The loop ends.** `max_tool_steps` bounds it, and hitting the bound is said
  out loud. A request that never comes back is the worse failure -- nothing in
  the logs names a cause for it.
- **Each step is one model call**, so the invariant that an AGENT job times out
  before BE stops waiting is true of this path.

This version answers in the response and stores nothing, and the consequence is
larger than losing a turn on reload: **every message starts from an empty
history.** The endpoint takes one sentence and nothing else, so a teacher
answering the assistant's own clarifying question sends that answer with no
trace of what was asked. `ask_clarify` therefore exists here without a way to
be answered -- the gate is built and its second half is not.

That is why there is no screen yet. The durable conversation is the next piece
of work, and it is what makes the input gate of ADR-05 usable rather than
merely present.
"""

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from be.agent_gateway import AgentError, run_task
from be.config import Settings, get_settings
from be.db import get_session
from be.identity import current_teacher
from be.models import Teacher
from be.teacher_tools import Asking, UnknownTool, catalog_for, execute
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
    """One step of this turn, as the client should render it.

    Mirrors `TurnRecord` rather than reusing it: that type crosses the queue to
    AGENT, and adding a field here for the interface's sake would put it into
    a payload AGENT has no use for.
    """

    kind: str
    text: str = ""
    tool_name: str = ""
    tool_result: dict = Field(default_factory=dict)


class Answered(BaseModel):
    """The result of one turn.

    Attributes:
        kind: How the turn ended: `say` or `ask_clarify`.
        text: The words to show.
        choices: Options for `ask_clarify`. **Always empty in this version.**
            ADR-05 requires the options in a clarifying question to come from
            data BE supplied, and nothing here can corroborate that yet -- so
            a list the model wrote is dropped rather than shown. Passing it
            through would put invented class names in front of a teacher with
            the system's authority behind them. Real choices arrive with
            `resolve_class`, which builds them from the rows it found.
        turns: Every step, in order, so the interface can show what was done
            and not only what was said.
    """

    kind: str
    text: str
    choices: list[str] = Field(default_factory=list)
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


def _visible(record: TurnRecord) -> Turn:
    """Project one internal record onto what the client is shown."""
    return Turn(
        kind=record.kind,
        text=record.text,
        tool_name=record.tool_name,
        tool_result=record.tool_result,
    )


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
        How the turn ended, plus every step it took.

    Raises:
        HTTPException: 503 when AGENT cannot be reached at all. No tool failure
            reaches here: every one of them, unknown name or broken query
            alike, becomes a result the model reads and recovers from. That is
            the difference between the assistant being broken and the
            assistant being told no.

    Side effects:
        Enqueues one AGENT job per step. Runs read-only tools against the
        database. Stores nothing yet.
    """
    # Identity and catalog read once, as values. Each tool step rolls the
    # session back to release its connection, and that expires every ORM
    # object attached to it -- so nothing below may touch the `teacher` row
    # again.
    asking = Asking.of(teacher)
    catalog = catalog_for(asking)

    history: list[TurnRecord] = [TurnRecord(kind="teacher", text=said.text)]
    deadline = asyncio.get_running_loop().time() + settings.turn_budget_seconds

    for _ in range(settings.max_tool_steps):
        if asyncio.get_running_loop().time() >= deadline:
            # The step ceiling alone is not a promise about waiting: eight
            # steps times the job timeout is over nine minutes, and a browser
            # or a proxy would cut the connection long before that while BE
            # logged a success. This is the bound the teacher actually feels.
            logger.warning("turn budget spent for %s", asking.teacher_code)
            break

        try:
            step = await _ask_agent(request, settings, asking.full_name, catalog, history)
        except AgentError as unreachable:
            logger.warning("agent unreachable for %s: %s", asking.teacher_code, unreachable)
            raise HTTPException(status_code=503, detail=_AGENT_UNAVAILABLE) from unreachable

        if step.kind in {"say", "ask_clarify"}:
            history.append(TurnRecord(kind="assistant", text=step.text))
            if step.choices:
                # Dropped, not forwarded. See `Answered.choices`: an option
                # BE cannot trace back to a row it read is an option the model
                # made up, and it would appear to the teacher as something the
                # system knows about.
                logger.info(
                    "dropped %d uncorroborated choice(s) for %s",
                    len(step.choices),
                    asking.teacher_code,
                )
            return Answered(
                kind=step.kind,
                text=step.text,
                turns=[_visible(record) for record in history],
            )

        history.append(
            TurnRecord(kind="tool_call", tool_name=step.tool_name, tool_args=step.tool_args)
        )
        try:
            result = await execute(session, asking, step.tool_name, step.tool_args)
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

        history.append(TurnRecord(kind="tool_result", tool_name=step.tool_name, tool_result=result))

    # The ceiling. Reached, not crashed into: the teacher gets a sentence that
    # names the cause and suggests the one thing that helps.
    logger.warning("tool loop hit %d steps for %s", settings.max_tool_steps, asking.teacher_code)
    history.append(TurnRecord(kind="assistant", text=_CEILING_REACHED))
    return Answered(
        kind="say",
        text=_CEILING_REACHED,
        turns=[_visible(record) for record in history],
    )
