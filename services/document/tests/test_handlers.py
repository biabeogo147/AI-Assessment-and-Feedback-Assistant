"""Một job đọc tệp, và hai cách nó có thể hỏng.

Hai cách ấy được xử khác nhau có chủ ý, và đó là thứ mấy test dưới canh: không đọc nổi tệp là
một **kết quả** gửi về cho BE, còn không giao nổi kết quả thì **ném** để arq thử lại.

Từ plan 3b còn một điều thứ ba: tệp có chữ để lại bản thô trong kho nội dung **trước** khi
`READY` đi về BE. Kho và queue giả ghi chung một nhật ký, nên thứ tự ấy kiểm được.
"""

import pymupdf
import pytest
from arq.worker import Retry
from redis.exceptions import ConnectionError as RedisConnectionError

from contracts import (
    DOCUMENT_PROBED_TASK,
    DocumentProbeRequested,
    DocumentState,
    RawDocument,
    RawPage,
    RawSource,
)
from document.config import get_settings
from document.content_store import ContentStoreUnavailable
from document.handlers import probe_document
from document.pdf import PdfUnreadable
from document.storage import StorageUnavailable


class _Store:
    """Một kho nội dung ghi lại thay vì ghi Mongo, hoặc chết nếu được bảo vậy."""

    def __init__(self, log: list[str], broken: bool = False) -> None:
        self.header: RawDocument | None = None
        self.pages: list[RawPage] = []
        self.finished = False
        self._log = log
        self._broken = broken

    async def begin(self, header: RawDocument) -> None:
        """Mở bản thô, hoặc chết như một Mongo không với tới được.

        Args:
            header: Đầu mục.

        Raises:
            ContentStoreUnavailable: Khi kho được dựng với `broken=True`.
        """
        if self._broken:
            raise ContentStoreUnavailable("mongo is down")
        self.header = header
        self._log.append("begin")
        self.pages = []

    async def put_page(self, page: RawPage) -> None:
        """Ghi một trang.

        Args:
            page: Trang.
        """
        self.pages.append(page)
        self._log.append(f"page {page.page}")

    async def finish(self, document_id: str, at: object) -> None:
        """Đánh dấu xong.

        Args:
            document_id: Id tài liệu.
            at: Lúc xong.
        """
        self.finished = True
        self._log.append("finish")


class _Reader:
    """Một object storage trả về byte đã dọn trước, hoặc chết nếu được bảo vậy."""

    def __init__(self, raw: bytes | None) -> None:
        self._raw = raw

    async def read(self, key: str) -> bytes:
        """Trả byte, hoặc ném đúng hình dạng mà `storage.py` ném.

        Args:
            key: Khoá. Không dùng.

        Returns:
            Byte đã dọn trước.

        Raises:
            StorageUnavailable: Khi reader được dựng với `None`.
        """
        if self._raw is None:
            raise StorageUnavailable(f"Could not read {key}")
        return self._raw


class _Queue:
    """Một pool arq ghi lại thay vì gửi đi."""

    def __init__(
        self, refuse: bool = False, log: list[str] | None = None, down: bool = False
    ) -> None:
        self.jobs: list[tuple[str, dict, str]] = []
        self._refuse = refuse
        self._down = down
        self._log = log if log is not None else []

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str = "") -> object | None:
        """Ghi lại một job, hoặc từ chối nó.

        Args:
            name: Tên task.
            payload: Payload đã serialise.
            _queue_name: Queue đích.

        Returns:
            Một object giả, hoặc `None` khi từ chối — đúng cách arq diễn đạt một job trùng id.

        Raises:
            ConnectionError: Khi pool được dựng với `down=True` -- lỗi của `redis` khi Redis tắt.
        """
        if self._down:
            raise RedisConnectionError("redis is down")
        if self._refuse:
            return None
        self.jobs.append((name, payload, _queue_name))
        self._log.append(f"hand back {payload['state']}")
        return object()


