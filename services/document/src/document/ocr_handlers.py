"""Một job: đọc một tệp, rồi giao kết quả về cho BE ghi.

Hai loại hỏng ở đây có hai cách xử khác nhau, và phân biệt chúng là cả thiết kế:

- **Không đọc nổi tệp** là một *kết quả*. Nó đi về BE dưới dạng `DocumentState.FAILED` kèm một
  câu giáo viên đọc được. Ném ra ngoài thay vì gửi đi là để chip đứng mãi ở *đang xử lý*, đúng
  thứ ADR-27 gọi là một chip nói dối.
- **Không giao nổi kết quả** thì xin arq **chạy lại** job (`arq.Retry`). Không còn đường nào để
  nói ra nữa, nên thứ duy nhất còn giá trị là thử lại sau vài giây. Hết lượt thử thì phép suy
  *đứng quá lâu* của BE là lưới cuối.

Từ plan 3b, một tệp có chữ còn để lại **bản thô** trong kho nội dung, và **trước** khi `READY`
rời service -- Decision Record *"chunk trước, `state` sau"*. Không ghi nổi bản thô cũng xin chạy
lại, cùng lý do: một `READY` mà kho không có chữ là một chip nói dối theo chiều ngược lại. Chạy lại
an toàn: `ContentStore.begin` xoá bản thô cũ, và trang ghi theo `_id`, nên lần chạy sau ghi đè
lần trước chứ không chồng lên.

**Phải là `Retry`, không phải một exception bất kỳ.** arq chỉ chạy lại job khi gặp `Retry` (hoặc
khi worker bị cắt giữa job); mọi exception khác đánh job *hỏng* ngay, không lượt nào nữa. Trước
review Task 2 của plan 3b (11/10/2026, đọc `arq/worker.py` 0.28), docstring này nói *"ném để arq
thử lại"* -- và không có lần thử lại nào cả.

**PDF scan đi đường OCR theo lô** (plan 3b, Task 3). `probe_document` không trả *không đọc được
chữ* cho một PDF scan nữa: nó mở đầu mục bản thô, rồi giao lô trang đầu cho `ocr_pages` trên chính
queue này. Mỗi lô đọc vài trang, ghi chúng vào kho, báo tiến độ về `services/ingest`, rồi tự giao lô
kế. Lô cuối mới gửi kết quả: `READY` khi cả cuốn có chữ, `NO_TEXT_LAYER` khi OCR xong mà không trang
nào ra chữ -- lúc ấy câu *không đọc được chữ* mới là một phán quyết thật.

**Từ plan 3c, `READY` không rời service này.** Bản thô xong thì tài liệu còn chờ cây: `_settle`
giao một job `index_document` cho `document.index_worker`, và chỉ job ấy gửi `READY` -- sau khi
cây đã nằm trong kho nội dung (D3). Mọi phán quyết khác vẫn đi thẳng về BE như trước.
"""

import asyncio
import logging
import time
from datetime import UTC, datetime

from arq.connections import ArqRedis
from arq.worker import Retry
from pydantic import BaseModel
from redis.exceptions import RedisError

from contracts import (
    DOCUMENT_PROBED_TASK,
    DOCUMENT_PROGRESS_TASK,
    INDEX_DOCUMENT_TASK,
    OCR_PAGES_TASK,
    DocumentIndexRequested,
    DocumentPagesRequested,
    DocumentProbed,
    DocumentProbeRequested,
    DocumentProgress,
    DocumentState,
    RawDocument,
    RawPage,
    RawSource,
)
from document.config import get_settings
from document.content_store import ContentStore, ContentStoreUnavailable
from document.pdf import PdfUnreadable
from document.probe import Finding, probe, raw_ocr_page, raw_pages
from document.storage import StorageUnavailable

logger = logging.getLogger(__name__)

# Lần thử thứ `n` chờ `n` lần bấy nhiêu giây. Với `MAX_TRIES = 5`, bốn lần chờ cộng lại là
# 5 + 10 + 15 + 20 = 50 s -- đủ cho Mongo hay Redis khởi động lại, và còn xa ngưỡng 300 s mà BE coi
# một tài liệu là chết. Một lô OCR chạy lại chỉ đọc những trang chưa nằm trong kho (`stored_pages`),
# nên năm lần thử liền không còn cộng năm lần đọc cả lô vào khoảng chờ ấy.
_RETRY_STEP_SECONDS = 5

