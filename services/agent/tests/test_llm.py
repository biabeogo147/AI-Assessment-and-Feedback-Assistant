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
