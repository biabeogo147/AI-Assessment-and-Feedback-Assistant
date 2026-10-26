"""Ba lời gọi model của document agent. Module duy nhất trong `services/document` import
`langchain`.

- **Đọc banner** (D9): `gpt-5.6-luna` nhìn phần trên của một trang mở chương và đọc **số và tên
  chương, cùng tên bài in ngay dưới** -- OCR không đọc nổi chữ trang trí (5/5 chương của Lớp 6 tập 1
  ra rác, `document-agent-hierarchy` Status). Chỉ được gọi ở trang qua cổng `features.banner_gates`:
  đo trên trang 7, luna nhận nhầm một trang bài thường là *"phần mở đầu"*.
- **Tóm tắt** (D6): `gpt-4o-mini`, một lời gọi mỗi nút, để model ở plan sau lần xuống cây bằng tiêu
  đề và tóm tắt (PageIndex).
- **Đọc công thức** (`formulas-on-demand`): Claude Haiku 5.5, tắt thinking, đọc mọi công thức trên
  ảnh cả trang -- chỉ trang có khối `formula`, chỉ khi một lượt chat của BE đọc tới trang ấy.

Cùng khuôn với `agent/llm.py`, và cùng hai bài học: **credential được truyền vào** (`.env` của repo
không bao giờ tới `os.environ`), và mọi lời gọi qua đúng một module -- đổi model là sửa `.env`, test
thay builder ở đây là không gì chạm mạng. Mỗi lời gọi chọn được provider, OpenAI hay Claude
(`SUMMARY_PROVIDER`, `BANNER_PROVIDER`; `claude-provider-option`), nên chữ trả về đọc bằng `.text`:
Claude trả `content` là một list block, và `str()` của list ấy không phải chữ model viết.
"""

import base64
import json
import logging
import re
from dataclasses import dataclass

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from document.config import Settings
from document.latex_escapes import restore_latex_escapes

logger = logging.getLogger(__name__)

_BANNER_PROMPT = (
    "Ảnh là phần trên của một trang sách giáo khoa tiếng Việt. Nếu đây là trang MỞ ĐẦU một chương "
    "hoặc một phần lớn của sách, đọc chính xác số và tên của nó như in trên ảnh. Nếu ngay dưới đó "
    "có tên bài đầu tiên (ví dụ một dải ghi BÀI 8 kèm tên bài) thì đọc cả số bài và tên bài. "
    "Trả về "
    'đúng một object JSON: {"la_mo_dau": true|false, "loai": "chương"|"phần"|null, '
    '"so": "<số như in, ví dụ I, II, 3>"|null, '
    '"ten": "<tên như in, giữ dấu, viết hoa như in>"|null, '
    '"so_bai": "<số bài>"|null, "ten_bai": "<tên bài như in>"|null}. '
    "Không đoán: chữ nào không đọc được thì để null."
)

_SUMMARY_SYSTEM = (
    "Bạn tóm tắt một phần của một tài liệu học tập tiếng Việt, để một trợ lý soạn đề sau này đọc "
    "tiêu đề và tóm tắt mà quyết định có mở phần ấy ra hay không.\n"
    "Luật:\n"
    "- Hai tới bốn câu, tiếng Việt, không gạch đầu dòng.\n"
    "- Nói phần ấy dạy kiến thức gì, có những dạng bài hay ví dụ nào.\n"
    "- Chỉ dùng điều có trong đoạn được đưa. Chữ đến từ OCR nên có lỗi chính tả: hiểu theo nghĩa, "
    "đừng chép lỗi, đừng bịa thêm khái niệm không có trong đoạn.\n"
    "- Không mở đầu bằng 'Phần này' hay nhắc lại tiêu đề."
)


