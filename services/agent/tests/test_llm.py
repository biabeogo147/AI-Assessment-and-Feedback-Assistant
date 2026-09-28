"""The adapter's own behaviour, including the mistake it exists to prevent.

`agent/llm.py` is the seam every handler will lean on from the next phase
onward, and two of its decisions are invisible at the call site: that a single
configured model is handed back unwrapped, and that the fallback chain is built
from already-shaped runnables. Both are the kind of thing a later tidy-up
"simplifies" away. These tests make that expensive.
"""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel

from agent import llm
from agent.config import Settings

# Captured before the autouse fixture in conftest.py replaces it, so these
# tests can exercise the real builder instead of the stand-in.
REAL_CHAT_MODELS = llm.chat_models


class Shape(BaseModel):
    """Stand-in for a structured-output schema."""

    value: int


class StructuredFake(GenericFakeChatModel):
    """A fake that answers `with_structured_output`, which the stock one does not.

    `GenericFakeChatModel.with_structured_output` raises NotImplementedError, so
    the stock fake cannot exercise the ordering rule this module turns on.
    """

    def with_structured_output(self, schema, **kwargs) -> Runnable:  # noqa: ANN001, ARG002
        """Return a runnable standing in for a schema-constrained model."""
        return RunnableLambda(lambda _: Shape(value=1))


def _fake() -> StructuredFake:
    """One fake chat model with an endless supply of answers."""
    return StructuredFake(messages=iter(["xin chào"] * 100))


def test_a_single_model_is_handed_back_unwrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """One provider means no fallback wrapper at all.

    Wrapping a lone model would buy nothing and would put
    `RunnableWithFallbacks` between the handler and the provider's own
    streaming behaviour.
    """
    only = _fake()
    monkeypatch.setattr(llm, "chat_models", lambda: (only,))

    assert llm.with_fallback(lambda model: model) is only


def test_structured_output_survives_a_second_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shaping happens per model, so a fallback chain keeps structured output.

    This is the whole reason `with_fallback` takes a callable instead of
    returning a model: see the module docstring in `agent/llm.py`.
    """
    monkeypatch.setattr(llm, "chat_models", lambda: (_fake(), _fake()))

    shaped = llm.with_fallback(lambda model: model.with_structured_output(Shape))

    assert shaped.invoke("bất kỳ") == Shape(value=1)


def test_the_shape_reaches_every_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each configured model is shaped itself, not just the first one.

    This is the contract that keeps the result independent of
    `RunnableWithFallbacks.__getattr__`'s type-hint reflection. Shaping the
    chain instead of its members happens to work today, but it works by
    introspection that fails unreadably when an annotation does not resolve --
    see the module docstring in `agent/llm.py`.
    """
    shaped: list[object] = []
    monkeypatch.setattr(llm, "chat_models", lambda: (_fake(), _fake()))

    def shape(model: object) -> Runnable:
        shaped.append(model)
        return RunnableLambda(lambda _: Shape(value=1))

    llm.with_fallback(shape)

    assert len(shaped) == 2


def test_no_model_id_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty `LLM_MODEL` fails where the reason is still readable."""
    monkeypatch.setattr(llm, "chat_models", REAL_CHAT_MODELS)
    monkeypatch.setattr(llm, "get_settings", lambda: Settings(llm_model=""))
    REAL_CHAT_MODELS.cache_clear()

    with pytest.raises(llm.ModelNotConfigured, match="LLM_MODEL"):
        llm.chat_models()

    REAL_CHAT_MODELS.cache_clear()


def test_a_provider_without_its_credential_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing key fails at build time, not inside a queued job.

    Inside a job the reason arrives wrapped in a queue error, one service away
    from the person who can fix it.
    """
    monkeypatch.setattr(llm, "chat_models", REAL_CHAT_MODELS)
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: Settings(llm_model="anything", llm_provider="openai", openai_api_key=""),
    )
    REAL_CHAT_MODELS.cache_clear()

    with pytest.raises(llm.ModelNotConfigured, match="credential"):
        llm.chat_models()

    REAL_CHAT_MODELS.cache_clear()


@pytest.mark.parametrize(
    ("enabled", "model", "expected"),
    [
        (True, "gpt-x", True),
        (True, "", False),
        (False, "gpt-x", False),
    ],
)
def test_enabled_needs_both_a_switch_and_a_model(
    monkeypatch: pytest.MonkeyPatch, enabled: bool, model: str, expected: bool
) -> None:
    """A half-filled `.env` demos with prepared content instead of failing.

    Args:
        monkeypatch: pytest's patcher.
        enabled: What `LLM_ENABLED` says.
        model: What `LLM_MODEL` says.
        expected: Whether handlers should call a real model.
    """
    monkeypatch.setattr(llm, "get_settings", lambda: Settings(llm_enabled=enabled, llm_model=model))

    assert llm.enabled() is expected
