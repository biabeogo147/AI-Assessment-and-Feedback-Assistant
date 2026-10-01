"""Truy cập queue cho BE.

BE đẩy việc vào queue theo tên task rồi đọc kết quả về qua chính result store của
arq. Nó không bao giờ import package AGENT: tên task là một hằng trong
`contracts`, nên hai service thống nhất với nhau trên một string chứ không phải
trên code.
"""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job, JobStatus

from be.config import Settings
from contracts import GRADE_SUBMISSION_TASK, GradingRequested

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


async def enqueue_grading(
    pool: ArqRedis,
    settings: Settings,
    request: GradingRequested,
) -> str:
    """Giao một bài nộp cho AGENT để chấm.

    Args:
        pool: Pool arq đã kết nối.
        settings: Settings của process, nơi cung cấp tên queue.
        request: Phần việc cần làm. Được serialise thành dict thuần, nhờ vậy payload
            trên đường truyền không phụ thuộc vào phiên bản pydantic mà mỗi bên chạy.

    Returns:
        job id của arq, thứ mà client poll để lấy kết quả.

    Raises:
        RuntimeError: Nếu arq từ chối job, chuyện xảy ra khi đã tồn tại một job cùng
            id.

    Side effects:
        Ghi một job lên queue Redis dùng chung.
    """
    job = await pool.enqueue_job(
        GRADE_SUBMISSION_TASK,
        request.model_dump(mode="json"),
        _queue_name=settings.agent_queue_name,
    )
    if job is None:
        raise RuntimeError(f"arq refused to enqueue submission {request.submission_id}")
    return job.job_id


async def read_job(pool: ArqRedis, settings: Settings, job_id: str) -> tuple[JobStatus, object]:
    """Đọc status hiện tại và kết quả của một job đã được đẩy vào queue trước đó.

    Args:
        pool: Pool arq đã kết nối.
        settings: Settings của process, nơi cung cấp tên queue.
        job_id: Identifier do enqueue_grading trả về.

    Returns:
        Một tuple gồm status của job và kết quả thô của nó. Kết quả là None cho tới
        khi job xong, và sau đó là đúng thứ AGENT đã trả về.
    """
    job = Job(job_id, redis=pool, _queue_name=settings.agent_queue_name)
    status = await job.status()
    info = await job.result_info()
    return status, (info.result if info is not None else None)
