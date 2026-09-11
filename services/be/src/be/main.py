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

    # A dead queue must not take phase 1 down with it. Sitting a paper,
    # submitting it and reading the floor score never touch AGENT (ADR-20), and
    # ADR-16 calls that score a floor -- a floor that needs a second service to
    # stand up is not one. What does break is everything that needs generated
    # content, and those routes answer 503 rather than failing at startup.
    try:
        app.state.queue_pool = await create_queue_pool(settings)
    except (OSError, RuntimeError) as exc:
        app.state.queue_pool = None
        logger.warning("queue unreachable (%s); phase 2 will answer 503 until it returns", exc)

    try:
        yield
    finally:
        if app.state.queue_pool is not None:
            await app.state.queue_pool.aclose()
        await engine.dispose()


app = FastAPI(
    title="AI Assessment and Feedback Assistant - BE",
    version="0.2.0",
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(student_router)
