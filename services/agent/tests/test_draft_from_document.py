"""AGENT dùng tài liệu (`draft-from-document`): job soạn câu nhận đúng mục của nó, Kriky biết tài
liệu đính kèm.

Không model nào được gọi: các khẳng định ở đây là về **chữ đưa vào prompt** -- brief của một job, và
system prompt của pha lên plan.
"""

import unicodedata

import pytest
from langchain_core.runnables import RunnableLambda

from agent import llm
from agent.graphs.authoring import draft_brief
from agent.graphs.propose import propose
from agent.graphs.propose.compose import _describe_tool, compose
from agent.graphs.propose.prompt import BOOK_PROCEDURE, LIBRARY
from agent.graphs.propose.proposal import _Proposal
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


def test_a_question_on_an_outline_item_is_told_exactly_that_item() -> None:
    """ADR-29: job nhận đúng mục dàn ý giáo viên đã duyệt -- kiến thức, công thức, cách làm."""
    brief = draft_brief(
        _asked(
            item_knowledge="Lũy thừa với số mũ tự nhiên",
            item_formulas=("$a^m \\cdot a^n = a^{m+n}$",),
            item_approach="Rút gọn rồi so sánh",
            item_part=2,
            item_parts=3,
            other_items=("Thứ tự thực hiện phép tính",),
        )
    )

    assert "Kiến thức câu này kiểm: Lũy thừa với số mũ tự nhiên" in brief
    assert "Công thức sẽ dùng: $a^m \\cdot a^n = a^{m+n}$" in brief
    assert "Cách làm bài: Rút gọn rồi so sánh" in brief
    assert "Mục này có 3 câu; đây là câu thứ 2." in brief
    assert "· Thứ tự thực hiện phép tính" in brief
    assert "giáo viên đã duyệt" in brief
    # Lời nhắc chung *"khía cạnh khác nhau"* nhường chỗ cho mục cụ thể.
    assert "khía cạnh khác nhau" not in brief


def test_a_one_question_item_is_not_told_about_parts() -> None:
    brief = draft_brief(_asked(item_knowledge="Tập hợp", item_approach="Chọn tập đúng"))

    assert "đây là câu thứ" not in brief
    assert "Công thức sẽ dùng" not in brief


def test_raw_document_text_never_reaches_the_brief_any_more() -> None:
    """Một payload cũ còn chở `focus_text` thì chữ ấy không vào prompt (ADR-29)."""
    old = _asked().model_dump() | {"focus_title": "Bài 1", "focus_text": "chữ OCR f8h4%2 rác"}
    brief = draft_brief(DraftQuestionRequested.model_validate(old))

    assert "f8h4%2" not in brief


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
    assert BOOK_PROCEDURE in prompts[0]


_TEACHER = TurnRecord(kind="teacher", text="soạn 10 câu")
_READ = (
    TurnRecord(kind="tool_call", tool_name="list_documents"),
    TurnRecord(kind="tool_result", tool_name="list_documents", tool_result={"candidates": []}),
)
_PLANNED = TurnRecord(kind="plan", tool_result={"steps": ["Tạo đề trống"], "total": 1})
_PROCESSING = AttachedDocument(document_id="new", filename="Mới.pdf", state="processing")
_READY = AttachedDocument(document_id="book", filename="Sách.pdf")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("attached", "history", "told"),
    [
        # Không chip, chưa mở thư viện: không chữ nào về thủ tục sách (`unbiased-model-text`,
        # run-13).
        (None, (_TEACHER,), False),
        (_READY, (_TEACHER,), True),
        # Chip còn đang xử lý: chưa đọc được mục lục -- kể cả khi đoạn chat từng mở thư viện, để
        # prompt không vừa bảo *đừng soạn* vừa bảo *đọc mục lục* (review T2, `unbiased-model-text`).
        (_PROCESSING, (_TEACHER,), False),
        (_PROCESSING, (*_READ, _TEACHER), False),
        # Model vừa mở thư viện, hay lượt trước mở rồi hỏi lại chương nào: việc chọn sách còn dở.
        (None, (_TEACHER, *_READ), True),
        (None, (*_READ, TurnRecord(kind="assistant", text="chương nào?"), _TEACHER), True),
        # Một plan đã nêu sau lần đọc: việc chọn sách xong rồi. BE vẫn để `list_chapters` trong
        # catalog cả đoạn chat, nên catalog **không** được là thứ quyết định (review T2,
        # `unbiased-model-text`).
        (None, (*_READ, _PLANNED, _TEACHER), False),
    ],
)
async def test_the_book_procedure_comes_only_with_a_book(
    monkeypatch, attached, history, told
) -> None:
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
            history=history,
            attached_document=attached,
            catalog=(ToolSpec(name="list_chapters", description="tra cứu", arguments={}),),
        )
    )

    assert (BOOK_PROCEDURE in prompts[0]) is told


