"""Một job đọc tệp, và hai cách nó có thể hỏng.

Hai cách ấy được xử khác nhau có chủ ý, và đó là thứ mấy test dưới canh: không đọc nổi tệp là
một **kết quả** gửi về cho BE, còn không giao nổi kết quả thì **ném** để arq thử lại.

Từ plan 3b còn một điều thứ ba: tệp có chữ để lại bản thô trong kho nội dung **trước** khi
`READY` đi về BE. Kho và queue giả ghi chung một nhật ký, nên thứ tự ấy kiểm được.

Và một điều thứ tư (Task 3): PDF scan không về BE ngay mà đi đường OCR theo lô, mỗi lô tự giao lô
kế, lô cuối mới gửi kết quả. Model OCR thật không nạp ở đây -- `_Ocr` đứng thay nó.
"""

from types import SimpleNamespace

import pymupdf
import pytest
from arq.worker import Retry
from redis.exceptions import ConnectionError as RedisConnectionError

from contracts import (
    DOCUMENT_PROBED_TASK,
    DOCUMENT_PROGRESS_TASK,
    INDEX_DOCUMENT_TASK,
    OCR_PAGES_TASK,
    DocumentPagesRequested,
    DocumentProbeRequested,
    DocumentState,
    RawDocument,
    RawPage,
    RawSource,
)
from document.config import get_settings
from document.content_store import ContentStoreUnavailable
from document.ocr_handlers import MAX_TRIES, ocr_pages, probe_document
from document.pdf import PdfUnreadable
from document.probe import Finding
from document.storage import StorageUnavailable


class _Store:
    """Một kho nội dung ghi lại thay vì ghi Mongo, hoặc chết nếu được bảo vậy."""

    def __init__(
        self,
        log: list[str],
        broken: bool = False,
        broken_pages: bool = False,
        broken_finish: bool = False,
    ) -> None:
        self.header: RawDocument | None = None
        self.pages: list[RawPage] = []
        self.finished = False
        self._log = log
        self._broken = broken
        self._broken_pages = broken_pages
        self._broken_finish = broken_finish

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
        """Ghi một trang, hoặc chết nếu được dựng với `broken_pages=True`.

        Args:
            page: Trang.

        Raises:
            ContentStoreUnavailable: Khi kho được dựng với `broken_pages=True`.
        """
        if self._broken_pages:
            raise ContentStoreUnavailable("mongo is down")
        self.pages.append(page)
        self._log.append(f"page {page.page}")

    async def put_pages(self, pages: list[RawPage]) -> None:
        """Ghi nhiều trang một lượt, cùng nhật ký với `put_page`.

        Args:
            pages: Các trang.

        Raises:
            ContentStoreUnavailable: Khi kho được dựng với `broken_pages=True`.
        """
        if self._broken_pages:
            raise ContentStoreUnavailable("mongo is down")
        self._log.append(f"pages {len(pages)}")
        self.pages.extend(pages)

    async def finish(self, document_id: str, at: object) -> None:
        """Đánh dấu xong, hoặc chết nếu được dựng với `broken_finish=True`.

        Args:
            document_id: Id tài liệu.
            at: Lúc xong.

        Raises:
            ContentStoreUnavailable: Khi kho được dựng với `broken_finish=True`.
        """
        if self._broken_finish:
            raise ContentStoreUnavailable("mongo is down")
        self.finished = True
        self._log.append("finish")

    async def characters(self, document_id: str) -> int:
        """Tổng ký tự của mọi trang đã ghi.

        Args:
            document_id: Id tài liệu.

        Returns:
            Tổng số ký tự.
        """
        return sum(len(page.text) for page in self.pages)


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
        self.ids: set[str] = set()
        self._refuse = refuse
        self._down = down
        self._log = log if log is not None else []

    async def enqueue_job(
        self, name: str, payload: dict, _queue_name: str = "", _job_id: str | None = None
    ) -> object | None:
        """Ghi lại một job, hoặc từ chối nó.

        Args:
            name: Tên task.
            payload: Payload đã serialise.
            _queue_name: Queue đích.
            _job_id: Id cố định. Một id đã thấy bị từ chối, như arq làm khi job còn nằm đó.

        Returns:
            Một object giả, hoặc `None` khi từ chối — đúng cách arq diễn đạt một job trùng id.

        Raises:
            ConnectionError: Khi pool được dựng với `down=True` -- lỗi của `redis` khi Redis tắt.
        """
        if self._down:
            raise RedisConnectionError("redis is down")
        if self._refuse or (_job_id is not None and _job_id in self.ids):
            return None
        if _job_id is not None:
            self.ids.add(_job_id)
        self.jobs.append((name, payload, _queue_name))
        if name == DOCUMENT_PROBED_TASK:
            self._log.append(f"hand back {payload['state']}")
        elif name == OCR_PAGES_TASK:
            self._log.append(f"queue batch {payload['first']}")
        elif name == INDEX_DOCUMENT_TASK:
            self._log.append("queue index")
        else:
            self._log.append(f"progress {payload['pages_read']}")
        return object()

    def sent(self, name: str) -> list[dict]:
        """Payload của mọi job mang tên này, theo thứ tự đẩy.

        Args:
            name: Tên task.

        Returns:
            Các payload.
        """
        return [payload for task, payload, _ in self.jobs if task == name]


