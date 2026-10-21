"""Chậm người đoán mật khẩu lại: đếm lần đăng nhập sai theo tên và theo địa chỉ (ADR-36).

Không có bộ đếm này thì một script thử được bao nhiêu mật khẩu cũng được: `scrypt` chạy ngoài
event loop nên BE không đứng, nhưng cũng không chặn ai. Hai khoá, vì hai cách đoán khác nhau:

- **Theo tên đăng nhập** (đã chuẩn hoá như lúc tra người): 5 lần sai trong 15 phút thì tên ấy
  khoá tới khi lần sai cũ nhất trôi khỏi cửa sổ. Đếm cả tên không có thật, để câu trả lời không
  lộ tên nào có.
- **Theo địa chỉ**: ngưỡng cao hơn hẳn, 50, vì cả một lớp đăng nhập sau cùng một địa chỉ NAT của
  trường, và mười em gõ nhầm không được khoá cả lớp.

Đăng nhập đúng xoá bộ đếm của tên ấy, không xoá bộ đếm của địa chỉ: một tài khoản đúng không làm
sạch được một địa chỉ đang thử hàng loạt tên khác.

Bộ đếm ở trong bộ nhớ của **một** tiến trình BE. Dev và lab đều chạy một uvicorn, không
`--workers`; có BE thứ hai thì bộ đếm phải dời ra Redis (backlog, mục *Khi có process hay BE thứ
hai*). Khởi động lại BE là mở mọi khoá.
"""

import contextlib
import math
import time
from collections import deque
from collections.abc import Callable

from fastapi import Request

WINDOW_SECONDS = 15 * 60
PER_LOGIN = 5
PER_ADDRESS = 50


class SignInLimit:
    """Hai bộ đếm lần thử chưa đúng trong một cửa sổ trượt.

    Một lần thử được ghi **trước** khi tra người và chạy `scrypt` (`attempt`), rồi gỡ đi nếu hoá
    ra đúng (`succeeded`). Ghi sau khi biết sai thì mọi request gửi cùng lúc đều qua bước kiểm
    trước khi lần sai đầu kịp vào sổ: review 21/10/2026 bắn 40 lần song song vào một tên, cả 40
    chạy tới `scrypt`.

    Args:
        clock: Đồng hồ đơn điệu, giây. Test tiêm một đồng hồ giả để khỏi chờ 15 phút.
        window: Độ dài cửa sổ, giây.
        per_login: Số lần sai một tên chịu được trong cửa sổ.
        per_address: Số lần sai một địa chỉ chịu được trong cửa sổ.
    """

    # Cứ ngần này lần thử thì quét bỏ mọi khoá đã hết hạn: tên ngẫu nhiên phun vào không được
    # để lại một khoá vĩnh viễn mỗi tên.
    _SWEEP_EVERY = 512

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        window: float = WINDOW_SECONDS,
        per_login: int = PER_LOGIN,
        per_address: int = PER_ADDRESS,
    ) -> None:
        self._clock = clock
        self._window = window
        self._limits = {"login": per_login, "address": per_address}
        self._tries: dict[tuple[str, str], deque[float]] = {}
        self._since_sweep = 0

    def wait_minutes(self, login: str, address: str) -> int | None:
        """Tên hay địa chỉ này còn bị khoá bao lâu.

        Args:
            login: Khoá của tên, gồm cả vai (`teacher:...`, `student:...`).
            address: Địa chỉ người gọi.

        Returns:
            Số phút còn phải chờ, làm tròn lên; `None` khi chưa khoá.
        """
        now = self._clock()
        waits = []
        for key in (("login", login), ("address", address)):
            tries = self._fresh(key, now)
            if len(tries) >= self._limits[key[0]]:
                # Mở lại khi lần thử cũ nhất trong số cần thiết trôi khỏi cửa sổ.
                oldest = tries[len(tries) - self._limits[key[0]]]
                waits.append(oldest + self._window - now)
        if not waits:
            return None
        return max(1, math.ceil(max(waits) / 60))

    def attempt(self, login: str, address: str) -> float:
        """Ghi một lần thử cho cả tên lẫn địa chỉ, như thể nó sai. Gọi ngay sau `wait_minutes`,
        không có `await` nào ở giữa.

        Args:
            login: Khoá của tên.
            address: Địa chỉ người gọi.

        Returns:
            Dấu thời gian của lần thử, để `succeeded` gỡ đúng nó.
        """
        now = self._clock()
        for key in (("login", login), ("address", address)):
            self._tries.setdefault(key, deque()).append(now)
        self._since_sweep += 1
        if self._since_sweep >= self._SWEEP_EVERY:
            self._since_sweep = 0
            for key in list(self._tries):
                self._fresh(key, now)
        return now

    def succeeded(self, login: str, address: str, stamp: float) -> None:
        """Đăng nhập đúng: tên này đếm lại từ đầu, và lần thử vừa rồi rời sổ của địa chỉ.

        Địa chỉ giữ các lần sai khác của nó: một tài khoản đúng không làm sạch được một địa chỉ
        đang thử hàng loạt tên khác. Nhưng lần đúng thì không được tính, kẻo một lớp 50 em đăng
        nhập đúng sau một NAT là khoá cả lớp.

        Args:
            login: Khoá của tên.
            address: Địa chỉ người gọi.
            stamp: Giá trị `attempt` đã trả cho lần thử này.
        """
        self._tries.pop(("login", login), None)
        tries = self._tries.get(("address", address))
        if tries is not None:
            # Đã bị quét khỏi cửa sổ thì không còn gì để gỡ.
            with contextlib.suppress(ValueError):
                tries.remove(stamp)
            if not tries:
                del self._tries[("address", address)]

    def _fresh(self, key: tuple[str, str], now: float) -> deque[float]:
        tries = self._tries.get(key)
        if tries is None:
            return deque()
        while tries and tries[0] <= now - self._window:
            tries.popleft()
        if not tries:
            del self._tries[key]
        return tries