def _a_pdf_with_text() -> bytes:
    """Một PDF một trang, đủ chữ để qua cổng.

    Returns:
        Byte của tệp.
    """
    with pymupdf.open() as book:
        page = book.new_page()
        page.insert_text(
            (72, 72),
            "Chương 1. Mệnh đề và tập hợp. Học sinh nhận biết được mệnh đề chứa biến và "
            "xác định được tính đúng sai của nó.",
            fontsize=11,
        )
        return book.tobytes()


def _a_scanned_pdf() -> bytes:
    """Một PDF hai trang không có chữ nào, như một bản scan.

    Returns:
        Byte của tệp.
    """
    with pymupdf.open() as book:
        book.new_page()
        book.new_page()
        return book.tobytes()


def _asked(filename: str = "sach.pdf") -> dict:
    """Payload của một job, đã serialise.

    Args:
        filename: Tên tệp giáo viên tải lên.

    Returns:
        Dict đúng hình dạng arq chở.
    """
    return DocumentProbeRequested(
        document_id="doc-1", storage_key="documents/gv/doc-1", filename=filename
    ).model_dump(mode="json")


@pytest.mark.asyncio
async def test_a_readable_file_is_handed_back_to_the_be_queue() -> None:
    """Đường thường: đọc xong thì kết quả đi về **queue của BE**, không về result store.

    Queue đích là nửa dễ sai nhất và nó không ném gì cả khi sai: job rơi vào một chỗ không ai
    nghe, và hệ thống trông y hệt một hệ thống đang rảnh.
    """
    queue = _Queue()
    ctx = {"reader": _Reader(_a_pdf_with_text()), "redis": queue, "store": _Store([])}
    out = await probe_document(ctx, _asked())

    assert len(queue.jobs) == 1
    name, payload, where = queue.jobs[0]
    assert name == DOCUMENT_PROBED_TASK
    assert where == get_settings().ingest_queue_name
    assert payload["state"] == DocumentState.READY
    assert payload["page_count"] == 1
    assert out["document_id"] == "doc-1"


@pytest.mark.asyncio
async def test_a_file_that_cannot_be_read_still_gets_an_answer() -> None:
    """Object storage chết vẫn phải sinh ra một câu trả lời.

    Ném ra ngoài thay vì gửi đi là để chip đứng mãi ở *đang xử lý* — đúng thứ ADR-27 gọi là một
    chip nói dối. Và trạng thái là `FAILED`, không `NO_TEXT_LAYER`: tệp có thể vẫn tốt, nên thử
    lại là việc có nghĩa, còn gọi nó *không đọc được chữ* là một phán quyết sai về cuốn sách của
    giáo viên.
    """
    queue = _Queue()
    store = _Store([])
    await probe_document({"reader": _Reader(None), "redis": queue, "store": store}, _asked())

    _, payload, _ = queue.jobs[0]
    assert payload["state"] == DocumentState.FAILED
    assert payload["page_count"] is None
    assert payload["fault"] != ""
    assert store.header is None


@pytest.mark.asyncio
@pytest.mark.parametrize("queue", [_Queue(refuse=True), _Queue(down=True)], ids=["refused", "down"])
async def test_a_result_that_cannot_be_handed_back_asks_arq_to_retry(queue: _Queue) -> None:
    """Không giao nổi kết quả thì xin arq **chạy lại** -- bằng `Retry`, không bằng một lỗi bất kỳ.

    arq chỉ chạy lại khi gặp `Retry`; mọi exception khác đánh job hỏng ngay (review Task 2, plan
    3b). Chạy lại an toàn: bản thô đã ghi được ghi đè chứ không chồng lên. Hết lượt thử thì phép
    suy *đứng quá lâu* của BE là lưới cuối.
    """
    ctx = {"reader": _Reader(_a_pdf_with_text()), "redis": queue, "store": _Store([])}
    with pytest.raises(Retry):
        await probe_document(ctx, _asked())


