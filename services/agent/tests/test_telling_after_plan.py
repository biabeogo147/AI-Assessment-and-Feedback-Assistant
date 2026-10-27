"""Lượt kể lại sau plan khi không có model (ADR-25, hậu ký 22/10/2026).

BE hỏi `propose_next_step` thêm một lần sau khi plan đã chạy, với `plannable` rỗng. Máy dev không
key vẫn phải có câu kết, và câu ấy chỉ nói đúng điều các bước đã trả về -- không đổ JSON thô như
nhánh *có kết quả tool* của mock, không nói quá.
"""

import pytest

from agent import handlers
from contracts import NextStepRequested, ToolSpec, TurnRecord

_READ = (ToolSpec(name="last_plan", description="Kể gọn plan gần nhất"),)


def _after(
    *results: dict, titles: tuple[str, ...] = ("Tạo đề trống", "Soạn câu hỏi")
) -> NextStepRequested:
    turns = [
        TurnRecord(kind="teacher", text="soạn 3 câu"),
        TurnRecord(kind="plan", tool_result={"steps": list(titles), "total": len(titles)}),
    ]
    for name, result in zip(("create_draft", "start_drafting"), results, strict=False):
        turns.append(TurnRecord(kind="tool_call", tool_name=name))
        turns.append(TurnRecord(kind="tool_result", tool_name=name, tool_result=result))
    return NextStepRequested(request_id="r1", history=tuple(turns), catalog=_READ)


def test_a_plan_that_ran_is_told_step_by_step() -> None:
    step = handlers.next_step(
        _after({"created": True, "assessment_id": "a1"}, {"started": True, "queued": 3})
    )
    assert step.kind == "say"
    assert step.text == "Mình đã tạo đề trống; soạn câu hỏi."


def test_a_step_that_broke_is_told_with_what_be_said() -> None:
    step = handlers.next_step(
        _after(
            {"created": True, "assessment_id": "a1"},
            {"started": False, "reason": "question_count phải là số", "said": "thiếu số câu"},
        )
    )
    assert step.text == "Mình đã tạo đề trống, nhưng dừng ở bước soạn câu hỏi (thiếu số câu)."
    # Chữ viết cho model (`reason`) không bao giờ lọt vào câu kết.
    assert "question_count" not in step.text


def test_a_plan_that_broke_at_once_says_nothing_was_done() -> None:
    step = handlers.next_step(_after({"error": "không chạy xong"}))
    assert step.text == "Mình chưa làm được bước tạo đề trống."


def test_a_turn_with_a_plan_still_open_for_planning_is_not_a_telling_turn() -> None:
    # Còn `plannable` là còn ở pha 1 của một lượt mới, không phải lượt kể lại.
    asked = _after({"created": True}).model_copy(
        update={"plannable": (ToolSpec(name="create_draft", description="Tạo đề"),)}
    )
    assert handlers.next_step(asked).text != "Mình đã tạo đề trống."


def test_the_drafting_skill_tells_how_to_tell() -> None:
    """Kể thế nào là bước 6 của skill `soan-de`, không phải một prompt riêng của BE hay AGENT."""
    from agent import skills

    text = skills.named(("soan-de",))[0].body
    assert "6. Plan vừa chạy xong" in text
    assert "last_plan" in text


@pytest.mark.asyncio
async def test_the_model_may_say_nothing_on_the_telling_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review `report-into-propose` (N1): `say` rỗng ở lượt kể lại là im, không bị hỏi lại thành một
    câu *chưa hiểu ý bạn*."""
    from langchain_core.runnables import RunnableLambda

    from agent import llm, skill_router
    from agent.graphs.propose.graph import propose
    from agent.graphs.propose.proposal import _Proposal

    class Scripted:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def with_structured_output(self, schema: object, **kwargs: object) -> RunnableLambda:
            def answer(messages: object) -> _Proposal:
                self.prompts.append(chr(10).join(message.text for message in messages))
                return _Proposal(kind="say", text="")

            return RunnableLambda(answer)

    async def only_general(history: object) -> tuple[str, ...]:
        return ("tro-chuyen-chung",)

    scripted = Scripted()
    monkeypatch.setattr(llm, "enabled", lambda: True)
    monkeypatch.setattr(llm, "chat_models", lambda: (scripted,))
    monkeypatch.setattr(skill_router, "choose", only_general)

    step = await propose(_after({"created": True, "assessment_id": "a1"}))

    assert (step.kind, step.text, step.notice) == ("say", "", False)
    assert len(scripted.prompts) == 1
    # Bước 6 của `soan-de` có trong prompt dù bộ chọn skill có chọn gì (V4).
    assert "6. Plan vừa chạy xong" in scripted.prompts[0]


@pytest.mark.asyncio
async def test_a_class_plan_is_told_with_the_class_skill_not_the_drafting_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plan `tao-lop`: plan tạo lớp mà kể bằng bước 6 của `soan-de` thì model nói về đề và câu đang
    soạn cho một việc không có đề nào. Lượt kể lại nạp skill của tool plan vừa chạy."""
    from langchain_core.runnables import RunnableLambda

    from agent import llm, skill_router
    from agent.graphs.propose.graph import propose
    from agent.graphs.propose.proposal import _Proposal

    prompts: list[str] = []

    class Scripted:
        def with_structured_output(self, schema: object, **kwargs: object) -> RunnableLambda:
            def answer(messages: object) -> _Proposal:
                prompts.append(chr(10).join(message.text for message in messages))
                return _Proposal(kind="say", text="Đã tạo lớp 12C.")

            return RunnableLambda(answer)

    async def only_general(history: object) -> tuple[str, ...]:
        return ("tro-chuyen-chung",)

    monkeypatch.setattr(llm, "enabled", lambda: True)
    monkeypatch.setattr(llm, "chat_models", lambda: (Scripted(),))
    monkeypatch.setattr(skill_router, "choose", only_general)
    turns = (
        TurnRecord(kind="teacher", text="tạo lớp 12C"),
        TurnRecord(kind="plan", tool_result={"steps": ["Tạo lớp 12C"], "total": 1}),
        TurnRecord(kind="tool_call", tool_name="create_class"),
        TurnRecord(
            kind="tool_result",
            tool_name="create_class",
            tool_result={"created": True, "class_id": "c1", "name": "12C"},
        ),
    )

    await propose(NextStepRequested(request_id="r1", history=turns, catalog=_READ))

    assert "6. Plan tạo lớp vừa chạy xong" in prompts[0]
    assert "6. Plan vừa chạy xong" not in prompts[0]


def test_a_plan_that_makes_a_class_and_a_paper_is_told_with_both_skills() -> None:
    """Review plan `tao-lop`: plan *tạo lớp rồi soạn đề* cần cả bước kể lại của hai skill."""
    from agent.graphs.propose.history import telling_skills

    turns = (
        TurnRecord(kind="teacher", text="tạo lớp 12C rồi soạn 3 câu"),
        TurnRecord(kind="plan", tool_result={"steps": ["Tạo lớp", "Tạo đề trống"], "total": 2}),
        TurnRecord(kind="tool_result", tool_name="create_class", tool_result={"created": True}),
        TurnRecord(kind="tool_result", tool_name="create_draft", tool_result={"created": True}),
    )

    told = telling_skills(NextStepRequested(request_id="r1", history=turns, catalog=_READ))

    assert told == {"lop-va-ket-qua", "soan-de"}
