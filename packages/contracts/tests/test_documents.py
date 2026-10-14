"""Hình dạng của vòng xử lý tài liệu, thứ BE và `services/document` cùng dựa vào.

Mấy test này canh những điều khoản mà một lần sửa vô ý phá được mà không bên nào đỏ lên,
không phải canh chính pydantic.
"""

import pytest
from pydantic import ValidationError

from contracts import (
    DOCUMENT_PROBED_TASK,
    DOCUMENT_PROGRESS_TASK,
    INDEX_DOCUMENT_TASK,
    OCR_PAGES_TASK,
    PROBE_DOCUMENT_TASK,
    DocumentIndexRequested,
    DocumentPagesRequested,
    DocumentProbed,
    DocumentProbeRequested,
    DocumentProgress,
    DocumentState,
)


def test_there_are_exactly_four_states() -> None:
    """ADR-27 chốt **bốn** trạng thái, và con số ấy phải đếm được ở một chỗ.

    Thêm một trạng thái thứ năm mà không ai vẽ nó lên chip là tái tạo đúng cái bệnh mà
    `check_the_result_card_has_exactly_three_states` tồn tại để chữa: không dòng code nào
    sai, chỉ là không chỗ nào đếm.
    """
    assert {state.value for state in DocumentState} == {
        "processing",
        "ready",
        "no_text_layer",
        "failed",
    }


def test_a_verdict_is_not_a_failure() -> None:
    """*Không đọc được chữ* và *xử lý hỏng* phải là hai giá trị khác nhau.

    Gộp chúng là nói với giáo viên rằng cuốn sách của họ vô dụng trong khi thật ra worker
    vừa bị tắt — một câu sai về cùng một tệp, và nó chặn luôn lần thử lại đáng làm.
    """
    assert DocumentState.NO_TEXT_LAYER != DocumentState.FAILED


def test_the_request_carries_a_key_not_the_bytes() -> None:
    """Payload chở khoá, không chở tệp.

    Trần một tệp là 100 MB. Nhét byte vào đây là bắt Redis chuyên chở một cuốn sách cho
    mỗi lần tải lên, và test này đỏ vào đúng ngày ai đó thêm một field như vậy.
    """
    asked = DocumentProbeRequested(
        document_id="doc-1", storage_key="documents/gv/doc-1.pdf", filename="sach.pdf"
    )
    assert set(asked.model_dump()) == {
        "schema_version",
        "document_id",
        "storage_key",
        "filename",
    }


def test_the_request_round_trips_through_json() -> None:
    """arq serialise payload, nên hợp đồng phải sống qua một vòng JSON."""
    original = DocumentProbeRequested(
        document_id="doc-1", storage_key="documents/gv/doc-1.pdf", filename="sách.pdf"
    )
    assert DocumentProbeRequested.model_validate_json(original.model_dump_json()) == original


def test_the_result_round_trips_and_the_state_becomes_a_string() -> None:
    """`DocumentState` phải đi qua JSON thành một chuỗi thuần.

    `StrEnum` cho điều đó miễn phí, nhưng đổi nó sang `Enum` thường thì `model_dump(mode="json")`
    vẫn chạy trong khi phía nhận đọc ra một thứ khác — nên khẳng định chuỗi, không khẳng định kiểu.
    """
    done = DocumentProbed(
        document_id="doc-1", state=DocumentState.NO_TEXT_LAYER, fault="Tệp này không có chữ."
    )
    assert done.model_dump(mode="json")["state"] == "no_text_layer"
    assert DocumentProbed.model_validate_json(done.model_dump_json()) == done


def test_no_page_count_is_none_not_zero() -> None:
    """Mặc định là `None`, vì `.txt` và `.md` **không có** trang.

    Một số `0` hợp lệ về kiểu và sai về nghĩa: màn hình sẽ in "0 trang", và giáo viên sẽ tin.
    """
    assert DocumentProbed(document_id="doc-1", state=DocumentState.READY).page_count is None


