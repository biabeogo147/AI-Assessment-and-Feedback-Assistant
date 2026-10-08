"""Phát một tiếng hích khi thư viện tài liệu của một giáo viên vừa đổi.

Đây là **nửa phát** của kênh; nửa nghe nằm ở `be/document_events.py`, và tên channel ở
`contracts.documents_channel` vì nó là thứ duy nhất hai bên phải nói giống nhau. Hình dạng này
đúng bằng chuông tiến độ chạy giữa AGENT và BE.

**Hích không chở dữ liệu**, và đó là cả thiết kế. Bài học nằm nguyên trong `be/drafting.py`:
*"Chuông không phải một bộ đếm... một tiếng chuông có thể mất"*, vì *"pub/sub của Redis không
giữ lịch sử"*. Một event chở nguyên bản đọc thì mất một event là một chip sai **vĩnh viễn**;
một event chỉ nói *"thư viện của bạn vừa đổi"* thì event sau sửa luôn cái trước, và một lần mở
lại kênh cũng sửa. Nó tự lành.
"""

import logging

from contracts import documents_channel

logger = logging.getLogger(__name__)


async def announce(pool: object, teacher_id: str) -> None:
    """Nói với mọi màn hình đang mở rằng thư viện của giáo viên này vừa đổi.

    Lỗi chỉ được **log**, không ném. Hàm này chạy sau khi hàng đã ghi xong: một kênh gãy không
    được phép biến một job đã làm tròn việc thành một job arq đem thử lại, vì lần thử lại ấy sẽ
    ghi đè đúng cái đã đúng.

    Args:
        pool: Pool Redis của worker, hoặc None khi không có.
        teacher_id: Giáo viên cần báo.

    Side effects:
        Một message trên channel Redis. Không ai giữ nó lại: không màn hình nào đang mở thì
        tiếng hích rơi vào phòng trống, và đó là chuyện bình thường.
    """
    if pool is None or not hasattr(pool, "publish"):
        return
    channel = documents_channel(teacher_id)
    try:
        await pool.publish(channel, "1")
    except Exception:  # noqa: BLE001 -- xem docstring: không được ném ngược vào arq
        logger.warning("could not ring %s", channel, exc_info=True)
