"""AGENT rung chuông sau mỗi câu viết xong — và tiếng chuông không bao giờ làm hỏng job.

Hai luật, và luật thứ hai là luật dễ mất nhất khi ai đó dọn code: công việc đã xong và đã
nằm trong result store **trước** khi chuông rung. Để một Redis dở chứng ném ra khỏi handler
là đánh đổi một câu hỏi thật lấy một lần cập nhật màn hình (ADR-25).
"""

import pytest

from agent import handlers, llm
from contracts import DraftQuestionRequested


class Bells:
    """Đóng thế cho connection Redis mà arq đưa cho handler."""

    def __init__(self, broken: bool = False) -> None:
        self.rung: list[tuple[str, str]] = []
        self.broken = broken

    async def publish(self, channel: str, message: str) -> None:
        if self.broken:
            raise ConnectionError("redis đi vắng")
        self.rung.append((channel, message))


def _asked(channel: str = "draft:de-1") -> dict:
    return DraftQuestionRequested(
        request_id="de-1:3:1",
        subject="Toán",
        grade="12",
        topic_scope="tích phân",
        ordinal=3,
        of_total=10,
        progress_channel=channel,
    ).model_dump(mode="json")


@pytest.mark.asyncio
async def test_the_bell_carries_a_number_not_a_question(monkeypatch) -> None:
    """Chuông chở số thứ tự, không chở nội dung.

    Pub/sub không bền: không ai nghe thì lời nói mất. Chở câu hỏi trong đó nghĩa là một
    người đóng tab đúng lúc làm **mất hẳn** một câu đã soạn xong, chứ không chỉ mất một
    lần cập nhật màn hình.
    """
    monkeypatch.setattr(llm, "enabled", lambda: False)
    bells = Bells()

    answer = await handlers.write_draft_question({"redis": bells}, _asked())

    assert bells.rung == [("draft:de-1", "3")]
    # Và câu hỏi vẫn đi đường cũ: nó nằm trong thứ handler trả về, tức result store của arq.
    assert answer["question"]["stem"]


@pytest.mark.asyncio
async def test_a_dev_box_without_a_key_still_rings(monkeypatch) -> None:
    """Đường mock cũng rung chuông.

    Một màn hình chỉ sống khi có API key thì không phải một màn hình sống: cả ba đường ra
    của handler đều đặt một kết quả vào result store, nên cả ba đều phải báo.
    """
    monkeypatch.setattr(llm, "enabled", lambda: False)
    bells = Bells()

    await handlers.write_draft_question({"redis": bells}, _asked())

    assert len(bells.rung) == 1


@pytest.mark.asyncio
async def test_a_model_that_dies_still_rings(monkeypatch) -> None:
    """Model hỏng thì handler lùi về nội dung dọn trước — và vẫn báo.

    Không rung ở nhánh này thì màn hình đứng im đúng lúc có một câu vừa vào đề, và người
    đọc kết luận rằng hệ thống treo.
    """
    monkeypatch.setattr(llm, "enabled", lambda: True)

    async def dies(brief, banned):
        raise RuntimeError("model đi vắng")

    monkeypatch.setattr(handlers, "write_question", dies)
    bells = Bells()

    answer = await handlers.write_draft_question({"redis": bells}, _asked())

    assert len(bells.rung) == 1
    assert answer["question"]["stem"]


@pytest.mark.asyncio
async def test_a_broken_bell_does_not_break_the_job(monkeypatch) -> None:
    """Redis ném thì job **vẫn** trả về câu hỏi.

    Phép kiểm đáng giá nhất trong file: lúc chuông rung, câu hỏi đã viết xong. Một
    exception thoát ra từ đây biến một job đã thành công thành một job thất bại, và BE sẽ
    đọc nó là *"chính job đó đã nổ"* — tức không hỏi lại, và vị trí ấy mất câu vĩnh viễn.
    """
    monkeypatch.setattr(llm, "enabled", lambda: False)

    answer = await handlers.write_draft_question({"redis": Bells(broken=True)}, _asked())

    assert answer["question"]["stem"]


@pytest.mark.asyncio
async def test_no_channel_means_no_bell(monkeypatch) -> None:
    """Không ai quan tâm thì không publish gì.

    Channel rỗng là cách BE nói *"lượt này không có ai nghe"*; publish vào một chuỗi rỗng
    là một lệnh Redis đi ra mỗi câu, cho không ai cả.
    """
    monkeypatch.setattr(llm, "enabled", lambda: False)
    bells = Bells()

    await handlers.write_draft_question({"redis": bells}, _asked(channel=""))

    assert bells.rung == []
