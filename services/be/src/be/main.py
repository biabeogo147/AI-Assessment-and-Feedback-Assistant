"""BE application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from be.config import get_settings
from be.queue import create_queue_pool
from be.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Hold one Redis pool open for the life of the process.

    Opening a pool per request would exhaust connections under polling, since
    every client polls its job once a second.

    Args:
        app: The application whose state carries the pool.

    Side effects:
        Opens a Redis connection pool on startup and closes it on shutdown.
    """
    app.state.queue_pool = await create_queue_pool(get_settings())
    try:
        yield
    finally:
        await app.state.queue_pool.aclose()


app = FastAPI(
    title="AI Assessment and Feedback Assistant - BE",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)
