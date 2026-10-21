"""Chặn một client xin lịch sử hội thoại dồn dập: lưới thứ hai cho vòng lặp phía client.

Ngày 29/09/2026 một effect của màn trợ lý tự nuôi mình: BE trả 409, lịch sử vẫn rỗng, effect
xin lại ngay, khoảng 1 500 request mỗi giây trong bốn tiếng (backlog, mục *Một effect tự nuôi mình,
và 69 GB*). Cái chốt ở `Tutor.tsx` sửa đúng gốc ấy, nhưng nó nằm ở client. Bộ đếm này để lần sau
một màn viết sai theo cùng kiểu thì BE trả 429 và ghi một dòng log, thay vì hứng hết.

Ngưỡng do người dùng chốt (Tier 2 câu 34 = A, 21/10/2026): **10 request trong một giây** cho một
bài làm là quá nhiều. Một lần mở màn trợ lý gọi hai đường (`/chat`, `/chat/stream`), StrictMode
của React gọi đôi lên bốn, nên người thật không chạm tới 10.

Đếm theo cặp học sinh + bài làm, mọi request đều vào sổ kể cả request bị từ chối: client còn dồn thì
còn bị chặn, dừng một giây là mở lại. Bộ đếm ở trong bộ nhớ của **một** tiến trình BE, như
`sign_in_limit`.
"""

import logging
import time
from collections import deque
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request

from be.identity import current_student
from schema.models import Student

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 1.0
PER_WINDOW = 10


class BurstLimit:
    """Một cửa sổ trượt ngắn cho mỗi khoá.

    Args:
        clock: Đồng hồ đơn điệu, giây. Test tiêm một đồng hồ giả.
        window: Độ dài cửa sổ, giây.
        per_window: Request thứ ngần này trong cửa sổ thì bị từ chối.
    """

    # Cứ ngần này request thì quét bỏ mọi khoá đã hết hạn, như `SignInLimit`.
    _SWEEP_EVERY = 512

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        window: float = WINDOW_SECONDS,
        per_window: int = PER_WINDOW,
    ) -> None:
        self._clock = clock
        self._window = window
        self._per_window = per_window
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._since_sweep = 0

    def allows(self, key: tuple[str, str]) -> bool:
        """Ghi một request cho khoá này, rồi nói nó có được qua không.

        Args:
            key: Cặp (học sinh, bài làm).

        Returns:
            `False` khi đây là request thứ `per_window` trở lên trong cửa sổ.
        """
        now = self._clock()
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self._window:
            hits.popleft()
        hits.append(now)
        self._since_sweep += 1
        if self._since_sweep >= self._SWEEP_EVERY:
            self._since_sweep = 0
            for one in [k for k, v in self._hits.items() if v[-1] <= now - self._window]:
                del self._hits[one]
        return len(hits) < self._per_window


def get_burst_limit(request: Request) -> BurstLimit:
    """Bộ đếm của ứng dụng đang chạy, dựng ở lần gọi đầu; gắn vào `app.state` như `sign_in_limit`.

    Args:
        request: Request đang xử lý.

    Returns:
        Bộ đếm dùng chung của ứng dụng.
    """
    state = request.app.state
    if getattr(state, "burst_limit", None) is None:
        state.burst_limit = BurstLimit()
    return state.burst_limit


REFUSED = "Màn này tải lại quá nhanh. Chờ một chút rồi thử lại."


async def hold_back_bursts(
    attempt_id: str,
    student: Student = Depends(current_student),
    limit: BurstLimit = Depends(get_burst_limit),
) -> None:
    """Dependency của các đường xin lịch sử hội thoại: dồn quá ngưỡng thì 429.

    Args:
        attempt_id: Bài làm, lấy từ đường dẫn.
        student: Người gọi; FastAPI dùng lại kết quả `current_student` của chính route.
        limit: Bộ đếm của ứng dụng.

    Raises:
        HTTPException: 429 khi đây là request thứ 10 trở lên trong một giây.

    Side effects:
        Ghi request vào bộ đếm; ghi một dòng log ở lần từ chối.
    """
    if not limit.allows((student.id, attempt_id)):
        logger.warning("burst: student %s, attempt %s, refused with 429", student.id, attempt_id)
        raise HTTPException(status_code=429, detail=REFUSED)
