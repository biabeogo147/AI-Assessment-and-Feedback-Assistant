"""Truy cập database cho INGEST, và chỉ cho INGEST.

Khai báo bảng **không** ở đây — nó ở `schema.models`, dùng chung với `services/be` vì hai
service cùng ghi vào một database và hai định nghĩa schema thì lệch nhau được. Ở lại đây đúng
những thứ khác nhau theo process: engine đọc `Settings` của chính service này, và session mở
theo **một việc** vì ở đây không có request nào.

Service này **không** gọi `prepare_schema`. Dựng schema là việc của process API, và lý do nằm
trong docstring của `schema/ddl.py`: `create_all` không bao giờ `ALTER`, nên hai process cùng
dựng là hai process cùng tin mình đúng về một schema chỉ một bên nhìn đủ — và worker khởi động
được **trước** API. Ở đây chỉ `check_schema`, rồi chết ngay nếu lệch.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ingest.config import Settings

_SESSION_MAKER: async_sessionmaker[AsyncSession] | None = None


def create_engine(settings: Settings) -> AsyncEngine:
    """Mở connection pool cho database đã cấu hình.

    Args:
        settings: Settings của process, nơi cung cấp connection string.

    Returns:
        Một async engine. Người gọi sở hữu nó và phải dispose nó.
    """
    return create_async_engine(settings.database_url, future=True)


def bind_sessions(engine: AsyncEngine) -> None:
    """Trỏ `session_scope` vào engine này.

    Args:
        engine: Engine mà mọi session nên dùng.

    Side effects:
        Đặt session factory ở mức module.
    """
    global _SESSION_MAKER
    _SESSION_MAKER = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Một session sống theo **một việc**.

    Mở theo việc chứ không theo process: một job sống vài trăm milli giây còn một process
    sống hàng giờ, và một session giữ suốt một process là một transaction không ai đóng.

    Yields:
        Một AsyncSession, đóng khi khối `async with` đi ra.

    Raises:
        RuntimeError: Nếu process chưa bao giờ gọi `bind_sessions`.
    """
    if _SESSION_MAKER is None:
        raise RuntimeError("Database is not configured; bind_sessions was never called")
    async with _SESSION_MAKER() as session:
        yield session
