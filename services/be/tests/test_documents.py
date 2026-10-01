"""Thư viện tài liệu của giáo viên.

Vòng này mới làm cái vỏ: tải lên được, liệt kê được, hiện trên rail được. Nội dung tài liệu
**chưa** đi vào prompt của AGENT ở bất cứ đâu, nên mấy test dưới đây cố ý không khẳng định gì
về việc đề ra sát sách hơn — chúng chỉ canh bốn chỗ mà cái vỏ có thể nói dối: nhận nhầm thứ
không phải tài liệu, khai sai kích thước, để tài liệu người này lọt sang người khác, và bịa ra
một con số mà không ai đọc file để biết.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.db import bind_sessions, prepare_schema
from be.models import Document, Teacher
from be.seed import seed_if_empty
from be.teacher_documents import router as document_router

TEACHER = {"X-Actor": "teacher:GV-001"}
OTHER = {"X-Actor": "teacher:GV-002"}


@pytest_asyncio.fixture
async def stack():
    """Một app có hai giáo viên, để "không phải của tôi" là một ca thật sự tồn tại."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        session.add(Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002"))
        await session.commit()

    app = FastAPI()
    app.include_router(document_router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker

    await engine.dispose()
    db_module._SESSION_MAKER = None


def _file(name: str = "SGK Giải tích 12.pdf", body: bytes = b"%PDF-1.7 ba trang gia vo"):
    """Một file tải lên, đúng hình dạng multipart mà trình duyệt gửi."""
    return {"file": (name, body, "application/pdf")}


@pytest.mark.asyncio
async def test_an_uploaded_document_comes_back_in_the_library(stack) -> None:
    """Tải lên rồi liệt kê thì thấy đúng nó, với đúng tên giáo viên đã đặt."""
    client, _ = stack
    body = b"%PDF-1.7 " + b"x" * 300

    sent = await client.post("/api/teacher/documents", headers=TEACHER, files=_file(body=body))
    assert sent.status_code == 201, sent.text
    assert sent.json()["filename"] == "SGK Giải tích 12.pdf"
    assert sent.json()["kind"] == "PDF"

    listed = await client.get("/api/teacher/documents", headers=TEACHER)
    assert listed.status_code == 200
    assert [one["document_id"] for one in listed.json()] == [sent.json()["document_id"]]


@pytest.mark.asyncio
async def test_the_size_is_measured_not_believed(stack) -> None:
    """Kích thước là độ dài chuỗi byte nhận được, không phải lời khai của client.

    Con số này về sau hiện trên chip ở rail. Lấy từ `content-length` thì một client khai sai
    sẽ để lại một con số sai **trên màn hình**, và không có gì mâu thuẫn để ai đó nhận ra.
    """
    client, maker = stack
    body = b"%PDF-1.7 " + b"y" * 1234

    sent = await client.post(
        "/api/teacher/documents",
        headers={**TEACHER, "content-length": "999999"},
        files=_file(body=body),
    )
    assert sent.status_code == 201
    assert sent.json()["byte_size"] == len(body)

    async with maker() as session:
        row = await session.scalar(select(Document))
        assert row is not None
        assert len(row.content) == len(body)


@pytest.mark.asyncio
async def test_a_document_belongs_to_the_teacher_who_uploaded_it(stack) -> None:
    """Thư viện tìm qua `teacher_id`, nên không id nào với tới tài liệu người khác (ADR-22)."""
    client, _ = stack
    await client.post("/api/teacher/documents", headers=TEACHER, files=_file())

    mine = await client.get("/api/teacher/documents", headers=TEACHER)
    theirs = await client.get("/api/teacher/documents", headers=OTHER)
    assert len(mine.json()) == 1
    assert theirs.json() == []


@pytest.mark.asyncio
async def test_the_newest_document_is_first(stack) -> None:
    """Rail dựng để tìm thứ **vừa** tải lên, nên thứ tự là mới nhất trước."""
    client, maker = stack
    for name in ("cũ.pdf", "mới.pdf"):
        sent = await client.post("/api/teacher/documents", headers=TEACHER, files=_file(name=name))
        assert sent.status_code == 201

    # Đẩy mốc của file đầu lùi lại, vì hai lần tải lên trong cùng một mili giây là chuyện
    # thường trong test và khi đó thứ tự không nói lên điều gì.
    async with maker() as session:
        row = await session.scalar(select(Document).where(Document.filename == "cũ.pdf"))
        row.uploaded_at = datetime(2026, 1, 1, tzinfo=UTC)
        session.add(row)
        await session.commit()

    listed = await client.get("/api/teacher/documents", headers=TEACHER)
    assert [one["filename"] for one in listed.json()] == ["mới.pdf", "cũ.pdf"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    ["ảnh.png", "bảng điểm.xlsx", "khong-co-duoi"],
)
async def test_what_is_not_a_document_is_refused(stack, name: str) -> None:
    """Lọc theo **đuôi tên**, thứ giáo viên nhìn thấy, chứ không theo content-type client khai."""
    client, _ = stack
    sent = await client.post("/api/teacher/documents", headers=TEACHER, files=_file(name=name))
    assert sent.status_code == 400
    assert "PDF" in sent.json()["detail"]


@pytest.mark.asyncio
async def test_an_empty_file_is_refused(stack) -> None:
    """Một file rỗng là một lần chọn nhầm, không phải một tài liệu."""
    client, _ = stack
    sent = await client.post("/api/teacher/documents", headers=TEACHER, files=_file(body=b""))
    assert sent.status_code == 400


@pytest.mark.asyncio
async def test_a_file_over_the_cap_is_refused_and_says_the_cap(stack) -> None:
    """Quá lớn thì 413, và câu từ chối nói ra **mức** — nếu không thì không ai sửa được gì."""
    client, _ = stack
    sent = await client.post(
        "/api/teacher/documents",
        headers=TEACHER,
        files=_file(body=b"%PDF-1.7 " + b"z" * (10 * 1024 * 1024)),
    )
    assert sent.status_code == 413
    assert "10 MB" in sent.json()["detail"]


@pytest.mark.asyncio
async def test_nothing_claims_a_page_count(stack) -> None:
    """Không field nào nói số trang hay "đọc được chữ".

    Vòng này không mở file ra đọc, nên hai thứ đó chỉ có thể là chữ bịa. Test này đỏ vào đúng
    ngày ai đó thêm một field như vậy mà chưa có phần đọc PDF đi kèm — và đó là ngày cần nhớ
    lại lý do.
    """
    client, _ = stack
    sent = await client.post("/api/teacher/documents", headers=TEACHER, files=_file())
    assert set(sent.json()) == {"document_id", "filename", "kind", "byte_size", "uploaded_at"}
