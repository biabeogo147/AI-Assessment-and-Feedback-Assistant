"""Process worker arq thứ hai của `services/document`: *document agent* dựng cây
(`document-agent-hierarchy`, D4).

Chạy bằng:  arq document.index_worker.WorkerSettings   (`.\\dev.ps1 index`)

Tách khỏi `document.ocr_worker` vì hai việc khác nhau ở đúng chỗ quyết định cấu hình worker. OCR
ăn hết CPU, nên worker ấy chạy **một job một lúc** và nạp ba model lúc khởi động. Dựng cây thì
**chờ mạng** -- Jev, `gpt-5.6-luna`, `gpt-4o-mini` -- nên chạy vài job song song và không nạp
model nào. Cùng một worker thì hoặc OCR tranh CPU, hoặc cây chờ sau mọi lô OCR đang xếp hàng.

Riêng với Kriky (`services/agent`): khác queue, khác prompt, khác model.
"""

import asyncio
import logging

from arq.worker import func

from contracts import INDEX_DOCUMENT_TASK
from document.config import get_settings
from document.content_store import ContentStore
from document.index.llm import claude_options, model_for
from document.index_handlers import index_document
from document.ocr_handlers import MAX_TRIES
from document.ocr_worker import _redis_settings
from document.storage import create_reader

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

_settings = get_settings()

# Trần thời gian cho một job dựng cây. Đo trên Lớp 6 tập 1 (125 trang): Jev 7,6 s cho 492 ứng viên;
# luna ~2 s mỗi banner; tóm tắt ~90 nút với 8 lời gọi song song. Mười phút rộng gấp nhiều lần, và
# `DocumentProgress` gửi ở mỗi chặng giữ chip khỏi *xử lý hỏng* trong lúc chờ.
_JOB_TIMEOUT_SECONDS = 600


async def startup(ctx: dict) -> None:
    """Mở kho nội dung, reader của object storage, và hai chat model.

    Mongo chưa lên thì worker chết ở đây, cùng lý do `document.ocr_worker`: một job không ghi được
    cây là một job phải ném rồi chờ.

    Args:
        ctx: Context worker của arq. Nhận `store`, `reader`, `jev_limit`, `banner_model`,
            `summary_model`.

    Raises:
        Exception: Khi Mongo không với tới được.
    """
    ctx["reader"] = create_reader(_settings)
    store = ContentStore(_settings.mongo_url, _settings.mongo_database)
    await store.prepare()
    ctx["store"] = store
    # Một trần lời gọi Jev cho **cả** worker, không mỗi job một trần: `max_jobs` job song song nhân
    # trần ấy lên (review Task 4, `document-agent-hierarchy`).
    ctx["jev_limit"] = asyncio.Semaphore(_settings.jev_concurrency)
    # Mỗi model cầm khoá của provider nó chọn (`claude-provider-option`); thiếu khoá thì chỉ model
    # ấy tắt, và handler đi đường không có nó như trước.
    banner = model_for(
        _settings, _settings.banner_provider, _settings.banner_model, reasoning_effort="low"
    )
    summary = model_for(_settings, _settings.summary_provider, _settings.summary_model)
    if banner is not None:
        ctx["banner_model"] = banner
    if summary is not None:
        ctx["summary_model"] = summary
    claude = ""
    if "anthropic" in {_settings.summary_provider, _settings.banner_provider}:
        options = claude_options(_settings.llm_thinking, _settings.llm_effort)
        claude = f" claude={options or 'model defaults'}"
    logger.info(
        "DOCUMENT INDEX worker ready: consuming=%s handing back to=%s jev=%s summary=%s "
        "banner=%s%s",
        _settings.document_index_queue_name,
        _settings.ingest_queue_name,
        _settings.jev_model if _settings.jev_api_key else "off (rules only)",
        f"{_settings.summary_provider}/{_settings.summary_model}" if summary else "off",
        f"{_settings.banner_provider}/{_settings.banner_model}" if banner else "off",
        claude,
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
    """Cấu hình worker dựng cây."""

    functions = [func(index_document, name=INDEX_DOCUMENT_TASK)]
    queue_name = _settings.document_index_queue_name
    redis_settings = _redis_settings()
    job_timeout = _JOB_TIMEOUT_SECONDS
    # Vài cuốn song song: mỗi job phần lớn thời gian chờ Jev và OpenAI, không chờ CPU.
    max_jobs = 4
    max_tries = MAX_TRIES
    keep_result = 0
    on_startup = startup
    on_shutdown = shutdown
