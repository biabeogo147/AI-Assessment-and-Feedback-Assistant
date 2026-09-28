"""The one module in AGENT that knows whose model is answering.

Every handler asks for a runnable and writes prompts against it. None of them
names OpenAI, Gemini or anyone else, so swapping provider is two lines in `.env`
rather than a change spread across three handlers. That is also what makes the
test suite free: a test replaces the builder here and nothing touches a network.

Two things in here are easy to get wrong and expensive to debug:

**The credential is passed, not inherited.** `init_chat_model` reads
`OPENAI_API_KEY` from the process environment, but this project loads `.env`
into a `Settings` object instead, which never reaches `os.environ`. Leave the
key out of the call and the model authenticates as nobody.

**Fallbacks wrap last.** `Runnable.with_fallbacks` returns a
`RunnableWithFallbacks`, and that class has no `with_structured_output` --
it is a chat model's method, not a runnable's. So the transform is applied to
each model first and the fallback chain is built around the results. Build it
the other way round and structured output disappears the moment a second
provider is configured.
"""

from collections.abc import Callable
from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable

from agent.config import Settings, get_settings

# Which setting holds the credential for which provider. A provider missing
# from here can still be configured; it just has to find its credential the way
# its own SDK does.
_CREDENTIAL = {
    "openai": "openai_api_key",
    "google_genai": "google_api_key",
}


class ModelNotConfigured(RuntimeError):
    """Calling a model was asked for, and nothing says which one."""


def enabled() -> bool:
    """Whether handlers should call a real model at all.

    Returns:
        True when `LLM_ENABLED` is on and a model id is set. A missing id
        counts as off rather than as an error, so a half-filled `.env` demos
        with prepared content instead of failing every job.
    """
    settings = get_settings()
    return settings.llm_enabled and bool(settings.llm_model)


def _build(settings: Settings, provider: str, model: str) -> BaseChatModel:
    """Construct one chat model.

    Args:
        settings: Process settings holding credentials and the call timeout.
        provider: Provider name LangChain understands, e.g. "openai".
        model: Model id at that provider.

    Returns:
        A chat model ready to call.

    Raises:
        ModelNotConfigured: If the provider needs a credential this process
            does not have. Failing here beats failing inside a job, where the
            reason arrives wrapped in a queue error.
    """
    extra: dict[str, object] = {"timeout": settings.llm_timeout_seconds}

    attribute = _CREDENTIAL.get(provider)
    if attribute is not None:
        credential = getattr(settings, attribute)
        if not credential:
            raise ModelNotConfigured(f"provider {provider!r} has no credential in this process")
        extra["api_key"] = credential

    return init_chat_model(model, model_provider=provider, **extra)


@lru_cache(maxsize=1)
def chat_models() -> tuple[BaseChatModel, ...]:
    """Every configured model, the one to try first at the front.

    Returns:
        One model, or two when a fallback provider is configured. Cached for
        the life of the worker: building a client per job would open a
        connection pool per job.

    Raises:
        ModelNotConfigured: If no model id is set, or a credential is missing.
    """
    settings = get_settings()
    if not settings.llm_model:
        raise ModelNotConfigured("LLM_MODEL is empty; nothing says which model to call")

    models = [_build(settings, settings.llm_provider, settings.llm_model)]
    if settings.llm_fallback_provider and settings.llm_fallback_model:
        models.append(_build(settings, settings.llm_fallback_provider, settings.llm_fallback_model))
    return tuple(models)


def with_fallback(shape: Callable[[BaseChatModel], Runnable]) -> Runnable:
    """Apply one transform to every configured model and chain them.

    `shape` is where `with_structured_output` goes. It runs against each model
    separately so the fallback chain is built from already-shaped runnables --
    see the module docstring for why the other order silently loses structured
    output.

    Args:
        shape: Turns a chat model into the runnable a handler wants. Identity
            is a fine answer when the handler just wants text.

    Returns:
        The first model's runnable, with the rest behind it as fallbacks. With
        one model configured, the runnable itself -- no wrapper, so streaming
        keeps whatever the provider gives it.
    """
    shaped = [shape(model) for model in chat_models()]
    if len(shaped) == 1:
        return shaped[0]
    return shaped[0].with_fallbacks(shaped[1:])
