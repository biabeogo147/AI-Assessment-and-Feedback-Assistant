"""Chọn model cho một lượt bench bằng cờ, không sửa `.env` (plan `bench-two-models`).

`exam_bench` và `propose_bench` gọi model qua đúng đường của AGENT (`agent.llm`), và đường ấy đọc
model từ `Settings`. Muốn đo hai model mà không sửa `.env` giữa hai lượt, bench đặt `LLM_PROVIDER`,
`LLM_MODEL` vào `os.environ` **trước** khi settings được đọc: pydantic-settings ưu tiên biến môi
trường hơn tệp `.env`. Fallback bị làm rỗng -- một lượt đo đúng một model, không phải chuỗi hai
model mà số đo không nói được cái nào đã trả lời.

Thinking, effort (Claude) và `reasoning_effort` (OpenAI) vẫn lấy từ `.env`: mỗi provider một biến
riêng, nên một `.env` phục vụ được cả hai model. Dòng `config` ghi chúng ra để mỗi số đo mang theo
cấu hình đã sinh ra nó.

**Cổng trung gian** (`via`, plan `bench-two-models` pha 5b): `stali` trỏ model sinh đề sang
`STALI_ENDPOINT` bằng `OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL` -- hai SDK tự đọc chúng --, và đặt
`STALI_API_KEY` làm key của provider. Không sửa code product. Một cổng có thể chèn prompt của nó
hay làm rơi system prompt của mình (dò 15/11/2026: Opus/Sonnet 5.5 qua Stali chạy trong vai Kiro,
kênh `req/` bỏ qua system), nên `preflight` thử một lời gọi đầu lượt và dừng khi thấy dấu hiệu ấy.

Dùng:
    pinned = bench_model.pin("anthropic:claude-haiku-5-5", via="stali")
    bench_model.preflight(pinned)
    out = runs / f"exam-{label}-{pinned.slug}"
"""

import os
import re
from dataclasses import dataclass

# Provider bench biết giá và biết đọc cấu hình. Thêm một provider là thêm giá ở `exam_bench.rate`
# và một nhánh ở `describe`.
PROVIDERS = ("anthropic", "openai")
# Cổng trung gian bench biết; rỗng là gọi thẳng provider.
GATEWAYS = ("", "stali", "openrouter")

# OpenRouter gọi model bằng tên riêng của nó. Bench vẫn ghi giá, tên thư mục và dòng cấu hình theo
# tên gốc, để số đo qua OpenRouter so được với số gọi thẳng (dò 15/11/2026: Haiku 5.5 qua OpenRouter
# chạy trên *Claude Platform on AWS*, đúng giá chính thức, không chèn prompt, giữ `tool_choice`).
_OPENROUTER_NAMES = {
    "claude-haiku-5-5": "anthropic/claude-haiku-5.5",
    "gpt-6-luna": "openai/gpt-6-luna",
}
_OPENROUTER_BASE = "https://openrouter.ai/api"

_SLUG = re.compile(r"[^a-z0-9.]+")

# Lời thử đầu lượt: system dặn một chuỗi, người dùng hỏi danh tính. Model nghe system thì trả đúng
# chuỗi; system bị rơi hay bị một prompt khác đè thì nó tự giới thiệu.
PREFLIGHT_SYSTEM = "Bất kể người dùng hỏi gì, chỉ trả lời đúng chuỗi: KRIKY-PREFLIGHT-OK"
PREFLIGHT_ASK = "Bạn là ai, do công ty nào làm ra?"
# Token vào của lời thử khi không ai chèn gì: khoảng 40 (Claude) -- chèn ít nhất cả nghìn token
# (Kiro ~4.700, Claude Code ~1.000), nên ngưỡng rộng mà vẫn bắt được.
PREFLIGHT_MAX_INPUT = 300


