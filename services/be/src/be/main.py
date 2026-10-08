"""Điểm vào của ứng dụng BE."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from be.config import get_settings
from be.db import bind_sessions, check_schema, create_engine, prepare_schema
from be.db import get_session as _session_dependency
from be.queue import create_queue_pool
from be.routes import router
from be.seed import seed_if_empty
from be.storage import bind_store, create_store
from be.student_routes import router as student_router
from be.teacher_chat import router as teacher_router
from be.teacher_documents import router as teacher_document_router
from be.teacher_routes import router as teacher_assessment_router

logger = logging.getLogger(__name__)


def _hear_our_own_loggers(level: str = "INFO") -> None:
    """Cho log của `be.*` đi ra được màn hình.

    **Trước đợt này BE không cấu hình logging gì cả.** uvicorn chỉ dựng logger của chính
    nó, nên `logging.getLogger("be.drafting")` không có handler nào và mọi `logger.info`
    của chúng ta rơi vào hư không.

    Cái giá đo được ngày 06/10/2026: một đề 3 câu về 2 câu, và dòng nói **vì sao** --
    *"đề trùng một câu đã có"* -- không tồn tại ở bất cứ đâu. Phải đọc bốn nhánh của
    `harvest` rồi loại trừ mới đoán ra nguyên nhân. Một hệ thống ghi log mà không ai bật
    thì không phải ghi log, nó là chú thích.

    Cấu hình **đúng cây logger của mình**, không dùng `basicConfig`. Bản đầu dùng
    `basicConfig` và nó sai một cách khó thấy: hàm ấy không làm gì khi root logger đã có
    handler, nên nó im lặng thành một lời gọi rỗng ở bất cứ process nào dựng handler
    trước -- pytest là một, và bất cứ ai thêm một dòng `dictConfig` cho uvicorn cũng vậy.
    Một cấu hình chỉ đúng khi không ai khác chạm vào logging thì không phải cấu hình.

    Logger của uvicorn không bị đụng tới, nên access log giữ nguyên hình dạng.

    Args:
        level: Mức log, lấy từ `Settings.log_level`.

    Side effects:
        Gắn một handler lên logger `be` nếu nó chưa có cái nào, và đặt mức cho nó.
    """
    ours = logging.getLogger("be")
    if not ours.handlers:
        writing = logging.StreamHandler()
        writing.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        ours.addHandler(writing)
    ours.setLevel(level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Giữ mở một database engine và một Redis pool cho cả process.

    Mở bất kỳ cái nào trong hai theo từng request sẽ làm cạn connection: học sinh
    nào cũng poll, và màn hình nào cũng đọc.

    Args:
        app: Ứng dụng mà state của nó chở cả hai pool.

    Side effects:
        Mở một database engine, một object store và một Redis pool, tạo những bảng
        còn thiếu, dựng bucket nếu chưa có, và seed dữ liệu demo vào một database
        rỗng. Đóng engine và pool khi shutdown.

    Raises:
        SchemaDrifted: Khi database đang có thiếu cột so với model. Startup dừng ở đây,
            kèm tên cột và lệnh dựng lại — một process chạy tiếp trên schema lệch chỉ
            dời cái lỗi tới chỗ khó đọc hơn.
        StorageUnavailable: Khi không tới được object storage. Cùng lý do: một BE
            nhận tài liệu mà không có chỗ cất là một BE nói dối ở mỗi lần upload.
    """
    settings = get_settings()
    _hear_our_own_loggers(settings.log_level)

    engine = create_engine(settings)
    await prepare_schema(engine)
    # Chết ngay tại đây khi database cũ hơn model. `create_all` ở dòng trên tạo bảng còn
    # thiếu nhưng không bao giờ `ALTER` một bảng đã có, nên không có chốt này thì process
    # khởi động sạch sẽ rồi hỏng ở lần ghi đầu tiên — dưới dạng một chuỗi 500 từ những
    # route không liên quan gì nhau, cách rất xa nguyên nhân.
    await check_schema(engine)
    bind_sessions(engine)
    app.state.db_engine = engine

    # Chết ngay nếu không tới được object storage, khác hẳn khối queue ở dưới. Queue chỉ
    # đỡ những thứ cần model, và ADR-20 gọi pha 1 là một cái sàn đứng được mà không cần
    # AGENT. Object storage thì **là** nơi ở duy nhất của tài liệu: một route mà việc duy
    # nhất của nó là cất byte thì không có phiên bản suy giảm nào. Dựng được client cũng
    # không chứng minh gì -- `Minio(...)` không chạm mạng -- nên `ensure_ready` là phép
    # thử thật, và nó phải chạy ở đây chứ không phải ở lần upload đầu tiên.
    store = create_store(settings)
    await store.ensure_ready()
    bind_store(store)
    app.state.object_store = store

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
app.include_router(teacher_document_router)