# Số lần arq chạy một job, kể cả lần đầu. Đúng mặc định của arq; `ocr_worker.py` đặt nó vào
# `WorkerSettings`, và `ocr_pages` cần biết nó để nhận ra lần thử cuối.
MAX_TRIES = 5

# Một lô dừng đọc khi đã chạy chừng này giây, dù chưa đủ `ocr_pages_per_job` trang, và giao phần còn
# lại cho lô kế. Lý do: arq **không** chạy lại một job chạm `job_timeout` (120 s) -- nó đánh hỏng
# hẳn, và chuỗi lô chết im. Một cuốn có trang dày chữ (8-12 s/trang) làm mười trang vượt trần ấy;
# ngân sách này giữ mỗi lô dưới trần bất kể trang dày tới đâu, chỉ trừ một trang đơn lẻ dài hơn
# 30 s.
_BATCH_BUDGET_SECONDS = 90

# Phiên bản đường OCR, ghi vào đầu mục bản thô. Cùng nghĩa với `_PIPELINE` của
# `tools/ocr_bench/run.py`: `text1` là *chỉ chữ, công thức không đọc lúc upload* (11/10/2026);
# `text2` thêm *khối hình giữ chữ của các dòng trong nó* (plan 3c, D2). Đổi đường đọc thì đổi số
# này, để bên đọc ở plan 3c biết bản thô nào cần đọc lại.
_OCR_PIPELINE = "text2"


class HandBackFailed(RuntimeError):
    """Không đẩy được một job sang queue -- kết quả về BE, tiến độ, hay lô OCR kế tiếp.

    Tách thành một kiểu để chỉ ca này xin chạy lại.
    """


async def probe_document(ctx: dict, payload: dict) -> dict:
    """Đọc tệp mà BE vừa cất, và báo lại nó dùng được hay không.

    Args:
        ctx: Context worker của arq. Mang `reader` và `store` do `on_startup` dựng, `redis` do arq
            dựng.
        payload: `DocumentProbeRequested` đã serialise. Chở `storage_key` chứ không chở byte:
            nhét cả tệp vào đây là bắt Redis chuyên chở một cuốn sách cho mỗi lần tải lên.

    Returns:
        Kết quả đã gửi, dưới dạng dict. Không ai đọc nó -- `keep_result = 0` -- nhưng arq ghi nó
        vào log của job, và đó là chỗ duy nhất đọc lại được một job đã chạy.

    Raises:
        Retry: Khi không ghi được vào kho nội dung, hoặc không đẩy được job tiếp theo -- kết quả
            về BE, hay lô OCR đầu. arq chạy lại job sau vài giây.

    Side effects:
        Với tệp có chữ: bản thô của nó trong kho nội dung, ghi đè bản cũ, rồi một job dựng cây
        trên queue của `document.index_worker` (plan 3c). Tệp hỏng: một job mới trên queue của
        BE. Với PDF scan: đầu mục bản thô, rồi lô OCR đầu trên queue của chính service này --
        **không** có gì về BE lúc này. Không ghi gì vào object storage.
    """
    asked = DocumentProbeRequested.model_validate(payload)

    try:
        raw = await ctx["reader"].read(asked.storage_key)
    except StorageUnavailable as missing:
        logger.error("could not read %s: %s", asked.storage_key, missing)
        found = _unreadable()
    else:
        # `probe` là sync và CPU-bound. Thiếu `to_thread` thì nó chặn mọi job khác trên worker
        # này suốt thời gian quét một cuốn sách, và không có exception nào nói ra điều đó.
        found = await asyncio.to_thread(probe, raw, asked.filename)
        try:
            if found.state is DocumentState.READY:
                found = await _keep_raw(ctx["store"], asked, raw, found)
            elif (pages := _scan_pages(found)) is not None:
                await _start_ocr(ctx, asked, pages)
                return {"document_id": asked.document_id, "ocr_pages": pages}
        except (ContentStoreUnavailable, HandBackFailed) as exc:
            raise _retry(ctx, exc) from exc

    # [CODE CHẾT 2026-10-11] READY chờ cây — plan 3c, D3
    # return await _conclude(ctx, asked.document_id, found)
    return await _settle(ctx, asked, found)


