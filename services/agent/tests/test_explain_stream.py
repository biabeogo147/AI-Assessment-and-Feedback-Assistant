"""Handler kèm học sinh làm gì trong lúc model viết, và khi nào nó dừng.

Hành vi đáng chú ý nằm cả ở phần thất bại: một model chết giữa đường thì đã đặt chữ lên màn
hình của học sinh rồi, và thứ được lưu buộc phải là đúng những chữ đó. Lưu một thứ khác
nghĩa là học sinh tải lại trang và gặp một câu trả lời khác câu em vừa đọc, mà không có gì
giải thích cho việc đổi chỗ ấy.
"""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from agent import handlers, llm
from contracts import (
    ExplainTurnRequested,
    GeneratedOption,
    GeneratedQuestion,
    SolutionMethod,
)

QUESTION = GeneratedQuestion(
    stem="Đồ thị y = (2x − 1)/(x + 3) có tiệm cận ngang là đường nào?",
    options=(
        GeneratedOption(label="A", text="y = 2", is_correct=True),
        GeneratedOption(label="B", text="x = −3", error_label="nhầm tiệm cận đứng"),
    ),
    methods=(
        SolutionMethod(title="Cách 1", body="Chia tử và mẫu cho x."),
        SolutionMethod(title="Cách 2", body="Xét giới hạn khi x → ±∞."),
    ),
    learning_objective="tiệm cận",
)

REQUEST = ExplainTurnRequested(
    request_id="a1",
    questions=(QUESTION,),
    question_numbers=(5,),
    chosen_labels={QUESTION.stem: "B"},
    error_labels={QUESTION.stem: "nhầm tiệm cận đứng"},
    stream_channel="aiafa:stream:test",
)


class Recorder:
    """Đóng thế cho connection Redis mà arq đưa cho handler."""

    def __init__(self) -> None:
        self.published: list[str] = []

    async def publish(self, channel: str, piece: str) -> None:
        self.published.append(piece)


@pytest.fixture
def on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bật đường gọi model lên mà không cần một key hay một file `.env`."""
    monkeypatch.setattr(llm, "enabled", lambda: True)


@pytest.mark.asyncio
async def test_the_answer_goes_out_piece_by_piece(
    on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Các mẩu được publish ngay khi được sinh ra, không gửi dồn một lần ở cuối."""
    monkeypatch.setattr(
        llm, "chat_models", lambda: (GenericFakeChatModel(messages=iter(["một hai ba"])),)
    )
    redis = Recorder()

    reply = await handlers.explain({"redis": redis}, REQUEST.model_dump(mode="json"))

    assert redis.published, "nothing was published, so the student watched a blank screen"
    assert "".join(redis.published) == reply["text"]


@pytest.mark.asyncio
async def test_a_model_that_dies_midway_keeps_the_words_already_read(
    on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Thứ được lưu phải là thứ đã được cho xem.

    Câu trả lời dọn trước chỉ là fallback đúng khi chưa ai đọc gì cả. Một khi chữ đã nằm trên
    màn hình thì nó thành fallback sai: lịch sử hội thoại sẽ lệch với cuộc hội thoại mà học
    sinh còn nhớ.
    """

    async def dies(request, publish):
        await publish("Ở câu 5, ")
        await publish("lỗi của em là ")
        raise RuntimeError("provider hung up")

    monkeypatch.setattr(handlers, "speak", dies)
    redis = Recorder()

    reply = await handlers.explain({"redis": redis}, REQUEST.model_dump(mode="json"))

    assert reply["text"] == "Ở câu 5, lỗi của em là "
    assert reply["text"] == "".join(redis.published)


@pytest.mark.asyncio
async def test_a_model_that_dies_before_saying_anything_falls_back(
    on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chưa có gì được đọc thì không có gì để nó mâu thuẫn.

    Nên câu trả lời dọn trước được đưa ra, và học sinh nhận được một lượt nói thay vì một
    lỗi.
    """

    async def dies(request, publish):
        raise RuntimeError("provider refused the connection")

    monkeypatch.setattr(handlers, "speak", dies)
    redis = Recorder()

    reply = await handlers.explain({"redis": redis}, REQUEST.model_dump(mode="json"))

    assert redis.published == []
    assert "Kriky" in reply["text"], "the prepared greeting should have stood in"


@pytest.mark.asyncio
async def test_nobody_listening_means_nothing_is_published(
    on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Một job mà client đã bỏ đi thì vẫn trả lời; nó chỉ trả lời trong im lặng."""
    monkeypatch.setattr(
        llm, "chat_models", lambda: (GenericFakeChatModel(messages=iter(["xong"])),)
    )
    redis = Recorder()
    silent = REQUEST.model_copy(update={"stream_channel": ""})

    reply = await handlers.explain({"redis": redis}, silent.model_dump(mode="json"))

    assert redis.published == []
    assert reply["text"]
