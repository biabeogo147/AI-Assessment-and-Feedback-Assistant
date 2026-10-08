"""Nửa **nghe** của kênh hích thư viện tài liệu.

Hai luật đáng canh ở đây, và cả hai đều là bài học `drafting.py` đã trả giá để biết: subscribe
phải xảy ra **lúc vào khối** chứ không phải lúc lặp lần đầu, và một Redis gãy giữa chừng không
được phép ném ngược ra ngoài.

Nửa phát -- `announce` -- và tên channel được canh ở `services/ingest/tests/test_events.py`,
vì chúng sống ở bên ấy. Một test ở lại đây sẽ là một test `be` không chạy nổi nếu `ingest` hỏng,
tức đúng thứ ranh giới này tồn tại để không có.
"""

import pytest

from be.document_events import open_changes


class _PubSub:
    """Một subscription giả, phát ra đúng những gì test dọn sẵn."""

    def __init__(self, messages: list[object], explode: bool = False) -> None:
        self.messages = list(messages)
        self.subscribed: list[str] = []
        self.closed = False
        self._explode = explode

    async def subscribe(self, channel: str) -> None:
        self.subscribed.append(channel)

    async def get_message(self, ignore_subscribe_messages: bool = False, timeout: float = 0):
        if self._explode:
            raise OSError("redis is gone")
        if not self.messages:
            raise AssertionError("test đọc nhiều hơn số message đã dọn")
        return self.messages.pop(0)

    async def unsubscribe(self, channel: str) -> None:
        pass

    async def aclose(self) -> None:
        self.closed = True


class _Pool:
    """Một pool Redis giả, chỉ biết mở pubsub. Nửa nghe không publish bao giờ."""

    def __init__(self, pubsub: _PubSub | None = None) -> None:
        self._pubsub = pubsub

    def pubsub(self) -> _PubSub:
        assert self._pubsub is not None
        return self._pubsub


@pytest.mark.asyncio
async def test_subscribing_happens_on_entering_the_block_not_on_the_first_loop() -> None:
    """**Vào khối là đã nghe**, chưa cần lặp lần nào.

    `drafting.py` ghi lại một lần mất trọn vòng soạn đầu tiên vì thân một async generator
    không chạy cho tới lần lặp đầu. Pub/sub của Redis không giữ lịch sử, nên subscribe muộn
    một nhịp là mất hẳn tiếng hích của nhịp ấy. Test này đỏ vào đúng ngày ai đó đổi
    `open_changes` từ context manager thành generator.
    """
    pubsub = _PubSub([])
    async with open_changes(_Pool(pubsub), "gv-1"):
        assert pubsub.subscribed == ["documents:gv-1"]


@pytest.mark.asyncio
async def test_silence_and_a_nudge_are_told_apart() -> None:
    """Im lặng nhả `False`, có tin nhả `True`.

    Người gọi cần nhịp im lặng ấy để phát nhịp tim và để nhận ra lúc client ngắt kết nối. Một
    vòng lặp chỉ nhả khi có tin sẽ treo im cho tới tiếng hích kế tiếp, và lúc đó không ai biết
    nó còn sống hay không.
    """
    pubsub = _PubSub([None, {"data": b"1"}])
    heard = []
    async with open_changes(_Pool(pubsub), "gv-1") as changes:
        async for changed in changes:
            heard.append(changed)
            if len(heard) == 2:
                break
    assert heard == [False, True]


@pytest.mark.asyncio
async def test_a_broken_redis_ends_the_stream_instead_of_raising() -> None:
    """Redis gãy giữa lúc nghe thì thôi nghe, không ném.

    Một exception thoát ra đây sẽ cắt luôn response SSE đang mở, mà thứ duy nhất mất đi là
    việc tự mới lại.
    """
    pubsub = _PubSub([], explode=True)
    heard = []
    async with open_changes(_Pool(pubsub), "gv-1") as changes:
        async for changed in changes:
            heard.append(changed)
    assert heard == []


@pytest.mark.asyncio
async def test_no_queue_means_a_quiet_channel_not_a_broken_one() -> None:
    """Không có queue thì kênh im, và màn hình vẫn vẽ được thư viện nó đã đọc.

    Một bề mặt nghèo đi, không phải một bề mặt hỏng — cùng luật mà `be/main.py` đã chọn cho
    pha 2 khi queue chết.
    """
    async with open_changes(None, "gv-1") as changes:
        assert [one async for one in changes] == []