async def ocr_pages(ctx: dict, payload: dict) -> dict:
    """Đọc một lô trang của một PDF scan bằng OCR, ghi chúng vào kho, rồi giao lô kế.

    Lô cuối không giao lô nào: nó đánh dấu bản thô đã xong, đếm chữ của cả cuốn, rồi gửi kết quả
    về BE -- `READY` khi có chữ, `NO_TEXT_LAYER` khi cả cuốn không ra chữ nào.

    Mỗi lô **đọc lại tệp** từ object storage thay vì nhận byte qua Redis: cùng lý do
    `DocumentProbeRequested` chở khoá chứ không chở tệp.

    Args:
        ctx: Context worker của arq. Mang `reader`, `store` và `ocr` (một `PageReader` đã nạp
            model) do `on_startup` dựng, `redis` do arq dựng.
        payload: `DocumentPagesRequested` đã serialise.

    Returns:
        Lô vừa đọc, hoặc kết quả đã gửi khi đây là lô cuối, dưới dạng dict cho log của job.

    Raises:
        Retry: Khi kho nội dung không ghi được, không đẩy được job tiếp theo, hoặc object storage
            chập chờn (trừ lần thử cuối). Lần chạy lại chỉ đọc những trang của lô chưa nằm trong
            kho; trang ghi theo `_id`, nên một trang đọc lại vẫn là ghi đè chứ không chồng.

    Side effects:
        Mỗi trang của lô trong kho nội dung. Rồi hoặc một tiếng báo tiến độ trên queue của
        `services/ingest` cùng lô kế trên queue này, hoặc kết quả cuối trên queue của BE.
    """
    batch = DocumentPagesRequested.model_validate(payload)
    planned = min(batch.first + get_settings().ocr_pages_per_job - 1, batch.page_count)

    try:
        raw = await ctx["reader"].read(batch.storage_key)
    except StorageUnavailable as missing:
        # Khác lần dò tệp: tệp **đã** đọc được lúc dò, nên giữa chuỗi lô một lần hụt là MinIO chập
        # chờn chứ không phải tệp mất -- và đánh hỏng ngay là bắt giáo viên tải lại rồi chờ mười
        # lăm phút nữa. Chỉ lần thử cuối mới thành phán quyết.
        if ctx.get("job_try", 1) < MAX_TRIES:
            raise _retry(ctx, missing) from missing
        logger.error("could not read %s: %s", batch.storage_key, missing)
        return await _conclude(ctx, batch.document_id, _unreadable())

    started = time.monotonic()
    last = batch.first - 1
    try:
        # Lần chạy lại của một lô (arq `Retry`) không đọc lại trang lần trước đã ghi: mỗi trang vài
        # giây, và năm lần chạy lại đọc cả lô từng sát ngưỡng 300 s của BE.
        stored = await ctx["store"].stored_pages(batch.document_id, batch.first, planned)
        for page in range(batch.first, planned + 1):
            if page in stored:
                last = page
                continue
            # CPU-bound và dài (vài giây một trang), nên vào thread như `probe`. `read_page` đếm
            # trang từ 0, kho đếm từ 1.
            read = await asyncio.to_thread(ctx["ocr"].read_page, raw, page - 1)
            await ctx["store"].put_page(raw_ocr_page(read, batch.document_id, datetime.now(UTC)))
            last = page
            if time.monotonic() - started > _BATCH_BUDGET_SECONDS:
                break
    except ContentStoreUnavailable as exc:
        raise _retry(ctx, exc) from exc
    except Exception:  # noqa: BLE001 -- xem chú thích: mọi lỗi đọc trang phải thành một câu trả lời
        # `probe` vừa mở được tệp, nên một trang không đọc nổi -- PyMuPDF không dựng được ảnh
        # (`PdfUnreadable`), hay model OCR ném một lỗi của torch / paddle -- là một phán quyết về
        # đúng trang ấy. Để nó thoát ra thì arq đánh job hỏng **không thử lại**, không gì về BE, và
        # chip chờ 300 s mới ra *xử lý hỏng*: đúng cái chip nói dối mà service này cấm.
        logger.exception("could not ocr page %s of document=%s", last + 1, batch.document_id)
        failed = Finding(
            DocumentState.FAILED, None, f"Không đọc được trang {last + 1} của tệp PDF này."
        )
        return await _conclude(ctx, batch.document_id, failed)

    logger.info(
        "ocr document=%s pages %s-%s of %s",
        batch.document_id,
        batch.first,
        last,
        batch.page_count,
    )
    try:
        if last < batch.page_count:
            await _tell_progress(ctx["redis"], batch, last)
            await _queue_batch(ctx["redis"], batch.model_copy(update={"first": last + 1}))
            return {"document_id": batch.document_id, "pages_read": last}
        await ctx["store"].finish(batch.document_id, datetime.now(UTC))
        characters = await ctx["store"].characters(batch.document_id)
    except (ContentStoreUnavailable, HandBackFailed) as exc:
        raise _retry(ctx, exc) from exc

    if characters > 0:
        found = Finding(DocumentState.READY, batch.page_count, "")
    else:
        found = Finding(
            DocumentState.NO_TEXT_LAYER,
            batch.page_count,
            "Đã đọc hết các trang nhưng không thấy chữ nào.",
        )
    # [CODE CHẾT 2026-10-11] READY chờ cây — plan 3c, D3
    # return await _conclude(ctx, batch.document_id, found)
    return await _settle(ctx, batch, found)


