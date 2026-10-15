"""Kriky nêu dàn ý đề (ADR-29, `draft-outline`): hình dạng model trả lời, và lịch sử nó đọc lại.

Không model thật nào được gọi. Ba loại khẳng định: một dàn ý đi ngược về BE đủ mục và đủ `for`;
dấu gạch chéo bị bộ giải mã JSON nuốt được trả lại ở cả ba trường chữ; và một lượt dàn ý trong lịch
sử tới model kèm các mục, để sửa dàn ý là nêu lại đủ mục.
"""

import pytest
from langchain_core.runnables import Runnable, RunnableLambda

from agent import llm
from agent.graphs import propose as propose_module
from agent.graphs.propose import (
    _CORE,
    _UNCLEAR,
    _Argument,
    _compose,
    _library_first,
    _miscounted,
    _OutlineItem,
    _Proposal,
    _read_before_outline,
    propose,
)
from agent.handlers import _AGREES
from contracts import (
    AttachedDocument,
    NextStepCompleted,
    NextStepRequested,
    OutlineItem,
    TurnRecord,
)


class Scripted:
    """Một chat model trả lời bằng các đề nghị xếp sẵn, có ghi lại các prompt."""

    def __init__(self, answers: list[_Proposal]) -> None:
        self.answers = answers
        self.prompts: list[str] = []

    def with_structured_output(self, schema: object, **kwargs: object) -> Runnable:
        def answer(messages: object) -> _Proposal:
            self.prompts.append("\n".join(message.text for message in messages))
            return self.answers.pop(0)

        return RunnableLambda(answer)


@pytest.fixture
def on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "enabled", lambda: True)


def _asked(*history: TurnRecord) -> NextStepRequested:
    return NextStepRequested(
        request_id="r1",
        teacher_name="Cô Lan",
        history=history or (TurnRecord(kind="teacher", text="soạn 3 câu chương 1"),),
    )


def _item(**overrides: object) -> _OutlineItem:
    fields: dict[str, object] = {
        "questions": 2,
        "knowledge": "Lũy thừa",
        "formulas": ("$a^m \\cdot a^n$",),
        "approach": "Rút gọn",
        "source_nodes": (3,),
    }
    fields.update(overrides)
    return _OutlineItem.model_validate(fields)


@pytest.mark.asyncio
async def test_an_outline_reaches_be_with_its_items_and_its_purpose(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    outline = _Proposal(
        kind="outline",
        text="Mình đề xuất dàn ý.",
        outline=(_item(), _item(questions=1, knowledge="Thứ tự")),
        tool_args=(_Argument(param="for", value="new"),),
    )
    monkeypatch.setattr(llm, "chat_models", lambda: (Scripted([outline]),))

    step = await propose(_asked())

    assert step.kind == "outline"
    assert [(one.questions, one.knowledge) for one in step.outline] == [
        (2, "Lũy thừa"),
        (1, "Thứ tự"),
    ]
    assert step.outline[0].source_nodes == (3,)
    assert step.tool_args == {"for": "new"}


@pytest.mark.asyncio
async def test_the_three_text_fields_get_their_backslashes_back(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """`\\frac` qua bộ giải mã JSON thành form-feed + "rac"; BE in mục nguyên văn ra `MathText`."""
    mangled = "\frac{a}{b}"
    outline = _Proposal(
        kind="outline",
        text="Dàn ý.",
        outline=(
            _item(knowledge=f"Phân số ${mangled}$", formulas=(f"${mangled}$",), approach=mangled),
        ),
    )
    monkeypatch.setattr(llm, "chat_models", lambda: (Scripted([outline]),))

    step = await propose(_asked())

    item = step.outline[0]
    assert "\\frac{a}{b}" in item.knowledge
    assert item.formulas == ("$\\frac{a}{b}$",)
    assert item.approach == "\\frac{a}{b}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "broken",
    [
        _Proposal(kind="outline", text="Dàn ý."),
        _Proposal(kind="outline", text="Dàn ý.", outline=(_item(questions=0),)),
        _Proposal(kind="outline", text="Dàn ý.", outline=(_item(approach=""),)),
    ],
)
async def test_an_outline_that_cannot_be_shown_is_asked_again(
    monkeypatch: pytest.MonkeyPatch, on: None, broken: _Proposal
) -> None:
    fixed = _Proposal(kind="outline", text="Dàn ý.", outline=(_item(),))
    model = Scripted([broken, fixed])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked())

    assert step.kind == "outline" and step.outline[0].questions == 2
    assert len(model.prompts) == 2


def test_an_outline_in_the_history_comes_back_with_its_items() -> None:
    """Sửa dàn ý là nêu lại đủ mục, nên model phải đọc được mục -- kể cả `source_nodes`."""
    shown = TurnRecord(
        kind="outline",
        text="Dàn ý — 2 câu (bản 1)",
        tool_result={
            "version": 1,
            "for": "new",
            "first": 1,
            "items": [{"questions": 2, "knowledge": "Lũy thừa", "source_nodes": [3]}],
        },
    )
    state = {
        "request": _asked(
            TurnRecord(kind="teacher", text="soạn 2 câu"),
            shown,
            TurnRecord(kind="teacher", text="câu 2 đổi sang hình học"),
        ),
        "skills": (),
        "messages": [],
        "step": None,
    }

    messages = _compose(state)["messages"]

    replayed = next(one.text for one in messages if "Dàn ý — 2 câu" in one.text)
    assert '"source_nodes": [3]' in replayed
    assert type(messages[2]).__name__ == "AIMessage"


