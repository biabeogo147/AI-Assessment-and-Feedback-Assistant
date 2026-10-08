"""Kênh hích của thư viện tài liệu.

Hai luật đáng canh ở đây, và cả hai đều là bài học `drafting.py` đã trả giá để biết: subscribe
phải xảy ra **lúc vào khối** chứ không phải lúc lặp lần đầu, và một Redis gãy giữa chừng không
được phép ném ngược ra ngoài.
"""

import pytest

from be.document_events import announce, documents_channel, open_changes


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
    """Một pool Redis giả, chỉ biết mở pubsub và publish."""

    def __init__(self, pubsub: _PubSub | None = None) -> None:
        self._pubsub = pubsub
        self.rang: list[tuple[str, str]] = []

    def pubsub(self) -> _PubSub:
        assert self._pubsub is not None
        return self._pubsub

    async def publish(self, channel: str, message: str) -> None:
        self.rang.append((channel, message))


def test_the_channel_is_named_after_the_teacher_not_the_document() -> None:
    """Một channel cho mỗi giáo viên.

    Rail vẽ **cả thư viện**, nên một màn hình đang mở là một subscription. Một channel cho mỗi
    tài liệu bắt trình duyệt đăng ký N kênh và huỷ từng cái khi chúng xong — N lần phức tạp cho
    đúng một thông tin.
    """
    assert documents_channel("gv-1") == "documents:gv-1"


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


@pytest.mark.asyncio
async def test_announce_never_raises_even_when_nobody_can_hear() -> None:
    """`announce` chạy sau khi hàng đã ghi, nên nó không được phép làm job đỏ."""
    await announce(None, "gv-1")

    pool = _Pool()
    await announce(pool, "gv-1")
    assert pool.rang == [("documents:gv-1", "1")]
