"""Hình dạng của `draft-outline` (ADR-29): dàn ý đi AGENT→BE, và mỗi job nhận đúng một mục.

Ba loại khẳng định. `kind='outline'` mang mục và chỉ nó được mang mục -- cùng luật `steps` của
`plan`. Trường mới của job đều **tuỳ chọn**, nên payload cũ trong Redis vẫn hợp lệ. Và pha 2 không
có chỗ cho mục dàn ý nào, như nó không có chỗ cho chữ tài liệu.
"""

import pytest
from pydantic import ValidationError

from contracts import (
    DraftQuestionRequested,
    ExplainTurnRequested,
    NextStepCompleted,
    OutlineItem,
    RetryQuestionRequested,
    TurnRecord,
)


def _item(**overrides: object) -> OutlineItem:
    fields: dict[str, object] = {
        "questions": 2,
        "knowledge": "Kiến thức A",
        "formulas": ("$a+b=b+a$",),
        "approach": "Tính rồi so sánh",
        "source_nodes": (3, 4),
    }
    fields.update(overrides)
    return OutlineItem.model_validate(fields)


def test_an_outline_turn_carries_its_items() -> None:
    said = NextStepCompleted(request_id="r1", kind="outline", text="Dàn ý:", outline=(_item(),))

    assert said.outline[0].questions == 2
    assert said.model_dump(mode="json")["outline"][0]["formulas"] == ["$a+b=b+a$"]


def test_an_outline_turn_without_items_is_refused() -> None:
    with pytest.raises(ValidationError, match="needs at least one item"):
        NextStepCompleted(request_id="r1", kind="outline", text="Dàn ý:")


@pytest.mark.parametrize("kind", ["say", "plan", "ask_clarify", "call_tool"])
def test_only_an_outline_turn_may_carry_items(kind: str) -> None:
    extra: dict[str, object] = {}
    if kind == "plan":
        extra["steps"] = ({"tool_name": "create_draft", "title": "Tạo đề"},)
    if kind == "call_tool":
        extra["tool_name"] = "list_chapters"
    with pytest.raises(ValidationError, match="only kind='outline'"):
        NextStepCompleted(request_id="r1", kind=kind, text="x", outline=(_item(),), **extra)


@pytest.mark.parametrize(
    "overrides",
    [{"questions": 0}, {"questions": 11}, {"knowledge": ""}, {"approach": ""}],
)
def test_an_item_that_cannot_be_reviewed_is_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _item(**overrides)


def test_an_item_without_a_document_has_no_source() -> None:
    assert _item(source_nodes=(), formulas=()).source_nodes == ()


def test_an_outline_is_a_turn_of_its_own() -> None:
    record = TurnRecord(kind="outline", text="Dàn ý đề", tool_result={"version": 1})

    assert record.kind == "outline"


def test_a_job_from_before_the_outline_still_reads() -> None:
    asked = DraftQuestionRequested.model_validate(
        {
            "request_id": "a:1:1",
            "subject": "Toán",
            "grade": "6",
            "topic_scope": "Chương I",
            "ordinal": 1,
            "of_total": 5,
        }
    )

    assert (asked.item_knowledge, asked.item_formulas, asked.item_approach) == ("", (), "")
    assert (asked.item_part, asked.item_parts, asked.other_items) == (1, 1, ())


def _job(**overrides: object) -> DraftQuestionRequested:
    fields: dict[str, object] = {
        "request_id": "a:1:1",
        "subject": "Toán",
        "grade": "6",
        "topic_scope": "Chương I",
        "ordinal": 1,
        "of_total": 5,
    }
    fields.update(overrides)
    return DraftQuestionRequested.model_validate(fields)


@pytest.mark.parametrize(
    "overrides",
    [
        {"item_part": 0},
        {"item_parts": 11, "item_part": 1},
        {"item_part": 3, "item_parts": 2},
    ],
)
def test_a_job_cannot_be_a_part_its_item_does_not_have(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _job(**overrides)


def test_the_last_part_of_an_item_is_a_part() -> None:
    assert _job(item_part=2, item_parts=2).item_part == 2


@pytest.mark.parametrize("phase_two", [RetryQuestionRequested, ExplainTurnRequested])
def test_phase_two_has_no_room_for_an_outline_item(phase_two: type) -> None:
    """ADR-29: pha 2 không đổi -- không nhận tài liệu, không qua dàn ý."""
    fields = set(phase_two.model_fields)

    assert not any(name.startswith("item_") or "outline" in name for name in fields)
    assert "other_items" not in fields