class _Ocr:
    """Một `PageReader` không nạp model nào: mỗi trang ra một khối chữ, trừ khi được dặn khác.

    `read_page` đếm trang từ 0 như bản thật; nhật ký ghi số trang đếm từ 1 như kho.
    """

    def __init__(
        self,
        log: list[str] | None = None,
        blank: bool = False,
        broken_at: int | None = None,
        error: type[Exception] = PdfUnreadable,
    ) -> None:
        self._log = log if log is not None else []
        self._blank = blank
        self._broken_at = broken_at
        self._error = error

    def read_page(self, raw: bytes, index: int) -> SimpleNamespace:
        """Trả một trang đã "đọc", hoặc chết như PyMuPDF không dựng nổi trang ấy.

        Args:
            raw: Byte của tệp. Không dùng.
            index: Số trang, đếm từ 0.

        Returns:
            Một trang cùng hình dạng `PageRead`.

        Raises:
            Exception: Lỗi kiểu `error` ở trang `broken_at`, đếm từ 1.
        """
        if index + 1 == self._broken_at:
            raise self._error(f"Could not read page {index}")
        self._log.append(f"ocr {index + 1}")
        found = SimpleNamespace(kind="paragraph_title", box=(1, 2, 3, 4), text=f"Trang {index + 1}")
        return SimpleNamespace(
            page=index + 1,
            width=800,
            height=1100,
            blocks=() if self._blank else (found,),
            seconds={"render": 0.1},
        )


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
async def test_a_readable_file_goes_to_the_index_queue_not_back_to_the_be() -> None:
    """Đọc xong một tệp có chữ thì tài liệu **chưa** sẵn sàng: nó còn chờ cây (plan 3c, D3).

    Queue đích là nửa dễ sai nhất và nó không ném gì cả khi sai: job rơi vào một chỗ không ai
    nghe, và hệ thống trông y hệt một hệ thống đang rảnh. Không gì về BE lúc này.
    """
    queue = _Queue()
    ctx = {"reader": _Reader(_a_pdf_with_text()), "redis": queue, "store": _Store([])}
    out = await probe_document(ctx, _asked())

    # [CODE CHẾT 2026-10-11] READY chờ cây — plan 3c, D3
    # assert len(queue.jobs) == 1
    # name, payload, where = queue.jobs[0]
    # assert name == DOCUMENT_PROBED_TASK
    # assert where == get_settings().ingest_queue_name
    # assert payload["state"] == DocumentState.READY
    # assert payload["page_count"] == 1
    assert len(queue.jobs) == 1
    name, payload, where = queue.jobs[0]
    assert name == INDEX_DOCUMENT_TASK
    assert where == get_settings().document_index_queue_name
    assert (payload["document_id"], payload["storage_key"]) == ("doc-1", "documents/gv/doc-1")
    assert payload["page_count"] == 1
    assert queue.sent(DOCUMENT_PROBED_TASK) == []
    assert out["document_id"] == "doc-1"


