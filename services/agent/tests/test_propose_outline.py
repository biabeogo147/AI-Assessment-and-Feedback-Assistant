"""Kriky nêu dàn ý đề (ADR-29, `draft-outline`): hình dạng model trả lời, và lịch sử nó đọc lại.

Không model thật nào được gọi. Ba loại khẳng định: một dàn ý đi ngược về BE đủ mục và đủ `for`;
dấu gạch chéo bị bộ giải mã JSON nuốt được trả lại ở cả ba trường chữ; và một lượt dàn ý trong lịch
sử tới model kèm các mục, để sửa dàn ý là nêu lại đủ mục.
"""

import pytest
from langchain_core.runnables import Runnable, RunnableLambda

from agent import llm
from agent.graphs.propose import read_order
from agent.graphs.propose.compose import compose
from agent.graphs.propose.graph import _UNCLEAR, propose
from agent.graphs.propose.outline import AGREES, approved_plan, brief_in, miscounted, right_purpose
from agent.graphs.propose.prompt import CORE
from agent.graphs.propose.proposal import _Argument, _OutlineItem, _Proposal, _Step
from agent.graphs.propose.read_order import library_first, read_before_outline
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

    messages = compose(state)["messages"]

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

    replayed = [one.text for one in compose(state)["messages"] if "bản 1" in one.text]

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
    # Câu cố định là thông báo của hệ thống, không phải lời Kriky (ADR-30, ngoại lệ 1).
    assert step.notice is True


def test_a_system_notice_in_history_reads_as_a_note_not_as_kriky_s_words() -> None:
    """Model đọc lại thông báo hệ thống như một ghi chú phía người dùng, không như lời mình đã nói
    (`kriky-writes-every-word`) -- nếu không, nó học giọng của câu cố định."""
    state = {
        "request": _asked(
            TurnRecord(kind="teacher", text="soạn đề"),
            TurnRecord(kind="notice", text="Kriky chưa trả lời được lúc này."),
        ),
        "skills": (),
        "messages": [],
        "step": None,
    }

    messages = compose(state)["messages"]

    noted = [one for one in messages if "Kriky chưa trả lời được lúc này." in one.text]
    assert [type(one).__name__ for one in noted] == ["HumanMessage"]
    assert "Ghi chú của hệ thống" in noted[0].text


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

    step = read_before_outline(outline, _with_book(TurnRecord(kind="teacher", text="soạn 6 câu")))

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

    step = read_before_outline(outline, _with_book(TurnRecord(kind="teacher", text="x"), read))

    assert step.kind == "outline"


def test_a_read_to_answer_a_question_does_not_count_as_reading_for_the_outline() -> None:
    """`ask-the-document`: hỏi về bài 7 rồi xin soạn đề bài 7 -- lượt soạn vẫn phải đọc phạm vi."""
    outline = NextStepCompleted(
        request_id="r1",
        kind="outline",
        text="Dàn ý.",
        outline=(OutlineItem(questions=2, knowledge="A", approach="B", source_nodes=(7,)),),
    )
    asked = TurnRecord(
        kind="tool_call", tool_name="read_section", tool_args={"document_id": "book", "nodes": "7"}
    )
    answered = TurnRecord(
        kind="tool_result",
        tool_name="read_section",
        tool_result={"found": True, "part": 1, "parts": 1, "more": False, "answering": True},
    )

    step = read_before_outline(
        outline,
        _with_book(
            TurnRecord(kind="teacher", text="bài 7 nói gì"),
            asked,
            answered,
            TurnRecord(kind="assistant", text="Bài 7 nói về …"),
            TurnRecord(kind="teacher", text="soạn 2 câu bài ấy"),
        ),
    )

    assert (step.kind, step.tool_name) == ("call_tool", "read_section")
    assert step.tool_args["questions"] == "2"


