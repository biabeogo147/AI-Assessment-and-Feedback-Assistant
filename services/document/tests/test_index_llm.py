"""Hai lời gọi model của document agent chọn được provider, và đọc đúng chữ của cả hai.

`claude-provider-option`: tóm tắt và banner mỗi cái một provider (`SUMMARY_PROVIDER`,
`BANNER_PROVIDER`), mỗi model cầm khoá của provider nó chọn. Claude trả `content` là một list block
-- `str()` của list ấy là chữ Python, không phải JSON banner hay câu tóm tắt. Không test nào chạm
mạng: `init_chat_model` bị thay bằng một hàm ghi lại tham số.
"""

import json

import pytest
from langchain_core.messages import AIMessage

from document.config import Settings
from document.index import llm


def _settings(**overrides: object) -> Settings:
    """Settings không đọc khoá nào từ `.env` thật của máy dev."""
    fields: dict[str, object] = {"openai_api_key": "", "claude_api_key": ""}
    fields.update(overrides)
    return Settings(_env_file=None, **fields)


@pytest.fixture
def built(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Tham số lần dựng model gần nhất, thay cho client thật."""
    seen: dict[str, object] = {}

    def capture(model: str, **kwargs: object) -> object:
        seen.clear()
        seen.update(kwargs, model=model)
        return object()

    monkeypatch.setattr(llm, "init_chat_model", capture)
    return seen


def test_claude_takes_its_own_key_and_options(built: dict[str, object]) -> None:
    settings = _settings(
        openai_api_key="openai-key",
        claude_api_key="claude-key",
        llm_thinking="disabled",
        llm_effort="low",
    )

    assert (
        llm.model_for(settings, "anthropic", "claude-haiku-5-5", reasoning_effort="low") is not None
    )
    assert built["model_provider"] == "anthropic"
    assert built["api_key"] == "claude-key"
    assert built["thinking"] == {"type": "disabled"}
    assert built["effort"] == "low"
    # `reasoning_effort` là của OpenAI (luna); Claude không nhận nó.
    assert "reasoning_effort" not in built


def test_openai_keeps_luna_effort_and_never_gets_claude_options(built: dict[str, object]) -> None:
    settings = _settings(openai_api_key="openai-key", llm_thinking="disabled", llm_effort="low")

    assert llm.model_for(settings, "openai", "gpt-5.6-luna", reasoning_effort="low") is not None
    assert built["model_provider"] == "openai"
    assert built["api_key"] == "openai-key"
    assert built["reasoning_effort"] == "low"
    assert "thinking" not in built
    assert "effort" not in built


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_a_missing_key_turns_off_only_that_model(provider: str, built: dict[str, object]) -> None:
    other = "claude_api_key" if provider == "openai" else "openai_api_key"
    settings = _settings(**{other: "the-other-key"})

    assert llm.model_for(settings, provider, "any-model") is None
    assert built == {}


def test_an_unknown_provider_is_refused_when_settings_load() -> None:
    with pytest.raises(ValueError, match="summary_provider"):
        _settings(summary_provider="gemini")


class _Answers:
    """Một model trả đúng một message xếp sẵn."""

    def __init__(self, message: AIMessage) -> None:
        self.message = message

    async def ainvoke(self, _messages: object) -> AIMessage:
        return self.message


def _blocks(text: str) -> AIMessage:
    """Câu trả lời dạng Claude: `content` là list block, kèm usage."""
    return AIMessage(
        content=[{"type": "text", "text": text}],
        usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
    )


@pytest.mark.asyncio
async def test_a_banner_answered_in_blocks_is_read() -> None:
    said = json.dumps(
        {"la_mo_dau": True, "loai": "chương", "so": "I", "ten": "TẬP HỢP CÁC SỐ TỰ NHIÊN"},
        ensure_ascii=False,
    )

    read = await llm.read_banner(_Answers(_blocks(said)), b"png")

    assert (read.is_opening, read.number, read.title) == (True, "I", "TẬP HỢP CÁC SỐ TỰ NHIÊN")
    assert read.tokens == 120


@pytest.mark.asyncio
async def test_a_summary_answered_in_blocks_is_the_text_itself() -> None:
    summary = await llm.summarise(_Answers(_blocks("  Bài dạy tập hợp.  ")), "Bài 1", "chữ")

    assert summary.text == "Bài dạy tập hợp."


@pytest.mark.asyncio
async def test_a_summary_answered_as_a_plain_string_is_unchanged() -> None:
    """Đường OpenAI: `content` là chuỗi, và `.text` trả đúng chuỗi ấy như `str()` trước đây."""
    answer = AIMessage(content="  Bài dạy phép cộng.  ")

    summary = await llm.summarise(_Answers(answer), "Bài 4", "chữ")

    assert summary.text == "Bài dạy phép cộng."
