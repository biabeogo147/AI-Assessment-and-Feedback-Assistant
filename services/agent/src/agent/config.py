"""AGENT configuration, read from the environment.

Note what is absent: no database URL. AGENT holds no persistence credentials,
so a submission must arrive carrying everything needed to grade it.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the AGENT worker.

    Attributes:
        redis_url: Connection string for the Redis instance shared with BE.
        agent_queue_name: Queue to consume from. Must match BE's value or the
            worker idles while jobs pile up somewhere else.
        job_result_ttl_seconds: How long a finished result stays readable by BE.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://127.0.0.1:6379/0"
    agent_queue_name: str = "aiafa:grading"
    job_result_ttl_seconds: int = 3600


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance.

    Returns:
        A cached Settings object, so the .env file is read once per process.
    """
    return Settings()
