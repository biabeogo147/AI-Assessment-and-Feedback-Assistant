"""Calling AGENT, and checking what comes back.

Two responsibilities, and the second is the important one. Enqueueing is
plumbing. Validating is a business rule: ADR-18 says a question carries exactly
one correct option, an error label on every distractor, and more than one
worked solution -- and a rule enforced only by a prompt is not enforced. A
review of hand-written sample data on 2026-09-11 found a question with two
correct answers, so this is not a theoretical failure mode.
"""

import asyncio
import logging
from collections.abc import AsyncIterator

from arq.connections import ArqRedis
from arq.jobs import Job, JobStatus

from be.config import Settings
from contracts import (
    GENERATE_RETRY_QUESTION_TASK,
    GeneratedQuestion,
    RetryQuestionCompleted,
    RetryQuestionRequested,
)

logger = logging.getLogger(__name__)

_POLL_SECONDS = 0.2

# How long one read of the stream channel waits before the loop looks at the
# job again. Small enough that finishing is noticed promptly, large enough that
# an idle stream is not a busy loop.
_LISTEN_SECONDS = 0.2


class AgentError(RuntimeError):
    """AGENT could not be reached, timed out, or returned unusable content."""


async def run_task(
    pool: ArqRedis | None,
    settings: Settings,
    task_name: str,
    payload: dict,
) -> dict:
    """Enqueue one AGENT task and wait for its result.

    BE waits rather than handing the client a job id, because every caller of
    this function is already inside a request the user is watching, and a second
    polling protocol on top of arq's would buy nothing.

    Args:
        pool: Connected arq pool, or None when the queue was unreachable at
            startup. BE stays up without it so phase 1 keeps working.
        settings: Process settings supplying the queue name and timeout.
        task_name: One of the task-name constants in `contracts`.
        payload: The serialised request message.

    Returns:
        The serialised reply message.

    Raises:
        AgentError: If the queue refuses the job, the worker never finishes
            within the timeout, or the job fails.

    Side effects:
        Writes a job onto the shared Redis queue.
    """
    if pool is None:
        raise AgentError("hàng đợi chưa sẵn sàng")

    job = await pool.enqueue_job(task_name, payload, _queue_name=settings.agent_queue_name)
    if job is None:
        raise AgentError(f"arq refused task {task_name}")

    deadline = asyncio.get_running_loop().time() + settings.agent_job_timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        status = await job.status()
        if status is JobStatus.complete:
            finished = Job(job.job_id, redis=pool, _queue_name=settings.agent_queue_name)
            info = await finished.result_info()
            if info is None or not info.success:
                raise AgentError(f"task {task_name} failed inside AGENT")
            return info.result
        await asyncio.sleep(_POLL_SECONDS)

    raise AgentError(f"task {task_name} did not finish in {settings.agent_job_timeout_seconds}s")


async def stream_task(
    pool: ArqRedis | None,
    settings: Settings,
    task_name: str,
    payload: dict,
    channel: str,
) -> AsyncIterator[tuple[str, object]]:
    """Enqueue one AGENT task and yield its output as it is written.

    The subscribe happens **before** the enqueue, and that order is the reason
    this function exists rather than three statements at the call site. Redis
    pub/sub keeps no history: publish to a channel nobody is listening on and
    the words are gone. arq hands a job to a worker almost immediately, so
    enqueueing first is handing the worker a chance to speak into an empty room.

    Args:
        pool: Connected arq pool, or None when the queue was unreachable.
        settings: Process settings supplying queue name and timeout.
        task_name: One of the task-name constants in `contracts`.
        payload: The serialised request message.
        channel: Where the worker was told to publish pieces.

    Yields:
        `("chunk", text)` for each piece as it arrives, then exactly one
        `("result", reply)` carrying the serialised reply.

    Raises:
        AgentError: If the queue refuses the job, the job fails, or nothing
            finishes within the timeout.

    Side effects:
        Subscribes to a Redis channel and writes a job onto the queue.
    """
    if pool is None:
        raise AgentError("hàng đợi chưa sẵn sàng")

    pubsub = pool.pubsub()
    try:
        # Inside the try, so a subscribe that fails half-way still reaches the
        # cleanup below instead of leaking a connection out of the pool.
        await pubsub.subscribe(channel)

        job = await pool.enqueue_job(task_name, payload, _queue_name=settings.agent_queue_name)
        if job is None:
            raise AgentError(f"arq refused task {task_name}")

        # Refreshed on every piece, so this is a silence timer and not a
        # length limit. A model writing a long answer is working; a model that
        # has said nothing for the whole window is not. Cutting off an answer
        # mid-flow because it was going well for too long would be absurd.
        deadline = asyncio.get_running_loop().time() + settings.agent_job_timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=_LISTEN_SECONDS
            )
            if message is not None and message.get("type") == "message":
                deadline = asyncio.get_running_loop().time() + settings.agent_job_timeout_seconds
                yield "chunk", _text(message["data"])
                continue

            if await job.status() is not JobStatus.complete:
                continue

            # The job is done, but pieces published in the last instant may
            # still be queued on this connection. Drain them before closing, or
            # the student loses the end of the sentence they were reading.
            while True:
                trailing = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.0)
                if trailing is None or trailing.get("type") != "message":
                    break
                yield "chunk", _text(trailing["data"])

            info = await Job(
                job.job_id, redis=pool, _queue_name=settings.agent_queue_name
            ).result_info()
            if info is None or not info.success:
                raise AgentError(f"task {task_name} failed inside AGENT")
            yield "result", info.result
            return

        raise AgentError(
            f"task {task_name} did not finish in {settings.agent_job_timeout_seconds}s"
        )
    finally:
        # Runs on a client disconnect too: the browser going away cancels this
        # generator, and an unclosed subscription would hold a connection from
        # the pool for the life of the process.
        #
        # Swallowed, because a failure while tidying up would otherwise
        # *replace* whatever went wrong first. The caller handles AgentError
        # and nothing else, so a ConnectionError raised here would escape a
        # generator that has already sent its status line -- the client gets a
        # broken stream and no reason for it.
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except Exception:  # noqa: BLE001 -- cleanup must not outrank the real error
            logger.warning("could not close the stream channel %s", channel, exc_info=True)


