"""Truy cập queue cho BE.

BE đẩy việc vào queue theo tên task rồi đọc kết quả về qua chính result store của
arq. Nó không bao giờ import package AGENT: tên task là một hằng trong
`contracts`, nên hai service thống nhất với nhau trên một string chứ không phải
trên code.
"""

import asyncio

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job, JobStatus

from be.config import Settings
from contracts import (
    PROBE_DOCUMENT_TASK,
    DocumentProbeRequested,
)

# arq mặc định timeout kết nối một giây, và mức đó quá chặt với Docker Desktop
# trên Windows: port proxy của nó cần vài giây sau khi container báo healthy mới
# chịu nhận kết nối, nên process chết ngay lúc startup thay vì chờ.
_CONNECT_TIMEOUT_SECONDS = 5


def redis_settings(settings: Settings) -> RedisSettings:
    """Dựng settings Redis cho arq với timeout kết nối phù hợp môi trường này.

    Args:
        settings: Settings của process, nơi cung cấp Redis DSN.

    Returns:
        RedisSettings sẵn sàng để đưa cho arq.
    """
    parsed = RedisSettings.from_dsn(settings.redis_url)
    parsed.conn_timeout = _CONNECT_TIMEOUT_SECONDS
    return parsed


async def create_queue_pool(settings: Settings) -> ArqRedis:
    """Mở connection pool Redis mà arq dùng để đẩy job và đọc kết quả.

    Args:
        settings: Settings của process, nơi cung cấp Redis DSN.

    Returns:
        Một pool ArqRedis đã kết nối. Người gọi sở hữu nó và phải đóng nó.

    Raises:
        OSError: Nếu không tới được Redis. Khởi nó bằng
            `docker compose -f docker-compose.infra.yml up -d`. redis-py ném
            ConnectionError riêng của nó, mà cái đó không phải OSError; ở đây nó
            được dịch sang OSError để người gọi xử lý được tình huống "queue chết"
            mà không phải import redis, một library BE chỉ có vì arq mang theo.
    """
    try:
        return await create_pool(redis_settings(settings))
    except Exception as exc:  # noqa: BLE001 -- đã thu hẹp lại bằng cách ném lại thành OSError
        raise OSError(f"Redis unreachable at {settings.redis_url}: {exc}") from exc


async def enqueue_probe(
    pool: ArqRedis,
    settings: Settings,
    request: DocumentProbeRequested,
) -> str:
    """Giao một tài liệu vừa cất cho `services/document` đọc.

    Khác mọi lời gọi qua `agent_gateway` ở một điểm đáng nói: **không ai sẽ đọc kết quả
    của job này**.
    Câu trả lời đi về bằng một job khác, trên queue của `services/ingest`, và service ấy
    ghi nó vào database. Đó là lý do hàm này trả job id nhưng không ai giữ nó -- nó vào log, để một
    lần truy vết còn nối được hai đầu.

    Args:
        pool: Pool arq đã kết nối.
        settings: Settings của process, nơi cung cấp tên queue.
        request: Khoá của object và tên tệp. Không chở byte: trần một tệp là 100 MB, và
            Redis không phải chỗ để chuyên chở một cuốn sách.

    Returns:
        job id của arq.

    Raises:
        RuntimeError: Nếu arq từ chối job.

    Side effects:
        Ghi một job lên queue Redis mà `services/document` tiêu thụ.
    """
    job = await pool.enqueue_job(
        PROBE_DOCUMENT_TASK,
        request.model_dump(mode="json"),
        _queue_name=settings.document_queue_name,
    )
    if job is None:
        raise RuntimeError(f"arq refused to enqueue document {request.document_id}")
    return job.job_id


# Nhịp hỏi trạng thái một job đang chờ. Chung cho AGENT và `services/document`.
POLL_SECONDS = 0.2


class JobFailed(RuntimeError):
    """Một job BE đang chờ không cho ra kết quả: queue từ chối, hết giờ, hay job hỏng."""


async def run_job(
    pool: ArqRedis,
    queue_name: str,
    task_name: str,
    payload: dict,
    timeout: float,
    job_id: str | None = None,
) -> dict:
    """Đẩy một job rồi chờ kết quả của nó, có trần.

    Một chỗ cho mọi lần BE chờ một job: lượt chat chờ AGENT (`agent_gateway.run_task`), và
    `read_section` chờ `services/document` đọc công thức (`formulas-on-demand`). Worker phải giữ
    kết quả (`keep_result`), không thì job xong mà không ai đọc được gì.

    Args:
        pool: Pool arq đã kết nối.
        queue_name: Queue của bên tiêu thụ.
        task_name: Một hằng tên task trong `contracts`.
        payload: Message yêu cầu đã serialise.
        timeout: Trần giây chờ.
        job_id: Id cố định khi hai lần xin giống nhau phải gặp **một** job: arq từ chối job thứ hai
            cùng id, và lần xin sau chờ chính job đang chạy thay vì bắn thêm một lần.

    Returns:
        Kết quả của job.

    Raises:
        JobFailed: Khi queue từ chối, job không xong trong `timeout`, hay job hỏng.

    Side effects:
        Ghi một job lên queue Redis.
    """
    fixed = {} if job_id is None else {"_job_id": job_id}
    job = await pool.enqueue_job(task_name, payload, _queue_name=queue_name, **fixed)
    if job is None and job_id is not None:
        job = Job(job_id, redis=pool, _queue_name=queue_name)
    if job is None:
        raise JobFailed(f"arq refused task {task_name}")

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        status = await job.status()
        if status is JobStatus.complete:
            finished = Job(job.job_id, redis=pool, _queue_name=queue_name)
            info = await finished.result_info()
            if info is None or not info.success:
                raise JobFailed(f"task {task_name} failed")
            return info.result
        await asyncio.sleep(POLL_SECONDS)
    raise JobFailed(f"task {task_name} did not finish in {timeout}s")