def get_sign_in_limit(request: Request) -> SignInLimit:
    """Bộ đếm của ứng dụng đang chạy, dựng ở lần gọi đầu.

    Gắn vào `app.state` chứ không là biến module: mỗi test dựng một `FastAPI()` mới thì có một bộ
    đếm mới, và lần sai của test này không khoá tên của test sau.

    Args:
        request: Request đang xử lý.

    Returns:
        Bộ đếm dùng chung của ứng dụng.
    """
    state = request.app.state
    if getattr(state, "sign_in_limit", None) is None:
        state.sign_in_limit = SignInLimit()
    return state.sign_in_limit


def address_of(request: Request) -> str:
    """Địa chỉ người gọi. Ở lab uvicorn chạy `--proxy-headers`, nên đây là địa chỉ Caddy chuyển tới.

    `--forwarded-allow-ips "*"` an toàn chỉ vì BE không publish cổng nào, mọi request qua Caddy, và
    Caddy (không đặt `trusted_proxies`) ghi đè `X-Forwarded-For` bằng địa chỉ thật của kết nối. Đặt
    thêm một proxy trước Caddy (ALB, CloudFront) thì mọi địa chỉ thành địa chỉ của proxy ấy, và
    ngưỡng theo địa chỉ khoá cả thế giới: lúc ấy phải cấu hình `trusted_proxies`.

    Args:
        request: Request đang xử lý.

    Returns:
        Địa chỉ IP, hay `"?"` khi ASGI không cho biết.
    """
    return request.client.host if request.client else "?"


def refused(minutes: int) -> str:
    """Câu báo khoá, một câu cho mọi tên -- có thật hay không.

    Args:
        minutes: Số phút còn phải chờ.

    Returns:
        Câu tiếng Việt cho hộp đăng nhập.
    """
    return f"Bạn nhập sai quá nhiều lần. Thử lại sau {minutes} phút."
