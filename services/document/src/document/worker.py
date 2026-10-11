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

import asyncio
import logging

from arq.connections import RedisSettings
from arq.worker import func

from contracts import OCR_PAGES_TASK, PROBE_DOCUMENT_TASK
from document.config import Settings, get_settings
from document.content_store import ContentStore
from document.handlers import MAX_TRIES, ocr_pages, probe_document
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
#
# Từ plan 3b nó cũng là trần của **một lô OCR**: `ocr_pages_per_job` trang × 4,5 s/trang (đo ở plan
# 3a) = ~45 s với mặc định 10. Tăng số trang mỗi lô thì xem lại con số này trước.
_JOB_TIMEOUT_SECONDS = 120


def _redis_settings() -> RedisSettings:
    """Dựng RedisSettings cho arq với timeout kết nối phù hợp môi trường này.

    Returns:
        RedisSettings worker dùng được ngay.
    """
    parsed = RedisSettings.from_dsn(_settings.redis_url)
    parsed.conn_timeout = _CONNECT_TIMEOUT_SECONDS
    return parsed


def _page_reader(settings: Settings) -> object:
    """Nạp ba model OCR. Sync và chậm (5-6 s đo ở plan 3a), người gọi đặt nó vào một thread.

    Import **ở trong hàm**, không ở đầu module: `document.ocr` nạp torch và paddle, vài giây và
    vài trăm MB. Đặt ở đầu thì mọi test chạm `worker` -- kể cả test vòng đời không cần model nào
    -- trả cái giá ấy, và không thay được hàm này bằng một bản giả.

    Args:
        settings: Setting của worker.

    Returns:
        Một `PageReader` đã nạp model.
    """
    from document.ocr.page import PageReader

    return PageReader(reader=settings.ocr_reader, threads=settings.ocr_threads)


async def startup(ctx: dict) -> None:
    """Dựng reader một lần cho cả process, và nói ra worker đang tiêu thụ queue nào.

    Dòng log không phải lời chào: nếu tên queue của BE và của service này lệch nhau thì hệ thống
    trông **y hệt một hệ thống đang rảnh** -- job được đẩy vào, không có lỗi nào, và không gì
    chạy. Hai cái tên in cạnh nhau là cách duy nhất thấy được điều đó mà không phải mở Redis.

    `create_reader` không chạm mạng, nên MinIO chưa lên cũng không làm worker chết ở đây. Lần đọc
    đầu tiên mới là lúc biết, và lúc ấy một job hỏng là một kết quả gửi về cho BE.

    Kho nội dung thì **ngược lại**, có chủ ý: `prepare` chạm Mongo ngay, và Mongo chưa lên thì
    worker chết ở đây. Một tệp không đọc được là kết quả nói được với giáo viên; còn một kho không
    ghi được thì mọi tệp có chữ đều phải ném rồi chờ arq thử lại -- tốt hơn là không nhận job nào.

    Model OCR nạp **một lần ở đây**, không ở lô đầu: nạp mất vài giây, và trả cái giá ấy cho mỗi
    lô là trả nó hai mươi lần cho một cuốn sách.

    Args:
        ctx: Context worker của arq. Nhận thêm khoá `reader`, `store` và `ocr`.

    Raises:
        Exception: Khi Mongo không với tới được, hoặc model OCR không nạp được.

    Side effects:
        Ghi một dòng log, đặt `reader`, `store` và `ocr` vào ctx, tạo index của kho nội dung.
    """
    ctx["reader"] = create_reader(_settings)
    store = ContentStore(_settings.mongo_url, _settings.mongo_database)
    await store.prepare()
    ctx["store"] = store
    ctx["ocr"] = await asyncio.to_thread(_page_reader, _settings)
    logger.info(
        "DOCUMENT worker ready: consuming=%s handing back to=%s redis=%s content=%s",
        _settings.document_queue_name,
        _settings.ingest_queue_name,
        _settings.redis_url,
        _settings.mongo_database,
    )


async def shutdown(ctx: dict) -> None:
    """Đóng pool kết nối của kho nội dung.

    Args:
        ctx: Context worker của arq.
    """
    store = ctx.get("store")
    if store is not None:
        await store.close()


class WorkerSettings:
    """Cấu hình worker của arq.

    Task đăng ký dưới hằng số lấy từ `contracts` chứ không dưới tên hàm Python, nhờ vậy việc đổi
    tên hàm không thể âm thầm làm hỏng lời gọi enqueue của BE.
    """

    functions = [
        func(probe_document, name=PROBE_DOCUMENT_TASK),
        func(ocr_pages, name=OCR_PAGES_TASK),
    ]
    queue_name = _settings.document_queue_name
    redis_settings = _redis_settings()
    job_timeout = _JOB_TIMEOUT_SECONDS
    # **Một job một lúc** (plan 3b, D3). OCR dùng hết `ocr_threads` luồng CPU, nên hai lô chạy
    # cùng lúc chỉ tranh nhau rồi cùng chậm -- và một lô chậm gấp đôi là một lô chạm trần
    # `job_timeout`. Mặc định của arq là 10.
    #
    # Cái giá, và nó lớn dần theo số cuốn scan đang đọc cùng lúc (`k`): lô kế của mỗi cuốn xếp
    # cuối queue, nên các cuốn đọc **xen nhau**, và khoảng giữa hai tiếng báo tiến độ của một cuốn
    # là chừng `k` × 45 s. Từ khoảng `k` = 7 (hoặc 4 với trang dày chữ), khoảng ấy vượt ngưỡng
    # 300 s và BE đọc **mọi** cuốn đang đọc ra *xử lý hỏng* cùng lúc. Một lần dò tệp có chữ cũng
    # chờ chừng ấy. Chấp nhận cho một giáo viên ở local; nợ ghi ở `backlog.md`.
    max_jobs = 1
    # Đúng mặc định của arq. Lấy từ `handlers` vì `ocr_pages` cần biết lần thử nào là lần cuối, và
    # `handlers._RETRY_STEP_SECONDS` tính tổng thời gian chờ từ con số này.
    max_tries = MAX_TRIES
    # Không giữ kết quả. Khác AGENT, ở đây **không ai đọc** kết quả một job: câu trả lời đi về
    # bằng một job khác trên queue của BE. Giữ lại chỉ là rác trong Redis, và tệ hơn, nó mời
    # người đọc sau tưởng rằng có một đường poll -- đúng cái bẫy mà `drafting.py` đã ghi lại.
    keep_result = 0
    on_startup = startup
    on_shutdown = shutdown
