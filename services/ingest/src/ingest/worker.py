"""Process worker arq của INGEST.

Chạy bằng:  arq ingest.worker.WorkerSettings   (hoặc `.\\dev.ps1 ingest`)

**Service thứ năm, và service thứ hai giữ credential database.** Nó tồn tại vì vòng xử lý tài
liệu không có ai chờ: giáo viên đã rời màn hình tải lên từ lâu, và kết quả vẫn phải vào
database — một process đã chết thì không có ai để trả 503 cho.

Nó **không sở hữu một quyết định nào**. Việc duy nhất của nó là ghi lại thứ `services/document`
đã báo về, đúng hình dạng mà `AGENTS.md` gọi là *"AGENT decides nothing"*, chỉ khác ở một điểm
và điểm ấy là cả lý do nó không phải service đọc-và-báo: nó **giữ credential database**. Việc ấy
hợp lệ — cái làm `agent` với `document` thành service không-credential là chúng không ghi vào
bảng nào, chứ không phải việc chúng chạy process riêng.

Vì sao nó không phải một process của `services/be`, mà là một service riêng: cho tới plan 2c nó
đúng là vậy, và không chỗ nào nói được process nào được làm gì. `be/config.py` chở hai mươi
trường cho một worker chạm năm; luật *API dựng schema, worker chỉ kiểm* sống trong một
docstring; và hai bootstrap gần giống nhau khác đúng một dòng. Tách ra làm cái ranh giới ấy
thành thứ `lint-imports` canh được: service này **không import nổi** một dòng nào của `be`, nên
không cần một danh sách module nghiệp vụ nào — và một danh sách không tồn tại thì không lỗi
thời được.

Một hạn chế đã biết trên Windows: arq không đăng ký được signal handler, nên Ctrl+C cắt ngang
job đang chạy. Ở đường này nó để lại một tài liệu đứng ở *đang xử lý*, và BE suy ra *xử lý hỏng*
khi nó đứng quá lâu — xem `be/teacher_documents.py`.
"""

import logging

from arq.connections import RedisSettings
from arq.worker import func

from contracts import DOCUMENT_PROBED_TASK
from ingest.config import get_settings
from ingest.db import bind_sessions, create_engine
from ingest.handlers import document_probed
from schema.ddl import check_schema

logger = logging.getLogger(__name__)

_settings = get_settings()

# arq mặc định timeout kết nối một giây, và mức đó quá chặt với Docker Desktop trên Windows:
# port proxy của nó cần vài giây sau khi container báo healthy mới chịu nhận kết nối, nên
# process chết ngay lúc startup thay vì chờ. Con số này nay có **bốn** bản trong repo --
# `be/queue.py`, `agent/worker.py`, `document/worker.py`, và đây -- và nhân bản là có chủ đích:
# bốn service không import nhau được, và năm giây không phải một hợp đồng giữa chúng, nó là một
# phép đo về cái máy đang chạy mà cả bốn cùng đứng trên. Lệch nhau thì hậu quả là một process
# chờ lâu hơn, không phải hai bên hiểu sai nhau.
_CONNECT_TIMEOUT_SECONDS = 5


def _hear_our_own_loggers(level: str) -> None:
    """Cho log của `ingest.*` đi ra được màn hình.

    **Đây là chỗ một lỗi thật được chữa.** Bản trước của file này — hồi nó còn là
    `be/worker.py` — gọi `logging.basicConfig(level=logging.INFO)`, tức hardcode mức log và
    bỏ qua `LOG_LEVEL`. Hệ quả: `LOG_LEVEL=WARNING` trong .env làm process API im nhưng process
    worker vẫn nói, và không một dòng nào ở đâu nói ra sự khác biệt ấy. Đúng loại chỗ mờ mà
    plan 2c tồn tại để dọn: một process làm khác process kia mà không ai khai.

    Cấu hình **đúng cây logger của mình**, không dùng `basicConfig`, và lý do đã ghi ở
    `be/main.py`: hàm ấy không làm gì khi root logger đã có handler, nên nó im lặng thành một
    lời gọi rỗng ở bất cứ process nào dựng handler trước — pytest là một. Một cấu hình chỉ đúng
    khi không ai khác chạm vào logging thì không phải cấu hình.

    Args:
        level: Mức log, lấy từ `Settings.log_level`.

    Side effects:
        Gắn một handler lên logger `ingest` nếu nó chưa có cái nào, và đặt mức cho nó.
    """
    ours = logging.getLogger("ingest")
    if not ours.handlers:
        writing = logging.StreamHandler()
        writing.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        ours.addHandler(writing)
    ours.setLevel(level)


def _redis_settings() -> RedisSettings:
    """Dựng RedisSettings cho worker.

    Returns:
        RedisSettings arq dùng được ngay.
    """
    parsed = RedisSettings.from_dsn(_settings.redis_url)
    parsed.conn_timeout = _CONNECT_TIMEOUT_SECONDS
    return parsed


async def startup(ctx: dict) -> None:
    """Mở engine cho cả process, kiểm schema, rồi nói ra đang tiêu thụ queue nào.

    Args:
        ctx: Context worker của arq. Nhận thêm khoá `db_engine` để shutdown đóng được nó.

    Side effects:
        Mở một database engine và đặt session factory ở mức module.

    Raises:
        SchemaDrifted: Khi database đang có thiếu cột so với model. Process dừng ở đây kèm tên
            cột và lệnh dựng lại — một worker chạy êm trên schema lệch sẽ hỏng ở lần `UPDATE`
            đầu tiên, cách rất xa nguyên nhân.
    """
    _hear_our_own_loggers(_settings.log_level)

    engine = create_engine(_settings)
    # `check_schema` chứ không `prepare_schema`: xem docstring của `ingest/db.py`.
    await check_schema(engine)
    bind_sessions(engine)
    ctx["db_engine"] = engine
    logger.info(
        "INGEST ready: queue=%s redis=%s",
        _settings.ingest_queue_name,
        _settings.redis_url,
    )


async def shutdown(ctx: dict) -> None:
    """Đóng engine.

    Args:
        ctx: Context worker của arq.

    Side effects:
        Trả mọi connection về. Trên Windows arq không tắt êm được, nên đừng dựa vào hàm này
        chạy sau Ctrl+C.
    """
    engine = ctx.pop("db_engine", None)
    if engine is not None:
        await engine.dispose()


class WorkerSettings:
    """Cấu hình worker của arq.

    Task đăng ký dưới hằng số lấy từ `contracts`, nên đổi tên hàm Python không làm hỏng lời gọi
    enqueue của `services/document`.
    """

    functions = [func(document_probed, name=DOCUMENT_PROBED_TASK)]
    queue_name = _settings.ingest_queue_name
    redis_settings = _redis_settings()
    # Không giữ kết quả: không ai đọc chúng. Kết quả của một job ghi database là chính cái hàng
    # đã được ghi.
    keep_result = 0
    on_startup = startup
    on_shutdown = shutdown
