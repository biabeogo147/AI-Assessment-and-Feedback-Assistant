"""`queue.run_job`: một chỗ cho mọi lần BE chờ một job (`formulas-on-demand`).

Không Redis thật: pool và `Job` là bản giả, đủ cho ba nhánh -- job mới, id đã có, hết giờ.
"""

from types import SimpleNamespace

import pytest
from arq.jobs import JobStatus

from be import queue
from be.queue import JobFailed, run_job


class _Job:
    """Job giả: xong ngay, kết quả mang id của nó để test biết đã đọc job nào."""

    status_of = JobStatus.complete

    def __init__(self, job_id: str, redis: object = None, _queue_name: str = "") -> None:
        self.job_id = job_id

    async def status(self) -> JobStatus:
        return self.status_of

    async def result_info(self) -> SimpleNamespace:
        return SimpleNamespace(success=True, result={"from": self.job_id})


class _Pool:
    def __init__(self, accepts: bool) -> None:
        self.accepts = accepts
        self.enqueued: list[dict] = []

    async def enqueue_job(self, task: str, payload: dict, **kwargs: object) -> _Job | None:
        self.enqueued.append(kwargs)
        return _Job(str(kwargs.get("_job_id", "fresh"))) if self.accepts else None


@pytest.fixture(autouse=True)
def fake_job(monkeypatch):
    monkeypatch.setattr(queue, "Job", _Job)
    monkeypatch.setattr(queue, "POLL_SECONDS", 0.01)
    _Job.status_of = JobStatus.complete


@pytest.mark.asyncio
async def test_a_task_without_a_fixed_id_never_sends_one() -> None:
    """Pool giả của các test khác không nhận `_job_id`; `run_task` không truyền nó."""
    pool = _Pool(accepts=True)

    assert await run_job(pool, "q", "t", {}, 1.0) == {"from": "fresh"}
    assert "_job_id" not in pool.enqueued[0]


@pytest.mark.asyncio
async def test_a_fixed_id_already_queued_waits_on_that_job() -> None:
    """arq từ chối id đang có: lần xin thứ hai chờ chính job ấy, không báo hỏng."""
    pool = _Pool(accepts=False)

    assert await run_job(pool, "q", "t", {}, 1.0, job_id="formulas:d:1") == {"from": "formulas:d:1"}


@pytest.mark.asyncio
async def test_a_refused_task_without_an_id_fails() -> None:
    with pytest.raises(JobFailed):
        await run_job(_Pool(accepts=False), "q", "t", {}, 1.0)


@pytest.mark.asyncio
async def test_a_job_that_does_not_finish_in_time_fails() -> None:
    _Job.status_of = JobStatus.in_progress

    with pytest.raises(JobFailed, match="did not finish"):
        await run_job(_Pool(accepts=True), "q", "t", {}, 0.05)
