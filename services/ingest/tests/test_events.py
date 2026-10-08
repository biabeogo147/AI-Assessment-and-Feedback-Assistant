"""Nửa **phát** của kênh hích thư viện tài liệu, và tên channel hai service cùng nói.

Nửa nghe -- `open_changes` -- được canh ở `services/be/tests/test_document_events.py`. Chia theo
người sở hữu code chứ không theo chủ đề: một test của `ingest` mà cần `be` import được là một
test nói rằng ranh giới không có thật.
"""

import pytest

from contracts import documents_channel
from ingest.events import announce


class _Pool:
    """Một pool Redis giả, chỉ biết publish."""

    def __init__(self) -> None:
        self.rang: list[tuple[str, str]] = []

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
async def test_announce_never_raises_even_when_nobody_can_hear() -> None:
    """`announce` chạy sau khi hàng đã ghi, nên nó không được phép làm job đỏ."""
    await announce(None, "gv-1")

    pool = _Pool()
    await announce(pool, "gv-1")
    assert pool.rang == [("documents:gv-1", "1")]
