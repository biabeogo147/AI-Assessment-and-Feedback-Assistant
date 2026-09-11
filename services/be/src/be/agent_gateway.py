"""Calling AGENT, and checking what comes back.

Two responsibilities, and the second is the important one. Enqueueing is
plumbing. Validating is a business rule: ADR-18 says a question carries exactly
one correct option, an error label on every distractor, and more than one
worked solution -- and a rule enforced only by a prompt is not enforced. A
review of hand-written sample data on 2026-09-11 found a question with two
correct answers, so this is not a theoretical failure mode.
"""

import asyncio

from arq.connections import ArqRedis
from arq.jobs import Job, JobStatus

from be.config import Settings
from contracts import GeneratedQuestion

_POLL_SECONDS = 0.2


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
