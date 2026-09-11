"""BE application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from be.config import get_settings
from be.db import bind_sessions, create_engine, prepare_schema
from be.db import get_session as _session_dependency
from be.queue import create_queue_pool
from be.routes import router
from be.seed import seed_if_empty
from be.student_routes import router as student_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Hold one database engine and one Redis pool open for the process.

    Opening either per request would exhaust connections: every student polls,
    and every screen reads.

    Args:
        app: The application whose state carries both pools.

    Side effects:
        Opens a database engine and a Redis pool, creates missing tables, and
        seeds demo data into an empty database. Closes both on shutdown.
    """
    settings = get_settings()

    engine = create_engine(settings)
    await prepare_schema(engine)
    bind_sessions(engine)
    app.state.db_engine = engine

    async for session in _session_dependency():
        if await seed_if_empty(session):
            logger.info("seeded the demo class, roster and published assessment")

    app.state.queue_pool = await create_queue_pool(settings)
    try:
        yield
    finally:
        await app.state.queue_pool.aclose()
        await engine.dispose()


app = FastAPI(
    title="AI Assessment and Feedback Assistant - BE",
    version="0.2.0",
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(student_router)
