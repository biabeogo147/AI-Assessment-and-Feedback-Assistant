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

from sqlalchemy import update

from contracts import DocumentProbed
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