_BOOK_TALK = TurnRecord(kind="teacher", text="soạn 10 câu chương 2 trong cuốn sách mình tải lên")
_ANSWER = TurnRecord(kind="teacher", text="lớp 8")


@pytest.mark.parametrize(
    ("attached", "history", "chosen", "told"),
    [
        # Soạn đề, nhắc sách, không chip, chưa đọc sách: lượt duy nhất mở thư viện có nghĩa.
        (None, (_BOOK_TALK,), ("soan-de",), True),
        # Không nhắc sách: đứng đầu các nhánh mà hiện ở mọi lượt thì model gọi `list_documents` cả
        # khi không ai nhắc sách (run-26: 0/6 ở mọi ca đủ mục) -- T3 (`unbiased-model-text`).
        (None, (_TEACHER,), ("soan-de",), False),
        (None, (TurnRecord(kind="teacher", text="cho mình danh sách lớp"),), ("soan-de",), False),
        # Có chip: dòng này từng thắng cả thủ tục sách, 24 lần đo 22/24 → 10/24
        # (`unbiased-model-text` T2b).
        (_READY, (_BOOK_TALK,), ("soan-de",), False),
        (_PROCESSING, (_BOOK_TALK,), ("soan-de",), False),
        # Đã mở thư viện: đang chọn sách, thủ tục sách lo phần còn lại.
        (None, (_BOOK_TALK, *_READ), ("soan-de",), False),
        # Không phải lượt soạn đề.
        (None, (_BOOK_TALK,), ("lop-va-ket-qua",), False),
        # Review T3 (`unbiased-model-text`): nhắc sách ở lượt trước, lượt này chỉ trả lời khối --
        # vẫn là soạn theo sách.
        (
            None,
            (_BOOK_TALK, TurnRecord(kind="assistant", text="khối nào?"), _ANSWER),
            ("soan-de",),
            True,
        ),
        # Một plan đã nêu sau câu nhắc sách: việc ấy xong, đề mới không nhắc sách là đề không sách.
        (None, (_BOOK_TALK, _PLANNED, _TEACHER), ("soan-de",), False),
        # Chữ gửi từ macOS ở dạng phân rã (NFD) -- "sách" phân rã không khớp nếu không chuẩn hoá.
        (
            None,
            (TurnRecord(kind="teacher", text=unicodedata.normalize("NFD", _BOOK_TALK.text)),),
            ("soan-de",),
            True,
        ),
        # Giáo viên gọi tài liệu bằng chữ khác "sách".
        (
            None,
            (TurnRecord(kind="teacher", text="soạn 8 câu theo giáo án tuần trước"),),
            ("soan-de",),
            True,
        ),
    ],
)
def test_the_library_hint_comes_only_to_a_drafting_turn_without_a_book(
    attached, history, chosen, told
) -> None:
    request = NextStepRequested(
        request_id="r1",
        history=history,
        attached_document=attached,
        catalog=(ToolSpec(name="list_documents", description="tra cứu", arguments={}),),
    )

    composed = compose({"request": request, "skills": chosen, "messages": [], "step": None})
    system = composed["messages"][0].text

    assert (LIBRARY in system) is told
    # Chỗ trống của skill không bao giờ tới model, điền hay xoá.
    assert "{thư viện}" not in system


