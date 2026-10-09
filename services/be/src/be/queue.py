"""Truy cập queue cho BE.

BE đẩy việc vào queue theo tên task rồi đọc kết quả về qua chính result store của
arq. Nó không bao giờ import package AGENT: tên task là một hằng trong
`contracts`, nên hai service thống nhất với nhau trên một string chứ không phải
trên code.
"""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

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
