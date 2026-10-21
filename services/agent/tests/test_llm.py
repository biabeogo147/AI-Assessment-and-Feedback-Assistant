"""Hành vi của chính cái adapter, kể cả sai lầm mà nó tồn tại để ngăn.

`agent/llm.py` là chỗ nối mọi handler sẽ tựa vào từ pha sau trở đi, và hai quyết định của
nó không nhìn thấy được từ chỗ gọi: rằng một model duy nhất đã cấu hình được trả lại mà
không bọc gì, và rằng chuỗi fallback được dựng từ những runnable đã shape xong. Cả hai đều
thuộc loại thứ mà một lần dọn dẹp về sau "làm cho gọn" là mất. Các test này làm cho việc đó
đắt.
"""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel

from agent import llm
from agent.config import Settings

# Bắt lấy trước khi fixture autouse trong conftest.py thay nó, để các test này chạy được
# qua builder thật thay vì qua bản đóng thế.
REAL_CHAT_MODELS = llm.chat_models


class Shape(BaseModel):
    """Đóng thế cho một schema của structured output."""

    value: int


class StructuredFake(GenericFakeChatModel):
    """Một fake có trả lời `with_structured_output`, điều bản có sẵn không làm.

    `GenericFakeChatModel.with_structured_output` raise NotImplementedError, nên bản fake có
    sẵn không chạy qua được cái luật thứ tự mà module này dựa vào.
    """

    def with_structured_output(self, schema, **kwargs) -> Runnable:  # noqa: ANN001, ARG002
        """Trả về một runnable đóng thế cho một model bị ràng buộc bởi schema."""
        return RunnableLambda(lambda _: Shape(value=1))


def _fake() -> StructuredFake:
    """Một chat model giả với nguồn câu trả lời vô tận."""
    return StructuredFake(messages=iter(["xin chào"] * 100))


def test_a_single_model_is_handed_back_unwrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Một provider nghĩa là không có lớp bọc fallback nào cả.

    Bọc một model đơn độc chẳng được gì và sẽ đặt `RunnableWithFallbacks` vào giữa handler và
    hành vi stream của chính provider.
    """
    only = _fake()
    monkeypatch.setattr(llm, "chat_models", lambda: (only,))

    assert llm.with_fallback(lambda model: model) is only


def test_structured_output_survives_a_second_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Việc shape diễn ra trên từng model, nên một chuỗi fallback vẫn giữ structured output.

    Đây là toàn bộ lý do `with_fallback` nhận một callable thay vì trả về một model: xem
    docstring của module trong `agent/llm.py`.
    """
    monkeypatch.setattr(llm, "chat_models", lambda: (_fake(), _fake()))

    shaped = llm.with_fallback(lambda model: model.with_structured_output(Shape))

    assert shaped.invoke("bất kỳ") == Shape(value=1)


def test_the_shape_reaches_every_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mỗi model đã cấu hình đều tự được shape, không chỉ model đầu tiên.

    Đây là hợp đồng giữ cho kết quả độc lập với phần reflection trên type hint của
    `RunnableWithFallbacks.__getattr__`. Shape cả chuỗi thay vì shape từng thành viên của nó
    thì hôm nay tình cờ vẫn chạy, nhưng nó chạy nhờ introspection, và introspection đó thất
    bại một cách không đọc hiểu được khi một annotation không resolve -- xem docstring của
    module trong `agent/llm.py`.
    """
    shaped: list[object] = []
    monkeypatch.setattr(llm, "chat_models", lambda: (_fake(), _fake()))

    def shape(model: object) -> Runnable:
        shaped.append(model)
        return RunnableLambda(lambda _: Shape(value=1))

    llm.with_fallback(shape)

    assert len(shaped) == 2


def test_no_model_id_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Một `LLM_MODEL` rỗng thì thất bại ở chỗ lý do còn đọc được."""
    monkeypatch.setattr(llm, "chat_models", REAL_CHAT_MODELS)
    monkeypatch.setattr(llm, "get_settings", lambda: Settings(llm_model=""))
    REAL_CHAT_MODELS.cache_clear()

    with pytest.raises(llm.ModelNotConfigured, match="LLM_MODEL"):
        llm.chat_models()

    REAL_CHAT_MODELS.cache_clear()