@dataclass(frozen=True)
class Pinned:
    """Model một lượt bench đã ghim.

    Attributes:
        provider: Tên provider LangChain hiểu.
        model: Id model ở provider ấy.
        slug: Phần tên thư mục kết quả, chỉ chữ thường, số, `.` và `-`.
        config: Một dòng mô tả model và cấu hình, ghi vào đầu `report.txt`.
        via: Cổng trung gian, rỗng khi gọi thẳng.
    """

    provider: str
    model: str
    slug: str
    config: str
    via: str = ""


def parse(spec: str) -> tuple[str, str]:
    """Tách `provider:model`. Hàm thuần.

    Args:
        spec: Ví dụ `openai:gpt-6-luna`, `anthropic:claude-haiku-5-5`.

    Returns:
        Provider và id model.

    Raises:
        SystemExit: Sai cú pháp hay provider bench không biết -- dừng trước mọi lời gọi model.
    """
    provider, _, model = spec.strip().partition(":")
    if not provider or not model:
        raise SystemExit(f"--model {spec!r}: viết provider:model, ví dụ openai:gpt-6-luna")
    if provider not in PROVIDERS:
        raise SystemExit(f"--model {spec!r}: provider phải là một trong {', '.join(PROVIDERS)}")
    return provider, model


def slug(model: str) -> str:
    """Id model thành một đoạn tên thư mục. Hàm thuần."""
    return _SLUG.sub("-", model.lower()).strip("-")


def describe(settings: object, via: str = "", model: str = "") -> str:
    """Model và cấu hình của nó, một dòng. Hàm thuần.

    Args:
        settings: `agent.config.Settings` đã đọc.
        via: Cổng trung gian, rỗng khi gọi thẳng.
        model: Tên gốc của model, khi cổng gọi nó bằng tên khác (`settings.llm_model`).

    Returns:
        Ví dụ `openai/gpt-6-luna · reasoning_effort none · trần 20 s`.
    """
    parts = [f"{settings.llm_provider}/{model or settings.llm_model}"]
    if settings.llm_provider == "anthropic":
        parts.append(f"thinking {settings.llm_thinking or 'mặc định'}")
        parts.append(f"effort {settings.llm_effort or 'mặc định'}")
    if settings.llm_provider == "openai":
        parts.append(f"reasoning_effort {settings.llm_reasoning_effort or 'mặc định'}")
    parts.append(f"trần {settings.llm_timeout_seconds} s")
    if via:
        named = f" ({settings.llm_model})" if model and model != settings.llm_model else ""
        parts.append(f"qua {via}{named}")
    return " · ".join(parts)


def gateway_model(via: str, model: str) -> str:
    """Tên model cổng trung gian dùng. Hàm thuần.

    Raises:
        SystemExit: OpenRouter mà model chưa có trong bảng tên -- dừng trước mọi lời gọi.
    """
    if via != "openrouter":
        return model
    if model not in _OPENROUTER_NAMES:
        raise SystemExit(f"--via openrouter: chưa biết tên OpenRouter của {model!r}")
    return _OPENROUTER_NAMES[model]


