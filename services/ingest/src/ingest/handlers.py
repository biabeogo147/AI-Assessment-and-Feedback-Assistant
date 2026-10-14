"""Ghi lại những gì `services/document` đọc được từ một tài liệu.

Đây là đường **duy nhất** mà kết quả xử lý tài liệu đi vào Postgres, và nó là đường đầu
tiên trong repo mà một job được **tiêu thụ** để ghi một hàng thay vì để đẩy một việc đi. Lý do
nó không thể là một request: không ai đang chờ. Giáo viên đã rời màn hình tải lên từ lâu, và
một process đã chết thì không có ai để trả 503 cho.

Vì sao không poll kết quả bằng result store của arq, cách `be/agent_gateway.py` vẫn làm
với job của AGENT:
`worker.py` của AGENT đặt `keep_result = job_result_ttl_seconds`, nên **kết quả job hết hạn**.
Một tài liệu xử lý xong trong mười giây mà không ai đọc trong một giờ là một kết quả bốc hơi --
đúng cái bẫy `drafting.py` đã ghi lại. Một job tự mang dữ liệu đi thì không có hạn sống nào.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import case, func, select, update

from contracts import DocumentProbed, DocumentProgress, DocumentState
from ingest.db import session_scope
from ingest.events import announce
from schema.models import Document

logger = logging.getLogger(__name__)


async def document_probed(ctx: dict, payload: dict) -> dict:
    """Ghi phán quyết, số trang và lý do vào hàng của tài liệu.

    Args:
        ctx: Context worker của arq. Không dùng -- session mở theo **việc**, không theo
            process, vì một job sống vài trăm milli giây còn một process sống hàng giờ.
        payload: `DocumentProbed` đã serialise.

    Returns:
        Một dict nói đã ghi được hàng nào chưa. Không ai đọc nó; nó vào log của job, và đó là
        chỗ duy nhất đọc lại được một job đã chạy.

    Side effects:
        Một `UPDATE` trên `documents`, rồi một tiếng hích lên channel của giáo viên sở hữu nó.
        Không `INSERT` bao giờ: hàng đã có từ lúc tải lên, và một job tạo hàng mới là một
        đường thứ hai để tài liệu xuất hiện trong thư viện.
    """
    done = DocumentProbed.model_validate(payload)

    async with session_scope() as session:
        written = await session.execute(
            update(Document)
            .where(Document.id == done.document_id)
            .values(state=done.state.value, page_count=done.page_count, fault=done.fault)
            # Lấy luôn chủ sở hữu từ chính câu `UPDATE`. Một `SELECT` thứ hai cũng ra đúng
            # con số ấy, nhưng nó là một vòng nữa tới database cho một thứ hàng vừa trả về --
            # và nó mở một khe cho hàng bị xoá giữa hai câu lệnh.
            .returning(Document.teacher_id)
        )
        owner = written.scalar_one_or_none()
        await session.commit()

    if owner is None:
        # Hàng không còn: giáo viên đã xoá tài liệu trong lúc nó đang được đọc, hoặc database đã
        # bị dựng lại. Không phải lỗi, và **không được ném**: arq sẽ thử lại một job không bao
        # giờ thành công được, rồi lặp lại đúng chừng ấy lần.
        logger.warning("nothing to write for document=%s; the row is gone", done.document_id)
        return {"document_id": done.document_id, "written": False}

    # Hích **sau** khi commit. Ngược lại thì màn hình nghe tin rồi đọc lại và thấy giá trị cũ,
    # một ca hiếm nhưng tự tạo ra -- và nó không tự sửa, vì sẽ không có tiếng hích thứ hai.
    await announce(ctx.get("redis"), owner)

    logger.info(
        "document=%s is now %s (pages=%s)",
        done.document_id,
        done.state.value,
        done.page_count,
    )
    return {"document_id": done.document_id, "written": True}


async def document_progress(ctx: dict, payload: dict) -> dict:
    """Ghi tiến độ của một PDF scan đang được OCR: số trang đã đọc, và lúc nghe được.

    Cột cần thiết là `progress_at`, không phải `pages_read`: BE đo *đứng quá lâu* từ nó, nên mỗi
    tiếng báo là một lần nói *chuỗi lô vẫn đang tiến* (plan 3b, D4). Mốc là giờ **của process
    này** lúc ghi, không phải giờ trong message: BE so nó với đồng hồ của chính BE, và hai process
    trên cùng một máy chung một đồng hồ -- còn một mốc chở theo message thì một job nằm lâu trong
    Redis sẽ ghi một mốc cũ.

    Chỉ ghi khi hàng **còn** `processing`. Kết quả cuối đã về thì một tiếng báo đến muộn không có gì
    để nói, và ghi nó là làm cột tiến độ nói một điều sai về một tài liệu đã xong.

    **`pages_read` không lùi.** Tiếng báo đi qua queue và có thể về sai thứ tự (một lô chạy lại
    báo sau lô kế của nó), nên cột giữ số lớn hơn giữa cái đã có và cái vừa nghe. Viết bằng
    `CASE` chứ không `GREATEST`, vì test chạy trên SQLite. Cái giá: lần dò tệp bị arq chạy lại thì
    OCR bắt đầu lại từ trang 1, và chip báo dư cho tới khi chuỗi mới vượt số cũ.

    `page_count` cũng được ghi, vì chip cần tổng để nói *"đang đọc 37/200 trang"* (người dùng chốt
    14/10/2026). Ghi nó lúc `processing` không phải nói sớm: dòng meta của chip chỉ in số trang ở
    `ready` và `no_text_layer` (`Rail.measure`), và phán quyết cuối ghi đè cột ấy bằng số của nó.

    Hích màn hình **chỉ khi `pages_read` tăng** -- tức khi chip đổi chữ. Job dựng cây gửi nhịp
    tim ở mỗi chặng (mỗi banner, mỗi nhóm tóm tắt) với `pages_read = page_count`; hích cả những
    tiếng ấy là mỗi màn hình đang mở đọc lại cả thư viện vài chục lần mà không thấy gì đổi. Tiếng
    đầu tiên của job ấy vẫn được hích: nó đưa `pages_read` lên bằng tổng, và chip sang *"đang dựng
    mục lục"*.

    Args:
        ctx: Context worker của arq. `redis` để hích; thiếu thì không hích.
        payload: `DocumentProgress` đã serialise.

    Returns:
        Một dict nói đã ghi được hàng nào chưa, cho log của job.

    Side effects:
        Một `UPDATE` trên `documents`, rồi một tiếng hích lên channel của chủ sở hữu.
    """
    told = DocumentProgress.model_validate(payload)

    async with session_scope() as session:
        # Đọc số cũ trong cùng giao dịch, chỉ để quyết có hích không. Hai tiếng báo chen nhau thì
        # tệ nhất là thừa hay thiếu một tiếng hích -- tiếng sau sửa lại, vì hích không chở dữ liệu.
        before = await session.scalar(
            select(Document.pages_read).where(Document.id == told.document_id)
        )
        written = await session.execute(
            update(Document)
            .where(
                Document.id == told.document_id,
                Document.state == DocumentState.PROCESSING.value,
            )
            .values(
                pages_read=case(
                    (
                        func.coalesce(Document.pages_read, 0) < told.pages_read,
                        told.pages_read,
                    ),
                    else_=Document.pages_read,
                ),
                page_count=told.page_count,
                progress_at=datetime.now(UTC),
            )
            .returning(Document.teacher_id)
        )
        owner = written.scalar_one_or_none()
        await session.commit()

    if owner is None:
        # Cùng lý do với `document_probed`: không ném, vì không lần thử lại nào sửa được.
        logger.info("no progress to write for document=%s", told.document_id)
        return {"document_id": told.document_id, "written": False}

    if told.pages_read > (before or 0):
        await announce(ctx.get("redis"), owner)

    logger.info("document=%s read %s/%s pages", told.document_id, told.pages_read, told.page_count)
    return {"document_id": told.document_id, "written": True}