def test_a_state_outside_the_four_is_refused() -> None:
    """Một trạng thái bịa ra phải chết ở biên, không chết ở lần ghi database."""
    with pytest.raises(ValidationError):
        DocumentProbed(document_id="doc-1", state="dang-nghi")


def test_the_two_task_names_are_not_the_same() -> None:
    """Hai chiều, hai tên.

    Trùng tên thì worker của BE và worker của `document` cùng nhận cùng một job, và triệu
    chứng là một vòng lặp vô hạn chứ không phải một lỗi.
    """
    assert PROBE_DOCUMENT_TASK != DOCUMENT_PROBED_TASK


def test_all_five_task_names_differ() -> None:
    """Từ `mongo-content-store` có bốn task trên ba queue, và hai cái trong số ấy cùng nằm trên
    queue của `services/document`. Trùng tên là một lô OCR bị đọc như một lần dò tệp -- payload sai
    hình dạng, và job chết ở `model_validate` thay vì đọc trang nào. `document-agent-hierarchy` thêm
    cái thứ năm, dựng cây.
    """
    names = [
        PROBE_DOCUMENT_TASK,
        DOCUMENT_PROBED_TASK,
        OCR_PAGES_TASK,
        DOCUMENT_PROGRESS_TASK,
        INDEX_DOCUMENT_TASK,
    ]
    assert len(set(names)) == len(names)


def test_a_page_batch_carries_a_key_not_the_bytes() -> None:
    """Mỗi lô đọc lại tệp từ object storage, cùng lý do với `DocumentProbeRequested`."""
    batch = DocumentPagesRequested(
        document_id="doc-1",
        storage_key="documents/gv/doc-1.pdf",
        filename="sách.pdf",
        first=11,
        page_count=184,
    )
    assert set(batch.model_dump()) == {
        "schema_version",
        "document_id",
        "storage_key",
        "filename",
        "first",
        "page_count",
    }
    assert DocumentPagesRequested.model_validate_json(batch.model_dump_json()) == batch


def test_progress_is_not_a_verdict() -> None:
    """Tiến độ không mang `state`: tài liệu vẫn *đang xử lý*, và chỉ `DocumentProbed` đổi điều ấy.

    Một tiếng báo tiến độ mang trạng thái là một đường thứ hai để chip đổi màu, và hai đường thì
    về sai thứ tự được.
    """
    told = DocumentProgress(document_id="doc-1", pages_read=20, page_count=184)
    assert "state" not in told.model_dump()
    assert DocumentProgress.model_validate_json(told.model_dump_json()) == told


@pytest.mark.parametrize("first, page_count", [(0, 10), (1, 0)])
def test_a_batch_that_would_read_nothing_is_refused(first: int, page_count: int) -> None:
    """Một lô không trang nào phải chết ở biên. Lọt qua thì nó tự giao lại chính nó với cùng id, bị
    arq từ chối vì job vẫn đang chạy, và chuỗi lô dừng im -- review Task 3 của
    `mongo-content-store`.
    """
    with pytest.raises(ValidationError):
        DocumentPagesRequested(
            document_id="doc-1",
            storage_key="documents/gv/doc-1.pdf",
            filename="sach.pdf",
            first=first,
            page_count=page_count,
        )


def test_an_index_job_carries_a_key_and_may_have_no_page_count() -> None:
    """Job dựng cây đọc bản thô từ Mongo và ảnh banner từ object storage, không chở byte; tệp văn
    bản thuần không có số trang, đúng như `DocumentProbed`.
    """
    asked = DocumentIndexRequested(document_id="d", storage_key="k", filename="a.txt")
    assert asked.page_count is None
    assert "content" not in DocumentIndexRequested.model_fields
    with pytest.raises(ValidationError):
        DocumentIndexRequested(document_id="d", storage_key="k", filename="a.pdf", page_count=0)
