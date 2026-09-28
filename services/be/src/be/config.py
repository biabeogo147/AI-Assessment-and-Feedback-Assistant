"""BE configuration, read from the environment.

Every value here has a matching entry in .env.example. Nothing in BE is allowed
to hardcode a host, port, queue name or threshold.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the BE process.

    Attributes:
        redis_url: Connection string for the Redis instance arq shares with AGENT.
        agent_queue_name: Queue both sides agree on. Must match AGENT's value or
            jobs are enqueued where nothing is listening.
        job_result_ttl_seconds: How long arq keeps a result readable after the
            job finishes.
        review_confidence_threshold: Confidence at or below which a graded
            submission is routed to the Teacher Review Queue. Owned by BE.
        database_url: Async SQLAlchemy URL for the store that holds attempt
            state. ADR-21 makes that state durable, so this is not optional in
            any environment where a student can come back tomorrow.
        dev_identity_header: Name of the header standing in for a login while
            no sign-in screen exists. Requests name themselves as
            "student:<code>" or "teacher:<code>".
        dev_identity_enabled: Whether that header is honoured. False is the
            safe value; the plan that introduced it requires the real sign-in
            to flip this off for good.
        agent_job_timeout_seconds: How long BE waits for an AGENT job before
            giving up on it.
        stream_first_chunk_timeout_seconds: How long the chat stream waits for
            the assistant's first piece of text before giving up on streaming
            and replaying the finished answer instead. Only the *first* piece
            is on this clock: once text has gone out, replaying would show the
            student the same half-sentence twice.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://127.0.0.1:6379/0"
    agent_queue_name: str = "aiafa:grading"
    job_result_ttl_seconds: int = 3600
    review_confidence_threshold: float = 0.7
    database_url: str = "postgresql+asyncpg://aiafa:aiafa@127.0.0.1:5432/aiafa"
    dev_identity_header: str = "X-Actor"
    dev_identity_enabled: bool = True
    agent_job_timeout_seconds: int = 30
    stream_first_chunk_timeout_seconds: float = 8.0


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance.

    Returns:
        A cached Settings object, so the .env file is read once per process.
    """
    return Settings()
