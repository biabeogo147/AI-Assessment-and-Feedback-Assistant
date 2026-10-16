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
    _AGREES,
    _CORE,
    _UNCLEAR,
    _approved_plan,
    _Argument,
    _brief_in,
    _compose,
    _library_first,
    _miscounted,
    _OutlineItem,
    _Proposal,
    _read_before_outline,
    _right_purpose,
    propose,
)
from contracts import (
    AttachedDocument,
    NextStepCompleted,
    NextStepRequested,
    OutlineItem,
    PlanStep,
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
        # Thử tay 15/10/2026: `outline` là kind, model lại gọi nó như một tool.
        _Proposal(kind="call_tool", tool_name="outline"),
        # ADR-30: lời trình bày dàn ý là lời Kriky viết, không còn khuôn BE dựng thay -- lời rỗng
        # thì hỏi lại ngay ở AGENT (review pha 4, `kriky-writes-every-word`).
        _Proposal(kind="outline", text="  ", outline=(_item(),)),
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

    # Lời Kriky về đúng là lời của nó; các mục đi riêng, như một ghi chú của hệ thống phía người
    # dùng -- không nối vào lời model để nó chép lại (review pha 4, `kriky-writes-every-word`).
    at = next(index for index, one in enumerate(messages) if one.text == "Dàn ý — 2 câu (bản 1)")
    assert type(messages[at]).__name__ == "AIMessage"
    assert type(messages[at + 1]).__name__ == "HumanMessage"
    assert '"source_nodes": [3]' in messages[at + 1].text


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


@pytest.mark.parametrize(
    "said", ["oke", "OK luôn", "được", "Đồng ý nhé", "chốt", "Được rồi", "ok, soạn đi", "vâng ạ."]
)
def test_the_mock_hears_an_agreement(said: str) -> None:
    assert _AGREES.search(said) is not None


@pytest.mark.parametrize(
    "said",
    [
        "ok nhưng câu 2 đổi sang tự luận",
        "được không?",
        "chốt câu 3 đổi sang hình học",
        "OK để mình xem lại đã",
        "đồng ý, nhưng chỉ 1 câu thôi",
        "duyệt lại câu 2 giúp mình",
        "ừ mà khoan",
        "Được rồi, nhưng đổi khối 7",
        "vâng nhưng đừng soạn vội",
    ],
)
def test_an_agreement_with_a_change_is_not_an_agreement(said: str) -> None:
    """Review đợt 6: khớp đầu câu thì những câu này soạn theo dàn ý giáo viên vừa xin đổi."""
    kept = {"version": 1, "for": "more", "items": [{"questions": 1}]}

    assert _AGREES.search(said) is None
    assert _approved_plan(_ASKED_AGAIN, _agreed(kept, said)) is _ASKED_AGAIN


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


_DRAFTED = TurnRecord(
    kind="tool_result",
    tool_name="start_drafting",
    tool_result={"started": True, "assessment_id": "p1"},
)


def _whole(*knowledge: str) -> NextStepCompleted:
    return NextStepCompleted(
        request_id="r1",
        kind="outline",
        text="Dàn ý.",
        outline=tuple(
            OutlineItem(questions=2 if one == "B" else 1, knowledge=one, approach="x")
            for one in knowledge
        ),
        tool_args={"for": "new"},
    )


def test_replacing_question_three_takes_the_item_holding_question_three() -> None:
    """Thử tay H4 (`draft-outline`): *"thay câu 3"* ra cả dàn ý `for=new`; câu 3 nằm trong mục B."""
    asked = NextStepRequested(
        request_id="r1",
        history=(_DRAFTED, TurnRecord(kind="teacher", text="thay câu 3 bằng một câu khó hơn")),
    )

    step = _right_purpose(_whole("A", "B", "C"), asked)

    assert step.tool_args == {"for": "replace", "question": "3"}
    assert [(item.knowledge, item.questions) for item in step.outline] == [("B", 1)]


def test_drafting_more_on_a_drafted_thread_is_for_more() -> None:
    asked = NextStepRequested(
        request_id="r1",
        history=(_DRAFTED, TurnRecord(kind="teacher", text="soạn thêm 3 câu nữa")),
    )

    assert _right_purpose(_whole("A", "C"), asked).tool_args == {"for": "more"}


@pytest.mark.parametrize(
    "said", ["thay câu 3 bằng câu khác", "soạn thêm 3 câu", "soạn 5 câu về tỉ lệ thức"]
)
def test_without_a_draft_in_the_thread_the_purpose_stays(said: str) -> None:
    asked = NextStepRequested(request_id="r1", history=(TurnRecord(kind="teacher", text=said),))

    assert _right_purpose(_whole("A", "C"), asked).tool_args == {"for": "new"}


def test_drafting_more_is_heard_across_the_questions_kriky_asked_back() -> None:
    """Thử tay sau review đợt 6: *"soạn thêm 1 câu"*, rồi hai lần bấm lựa chọn -- câu cuối là tên
    một bài, việc vẫn là soạn thêm."""
    asked = NextStepRequested(
        request_id="r1",
        history=(
            _DRAFTED,
            TurnRecord(kind="teacher", text="soạn thêm 1 câu về cách ghi số La Mã"),
            TurnRecord(kind="assistant", text="Khía cạnh nào?"),
            TurnRecord(kind="teacher", text="CÁCH GHI SỐ TỰ NHIÊN (tr. 9–13)"),
        ),
    )

    assert _right_purpose(_whole("A", "C"), asked).tool_args == {"for": "more"}


def test_drafting_another_paper_on_a_drafted_thread_stays_new() -> None:
    """Review đợt 6: *"soạn thêm một đề mới"* là đề khác, không phải câu thêm vào đề cũ."""
    asked = NextStepRequested(
        request_id="r1",
        history=(_DRAFTED, TurnRecord(kind="teacher", text="soạn thêm một đề mới về hàm số 5 câu")),
    )

    assert _right_purpose(_whole("A", "C"), asked).tool_args == {"for": "new"}


def test_an_outline_after_part_one_of_five_reads_part_two_first() -> None:
    """Thử tay 15/10/2026 (`draft-outline`): đọc phần 1/5 rồi viết dàn ý -- dàn ý chỉ phủ đầu
    chương."""
    outline = NextStepCompleted(
        request_id="r1",
        kind="outline",
        text="Dàn ý.",
        outline=(OutlineItem(questions=1, knowledge="A", approach="B", source_nodes=(1,)),),
    )
    asked = {"document_id": "book", "nodes": "0", "questions": "5", "part": "1"}
    read = TurnRecord(
        kind="tool_result",
        tool_name="read_section",
        tool_result={"found": True, "part": 1, "parts": 5, "more": True, "nodes": [1, 2]},
    )
    call = TurnRecord(kind="tool_call", tool_name="read_section", tool_args=asked)

    step = _read_before_outline(
        outline, _with_book(TurnRecord(kind="teacher", text="x"), call, read)
    )

    assert (step.kind, step.tool_name) == ("call_tool", "read_section")
    assert step.tool_args == {**asked, "part": "2"}


def _read_part(more: bool, nodes: str, read: list[int]) -> tuple[TurnRecord, TurnRecord]:
    asked = {"document_id": "book", "nodes": nodes, "questions": "5", "part": "1"}
    return (
        TurnRecord(kind="tool_call", tool_name="read_section", tool_args=asked),
        TurnRecord(
            kind="tool_result",
            tool_name="read_section",
            tool_result={"found": True, "part": 1, "parts": 5, "more": more, "nodes": read},
        ),
    )


@pytest.mark.parametrize(
    "history",
    [
        # Đọc hết rồi.
        (TurnRecord(kind="teacher", text="x"), *_read_part(False, "0", [1, 2])),
        # Ngó một mục khác dàn ý không trỏ tới (review đợt 6).
        (TurnRecord(kind="teacher", text="x"), *_read_part(True, "7", [8, 9])),
        # Lần đọc của lượt trước, rồi giáo viên đã gõ câu mới (review đợt 6).
        (
            TurnRecord(kind="teacher", text="x"),
            *_read_part(True, "0", [1, 2]),
            TurnRecord(kind="outline", text="Dàn ý."),
            TurnRecord(kind="teacher", text="câu 1 đổi"),
        ),
    ],
)
def test_an_outline_is_not_held_back_for_a_read_it_does_not_need(
    history: tuple[TurnRecord, ...],
) -> None:
    outline = NextStepCompleted(
        request_id="r1",
        kind="outline",
        text="Dàn ý.",
        outline=(OutlineItem(questions=1, knowledge="A", approach="B", source_nodes=(1,)),),
    )

    assert _read_before_outline(outline, _with_book(*history)) is outline


def _agreed(kept: dict, said: str = "oke") -> NextStepRequested:
    return NextStepRequested(
        request_id="r1",
        history=(
            TurnRecord(kind="teacher", text="soạn 2 câu"),
            TurnRecord(kind="outline", text="Dàn ý", tool_result=kept),
            TurnRecord(kind="teacher", text=said),
        ),
    )


_ASKED_AGAIN = NextStepCompleted(request_id="r1", kind="ask_clarify", text="Khối mấy?")
_BRIEF = {"subject": "Toán", "grade": "7", "topic_scope": "tỉ lệ thức"}


def test_an_agreement_after_an_outline_becomes_its_plan_even_if_the_model_forgot() -> None:
    """Thử tay 15/10/2026 (`draft-outline`): sau *"oke"* model mất phạm vi và hỏi lại khối."""
    kept = {"version": 1, "for": "new", "items": [{"questions": 2}], "brief": _BRIEF}

    step = _approved_plan(_ASKED_AGAIN, _agreed(kept))

    assert step.kind == "plan"
    assert [one.tool_name for one in step.steps] == ["create_draft", "start_drafting"]
    assert step.steps[0].args == {**_BRIEF, "document_id": "", "nodes": ""}
    assert step.steps[1].args == {"assessment_id": "{1.assessment_id}", "question_count": ""}


def test_an_agreement_to_more_wins_over_a_plan_that_opens_a_new_draft() -> None:
    """Thử tay 15/10/2026: *"oke"* cho dàn ý soạn thêm ra plan `create_draft` khối 6."""
    kept = {"version": 7, "for": "more", "first": 8, "items": [{"questions": 2}]}
    opened = NextStepCompleted(
        request_id="r1",
        kind="plan",
        text="Mình mở đề nháp.",
        steps=(
            PlanStep(
                tool_name="create_draft",
                args={"subject": "Toán", "grade": "6", "topic_scope": "tỉ lệ nghịch"},
                title="Tạo đề trống",
            ),
        ),
    )

    step = _approved_plan(opened, _agreed(kept))

    assert [one.tool_name for one in step.steps] == ["start_drafting"]


@pytest.mark.parametrize(
    ("purpose", "tool"), [("more", "start_drafting"), ("replace", "replace_question")]
)
def test_an_agreement_to_more_or_a_replacement_plans_that(purpose: str, tool: str) -> None:
    kept = {"version": 2, "for": purpose, "first": 3, "items": [{"questions": 1}]}

    step = _approved_plan(_ASKED_AGAIN, _agreed(kept))

    assert [one.tool_name for one in step.steps] == [tool]


@pytest.mark.parametrize(
    ("kept", "said"),
    [
        ({"version": 1, "for": "new", "items": [{"questions": 2}], "brief": _BRIEF}, "câu 2 đổi"),
        ({"version": 1, "for": "new", "items": [{"questions": 2}]}, "oke"),
        ({"version": 1, "superseded": True}, "oke"),
    ],
)
def test_no_agreement_or_no_brief_leaves_the_model_answer(kept: dict, said: str) -> None:
    assert _approved_plan(_ASKED_AGAIN, _agreed(kept, said)) is _ASKED_AGAIN


def test_an_agreement_retyped_after_a_turn_that_never_answered_still_plans() -> None:
    """Review đợt 6: lượt *"oke"* hỏng trước khi đáp để lại một câu mồ côi; gõ lại *"oke"* vẫn
    duyệt."""
    kept = {"version": 2, "for": "more", "first": 6, "items": [{"questions": 2}]}
    asked = NextStepRequested(
        request_id="r1",
        history=(
            TurnRecord(kind="teacher", text="soạn thêm 2 câu"),
            TurnRecord(kind="outline", text="Dàn ý", tool_result=kept),
            TurnRecord(kind="teacher", text="oke"),
            TurnRecord(kind="teacher", text="oke"),
        ),
    )

    assert [one.tool_name for one in _approved_plan(_ASKED_AGAIN, asked).steps] == [
        "start_drafting"
    ]


@pytest.mark.asyncio
async def test_a_broken_reply_to_an_agreement_still_plans(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Review đợt 6: sau *"oke"* model trả lời rỗng hai lần -- trước đây thành câu trung tính, lời
    duyệt mất."""
    model = Scripted([_Proposal(kind="say", text=""), _Proposal(kind="say", text="")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))
    kept = {"version": 2, "for": "more", "first": 6, "items": [{"questions": 2}]}

    step = await propose(_agreed(kept))

    assert step.kind == "plan" and [one.tool_name for one in step.steps] == ["start_drafting"]


def test_the_brief_keeps_a_scope_with_a_comma_in_it() -> None:
    """Review đợt 6: *"tỉ lệ thuận, tỉ lệ nghịch"* là một phạm vi, không phải hai mục."""
    known = "topic_scope=tỉ lệ thuận, tỉ lệ nghịch «hai bài»; subject=Toán; grade=7"

    assert _brief_in(known) == {
        "topic_scope": "tỉ lệ thuận, tỉ lệ nghịch",
        "subject": "Toán",
        "grade": "7",
    }


def test_the_brief_is_read_from_what_the_model_knew() -> None:
    known = (
        "topic_scope=tỉ lệ thức «tỉ lệ thức»; subject=Toán «Toán»; grade=? «?»; question_count=5"
    )

    assert _brief_in(known) == {"topic_scope": "tỉ lệ thức", "subject": "Toán"}
