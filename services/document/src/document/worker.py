"""Process worker arq của `services/document`.

Chạy bằng:  arq document.worker.WorkerSettings

Không có server HTTP và không có cổng. `architecture.md` dành cổng **8100** cho service thứ tư,
nhưng một cổng chỉ đáng mở khi có ai gọi vào -- mà kết quả đi về BE bằng một job trên queue của
BE, không bằng một request. Một cổng không ai gọi là một bề mặt không ai canh.

Một hạn chế đã biết trên Windows: arq đăng ký signal handler qua ``loop.add_signal_handler``,
và hàm đó raise NotImplementedError trên ProactorEventLoop. arq nuốt lỗi ấy và chỉ log ở mức
debug, nên worker vẫn chạy nhưng không tắt một cách êm đẹp -- Ctrl+C cắt ngang job đang chạy.
Chấp nhận được ở đây hơn ở AGENT: một job bị cắt ngang để lại một hàng đứng ở *đang xử lý*, và
BE suy ra *xử lý hỏng* khi nó đứng quá lâu.
"""

import logging

from arq.connections import RedisSettings
from arq.worker import func

from contracts import PROBE_DOCUMENT_TASK
from document.config import get_settings
from document.handlers import probe_document
from document.storage import create_reader

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

_settings = get_settings()

# arq mặc định timeout kết nối một giây, chặt quá so với Docker Desktop trên Windows: port proxy
# của nó cần vài giây sau khi container báo healthy mới chịu nhận connection, và worker thì thoát
# ngay lúc khởi động thay vì chờ.
_CONNECT_TIMEOUT_SECONDS = 5

# Trần thời gian cho một job. Đo được: quét 29 trang mất 31 ms, ngoại suy 400 trang khoảng 0,4
# giây. Hai phút là rộng gấp hàng trăm lần, và nó không phải để chờ việc -- nó để một tệp bệnh
# hoạn làm `pymupdf` quay vòng vẫn có chỗ dừng, thay vì giữ một slot của worker vĩnh viễn.
_JOB_TIMEOUT_SECONDS = 120


def _redis_settings() -> RedisSettings:
    """Dựng RedisSettings cho arq với timeout kết nối phù hợp môi trường này.

    Returns:
        RedisSettings worker dùng được ngay.
    """
    parsed = RedisSettings.from_dsn(_settings.redis_url)
    parsed.conn_timeout = _CONNECT_TIMEOUT_SECONDS
    return parsed


async def startup(ctx: dict) -> None:
    """Dựng reader một lần cho cả process, và nói ra worker đang tiêu thụ queue nào.

    Dòng log không phải lời chào: nếu tên queue của BE và của service này lệch nhau thì hệ thống
    trông **y hệt một hệ thống đang rảnh** -- job được đẩy vào, không có lỗi nào, và không gì
    chạy. Hai cái tên in cạnh nhau là cách duy nhất thấy được điều đó mà không phải mở Redis.

    `create_reader` không chạm mạng, nên MinIO chưa lên cũng không làm worker chết ở đây. Lần đọc
    đầu tiên mới là lúc biết, và lúc ấy một job hỏng là một kết quả gửi về cho BE.

    Args:
        ctx: Context worker của arq. Nhận thêm khoá `reader`.

    Side effects:
        Ghi một dòng log, và đặt `reader` vào ctx.
    """
    ctx["reader"] = create_reader(_settings)
    logger.info(
        "DOCUMENT worker ready: consuming=%s handing back to=%s redis=%s",
        _settings.document_queue_name,
        _settings.ingest_queue_name,
        _settings.redis_url,
    )


class WorkerSettings:
    """Cấu hình worker của arq.

    Task đăng ký dưới hằng số lấy từ `contracts` chứ không dưới tên hàm Python, nhờ vậy việc đổi
    tên hàm không thể âm thầm làm hỏng lời gọi enqueue của BE.
    """

    functions = [func(probe_document, name=PROBE_DOCUMENT_TASK)]
    queue_name = _settings.document_queue_name
    redis_settings = _redis_settings()
    job_timeout = _JOB_TIMEOUT_SECONDS
    # Không giữ kết quả. Khác AGENT, ở đây **không ai đọc** kết quả một job: câu trả lời đi về
    # bằng một job khác trên queue của BE. Giữ lại chỉ là rác trong Redis, và tệ hơn, nó mời
    # người đọc sau tưởng rằng có một đường poll -- đúng cái bẫy mà `drafting.py` đã ghi lại.
    keep_result = 0
    on_startup = startup
