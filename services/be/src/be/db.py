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

from sqlalchemy import inspect, text
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


class SchemaDrifted(RuntimeError):
    """Database đang có không khớp với model trong code.

    Một exception riêng chứ không phải một `RuntimeError` trần, vì chỗ bắt nó là `main` và
    câu nó mang theo là câu một người đọc rồi gõ một lệnh.
    """


# Lệnh dựng lại. Nằm trong chuỗi lỗi vì một thông báo nói "schema lệch" mà không nói phải
# làm gì là một thông báo bắt người ta đi tìm.
_HOW_TO_FIX = ".\\dev.ps1 db-reset"


async def check_schema(engine: AsyncEngine) -> None:
    """Đối chiếu bảng thật với model, và **chết ngay** khi chúng lệch.

    `create_all` chỉ tạo bảng còn thiếu; nó không bao giờ `ALTER` một bảng đã có. Nên một
    model thêm cột rồi chạy trên database cũ sẽ khởi động sạch sẽ, rồi hỏng ở lần ghi đầu
    tiên — và hỏng dưới dạng một chuỗi lỗi 500 từ những route không liên quan gì tới nhau.
    Đúng chuyện đã xảy ra: `assessments` thiếu `teacher_id`, nên mọi lần tạo đề đều ném, và
    trên màn hình nó đọc ra như lỗi của khung chat.

    Chỉ kiểm **cột còn thiếu**, không kiểm kiểu hay index: đó là phần `create_all` không
    cứu được, và cũng là phần một người đọc thông báo sửa được bằng một lệnh.

    Args:
        engine: Engine để soi.

    Raises:
        SchemaDrifted: Khi một bảng của model có cột mà database không có.

    Side effects:
        Đọc catalog của database.
    """

    def missing(connection) -> list[str]:
        looker = inspect(connection)
        found = set(looker.get_table_names())
        gaps = []
        for name, table in Base.metadata.tables.items():
            if name not in found:
                # Bảng chưa có là việc của `create_all`, không phải lệch.
                continue
            columns = {one["name"] for one in looker.get_columns(name)}
            for column in table.columns:
                if column.name not in columns:
                    gaps.append(f"{name}.{column.name}")
        return gaps

    async with engine.begin() as connection:
        gaps = await connection.run_sync(missing)

    if gaps:
        raise SchemaDrifted(
            "database lệch so với model, thiếu: "
            + ", ".join(sorted(gaps))
            + f". Dữ liệu local bỏ được, nên dựng lại bằng: {_HOW_TO_FIX}"
        )


async def reset_schema(engine: AsyncEngine) -> None:
    """Xoá sạch rồi dựng lại schema theo model hiện tại.

    Đây là **đường của máy dev**, và nó xoá hết dữ liệu — một đánh đổi đã được chọn: ở local
    thì dữ liệu là thứ seed lại được, còn một schema lệch thì không sửa được bằng gì khác khi
    repo không giữ migration (xem docstring của module).

    Trên Postgres: `DROP SCHEMA public CASCADE` chứ không `drop_all`. `drop_all` chỉ biết
    những bảng model còn khai, nên một bảng đã bị xoá khỏi code sẽ ở lại mãi trong database —
    đúng loại rác làm lần đối chiếu sau nói dối. Các dialect khác (sqlite của test) không có
    schema để xoá, nên ở đó `drop_all` là thứ duy nhất có.

    Args:
        engine: Engine để chạy lên.

    Side effects:
        **Xoá toàn bộ** schema `public` rồi tạo lại mọi bảng. Không hỏi lại.
    """
    async with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            await connection.execute(text("DROP SCHEMA public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
        else:
            # sqlite không có schema để xoá. Dùng `drop_all`, và chấp nhận giới hạn của
            # nó -- một bảng không còn trong model sẽ ở lại; file database của test thì
            # sinh ra mới mỗi lần nên giới hạn ấy không chạm tới ai.
            await connection.run_sync(Base.metadata.drop_all)
    await prepare_schema(engine)


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
