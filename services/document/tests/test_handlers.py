"""Một job đọc tệp, và hai cách nó có thể hỏng.

Hai cách ấy được xử khác nhau có chủ ý, và đó là thứ mấy test dưới canh: không đọc nổi tệp là
một **kết quả** gửi về cho BE, còn không giao nổi kết quả thì **ném** để arq thử lại.
"""

import pymupdf
import pytest

from contracts import DOCUMENT_PROBED_TASK, DocumentProbeRequested, DocumentState
from document.config import get_settings
from document.handlers import probe_document
from document.storage import StorageUnavailable


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

    def __init__(self, refuse: bool = False) -> None:
        self.jobs: list[tuple[str, dict, str]] = []
        self._refuse = refuse

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str = "") -> object | None:
        """Ghi lại một job, hoặc từ chối nó.

        Args:
            name: Tên task.
            payload: Payload đã serialise.
            _queue_name: Queue đích.

        Returns:
            Một object giả, hoặc `None` khi từ chối — đúng cách arq diễn đạt một job trùng id.
        """
        if self._refuse:
            return None
        self.jobs.append((name, payload, _queue_name))
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


def _asked() -> dict:
    """Payload của một job, đã serialise.

    Returns:
        Dict đúng hình dạng arq chở.
    """
    return DocumentProbeRequested(
        document_id="doc-1", storage_key="documents/gv/doc-1.pdf", filename="sach.pdf"
    ).model_dump(mode="json")


@pytest.mark.asyncio
async def test_a_readable_file_is_handed_back_to_the_be_queue() -> None:
    """Đường thường: đọc xong thì kết quả đi về **queue của BE**, không về result store.

    Queue đích là nửa dễ sai nhất và nó không ném gì cả khi sai: job rơi vào một chỗ không ai
    nghe, và hệ thống trông y hệt một hệ thống đang rảnh.
    """
    queue = _Queue()
    out = await probe_document({"reader": _Reader(_a_pdf_with_text()), "redis": queue}, _asked())

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
    await probe_document({"reader": _Reader(None), "redis": queue}, _asked())

    _, payload, _ = queue.jobs[0]
    assert payload["state"] == DocumentState.FAILED
    assert payload["page_count"] is None
    assert payload["fault"] != ""


@pytest.mark.asyncio
async def test_a_result_that_cannot_be_handed_back_raises_so_arq_retries() -> None:
    """Không giao nổi kết quả thì **ném**, và đó là chủ ý.

    Khác hai ca trên: ở đây không còn đường nào để nói ra nữa, nên thứ duy nhất còn giá trị là
    để arq thử lại. Việc này đọc một tệp rồi gửi một message, không đổi gì ở đâu, nên chạy lại
    nó an toàn. Hết lượt thử thì phép suy *đứng quá lâu* của BE là lưới cuối.
    """
    with pytest.raises(RuntimeError):
        await probe_document(
            {"reader": _Reader(_a_pdf_with_text()), "redis": _Queue(refuse=True)}, _asked()
        )