def _scan_pages(found: Finding) -> int | None:
    """Số trang cần OCR, khi `probe` nói *không có chữ* về một PDF **có trang** -- một bản scan.

    Hai ca `NO_TEXT_LAYER` khác vẫn là phán quyết cuối: tệp văn bản thuần rỗng (`page_count` là
    `None`) và PDF không trang nào (`0`). OCR không có gì để đọc ở cả hai.

    Args:
        found: Phán quyết của `probe`.

    Returns:
        Số trang khi tệp phải đi đường OCR, `None` khi không.
    """
    if found.state is DocumentState.NO_TEXT_LAYER and found.page_count:
        return found.page_count
    return None


async def _start_ocr(ctx: dict, asked: DocumentProbeRequested, page_count: int) -> None:
    """Mở bản thô của một PDF scan, rồi giao lô đầu.

    Đầu mục đi **trước** lô đầu: `begin` xoá trang cũ của tài liệu, nên mở nó sau khi lô đầu đã
    ghi là xoá chính những trang vừa đọc.

    Args:
        ctx: Context worker của arq.
        asked: Job dò tệp đang chạy.
        page_count: Số trang `probe` đếm được.

    Raises:
        ContentStoreUnavailable: Khi kho nội dung không ghi được.
        HandBackFailed: Khi không đẩy được lô đầu.
    """
    settings = get_settings()
    await ctx["store"].begin(
        RawDocument(
            document_id=asked.document_id,
            source=RawSource.OCR,
            page_count=page_count,
            reader=settings.ocr_reader,
            pipeline=_OCR_PIPELINE,
            started_at=datetime.now(UTC),
        )
    )
    await _queue_batch(
        ctx["redis"],
        DocumentPagesRequested(
            document_id=asked.document_id,
            storage_key=asked.storage_key,
            filename=asked.filename,
            first=1,
            page_count=page_count,
        ),
    )
    logger.info(
        "document=%s is a scan of %s pages; reading it by ocr", asked.document_id, page_count
    )


async def _settle(
    ctx: dict, asked: DocumentProbeRequested | DocumentPagesRequested, found: Finding
) -> dict:
    """Kết thúc đường đọc: phán quyết đi về BE, **trừ** `READY` -- nó còn chờ cây (plan 3c, D3).

    Bản thô đã nằm trong kho thì tài liệu chưa *sẵn sàng*: ba tool đọc ở plan sau cần cây, và một
    chip *sẵn sàng* mà tool không có gì để lần xuống là một chip nói dối. Nên `READY` thành một job
    trên queue dựng cây, và chỉ job ấy gửi `READY` -- sau khi cây đã vào Mongo.

    Args:
        ctx: Context worker của arq.
        asked: Job dò tệp hoặc lô OCR cuối -- cả hai chở khoá object storage và tên tệp.
        found: Phán quyết.

    Returns:
        Kết quả cho log của job.

    Raises:
        Retry: Khi không đẩy được job tiếp theo.
    """
    if found.state is not DocumentState.READY:
        return await _conclude(ctx, asked.document_id, found)
    request = DocumentIndexRequested(
        document_id=asked.document_id,
        storage_key=asked.storage_key,
        filename=asked.filename,
        page_count=found.page_count,
    )
    try:
        await _queue_index(ctx["redis"], request)
    except HandBackFailed as exc:
        raise _retry(ctx, exc) from exc
    logger.info("document=%s has its raw content; queued for indexing", asked.document_id)
    return {"document_id": asked.document_id, "indexing": True}


