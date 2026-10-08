"""Thư viện tài liệu của giáo viên.

Nội dung tài liệu **chưa** đi vào prompt của AGENT ở bất cứ đâu, nên mấy test dưới đây cố ý
không khẳng định gì về việc đề ra sát sách hơn — chúng canh những chỗ mà đường tải lên có thể
nói dối: nhận nhầm thứ không phải tài liệu, khai sai kích thước, để tài liệu người này lọt
sang người khác, nói rằng đã cất một tệp mà byte thì không ở đâu cả, và — từ 08/10/2026 —
khai một trạng thái mà vòng xử lý chưa hề nói ra.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import storage as storage_module
from be import teacher_documents
from be.config import get_settings
from be.db import bind_sessions, prepare_schema
from be.models import Document, Teacher
from be.seed import seed_if_empty
from be.storage import MemoryObjectStore, StorageUnavailable, bind_store, get_store
from be.teacher_documents import router as document_router
from contracts import PROBE_DOCUMENT_TASK, DocumentState

TEACHER = {"X-Actor": "teacher:GV-001"}
OTHER = {"X-Actor": "teacher:GV-002"}


class _Job:
    """Thứ arq trả về từ `enqueue_job`. Chỉ `job_id` được đọc tới."""

    job_id = "job-gia"


class _Queue:
    """Một pool arq ghi lại thay vì gửi đi.

    Có mặt vì nếu không thì app của fixture **không có** pool nào, và khi ấy mọi lần tải lên đi
    vào nhánh *chưa giao được việc* — mọi test sẽ chạy trên một trạng thái sai mà không test nào
    đỏ. Đường thường phải là đường mặc định của fixture; ca queue chết có test riêng.
    """

    def __init__(self) -> None:
        self.jobs: list[tuple[str, dict, str]] = []
        self.refuse = False

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str = "") -> object:
        """Ghi lại một job, hoặc chết nếu test đã bảo nó chết.

        Args:
            name: Tên task.
            payload: Payload đã serialise.
            _queue_name: Queue đích.

        Returns:
            Một job giả.

        Raises:
            OSError: Khi `refuse` bật — đúng hình dạng mà `create_queue_pool` dịch sang.
        """
        if self.refuse:
            raise OSError("redis is gone")
        self.jobs.append((name, payload, _queue_name))
        return _Job()


@pytest_asyncio.fixture
async def stack():
    """Một app có hai giáo viên, để "không phải của tôi" là một ca thật sự tồn tại.

    Yields:
        Client HTTP, session maker, và queue giả — ba thứ mà một test có thể cần soi.
    """
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)
    bind_store(MemoryObjectStore())
    queue = _Queue()

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        session.add(Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002"))
        await session.commit()

    app = FastAPI()
    app.include_router(document_router)
    app.state.queue_pool = queue

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker, queue

    await engine.dispose()
    db_module._SESSION_MAKER = None
    storage_module._STORE = None


def _file(name: str = "SGK Giải tích 12.pdf", body: bytes = b"%PDF-1.7 ba trang gia vo"):
    """Một file tải lên, đúng hình dạng multipart mà trình duyệt gửi."""
    return {"file": (name, body, "application/pdf")}


@pytest.mark.asyncio
async def test_an_uploaded_document_comes_back_in_the_library(stack) -> None:
    """Tải lên rồi liệt kê thì thấy đúng nó, với đúng tên giáo viên đã đặt."""
    client, _, _ = stack
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
    client, maker, _ = stack
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
        assert row.storage_key
        key = row.storage_key

    # So **nội dung**, không so độ dài. Bản trước chỉ so `len`, và một phép so độ dài không
    # phân biệt được một object đúng với một object đã bị `seek(0)` bỏ quên làm cụt đầu rồi
    # đệm lại cho đủ. Hai lỗi duy nhất mà đường stream này sinh ra được -- cụt đầu vì quên
    # `seek`, cụt đuôi vì `length` sai -- đều lọt qua phép so cũ.
    assert await get_store().read(key) == body


@pytest.mark.asyncio
async def test_a_document_belongs_to_the_teacher_who_uploaded_it(stack) -> None:
    """Thư viện tìm qua `teacher_id`, nên không id nào với tới tài liệu người khác (ADR-22)."""
    client, _, _ = stack
    await client.post("/api/teacher/documents", headers=TEACHER, files=_file())

    mine = await client.get("/api/teacher/documents", headers=TEACHER)
    theirs = await client.get("/api/teacher/documents", headers=OTHER)
    assert len(mine.json()) == 1
    assert theirs.json() == []


@pytest.mark.asyncio
async def test_the_newest_document_is_first(stack) -> None:
    """Rail dựng để tìm thứ **vừa** tải lên, nên thứ tự là mới nhất trước."""
    client, maker, _ = stack
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
    ["ảnh.png", "bảng điểm.xlsx", "khong-co-duoi", "đề cương.docx", "đề cương.doc"],
)
async def test_what_is_not_a_document_is_refused(stack, name: str) -> None:
    """Lọc theo **đuôi tên**, thứ giáo viên nhìn thấy, chứ không theo content-type client khai.

    `.doc` và `.docx` nằm trong danh sách này từ 08/10/2026. PyMuPDF không đọc được cả hai,
    nên nhận chúng là hứa một thứ bước xử lý chắc chắn phải từ chối -- và lúc ấy giáo viên
    đang nghe từ chối cho một việc họ tưởng đã xong.
    """
    client, _, _ = stack
    sent = await client.post("/api/teacher/documents", headers=TEACHER, files=_file(name=name))
    assert sent.status_code == 400
    assert "PDF" in sent.json()["detail"]


@pytest.mark.asyncio
async def test_an_empty_file_is_refused(stack) -> None:
    """Một file rỗng là một lần chọn nhầm, không phải một tài liệu."""
    client, _, _ = stack
    sent = await client.post("/api/teacher/documents", headers=TEACHER, files=_file(body=b""))
    assert sent.status_code == 400


@pytest.mark.asyncio
async def test_a_file_over_the_cap_is_refused_and_says_the_cap(stack, monkeypatch) -> None:
    """Quá lớn thì 413, và câu từ chối nói ra **mức** — nếu không thì không ai sửa được gì.

    Trần thật là 100 MB, và test này **không** dựng 100 MB: cộng cả bản encode multipart của
    httpx thì đó là vài trăm MB RAM cho một phép khẳng định về một câu chữ. Hạ trần xuống
    1 MB rồi gửi 1,1 MB chứng minh đúng cùng một thứ, **và** vẫn đi qua đúng nhánh mà
    production chạy: ngưỡng spool của Starlette cũng là 1 MB, nên phần thân đã tràn ra đĩa.
    """
    client, _, _ = stack
    monkeypatch.setattr(teacher_documents, "_MAX_BYTES", 1024 * 1024)

    sent = await client.post(
        "/api/teacher/documents",
        headers=TEACHER,
        files=_file(body=b"%PDF-1.7 " + b"z" * (1024 * 1024 + 100)),
    )
    assert sent.status_code == 413
    assert "1 MB" in sent.json()["detail"]


@pytest.mark.asyncio
async def test_nothing_claims_a_page_count_before_anyone_counted(stack) -> None:
    """Bản đọc chỉ claim thứ đã đo, và **ngay sau khi tải lên thì chưa đo được gì**.

    Bản trước của test này tên `test_nothing_claims_a_page_count` và khẳng định đúng năm khoá:
    vòng ấy không mở file ra đọc, nên một con số trang chỉ có thể là chữ bịa. Luật đổi hình ngày
    08/10/2026 — nay có người đếm thật — nên nó đổi từ *không claim gì* sang *chỉ claim thứ đã
    đo*. Phần không đổi, và là phần quan trọng: `page_count` phải là `None` cho tới khi
    `services/document` trả lời.

    Tám khoá, không bảy: `fault` ở trong đó, vì ADR-27 đòi *lý do nói bằng lời giáo viên hiểu* —
    và hai lý do khác nhau cùng dẫn tới *không đọc được chữ*, một bản scan và một PDF không có
    trang nào. Riêng trạng thái không phân biệt được hai câu ấy.
    """
    client, _, _ = stack
    sent = await client.post("/api/teacher/documents", headers=TEACHER, files=_file())
    body = sent.json()
    assert set(body) == {
        "document_id",
        "filename",
        "kind",
        "byte_size",
        "state",
        "page_count",
        "fault",
        "uploaded_at",
    }
    assert body["page_count"] is None
    assert body["state"] == DocumentState.PROCESSING


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "body", "status"),
    [("ảnh.png", b"%PDF-1.7 that ra la png", 400), ("to.pdf", b"", 400)],
)
async def test_a_refused_file_never_reaches_storage(
    stack, name: str, body: bytes, status: int
) -> None:
    """Mọi lớp kiểm chạy **trước khi** chạm object storage.

    Đây là test duy nhất khẳng định được thứ tự ấy. Chuyển `put` lên trước lớp kiểm thì mọi
    test khác vẫn xanh -- file vẫn bị từ chối, mã vẫn đúng -- chỉ có bucket là âm thầm đầy
    rác mà không ai nhìn.
    """
    client, _, _ = stack

    sent = await client.post(
        "/api/teacher/documents", headers=TEACHER, files=_file(name=name, body=body)
    )

    assert sent.status_code == status
    assert get_store().objects == {}


@pytest.mark.asyncio
async def test_storage_down_fails_loudly_and_leaves_no_row(stack) -> None:
    """Không cất được byte thì **không** được có hàng nào.

    503 chứ không 500: đây là hạ tầng chưa sẵn sàng, không phải một lỗi lập trình, và giáo
    viên cần biết là thử lại được. Và nếu hàng vẫn được ghi thì chip sẽ hiện trên rail trỏ
    vào hư không -- đúng hình dạng hỏng mà thứ tự "object trước, hàng sau" sinh ra để tránh.
    """
    client, maker, _ = stack

    class Broken(MemoryObjectStore):
        async def put(self, key, data, length, content_type):
            raise StorageUnavailable("bucket di vang")

    bind_store(Broken())

    sent = await client.post("/api/teacher/documents", headers=TEACHER, files=_file())

    assert sent.status_code == 503
    async with maker() as session:
        assert await session.scalar(select(Document)) is None


@pytest.mark.asyncio
async def test_the_key_never_carries_the_teacher_of_someone_else(stack) -> None:
    """Khoá mang id của chính chủ, nên một lần xoá theo prefix không bao giờ cắt nhầm người."""
    client, maker, _ = stack

    await client.post("/api/teacher/documents", headers=TEACHER, files=_file())

    async with maker() as session:
        row = await session.scalar(select(Document))
        assert row is not None
        assert row.storage_key.startswith(f"documents/{row.teacher_id}/")
        assert row.storage_key.endswith(".pdf")


def test_the_cap_is_a_hundred_megabytes() -> None:
    """Trần là 100 MB, và con số ấy phải có một lưới của riêng nó.

    Một test khẳng định một hằng số thường là một test vô dụng. Cái này không, và lý do đáng
    ghi lại: test trần ở trên `monkeypatch` `_MAX_BYTES` xuống 1 MB để khỏi dựng vài trăm MB
    trong RAM — mà làm vậy thì **giá trị thật không còn lưới nào chạm tới**. Một phép đột
    biến đổi 100 thành 10 chạy qua toàn bộ suite mà không một test nào đỏ.

    Nó là một quyết định nghiệp vụ: 10 MB loại phần lớn SGK scan, 100 MB thì không. Hạ nó
    xuống trong im lặng là thu hẹp thư viện của giáo viên mà không ai thấy.
    """
    assert teacher_documents._MAX_BYTES == 100 * 1024 * 1024


@pytest.mark.asyncio
async def test_a_stored_document_is_handed_to_the_document_service(stack) -> None:
    """Cất xong thì phải **giao việc đọc**, và giao đúng queue với đúng khoá.

    Không có job này thì tài liệu đứng ở *đang xử lý* mãi mãi dù mọi thứ khác đều chạy đúng, và
    không màn hình nào nói ra điều đó cho tới khi phép suy *đứng quá lâu* hết giờ.

    Payload chở `storage_key` chứ không chở byte: trần một tệp là 100 MB, và Redis không phải
    chỗ chuyên chở một cuốn sách.
    """
    client, _, queue = stack

    sent = await client.post("/api/teacher/documents", headers=TEACHER, files=_file())

    assert len(queue.jobs) == 1
    name, payload, where = queue.jobs[0]
    assert name == PROBE_DOCUMENT_TASK
    assert where == get_settings().document_queue_name
    assert payload["document_id"] == sent.json()["document_id"]
    assert payload["storage_key"].endswith(".pdf")
    assert "content" not in payload


@pytest.mark.asyncio
async def test_a_refused_file_is_never_handed_to_anyone(stack) -> None:
    """Một tệp bị từ chối không sinh ra job nào.

    Cùng một luật với "không chạm object storage": mọi lớp kiểm phải xong trước khi có việc gì
    rời khỏi request này.
    """
    client, _, queue = stack
    await client.post("/api/teacher/documents", headers=TEACHER, files=_file(name="anh.png"))
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_a_dead_queue_leaves_the_row_saying_so_not_saying_processing(stack) -> None:
    """Queue chết thì hàng nói **xử lý hỏng** ngay, không nói *đang xử lý*.

    Đây là ca duy nhất mà `processing` là một lời nói dối không bao giờ được sửa: không có job
    nào để mà về muộn. ADR-27 gọi đúng hình dạng ấy — *"một chip đứng mãi ở đang xử lý vì job đã
    chết cũng là một chip nói dối"*.

    Và tệp **vẫn ở lại**: nó đã cất xong, một lần thử lại về sau cần nó, nên 201 chứ không 503.
    """
    client, maker, queue = stack
    queue.refuse = True

    sent = await client.post("/api/teacher/documents", headers=TEACHER, files=_file())

    assert sent.status_code == 201
    assert sent.json()["state"] == DocumentState.FAILED
    assert sent.json()["fault"] != ""

    async with maker() as session:
        row = await session.scalar(select(Document))
        assert row is not None
        assert row.state == DocumentState.FAILED
        assert await get_store().read(row.storage_key) != b""


@pytest.mark.asyncio
async def test_a_document_stuck_in_processing_reads_as_failed_without_being_written(stack) -> None:
    """Trạng thái thứ tư sinh ra **lúc đọc**, và nó không ghi gì cả.

    Một process bị giết thì không còn ai sống để ghi *xử lý hỏng*, nên nó phải là một phép so.
    Nửa sau của phép khẳng định là nửa quan trọng: cột vẫn giữ `processing`. Đó không phải nói
    dối — cột ghi *đã nghe được gì*, đường đọc trả lời *nên tin gì* — và nó là thứ cho một job
    về muộn vẫn thắng.
    """
    client, maker, _ = stack
    await client.post("/api/teacher/documents", headers=TEACHER, files=_file())

    async with maker() as session:
        row = await session.scalar(select(Document))
        assert row is not None
        row.uploaded_at = datetime.now(UTC) - timedelta(
            seconds=get_settings().document_stale_after_seconds + 60
        )
        await session.commit()

    listed = await client.get("/api/teacher/documents", headers=TEACHER)
    assert listed.json()[0]["state"] == DocumentState.FAILED

    async with maker() as session:
        row = await session.scalar(select(Document))
        assert row is not None
        assert row.state == DocumentState.PROCESSING


@pytest.mark.asyncio
async def test_a_document_still_being_read_is_not_called_failed(stack) -> None:
    """Và chiều ngược lại: vừa tải lên thì **chưa** quá hạn.

    Cặp với test trên. Thiếu cái này thì một phép suy luôn trả `failed` vẫn xanh, và mọi tài
    liệu trên rail sẽ mang nhãn hỏng ngay giây đầu.
    """
    client, _, _ = stack
    await client.post("/api/teacher/documents", headers=TEACHER, files=_file())

    listed = await client.get("/api/teacher/documents", headers=TEACHER)
    assert listed.json()[0]["state"] == DocumentState.PROCESSING
