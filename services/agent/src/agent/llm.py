"""Module duy nhất trong AGENT biết model của ai đang trả lời.

Mọi handler đều xin một runnable rồi viết prompt cho nó. Không handler nào gọi tên
OpenAI, Gemini hay bất kỳ ai, nên đổi provider là sửa hai dòng trong `.env` thay vì
một thay đổi rải ra ba handler. Đó cũng là thứ làm cho bộ test miễn phí: một test
thay cái builder ở đây và không có gì chạm tới network.

Hai điều trong đây dễ làm sai và tốn công debug:

**Credential được truyền vào, không phải thừa hưởng.** `init_chat_model` đọc
`OPENAI_API_KEY` từ environment của process, nhưng dự án này nạp `.env` vào một đối
tượng `Settings`, và đối tượng đó không bao giờ tới `os.environ`. Bỏ key ra khỏi
lời gọi thì model xác thực với danh nghĩa không ai cả.

**Shape được áp cho từng model, một cách có chủ ý.** `with_fallbacks` trả về một
`RunnableWithFallbacks`, mà class đó không mang `with_structured_output`. Cứ gọi thì
vẫn chạy -- `RunnableWithFallbacks.__getattr__` đọc annotation trả về của method,
thấy một `Runnable`, rồi dựng lại chuỗi qua nó -- nhưng đường đó là reflection trên
type hint, và nó sụp rất tệ khi một annotation không resolve được trong module của
chính nó: lỗi hiện ra thành `NameError: name 'Runnable' is not defined` raise từ
trong `typing`, chẳng gọi tên method cũng chẳng gọi tên model. Vì thế
`with_fallback` tự shape từng model rồi lắp chuỗi từ các kết quả. Cùng một kết quả
khi phép thuật kia chạy được, và một lần thất bại đọc hiểu được khi nó không chạy.
"""

from collections.abc import Callable
from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable

from agent.config import Settings, get_settings

# Setting nào giữ credential cho provider nào. Một provider không có mặt ở đây vẫn
# cấu hình được; nó chỉ phải tự tìm credential theo cách SDK của nó làm.
_CREDENTIAL = {
    "openai": "openai_api_key",
    "google_genai": "google_api_key",
}


class ModelNotConfigured(RuntimeError):
    """Có người yêu cầu gọi model, mà không có gì nói là model nào."""


def enabled() -> bool:
    """Handler có nên gọi model thật hay không.

    Returns:
        True khi `LLM_ENABLED` đang bật và có đặt id model. Thiếu id được tính là
        tắt chứ không phải lỗi, nhờ vậy một `.env` điền nửa vời vẫn demo được bằng
        nội dung dọn trước thay vì làm mọi job thất bại.
    """
    settings = get_settings()
    return settings.llm_enabled and bool(settings.llm_model)


def _build(settings: Settings, provider: str, model: str) -> BaseChatModel:
    """Dựng một chat model.

    Args:
        settings: Settings của process, nơi giữ credential và timeout cho một lần
            gọi.
        provider: Tên provider mà LangChain hiểu, ví dụ "openai".
        model: Id model tại provider đó.

    Returns:
        Một chat model gọi được ngay.

    Raises:
        ModelNotConfigured: Nếu provider cần một credential mà process này không
            có. Thất bại ở đây tốt hơn thất bại bên trong một job, nơi lý do tới
            kèm trong một lỗi queue.
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
    """Mọi model đã cấu hình, cái cần thử trước nằm ở đầu.

    Returns:
        Một model, hoặc hai khi có cấu hình provider fallback. Được cache suốt đời
        worker: dựng một client cho mỗi job sẽ là mở một connection pool cho mỗi
        job.

    Raises:
        ModelNotConfigured: Nếu không có id model nào được đặt, hoặc thiếu một
            credential.
    """
    settings = get_settings()
    if not settings.llm_model:
        raise ModelNotConfigured("LLM_MODEL is empty; nothing says which model to call")

    models = [_build(settings, settings.llm_provider, settings.llm_model)]
    if settings.llm_fallback_provider and settings.llm_fallback_model:
        models.append(_build(settings, settings.llm_fallback_provider, settings.llm_fallback_model))
    return tuple(models)


def with_fallback(shape: Callable[[BaseChatModel], Runnable]) -> Runnable:
    """Áp một phép biến đổi lên mọi model đã cấu hình rồi xâu chúng lại.

    `shape` là chỗ `with_structured_output` được đặt vào. Nó chạy riêng trên từng
    model để chuỗi fallback được dựng từ những runnable đã shape xong -- xem docstring
    của module để biết vì sao thứ tự còn lại âm thầm làm mất structured output.

    Args:
        shape: Biến một chat model thành runnable mà handler muốn. Hàm đồng nhất là
            một câu trả lời hoàn toàn ổn khi handler chỉ cần chữ.

    Returns:
        Runnable của model đầu tiên, với những model còn lại đứng sau làm fallback.
        Khi chỉ cấu hình một model thì trả về chính runnable đó -- không bọc gì, nhờ
        vậy stream giữ nguyên thứ provider đưa cho nó.
    """
    shaped = [shape(model) for model in chat_models()]
    if len(shaped) == 1:
        return shaped[0]
    return shaped[0].with_fallbacks(shaped[1:])