@pytest.mark.parametrize(
    ("since_question", "chosen", "asks_again"),
    [
        ((), ("hoi-tai-lieu",), True),
        ((("list_chapters", {}),), ("hoi-tai-lieu",), True),
        ((("get_chapter", {"node": "3"}),), ("hoi-tai-lieu",), False),
        ((("read_section", {"nodes": "4"}),), ("hoi-tai-lieu",), False),
        ((), ("tro-chuyen-chung",), False),
    ],
)
def test_an_answer_about_the_book_needs_a_look_inside_it(
    since_question, chosen, asks_again
) -> None:
    """`ask-the-document`, thử tay case 18: trả lời khi chưa mở mục nào thì hỏi model lại."""
    from agent.graphs.propose.read_order import answered_unread

    calls = tuple(
        TurnRecord(kind="tool_call", tool_name=name, tool_args=args)
        for name, args in since_question
    )
    request = _with_book(TurnRecord(kind="teacher", text="bài nào nói về số La Mã?"), *calls)
    said = NextStepCompleted(request_id="r1", kind="say", text="Sách không có.")

    assert answered_unread(said, request, chosen) is asks_again


def test_a_look_inside_from_an_earlier_question_does_not_count() -> None:
    """Mở mục ở câu hỏi trước không thay cho câu hỏi mới nhất (review pha 5, `ask-the-document`)."""
    from agent.graphs.propose.read_order import answered_unread

    request = _with_book(
        TurnRecord(kind="teacher", text="sách định nghĩa luỹ thừa thế nào?"),
        TurnRecord(kind="tool_call", tool_name="get_chapter", tool_args={"node": "0"}),
        TurnRecord(kind="assistant", text="Sách định nghĩa …"),
        TurnRecord(kind="teacher", text="bài nào nói về số La Mã?"),
    )
    said = NextStepCompleted(request_id="r1", kind="say", text="Ở mục 2.")

    assert answered_unread(said, request, ("hoi-tai-lieu",)) is True


def test_only_an_answer_on_a_turn_with_a_book_is_held_back() -> None:
    from agent.graphs.propose.read_order import answered_unread

    asked = TurnRecord(kind="teacher", text="bài nào nói về số La Mã?")
    said = NextStepCompleted(request_id="r1", kind="say", text="Ở mục 2.")
    question = NextStepCompleted(request_id="r1", kind="ask_clarify", text="Chương nào?")
    bookless = NextStepRequested(request_id="r1", history=(asked,))

    assert answered_unread(question, _with_book(asked), ("hoi-tai-lieu",)) is False
    assert answered_unread(said, bookless, ("hoi-tai-lieu",)) is False


