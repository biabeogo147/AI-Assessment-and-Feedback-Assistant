"""Job dựng cây của một tài liệu đã có bản thô, rồi báo nó *sẵn sàng* (plan 3c, D3).

Chạy trên `document.index_worker`, queue riêng -- không phải worker OCR (D4). Thứ tự là hợp đồng:
cây vào Mongo **trước**, `DocumentProbed(READY)` rời service **sau** (*"chunk trước, `state` sau"*).

Ba cách kết thúc khác `READY`, mỗi cái một lý do:

- **Kho nội dung hay Redis chập chờn** → `Retry`, như mọi job khác của service này. Một lần chạy lại
  mà cây **đã** ghi trọn cho đúng bản thô hiện tại thì **không** dựng lại: chỉ gửi lại `READY` --
  dựng lại là trả tiền Jev và OpenAI lần nữa cho đúng cái cây đã có.
- **Bản thô bị đọc lại giữa chừng, hoặc chưa đọc xong** (`RawChanged`) → lần đọc mới đã xong thì
  chạy lại trên bản mới; còn đang đọc thì bỏ, lô OCR cuối sẽ giao job dựng cây sau.
- **Mọi lỗi khác**, kể cả hết `INDEX_BUDGET_SECONDS` → gửi `FAILED` kèm một câu giáo viên đọc được:
  arq không chạy lại chúng, và một job chết im là một chip đứng *đang xử lý* 300 s.
- **Không có bản thô** (`NothingToIndex`) → bỏ, không gửi gì: DB vừa dựng lại hoặc tài liệu đã xoá;
  phép suy *đứng quá lâu* của BE là lưới.
"""

import asyncio
import logging

from contracts import (
    DOCUMENT_PROGRESS_TASK,
    DocumentIndexRequested,
    DocumentProbed,
    DocumentProgress,
    DocumentState,
)
from document.config import get_settings
from document.content_store import ContentStoreUnavailable, RawChanged
from document.index.graph import Deps, NothingToIndex, build
from document.index.jev import JevClassifier
from document.index.llm import read_banner, summarise
from document.ocr_handlers import HandBackFailed, _hand_back, _retry, _send

logger = logging.getLogger(__name__)

# Ngân sách giờ của một job dựng cây, **dưới** `job_timeout` (600 s) của `index_worker`: hết ngân
# sách thì job tự gửi `FAILED`, còn chạm `job_timeout` thì arq giết job và không ai gửi gì.
INDEX_BUDGET_SECONDS = 540


async def index_document(ctx: dict, payload: dict) -> dict:
    """Dựng cây cho một tài liệu, ghi nó, rồi báo tài liệu *sẵn sàng*.

    Args:
        ctx: Context worker của arq: `store`, `reader`, `redis`, và hai chat model `banner_model`,
            `summary_model` (`None` khi không có khoá OpenAI).
        payload: `DocumentIndexRequested` đã serialise.

    Returns:
        Kết quả, cho log của job.

    Raises:
        Retry: Khi kho nội dung hay Redis không với tới được.
    """
    asked = DocumentIndexRequested.model_validate(payload)
    settings = get_settings()
    store = ctx["store"]
    jev = (
        JevClassifier(
            settings.jev_api_key,
            settings.jev_model,
            settings.jev_concurrency,
            settings.jev_timeout_seconds,
            ctx.get("jev_limit"),
        )
        if settings.jev_api_key
        else None
    )
    try:
        # Tự cắt **trước** `job_timeout` của arq: arq giết job chạm trần mà không chạy lại, và một
        # job bị giết thì không gửi được gì -- chip chờ 300 s rồi ra *xử lý hỏng* với câu chung
        # chung. Tự cắt thì còn kịp gửi `FAILED` kèm lý do (review Task 4).
        async with asyncio.timeout(INDEX_BUDGET_SECONDS):
            if await _already_indexed(store, asked.document_id):
                logger.info("document=%s already has its index; handing back", asked.document_id)
            else:
                graph = build(_deps(ctx, asked, jev))
                await graph.ainvoke({"asked": asked})
        await _hand_back(
            ctx["redis"],
            DocumentProbed(
                document_id=asked.document_id,
                state=DocumentState.READY,
                page_count=asked.page_count,
            ),
        )
    except (ContentStoreUnavailable, HandBackFailed) as exc:
        raise _retry(ctx, exc) from exc
    except RawChanged:
        return await _raw_changed(ctx, asked)
    except NothingToIndex:
        logger.warning("document=%s has no raw content to index", asked.document_id)
        return {"document_id": asked.document_id, "dropped": "no raw content"}
    except Exception:
        # Lỗi lập trình, lỗi LangGraph, hết ngân sách giờ: arq không chạy lại chúng, nên đây là
        # chỗ cuối để chip không đứng *đang xử lý* trong im lặng (`services/document/AGENTS.md`).
        logger.exception("could not build the index of %s", asked.document_id)
        return await _give_up(ctx, asked)
    finally:
        if jev is not None:
            await jev.aclose()
    return {"document_id": asked.document_id, "state": DocumentState.READY.value}


