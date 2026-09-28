"""AGENT configuration, read from the environment.

Note what is absent: no database URL. AGENT holds no persistence credentials,
so a submission must arrive carrying everything needed to grade it.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchored to the repository root rather than left relative to the working
# directory. Relative, it silently resolves to nothing when a process starts
# from its own service folder -- and a missing .env is not an error, it is a
# full set of defaults. The symptom is the worst kind: a key that is not there,
# a switch that stays off, and no message anywhere saying so.
_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    """Runtime settings for the AGENT worker.

    Attributes:
        redis_url: Connection string for the Redis instance shared with BE.
        agent_queue_name: Queue to consume from. Must match BE's value or the
            worker idles while jobs pile up somewhere else.
        job_result_ttl_seconds: How long a finished result stays readable by BE.
        llm_enabled: Whether handlers call a real model. False keeps the
            prepared content, which is what every test runs against and what a
            demo falls back to when no key is configured.
        llm_provider: Provider name LangChain understands, e.g. "openai".
        llm_model: Model id at that provider. No default worth having: a wrong
            id is a failed call, so this must be set deliberately.
        openai_api_key: Credential for the OpenAI provider.
        google_api_key: Credential for the Gemini provider. Empty means the
            fallback chain has nowhere to fall, which is allowed.
        llm_fallback_provider: Provider tried when the first one raises.
        llm_fallback_model: Model id at the fallback provider.
        llm_timeout_seconds: Ceiling on one model call.
        llm_max_attempts: How many times one job may ask the model before
            giving up. It lives here rather than beside the loop it governs
            because BE's patience for a job has to cover all of them, and
            `tools/check_contract.py` can only check that if it can read the
            number.
    """

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    redis_url: str = "redis://127.0.0.1:6379/0"
    agent_queue_name: str = "aiafa:grading"
    job_result_ttl_seconds: int = 3600

    llm_enabled: bool = False
    llm_provider: str = "openai"
    llm_model: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    llm_fallback_provider: str = ""
    llm_fallback_model: str = ""
    llm_timeout_seconds: int = 20
    llm_max_attempts: int = 3


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance.

    Returns:
        A cached Settings object, so the .env file is read once per process.
    """
    return Settings()