# Lời dặn đọc công thức (plan `formulas-on-demand`): chữ của khảo sát 11/10/2026 và lần đo lại
# 26/10/2026 trên 5 trang `run-5`, cộng một dòng cho `⋮` -- mọi model đã đo đều đọc nó thành `:`,
# đổi *chia hết* thành *chia*. Trả JSON tự viết như banner, không structured output: hai đường cùng
# bẫy JSON nuốt gạch chéo, và đường này đi qua `restore_latex_escapes` (`parse_formulas`).
_FORMULA_PROMPT = (
    "Ảnh là một trang sách giáo khoa Toán tiếng Việt. Liệt kê MỌI phương trình, công thức, biểu "
    "thức toán học có trên trang, theo thứ tự đọc (trên xuống, trái sang). Mỗi phần tử là một công "
    "thức viết bằng LaTeX, không bọc $ hay \\[ \\]. Chữ tiếng Việt nằm trong công thức (ví dụ "
    "ƯCLN, “với”, “người”) đặt trong \\text{}. Công thức nhiều dòng dùng "
    "\\begin{aligned}...\\end{aligned}. "
    "Dấu ba chấm dọc ⋮ (chia hết, như trong a ⋮ b) viết là \\vdots, KHÔNG viết là dấu hai chấm. "
    "KHÔNG chép văn xuôi, tiêu đề hay lời giải thích. Trả về đúng một object JSON "
    '{"cong_thuc": ["<công thức>", ...]}; trang không có công thức thì danh sách rỗng.'
)
# Đọc công thức chạy tắt thinking, effort `low`, không theo `LLM_THINKING` / `LLM_EFFORT` chung: đo
# 26/10/2026, thinking làm chậm gấp đôi mà không bớt lỗi nào.
FORMULA_CLAUDE: dict[str, object] = {"thinking": {"type": "disabled"}, "effort": "low"}
# Gỡ phần bọc model hay thêm dù đã dặn: `$…$`, `\[…\]`, `\(…\)`.
_FORMULA_WRAPS = ((r"\[", r"\]"), (r"\(", r"\)"), ("$$", "$$"), ("$", "$"))


@dataclass(frozen=True)
class FormulaReading:
    """Thứ VLM đọc được trên ảnh một trang.

    Attributes:
        formulas: Công thức LaTeX, đã sửa gạch chéo và gỡ phần bọc, bỏ chuỗi rỗng.
        refused: Model từ chối (`stop_reason` *refusal*).
        tokens: Token vào + ra.
    """

    formulas: tuple[str, ...]
    refused: bool
    tokens: int


@dataclass(frozen=True)
class BannerReading:
    """Thứ luna đọc được trên một banner.

    Attributes:
        is_opening: Luna cho rằng trang mở một chương hay một phần.
        kind: *"chương"* hoặc *"phần"*.
        number: Số như in (*"II"*).
        title: Tên như in.
        lesson_number: Số bài in ngay dưới banner.
        lesson_title: Tên bài ấy.
        tokens: Token vào + ra của lời gọi.
    """

    is_opening: bool
    kind: str | None
    number: str | None
    title: str | None
    lesson_number: str | None
    lesson_title: str | None
    tokens: int


@dataclass(frozen=True)
class Summary:
    """Một tóm tắt và giá của nó.

    Attributes:
        text: Tóm tắt.
        tokens: Token vào + ra.
    """

    text: str
    tokens: int


def claude_options(thinking: str, effort: str) -> dict[str, object]:
    """Tham số riêng của Claude, như `agent/llm.claude_options`. Hàm thuần.

    Hai service không import nhau (import-linter), nên phép dịch bốn dòng này có hai bản; luật
    của nó -- rỗng thì theo mặc định của model -- là một.

    Args:
        thinking: `LLM_THINKING`: `disabled`, `adaptive`, hay rỗng.
        effort: `LLM_EFFORT`, hay rỗng.

    Returns:
        `thinking` và `effort` khi có đặt.
    """
    options: dict[str, object] = {}
    if thinking:
        options["thinking"] = {"type": thinking}
    if effort:
        options["effort"] = effort
    return options


def chat_model(
    provider: str, model: str, api_key: str, timeout: float, **extra: object
) -> BaseChatModel:
    """Dựng một chat model với khoá truyền vào.

    Args:
        provider: `openai` hay `anthropic`.
        model: Id model.
        api_key: Khoá của provider ấy, từ `Settings`.
        timeout: Trần giây.
        **extra: Tham số riêng của provider (`reasoning_effort` cho luna, `claude_options` cho
            Claude).

    Returns:
        Một chat model gọi được ngay.
    """
    return init_chat_model(
        model, model_provider=provider, api_key=api_key, timeout=timeout, **extra
    )