async def _queue_index(pool: ArqRedis, request: DocumentIndexRequested) -> None:
    """Giao job dựng cây cho `document.index_worker`.

    Id cố định theo tài liệu, cùng lý do `_queue_batch`: lô OCR cuối chạy lại sau khi đã giao thì
    lần giao thứ hai bị từ chối, thay vì hai job dựng cùng một cây và trả tiền Jev hai lần.

    Args:
        pool: Pool arq của worker.
        request: Job cần giao.

    Raises:
        HandBackFailed: Khi Redis không với tới được.
    """
    job = await _send(
        pool,
        INDEX_DOCUMENT_TASK,
        request,
        get_settings().document_index_queue_name,
        request.document_id,
        job_id=f"index:{request.document_id}",
    )
    if job is None:
        logger.info("indexing of %s is already queued", request.document_id)


async def _conclude(ctx: dict, document_id: str, found: Finding) -> dict:
    """Gửi kết quả cuối về BE.

    Args:
        ctx: Context worker của arq.
        document_id: Tài liệu.
        found: Phán quyết.

    Returns:
        Kết quả đã gửi, dưới dạng dict. Không ai đọc nó -- `keep_result = 0` -- nhưng arq ghi nó
        vào log của job.

    Raises:
        Retry: Khi không đẩy được kết quả về queue của BE.
    """
    done = DocumentProbed(
        document_id=document_id,
        state=found.state,
        page_count=found.page_count,
        fault=found.fault,
    )
    try:
        await _hand_back(ctx["redis"], done)
    except HandBackFailed as exc:
        raise _retry(ctx, exc) from exc
    logger.info(
        "probed document=%s state=%s pages=%s",
        done.document_id,
        done.state.value,
        done.page_count,
    )
    return done.model_dump(mode="json")


async def _keep_raw(
    store: ContentStore, asked: DocumentProbeRequested, raw: bytes, found: Finding
) -> Finding:
    """Ghi bản thô của một tệp có chữ vào kho nội dung.

    Args:
        store: Kho nội dung.
        asked: Job đang chạy.
        raw: Byte của tệp.
        found: Phán quyết `READY` của `probe`.

    Returns:
        `found` nguyên vẹn khi đã ghi xong. Một phán quyết `FAILED` khi lần đọc thứ hai của tệp
        hỏng -- `probe` vừa mở được nó nên chuyện này gần như không xảy ra, nhưng nếu có thì đó
        là một tệp xấu, không phải một lỗi của hệ thống.

    Raises:
        ContentStoreUnavailable: Khi kho nội dung không ghi được.

    Side effects:
        Đầu mục và mọi trang của tài liệu trong kho nội dung.
    """
    at = datetime.now(UTC)
    try:
        # Sync và CPU-bound như `probe`, cùng lý do cần `to_thread`.
        pages: list[RawPage] = await asyncio.to_thread(
            raw_pages, raw, asked.filename, asked.document_id, at
        )
    except PdfUnreadable:
        return Finding(DocumentState.FAILED, None, "Không mở được tệp PDF này.")

    await store.begin(
        RawDocument(
            document_id=asked.document_id,
            source=pages[0].source,
            page_count=found.page_count,
            started_at=at,
        )
    )
    await store.put_pages(pages)
    await store.finish(asked.document_id, datetime.now(UTC))
    logger.info("kept raw content document=%s pages=%s", asked.document_id, len(pages))
    return found


def _retry(ctx: dict, cause: Exception) -> Retry:
    """Dựng lời xin arq chạy lại job, chờ lâu dần theo số lần đã thử.

    Args:
        ctx: Context worker của arq. `job_try` đếm từ 1.
        cause: Lỗi khiến job phải chạy lại, cho dòng log.

    Returns:
        Một `Retry` để người gọi `raise`.
    """
    attempt = ctx.get("job_try", 1)
    logger.warning("try %s failed, asking arq to run the job again: %s", attempt, cause)
    return Retry(defer=attempt * _RETRY_STEP_SECONDS)


def _unreadable() -> Finding:
    """Kết quả cho ca không với tới được tệp đã cất.

    `FAILED`, không phải `NO_TEXT_LAYER`: tệp có thể vẫn tốt, chỉ là lần này không lấy được nó,
    nên thử lại là việc có nghĩa. Gộp hai cái lại là nói với giáo viên rằng cuốn sách của họ vô
    dụng trong khi thật ra object storage vừa bị tắt.

    Returns:
        Một `Finding` mang `FAILED`.
    """
    return Finding(DocumentState.FAILED, None, "Chưa đọc được tệp đã cất. Thử lại sau.")


