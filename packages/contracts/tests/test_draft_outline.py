"""Hình dạng của dàn ý (ADR-29, ADR-38): dàn ý đi AGENT→BE là lời kèm một con số, và khi giáo viên
đồng ý thì plan chở cách AGENT chia lời ấy thành câu.

Ba loại khẳng định. `kind='outline'` mang số câu và chỉ nó được mang số câu hay nút -- cùng luật
`steps` của `plan`; `split` chỉ đi với `plan`. Trường dàn ý của job đều **tuỳ chọn**, nên payload cũ
trong Redis vẫn hợp lệ. Và pha 2 không có chỗ cho chữ tài liệu.
"""

import pytest
from pydantic import ValidationError

from contracts import (
    DraftQuestionRequested,
    ExplainTurnRequested,
    NextStepCompleted,
    RetryQuestionRequested,
    Split,
    SplitJob,
    TurnRecord,
)


def test_an_outline_turn_carries_its_count_and_its_sources() -> None:
    said = NextStepCompleted(
        request_id="r1", kind="outline", text="Dàn ý:", outline_questions=5, outline_nodes=(3, 4)
    )

    assert (said.outline_questions, said.outline_nodes) == (5, (3, 4))


def test_an_outline_turn_without_a_count_is_refused() -> None:
    with pytest.raises(ValidationError, match="needs a question count"):
        NextStepCompleted(request_id="r1", kind="outline", text="Dàn ý:")


@pytest.mark.parametrize(
    "extra", [{"outline_questions": 3}, {"outline_nodes": (2,)}], ids=["count", "nodes"]
)
@pytest.mark.parametrize("kind", ["say", "plan", "ask_clarify", "call_tool"])
def test_only_an_outline_turn_may_carry_an_outline(kind: str, extra: dict[str, object]) -> None:
    more: dict[str, object] = {}
    if kind == "plan":
        more["steps"] = ({"tool_name": "create_draft", "title": "Tạo đề"},)
    if kind == "call_tool":
        more["tool_name"] = "list_chapters"
    with pytest.raises(ValidationError, match="only kind='outline'"):
        NextStepCompleted(request_id="r1", kind=kind, text="x", **extra, **more)


def _split(jobs: int = 2) -> Split:
    return Split(
        note="Câu 1 lo phần A, câu 2 lo phần B.",
        jobs=tuple(SplitJob(knowledge=f"Kiến thức {at}", approach="Tính") for at in range(jobs)),
    )


def test_a_drafting_plan_carries_how_the_outline_was_split() -> None:
    said = NextStepCompleted(
        request_id="r1",
        kind="plan",
        steps=({"tool_name": "start_drafting", "title": "Soạn câu hỏi"},),
        split=_split(),
    )

    assert len(said.split.jobs) == 2
    assert said.model_dump(mode="json")["split"]["jobs"][0]["formulas"] == []


@pytest.mark.parametrize("kind", ["say", "outline", "ask_clarify"])
def test_only_a_plan_may_carry_a_split(kind: str) -> None:
    extra: dict[str, object] = {"outline_questions": 2} if kind == "outline" else {}
    with pytest.raises(ValidationError, match="only kind='plan' may carry a split"):
        NextStepCompleted(request_id="r1", kind=kind, text="x", split=_split(), **extra)


@pytest.mark.parametrize(
    "build",
    [
        lambda: Split(note="x", jobs=()),
        lambda: SplitJob(knowledge="", approach="a"),
        lambda: SplitJob(knowledge="k", approach=""),
    ],
    ids=["no-job", "no-knowledge", "no-approach"],
)
def test_a_split_that_cannot_be_drafted_is_refused(build) -> None:
    with pytest.raises(ValidationError):
        build()


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


def test_a_retry_carries_the_outline_item_of_its_origin_and_nothing_of_the_document() -> None:
    """Hậu ký ADR-17 (26/10/2026): câu làm lại nhận mục dàn ý của câu gốc -- đúng ba trường giáo
    viên đã duyệt -- và không có chỗ nào cho chữ tài liệu (ADR-29: pha 2 không nhận tài liệu)."""
    fields = set(RetryQuestionRequested.model_fields)

    assert {name for name in fields if name.startswith("item_")} == {
        "item_knowledge",
        "item_formulas",
        "item_approach",
    }
    assert not any("focus" in name or "chunk" in name or "document" in name for name in fields)
    assert "other_items" not in fields


def test_the_tutor_turn_still_has_no_room_for_an_outline_item() -> None:
    """Gia sư pha 2 không đổi: không nhận tài liệu, không qua dàn ý."""
    fields = set(ExplainTurnRequested.model_fields)

    assert not any(name.startswith("item_") or "outline" in name for name in fields)
    assert "other_items" not in fields