def test_a_bookless_outline_on_a_turn_that_names_a_book_opens_the_library(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(read_order, "opens_library", lambda request, chosen: True)
    outline = NextStepCompleted(
        request_id="r1",
        kind="outline",
        text="Dàn ý.",
        outline=(OutlineItem(questions=1, knowledge="A", approach="B"),),
    )

    step = library_first(outline, _asked(), ("soan-de",))

    assert (step.kind, step.tool_name) == ("call_tool", "list_documents")


def test_only_an_outline_turn_carries_items_to_be() -> None:
    said = _Proposal(kind="say", text="Chào bạn.", outline=(_item(),))

    assert said.completed(request_id="r1", model_tokens=0).outline == ()


def test_the_core_prompt_carries_the_outline_rules() -> None:
    assert "outline: đề xuất DÀN Ý đề" in CORE
    assert "chỉ nêu SAU KHI giáo viên đã đồng ý một dàn ý ở lượt trước" in CORE
    assert "nêu lại outline ĐỦ mọi mục" in CORE
    assert "for = new (đề mới), more" in CORE
    assert "replace (thay một câu: một mục một câu, kèm question" in CORE


@pytest.mark.parametrize(
    "said", ["oke", "OK luôn", "được", "Đồng ý nhé", "chốt", "Được rồi", "ok, soạn đi", "vâng ạ."]
)
def test_the_mock_hears_an_agreement(said: str) -> None:
    assert AGREES.search(said) is not None


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

    assert AGREES.search(said) is None
    assert approved_plan(_ASKED_AGAIN, _agreed(kept, said)) is _ASKED_AGAIN


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
    silent = _asked(TurnRecord(kind="teacher", text="soạn đề chương 1"))
    assert bool(miscounted(step, known, silent)) is wrong


@pytest.mark.parametrize(
    ("said", "total", "wrong"),
    [
        # Backlog *Mất số câu sau một lượt hỏi lại*: 5 câu, hỏi lại, *"cả chương luôn"*, dàn ý 10.
        (("cho mình 5 câu chương 1", "cả chương luôn"), 10, True),
        (("cho mình 5 câu chương 1", "cả chương luôn"), 5, False),
        # Tin gộp của thẻ hỏi lại nhiều câu (ADR-32).
        (("soạn đề", "Khối: lớp 11 · Số câu: 5 câu · Phạm vi: cấp số cộng"), 5, False),
        # Lời nói sau thắng: giáo viên đổi ý.
        (("soạn 5 câu", "à thôi 8 câu nhé"), 8, False),
        # *"thay câu 3"* là số thứ tự, không phải số câu.
        (("soạn 4 câu", "thay câu 3 cho khó hơn"), 4, False),
        # Không ai nói số câu thì không đối chiếu.
        (("soạn đề chương 1",), 7, False),
    ],
)
def test_without_a_count_in_known_the_teacher_s_own_count_is_used(
    said: tuple[str, ...], total: int, wrong: bool
) -> None:
    step = _counted(total)
    asked = _asked(*(TurnRecord(kind="teacher", text=text) for text in said))
    assert bool(miscounted(step, "topic_scope=chương 1", asked)) is wrong


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
    # Lần hỏi lại nói số câu đúng (review code pha 5), theo đúng nguồn của nó: 6 là con số model
    # ghi trong `known`, không phải lời giáo viên (review code vòng 2).
    assert "question_count=6 trong known" in model.prompts[1]
    assert "question_count=6 trong known" not in model.prompts[0]


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

    step = right_purpose(_whole("A", "B", "C"), asked)

    assert step.tool_args == {"for": "replace", "question": "3"}
    assert [(item.knowledge, item.questions) for item in step.outline] == [("B", 1)]


def test_drafting_more_on_a_drafted_thread_is_for_more() -> None:
    asked = NextStepRequested(
        request_id="r1",
        history=(_DRAFTED, TurnRecord(kind="teacher", text="soạn thêm 3 câu nữa")),
    )

    assert right_purpose(_whole("A", "C"), asked).tool_args == {"for": "more"}


@pytest.mark.parametrize(
    "said", ["thay câu 3 bằng câu khác", "soạn thêm 3 câu", "soạn 5 câu về tỉ lệ thức"]
)
def test_without_a_draft_in_the_thread_the_purpose_stays(said: str) -> None:
    asked = NextStepRequested(request_id="r1", history=(TurnRecord(kind="teacher", text=said),))

    assert right_purpose(_whole("A", "C"), asked).tool_args == {"for": "new"}


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

    assert right_purpose(_whole("A", "C"), asked).tool_args == {"for": "more"}


def test_drafting_another_paper_on_a_drafted_thread_stays_new() -> None:
    """Review đợt 6: *"soạn thêm một đề mới"* là đề khác, không phải câu thêm vào đề cũ."""
    asked = NextStepRequested(
        request_id="r1",
        history=(_DRAFTED, TurnRecord(kind="teacher", text="soạn thêm một đề mới về hàm số 5 câu")),
    )

    assert right_purpose(_whole("A", "C"), asked).tool_args == {"for": "new"}


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

    step = read_before_outline(
        outline, _with_book(TurnRecord(kind="teacher", text="x"), call, read)
    )

    assert (step.kind, step.tool_name) == ("call_tool", "read_section")
    assert step.tool_args == {**asked, "part": "2"}


def test_an_outline_after_part_three_that_points_at_part_one_still_reads_on() -> None:
    """Thử tay 17/10 (case 04, plan `backlog-tier-1`): đọc phần 1–3/5, dàn ý trỏ nút của phần 1 --
    so với phần **cuối** thì không giao nhau và AGENT thôi bắt đọc tiếp."""
    outline = NextStepCompleted(
        request_id="r1",
        kind="outline",
        text="Dàn ý.",
        outline=(OutlineItem(questions=1, knowledge="A", approach="B", source_nodes=(1,)),),
    )
    turns = [TurnRecord(kind="teacher", text="x")]
    for part, nodes in ((1, [1, 2]), (2, [3, 4]), (3, [5, 6])):
        asked = {"document_id": "book", "nodes": "0", "questions": "5", "part": str(part)}
        turns += [
            TurnRecord(kind="tool_call", tool_name="read_section", tool_args=asked),
            TurnRecord(
                kind="tool_result",
                tool_name="read_section",
                tool_result={"found": True, "part": part, "parts": 5, "more": True, "nodes": nodes},
            ),
        ]

    step = read_before_outline(outline, _with_book(*turns))

    assert (step.kind, step.tool_name) == ("call_tool", "read_section")
    assert step.tool_args["part"] == "4"


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
        # Đọc trọn mục dàn ý trỏ tới, rồi ngó phần 1 của mục khác (review code pha 5).
        (
            TurnRecord(kind="teacher", text="x"),
            *_read_part(False, "0", [1, 2]),
            *_read_part(True, "7", [8, 9]),
        ),
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

    assert read_before_outline(outline, _with_book(*history)) is outline


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


@pytest.mark.asyncio
async def test_an_agreement_keeps_the_words_the_model_wrote_for_its_plan(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Review pha 5 (`kriky-writes-every-word`): lời mở đi qua `choose` -- test gọi thẳng
    `approved_plan` không thấy được đường chạy thật làm rơi mất nó."""
    kept = {"version": 1, "for": "new", "items": [{"questions": 2}], "brief": _BRIEF}
    planned = _Proposal(
        kind="plan",
        text="Mình soạn 2 câu theo dàn ý nhé.",
        steps=(_Step(tool_name="create_draft", title="Tạo đề trống"),),
    )
    monkeypatch.setattr(llm, "chat_models", lambda: (Scripted([planned]),))

    step = await propose(_agreed(kept))

    assert step.kind == "plan"
    assert step.text == "Mình soạn 2 câu theo dàn ý nhé."


def test_a_system_notice_between_the_outline_and_the_agreement_does_not_hide_it() -> None:
    """Review pha 5: model hỏng sau *"oke"*, thông báo dặn gửi lại -- gửi lại vẫn duyệt dàn ý."""
    kept = {"version": 1, "for": "new", "items": [{"questions": 2}], "brief": _BRIEF}
    request = NextStepRequested(
        request_id="r1",
        history=(
            TurnRecord(kind="teacher", text="soạn 2 câu"),
            TurnRecord(kind="outline", text="Dàn ý", tool_result=kept),
            TurnRecord(kind="teacher", text="oke"),
            TurnRecord(kind="notice", text="Kriky chưa trả lời được lúc này."),
            TurnRecord(kind="teacher", text="oke"),
        ),
    )

    step = approved_plan(_ASKED_AGAIN, request)

    assert [one.tool_name for one in step.steps] == ["create_draft", "start_drafting"]


_BRIEF = {"subject": "Toán", "grade": "7", "topic_scope": "tỉ lệ thức"}


def test_an_agreement_after_an_outline_becomes_its_plan_even_if_the_model_forgot() -> None:
    """Thử tay 15/10/2026 (`draft-outline`): sau *"oke"* model mất phạm vi và hỏi lại khối."""
    kept = {"version": 1, "for": "new", "items": [{"questions": 2}], "brief": _BRIEF}

    step = approved_plan(_ASKED_AGAIN, _agreed(kept))

    assert step.kind == "plan"
    # Model không nêu plan nên không có lời mở nào -- không câu cố định (ADR-30).
    assert step.text == ""
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

    step = approved_plan(opened, _agreed(kept))

    assert [one.tool_name for one in step.steps] == ["start_drafting"]
    # Lời mở là lời của chính model khi nó vừa nêu plan (ADR-30).
    assert step.text == "Mình mở đề nháp."


@pytest.mark.parametrize(
    ("purpose", "tool"), [("more", "start_drafting"), ("replace", "replace_question")]
)
def test_an_agreement_to_more_or_a_replacement_plans_that(purpose: str, tool: str) -> None:
    kept = {"version": 2, "for": purpose, "first": 3, "items": [{"questions": 1}]}

    step = approved_plan(_ASKED_AGAIN, _agreed(kept))

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
    assert approved_plan(_ASKED_AGAIN, _agreed(kept, said)) is _ASKED_AGAIN


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

    assert [one.tool_name for one in approved_plan(_ASKED_AGAIN, asked).steps] == ["start_drafting"]


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


@pytest.mark.asyncio
async def test_an_unreadable_reply_to_an_agreement_still_plans_without_asking_again(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Review plan `tier-1` (27/10/2026): đầu ra không parse được sau *"oke"* không tốn một lần hỏi
    lại -- plan dựng từ dàn ý, như mọi lần hỏi lại khác."""
    from types import SimpleNamespace

    from langchain_core.runnables import RunnableLambda

    calls: list[int] = []

    class Unreadable:
        def with_structured_output(self, schema: object, **kwargs: object):
            def answer(messages: object) -> dict:
                calls.append(1)
                raw = SimpleNamespace(usage_metadata=None, tool_calls=[])
                return {"parsed": None, "raw": raw, "parsing_error": "hỏng"}

            return RunnableLambda(answer)

    monkeypatch.setattr(llm, "chat_models", lambda: (Unreadable(),))
    kept = {"version": 2, "for": "more", "first": 6, "items": [{"questions": 2}]}

    step = await propose(_agreed(kept))

    assert step.kind == "plan" and [one.tool_name for one in step.steps] == ["start_drafting"]
    assert len(calls) == 1


def test_the_brief_keeps_a_scope_with_a_comma_in_it() -> None:
    """Review đợt 6: *"tỉ lệ thuận, tỉ lệ nghịch"* là một phạm vi, không phải hai mục."""
    known = "topic_scope=tỉ lệ thuận, tỉ lệ nghịch «hai bài»; subject=Toán; grade=7"

    assert brief_in(known) == {
        "topic_scope": "tỉ lệ thuận, tỉ lệ nghịch",
        "subject": "Toán",
        "grade": "7",
    }


def test_the_brief_is_read_from_what_the_model_knew() -> None:
    known = (
        "topic_scope=tỉ lệ thức «tỉ lệ thức»; subject=Toán «Toán»; grade=? «?»; question_count=5"
    )

    assert brief_in(known) == {"topic_scope": "tỉ lệ thức", "subject": "Toán"}


@pytest.mark.parametrize(
    ("said", "held"),
    [
        ("câu 2 đổi sang tự luận nhé", True),
        ("oke nhưng câu 3 khó hơn", True),
        ("thêm một câu hình học", True),
        ("oke", False),
        ("được rồi, soạn đi nhé", False),
        # Lời phủ định không phải lời xin sửa (review code pha 5).
        ("không cần sửa gì, soạn đi", False),
        ("ok không đổi gì nữa, soạn luôn nhé", False),
        ("không cần sửa, nhưng câu 3 khó hơn nhé", True),
        # Review code vòng 2: cả hai chiều.
        ("không cần thay đổi gì, soạn đi", False),
        ("không có gì cần sửa, soạn đi", False),
        ("không cần thêm câu hình học", True),
        # Tiểu từ cuối câu (review code vòng 3).
        ("ok không cần sửa nhé", False),
        ("không cần sửa đâu, soạn đi", False),
        ("oke ko cần sửa ạ", False),
        # Tiểu từ giữa câu thì không phải cuối ý (review code vòng 4).
        ("sao không đổi luôn câu 3 sang tự luận?", True),
        ("ok không cần sửa luôn", False),
        # Tiểu từ cuối câu thật không cần dấu câu theo sau; *"sửa thêm"* là một lời (vòng 5).
        ("không cần sửa nhé em", False),
        ("không cần sửa đâu soạn đi", False),
        ("không cần sửa nhé :)", False),
        ("không cần sửa thêm, soạn luôn", False),
        ("không cần sửa nhé nhưng câu 3 khó hơn", True),
        # *luôn* trước một tiểu từ cuối câu; *nha* không ăn đầu chữ *nhanh* (vòng 6).
        ("không cần sửa luôn nhé", False),
        ("khỏi sửa luôn nha", False),
        ("sao không sửa nhanh câu 3", True),
    ],
)
def test_a_drafting_plan_right_after_a_revision_is_held_back(said: str, held: bool) -> None:
    """Plan `backlog-tier-1`, pha 3: *Plan soạn … sau một lời xin sửa dàn ý vẫn qua cổng*. Cổng BE
    chỉ đòi một dàn ý ở lượt ngay trước, nên plan soạn theo dàn ý cũ đi lọt."""
    from agent.graphs.propose.plan_checks import drafts_over_a_revision

    plan = NextStepCompleted(
        request_id="r1",
        kind="plan",
        text="Mình soạn.",
        steps=(
            PlanStep(
                tool_name="start_drafting",
                args={"assessment_id": "p1", "question_count": "2"},
                title="Soạn câu hỏi",
            ),
        ),
    )
    kept = {"version": 1, "for": "new", "items": [{"questions": 2}], "brief": _BRIEF}

    assert drafts_over_a_revision(plan, _agreed(kept, said)) is held


@pytest.mark.parametrize(
    ("said", "total", "wrong"),
    [
        # Số sau *lớp* là khối, không phải số câu.
        (("ra đề cho lớp 7 câu hỏi về tỉ lệ thức nhé",), 5, False),
        # Sau một dàn ý, *"thêm 2 câu"* sửa dàn ý ấy: không đối chiếu với 2.
        (("soạn 5 câu", "@outline", "thêm 2 câu hình học"), 7, False),
        (("soạn 5 câu", "@outline", "bớt 1 câu"), 4, False),
        # Một lời sửa khác sau *"thêm 2 câu"*: tổng vẫn là dàn ý đã sửa (review code vòng 3).
        (
            ("soạn 5 câu", "@outline", "thêm 2 câu hình học", "@outline", "câu 3 khó hơn nhé"),
            7,
            False,
        ),
        # Giáo viên nói lại tổng sau lời *thêm*: lời sau thắng.
        (("soạn 5 câu", "@outline", "thêm 2 câu", "@outline", "à thôi 6 câu thôi"), 7, True),
        # Không có dàn ý trước thì *"soạn thêm 3 câu"* vẫn là số câu xin.
        (("soạn thêm 3 câu",), 5, True),
    ],
)
def test_a_count_after_a_grade_or_a_revision_is_not_the_total(
    said: tuple[str, ...], total: int, wrong: bool
) -> None:
    """Review code pha 5 (plan `backlog-tier-1`): `_count_said` bắt nhầm số câu."""
    turns = tuple(
        TurnRecord(kind="outline", text="Dàn ý.")
        if text == "@outline"
        else TurnRecord(kind="teacher", text=text)
        for text in said
    )
    assert bool(miscounted(_counted(total), "topic_scope=chương 1", _asked(*turns))) is wrong


def test_a_count_in_known_is_set_aside_after_the_teacher_adds_questions() -> None:
    """Review code vòng 2 (plan `backlog-tier-1`): *"thêm 2 câu"* sau dàn ý 5 câu, model ra 7 câu mà
    `known` còn ghi 5 -- đối chiếu với `known` là kéo dàn ý về 5 và mất lời sửa của giáo viên."""
    asked = _asked(
        TurnRecord(kind="teacher", text="soạn 5 câu"),
        TurnRecord(kind="outline", text="Dàn ý."),
        TurnRecord(kind="teacher", text="thêm 2 câu hình học"),
    )
    assert miscounted(_counted(7), "question_count=5 «5 câu»", asked) is None


def test_the_same_scope_spelled_differently_is_still_the_same_scope() -> None:
    """Review code vòng 2 (plan `backlog-tier-1`): phần 2 gửi `nodes="4, 3"` trong khi phần 1 là
    `"3,4"` -- vẫn một phạm vi, nên nút đọc ở phần 1 vẫn tính và AGENT bắt đọc phần 4."""
    outline = NextStepCompleted(
        request_id="r1",
        kind="outline",
        text="Dàn ý.",
        outline=(OutlineItem(questions=1, knowledge="A", approach="B", source_nodes=(1,)),),
    )
    turns = [TurnRecord(kind="teacher", text="x")]
    for part, spelled, nodes in ((1, "3,4", [1, 2]), (2, "4, 3", [5, 6]), (3, " 3,4 ", [7, 8])):
        asked = {"document_id": "book", "nodes": spelled, "questions": "5", "part": str(part)}
        turns += [
            TurnRecord(kind="tool_call", tool_name="read_section", tool_args=asked),
            TurnRecord(
                kind="tool_result",
                tool_name="read_section",
                tool_result={"found": True, "part": part, "parts": 5, "more": True, "nodes": nodes},
            ),
        ]

    step = read_before_outline(outline, _with_book(*turns))

    assert (step.kind, step.tool_name) == ("call_tool", "read_section")
    assert step.tool_args["part"] == "4"


# --- chữ gõ từ bàn phím NFD (macOS, iOS): plan `muc-1-2-loop-1`, 21/10/2026 ----------------------


def _nfd(text: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFD", text)


def test_a_count_typed_in_nfd_is_still_the_count_asked_for() -> None:
    asked = _asked(TurnRecord(kind="teacher", text=_nfd("soạn 5 câu chương 1")))
    assert miscounted(_counted(7), "topic_scope=chương 1", asked)


def test_an_added_count_typed_in_nfd_still_revises_the_outline() -> None:
    asked = _asked(
        TurnRecord(kind="teacher", text="soạn 5 câu"),
        TurnRecord(kind="outline", text="Dàn ý."),
        TurnRecord(kind="teacher", text=_nfd("thêm 2 câu hình học")),
    )
    assert not miscounted(_counted(7), "topic_scope=chương 1", asked)


def test_a_revision_typed_in_nfd_still_holds_the_drafting_plan_back() -> None:
    from agent.graphs.propose.plan_checks import drafts_over_a_revision

    plan = NextStepCompleted(
        request_id="r1",
        kind="plan",
        text="Mình soạn.",
        steps=(
            PlanStep(
                tool_name="start_drafting",
                args={"assessment_id": "p1", "question_count": "2"},
                title="Soạn câu hỏi",
            ),
        ),
    )
    kept = {"version": 1, "for": "new", "items": [{"questions": 2}], "brief": _BRIEF}
    assert drafts_over_a_revision(plan, _agreed(kept, _nfd("đổi câu 2 sang tự luận")))


@pytest.mark.asyncio
async def test_an_agreement_gives_back_the_backslashes_of_the_plan_s_opening(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Lời mở của plan đã đồng ý đi qua bước sửa chữ như mọi lời khác: `\frac` bị bộ giải mã JSON
    nuốt thành form-feed thì được trả lại (backlog, *Lời mở của plan đã đồng ý bỏ qua bước sửa
    chữ*)."""
    kept = {"version": 1, "for": "new", "items": [{"questions": 2}], "brief": _BRIEF}
    planned = _Proposal(
        kind="plan",
        text=_nfd("Mình soạn câu về $") + chr(12) + "rac{a}{b}$ nhé.",
        steps=(_Step(tool_name="create_draft", title="Tạo đề trống"),),
    )
    monkeypatch.setattr(llm, "chat_models", lambda: (Scripted([planned]),))

    step = await propose(_agreed(kept))

    assert step.kind == "plan"
    assert step.text == "Mình soạn câu về $" + chr(92) + "frac{a}{b}$ nhé."


def _part_one_read(nodes: object) -> tuple[NextStepCompleted, TurnRecord, TurnRecord]:
    outline = NextStepCompleted(
        request_id="r1",
        kind="outline",
        text="Dàn ý.",
        outline=(OutlineItem(questions=1, knowledge="A", approach="B", source_nodes=(1,)),),
    )
    asked = {"document_id": "book", "nodes": "0", "questions": "5", "part": "1"}
    call = TurnRecord(kind="tool_call", tool_name="read_section", tool_args=asked)
    read = TurnRecord(
        kind="tool_result",
        tool_name="read_section",
        tool_result={"found": True, "part": 1, "parts": 5, "more": True, "nodes": nodes},
    )
    return outline, call, read


def test_a_read_with_no_result_does_not_shift_the_pairs_after_it() -> None:
    """Backlog (chia `propose.py`, 20/10/2026): ghép lời gọi với kết quả theo chỉ số thì một lời gọi
    không có kết quả làm lệch mọi cặp sau, và phần đã đọc thành phần của lời gọi khác."""
    outline, call, read = _part_one_read([1, 2])
    elsewhere = TurnRecord(
        kind="tool_call",
        tool_name="read_section",
        tool_args={"document_id": "book", "nodes": "9", "questions": "5"},
    )
    step = read_before_outline(
        outline, _with_book(TurnRecord(kind="teacher", text="x"), elsewhere, call, read)
    )
    assert (step.kind, step.tool_name) == ("call_tool", "read_section")
    assert step.tool_args["part"] == "2"


def test_a_node_that_is_not_a_number_does_not_break_the_turn() -> None:
    """`int(node)` trên một node lạ từng ném `ValueError`, và lượt gãy thành *model hỏng*."""
    outline, call, read = _part_one_read(["1", "mục 2"])
    step = read_before_outline(
        outline, _with_book(TurnRecord(kind="teacher", text="x"), call, read)
    )
    assert step.tool_args["part"] == "2"


_KNOWN_ALL = "subject=Toán; grade=12; topic_scope=chương Hàm số; question_count=5 «5 câu»"


@pytest.mark.asyncio
async def test_asking_again_with_every_field_known_is_asked_once_more(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Tier 2 câu 33 = A (21/10/2026): thử tay V6, `known` đủ bốn mục mà model vẫn hỏi lại, không
    câu hỏi nào, giáo viên kẹt. AGENT hỏi model lại một lần, kèm lời nhắc nêu dàn ý."""
    empty = _Proposal(
        kind="ask_clarify", text="Bạn cho mình biết thêm một điều nhé:", known=_KNOWN_ALL
    )
    outline = _Proposal(
        kind="outline",
        text="Mình đề xuất dàn ý.",
        known=_KNOWN_ALL,
        outline=(_item(questions=5),),
        tool_args=(_Argument(param="for", value="new"),),
    )
    scripted = Scripted([empty, outline])
    monkeypatch.setattr(llm, "chat_models", lambda: (scripted,))

    step = await propose(_asked(TurnRecord(kind="teacher", text="soạn 5 câu chương Hàm số lớp 12")))

    assert step.kind == "outline"
    assert "nêu dàn ý" in scripted.prompts[1]


@pytest.mark.asyncio
async def test_asking_again_with_a_field_missing_stays_a_question(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    known = "subject=Toán; grade=?; topic_scope=chương Hàm số; question_count=5 «5 câu»"
    ask = _Proposal(
        kind="ask_clarify",
        text="Đề này cho khối nào?",
        known=known,
        choices=("Khối 10", "Khối 11", "Khối 12"),
    )
    monkeypatch.setattr(llm, "chat_models", lambda: (Scripted([ask]),))

    step = await propose(_asked(TurnRecord(kind="teacher", text="soạn 5 câu chương Hàm số")))

    assert step.kind == "ask_clarify"


@pytest.mark.asyncio
async def test_asking_which_section_with_every_field_known_stays_a_question(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Review vòng 1 (21/10/2026): phạm vi khớp nhiều mục thì hỏi lại kèm nút là hợp lệ dù `known`
    đủ bốn mục; chỉ lời hỏi lại không câu hỏi, không nút nào mới bị hỏi lại."""
    ask = _Proposal(
        kind="ask_clarify",
        text="Phạm vi này khớp ba mục, bạn chọn mục nào?",
        known=_KNOWN_ALL,
        choices=("1. Đồng biến", "2. Cực trị", "3. Giá trị lớn nhất"),
    )
    scripted = Scripted([ask])
    monkeypatch.setattr(llm, "chat_models", lambda: (scripted,))

    step = await propose(_asked(TurnRecord(kind="teacher", text="soạn 5 câu chương Hàm số lớp 12")))

    assert step.kind == "ask_clarify"
    assert len(scripted.prompts) == 1