async def _hand_back(pool: ArqRedis, done: DocumentProbed) -> None:
    """Đẩy kết quả sang queue của BE.

    Args:
        pool: Pool arq của worker.
        done: Kết quả cần giao.

    Raises:
        HandBackFailed: Khi Redis không với tới được, hoặc arq từ chối job -- chuyện xảy ra khi đã
            có một job cùng id.

    Side effects:
        Một job mới trên `ingest_queue_name`.
    """
    job = await _send(
        pool, DOCUMENT_PROBED_TASK, done, get_settings().ingest_queue_name, done.document_id
    )
    if job is None:
        raise HandBackFailed(f"arq refused to hand back document {done.document_id}")


async def _tell_progress(pool: ArqRedis, batch: DocumentPagesRequested, pages_read: int) -> None:
    """Báo `services/ingest` rằng chuỗi lô vẫn đang tiến.

    Args:
        pool: Pool arq của worker.
        batch: Lô vừa đọc xong.
        pages_read: Số trang đã nằm trong kho.

    Raises:
        HandBackFailed: Khi Redis không với tới được.

    Side effects:
        Một job mới trên `ingest_queue_name`.
    """
    told = DocumentProgress(
        document_id=batch.document_id, pages_read=pages_read, page_count=batch.page_count
    )
    await _send(
        pool, DOCUMENT_PROGRESS_TASK, told, get_settings().ingest_queue_name, batch.document_id
    )


async def _queue_batch(pool: ArqRedis, batch: DocumentPagesRequested) -> None:
    """Giao một lô OCR cho queue của chính service này.

    Job mang **id cố định** theo tài liệu và trang đầu. Một lô bị arq chạy lại sau khi đã giao lô kế
    thì lần giao thứ hai bị từ chối thay vì đẻ ra một chuỗi lô thứ hai đọc song song cùng cuốn sách
    -- hai chuỗi tranh CPU, và mỗi chuỗi lại đẻ thêm. Từ chối ở đây vì thế là *đã có rồi*, không
    phải hỏng. arq xoá khoá của job khi nó xong, nên đọc lại tài liệu ấy về sau vẫn giao được.

    Giới hạn: id chỉ chặn trùng **trong lúc** lô kế còn nằm trong queue hay đang chạy. Với một
    process worker -- đúng hình dạng hiện tại, `max_jobs = 1` -- một lô chỉ chạy lại khi lô kế chưa
    được giao, nên điều ấy đủ. Chạy hai process `document` thì không đủ nữa.

    Args:
        pool: Pool arq của worker.
        batch: Lô cần giao.

    Raises:
        HandBackFailed: Khi Redis không với tới được.

    Side effects:
        Một job mới trên `document_queue_name`, trừ khi lô ấy đã nằm sẵn trong queue.
    """
    job = await _send(
        pool,
        OCR_PAGES_TASK,
        batch,
        get_settings().document_queue_name,
        batch.document_id,
        job_id=f"ocr:{batch.document_id}:{batch.first}",
    )
    if job is None:
        logger.info(
            "ocr batch from page %s of %s is already queued", batch.first, batch.document_id
        )


async def _send(
    pool: ArqRedis,
    task: str,
    message: BaseModel,
    queue: str,
    document_id: str,
    job_id: str | None = None,
) -> object | None:
    """Đẩy một message thành một job arq, dịch lỗi Redis thành `HandBackFailed`.

    Args:
        pool: Pool arq của worker.
        task: Tên task trên queue đích.
        message: Payload, serialise thành JSON.
        queue: Queue đích.
        document_id: Tài liệu, cho câu lỗi.
        job_id: Id cố định của job, hoặc `None` để arq tự sinh.

    Returns:
        Job arq trả về, hoặc `None` khi arq từ chối vì đã có một job cùng id -- người gọi quyết
        nghĩa của lời từ chối ấy.

    Raises:
        HandBackFailed: Khi Redis không với tới được.
    """
    try:
        return await pool.enqueue_job(
            task, message.model_dump(mode="json"), _queue_name=queue, _job_id=job_id
        )
    except (RedisError, OSError) as exc:
        raise HandBackFailed(f"Could not send {task} for document {document_id}: {exc}") from exc
