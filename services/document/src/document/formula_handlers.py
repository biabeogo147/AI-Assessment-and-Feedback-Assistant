"""Đọc công thức trên ảnh trang khi BE xin (plan `formulas-on-demand`).

Task duy nhất của `services/document` **có người chờ**: BE đẩy `FormulaReadRequested` lúc một lượt
chat đọc tới trang có khối `formula`, rồi chờ kết quả có trần. Vì vậy worker giữ kết quả của riêng
task này (`index_worker`), và lời đáp không chở công thức -- chúng nằm trong cache `page_formulas`,
nơi BE đọc như mọi nội dung khác.

Một trang hỏng (model lỗi, ảnh không dựng được) không làm hỏng các trang kia: trang ấy không có hàng
nào, và lần đọc sau xin lại nó. Một trang model **từ chối** thì có hàng `refused` -- xin lại cũng bị
từ chối, và Claude Haiku không có fallback.

Hai giới hạn đã biết, chấp nhận: `ContentStore.begin` xoá `page_formulas` trong lúc một job đang đọc
thì job ấy vẫn ghi hàng của nó sau -- ảnh dựng từ cùng `storage_key`, nên công thức vẫn đúng trang;
và job chạy chung `max_jobs` với `index_document`, nên lúc nhiều cuốn đang dựng cây nó có thể nằm
chờ quá `FORMULA_WAIT_SECONDS` của BE -- phần đọc ấy chỉ có chữ, lần sau có công thức.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from contracts import FormulaReadRequested, FormulasRead, PageFormulas
from document.config import get_settings
from document.index.llm import FormulaReading, read_formulas
from document.pdf import PdfUnreadable, open_pdf

logger = logging.getLogger(__name__)


def _render_pages(raw: bytes, pages: tuple[int, ...], dpi: int) -> dict[int, bytes]:
    """Ảnh các trang xin được; trang ngoài tệp hay dựng hỏng thì không có ảnh, trang khác vẫn có."""
    images: dict[int, bytes] = {}
    with open_pdf(raw) as book:
        count = len(book)
        for page in pages:
            if not 1 <= page <= count:
                continue
            try:
                images[page] = book.render(page - 1, dpi)
            except PdfUnreadable:
                logger.warning("could not render page %s", page)
    return images


async def read_pages(
    asked: FormulaReadRequested,
    raw: bytes,
    read: Callable[[bytes], Awaitable[FormulaReading]],
    keep: Callable[[PageFormulas], Awaitable[None]],
    limit: asyncio.Semaphore,
    model: str,
    dpi: int,
) -> list[PageFormulas]:
    """Đọc công thức của các trang được xin, song song trong trần `limit`, ghi **từng trang** ngay.

    Ghi ngay chứ không đợi cả lô: job có trần giờ, và một trang chậm chạm trần không được làm mất
    những trang đã đọc xong (review pha 2, `formulas-on-demand`).

    Args:
        asked: Lời xin.
        raw: Byte của tệp.
        read: Một lời gọi VLM trên ảnh một trang.
        keep: Ghi một hàng vào cache.
        limit: Trần lời gọi model bay cùng lúc của cả worker.
        model: Tên model, ghi vào hàng.
        dpi: Độ phân giải ảnh.

    Returns:
        Mỗi trang đọc được (kể cả bị từ chối) một hàng; trang hỏng không có hàng.
    """
    try:
        images = await asyncio.to_thread(_render_pages, raw, asked.pages, dpi)
    except PdfUnreadable:
        logger.warning("could not render pages %s of %s", asked.pages, asked.document_id)
        return []

    async def one(page: int, png: bytes) -> PageFormulas | None:
        async with limit:
            try:
                reading = await read(png)
            # Ranh giới mạng của một nhà cung cấp model: lỗi nào của nó cũng chỉ là *trang này
            # chưa đọc được*, như bước banner của cây (`index/graph.py`).
            except Exception:
                logger.exception("formula model failed on page %s of %s", page, asked.document_id)
                return None
        row = PageFormulas(
            document_id=asked.document_id,
            page=page,
            model=model,
            formulas=reading.formulas,
            refused=reading.refused,
            tokens=reading.tokens,
            read_at=datetime.now(UTC),
        )
        await keep(row)
        return row

    found = await asyncio.gather(*(one(page, png) for page, png in sorted(images.items())))
    return [row for row in found if row is not None]


async def read_formulas_job(ctx: dict, payload: dict) -> dict:
    """Task arq `read_formulas`: đọc, ghi cache, trả trang nào đã có.

    Args:
        ctx: Context worker: `reader`, `store`, `formula_limit`, và `formula_model` khi có khoá.
        payload: `FormulaReadRequested` đã serialise.

    Returns:
        `FormulasRead` đã serialise. Không có model (thiếu khoá) thì không trang nào -- BE trả chữ
        như trước plan này.

    Raises:
        ContentStoreUnavailable: Khi Mongo không ghi được; BE thấy job hỏng và đi tiếp không công
            thức.
    """
    asked = FormulaReadRequested.model_validate(payload)
    model = ctx.get("formula_model")
    if model is None:
        return FormulasRead(document_id=asked.document_id).model_dump(mode="json")
    settings = get_settings()
    raw = await ctx["reader"].read(asked.storage_key)

    async def read(png: bytes) -> FormulaReading:
        return await read_formulas(model, png)

    async def keep(row: PageFormulas) -> None:
        await ctx["store"].put_formulas([row])

    rows = await read_pages(
        asked, raw, read, keep, ctx["formula_limit"], settings.formula_model, settings.formula_dpi
    )
    logger.info(
        "read formulas of %s pages %s: %s formulas, %s tokens",
        asked.document_id,
        [row.page for row in rows],
        sum(len(row.formulas) for row in rows),
        sum(row.tokens for row in rows),
    )
    return FormulasRead(
        document_id=asked.document_id, pages=tuple(row.page for row in rows)
    ).model_dump(mode="json")