def test_a_provider_without_its_credential_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Thiếu key thì thất bại lúc dựng, không phải bên trong một job đã vào queue.

    Bên trong một job thì lý do tới kèm trong một lỗi queue, cách người sửa được nó một
    service.
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
    """Một `.env` điền nửa vời thì demo bằng nội dung dọn trước thay vì thất bại.

    Args:
        monkeypatch: Bộ patch của pytest.
        enabled: `LLM_ENABLED` nói gì.
        model: `LLM_MODEL` nói gì.
        expected: Handler có nên gọi một model thật hay không.
    """
    monkeypatch.setattr(llm, "get_settings", lambda: Settings(llm_enabled=enabled, llm_model=model))

    assert llm.enabled() is expected


def _isolated(**settings: object) -> Settings:
    """Settings chỉ từ tham số: không đọc `.env` thật, không có fallback nào lọt vào.

    `.env` của máy dev đổi theo lần thử tay (`claude-provider-option` đợt 4); một `LLM_FALLBACK_*`
    đặt ở đó làm `chat_models` dựng hai model, và test đọc nhầm tham số của model thứ hai.
    """
    fields: dict[str, object] = {"llm_fallback_provider": "", "llm_fallback_model": ""}
    fields.update(settings)
    return Settings(_env_file=None, **fields)


def _built_with(monkeypatch: pytest.MonkeyPatch, **settings: object) -> dict[str, object]:
    """Dựng model thật qua `chat_models`, nhưng bắt lấy tham số thay vì dựng client.

    Args:
        monkeypatch: Bộ patch của pytest.
        **settings: Các setting của lần dựng.

    Returns:
        Provider và mọi tham số `init_chat_model` nhận được.
    """
    seen: dict[str, object] = {}

    def capture(model: str, **kwargs: object) -> object:
        seen.update(kwargs, model=model)
        return _fake()

    monkeypatch.setattr(llm, "chat_models", REAL_CHAT_MODELS)
    monkeypatch.setattr(llm, "init_chat_model", capture)
    monkeypatch.setattr(llm, "get_settings", lambda: _isolated(**settings))
    REAL_CHAT_MODELS.cache_clear()
    llm.chat_models()
    REAL_CHAT_MODELS.cache_clear()
    return seen


def test_claude_gets_its_key_and_its_thinking_and_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    """`LLM_PROVIDER=anthropic` lấy `CLAUDE_API_KEY`, kèm thinking và effort của `.env`.

    Key truyền vào, không thừa hưởng: `.env` không bao giờ tới `os.environ`, nên SDK tự tìm
    `ANTHROPIC_API_KEY` thì không thấy gì (docstring của `agent/llm.py`).
    """
    seen = _built_with(
        monkeypatch,
        llm_provider="anthropic",
        llm_model="claude-haiku-5-5",
        claude_api_key="claude-key",
        openai_api_key="openai-key",
        llm_thinking="disabled",
        llm_effort="low",
    )

    assert seen["model_provider"] == "anthropic"
    assert seen["api_key"] == "claude-key"
    assert seen["thinking"] == {"type": "disabled"}
    assert seen["effort"] == "low"


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_the_sdk_never_retries_on_its_own(monkeypatch: pytest.MonkeyPatch, provider: str) -> None:
    """Tier 2 câu 14 = A (21/10/2026): SDK tự thử lại hai lần thì một job tính đủ là
    3 + 20 × 3 × 3 = 183 s, vượt 70 s BE chờ, mà check `timeout-order` không thấy. Chỉ AGENT thử
    lại (`LLM_MAX_ATTEMPTS`), nên phép tính của check là phép tính thật."""
    seen = _built_with(
        monkeypatch,
        llm_provider=provider,
        llm_model="m",
        claude_api_key="claude-key",
        openai_api_key="openai-key",
    )
    assert seen["max_retries"] == 0