def model_for(
    settings: Settings,
    provider: str,
    model: str,
    claude: dict[str, object] | None = None,
    **openai_extra: object,
) -> BaseChatModel | None:
    """Model của một lời gọi theo provider nó chọn, hay `None` khi thiếu khoá của provider ấy.

    Khoá theo **provider**, không theo lời gọi: tóm tắt trên Claude và banner trên OpenAI thì mỗi
    model cầm khoá của mình, và thiếu một khoá chỉ tắt đúng model cần nó.

    Args:
        settings: Settings của process.
        provider: `openai` hay `anthropic` (`Settings` đã từ chối giá trị khác).
        model: Id model.
        claude: Tham số Claude riêng của lời gọi này, thay cho `LLM_THINKING` / `LLM_EFFORT` chung
            -- đọc công thức chạy tắt thinking, effort `low` dù tóm tắt chạy thế nào
            (`formulas-on-demand`). `None` là theo cấu hình chung.
        **openai_extra: Tham số chỉ OpenAI nhận (`reasoning_effort` của luna); Claude nhận
            `claude_options` thay vào.

    Returns:
        Chat model, hoặc `None`.
    """
    if provider == "anthropic":
        key, extra = (
            settings.claude_api_key,
            claude
            if claude is not None
            else claude_options(settings.llm_thinking, settings.llm_effort),
        )
    else:
        key, extra = settings.openai_api_key, dict(openai_extra)
    if not key:
        return None
    return chat_model(provider, model, key, settings.llm_timeout_seconds, **extra)


def parse_banner(raw: str, tokens: int) -> BannerReading:
    """Đọc JSON luna trả về. Hàm thuần.

    Luna đôi khi bọc JSON trong ```` ``` ````; một câu trả lời không phải JSON thì coi như không đọc
    được gì -- tên chương lùi về nhãn số (D6, `document-agent-hierarchy`), không bao giờ bịa.

    Args:
        raw: Chữ model trả.
        tokens: Token của lời gọi.

    Returns:
        Kết quả đọc; mọi trường `None` khi không parse được.
    """
    body = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("banner reader returned no json: %r", raw[:200])
        return BannerReading(False, None, None, None, None, None, tokens)

    def text(key: str) -> str | None:
        value = data.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else None

    return BannerReading(
        is_opening=bool(data.get("la_mo_dau")),
        kind=text("loai"),
        number=text("so"),
        title=text("ten"),
        lesson_number=text("so_bai"),
        lesson_title=text("ten_bai"),
        tokens=tokens,
    )


def _tokens(message: object) -> int:
    usage = getattr(message, "usage_metadata", None) or {}
    return int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))


async def read_banner(model: BaseChatModel, png: bytes) -> BannerReading:
    """Hỏi luna tên chương (và tên bài đầu) trên ảnh banner.

    Args:
        model: Chat model của `banner_model`.
        png: Ảnh phần trên của trang.

    Returns:
        Kết quả đọc.
    """
    image = "data:image/png;base64," + base64.b64encode(png).decode()
    message = HumanMessage(
        content=[
            {"type": "text", "text": _BANNER_PROMPT},
            {"type": "image_url", "image_url": {"url": image}},
        ]
    )
    answer = await model.ainvoke([message])
    return parse_banner(answer.text, _tokens(answer))


async def summarise(model: BaseChatModel, title: str, body: str) -> Summary:
    """Tóm tắt một nút cây.

    Args:
        model: Chat model của `summary_model`.
        title: Tiêu đề nút, kèm nhãn số.
        body: Chữ của nút -- hoặc, với nút có con, tóm tắt của các con.

    Returns:
        Tóm tắt.
    """
    answer = await model.ainvoke(
        [
            SystemMessage(content=_SUMMARY_SYSTEM),
            HumanMessage(content=f"Tiêu đề: {title}\n\nNội dung:\n{body}"),
        ]
    )
    return Summary(answer.text.strip(), _tokens(answer))


