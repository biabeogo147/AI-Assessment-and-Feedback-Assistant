"""Bước chia việc (ADR-38): dàn ý đã duyệt thành đúng số câu, mỗi câu một lời dặn tự đủ.

Không model thật nào được gọi: một model giả trả lời lần lượt các cách chia xếp sẵn và ghi lại
lời gọi.
"""

import pytest
from langchain_core.runnables import Runnable, RunnableLambda

from agent import llm
from agent.graphs.propose import split
from contracts import NextStepCompleted, NextStepRequested, PlanStep, TurnRecord


def _job(**overrides: object) -> split._Job:
    fields: dict[str, object] = {
        "part": "Câu 1–2",
        "knowledge": "Lũy thừa",
        "formulas": ("$a^m \\cdot a^n$",),
        "approach": "Rút gọn",
        "differs": "",
    }
    fields.update(overrides)
    return split._Job.model_validate(fields)


class Dividing:
    """Model giả: mỗi lời gọi trả cách chia kế tiếp, ghi lại các message nó nhận."""

    def __init__(self, *answers: tuple[split._Job, ...]) -> None:
        self.answers = list(answers)
        self.calls: list[list] = []

    def with_structured_output(self, schema: object, **kwargs: object) -> Runnable:
        assert schema is split._Split

        def divide(messages: list) -> split._Split:
            self.calls.append(list(messages))
            return split._Split(note="Câu 1 lo phần A.", jobs=self.answers.pop(0))

        return RunnableLambda(divide)


@pytest.fixture
def on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "enabled", lambda: True)


_PLAN = NextStepCompleted(
    request_id="r1",
    kind="plan",
    steps=(
        PlanStep(tool_name="create_draft", title="Tạo đề"),
        PlanStep(tool_name="start_drafting", title="Soạn câu hỏi theo dàn ý"),
    ),
    model_tokens=10,
)


def _agreed(kept: dict) -> NextStepRequested:
    return NextStepRequested(
        request_id="r1",
        history=(
            TurnRecord(kind="teacher", text="soạn 3 câu lũy thừa lớp 6"),
            TurnRecord(kind="outline", text="**Câu 1–3**: lũy thừa.", tool_result=kept),
            TurnRecord(kind="teacher", text="oke"),
        ),
    )


@pytest.mark.asyncio
async def test_a_drafting_plan_gets_one_job_per_question_of_the_outline(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    model = Dividing((_job(), _job(differs="hỏi chiều ngược lại"), _job(knowledge="Thứ tự")))
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await split.split_outline(_PLAN, _agreed({"version": 1, "for": "new", "total": 3}))

    assert [one.knowledge for one in step.split.jobs] == ["Lũy thừa", "Lũy thừa", "Thứ tự"]
    assert step.split.note == "Câu 1 lo phần A."
    # `differs` nối vào cách làm: chỗ duy nhất của lời dặn soạn câu nói về dạng câu.
    assert step.split.jobs[1].approach == f"Rút gọn\n{split.DIFFERS_LEAD} hỏi chiều ngược lại"
    assert step.split.jobs[0].approach == "Rút gọn"
    # Model đọc đúng lời dàn ý giáo viên đã đọc, câu giáo viên xin, và số câu.
    asked = model.calls[0][-1].text
    assert "**Câu 1–3**: lũy thừa." in asked and "soạn 3 câu lũy thừa lớp 6" in asked
    assert "đúng 3 job" in asked


@pytest.mark.asyncio
async def test_a_miscounted_split_goes_back_to_the_model_once(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    model = Dividing((_job(),) * 2, (_job(),) * 3)
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await split.split_outline(_PLAN, _agreed({"version": 1, "for": "new", "total": 3}))

    assert len(step.split.jobs) == 3 and len(model.calls) == 2
    assert model.calls[1][-1].text == split.recount(3, 2)


@pytest.mark.asyncio
async def test_too_few_jobs_twice_is_no_plan_and_too_many_are_cut(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    kept = {"version": 1, "for": "new", "total": 3}
    monkeypatch.setattr(llm, "chat_models", lambda: (Dividing((_job(),) * 2, (_job(),) * 2),))
    with pytest.raises(split.SplitFailed):
        await split.split_outline(_PLAN, _agreed(kept))

    many = (_job(knowledge="A"), _job(knowledge="B"), _job(knowledge="C"), _job(knowledge="D"))
    monkeypatch.setattr(llm, "chat_models", lambda: (Dividing(many, many),))
    step = await split.split_outline(_PLAN, _agreed(kept))
    assert [one.knowledge for one in step.split.jobs] == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_replacing_a_question_splits_out_that_one_question(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    model = Dividing((_job(),))
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))
    plan = _PLAN.model_copy(
        update={"steps": (PlanStep(tool_name="replace_question", title="Thay câu 6"),)}
    )

    step = await split.split_outline(
        plan, _agreed({"version": 2, "for": "replace", "first": 6, "total": 1})
    )

    assert len(step.split.jobs) == 1
    assert "thay câu 6" in model.calls[0][-1].text


@pytest.mark.asyncio
async def test_the_job_text_gets_its_backslashes_back(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """`\\frac` qua bộ giải mã JSON thành form-feed + "rac"; job soạn câu đọc đúng chữ này."""
    mangled = "\frac{a}{b}"
    job = _job(knowledge=f"Phân số ${mangled}$", formulas=(f"${mangled}$",), approach=mangled)
    monkeypatch.setattr(llm, "chat_models", lambda: (Dividing((job,)),))

    step = await split.split_outline(_PLAN, _agreed({"version": 1, "for": "new", "total": 1}))

    made = step.split.jobs[0]
    assert "\\frac{a}{b}" in made.knowledge
    assert made.formulas == ("$\\frac{a}{b}$",)
    assert made.approach == "\\frac{a}{b}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("step", "history"),
    [
        # Không phải plan soạn: không chia gì.
        (NextStepCompleted(request_id="r1", kind="say", text="Chào bạn."), None),
        (
            _PLAN.model_copy(update={"steps": (PlanStep(tool_name="publish", title="x"),)}),
            None,
        ),
        # Plan soạn mà chưa có dàn ý nào: cổng duyệt của BE từ chối nó bằng lời của nó.
        (_PLAN, (TurnRecord(kind="teacher", text="soạn 3 câu"),)),
    ],
    ids=["say", "not-drafting", "no-outline"],
)
async def test_only_a_drafting_plan_on_a_shown_outline_is_split(
    monkeypatch: pytest.MonkeyPatch, on: None, step: NextStepCompleted, history: tuple | None
) -> None:
    model = Dividing()
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))
    asked = (
        NextStepRequested(request_id="r1", history=history)
        if history is not None
        else _agreed({"version": 1, "for": "new", "total": 3})
    )

    assert await split.split_outline(step, asked) is step
    assert model.calls == []