def test_a_superseded_outline_comes_back_as_its_text_only() -> None:
    shown = TurnRecord(
        kind="outline", text="Dàn ý — bản 1", tool_result={"version": 1, "superseded": True}
    )
    state = {
        "request": _asked(TurnRecord(kind="teacher", text="soạn"), shown),
        "skills": (),
        "messages": [],
        "step": None,
    }

    replayed = [one.text for one in _compose(state)["messages"] if "bản 1" in one.text]

    assert replayed == ["Dàn ý — bản 1"]


# ------------------------------------------------------------------ review đợt 4


@pytest.mark.asyncio
async def test_an_outline_broken_twice_ends_in_a_neutral_ask_not_the_mock(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Lùi về mock là cho giáo viên xem một dàn ý mock bịa giữa một lượt chat thật."""
    empty = _Proposal(kind="outline", text="Dàn ý.")
    monkeypatch.setattr(llm, "chat_models", lambda: (Scripted([empty, empty]),))

    step = await propose(_asked())

    assert (step.kind, step.text) == ("say", _UNCLEAR)


def _with_book(*history: TurnRecord) -> NextStepRequested:
    return NextStepRequested(
        request_id="r1",
        history=history,
        attached_document=AttachedDocument(document_id="book", filename="SGK.pdf"),
    )


def test_an_outline_before_reading_the_book_reads_it_first() -> None:
    outline = NextStepCompleted(
        request_id="r1",
        kind="outline",
        text="Dàn ý.",
        outline=(
            OutlineItem(questions=4, knowledge="A", approach="B", source_nodes=(8, 7)),
            OutlineItem(questions=2, knowledge="C", approach="D", source_nodes=(7,)),
        ),
    )

    step = _read_before_outline(outline, _with_book(TurnRecord(kind="teacher", text="soạn 6 câu")))

    assert (step.kind, step.tool_name) == ("call_tool", "read_section")
    assert step.tool_args == {"document_id": "book", "nodes": "7,8", "questions": "6", "part": "1"}


def test_an_outline_after_reading_the_book_stays_an_outline() -> None:
    outline = NextStepCompleted(
        request_id="r1",
        kind="outline",
        text="Dàn ý.",
        outline=(OutlineItem(questions=1, knowledge="A", approach="B", source_nodes=(7,)),),
    )
    read = TurnRecord(kind="tool_result", tool_name="read_section", tool_result={"found": True})

    step = _read_before_outline(outline, _with_book(TurnRecord(kind="teacher", text="x"), read))

    assert step.kind == "outline"


def test_a_bookless_outline_on_a_turn_that_names_a_book_opens_the_library(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(propose_module, "_opens_library", lambda request, chosen: True)
    outline = NextStepCompleted(
        request_id="r1",
        kind="outline",
        text="Dàn ý.",
        outline=(OutlineItem(questions=1, knowledge="A", approach="B"),),
    )

    step = _library_first(outline, _asked(), ("soan-de",))

    assert (step.kind, step.tool_name) == ("call_tool", "list_documents")


def test_only_an_outline_turn_carries_items_to_be() -> None:
    said = _Proposal(kind="say", text="Chào bạn.", outline=(_item(),))

    assert said.completed(request_id="r1", model_tokens=0).outline == ()


def test_the_core_prompt_carries_the_outline_rules() -> None:
    assert "outline: đề xuất DÀN Ý đề" in _CORE
    assert "chỉ nêu SAU KHI giáo viên đã đồng ý một dàn ý ở lượt trước" in _CORE
    assert "nêu lại outline ĐỦ mọi mục" in _CORE
    assert "for = new (đề mới), more" in _CORE
    assert "replace (thay một câu: một mục một câu, kèm question" in _CORE


@pytest.mark.parametrize("said", ["oke", "OK luôn", "được", "Đồng ý nhé", "chốt"])
def test_the_mock_hears_an_agreement(said: str) -> None:
    assert _AGREES.search(said) is not None


def _counted(*questions: int, purpose: str = "new") -> NextStepCompleted:
    return NextStepCompleted(
        request_id="r1",
        kind="outline",
        text="Dàn ý.",
        outline=tuple(OutlineItem(questions=n, knowledge="A", approach="B") for n in questions),
        tool_args={"for": purpose},
    )


@pytest.mark.parametrize(
    ("step", "known", "wrong"),
    [
        (_counted(2, 2, 2), "question_count=6 «6 câu»", False),
        (_counted(2, 2, 2, 2), "question_count=6 «6 câu»", True),
        (_counted(3), "topic_scope=x", False),
        (_counted(1, purpose="replace"), "question_count=5 «5 câu»", False),
        (_counted(1, 1, purpose="replace"), "", True),
        (_counted(2, purpose="replace"), "", True),
    ],
)
def test_an_outline_must_add_up_to_what_was_asked(
    step: NextStepCompleted, known: str, wrong: bool
) -> None:
    """Bench run-98 (`draft-outline`): *"6 câu"* ra 4 mục × 2 câu; *"thay câu 2"* ra cả đề."""
    assert bool(_miscounted(step, known)) is wrong


@pytest.mark.asyncio
async def test_a_miscounted_outline_is_asked_again(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    eight = _Proposal(
        known="question_count=6 «6 câu»",
        kind="outline",
        text="Dàn ý.",
        outline=(_item(questions=4), _item(questions=4)),
    )
    six = _Proposal(
        known="question_count=6 «6 câu»",
        kind="outline",
        text="Dàn ý.",
        outline=(_item(questions=3), _item(questions=3)),
    )
    model = Scripted([eight, six])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked())

    assert sum(item.questions for item in step.outline) == 6
    assert len(model.prompts) == 2