@pytest.mark.asyncio
async def test_a_retried_probe_does_not_queue_the_index_twice() -> None:
    """Id cố định: hai job dựng cùng một cây là trả tiền Jev hai lần cho một kết quả."""
    queue = _Queue()
    ctx = {"reader": _Reader(_a_pdf_with_text()), "redis": queue, "store": _Store([])}
    await probe_document(ctx, _asked())
    await probe_document(ctx, _asked())
    assert len(queue.sent(INDEX_DOCUMENT_TASK)) == 1


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

    Từ plan 3c chỉ phán quyết **không phải** `READY` còn đi thẳng về BE, nên ca này dùng một tệp
    không đọc được: với job dựng cây, *bị từ chối* nghĩa là *đã xếp hàng rồi*, không phải hỏng.
    """
    # [CODE CHẾT 2026-10-11] READY chờ cây — plan 3c, D3
    # ctx = {"reader": _Reader(_a_pdf_with_text()), "redis": queue, "store": _Store([])}
    ctx = {"reader": _Reader(None), "redis": queue, "store": _Store([])}
    with pytest.raises(Retry):
        await probe_document(ctx, _asked())


@pytest.mark.asyncio
async def test_a_pdf_with_text_is_kept_in_the_store_before_ready_leaves() -> None:
    """Bản thô nằm trong kho **trước** khi `READY` đi về BE -- *"chunk trước, `state` sau"*.

    Đảo thứ tự thì có một khoảnh khắc chip báo *sẵn sàng* mà plan 3c đọc kho không thấy chữ nào,
    và nếu job chết đúng lúc ấy thì khoảnh khắc ấy kéo dài mãi.
    """
    log: list[str] = []
    store = _Store(log)
    ctx = {"reader": _Reader(_a_pdf_with_text()), "redis": _Queue(log=log), "store": store}
    await probe_document(ctx, _asked())

    # [CODE CHẾT 2026-10-11] READY chờ cây — plan 3c, D3
    # assert log == ["begin", "page 1", "finish", "hand back ready"]
    assert log == ["begin", "pages 1", "finish", "queue index"]
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
async def test_a_scanned_pdf_goes_to_ocr_instead_of_back_to_the_be() -> None:
    """Một PDF scan không còn về BE với *không đọc được chữ*: nó mở đầu mục OCR, rồi giao lô đầu.

    Đầu mục đi **trước** lô đầu -- `begin` xoá trang cũ, nên mở nó sau là xoá trang vừa đọc. Và
    không gì về BE lúc này: tài liệu vẫn *đang xử lý*, đúng là thứ nó đang làm.
    """
    log: list[str] = []
    queue = _Queue(log=log)
    store = _Store(log)
    await probe_document(
        {"reader": _Reader(_a_scanned_pdf()), "redis": queue, "store": store}, _asked()
    )

    assert log == ["begin", "queue batch 1"]
    assert store.header is not None
    assert store.header.source is RawSource.OCR
    assert store.header.page_count == 2
    assert store.header.reader == get_settings().ocr_reader
    assert store.header.pipeline == "text2"
    [(name, payload, where)] = queue.jobs
    assert name == OCR_PAGES_TASK
    assert where == get_settings().document_queue_name
    assert payload["first"] == 1
    assert payload["page_count"] == 2
    assert payload["storage_key"] == "documents/gv/doc-1"


@pytest.mark.asyncio
async def test_a_scan_whose_first_batch_cannot_be_queued_asks_for_a_retry() -> None:
    """Redis tắt đúng lúc giao lô đầu: xin chạy lại, không thì chuỗi lô không bao giờ bắt đầu."""
    ctx = {"reader": _Reader(_a_scanned_pdf()), "redis": _Queue(down=True), "store": _Store([])}
    with pytest.raises(Retry):
        await probe_document(ctx, _asked())


@pytest.mark.asyncio
async def test_a_pdf_with_no_pages_is_still_a_verdict_not_an_ocr_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PDF không trang nào thì OCR không có gì để đọc: phán quyết về BE ngay, như trước.

    `probe` được thay bằng phán quyết của nó cho ca ấy, vì PyMuPDF không ghi ra nổi một PDF không
    trang nào để dựng tệp thật.
    """
    monkeypatch.setattr(
        "document.ocr_handlers.probe",
        lambda *_: Finding(DocumentState.NO_TEXT_LAYER, 0, "Tệp PDF này không có trang nào."),
    )
    queue = _Queue()
    store = _Store([])
    await probe_document({"reader": _Reader(b"%PDF"), "redis": queue, "store": store}, _asked())

    [(name, payload, _)] = queue.jobs
    assert name == DOCUMENT_PROBED_TASK
    assert payload["state"] == DocumentState.NO_TEXT_LAYER
    assert store.header is None


