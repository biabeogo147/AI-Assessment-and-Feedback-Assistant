"""Truy cập database cho BE, và chỉ cho BE.

Engine được tạo một lần mỗi process rồi phát ra qua một dependency, nên một
request không bao giờ tự mở connection của riêng nó. Bảng được tạo từ metadata
của model lúc startup chứ không qua công cụ migration: schema này chỉ có một
người dùng và chưa có dữ liệu nào đã deploy, nên thêm Alembic vào lúc này là
dựng nghi lễ quanh một file chưa ai phải sửa tới lần thứ hai. Ngay khi có dữ
liệu thật, cái đánh đổi đó đảo chiều -- ADR-21 đã ghi migration là một khoản
chi mà dự án này nhận lấy.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from be.config import Settings
from be.models import Base

_SESSION_MAKER: async_sessionmaker[AsyncSession] | None = None


def create_engine(settings: Settings) -> AsyncEngine:
    """Mở connection pool cho database đã cấu hình.

    Args:
        settings: Settings của process, nơi cung cấp connection string.

    Returns:
        Một async engine. Người gọi sở hữu nó và phải dispose nó.
    """
    return create_async_engine(settings.database_url, future=True)


async def prepare_schema(engine: AsyncEngine) -> None:
    """Tạo mọi bảng còn thiếu.

    Args:
        engine: Engine để chạy lên.

    Side effects:
        Phát CREATE TABLE cho những bảng chưa tồn tại. Bảng đã có thì để nguyên,
        nên hàm này không bao giờ cứu được một cột đã đổi hình dạng.
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


def bind_sessions(engine: AsyncEngine) -> None:
    """Trỏ dependency của request vào engine này.

    Args:
        engine: Engine mà mọi session nên dùng.

    Side effects:
        Đặt session factory ở mức module.
    """
    global _SESSION_MAKER
    _SESSION_MAKER = async_sessionmaker(engine, expire_on_commit=False)


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