def test_the_library_line_stands_among_the_drafting_branches() -> None:
    """Đứng thành một đoạn riêng sau skill thì model không theo nó; đứng sau nhánh *hỏi lại* thì
    nhánh ấy thắng.

    Nhắc sách không chip: đoạn riêng 0/6 -- model ghi khối bịa rồi nêu plan (`unbiased-model-text`
    T2b); sau nhánh *còn ? → hỏi lại* 11--14/24 -- hỏi khối rồi soạn đề không sách (T3). Chỗ của nó
    là nhánh đầu.
    """
    request = NextStepRequested(
        request_id="r1",
        history=(_BOOK_TALK,),
        catalog=(ToolSpec(name="list_documents", description="tra cứu", arguments={}),),
    )

    system = compose({"request": request, "skills": ("soan-de",), "messages": [], "step": None})[
        "messages"
    ][0].text

    assert system.index("Chỉ mục ghi ? mới được hỏi") < system.index(LIBRARY)
    assert system.index(LIBRARY) < system.index("- còn ? → ask_clarify")
    # Khối thường chỉ có trong tên tài liệu, nên mở thư viện không chờ đủ mục.
    assert "kể cả khi còn ?" in LIBRARY


@pytest.mark.asyncio
async def test_kriky_is_told_a_document_still_being_read(monkeypatch) -> None:
    """Review B6 (`draft-from-document`): chip của tệp còn đang xử lý -- Kriky được báo, không soạn
    như thể không có."""
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
    """Review B7 (`draft-from-document`): tài liệu hỏng thì bảo chờ là kẹt đoạn chat mãi -- nói nó
    không dùng được."""
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


@pytest.mark.parametrize("on_an_item", [True, False])
def test_a_question_is_shown_the_questions_already_in_the_paper(on_an_item: bool) -> None:
    """Thử tay 17/10/2026 (plan `backlog-tier-1`, case 02): ô 4 bị trả về ba lần vì gần trùng câu 3,
    và cả ba lần model viết lại đúng bài ấy -- brief chưa từng cho nó thấy các câu đã có."""
    already = r"Tìm số x thỏa mãn tỉ lệ thức $\frac{x}{12}=\frac{5}{8}$."
    item = {"item_knowledge": "Tỉ lệ thức", "item_approach": "Nhân chéo"} if on_an_item else {}

    brief = draft_brief(_asked(banned_stems=(already,), **item))
    fresh = draft_brief(_asked(**item))

    assert already in brief
    assert "Không viết lại bài nào" in brief
    assert "Không viết lại bài nào" not in fresh


@pytest.mark.parametrize("on_an_item", [True, False])
def test_a_long_paper_shows_every_question_after_the_teachers_brief(on_an_item: bool) -> None:
    """Review code vòng 12, 13 (plan `backlog-tier-1`): câu đã gây trùng nằm ở đâu cũng được (một ô
    soạn thêm trùng câu 1), nên đề mười hai câu nêu cả mười hai, không cắt đầu hay cuối. Và các danh
    sách phải tránh đứng sau những câu *"… trên"* của brief, để chữ *trên* không trỏ vào chúng."""
    stems = tuple(f"Câu đã có số {n}: tính $ {n} + {n} $." for n in range(1, 13))
    item = (
        {"item_knowledge": "Tỉ lệ thức", "item_approach": "Nhân chéo", "other_items": ("Luỹ thừa",)}
        if on_an_item
        else {}
    )

    brief = draft_brief(_asked(banned_stems=stems, **item))

    assert all(stem in brief for stem in stems)
    above = "Bám đúng kiến thức" if on_an_item else "phạm vi trên"
    assert brief.index(above) < brief.index("Không viết lại bài nào")
    if on_an_item:
        assert brief.index(above) < brief.index("đừng hỏi sang")