def _batch(first: int, page_count: int) -> dict:
    """Payload của một lô OCR, đã serialise.

    Args:
        first: Trang đầu, đếm từ 1.
        page_count: Tổng số trang.

    Returns:
        Dict đúng hình dạng arq chở.
    """
    return DocumentPagesRequested(
        document_id="doc-1",
        storage_key="documents/gv/doc-1",
        filename="sach.pdf",
        first=first,
        page_count=page_count,
    ).model_dump(mode="json")


def _ocr_ctx(log: list[str], queue: _Queue, store: _Store, ocr: "_Ocr | None" = None) -> dict:
    """Context của một lô OCR.

    Args:
        log: Nhật ký chung.
        queue: Pool arq giả.
        store: Kho giả.
        ocr: Bộ đọc giả, mặc định ghi vào `log`.

    Returns:
        Context đủ khoá `ocr_pages` cần.
    """
    return {
        "reader": _Reader(b"%PDF"),
        "redis": queue,
        "store": store,
        "ocr": ocr if ocr is not None else _Ocr(log),
    }


@pytest.mark.asyncio
async def test_a_middle_batch_reads_its_pages_reports_progress_then_queues_the_next() -> None:
    """Lô giữa: đọc đúng `ocr_pages_per_job` trang, ghi chúng, báo tiến độ, giao lô kế -- theo
    đúng thứ tự ấy, và **không** gửi kết quả nào về BE.

    Tiến độ đi trước lô kế: nó là thứ giữ tài liệu khỏi bị BE đọc ra *xử lý hỏng*, nên nó không
    chờ sau một việc có thể hỏng.
    """
    per_job = get_settings().ocr_pages_per_job
    log: list[str] = []
    queue = _Queue(log=log)
    store = _Store(log)

    await ocr_pages(_ocr_ctx(log, queue, store), _batch(1, per_job * 2 + 5))

    assert [line for line in log if line.startswith("ocr")] == [
        f"ocr {n}" for n in range(1, per_job + 1)
    ]
    assert [page.page for page in store.pages] == list(range(1, per_job + 1))
    assert log[-2:] == [f"progress {per_job}", f"queue batch {per_job + 1}"]
    assert queue.sent(DOCUMENT_PROBED_TASK) == []
    [progress] = queue.sent(DOCUMENT_PROGRESS_TASK)
    assert progress["page_count"] == per_job * 2 + 5
    where = {name: queue_name for name, _, queue_name in queue.jobs}
    assert where[OCR_PAGES_TASK] == get_settings().document_queue_name
    assert where[DOCUMENT_PROGRESS_TASK] == get_settings().ingest_queue_name
    assert not store.finished


@pytest.mark.asyncio
async def test_the_pages_of_a_batch_are_kept_as_ocr_pages() -> None:
    """Trang OCR vào kho với nhãn thật, hộp, số giây -- thứ plan 3c dựng cây từ đó."""
    store = _Store([])
    await ocr_pages(_ocr_ctx([], _Queue(), store), _batch(1, 2))

    first, second = store.pages
    assert (first.page, second.page) == (1, 2)
    assert first.source is RawSource.OCR
    assert first.blocks[0].kind == "paragraph_title"
    assert first.blocks[0].box == (1, 2, 3, 4)
    assert first.text == "Trang 1"
    assert first.seconds == {"render": 0.1}
    assert (first.width, first.height) == (800, 1100)