def _text(data: object) -> str:
    """Decode one published piece.

    Args:
        data: What redis handed back, bytes or str depending on how the pool
            was configured.

    Returns:
        The piece as text.
    """
    return data.decode() if isinstance(data, bytes) else str(data)


# How many times BE re-asks after rejecting a question. Two, because the point
# is to survive a model that misread the brief, not to argue with one that
# cannot do the task -- and a student is waiting on every attempt.
_RETRY_ASKS = 2


async def ask_for_retry_question(
    pool: ArqRedis | None,
    settings: Settings,
    ask: RetryQuestionRequested,
    origin_stem: str,
    spent: list[str],
) -> GeneratedQuestion:
    """Get one round's question, re-asking when what comes back breaks a rule.

    The re-ask carries the rejected stem in `previous_stems`. Sending the same
    payload again would leave a different answer to chance; naming what was
    wrong with the last one is the difference between a retry and a re-roll.

    ADR-18 and ADR-17 are checked here and not inside AGENT, because a
    generator that accepted its own work would be marking its own homework.
    AGENT does check its own shape before answering -- that saves a round trip,
    and this is still the check that counts.

    Args:
        pool: Connected arq pool, or None when the queue was unreachable.
        settings: Process settings.
        ask: The request, which this function copies and amends between tries.
        origin_stem: The phase 1 question being remediated.
        spent: Stems already used in earlier rounds of this question.

    Returns:
        A question that satisfies both rules.

    Raises:
        AgentError: If every attempt broke a rule, or the queue failed.

    Side effects:
        Writes up to three jobs onto the queue.
    """
    rejected: list[str] = []
    last: AgentError | None = None

    for attempt in range(1 + _RETRY_ASKS):
        payload = ask.model_copy(
            update={"previous_stems": (*ask.previous_stems, *rejected)}
        ).model_dump(mode="json")

        raw = await run_task(pool, settings, GENERATE_RETRY_QUESTION_TASK, payload)
        question = RetryQuestionCompleted.model_validate(raw).question

        try:
            validate_question(question)
            validate_retry(question, origin_stem, [*spent, *rejected])
        except AgentError as exc:
            logger.warning("rejected round question on attempt %d: %s", attempt + 1, exc)
            last = exc
            rejected.append(question.stem)
            continue

        return question

    # The last complaint travels with the refusal. Without it the 503 says only
    # that three tries failed, which tells whoever reads the log nothing about
    # which rule was broken -- and the rule is the whole reason we refused.
    raise AgentError(f"{1 + _RETRY_ASKS} lần thử đều không đạt — {last}")


def validate_question(question: GeneratedQuestion) -> None:
    """Check one generated question against ADR-18 before it is stored.

    Args:
        question: What AGENT produced.

    Raises:
        AgentError: If the question has anything other than exactly one correct
            option, a distractor with no error label, or fewer than two worked
            solutions.
    """
    correct = [option for option in question.options if option.is_correct]
    if len(correct) != 1:
        raise AgentError(
            f"a question must have exactly one correct option, got {len(correct)}: {question.stem}"
        )

    unmapped = [
        option.label
        for option in question.options
        if not option.is_correct and not option.error_label
    ]
    if unmapped:
        raise AgentError(f"distractors {unmapped} carry no error label: {question.stem}")

    if len(question.methods) < 2:
        raise AgentError(f"a question needs more than one worked solution: {question.stem}")


def validate_retry(question: GeneratedQuestion, origin_stem: str, spent: list[str]) -> None:
    """Check that a retry question is a new question, not the old one again.

    ADR-17 is specific about what a retry is for: it tests whether the student
    fixed the mistake, not whether they remember the answer. A round that hands
    back the same stem tests memory, which is the failure the whole ceiling of
    three rounds exists to avoid.

    Args:
        question: What AGENT produced for this round.
        origin_stem: The phase 1 question being remediated.
        spent: Stems already used in earlier rounds of this question.

    Raises:
        AgentError: If the stem repeats the origin or any earlier round.
    """
    normalise = " ".join(question.stem.split())
    if normalise == " ".join(origin_stem.split()):
        raise AgentError(f"a retry question repeats the question it replaces: {question.stem}")
    if normalise in {" ".join(stem.split()) for stem in spent}:
        raise AgentError(f"a retry question repeats an earlier round: {question.stem}")
