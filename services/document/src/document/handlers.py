"""Một job: đọc một tệp, rồi giao kết quả về cho BE ghi.

Hai loại hỏng ở đây có hai cách xử khác nhau, và phân biệt chúng là cả thiết kế:

- **Không đọc nổi tệp** là một *kết quả*. Nó đi về BE dưới dạng `DocumentState.FAILED` kèm một
  câu giáo viên đọc được. Ném ra ngoài thay vì gửi đi là để chip đứng mãi ở *đang xử lý*, đúng
  thứ ADR-27 gọi là một chip nói dối.
- **Không giao nổi kết quả** thì **ném**, có chủ ý. Không còn đường nào để nói ra nữa, nên thứ
  duy nhất còn giá trị là để arq thử lại job -- việc này đọc một tệp rồi gửi một message, không
  đổi gì ở đâu, nên chạy lại nó an toàn. Hết lượt thử thì phép suy *đứng quá lâu* của BE là lưới
  cuối.
"""

import asyncio
import logging

from arq.connections import ArqRedis

from contracts import DOCUMENT_PROBED_TASK, DocumentProbed, DocumentProbeRequested, DocumentState
from document.config import get_settings
from document.probe import Finding, probe
from document.storage import StorageUnavailable

logger = logging.getLogger(__name__)


async def probe_document(ctx: dict, payload: dict) -> dict:
    """Đọc tệp mà BE vừa cất, và báo lại nó dùng được hay không.

    Args:
        ctx: Context worker của arq. Mang `reader` do `on_startup` dựng và `redis` do arq dựng.
        payload: `DocumentProbeRequested` đã serialise. Chở `storage_key` chứ không chở byte:
            nhét cả tệp vào đây là bắt Redis chuyên chở một cuốn sách cho mỗi lần tải lên.

    Returns:
        Kết quả đã gửi, dưới dạng dict. Không ai đọc nó -- `keep_result = 0` -- nhưng arq ghi nó
        vào log của job, và đó là chỗ duy nhất đọc lại được một job đã chạy.

    Raises:
        Exception: Khi không đẩy được kết quả về queue của BE. Để arq thử lại.

    Side effects:
        Một job mới trên queue của BE. Không ghi gì vào object storage.
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

    done = DocumentProbed(
        document_id=asked.document_id,
        state=found.state,
        page_count=found.page_count,
        fault=found.fault,
    )
    await _hand_back(ctx["redis"], done)
    logger.info(
        "probed document=%s state=%s pages=%s",
        done.document_id,
        done.state.value,
        done.page_count,
    )
    return done.model_dump(mode="json")


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
        RuntimeError: Khi arq từ chối job, chuyện xảy ra khi đã có một job cùng id.

    Side effects:
        Một job mới trên `be_queue_name`.
    """
    job = await pool.enqueue_job(
        DOCUMENT_PROBED_TASK,
        done.model_dump(mode="json"),
        _queue_name=get_settings().be_queue_name,
    )
    if job is None:
        raise RuntimeError(f"arq refused to hand back document {done.document_id}")