@pytest.mark.asyncio
async def test_the_last_batch_finishes_and_queues_the_index() -> None:
    """Lô cuối: đọc phần còn lại, đánh dấu xong, rồi **mới** giao job dựng cây kèm số trang."""
    per_job = get_settings().ocr_pages_per_job
    log: list[str] = []
    queue = _Queue(log=log)
    store = _Store(log)

    await ocr_pages(_ocr_ctx(log, queue, store), _batch(per_job + 1, per_job + 3))

    assert [page.page for page in store.pages] == [per_job + 1, per_job + 2, per_job + 3]
    # [CODE CHẾT 2026-10-11] READY chờ cây — plan 3c, D3
    # assert log[-2:] == ["finish", "hand back ready"]
    # [done] = queue.sent(DOCUMENT_PROBED_TASK)
    assert log[-2:] == ["finish", "queue index"]
    assert queue.sent(DOCUMENT_PROBED_TASK) == []
    [done] = queue.sent(INDEX_DOCUMENT_TASK)
    assert done["page_count"] == per_job + 3
    assert queue.sent(OCR_PAGES_TASK) == []
    assert queue.sent(DOCUMENT_PROGRESS_TASK) == []


@pytest.mark.asyncio
async def test_a_book_where_ocr_finds_no_text_is_a_verdict() -> None:
    """OCR đọc hết mà cả cuốn không ra chữ nào: giờ *không đọc được chữ* mới là phán quyết thật."""
    queue = _Queue()
    await ocr_pages(_ocr_ctx([], queue, _Store([]), _Ocr(blank=True)), _batch(1, 3))

    [done] = queue.sent(DOCUMENT_PROBED_TASK)
    assert done["state"] == DocumentState.NO_TEXT_LAYER
    assert done["page_count"] == 3
    assert done["fault"] != ""


@pytest.mark.asyncio
async def test_a_batch_run_again_does_not_start_a_second_chain() -> None:
    """arq chạy lại một lô đã giao lô kế: lần giao thứ hai bị từ chối, và đó **không** phải lỗi.

    Coi nó là lỗi thì lô xin chạy lại mãi; cho nó qua bằng một id mới thì hai chuỗi lô cùng đọc
    một cuốn sách, tranh CPU, và mỗi chuỗi lại đẻ thêm.
    """
    queue = _Queue()
    total = get_settings().ocr_pages_per_job + 1

    for _ in range(2):
        await ocr_pages(_ocr_ctx([], queue, _Store([])), _batch(1, total))

    assert len(queue.sent(OCR_PAGES_TASK)) == 1


@pytest.mark.asyncio
async def test_a_store_that_breaks_mid_batch_asks_for_a_retry() -> None:
    """Kho chết giữa lô thì xin arq chạy lại cả lô, và không tiến độ hay lô kế nào đi trước."""
    queue = _Queue()
    with pytest.raises(Retry):
        await ocr_pages(_ocr_ctx([], queue, _Store([], broken_pages=True)), _batch(1, 30))
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_a_page_that_cannot_be_rendered_fails_the_document_by_page_number() -> None:
    """Một trang hỏng giữa cuốn là một tệp xấu ở đúng trang ấy: `FAILED`, câu nói ra số trang."""
    queue = _Queue()
    await ocr_pages(_ocr_ctx([], queue, _Store([]), _Ocr(broken_at=3)), _batch(1, 30))

    [done] = queue.sent(DOCUMENT_PROBED_TASK)
    assert done["state"] == DocumentState.FAILED
    assert "trang 3 " in done["fault"]
    assert queue.sent(OCR_PAGES_TASK) == []