async def _raw_changed(ctx: dict, asked: DocumentIndexRequested) -> dict:
    """Bản thô đã đổi dưới chân job: đọc lại xong rồi thì **chạy lại**, đang đọc dở thì bỏ.

    Chạy lại chứ không bỏ khi lần đọc mới đã xong (review Task 4): job dựng cây mang id cố định
    `index:<doc>`, nên lần đọc mới giao job của nó trong lúc job này còn chạy thì bị **từ chối** --
    bỏ ở đây là không còn ai dựng cây. Còn khi lần đọc mới chưa xong, lô OCR cuối của nó sẽ giao
    job sau khi job này đã nhả id.

    Args:
        ctx: Context worker.
        asked: Job đang chạy.

    Returns:
        Kết quả cho log khi bỏ.

    Raises:
        Retry: Khi bản thô mới đã đọc xong, hoặc Mongo không đọc được.
    """
    try:
        raw = await ctx["store"].raw(asked.document_id)
    except ContentStoreUnavailable as exc:
        raise _retry(ctx, exc) from exc
    if raw is not None and raw.finished_at is not None:
        raise _retry(
            ctx, RawChanged(f"{asked.document_id} was read again; building on the new read")
        )
    logger.info("document=%s is being read again; its last batch will queue it", asked.document_id)
    return {"document_id": asked.document_id, "dropped": "raw changed"}


async def _give_up(ctx: dict, asked: DocumentIndexRequested) -> dict:
    """Gửi `FAILED` kèm một câu giáo viên đọc được.

    Args:
        ctx: Context worker.
        asked: Job đang chạy.

    Returns:
        Kết quả cho log.

    Raises:
        Retry: Khi không gửi được về BE.
    """
    failed = DocumentProbed(
        document_id=asked.document_id,
        state=DocumentState.FAILED,
        page_count=asked.page_count,
        fault="Đã đọc được chữ nhưng chưa dựng được mục lục. Thử tải lại tệp.",
    )
    try:
        await _hand_back(ctx["redis"], failed)
    except HandBackFailed as exc:
        raise _retry(ctx, exc) from exc
    return {"document_id": asked.document_id, "state": DocumentState.FAILED.value}


async def _already_indexed(store, document_id: str) -> bool:
    """Cây đã ghi trọn cho **đúng** bản thô hiện tại chưa.

    Args:
        store: Kho nội dung.
        document_id: Tài liệu.

    Returns:
        True khi có đầu mục cây và nó mang mốc của bản thô đang có.

    Raises:
        ContentStoreUnavailable: Khi Mongo không đọc được.
    """
    header = await store.indexed(document_id)
    raw = await store.raw(document_id)
    if header is None or raw is None or raw.finished_at is None:
        return False
    return header.raw_started_at == raw.started_at


def _deps(ctx: dict, asked: DocumentIndexRequested, jev: JevClassifier | None) -> Deps:
    """Phụ thuộc của graph cho một job.

    Args:
        ctx: Context worker.
        asked: Job đang chạy.
        jev: Client Jev của job, `None` khi không có khoá.

    Returns:
        `Deps`.
    """
    banner_model = ctx.get("banner_model")
    summary_model = ctx.get("summary_model")

    async def tell(pages: int) -> None:
        told = DocumentProgress(document_id=asked.document_id, pages_read=pages, page_count=pages)
        await _send(
            ctx["redis"],
            DOCUMENT_PROGRESS_TASK,
            told,
            get_settings().ingest_queue_name,
            asked.document_id,
        )

    async def banner(png: bytes):
        return await read_banner(banner_model, png)

    async def summary(title: str, body: str):
        return await summarise(summary_model, title, body)

    return Deps(
        store=ctx["store"],
        settings=get_settings(),
        read_file=ctx["reader"].read,
        jev=jev.decide_all if jev else None,
        read_banner=banner if banner_model is not None else None,
        summarise=summary if summary_model is not None else None,
        tell=tell,
    )
