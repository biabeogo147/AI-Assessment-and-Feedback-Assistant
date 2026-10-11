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
    loaded = object()
    monkeypatch.setattr(worker, "_page_reader", lambda _settings: loaded)
    ctx: dict = {}

    await worker.startup(ctx)
    [store] = _Store.made
    assert ctx["store"] is store
    assert store.prepared
    assert "reader" in ctx
    # Model OCR nạp một lần ở đây, không ở lô đầu.
    assert ctx["ocr"] is loaded

    await worker.shutdown(ctx)
    assert store.closed
    assert worker.WorkerSettings.on_shutdown is worker.shutdown


def test_the_worker_runs_both_tasks_one_at_a_time() -> None:
    """Hai task trên một queue, và **một job một lúc**: hai lô OCR song song chỉ tranh CPU rồi cùng
    chạm trần `job_timeout` (plan 3b, D3).
    """
    names = {function.name for function in worker.WorkerSettings.functions}
    assert names == {"probe_document", "ocr_pages"}
    assert worker.WorkerSettings.max_jobs == 1
