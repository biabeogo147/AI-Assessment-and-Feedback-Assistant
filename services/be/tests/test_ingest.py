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


class _Redis:
    """Một pool Redis chỉ ghi lại, hoặc chết nếu test bảo nó chết."""

    def __init__(self, broken: bool = False) -> None:
        self.rang: list[tuple[str, str]] = []
        self._broken = broken

    async def publish(self, channel: str, message: str) -> None:
        """Ghi lại một tiếng hích.

        Args:
            channel: Channel đích.
            message: Nội dung. Không ai đọc nó.

        Raises:
            OSError: Khi test dựng pool này ở trạng thái gãy.
        """
        if self._broken:
            raise OSError("redis is gone")
        self.rang.append((channel, message))


@pytest.mark.asyncio
async def test_the_owner_is_told_on_the_channel_that_belongs_to_them(library) -> None:
    """Ghi xong thì hích, và hích đúng channel của chủ sở hữu.

    Channel mang `teacher_id`, không mang `document_id`: rail vẽ **cả thư viện**, nên một màn
    hình đang mở là một subscription. Lấy chủ sở hữu bằng `returning` ngay trong câu `UPDATE`,
    nên không có một `SELECT` thứ hai và không có khe nào cho hàng biến mất giữa hai câu lệnh.
    """
    maker, document_id = library
    async with maker() as session:
        owner = (await session.scalar(select(Document))).teacher_id

    redis = _Redis()
    await document_probed(
        {"redis": redis},
        DocumentProbed(
            document_id=document_id, state=DocumentState.READY, page_count=184
        ).model_dump(mode="json"),
    )

    assert redis.rang == [(f"documents:{owner}", "1")]


@pytest.mark.asyncio
async def test_a_dead_channel_does_not_fail_a_job_that_already_did_its_work(library) -> None:
    """Kênh gãy thì job vẫn **xong**, vì hàng đã ghi rồi.

    Ném ra ngoài ở đây là để arq đem job đi thử lại — và lần thử lại ấy ghi đè đúng cái vừa
    ghi đúng. Thứ duy nhất mất đi khi kênh gãy là việc màn hình tự mới lại.
    """
    maker, document_id = library

    written = await document_probed(
        {"redis": _Redis(broken=True)},
        DocumentProbed(
            document_id=document_id, state=DocumentState.READY, page_count=184
        ).model_dump(mode="json"),
    )

    assert written["written"] is True
    async with maker() as session:
        assert (await session.scalar(select(Document))).state == DocumentState.READY


@pytest.mark.asyncio
async def test_a_row_that_is_gone_rings_nobody(library) -> None:
    """Không ghi được hàng nào thì không hích ai cả.

    Một tiếng hích cho một hàng không tồn tại làm mọi màn hình đang mở đọc lại danh sách mà
    không có gì đổi — rẻ, nhưng là một lời nói dối nhỏ về việc *vừa có gì đó xảy ra*.
    """
    redis = _Redis()
    await document_probed(
        {"redis": redis},
        DocumentProbed(document_id="khong-ton-tai", state=DocumentState.READY).model_dump(
            mode="json"
        ),
    )
    assert redis.rang == []
