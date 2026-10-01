"""Không test nào trong thư mục này được phép chạm tới một provider model.

Một test gọi model thật thì chậm, tốn tiền, và trả lời khác nhau mỗi lần chạy, nên nó
chỉ khẳng định được những điều mơ hồ -- đúng loại test xanh trong khi thứ nó canh đã
hỏng. Chỗ nối là `agent.llm`, và fixture này đóng chỗ nối đó cho cả bộ test thay vì để
từng test phải tự nhớ.

`agent/llm.py` là module duy nhất dựng client của provider, nên thay `chat_models` ở
đây là đủ: các handler xin `with_fallback` một runnable và không bao giờ biết nó là của
ai.
"""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from agent import llm


@pytest.fixture(autouse=True)
def no_real_model(monkeypatch: pytest.MonkeyPatch) -> GenericFakeChatModel:
    """Cấp cho mọi test một chat model giả thay cho client của provider.

    Args:
        monkeypatch: Bộ patch của pytest, phạm vi một test.

    Returns:
        Cái fake đó, để một test có quan tâm đọc được những gì đã hỏi nó hoặc xếp sẵn
        một câu trả lời khác.

    Side effects:
        Thay `agent.llm.chat_models` trong suốt test và xoá cache của nó lúc đi vào, nhờ
        vậy một client thật do một test trước dựng lên không rò sang được.
    """
    fake = GenericFakeChatModel(messages=iter(["nội dung giả cho test"] * 1000))
    llm.chat_models.cache_clear()
    monkeypatch.setattr(llm, "chat_models", lambda: (fake,))
    return fake
