"""arq worker process for AGENT.

Run with:  arq agent.worker.WorkerSettings

Known Windows limitation: arq registers signal handlers through
``loop.add_signal_handler``, which raises NotImplementedError on the Windows
ProactorEventLoop. arq swallows that and logs it at debug level, so the worker
runs but does not shut down gracefully -- Ctrl+C cuts an in-flight job rather
than letting it finish. Accepted for local MVP work; revisit when the service is
containerised on Linux.
"""

import logging

from arq.connections import RedisSettings
from arq.worker import func

from agent.config import get_settings
from agent.handlers import draft_assessment, explain, generate_retry_question
from agent.legacy_grading import grade_submission
from contracts import (
    DRAFT_ASSESSMENT_TASK,
    EXPLAIN_TURN_TASK,
    GENERATE_RETRY_QUESTION_TASK,
    GRADE_SUBMISSION_TASK,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

_settings = get_settings()

# arq defaults to a one second connect timeout, which is too tight for Docker
# Desktop on Windows: its port proxy needs a few seconds after the container
# reports healthy before it accepts connections, and the worker exits at startup
# rather than waiting.
_CONNECT_TIMEOUT_SECONDS = 5


def _redis_settings() -> RedisSettings:
    """Build arq Redis settings with a connect timeout suited to this environment.

    Returns:
        RedisSettings ready for the worker to use.
    """
    parsed = RedisSettings.from_dsn(_settings.redis_url)
    parsed.conn_timeout = _CONNECT_TIMEOUT_SECONDS
    return parsed


async def startup(ctx: dict) -> None:
    """Announce which queue the worker is consuming.

    Without this line a queue-name mismatch between BE and AGENT looks identical
    to an idle system: jobs are enqueued, nothing errors, and nothing runs.

    Args:
        ctx: arq worker context. Unused.

    Side effects:
        Writes one log line.
    """
    logger.info(
        "AGENT worker ready: queue=%s redis=%s",
        _settings.agent_queue_name,
        _settings.redis_url,
    )


class WorkerSettings:
    """arq worker configuration.

    The task is registered under the constant from `contracts` rather than under
    the Python function name, so renaming the function cannot silently break
    BE's enqueue call.
    """

    functions = [
        func(draft_assessment, name=DRAFT_ASSESSMENT_TASK),
        func(generate_retry_question, name=GENERATE_RETRY_QUESTION_TASK),
        func(explain, name=EXPLAIN_TURN_TASK),
        # Legacy, superseded by ADR-20. Registered so an old client does not
        # hang forever on a task nothing consumes.
        func(grade_submission, name=GRADE_SUBMISSION_TASK),
    ]
    queue_name = _settings.agent_queue_name
    redis_settings = _redis_settings()
    keep_result = _settings.job_result_ttl_seconds
    on_startup = startup
