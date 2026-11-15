"""`bench_model`: một lượt bench đo đúng một model, chọn bằng cờ (plan `bench-two-models`)."""

import os

import pytest

import bench_model
from ocr_bench.run import task_code_in

_KEYS = (
    "LLM_ENABLED",
    "LLM_PROVIDER",
    "LLM_MODEL",
    "LLM_FALLBACK_PROVIDER",
    "LLM_FALLBACK_MODEL",
    "LLM_REASONING_EFFORT",
    "LLM_THINKING",
    "LLM_EFFORT",
    "LLM_TIMEOUT_SECONDS",
    "OPENAI_API_KEY",
    "CLAUDE_API_KEY",
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch):
    """Biến môi trường của lượt thử, trả lại như cũ sau test; settings và model không cache lại."""
    from agent import llm
    from agent.config import get_settings

    # Rỗng đè lên `.env` của máy dev (biến môi trường thắng tệp), nên test không đọc key thật.
    for key in _KEYS:
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "20")
    yield monkeypatch
    get_settings.cache_clear()
    llm.chat_models.cache_clear()


@pytest.mark.parametrize("spec", ["gpt-6-luna", "openai:", ":gpt-6-luna", "google:gemini"])
def test_a_spec_that_names_no_known_provider_and_model_stops_the_run(spec: str) -> None:
    with pytest.raises(SystemExit, match="--model"):
        bench_model.parse(spec)


def test_both_models_of_the_bench_parse_and_slug_into_names_without_a_task_code() -> None:
    assert bench_model.parse("openai:gpt-6-luna") == ("openai", "gpt-6-luna")
    assert bench_model.parse(" anthropic:claude-haiku-5-5 ") == ("anthropic", "claude-haiku-5-5")
    assert bench_model.slug("gpt-6-luna") == "gpt-6-luna"
    assert bench_model.slug("Some/Model_X") == "some-model-x"
    # Slug thành tên thư mục kết quả, sống lâu hơn plan: không được trông như mã task.
    assert task_code_in("exam-hai-model-gpt-6-luna") == ""
    assert task_code_in("exam-hai-model-claude-haiku-5-5") == ""


def test_pin_measures_one_model_with_the_env_options_of_its_own_provider(clean_env) -> None:
    clean_env.setenv("OPENAI_API_KEY", "not-a-real-key")
    clean_env.setenv("LLM_FALLBACK_PROVIDER", "anthropic")
    clean_env.setenv("LLM_FALLBACK_MODEL", "claude-haiku-5-5")
    clean_env.setenv("LLM_REASONING_EFFORT", "none")
    clean_env.setenv("LLM_THINKING", "disabled")
    clean_env.setenv("LLM_TIMEOUT_SECONDS", "20")

    pinned = bench_model.pin("openai:gpt-6-luna")

    from agent import llm
    from agent.config import get_settings

    settings = get_settings()
    assert (settings.llm_provider, settings.llm_model, settings.llm_enabled) == (
        "openai",
        "gpt-6-luna",
        True,
    )
    # Fallback rỗng: số đo nói đúng một model đã trả lời.
    assert os.environ["LLM_FALLBACK_PROVIDER"] == "" and len(llm.chat_models()) == 1
    assert pinned.slug == "gpt-6-luna"
    # Thinking của Claude không có mặt trong dòng cấu hình của một model OpenAI.
    assert pinned.config == "openai/gpt-6-luna · reasoning_effort none · trần 20 s"


def test_pin_replaces_a_model_pinned_earlier_in_the_same_process(clean_env) -> None:
    clean_env.setenv("OPENAI_API_KEY", "not-a-real-key")
    clean_env.setenv("CLAUDE_API_KEY", "not-a-real-key")
    clean_env.setenv("LLM_THINKING", "disabled")
    clean_env.setenv("LLM_EFFORT", "low")

    bench_model.pin("openai:gpt-6-luna")
    pinned = bench_model.pin("anthropic:claude-haiku-5-5")

    from agent.config import get_settings

    assert get_settings().llm_model == "claude-haiku-5-5"
    assert pinned.config.startswith("anthropic/claude-haiku-5-5 · thinking disabled · effort low")


def test_pin_without_the_providers_key_stops_before_any_call(clean_env) -> None:
    with pytest.raises(SystemExit, match="anthropic"):
        bench_model.pin("anthropic:claude-haiku-5-5")


# ------------------------------------------------------------- cổng trung gian (pha 5b)


def test_the_gateway_points_each_sdk_at_the_url_it_expects() -> None:
    """Stali: `…/v1` cho SDK OpenAI, gốc cho SDK Anthropic (tài liệu Stali); key của cổng thay key
    của provider."""
    values = {"STALI_API_KEY": "sk-stali-x", "STALI_ENDPOINT": "https://api.stali.test/v1/"}

    assert bench_model.gateway_env("stali", "openai", values) == {
        "OPENAI_BASE_URL": "https://api.stali.test/v1",
        "OPENAI_API_KEY": "sk-stali-x",
    }
    assert bench_model.gateway_env("stali", "anthropic", values) == {
        "ANTHROPIC_BASE_URL": "https://api.stali.test",
        "CLAUDE_API_KEY": "sk-stali-x",
    }
    assert bench_model.gateway_env("", "openai", values) == {}


@pytest.mark.parametrize(
    ("via", "values", "why"),
    [
        ("openrouter", {}, "--via"),
        ("stali", {"STALI_API_KEY": "k"}, "STALI_ENDPOINT"),
        ("stali", {"STALI_ENDPOINT": "https://x"}, "STALI_API_KEY"),
    ],
)
def test_an_unknown_gateway_or_a_missing_key_stops_before_any_call(
    via: str, values: dict, why: str
) -> None:
    with pytest.raises(SystemExit, match=why):
        bench_model.gateway_env(via, "openai", values)