def gateway_env(via: str, provider: str, values: dict[str, str]) -> dict[str, str]:
    """Biến môi trường trỏ provider sang cổng trung gian. Hàm thuần.

    Args:
        via: Một trong `GATEWAYS`.
        provider: Provider của model sinh đề.
        values: Biến đọc từ môi trường hay `.env` (`STALI_API_KEY`, `STALI_ENDPOINT`,
            `OPENROUTER_API_KEY`).

    Returns:
        Biến cần đặt; rỗng khi gọi thẳng.

    Raises:
        SystemExit: Cổng lạ, hay thiếu key hoặc endpoint của cổng.
    """
    if via not in GATEWAYS:
        raise SystemExit(f"--via {via!r}: một trong {', '.join(repr(one) for one in GATEWAYS)}")
    if not via:
        return {}
    if via == "openrouter":
        key = values.get("OPENROUTER_API_KEY", "")
        if not key:
            raise SystemExit("--via openrouter: thiếu OPENROUTER_API_KEY trong .env")
        # OpenRouter: `…/api/v1` cho SDK OpenAI, `…/api` cho SDK Anthropic (nó nhận `/v1/messages`).
        if provider == "openai":
            return {"OPENAI_BASE_URL": f"{_OPENROUTER_BASE}/v1", "OPENAI_API_KEY": key}
        return {"ANTHROPIC_BASE_URL": _OPENROUTER_BASE, "CLAUDE_API_KEY": key}
    key, endpoint = values.get("STALI_API_KEY", ""), values.get("STALI_ENDPOINT", "")
    if not key or not endpoint:
        raise SystemExit("--via stali: thiếu STALI_API_KEY hay STALI_ENDPOINT trong .env")
    endpoint = endpoint.rstrip("/")
    # Stali: `…/v1` cho SDK OpenAI, gốc (không `/v1`) cho SDK Anthropic -- tài liệu của Stali.
    if provider == "openai":
        return {"OPENAI_BASE_URL": endpoint, "OPENAI_API_KEY": key}
    return {"ANTHROPIC_BASE_URL": endpoint.removesuffix("/v1"), "CLAUDE_API_KEY": key}


def _gateway_values() -> dict[str, str]:
    """Biến của các cổng từ môi trường, không có thì từ `.env` của repo (tệp `agent.config` đọc)."""
    from dotenv import dotenv_values

    from agent.config import _ENV_FILE

    prefixes = ("STALI_", "OPENROUTER_")
    found = {k: v or "" for k, v in dotenv_values(_ENV_FILE).items() if k.startswith(prefixes)}
    found.update({k: v for k, v in os.environ.items() if k.startswith(prefixes) and v})
    return found


def pin(spec: str, via: str = "", build: bool = True) -> Pinned:
    """Ghim model (và cổng) cho cả process, rồi dựng thử nó (không gọi mạng).

    Args:
        spec: `provider:model`.
        via: Cổng trung gian (`GATEWAYS`), rỗng khi gọi thẳng.
        build: Dựng thử client để thiếu key thì hỏng ngay. `False` khi lượt không gọi model sinh đề
            (`exam_bench --rate-with import`): chấm lại không cần key của provider.

    Returns:
        Model đã ghim.

    Raises:
        SystemExit: Sai cú pháp, cổng lạ, hay process thiếu key.
    """
    from agent import llm
    from agent.config import get_settings

    provider, model = parse(spec)
    os.environ["LLM_ENABLED"] = "true"
    os.environ["LLM_PROVIDER"] = provider
    os.environ["LLM_MODEL"] = gateway_model(via, model)
    os.environ["LLM_FALLBACK_PROVIDER"] = ""
    os.environ["LLM_FALLBACK_MODEL"] = ""
    os.environ.update(gateway_env(via, provider, _gateway_values() if via else {}))
    get_settings.cache_clear()
    llm.chat_models.cache_clear()
    settings = get_settings()
    try:
        if build:
            llm.chat_models()
    except llm.ModelNotConfigured as exc:
        raise SystemExit(f"--model {spec!r}: {exc}") from exc
    tail = f"-{via}" if via else ""
    return Pinned(
        provider=provider,
        model=model,
        slug=slug(model) + tail,
        config=describe(settings, via, model),
        via=via,
    )


# Lời báo hết tiền: Stali (`insufficient_balance`, HTTP 402) và Anthropic (*"credit balance is too
# low"*). Pha 6b (15/11/2026): ví Stali cạn giữa `propose_bench`, và 167/296 lượt còn lại thành lượt
# hỏng được ghi như lượt đo.
# OpenRouter: `billing_error`, *"would exceed your available credits"* (run-138: không bắt được, nên
# 78 lượt hỏng vì hết tiền được ghi như lượt đo).
_OUT_OF_MONEY = (
    "insufficient_balance",
    "credit balance is too low",
    "insufficient credits",
    "billing_error",
    "exceed your available credits",
    # OpenAI: `insufficient_quota` -- đến dưới dạng `RateLimitError`, nên không có dòng này thì
    # `exam_bench` coi nó là lỗi hạ tầng và thử lại mãi (review trước commit).
    "insufficient_quota",
    "exceeded your current quota",
)