@pytest.mark.asyncio
async def test_an_ocr_error_of_any_kind_fails_the_document_instead_of_killing_the_chain() -> None:
    """Model OCR ném một lỗi thường (torch, paddle, PIL): vẫn phải thành `FAILED` về BE.

    Để nó thoát ra thì arq đánh job hỏng **không thử lại**, không gì về BE, và chip chờ 300 s mới
    ra *xử lý hỏng* -- review Task 3 của plan 3b.
    """
    queue = _Queue()
    ocr = _Ocr(broken_at=2, error=RuntimeError)
    await ocr_pages(_ocr_ctx([], queue, _Store([]), ocr), _batch(1, 30))

    [done] = queue.sent(DOCUMENT_PROBED_TASK)
    assert done["state"] == DocumentState.FAILED
    assert "trang 2 " in done["fault"]


@pytest.mark.asyncio
async def test_a_slow_batch_stops_at_its_budget_and_hands_the_rest_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hết ngân sách giờ thì lô dừng giữa chừng và lô kế bắt đầu **đúng** ở trang sau trang cuối
    đã ghi -- không bỏ trang, không đọc lại trang. arq không chạy lại một job chạm `job_timeout`,
    nên đây là thứ giữ một cuốn dày chữ khỏi chết im.
    """
    monkeypatch.setattr("document.ocr_handlers._BATCH_BUDGET_SECONDS", -1)
    queue = _Queue()
    store = _Store([])

    await ocr_pages(_ocr_ctx([], queue, store), _batch(5, 30))

    assert [page.page for page in store.pages] == [5]
    [progress] = queue.sent(DOCUMENT_PROGRESS_TASK)
    assert progress["pages_read"] == 5
    [following] = queue.sent(OCR_PAGES_TASK)
    assert following["first"] == 6


@pytest.mark.asyncio
async def test_a_storage_blip_mid_chain_asks_for_a_retry() -> None:
    """Tệp đã đọc được lúc dò, nên giữa chuỗi lô một lần hụt là MinIO chập chờn: thử lại, chứ
    không bắt giáo viên tải lại rồi chờ mười lăm phút nữa.
    """
    queue = _Queue()
    ctx = _ocr_ctx([], queue, _Store([]))
    ctx["reader"] = _Reader(None)

    with pytest.raises(Retry):
        await ocr_pages(ctx, _batch(11, 30))
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_a_file_still_gone_on_the_last_try_fails_the_document() -> None:
    """Lần thử cuối mà tệp vẫn không đọc được thì mới là phán quyết: `FAILED` về BE."""
    queue = _Queue()
    ctx = _ocr_ctx([], queue, _Store([]))
    ctx["reader"] = _Reader(None)
    ctx["job_try"] = MAX_TRIES

    await ocr_pages(ctx, _batch(11, 30))

    [done] = queue.sent(DOCUMENT_PROBED_TASK)
    assert done["state"] == DocumentState.FAILED


@pytest.mark.asyncio
async def test_a_middle_batch_that_cannot_reach_redis_asks_for_a_retry() -> None:
    """Redis tắt lúc báo tiến độ hay giao lô kế: xin chạy lại, không thì chuỗi lô dừng im."""
    store = _Store([])
    with pytest.raises(Retry):
        await ocr_pages(_ocr_ctx([], _Queue(down=True), store), _batch(1, 30))


@pytest.mark.asyncio
async def test_a_last_batch_that_cannot_finish_asks_for_a_retry_and_ready_never_leaves() -> None:
    """Kho chết lúc đánh dấu xong: xin chạy lại, và không có `READY` nào đi trước khi kho xong."""
    queue = _Queue()
    with pytest.raises(Retry):
        await ocr_pages(_ocr_ctx([], queue, _Store([], broken_finish=True)), _batch(1, 3))
    assert queue.sent(DOCUMENT_PROBED_TASK) == []


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

    monkeypatch.setattr("document.ocr_handlers.raw_pages", _broken)
    queue = _Queue()
    store = _Store([])
    await probe_document(
        {"reader": _Reader(_a_pdf_with_text()), "redis": queue, "store": store}, _asked()
    )

    assert queue.jobs[0][1]["state"] == DocumentState.FAILED
    assert queue.jobs[0][1]["fault"] != ""
    assert store.header is None
