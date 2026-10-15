"""Lịch sử gửi AGENT không phình vì chữ đã đọc và dàn ý đã bị thay (`draft-outline`, ADR-29).

`read_section` trả tới tám nghìn ký tự mỗi phần, mười phần một lượt; phát lại nguyên văn ở mọi lượt
sau là prompt không ai trả nổi. Bốn khẳng định: chữ đã thành dàn ý chỉ còn dấu đã đọc gì; chữ chưa
thành dàn ý ở lại, tới mười phần; chỉ dàn ý **mới nhất** giữ mục; và chữ đọc không tới client.
"""

from datetime import UTC, datetime

from be.teacher_chat import _as_records, _visible
from schema.models import TeacherTurn

_NOW = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)


def _turn(sequence: int, kind: str, **fields: object) -> TeacherTurn:
    return TeacherTurn(
        conversation_id="c1",
        sequence=sequence,
        kind=kind,
        text=str(fields.pop("text", "")),
        tool_name=str(fields.pop("tool_name", "")),
        tool_args=fields.pop("tool_args", {}),
        tool_result=fields.pop("tool_result", {}),
        # Mặc định của cột chỉ có khi hàng đi qua database; hàng dựng tay phải tự điền.
        entity_kind="",
        entity_id="",
        choices=[],
        more_choices=0,
        model_tokens=0,
        duration_ms=0,
        created_at=_NOW,
    )


_READ = {
    "found": True,
    "part": 1,
    "parts": 2,
    "more": True,
    "nodes": [1],
    "labels": ["Bài 1. Bài A (tr. 5–6)"],
    "text": "chữ của bài " * 500,
}


def test_a_read_already_written_into_an_outline_keeps_what_was_read_but_not_the_text() -> None:
    records = _as_records(
        [
            _turn(0, "teacher", text="soạn 2 câu chương I"),
            _turn(1, "tool_call", tool_name="read_section", tool_args={"part": "1"}),
            _turn(2, "tool_result", tool_name="read_section", tool_result=_READ),
            _turn(3, "outline", text="Dàn ý", tool_result={"version": 1, "items": []}),
        ]
    )

    shrunk = records[2].tool_result
    assert "text" not in shrunk
    assert shrunk["elided"] is True
    assert (shrunk["nodes"], shrunk["labels"], shrunk["part"]) == ([1], _READ["labels"], 1)
    # Lời gọi giữ nguyên: nó nhỏ, và nó là thứ nói *đã đọc phần nào*.
    assert records[1].tool_args == {"part": "1"}


def test_a_read_not_yet_written_into_an_outline_keeps_its_text() -> None:
    """Đọc rồi hỏi lại giáo viên: lượt sau viết dàn ý từ chữ ấy, không phải đọc lại."""
    records = _as_records(
        [
            _turn(0, "outline", text="Dàn ý cũ", tool_result={"version": 1, "items": []}),
            _turn(1, "tool_result", tool_name="read_section", tool_result=_READ),
            _turn(2, "assistant", text="Bạn muốn mức độ nào?"),
        ]
    )

    assert records[1].tool_result == _READ


def test_reads_waiting_for_an_outline_never_pile_up_past_ten_parts() -> None:
    turns = [
        _turn(sequence, "tool_result", tool_name="read_section", tool_result=_READ)
        for sequence in range(12)
    ]

    kept = ["text" in record.tool_result for record in _as_records(turns)]

    assert kept == [False, False] + [True] * 10


def test_other_tool_results_pass_through_untouched() -> None:
    listed = {"found": True, "candidates": [{"node": 0, "label": "Chương I"}], "more": 0}
    records = _as_records([_turn(0, "tool_result", tool_name="list_chapters", tool_result=listed)])

    assert records[0].tool_result == listed


def test_only_the_latest_outline_keeps_its_items() -> None:
    items = [{"questions": 2, "knowledge": "A", "formulas": [], "approach": "B"}]
    records = _as_records(
        [
            _turn(0, "outline", text="bản 1", tool_result={"version": 1, "items": items}),
            _turn(1, "teacher", text="câu 2 đổi sang hình học"),
            _turn(2, "outline", text="bản 2", tool_result={"version": 2, "items": items}),
        ]
    )

    assert records[0].tool_result == {"version": 1, "superseded": True}
    assert records[2].tool_result == {"version": 2, "items": items}
    # Chữ BE đã in vẫn ở lại: đó là thứ giáo viên đã đọc.
    assert records[0].text == "bản 1"


def test_the_client_never_receives_the_text_read() -> None:
    shown = _visible(_turn(2, "tool_result", tool_name="read_section", tool_result=_READ))

    assert "text" not in shown.tool_result
    assert shown.tool_result["labels"] == _READ["labels"]
