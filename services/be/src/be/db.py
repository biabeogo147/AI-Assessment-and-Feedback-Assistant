"""Database access for BE, and only for BE.

The engine is created once per process and handed out through a dependency, so
a request never opens its own connection. Tables are created from the model
metadata at startup rather than through a migration tool: the schema has one
consumer and no deployed data yet, and adding Alembic now would be ceremony
around a file nobody has needed to change twice. The moment real data exists,
that trade flips -- ADR-21 already records migrations as a cost this project
took on.
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
    """Open the connection pool for the configured database.

    Args:
        settings: Process settings supplying the connection string.

    Returns:
        An async engine. The caller owns it and must dispose of it.
    """
    return create_async_engine(settings.database_url, future=True)


async def prepare_schema(engine: AsyncEngine) -> None:
    """Create any missing table.

    Args:
        engine: Engine to run against.

    Side effects:
        Issues CREATE TABLE for tables that do not exist. Existing tables are
        left untouched, so this never rescues a column that changed shape.
    """
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


def bind_sessions(engine: AsyncEngine) -> None:
    """Point the request dependency at this engine.

    Args:
        engine: Engine every session should use.

    Side effects:
        Sets the module-level session factory.
    """
    global _SESSION_MAKER
    _SESSION_MAKER = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield one session per request.

    Yields:
        An AsyncSession that is closed when the request ends.

    Raises:
        RuntimeError: If the application never called bind_sessions, which
            means a route is running outside the configured lifespan.
    """
    if _SESSION_MAKER is None:
        raise RuntimeError("Database is not configured; bind_sessions was never called")
    async with _SESSION_MAKER() as session:
        yield session
