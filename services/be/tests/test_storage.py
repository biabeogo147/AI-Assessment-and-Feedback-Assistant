"""Kho byte của tài liệu.

Mấy test dưới đây canh **bản in-memory** và mấy hàm thuần quanh nó. Bản MinIO thật
không có test ở đây: nó cần một container sống, và thứ duy nhất nó làm thêm so với bản
in-memory là dịch lời gọi SDK — phần ấy được chứng minh bằng một lượt thử tay, không
bằng một mock dựng lại chính SDK rồi khẳng định rằng mock chạy đúng.

Cái **đáng** canh ở đây là hợp đồng mà cả hai bản phải giữ giống nhau, vì
`teacher_documents` chỉ nói chuyện qua hợp đồng ấy.
"""

import io

import pytest

from be import storage as storage_module
from be.config import Settings
from be.storage import (
    MemoryObjectStore,
    StorageUnavailable,
    bind_store,
    content_type_for,
    create_store,
    document_key,
    get_store,
)


@pytest.fixture(autouse=True)
def unbind():
    """Mỗi test bắt đầu và kết thúc với một module chưa bind.

    Không có nó thì một test bind store rồi rò sang test sau, và ca "chưa bind thì ném"
    sẽ xanh hoặc đỏ tuỳ thứ tự chạy.
    """
    storage_module._STORE = None
    yield
    storage_module._STORE = None


@pytest.mark.asyncio
async def test_what_goes_in_comes_back_out() -> None:
    """Hợp đồng tối thiểu: ghi rồi đọc lại ra đúng chuỗi byte ấy."""
    store = MemoryObjectStore()
    body = b"%PDF-1.7 vai trang"

    await store.put("documents/t/d.pdf", io.BytesIO(body), len(body), "application/pdf")

    assert await store.read("documents/t/d.pdf") == body


@pytest.mark.asyncio
async def test_a_short_length_truncates_the_object() -> None:
    """Bản in-memory đọc **đúng** `length` byte, không `read()` hết.

    Đây là lý do nó làm vậy: một `length` sai hoặc một `seek(0)` bị quên trên đường
    upload sẽ cắt cụt object trên MinIO thật mà không ném lỗi nào. Nếu bản in-memory
    nuốt cả stream thì test đường upload sẽ xanh trong khi production cụt — tức là bản
    giả che mất đúng cái lỗi nó sinh ra để bắt.
    """
    store = MemoryObjectStore()
    body = b"mot hai ba bon"

    await store.put("k", io.BytesIO(body), 7, "text/plain")

    assert await store.read("k") == b"mot hai"


@pytest.mark.asyncio
async def test_reading_a_key_that_was_never_written_fails_the_same_way() -> None:
    """Hai bản phải hỏng giống nhau, nếu không test chạy trên bản giả không nói gì."""
    with pytest.raises(StorageUnavailable):
        await MemoryObjectStore().read("khong-co")


@pytest.mark.asyncio
async def test_removing_what_is_not_there_is_quiet() -> None:
    """Đường dọn rác gọi nó sau một INSERT hỏng; ném ở đó chỉ che mất lỗi thật."""
    await MemoryObjectStore().remove("khong-co")


@pytest.mark.asyncio
async def test_clear_empties_the_bucket() -> None:
    """`be.reset_db` dựa vào đúng hành vi này."""
    store = MemoryObjectStore()
    await store.put("a", io.BytesIO(b"x"), 1, "text/plain")
    await store.put("b", io.BytesIO(b"y"), 1, "text/plain")

    await store.clear()

    assert store.objects == {}


def test_a_route_without_a_bound_store_says_so() -> None:
    """Giống `get_session`: chạy ngoài lifespan đã cấu hình là một lỗi lập trình."""
    with pytest.raises(RuntimeError, match="bind_store"):
        get_store()


def test_binding_is_what_routes_read() -> None:
    """`bind_store` và `get_store` phải nói về cùng một đối tượng."""
    store = MemoryObjectStore()
    bind_store(store)
    assert get_store() is store


def test_the_key_carries_the_teacher_and_never_the_filename() -> None:
    """Tên file là chuỗi client khai, có Unicode và khoảng trắng; nó không vào khoá."""
    key = document_key("gv-1", "doc-9", "SGK Giải tích 12.pdf")

    assert key == "documents/gv-1/doc-9.pdf"
    assert "Giải" not in key
    assert " " not in key


def test_a_name_without_an_extension_still_makes_a_key() -> None:
    """Đuôi rỗng không được phép làm hỏng khoá — `_ALLOWED` chặn ca này trước, nhưng
    một khoá hợp lệ vẫn rẻ hơn một `None` đi lang thang."""
    assert document_key("gv-1", "doc-9", "khong-co-duoi") == "documents/gv-1/doc-9"


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("sach.pdf", "application/pdf"),
        ("SACH.PDF", "application/pdf"),
        ("ghi-chu.txt", "text/plain; charset=utf-8"),
        ("ghi-chu.md", "text/markdown; charset=utf-8"),
    ],
)
def test_the_content_type_comes_from_the_extension(filename: str, expected: str) -> None:
    """Không bao giờ từ `file.content_type`.

    Giá trị này đi vào metadata của object, nên nó là `Content-Type` MinIO **trả về**.
    Tin lời khai của client ở đây là chôn sẵn một stored-XSS cho ngày có endpoint tải về.
    """
    assert content_type_for(filename) == expected


def test_an_unknown_extension_gets_a_type_no_browser_will_render() -> None:
    """Ca này không tới được qua `_ALLOWED`, nhưng mặc định phải an toàn chứ không tiện."""
    assert content_type_for("la.exe") == "application/octet-stream"


def test_creating_the_real_store_touches_no_network() -> None:
    """Dựng được client **không** nghĩa là tới được kho.

    Câu ấy đáng một test vì nó là cái bẫy: `Minio(...)` không chạm mạng, nên nếu
    lifespan chỉ gọi `create_store` mà quên `ensure_ready` thì BE khởi động sạch sẽ
    trong khi MinIO tắt, và lỗi dời tới lần upload đầu tiên.
    """
    store = create_store(Settings(minio_endpoint="127.0.0.1:1", minio_bucket="aiafa-documents"))

    assert store is not None
