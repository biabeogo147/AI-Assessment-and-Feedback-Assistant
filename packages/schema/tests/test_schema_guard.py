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
async def test_a_unique_the_models_declare_but_the_database_lacks_is_drift(engine) -> None:
    """Một unique model khai mà database không giữ thì chết ngay (plan `wave-3-draft-panel`).

    `create_all` không thêm ràng buộc vào bảng đã có, nên luật *"database phân xử"* của một
    unique thêm sau chỉ đứng trên giấy. Index partial `uq_one_open_round_per_attempt` là cái sqlite
    gỡ được; một `UniqueConstraint` thì sqlite không cho `DROP`.
    """
    async with engine.begin() as connection:
        await connection.execute(text("DROP INDEX uq_one_open_round_per_attempt"))

    with pytest.raises(SchemaDrifted) as blew:
        await check_schema(engine)

    assert "thiếu unique rounds(attempt_id)" in str(blew.value)


@pytest.mark.asyncio
async def test_a_unique_the_models_dropped_but_the_database_keeps_is_drift(engine) -> None:
    """Database còn giữ một unique model đã bỏ thì cũng chết ngay.

    Đúng ca đã xảy ra: `teacher_conversations.teacher_id` còn unique trên database cũ sau khi
    giáo viên được mở nhiều đoạn chat, và mọi lần mở đoạn thứ hai là một `IntegrityError`.
    """
    async with engine.begin() as connection:
        await connection.execute(
            text("CREATE UNIQUE INDEX one_thread ON teacher_conversations (teacher_id)")
        )

    with pytest.raises(SchemaDrifted) as blew:
        await check_schema(engine)

    said = str(blew.value)
    assert "thừa unique teacher_conversations(teacher_id)" in said
    assert "ALTER" in said


async def _rebuild(engine, table: str, edit) -> None:
    """Dựng lại một bảng sqlite theo câu `CREATE` đã sửa: sqlite không `ADD`/`DROP CONSTRAINT`.

    Hai test dưới đi đường **constraint** (`get_unique_constraints`), không đường index -- ca thật
    trên Postgres là một constraint.
    """
    async with engine.begin() as connection:
        made = await connection.scalar(
            text("SELECT sql FROM sqlite_master WHERE name = :name"), {"name": table}
        )
        await connection.execute(text(f"ALTER TABLE {table} RENAME TO {table}_old"))
        await connection.execute(text(edit(made)))
        await connection.execute(text(f"DROP TABLE {table}_old"))


@pytest.mark.asyncio
async def test_a_unique_column_the_database_lost_is_drift(engine) -> None:
    """`unique=True` trên `students.student_code` mà database không giữ thì lệch."""
    await _rebuild(engine, "students", lambda made: made.replace(", \n\tUNIQUE (student_code)", ""))

    with pytest.raises(SchemaDrifted) as blew:
        await check_schema(engine)

    assert "thiếu unique students(student_code)" in str(blew.value)


@pytest.mark.asyncio
async def test_a_unique_constraint_the_models_dropped_is_drift(engine) -> None:
    """Đúng hình của ca thật: `UNIQUE (teacher_id)` dạng constraint cấp bảng còn sót lại."""
    await _rebuild(
        engine,
        "teacher_conversations",
        lambda made: made.replace("PRIMARY KEY (id), ", "PRIMARY KEY (id), UNIQUE (teacher_id), "),
    )

    with pytest.raises(SchemaDrifted) as blew:
        await check_schema(engine)

    assert "thừa unique teacher_conversations(teacher_id)" in str(blew.value)


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