def test_the_split_prompt_names_the_task_and_never_the_answers() -> None:
    told = split.split_prompt("soạn đề", "**Câu 1**: A", 4, None)

    assert told.endswith("Chia thành đúng 4 job.")
    assert "thay câu 2" in split.split_prompt("x", "y", 1, 2)


# ------------------------------------------------------------------ review pha 1


@pytest.mark.asyncio
async def test_a_replacement_split_into_many_jobs_is_never_cut_to_question_one(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Review pha 1: dàn ý cả đề được đổi thành *thay câu 3*; model chia lại cả đề. Job đầu là câu
    1, không phải câu 3 -- cắt đuôi là thay câu 3 bằng câu 1. Lời trả lại nhắc đúng câu 3."""
    model = Dividing((_job(),) * 5, (_job(),) * 5)
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))
    plan = _PLAN.model_copy(
        update={"steps": (PlanStep(tool_name="replace_question", title="Thay câu 3"),)}
    )
    kept = {"version": 2, "for": "replace", "first": 3, "total": 1}

    with pytest.raises(split.SplitFailed):
        await split.split_outline(plan, _agreed(kept))

    assert "câu 3" in model.calls[1][-1].text and len(model.calls) == 2


@pytest.mark.asyncio
async def test_extra_jobs_for_a_new_paper_are_cut_without_asking_again(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    many = (_job(knowledge="A"), _job(knowledge="B"), _job(knowledge="C"), _job(knowledge="D"))
    model = Dividing(many)
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await split.split_outline(_PLAN, _agreed({"version": 1, "for": "new", "total": 3}))

    assert [one.knowledge for one in step.split.jobs] == ["A", "B", "C"]
    assert len(model.calls) == 1


@pytest.mark.asyncio
async def test_a_job_left_empty_goes_back_to_the_model(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Review pha 1: một job trống là một người soạn nhận lời dặn rỗng -- không thay bằng chữ giữ
    chỗ; trả lại model, lần hai vẫn trống thì không có plan."""
    empty = (_job(), _job(knowledge="  "))
    model = Dividing(empty, (_job(), _job(knowledge="B")))
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await split.split_outline(_PLAN, _agreed({"version": 1, "for": "new", "total": 2}))

    assert [one.knowledge for one in step.split.jobs] == ["Lũy thừa", "B"]
    assert "Job 2" in model.calls[1][-1].text

    monkeypatch.setattr(llm, "chat_models", lambda: (Dividing(empty, empty),))
    with pytest.raises(split.SplitFailed):
        await split.split_outline(_PLAN, _agreed({"version": 1, "for": "new", "total": 2}))


def _later(*after: TurnRecord) -> NextStepRequested:
    """Dàn ý, rồi những gì xảy ra sau nó, rồi lời giáo viên mở lượt này."""
    return NextStepRequested(
        request_id="r1",
        history=(
            TurnRecord(kind="teacher", text="soạn 3 câu"),
            TurnRecord(kind="outline", text="Dàn ý", tool_result={"for": "new", "total": 3}),
            *after,
            TurnRecord(kind="teacher", text="soạn thêm 2 câu đi"),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "asked",
    [
        # Dàn ý đã thành đề ở một plan trước.
        _later(
            TurnRecord(kind="teacher", text="oke"),
            TurnRecord(kind="plan", tool_result={"steps": ["Soạn"], "total": 1}),
            TurnRecord(kind="assistant", text="Mình soạn xong rồi."),
        ),
        # Kriky đã đáp một câu sau dàn ý: dàn ý ấy đã qua.
        _later(
            TurnRecord(kind="teacher", text="câu 2 khó không?"),
            TurnRecord(kind="assistant", text="Câu 2 mức vận dụng."),
        ),
    ],
    ids=["used", "answered"],
)
async def test_an_outline_that_is_not_the_one_just_answered_is_not_split(
    monkeypatch: pytest.MonkeyPatch, on: None, asked: NextStepRequested
) -> None:
    """Review pha 1: cùng luật *ngay trước* với cổng duyệt của BE -- dàn ý cũ thì BE từ chối plan,
    chia nó chỉ tốn một lời gọi model."""
    model = Dividing()
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    assert await split.split_outline(_PLAN, asked) is _PLAN
    assert model.calls == []


@pytest.mark.asyncio
async def test_a_lookup_within_this_turn_does_not_hide_the_outline(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Bước tra cứu của chính lượt này đứng sau lời giáo viên: dàn ý vẫn là dàn ý vừa đáp, và lời
    giáo viên trước nó gồm cả lời sửa lẫn yêu cầu gốc."""
    model = Dividing((_job(),) * 3)
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))
    asked = NextStepRequested(
        request_id="r1",
        history=(
            TurnRecord(kind="teacher", text="soạn 3 câu lũy thừa"),
            TurnRecord(kind="outline", text="Dàn ý 1", tool_result={"for": "new", "total": 3}),
            TurnRecord(kind="teacher", text="câu 2 đổi sang so sánh"),
            TurnRecord(kind="outline", text="Dàn ý 2", tool_result={"for": "new", "total": 3}),
            TurnRecord(kind="teacher", text="oke"),
            TurnRecord(kind="tool_call", tool_name="list_class"),
            TurnRecord(kind="tool_result", tool_name="list_class", tool_result={}),
        ),
    )

    step = await split.split_outline(_PLAN, asked)

    told = model.calls[0][-1].text
    assert "Dàn ý 2" in told and "Dàn ý 1" not in told.split("đồng ý:")[1]
    assert "soạn 3 câu lũy thừa" in told and "câu 2 đổi sang so sánh" in told
    assert len(step.split.jobs) == 3


@pytest.mark.asyncio
async def test_a_plan_for_a_different_job_than_the_outline_is_not_split(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    model = Dividing()
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))
    replacing = _PLAN.model_copy(
        update={"steps": (PlanStep(tool_name="replace_question", title="Thay câu 2"),)}
    )

    assert await split.split_outline(replacing, _agreed({"for": "new", "total": 3})) is replacing
    assert await split.split_outline(_PLAN, _agreed({"for": "replace", "total": 1})) is _PLAN
    assert model.calls == []


class Unparsed:
    """Model giả trả lời không parse được, kèm báo cáo token."""

    def __init__(self) -> None:
        self.calls = 0

    def with_structured_output(self, schema: object, **kwargs: object) -> Runnable:
        def answer(messages: list) -> dict:
            self.calls += 1
            raw = type("Raw", (), {"usage_metadata": {"total_tokens": 7}})()
            return {"parsed": None, "raw": raw, "parsing_error": "hỏng"}

        return RunnableLambda(answer)


@pytest.mark.asyncio
async def test_a_split_that_never_parses_ends_the_turn_in_a_system_notice(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """`SplitFailed` lan tới handler: lượt ra thông báo hệ thống (ADR-30), không sập job, không lùi
    về mock."""
    from agent.handlers import _MODEL_DOWN, propose_next_step

    model = Unparsed()
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))
    with pytest.raises(split.SplitFailed):
        await split.split_outline(_PLAN, _agreed({"version": 1, "for": "new", "total": 2}))
    assert model.calls == 2

    async def agreed_plan(request: NextStepRequested) -> NextStepCompleted:
        return await split.split_outline(_PLAN, request)

    monkeypatch.setattr("agent.handlers.propose", agreed_plan)
    answer = await propose_next_step(
        {}, _agreed({"version": 1, "for": "new", "total": 2}).model_dump(mode="json")
    )

    assert (answer["kind"], answer["text"], answer["notice"]) == ("say", _MODEL_DOWN, True)


@pytest.mark.asyncio
async def test_the_tokens_of_every_split_call_are_counted(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    class Counted(Dividing):
        def with_structured_output(self, schema: object, **kwargs: object) -> Runnable:
            plain = super().with_structured_output(schema)
            raw = type("Raw", (), {"usage_metadata": {"total_tokens": 5}})()
            return plain | RunnableLambda(lambda parsed: {"parsed": parsed, "raw": raw})

    monkeypatch.setattr(llm, "chat_models", lambda: (Counted((_job(),), (_job(),) * 2),))

    step = await split.split_outline(_PLAN, _agreed({"version": 1, "for": "new", "total": 2}))

    assert step.model_tokens == 10 + 5 + 5
