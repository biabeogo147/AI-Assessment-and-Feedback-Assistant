"""Một tiếng hích khi thư viện tài liệu của một giáo viên vừa đổi.

**Đây là nửa nghe.** Nửa phát ở `ingest/events.py`: `services/ingest` hích sau khi ghi xong
kết quả xử lý, còn route trong `be/teacher_documents.py` nghe và đẩy xuống trình duyệt qua SSE.
Hai service nói với nhau qua pub/sub của Redis, đúng hình dạng mà chuông tiến độ của
`be/drafting.py` đã chạy giữa AGENT và BE.

Tên channel ở `contracts.documents_channel`, không ở đây: nó là thứ **duy nhất** hai bên phải
nói giống nhau, nên nó thuộc chỗ hai bên cùng import được. Một bản sao ở mỗi bên là hai chuỗi
f-string lệch nhau được, và lúc lệch thì không có lỗi nào — chỉ có một kênh im.

**Hích không chở dữ liệu**, và đó là cả thiết kế. Bài học nằm nguyên trong `drafting.py`:
*"Chuông không phải một bộ đếm... một tiếng chuông có thể mất"*, vì *"pub/sub của Redis không
giữ lịch sử"*. Một event chở nguyên bản đọc thì mất một event là một chip sai **vĩnh viễn**;
một event chỉ nói *"thư viện của bạn vừa đổi"* thì event sau sửa luôn cái trước, và một lần mở
lại kênh cũng sửa. Nó tự lành.

Hệ quả bắt buộc: trình duyệt **vẫn phải** đọc danh sách một lần lúc mở màn hình. Kênh này chỉ
nói *có gì đó đổi*, không bao giờ nói *đổi thành gì*.

Một channel cho mỗi **giáo viên**, không phải mỗi tài liệu: rail vẽ cả thư viện, nên một màn
hình đang mở là một subscription.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from contracts import documents_channel

logger = logging.getLogger(__name__)

# Nghe mỗi nhịp bao lâu rồi nhả ra cho vòng lặp thở. Cùng con số với chuông tiến độ.
_LISTEN_WAIT = 0.2


@asynccontextmanager
async def open_changes(pool: object, teacher_id: str) -> AsyncIterator[AsyncIterator[bool]]:
    """Mở tai nghe thư viện của một giáo viên; mỗi lần lặp là một lần có gì đó đổi.

    **Một context manager, không phải một async generator**, và `drafting.py` đã trả giá để
    biết vì sao: thân một async generator không chạy cho tới lần lặp đầu tiên, nên việc
    subscribe sẽ xảy ra muộn hơn người đọc tưởng. Ở đây subscribe nằm trong `__aenter__`, nên
    câu *"mở tai trước đã"* là một tính chất của cú pháp chứ không phải một lời dặn.

    Không có hạn: màn hình mở bao lâu thì nghe bấy lâu. Vòng lặp kết thúc khi client ngắt kết
    nối — Starlette huỷ generator, và `finally` ở đây huỷ đăng ký.

    Args:
        pool: Pool Redis của process API, hoặc None khi không tới được queue.
        teacher_id: Giáo viên nào.

    Yields:
        Một iterator **không bao giờ kết thúc cho tới khi kênh gãy**, nhả ra `True` mỗi lần
        thư viện đổi và `False` mỗi nhịp im lặng. Người gọi cần nhịp im lặng ấy để còn phát
        nhịp tim và còn nhận ra lúc client ngắt kết nối; một vòng lặp chỉ nhả khi có tin sẽ
        treo im cho tới tiếng hích kế tiếp, và lúc đó không ai biết nó còn sống hay không.

    Side effects:
        Subscribe một channel Redis khi vào, huỷ đăng ký khi ra.
    """
    opener = getattr(pool, "pubsub", None)
    if pool is None or opener is None:
        # Không có queue thì không có tiếng hích nào. Màn hình vẫn vẽ được thư viện nó đã đọc
        # lúc mở, chỉ là nó không tự mới lại — một bề mặt nghèo đi, không phải một bề mặt hỏng.
        yield _no_changes()
        return

    channel = documents_channel(teacher_id)
    pubsub = opener()
    try:
        await pubsub.subscribe(channel)
        yield _changes_from(pubsub, channel)
    finally:
        # Chạy cả khi người nghe thoát sớm hay bị cancel. Lỗi bị nuốt, vì một lần gãy lúc dọn
        # dẹp sẽ **thay thế** đúng cái thứ đã sai trước đó.
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except Exception:  # noqa: BLE001 -- dọn dẹp không được đứng trên lỗi thật
            logger.warning("could not close the document channel %s", channel, exc_info=True)


async def _no_changes() -> AsyncIterator[bool]:
    """Không có queue thì không có tiếng hích nào, và đó không phải một lỗi."""
    return
    yield False  # pragma: no cover -- chỉ để Python coi đây là một async generator


async def _changes_from(pubsub: object, channel: str) -> AsyncIterator[bool]:
    """Đọc từng tiếng hích từ một subscription đã mở.

    Args:
        pubsub: Subscription đã subscribe xong.
        channel: Tên channel, chỉ để log.

    Yields:
        `True` cho mỗi tiếng hích, `False` cho mỗi nhịp im lặng.
    """
    while True:
        try:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=_LISTEN_WAIT)
        except Exception:  # noqa: BLE001 -- xem bên dưới
            # Redis gãy giữa lúc nghe thì thôi nghe, không ném. Một exception thoát ra đây sẽ
            # cắt luôn response SSE đang mở, mà thứ duy nhất mất đi là việc tự mới lại.
            logger.warning("stopped listening on %s", channel, exc_info=True)
            return
        # `get_message` với timeout trả None khi im lặng. Nhả cả hai ca ra ngoài, có nhãn,
        # để vòng lặp gọi còn kịp phát nhịp tim và còn thấy được lúc client ngắt kết nối.
        yield message is not None