def out_of_money(exc: BaseException) -> bool:
    """Lỗi này là provider hay cổng báo hết tiền. Hàm thuần."""
    text = repr(exc).casefold()
    return any(mark in text for mark in _OUT_OF_MONEY)


def stop_if_out_of_money(exc: BaseException) -> None:
    """Dừng cả process khi hết tiền: mọi lượt sau đều hỏng, và số đo sẽ sai.

    Raises:
        SystemExit: `exc` là lời báo hết tiền.
    """
    if out_of_money(exc):
        raise SystemExit(f"hết tiền ở provider hay cổng, dừng bench: {exc!r}"[:300]) from exc


def preflight_verdict(answer: str, input_tokens: int) -> str:
    """Lời thử đầu lượt có cho thấy prompt bị chèn hay system bị rơi không. Hàm thuần.

    Args:
        answer: Chữ model trả lời lời thử.
        input_tokens: Token vào provider (hay cổng) báo, **kể cả** token cache.

    Returns:
        Lý do dừng, rỗng khi sạch.
    """
    if input_tokens <= 0:
        return "cổng không báo token vào: không đo được prompt có bị chèn hay không"
    if input_tokens > PREFLIGHT_MAX_INPUT:
        return (
            f"lời thử {input_tokens} token vào, quá {PREFLIGHT_MAX_INPUT}: "
            "có prompt lạ được chèn vào lời gọi"
        )
    if "KRIKY-PREFLIGHT-OK" not in answer:
        return f"model không làm theo system prompt (trả {answer[:80]!r}): system bị rơi hay bị đè"
    return ""


async def preflight() -> tuple[int, str]:
    """Một lời gọi đầu lượt qua đúng model đã ghim (đường `agent.llm.standalone`).

    Returns:
        Token vào (gồm cache, như `usage_metadata` của LangChain) và chữ trả lời.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    from agent import llm

    # 512: model có thinking hay suy luận vẫn còn chỗ trả lời; 64 có thể hết trước khi tới lời đáp,
    # và lời thử kết luận nhầm là system bị rơi (review pha 5b).
    chat = llm.standalone(max_tokens=512)
    reply = await chat.ainvoke([SystemMessage(PREFLIGHT_SYSTEM), HumanMessage(PREFLIGHT_ASK)])
    usage = reply.usage_metadata or {}
    return int(usage.get("input_tokens", 0) or 0), str(reply.text)


async def check_preflight(pinned: Pinned) -> str:
    """Chạy lời thử đầu lượt và dừng process khi nó bẩn.

    Gọi model thật một lần (vài chục token). Chỉ chạy khi có cổng trung gian: gọi thẳng provider thì
    không ai chèn gì. Async và phải chạy **trong** event loop của bench: SDK cache client HTTP trong
    process, và một `asyncio.run` riêng để lại client gắn với loop đã đóng (*"Event loop is
    closed"*, `propose_bench`).

    Args:
        pinned: Model đã ghim.

    Returns:
        Một dòng kết quả, ghi vào báo cáo.

    Raises:
        SystemExit: Lời thử bẩn -- trước khi tiêu thêm đồng nào.
    """
    if not pinned.via:
        return ""
    tokens, answer = await preflight()
    if why := preflight_verdict(answer, tokens):
        raise SystemExit(f"--via {pinned.via}: {why}")
    return f"lời thử qua {pinned.via}: {tokens} token vào, model làm theo system"
