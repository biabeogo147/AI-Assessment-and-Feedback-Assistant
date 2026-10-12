"""AGENT dùng tài liệu (plan 4b): job soạn câu nhận đúng mục của nó, Kriky biết tài liệu đính kèm.

Không model nào được gọi: các khẳng định ở đây là về **chữ đưa vào prompt** -- brief của một job, và
system prompt của pha lên plan.
"""

import pytest
from langchain_core.runnables import RunnableLambda

from agent import llm
from agent.graphs.authoring import draft_brief
from agent.graphs.propose import _describe_tool, _Proposal, propose
from contracts import (
    AttachedDocument,
    DraftQuestionRequested,
    NextStepRequested,
    ToolSpec,
    TurnRecord,
)


def _asked(**extra) -> DraftQuestionRequested:
    return DraftQuestionRequested(
        request_id="a:1:1",
        subject="Toán",
        grade="6",
        topic_scope="Chương I",
        ordinal=1,
        of_total=3,
        **extra,
    )


def test_a_question_with_a_unit_is_told_its_unit_its_text_and_what_others_cover() -> None:
    brief = draft_brief(
        _asked(
            focus_title="Chương I. SỐ TỰ NHIÊN › Bài 1. Tập hợp",
            focus_text="Tập hợp là một khái niệm cơ bản …",
            other_foci=("Chương I. SỐ TỰ NHIÊN › Bài 2. Ghi số",),
        )
    )

    assert "CHỈ hỏi kiến thức của mục: Chương I. SỐ TỰ NHIÊN › Bài 1. Tập hợp" in brief
    assert "Tập hợp là một khái niệm cơ bản" in brief
    # Hậu ký ADR-27: kiến thức để viết câu mới, không kho câu để chép.
    assert "Không chép nguyên một câu" in brief
    assert "· Chương I. SỐ TỰ NHIÊN › Bài 2. Ghi số" in brief
    # Lời nhắc chung *"khía cạnh khác nhau"* nhường chỗ cho mục cụ thể.
    assert "khía cạnh khác nhau" not in brief


def test_a_question_without_a_document_is_briefed_as_before() -> None:
    brief = draft_brief(_asked())

    assert "khía cạnh khác nhau" in brief
    assert "mục" not in brief.split("Phạm vi giáo viên giới hạn")[1]


def test_an_optional_argument_is_marked_for_the_model() -> None:
    spec = ToolSpec(
        name="create_draft",
        description="Mở một đề nháp trống.",
        arguments={"subject": "môn", "document_id": "id tài liệu"},
        optional=("document_id",),
    )

    described = _describe_tool(spec)

    assert "document_id (tùy chọn): id tài liệu" in described
    assert "subject: môn" in described


@pytest.mark.asyncio
async def test_kriky_is_told_the_attached_document_and_its_id(monkeypatch) -> None:
    prompts: list[str] = []

    class Recording:
        def with_structured_output(self, schema, **kwargs):
            def answer(messages):
                prompts.append("\n".join(message.text for message in messages))
                return _Proposal(kind="say", text="vâng")

            return RunnableLambda(answer)

    monkeypatch.setattr(llm, "enabled", lambda: True)
    monkeypatch.setattr(llm, "chat_models", lambda: (Recording(),))

    await propose(
        NextStepRequested(
            request_id="r1",
            history=(TurnRecord(kind="teacher", text="soạn 10 câu chương 1"),),
            attached_document=AttachedDocument(document_id="book", filename="SGK Toán 6.pdf"),
        )
    )

    assert "Tài liệu giáo viên đính kèm: SGK Toán 6.pdf (document_id = book)." in prompts[0]


def test_a_unit_with_no_text_is_briefed_without_an_empty_frame() -> None:
    """Review B5: mục có tên mà đoạn không đọc được -- không gửi khung `<<< >>>` rỗng."""
    brief = draft_brief(_asked(focus_title="Chương I › Bài 1", focus_text="  "))

    assert "<<<" not in brief
    assert "khía cạnh khác nhau" in brief


@pytest.mark.asyncio
async def test_kriky_is_told_a_document_still_being_read(monkeypatch) -> None:
    """Review B6: chip của tệp còn đang xử lý -- Kriky được báo, không soạn như thể không có."""
    prompts: list[str] = []

    class Recording:
        def with_structured_output(self, schema, **kwargs):
            def answer(messages):
                prompts.append("\n".join(message.text for message in messages))
                return _Proposal(kind="say", text="vâng")

            return RunnableLambda(answer)

    monkeypatch.setattr(llm, "enabled", lambda: True)
    monkeypatch.setattr(llm, "chat_models", lambda: (Recording(),))

    await propose(
        NextStepRequested(
            request_id="r1",
            history=(TurnRecord(kind="teacher", text="soạn đề từ file này"),),
            attached_document=AttachedDocument(
                document_id="new", filename="Mới tải.pdf", state="processing"
            ),
        )
    )

    assert "Mới tải.pdf -- đang xử lý" in prompts[0]
    assert "document_id = new" not in prompts[0]


@pytest.mark.asyncio
async def test_a_broken_document_is_not_something_to_wait_for(monkeypatch) -> None:
    """Review B7: tài liệu hỏng thì bảo chờ là kẹt đoạn chat mãi -- nói nó không dùng được."""
    prompts: list[str] = []

    class Recording:
        def with_structured_output(self, schema, **kwargs):
            def answer(messages):
                prompts.append("\n".join(message.text for message in messages))
                return _Proposal(kind="say", text="vâng")

            return RunnableLambda(answer)

    monkeypatch.setattr(llm, "enabled", lambda: True)
    monkeypatch.setattr(llm, "chat_models", lambda: (Recording(),))

    await propose(
        NextStepRequested(
            request_id="r1",
            history=(TurnRecord(kind="teacher", text="soạn đề từ file này"),),
            attached_document=AttachedDocument(
                document_id="bad", filename="Hỏng.pdf", state="failed"
            ),
        )
    )

    assert "Hỏng.pdf -- KHÔNG đọc được" in prompts[0]
    assert "chờ" not in prompts[0].split("Hỏng.pdf")[1].split("\n")[0]
