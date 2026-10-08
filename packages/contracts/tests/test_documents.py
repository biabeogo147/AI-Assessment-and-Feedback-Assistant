"""Hình dạng của vòng xử lý tài liệu, thứ BE và `services/document` cùng dựa vào.

Mấy test này canh những điều khoản mà một lần sửa vô ý phá được mà không bên nào đỏ lên,
không phải canh chính pydantic.
"""

import pytest
from pydantic import ValidationError

from contracts import (
    DOCUMENT_PROBED_TASK,
    PROBE_DOCUMENT_TASK,
    DocumentProbed,
    DocumentProbeRequested,
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