# Một gạch chéo trong chữ model: cặp `\\` và `\"` (đã thoát đúng), `\uXXXX` (chữ Unicode), hay một
# gạch chéo đơn. Công thức không bao giờ chứa xuống dòng hay tab **thật**, nên mọi gạch chéo đơn đều
# là của LaTeX: `\frac`, `\neq`, `\rho`, `\in`. Nhân đôi chúng **trước** khi giải mã -- trông vào
# `restore_latex_escapes` sau đó là để `\neq` thành xuống dòng thật + `eq`, vì luật ngưỡng của nó
# đúng cho lời giải có xuống dòng, sai cho công thức (review pha 2, `formulas-on-demand`).
_BACKSLASH_TOKEN = re.compile(r'\\\\|\\"|\\u[0-9a-fA-F]{4}|\\')


def _latex_safe(body: str) -> str:
    """Nhân đôi mọi gạch chéo đơn trong chữ JSON model trả, giữ escape đã đúng. Hàm thuần."""
    return _BACKSLASH_TOKEN.sub(
        lambda found: "\\\\" if found.group() == "\\" else found.group(), body
    )


def _unwrapped(formula: str) -> str:
    """Gỡ một lớp bọc `$…$`, `\\[…\\]`, `\\(…\\)` -- chỉ khi bên trong không còn dấu ấy.

    `$a$ và $b$` giữ nguyên: gỡ hai đầu của nó là ra `a$ và $b`.
    """
    bare = formula.strip()
    for opening, closing in _FORMULA_WRAPS:
        inner = bare[len(opening) : -len(closing)]
        if (
            bare.startswith(opening)
            and bare.endswith(closing)
            and len(bare) > len(opening) * 2
            and opening not in inner
            and closing not in inner
        ):
            bare = inner.strip()
    return bare


def parse_formulas(raw: str, tokens: int, refused: bool = False) -> FormulaReading:
    """Đọc JSON VLM trả về cho một trang. Hàm thuần.

    Mỗi công thức đi qua `restore_latex_escapes` -- đúng bẫy `\frac` thành form-feed mà check
    `escape-repair-is-wired-in` canh -- rồi gỡ phần bọc `$…$`. Một câu trả lời không đọc được thì
    trang ấy không có công thức nào: không bịa, và lần đọc sau vẫn chỉ có chữ như trước plan này.

    Args:
        raw: Chữ model trả.
        tokens: Token của lời gọi.
        refused: Model đã từ chối.

    Returns:
        Kết quả đọc.
    """
    if refused:
        return FormulaReading((), True, tokens)
    body = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(_latex_safe(body), strict=False)
    except json.JSONDecodeError:
        logger.warning("formula reader returned no json: %r", raw[:200])
        return FormulaReading((), False, tokens)
    found = data.get("cong_thuc") if isinstance(data, dict) else None
    # `restore_latex_escapes` vẫn chạy sau: `_latex_safe` không chạm ký tự điều khiển model tự gõ
    # thẳng vào chuỗi (`strict=False` nhận chúng), và đó đúng là hình dạng bộ sửa ấy dựng lại.
    formulas = tuple(
        bare
        for one in (found if isinstance(found, list) else [])
        if isinstance(one, str) and (bare := _unwrapped(restore_latex_escapes(one)))
    )
    return FormulaReading(formulas, False, tokens)


async def read_formulas(model: BaseChatModel, png: bytes) -> FormulaReading:
    """Hỏi VLM mọi công thức trên ảnh cả trang (plan `formulas-on-demand`).

    Args:
        model: Chat model của `formula_model` -- thinking tắt, effort `low`.
        png: Ảnh cả trang.

    Returns:
        Kết quả đọc. Model từ chối thì `refused`, không ném: Claude Haiku không có fallback, và một
        trang bị từ chối chỉ là một trang không có công thức.
    """
    image = "data:image/png;base64," + base64.b64encode(png).decode()
    message = HumanMessage(
        content=[
            {"type": "image_url", "image_url": {"url": image}},
            {"type": "text", "text": _FORMULA_PROMPT},
        ]
    )
    answer = await model.ainvoke([message])
    stop = (getattr(answer, "response_metadata", None) or {}).get("stop_reason")
    return parse_formulas(answer.text, _tokens(answer), refused=stop == "refusal")
