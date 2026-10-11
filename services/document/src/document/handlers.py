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
"""

import asyncio
import logging
from datetime import UTC, datetime

from arq.connections import ArqRedis
from arq.worker import Retry
from redis.exceptions import RedisError

from contracts import (
    DOCUMENT_PROBED_TASK,
    DocumentProbed,
    DocumentProbeRequested,
    DocumentState,
    RawDocument,
    RawPage,
)
from document.config import get_settings
from document.content_store import ContentStore, ContentStoreUnavailable
from document.pdf import PdfUnreadable
from document.probe import Finding, probe, raw_pages
from document.storage import StorageUnavailable

logger = logging.getLogger(__name__)

# Lần thử thứ `n` chờ `n` lần bấy nhiêu giây. Với `max_tries = 5` của worker, bốn lần chờ cộng lại
# là 5 + 10 + 15 + 20 = 50 s -- đủ cho Mongo hay Redis khởi động lại, và còn xa ngưỡng 300 s mà BE
# coi một tài liệu là chết.
_RETRY_STEP_SECONDS = 5


class HandBackFailed(RuntimeError):
    """Không đẩy được kết quả sang queue của BE. Tách thành một kiểu để chỉ ca này xin chạy lại."""


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
        Retry: Khi không ghi được bản thô vào kho nội dung, hoặc không đẩy được kết quả về queue
            của BE. arq chạy lại job sau vài giây.

    Side effects:
        Với tệp có chữ: bản thô của nó trong kho nội dung, ghi đè bản cũ. Rồi một job mới trên
        queue của BE. Không ghi gì vào object storage.
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
        if found.state is DocumentState.READY:
            try:
                found = await _keep_raw(ctx["store"], asked, raw, found)
            except ContentStoreUnavailable as exc:
                raise _retry(ctx, exc) from exc

    done = DocumentProbed(
        document_id=asked.document_id,
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
    for page in pages:
        await store.put_page(page)
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
    try:
        job = await pool.enqueue_job(
            DOCUMENT_PROBED_TASK,
            done.model_dump(mode="json"),
            _queue_name=get_settings().ingest_queue_name,
        )
    except (RedisError, OSError) as exc:
        raise HandBackFailed(f"Could not hand back document {done.document_id}: {exc}") from exc
    if job is None:
        raise HandBackFailed(f"arq refused to hand back document {done.document_id}")
