"""Queue access for BE.

BE enqueues work by task name and reads results back through arq's own result
store. It never imports the AGENT package: the task name is a constant in
`contracts`, so the two services agree on a string rather than on code.
"""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job, JobStatus

from be.config import Settings
from contracts import GRADE_SUBMISSION_TASK, GradingRequested

# arq defaults to a one second connect timeout, which is too tight for Docker
# Desktop on Windows: its port proxy needs a few seconds after the container
# reports healthy before it accepts connections, and the process dies at startup
# rather than waiting.
_CONNECT_TIMEOUT_SECONDS = 5


def redis_settings(settings: Settings) -> RedisSettings:
    """Build arq Redis settings with a connect timeout suited to this environment.

    Args:
        settings: Process settings supplying the Redis DSN.

    Returns:
        RedisSettings ready to hand to arq.
    """
    parsed = RedisSettings.from_dsn(settings.redis_url)
    parsed.conn_timeout = _CONNECT_TIMEOUT_SECONDS
    return parsed


async def create_queue_pool(settings: Settings) -> ArqRedis:
    """Open the Redis connection pool arq uses for enqueueing and result reads.

    Args:
        settings: Process settings supplying the Redis DSN.

    Returns:
        A connected ArqRedis pool. The caller owns it and must close it.

    Raises:
        OSError: If Redis is unreachable. Start it with
            `docker compose -f docker-compose.infra.yml up -d`. redis-py raises
            its own ConnectionError, which is not an OSError; it is translated
            here so callers can handle "the queue is down" without importing
            redis, a library BE only has because arq brought it.
    """
    try:
        return await create_pool(redis_settings(settings))
    except Exception as exc:  # noqa: BLE001 -- narrowed by re-raising as OSError
        raise OSError(f"Redis unreachable at {settings.redis_url}: {exc}") from exc


async def enqueue_grading(
    pool: ArqRedis,
    settings: Settings,
    request: GradingRequested,
) -> str:
    """Hand one submission to AGENT for grading.

    Args:
        pool: Connected arq pool.
        settings: Process settings supplying the queue name.
        request: The work item. Serialised to a plain dict so the payload on the
            wire stays independent of the pydantic version either side runs.

    Returns:
        The arq job id, which the client polls for a result.

    Raises:
        RuntimeError: If arq declines the job, which happens when a job with the
            same id already exists.

    Side effects:
        Writes a job onto the shared Redis queue.
    """
    job = await pool.enqueue_job(
        GRADE_SUBMISSION_TASK,
        request.model_dump(mode="json"),
        _queue_name=settings.agent_queue_name,
    )
    if job is None:
        raise RuntimeError(f"arq refused to enqueue submission {request.submission_id}")
    return job.job_id


async def read_job(pool: ArqRedis, settings: Settings, job_id: str) -> tuple[JobStatus, object]:
    """Read the current status and result of a previously enqueued job.

    Args:
        pool: Connected arq pool.
        settings: Process settings supplying the queue name.
        job_id: Identifier returned by enqueue_grading.

    Returns:
        A tuple of the job status and its raw result. The result is None until
        the job completes, and is whatever AGENT returned once it has.
    """
    job = Job(job_id, redis=pool, _queue_name=settings.agent_queue_name)
    status = await job.status()
    info = await job.result_info()
    return status, (info.result if info is not None else None)
