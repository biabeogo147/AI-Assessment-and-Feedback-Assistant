"""Truy cập database cho BE, và chỉ cho BE.

Engine được tạo một lần mỗi process rồi phát ra qua một dependency, nên một
request không bao giờ tự mở connection của riêng nó.

Module này **không khai schema và không phát một câu DDL nào**. Khai báo bảng ở
`schema.models`, còn dựng/đối chiếu/dựng lại ở `schema.ddl`, vì `services/ingest`
cũng ghi vào chính database này và một định nghĩa schema sống trong một service
thì service kia không với tới được. Ở lại đây đúng những thứ **khác nhau theo
process**: engine đọc `Settings` của chính BE, và session thì gắn với vòng đời
một request của FastAPI.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from be.config import Settings

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
    """Trỏ dependency của request vào engine này.

    Args:
        engine: Engine mà mọi session nên dùng.

    Side effects:
        Đặt session factory ở mức module.
    """
    global _SESSION_MAKER
    _SESSION_MAKER = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Một session sống theo **một việc**, không theo một request.

    `get_session` là dependency của FastAPI: session nó mở bị đóng khi **response** kết
    thúc. Với một lượt chat phát ra qua SSE, "response kết thúc" là sau cả vòng soạn đề —
    nên một đường dài như vậy nên sở hữu session của chính nó thay vì mượn vòng đời của
    request.

    Nó **không** làm cho việc chạy tiếp khi client bỏ đi: generator bị cancel thì cả khối
    `async with` này đi theo. Quyền sở hữu rõ ràng là thứ duy nhất nó mua.

    Yields:
        Một AsyncSession, đóng khi khối `async with` đi ra.

    Raises:
        RuntimeError: Nếu ứng dụng chưa bao giờ gọi `bind_sessions`.
    """
    if _SESSION_MAKER is None:
        raise RuntimeError("Database is not configured; bind_sessions was never called")
    async with _SESSION_MAKER() as session:
        yield session


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield một session cho mỗi request.

    Yields:
        Một AsyncSession được đóng khi request kết thúc.

    Raises:
        RuntimeError: Nếu ứng dụng chưa bao giờ gọi bind_sessions, nghĩa là một
            route đang chạy ngoài lifespan đã cấu hình.
    """
    if _SESSION_MAKER is None:
        raise RuntimeError("Database is not configured; bind_sessions was never called")
    async with _SESSION_MAKER() as session:
        yield session