def test_pin_through_the_gateway_builds_a_client_aimed_at_it(clean_env) -> None:
    """Không gọi mạng: client LangChain thật đọc `ANTHROPIC_BASE_URL` và key của cổng."""
    clean_env.setenv("STALI_API_KEY", "sk-stali-not-real")
    clean_env.setenv("STALI_ENDPOINT", "https://api.stali.test/v1")
    clean_env.setenv("ANTHROPIC_BASE_URL", "")
    clean_env.setenv("LLM_THINKING", "disabled")
    clean_env.setenv("LLM_EFFORT", "low")

    pinned = bench_model.pin("anthropic:claude-haiku-5-5", via="stali")

    from agent import llm

    (chat,) = llm.chat_models()
    assert chat.anthropic_api_url == "https://api.stali.test"
    assert chat.anthropic_api_key.get_secret_value() == "sk-stali-not-real"
    assert pinned.slug == "claude-haiku-5-5-stali" and pinned.config.endswith("qua stali")


@pytest.mark.parametrize(
    ("answer", "tokens", "why"),
    [
        ("KRIKY-PREFLIGHT-OK", 40, ""),
        ("KRIKY-PREFLIGHT-OK.", 40, ""),
        # Kiro qua kênh thường của Stali, 15/11/2026: ~4.700 token vào cho một câu ngắn.
        ("KRIKY-PREFLIGHT-OK", 4736, "prompt lạ"),
        # Kênh `req/`: system bị bỏ qua, model tự giới thiệu.
        ("I'm Claude, a large language model made by Anthropic.", 25, "system"),
        # Cổng không báo usage: không đo được, không coi là sạch (review pha 5b).
        ("KRIKY-PREFLIGHT-OK", 0, "không đo được"),
    ],
)
def test_the_preflight_stops_on_an_injected_prompt_or_a_dropped_system(
    answer: str, tokens: int, why: str
) -> None:
    verdict = bench_model.preflight_verdict(answer, tokens)
    assert (why in verdict) if why else verdict == ""


@pytest.mark.asyncio
async def test_a_direct_call_needs_no_preflight() -> None:
    """Gọi thẳng provider thì không ai chèn gì: không tốn lời gọi thử."""
    pinned = bench_model.Pinned("openai", "gpt-6-luna", "gpt-6-luna", "x")
    assert await bench_model.check_preflight(pinned) == ""


@pytest.mark.parametrize(
    "message",
    [
        "Error code: 402 - {'type': 'error', 'error': {'type': 'insufficient_balance'}}",
        "Your credit balance is too low to access the Anthropic API.",
        "Error code: 402 - {'type': 'billing_error', 'message': 'This request would exceed your "
        "available credits'}",
        "Error code: 429 - {'error': {'message': 'You exceeded your current quota', "
        "'type': 'insufficient_quota'}}",
    ],
)
def test_running_out_of_money_stops_the_whole_bench(message: str) -> None:
    """Pha 6b: ví Stali cạn giữa `propose_bench`, và 167/296 lượt còn lại thành lượt hỏng được ghi
    như lượt đo. Hết tiền thì dừng hẳn; lỗi khác vẫn là một lượt trượt."""

    class APIStatusError(Exception):
        pass

    with pytest.raises(SystemExit, match="hết tiền"):
        bench_model.stop_if_out_of_money(APIStatusError(message))
    bench_model.stop_if_out_of_money(APIStatusError("Error code: 529 - overloaded"))


def test_openrouter_takes_its_own_model_name_and_both_sdk_addresses(clean_env) -> None:
    """Dò 15/11/2026: OpenRouter nhận `/api/v1` cho SDK OpenAI và `/api` cho SDK Anthropic, và gọi
    Haiku là `anthropic/claude-haiku-5.5`; giá và tên thư mục vẫn theo tên gốc."""
    values = {"OPENROUTER_API_KEY": "sk-or-x"}
    assert bench_model.gateway_env("openrouter", "anthropic", values) == {
        "ANTHROPIC_BASE_URL": "https://openrouter.ai/api",
        "CLAUDE_API_KEY": "sk-or-x",
    }
    assert bench_model.gateway_env("openrouter", "openai", values)["OPENAI_BASE_URL"] == (
        "https://openrouter.ai/api/v1"
    )
    with pytest.raises(SystemExit, match="OPENROUTER_API_KEY"):
        bench_model.gateway_env("openrouter", "anthropic", {})
    with pytest.raises(SystemExit, match="tên OpenRouter"):
        bench_model.gateway_model("openrouter", "claude-opus-5-5")

    clean_env.setenv("OPENROUTER_API_KEY", "sk-or-not-real")
    clean_env.setenv("ANTHROPIC_BASE_URL", "")
    pinned = bench_model.pin("anthropic:claude-haiku-5-5", via="openrouter")

    from agent import llm

    (chat,) = llm.chat_models()
    assert chat.model == "anthropic/claude-haiku-5.5"
    assert chat.anthropic_api_url == "https://openrouter.ai/api"
    assert pinned.model == "claude-haiku-5-5" and pinned.slug == "claude-haiku-5-5-openrouter"
    assert pinned.config.startswith("anthropic/claude-haiku-5-5 ")
    assert pinned.config.endswith("qua openrouter (anthropic/claude-haiku-5.5)")
