"""Process worker arq của BE.

Chạy bằng:  arq be.worker.WorkerSettings

**Process thứ hai của BE**, và cái đầu tiên. Cho tới ngày 08/10/2026 BE chỉ đẩy job rồi đọc kết
quả về ngay trong request; `be/queue.py` không có một handler nào. Vòng xử lý tài liệu phá hình
dạng ấy vì không ai chờ nó: giáo viên đã rời màn hình, và kết quả vẫn phải vào database.

Tách khỏi process API chứ không nhúng vào `lifespan` của uvicorn, và lý do rất cụ thể: `dev.ps1
be` chạy uvicorn với `--reload`, nên mỗi lần sửa một file Python là một lần worker bị cắt ngang
giữa job. Nó cũng làm `--workers N` ngày sau thành N worker cùng tiêu thụ một queue mà không ai
chủ ý.

Nó **không** `prepare_schema`. Dựng schema là việc của process API; ở đây chỉ `check_schema`,
vì một worker chạy êm trên schema lệch sẽ hỏng ở lần `UPDATE` đầu tiên, cách rất xa nguyên nhân.

Một hạn chế đã biết trên Windows: arq không đăng ký được signal handler, nên Ctrl+C cắt ngang
job đang chạy. Ở đường này nó để lại một tài liệu đứng ở *đang xử lý*, và BE suy ra *xử lý hỏng*
khi nó đứng quá lâu -- xem `teacher_documents.py`.
"""

import logging

from arq.connections import RedisSettings
from arq.worker import func

from be.config import get_settings
from be.db import bind_sessions, check_schema, create_engine
from be.ingest import document_probed
from be.queue import redis_settings
from contracts import DOCUMENT_PROBED_TASK

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

_settings = get_settings()


def _redis_settings() -> RedisSettings:
    """Dựng RedisSettings cho worker.

    Dùng lại `be.queue.redis_settings` chứ không viết lại: timeout kết nối năm giây ở đó có một
    lý do đo được về Docker Desktop trên Windows, và hai bản sao sẽ lệch nhau vào ngày ai đó sửa
    một bản.

    Returns:
        RedisSettings worker dùng được ngay.
    """
    return redis_settings(_settings)


async def startup(ctx: dict) -> None:
    """Mở engine cho cả process, kiểm schema, rồi nói ra đang tiêu thụ queue nào.

    Args:
        ctx: Context worker của arq. Nhận thêm khoá `db_engine` để shutdown đóng được nó.

    Side effects:
        Mở một database engine và đặt session factory ở mức module.

    Raises:
        SchemaDrifted: Khi database đang có thiếu cột so với model. Worker dừng ở đây kèm tên
            cột và lệnh dựng lại, cùng hình dạng với `be/main.py`.
    """
    engine = create_engine(_settings)
    await check_schema(engine)
    bind_sessions(engine)
    ctx["db_engine"] = engine
    logger.info(
        "BE worker ready: queue=%s redis=%s",
        _settings.be_queue_name,
        _settings.redis_url,
    )


async def shutdown(ctx: dict) -> None:
    """Đóng engine.

    Args:
        ctx: Context worker của arq.

    Side effects:
        Trả mọi connection về. Trên Windows arq không tắt êm được, nên đừng dựa vào hàm này
        chạy sau Ctrl+C.
    """
    engine = ctx.pop("db_engine", None)
    if engine is not None:
        await engine.dispose()


class WorkerSettings:
    """Cấu hình worker của arq.

    Task đăng ký dưới hằng số lấy từ `contracts`, nên đổi tên hàm Python không làm hỏng lời gọi
    enqueue của `services/document`.
    """

    functions = [func(document_probed, name=DOCUMENT_PROBED_TASK)]
    queue_name = _settings.be_queue_name
    redis_settings = _redis_settings()
    # Không giữ kết quả: không ai đọc chúng. Kết quả của một job ghi database là chính cái hàng
    # đã được ghi.
    keep_result = 0
    on_startup = startup
    on_shutdown = shutdown
