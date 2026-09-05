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
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://127.0.0.1:6379/0"
    agent_queue_name: str = "aiafa:grading"
    job_result_ttl_seconds: int = 3600
    review_confidence_threshold: float = 0.7


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance.

    Returns:
        A cached Settings object, so the .env file is read once per process.
    """
    return Settings()
