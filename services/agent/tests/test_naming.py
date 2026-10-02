"""Đặt tên cho một đoạn chat: đường model, đường mock, và đường hỏng.

Task này nhỏ tới mức dễ tưởng không cần test. Thứ đáng kiểm không phải cái tên — một cái
tên xấu vẫn là một cái tên — mà là **ba đường ra** của nó phải cùng trả về một
`ConversationNameCompleted` hợp lệ. Nó chạy ở cuối một lượt nói, nên mọi cách nó hỏng đều
có cơ hội kéo theo cả lượt ấy.
"""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from agent import handlers, llm
from contracts import ConversationNameRequested

REQUEST = ConversationNameRequested(
    request_id="r1",
    said="Soạn cho tôi 2 câu trắc nghiệm về đạo hàm của đa thức, lớp 12, mức cơ bản",
)


@pytest.fixture
def on(monkeypatch):
    """Bật đường model mà không cần API key nào."""
    monkeypatch.setattr(llm, "enabled", lambda: True)


@pytest.mark.asyncio
async def test_the_model_writes_the_title(on, monkeypatch) -> None:
    """Đường thường: model trả về gì thì handler trả về đúng thứ đó.

    Nguyên văn, không cắt. Việc cắt và dọn là của BE — nó biết chuỗi này sẽ nằm trên một
    hàng rộng 228px, còn AGENT thì không biết gì về rail.
    """
    monkeypatch.setattr(
        llm,
        "chat_models",
        lambda: (GenericFakeChatModel(messages=iter(["Đề đạo hàm đa thức 12"])),),
    )

    answer = await handlers.name_conversation({}, REQUEST.model_dump(mode="json"))

    assert answer["title"] == "Đề đạo hàm đa thức 12"
    assert answer["request_id"] == "r1"


@pytest.mark.asyncio
async def test_a_dev_box_without_a_key_still_gets_a_name(monkeypatch) -> None:
    """`LLM_ENABLED=false` không được để rail trống.

    Mock lấy mấy từ đầu. Nó xấu hơn hẳn một cái tên model viết, và nó **đúng** — đó là
    điều kiện duy nhất một mock phải đạt.
    """
    monkeypatch.setattr(llm, "enabled", lambda: False)

    answer = await handlers.name_conversation({}, REQUEST.model_dump(mode="json"))

    assert answer["title"] == "Soạn cho tôi 2 câu trắc"


@pytest.mark.asyncio
async def test_a_model_that_dies_still_gets_a_name(on, monkeypatch) -> None:
    """Model ném lỗi thì lùi về mock, không ném tiếp lên trên.

    Đây là phép kiểm đáng giá nhất trong file. Task này chạy ở **cuối một lượt nói**, sau
    khi giáo viên đã chờ xong và mọi bước đã commit. Một exception thoát ra từ đây sẽ biến
    một lượt đã thành công thành một lỗi 500 — mất cả việc vừa làm, vì một cái tên.
    """

    async def dies(request):
        raise RuntimeError("model đi vắng")

    monkeypatch.setattr(handlers, "name_it", dies)

    answer = await handlers.name_conversation({}, REQUEST.model_dump(mode="json"))

    assert answer["title"] == "Soạn cho tôi 2 câu trắc"
