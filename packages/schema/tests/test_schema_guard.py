"""Chốt kiểm schema: một database cũ hơn model phải làm process **chết ngay**.

Vì sao test này đáng có: `create_all` tạo bảng còn thiếu nhưng không bao giờ `ALTER` một
bảng đã có, nên một model thêm cột rồi chạy trên database cũ **khởi động sạch sẽ** rồi hỏng
ở lần ghi đầu tiên. Và nó hỏng dưới dạng một chuỗi lỗi 500 từ những route không liên quan gì
nhau — đo được trên máy thật: `assessments` thiếu `teacher_id`, nên mọi lần tạo đề đều ném,
và trên màn hình nó đọc ra như lỗi của khung chat.
"""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from schema.ddl import SchemaDrifted, check_schema, prepare_schema, reset_schema
from schema.models import Base


@pytest_asyncio.fixture
async def engine():
    """Một database sqlite trong bộ nhớ, đã dựng đủ bảng theo model.

    Cùng khuôn với các test BE khác: một engine `sqlite+aiosqlite://` giữ đúng một connection
    cho cả test, nên mọi lệnh đi vào cùng một database.
    """
    made = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(made)
    try:
        yield made
    finally:
        await made.dispose()


@pytest.mark.asyncio
async def test_a_database_that_matches_the_models_starts_quietly(engine) -> None:
    """Đường thường: khớp thì không nói gì."""
    await check_schema(engine)


@pytest.mark.asyncio
async def test_a_column_the_models_added_stops_startup_and_names_itself(engine) -> None:
    """Thiếu một cột thì chết ngay, và thông báo nói **cột nào** cùng **lệnh nào**.

    Một thông báo chỉ nói "schema lệch" là một thông báo bắt người đọc đi tìm; chỗ tốn thời
    gian nhất của sự cố thật không phải lúc sửa mà là lúc tìm ra phải sửa gì.

    Cột bị bỏ ở đây là `grade` chứ không phải `teacher_id` của ca thật, chỉ vì sqlite từ chối
    `DROP COLUMN` trên một cột có khoá ngoại. Thứ được canh là cùng một luật.
    """
    async with engine.begin() as connection:
        await connection.execute(text("ALTER TABLE assessments DROP COLUMN grade"))

    with pytest.raises(SchemaDrifted) as blew:
        await check_schema(engine)

    said = str(blew.value)
    assert "assessments.grade" in said
    assert "db-reset" in said


@pytest.mark.asyncio
async def test_a_table_the_models_added_is_not_drift(engine) -> None:
    """Bảng còn thiếu là việc của `create_all`, không phải lệch.

    Phân biệt hai ca này là cả giá trị của chốt: nếu một bảng mới cũng kêu *lệch* thì lần
    đầu ai đó chạy trên database trống sẽ bị bảo đi xoá một database chưa có gì.
    """
    async with engine.begin() as connection:
        await connection.execute(text("DROP TABLE teacher_turns"))

    await check_schema(engine)


@pytest.mark.asyncio
async def test_a_reset_rebuilds_every_table_the_models_declare(engine) -> None:
    """`reset_schema` đưa một database lệch về khớp, kể cả khi nó thiếu cột.

    Chạy trên sqlite nên nhánh `DROP SCHEMA` của Postgres không đi qua đây; thứ được canh là
    hợp đồng của hàm — sau nó, mọi bảng của model có mặt và `check_schema` im lặng.
    """
    async with engine.begin() as connection:
        await connection.execute(text("ALTER TABLE assessments DROP COLUMN grade"))

    await reset_schema(engine)

    await check_schema(engine)
    async with engine.begin() as connection:
        found = await connection.run_sync(
            lambda sync: set(__import__("sqlalchemy").inspect(sync).get_table_names())
        )
    assert set(Base.metadata.tables) <= found
