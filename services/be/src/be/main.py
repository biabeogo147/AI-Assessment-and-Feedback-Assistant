"""Điểm vào của ứng dụng BE."""

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
from be.teacher_chat import router as teacher_router
from be.teacher_routes import router as teacher_assessment_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Giữ mở một database engine và một Redis pool cho cả process.

    Mở bất kỳ cái nào trong hai theo từng request sẽ làm cạn connection: học sinh
    nào cũng poll, và màn hình nào cũng đọc.

    Args:
        app: Ứng dụng mà state của nó chở cả hai pool.

    Side effects:
        Mở một database engine và một Redis pool, tạo những bảng còn thiếu, và
        seed dữ liệu demo vào một database rỗng. Đóng cả hai khi shutdown.
    """
    settings = get_settings()

    engine = create_engine(settings)
    await prepare_schema(engine)
    bind_sessions(engine)
    app.state.db_engine = engine

    async for session in _session_dependency():
        if await seed_if_empty(session):
            logger.info("seeded the demo class, roster and published assessment")

    # Một queue chết không được phép kéo pha 1 chết theo. Làm một đề, nộp nó và
    # đọc điểm sàn không hề chạm tới AGENT (ADR-20), còn ADR-16 gọi điểm đó là
    # một cái sàn -- một cái sàn mà phải cần tới service thứ hai mới đứng được
    # thì không phải sàn. Thứ thật sự hỏng là mọi thứ cần nội dung do model sinh
    # ra, và những route đó trả 503 chứ không làm startup gãy.
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
app.include_router(teacher_router)
app.include_router(teacher_assessment_router)
