"""Hình dạng của plan 4b: tài liệu đi kèm tin nhắn, mỗi câu một mục kiến thức.

Hai loại khẳng định. Trường mới đều **tuỳ chọn**, nên payload trước plan 4b vẫn hợp lệ -- một
job đang nằm trong Redis lúc deploy không chết vì thiếu field. Và pha 2 **không** có chỗ chở nội
dung tài liệu: hậu ký ADR-27 chỉ rút luật lọc bài tập cho prompt soạn đề, vì câu luyện tập đi
thẳng tới học sinh mà không qua duyệt.
"""

import pytest

from contracts import (
    AttachedDocument,
    DraftQuestionRequested,
    ExplainTurnRequested,
    NextStepRequested,
    RetryQuestionRequested,
)


def test_a_turn_from_before_plan_4b_still_reads() -> None:
    asked = NextStepRequested.model_validate({"request_id": "r1"})

    assert asked.attached_document is None


def test_a_turn_carries_the_document_on_its_chip() -> None:
    asked = NextStepRequested(
        request_id="r1",
        attached_document=AttachedDocument(document_id="d1", filename="SGK Toán 6.pdf"),
    )

    assert asked.model_dump(mode="json")["attached_document"] == {
        "document_id": "d1",
        "filename": "SGK Toán 6.pdf",
        "state": "ready",
    }


def test_a_question_without_a_document_is_written_as_before() -> None:
    asked = DraftQuestionRequested.model_validate(
        {
            "request_id": "a:1:1",
            "subject": "Toán",
            "grade": "12",
            "topic_scope": "Hàm số",
            "ordinal": 1,
            "of_total": 10,
        }
    )

    assert (asked.focus_title, asked.focus_text, asked.other_foci) == ("", "", ())


@pytest.mark.parametrize("phase_two", [RetryQuestionRequested, ExplainTurnRequested])
def test_phase_two_has_no_room_for_document_content(phase_two: type) -> None:
    """Hậu ký ADR-27: pha 2 không nhận nội dung tài liệu cho tới một quyết định riêng.

    Thêm một trường chở nội dung tài liệu vào payload pha 2 thì test này đỏ -- đó là lúc phải viết
    quyết định ấy, không phải lúc lặng lẽ nối thêm.
    """
    fields = set(phase_two.model_fields)

    assert not fields & {"focus_title", "focus_text", "other_foci", "attached_document"}
    assert not any("document" in name or "chunk" in name for name in fields)
