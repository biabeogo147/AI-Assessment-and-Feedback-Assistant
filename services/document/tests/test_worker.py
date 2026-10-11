"""Vòng đời của worker: kho nội dung mở lúc khởi động, đóng lúc tắt."""

import pytest

from document import worker


class _Store:
    """Kho nội dung giả, ghi lại nó đã được làm gì."""

    made: list["_Store"] = []

    def __init__(self, url: str, database: str) -> None:
        self.database = database
        self.prepared = False
        self.closed = False
        _Store.made.append(self)

    async def prepare(self) -> None:
        """Ghi lại rằng index đã được tạo."""
        self.prepared = True

    async def close(self) -> None:
        """Ghi lại rằng pool đã đóng."""
        self.closed = True


@pytest.mark.asyncio
async def test_startup_touches_the_store_and_shutdown_closes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`prepare` lúc khởi động là cách worker chết **trước** job đầu khi Mongo không với tới --
    bỏ nó thì lỗi đến kèm tài liệu đầu tiên của một giáo viên.
    """
    _Store.made.clear()
    monkeypatch.setattr(worker, "ContentStore", _Store)
    ctx: dict = {}

    await worker.startup(ctx)
    [store] = _Store.made
    assert ctx["store"] is store
    assert store.prepared
    assert "reader" in ctx

    await worker.shutdown(ctx)
    assert store.closed
    assert worker.WorkerSettings.on_shutdown is worker.shutdown