@pytest.mark.asyncio
async def test_a_pdf_with_text_is_kept_page_by_page_before_ready_leaves() -> None:
    """Bản thô nằm trong kho **trước** khi `READY` đi về BE -- *"chunk trước, `state` sau"*.

    Đảo thứ tự thì có một khoảnh khắc chip báo *sẵn sàng* mà plan 3c đọc kho không thấy chữ nào,
    và nếu job chết đúng lúc ấy thì khoảnh khắc ấy kéo dài mãi.
    """
    log: list[str] = []
    store = _Store(log)
    ctx = {"reader": _Reader(_a_pdf_with_text()), "redis": _Queue(log=log), "store": store}
    await probe_document(ctx, _asked())

    assert log == ["begin", "page 1", "finish", "hand back ready"]
    assert store.header is not None
    assert store.header.source is RawSource.TEXT_LAYER
    assert store.header.page_count == 1
    assert store.header.reader is None
    assert store.header.pipeline is None
    [page] = store.pages
    assert page.document_id == "doc-1"
    assert page.source is RawSource.TEXT_LAYER
    # Font mặc định của `pymupdf` không có dấu tiếng Việt, nên chỉ phần không dấu đi về nguyên vẹn.
    assert page.text.startswith("Ch") and "1. M" in page.text
    assert page.blocks and page.blocks[0].box is not None


@pytest.mark.asyncio
async def test_a_plain_text_file_is_kept_as_one_page() -> None:
    """Tệp `.md` không có trang, nhưng bên đọc ở plan 3c đọc một hình dạng: một trang, một khối."""
    store = _Store([])
    raw = "# Chương 1\n\nMệnh đề và tập hợp.\n".encode()
    await probe_document(
        {"reader": _Reader(raw), "redis": _Queue(), "store": store}, _asked("bai.md")
    )

    assert store.header is not None
    assert store.header.source is RawSource.PLAIN
    assert store.header.page_count is None
    [page] = store.pages
    assert page.text == "# Chương 1\n\nMệnh đề và tập hợp."
    assert page.blocks[0].box is None
    assert page.width is None


@pytest.mark.asyncio
async def test_a_scanned_pdf_leaves_nothing_in_the_store_yet() -> None:
    """Một PDF scan không có chữ để dựng bản thô ở bước này: bản thô của nó đi đường OCR (Task 3).

    Ghi một bản thô rỗng ở đây là để plan 3c thấy một tài liệu *đã đọc xong, không chữ* trong
    khi nó chưa được đọc.
    """
    queue = _Queue()
    store = _Store([])
    await probe_document(
        {"reader": _Reader(_a_scanned_pdf()), "redis": queue, "store": store}, _asked()
    )

    assert store.header is None
    assert queue.jobs[0][1]["state"] == DocumentState.NO_TEXT_LAYER


@pytest.mark.asyncio
async def test_a_store_that_cannot_be_written_asks_for_a_retry_and_ready_never_leaves() -> None:
    """Kho chết thì xin arq chạy lại, chờ lâu dần, và không có `READY` nào đi về BE trước đó.

    Gửi `READY` rồi mới ghi là đúng cái chip nói dối theo chiều ngược: *sẵn sàng* mà không có chữ.
    """
    queue = _Queue()
    waits = []
    for attempt in (1, 3):
        ctx = {
            "reader": _Reader(_a_pdf_with_text()),
            "redis": queue,
            "store": _Store([], broken=True),
            "job_try": attempt,
        }
        with pytest.raises(Retry) as asked_again:
            await probe_document(ctx, _asked())
        waits.append(asked_again.value.defer_score)
    assert queue.jobs == []
    assert 0 < waits[0] < waits[1]


@pytest.mark.asyncio
async def test_a_pdf_that_breaks_on_the_second_read_fails_and_leaves_the_store_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`probe` mở được tệp nhưng lần đọc thứ hai (`raw_pages`) hỏng: một tệp xấu, không phải một
    lỗi của hệ thống -- nên ra `FAILED` nói được với giáo viên, và kho không có đầu mục nào.
    """

    def _broken(*_: object) -> list[RawPage]:
        raise PdfUnreadable("Could not read the text of page 0")

    monkeypatch.setattr("document.handlers.raw_pages", _broken)
    queue = _Queue()
    store = _Store([])
    await probe_document(
        {"reader": _Reader(_a_pdf_with_text()), "redis": queue, "store": store}, _asked()
    )

    assert queue.jobs[0][1]["state"] == DocumentState.FAILED
    assert queue.jobs[0][1]["fault"] != ""
    assert store.header is None