def test_claude_without_its_key_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Có key OpenAI mà thiếu key Claude thì vẫn từ chối: mỗi provider một key."""
    monkeypatch.setattr(llm, "chat_models", REAL_CHAT_MODELS)
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: _isolated(
            llm_provider="anthropic",
            llm_model="claude-haiku-5-5",
            openai_api_key="openai-key",
            claude_api_key="",
        ),
    )
    REAL_CHAT_MODELS.cache_clear()

    with pytest.raises(llm.ModelNotConfigured, match="anthropic"):
        llm.chat_models()

    REAL_CHAT_MODELS.cache_clear()


def test_openai_never_receives_claude_options(monkeypatch: pytest.MonkeyPatch) -> None:
    """`LLM_THINKING`, `LLM_EFFORT` để sẵn trong `.env` không lọt sang client OpenAI.

    Đổi qua lại hai provider chỉ là sửa `LLM_PROVIDER` và `LLM_MODEL`; một tham số lạ đi tới
    OpenAI là một lỗi ở mọi lời gọi.
    """
    seen = _built_with(
        monkeypatch,
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        openai_api_key="openai-key",
        llm_thinking="disabled",
        llm_effort="low",
    )

    assert seen["api_key"] == "openai-key"
    assert "thinking" not in seen
    assert "effort" not in seen


@pytest.mark.parametrize(("field", "value"), [("llm_effort", "lowest"), ("llm_thinking", "off")])
def test_an_unknown_claude_option_is_refused_when_settings_load(field: str, value: str) -> None:
    """Gõ sai hỏng lúc worker khởi động, không phải ở lời gọi model đầu tiên."""
    with pytest.raises(ValueError, match=field):
        _isolated(**{field: value})


def test_a_claude_fallback_gets_claude_options_and_the_openai_model_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chuỗi openai → anthropic: mỗi model nhận đúng tham số của provider nó."""
    built: list[dict[str, object]] = []

    def capture(model: str, **kwargs: object) -> object:
        built.append({**kwargs, "model": model})
        return _fake()

    monkeypatch.setattr(llm, "chat_models", REAL_CHAT_MODELS)
    monkeypatch.setattr(llm, "init_chat_model", capture)
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: _isolated(
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            openai_api_key="openai-key",
            llm_fallback_provider="anthropic",
            llm_fallback_model="claude-haiku-5-5",
            claude_api_key="claude-key",
            llm_thinking="disabled",
            llm_effort="low",
        ),
    )
    REAL_CHAT_MODELS.cache_clear()
    llm.chat_models()
    REAL_CHAT_MODELS.cache_clear()

    first, second = built
    assert "thinking" not in first and "effort" not in first
    assert (second["api_key"], second["thinking"], second["effort"]) == (
        "claude-key",
        {"type": "disabled"},
        "low",
    )


def test_the_real_claude_client_sends_thinking_off_and_low_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Qua `ChatAnthropic` thật -- key giả, không gọi mạng: payload mang đúng hai tham số.

    Test trên chỉ bắt tham số **trước** `init_chat_model`; langchain đổi tên alias `effort` thì chỉ
    test này đỏ. Và structured output phải còn ép tool: thinking bật thì langchain bỏ ép, model có
    thể không gọi tool, và `_Proposal` không parse được.
    """
    monkeypatch.setattr(llm, "chat_models", REAL_CHAT_MODELS)
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: _isolated(
            llm_provider="anthropic",
            llm_model="claude-haiku-5-5",
            claude_api_key="not-a-real-key",
            llm_thinking="disabled",
            llm_effort="low",
            llm_timeout_seconds=20,
        ),
    )
    REAL_CHAT_MODELS.cache_clear()
    (chat,) = llm.chat_models()
    REAL_CHAT_MODELS.cache_clear()

    payload = chat._get_request_payload([("human", "chào")])
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["output_config"]["effort"] == "low"
    assert chat.default_request_timeout == 20

    shaped = chat.with_structured_output(Shape)
    bound = shaped.first.kwargs
    assert bound["tool_choice"]["type"] == "tool"
