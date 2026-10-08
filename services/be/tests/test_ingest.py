"""Đường duy nhất mà kết quả xử lý tài liệu đi vào Postgres.

Handler này chạy trong process worker của BE, không trong một request, nên mấy test dưới gọi nó
thẳng. Chúng canh ba chỗ nó có thể nói dối: ghi thiếu một cột, ghi vào hàng không còn tồn tại,
và ném ra ngoài một thứ mà arq sẽ thử lại mãi không xong.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.db import bind_sessions, prepare_schema
from be.ingest import document_probed
from be.models import Document, Teacher
from contracts import DocumentProbed, DocumentState


@pytest_asyncio.fixture
async def library():
    """Một database có đúng một tài liệu, đang ở *đang xử lý*.

    Yields:
        Session maker, và id của tài liệu ấy.
    """
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        teacher = Teacher(full_name="Cô Trần Thị A", teacher_code="GV-001")
        session.add(teacher)
        await session.flush()
        row = Document(
            teacher_id=teacher.id,
            filename="SGK Giải tích 12.pdf",
            content_type="application/pdf",
            byte_size=2048,
            storage_key=f"documents/{teacher.id}/x.pdf",
            uploaded_at=datetime.now(UTC),
        )
        session.add(row)
        await session.commit()
        document_id = row.id

    yield maker, document_id

    await engine.dispose()
    db_module._SESSION_MAKER = None


@pytest.mark.asyncio
async def test_a_verdict_lands_in_all_three_columns(library) -> None:
    """Ghi đủ ba cột trong một lượt.

    Ghi thiếu một cột là hình dạng hỏng khó thấy nhất ở đây: trạng thái đổi, nên chip trông
    đúng, nhưng số trang vẫn `None` và plan sau sẽ đi tìm một con số không ai ghi.
    """
    maker, document_id = library

    await document_probed(
        {},
        DocumentProbed(
            document_id=document_id, state=DocumentState.READY, page_count=184
        ).model_dump(mode="json"),
    )

    async with maker() as session:
        row = await session.scalar(select(Document))
        assert row is not None
        assert row.state == DocumentState.READY
        assert row.page_count == 184
        assert row.fault == ""


@pytest.mark.asyncio
async def test_a_refusal_keeps_the_reason_a_teacher_can_read(library) -> None:
    """*Không đọc được chữ* phải mang theo lý do, vì lý do ấy đi thẳng lên chip."""
    maker, document_id = library

    await document_probed(
        {},
        DocumentProbed(
            document_id=document_id,
            state=DocumentState.NO_TEXT_LAYER,
            page_count=184,
            fault="Tệp này là ảnh scan, chưa đọc được chữ.",
        ).model_dump(mode="json"),
    )

    async with maker() as session:
        row = await session.scalar(select(Document))
        assert row is not None
        assert row.state == DocumentState.NO_TEXT_LAYER
        assert "scan" in row.fault


@pytest.mark.asyncio
async def test_a_result_for_a_row_that_is_gone_is_dropped_not_raised(library) -> None:
    """Hàng không còn thì bỏ job, **không ném**.

    Giáo viên đã xoá tài liệu trong lúc nó đang được đọc, hoặc database vừa bị dựng lại. Ném ra
    ngoài là để arq thử lại một job không bao giờ thành công được, rồi lặp lại đúng chừng ấy
    lần — và không lần nào sửa được gì.
    """
    maker, _ = library

    written = await document_probed(
        {},
        DocumentProbed(
            document_id="khong-ton-tai", state=DocumentState.READY, page_count=3
        ).model_dump(mode="json"),
    )

    assert written["written"] is False
    async with maker() as session:
        row = await session.scalar(select(Document))
        assert row is not None
        assert row.state == DocumentState.PROCESSING


@pytest.mark.asyncio
async def test_the_handler_never_inserts_a_row(library) -> None:
    """Chỉ `UPDATE`, không bao giờ `INSERT`.

    Một job tạo hàng mới là một đường thứ hai để tài liệu xuất hiện trong thư viện — một đường
    không đi qua lớp kiểm đuôi tệp, không qua trần kích thước, và không có byte nào trong object
    storage đứng sau nó.
    """
    maker, _ = library

    await document_probed(
        {},
        DocumentProbed(
            document_id="khong-ton-tai", state=DocumentState.READY, page_count=3
        ).model_dump(mode="json"),
    )

    async with maker() as session:
        assert len((await session.scalars(select(Document))).all()) == 1
