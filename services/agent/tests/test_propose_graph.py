"""AGENT đề nghị gì cho một lượt trong khung chat của giáo viên.

Các test này khẳng định hai loại điều và không gì khác. Thứ nhất, rằng một đề nghị đi
ngược về mà không bị sửa: tên tool và các argument của nó là thứ BE dispatch theo, nên
một graph nắn lại chúng sẽ gửi yêu cầu của giáo viên đi một nơi khác. Thứ hai, rằng model
thật sự được cho biết những gì nó cần -- các tool nó được dùng và các tool trước đã trả
về gì -- vì một model bị bảo chọn từ một danh mục nó không thấy được thì sẽ bịa ra một
danh mục.

Thứ cố ý không được test ở đây là một đề nghị có *được phép* hay không. AGENT không thể
biết điều đó: danh tính giáo viên và database nằm ở phía bên kia bức tường, phía BE. Những
test ấy nằm cùng với bên thực thi.
"""

import unicodedata
from types import SimpleNamespace

import pytest
from langchain_core.runnables import Runnable, RunnableLambda

from agent import llm, skill_router
from agent.graphs.propose import (
    _answers,
    _Argument,
    _choices_wanted,
    _Proposal,
    _Step,
    propose,
)
from contracts import AttachedDocument, NextStepRequested, ToolSpec, TurnRecord

_CATALOG = (
    ToolSpec(
        name="get_class",
        description="Lấy thông tin một lớp của giáo viên.",
        arguments={"class_id": "id lớp, lấy từ list_class"},
    ),
    ToolSpec(
        name="class_assessment_summary",
        description="Tóm tắt kết quả một bài kiểm tra trong một lớp.",
        arguments={"class_id": "id lớp", "assessment_id": "id đề"},
    ),
)


class Scripted:
    """Một chat model trả lời bằng các đề nghị xếp sẵn, có ghi lại các prompt của nó.

    Dựng theo cái fake trong `test_authoring_graph.py` chứ không theo
    `GenericFakeChatModel`, vì model đó raise `NotImplementedError` từ
    `with_structured_output` nên không thể đóng thế cho một lần gọi structured.
    """

    def __init__(self, answers: list[_Proposal]) -> None:
        self.answers = answers
        self.prompts: list[str] = []

    def with_structured_output(self, schema: object, **kwargs: object) -> Runnable:
        """Trả về một runnable đưa lại đề nghị xếp sẵn tiếp theo."""

        def answer(messages: object) -> _Proposal:
            self.prompts.append("\n".join(message.text for message in messages))
            return self.answers.pop(0)

        return RunnableLambda(answer)


def _said(text: str) -> _Proposal:
    return _Proposal(kind="say", text=text)


def _wants(tool: str, **args: str) -> _Proposal:
    return _Proposal(
        kind="call_tool",
        tool_name=tool,
        tool_args=tuple(_Argument(param=key, value=value) for key, value in args.items()),
    )


@pytest.fixture
def on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bật đường gọi model lên mà không cần tới một credential."""
    monkeypatch.setattr(llm, "enabled", lambda: True)


def _asked(text: str) -> NextStepRequested:
    return NextStepRequested(
        request_id="r1",
        teacher_name="Cô Lan",
        history=(TurnRecord(kind="teacher", text=text),),
        catalog=_CATALOG,
    )


# Những tool chỉ nêu được trong plan. Chúng tới riêng với `catalog`, vì "gọi được bây giờ"
# và "hẹn làm ở pha sau" là hai quyền khác nhau (ADR-25).
_PLANNABLE = (
    ToolSpec(
        name="create_draft",
        description="Mở một đề nháp trống.",
        arguments={
            "subject": "môn",
            "grade": "khối",
            "topic_scope": "phạm vi kiến thức",
            "question_count": "số câu",
        },
    ),
    ToolSpec(
        name="start_drafting",
        description="Bắt đầu sinh câu hỏi cho một đề nháp đã có brief.",
        arguments={"assessment_id": "id đề nháp"},
    ),
)


def _to_plan(text: str) -> NextStepRequested:
    return NextStepRequested(
        request_id="r1",
        teacher_name="Cô Lan",
        history=(TurnRecord(kind="teacher", text=text),),
        catalog=_CATALOG,
        plannable=_PLANNABLE,
    )


@pytest.mark.asyncio
async def test_a_tool_proposal_keeps_its_name_and_arguments(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """BE dispatch theo hai field này, nên không gì được viết lại chúng."""
    model = Scripted([_wants("get_class", class_id="c-1")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("lớp 12A1 làm bài hôm qua thế nào"))

    assert step.kind == "call_tool"
    assert step.tool_name == "get_class"
    assert step.tool_args == {"class_id": "c-1"}


@pytest.mark.asyncio
async def test_the_model_is_told_which_tools_it_may_use(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Một danh mục model không thấy được là một danh mục nó sẽ bịa ra.

    Các tên tool đi theo vì BE dispatch theo chúng; các mô tả đi theo vì chọn giữa hai
    tool chính là quyết định đang được hỏi.
    """
    model = Scripted([_said("vâng")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    await propose(_asked("chào"))

    prompt = model.prompts[0]
    assert "get_class" in prompt
    assert "class_assessment_summary" in prompt
    assert "Tóm tắt kết quả một bài kiểm tra" in prompt


@pytest.mark.asyncio
async def test_a_tool_result_reaches_the_model_as_data(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Thứ một tool trả về là một phần những gì model biết.

    Đây là toàn bộ lý do cái loop gửi lại lịch sử hội thoại mỗi vòng. Nếu kết quả không
    tới, model sẽ đề nghị lại đúng tool đó và lượt này sẽ xoay cho tới khi cái trần chặn
    nó lại.
    """
    model = Scripted([_said("Lớp 12A1 trung bình 6,5.")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    asked = NextStepRequested(
        request_id="r1",
        history=(
            TurnRecord(kind="teacher", text="lớp 12A1 thế nào"),
            TurnRecord(kind="tool_call", tool_name="get_class", tool_args={"class_id": "c-1"}),
            TurnRecord(
                kind="tool_result",
                tool_name="get_class",
                tool_result={"class_id": "c-1", "name": "12A1", "student_count": 40},
            ),
        ),
        catalog=_CATALOG,
    )

    await propose(asked)

    prompt = model.prompts[0]
    assert "12A1" in prompt
    assert "40" in prompt


@pytest.mark.asyncio
async def test_the_request_id_comes_back_on_the_proposal(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """BE khớp câu trả lời với câu hỏi nó đã đặt.

    Model không thể làm sai chỗ này được nữa, vì nó không được hỏi: schema nó trả lời
    không có `request_id` nào cả. Điều đó mạnh hơn việc ghi đè lên bất cứ thứ gì nó bịa
    ra, mà đó là việc chỗ này từng làm.
    """
    model = Scripted([_said("ừ")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("chào"))

    assert step.request_id == "r1"


class WithUsage:
    """Một chat model trả lời theo hình dạng `include_raw`, kèm một báo cáo usage.

    `Scripted` ở trên bỏ qua `include_raw` và trả thẳng lại đối tượng đã parse, đó cũng
    là một hình dạng các provider thật sinh ra khi chúng không báo được usage. Cái này là
    hình dạng còn lại, và nó tồn tại vì số token là một lời khẳng định về một library --
    mà những lời khẳng định về library trong plan này đã sai ba lần ở những chỗ không có
    gì đo chúng.
    """

    def __init__(self, step: _Proposal, total_tokens: int | None) -> None:
        self.step = step
        self.total_tokens = total_tokens

    def with_structured_output(self, schema: object, **kwargs: object) -> Runnable:
        assert kwargs.get("include_raw") is True

        usage = None if self.total_tokens is None else {"total_tokens": self.total_tokens}
        raw = SimpleNamespace(usage_metadata=usage)

        return RunnableLambda(lambda messages: {"parsed": self.step, "raw": raw})


@pytest.mark.asyncio
async def test_the_token_count_comes_from_the_provider(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Chi phí của lần gọi được đọc từ response, không đọc từ đề nghị.

    Model cũng không được hỏi điều này -- một số token nó bịa ra còn tệ hơn không có số
    nào, vì nó sẽ trông như một phép đo.
    """
    model = WithUsage(_said("ừ"), 1234)
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("chào"))

    assert step.model_tokens == 1234


@pytest.mark.asyncio
async def test_a_provider_that_reports_no_usage_costs_zero_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Số 0 nghĩa là "không được cho biết", và lượt nói vẫn diễn ra.

    Gemini là fallback đang được cấu hình và nó không luôn báo usage. Một con số thiếu
    không được phép kéo cả câu trả lời sụp theo.
    """
    model = WithUsage(_said("ừ"), None)
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("chào"))

    assert step.kind == "say"
    assert step.model_tokens == 0


def test_the_schema_the_model_sees_is_one_openai_accepts() -> None:
    """Structured output ở chế độ strict từ chối các object tự do.

    Đây là cái bug mà mock không bao giờ cho thấy được. `NextStepCompleted.tool_args` là
    một `dict[str, object]`, nó trở thành một JSON object mở, và OpenAI trả lời mọi request
    như vậy bằng

        400 Invalid schema for response_format: In context=('properties',
        'tool_args'), 'additionalProperties' is required to be supplied and to
        be false.

    Thế là mọi lần gọi thật đều thất bại rồi lùi về đề nghị dọn trước. Thời lượng trông
    như thật, câu trả lời đọc thấy hợp lý, và không có gì nổi lên. Tìm ra bằng cách gọi
    model một lần.

    Check này thuần cơ học: mọi object trong schema phải tự đóng kín, và model không được
    bị hỏi bất cứ thứ gì nó không thể biết.
    """
    schema = _Proposal.model_json_schema()

    def closed(node: object) -> list[str]:
        open_objects = []
        if isinstance(node, dict):
            if node.get("type") == "object" and node.get("additionalProperties") is not False:
                open_objects.append(str(node.get("title") or node.get("properties")))
            for value in node.values():
                open_objects += closed(value)
        elif isinstance(node, list):
            for value in node:
                open_objects += closed(value)
        return open_objects

    assert closed(schema) == []

    # Không field nào trong hai field này là thứ một model trả lời được: BE phát ra id,
    # còn provider báo chi phí sau khi việc đã xong. Một field trong schema là một câu hỏi
    # đặt ra cho model.
    asked_for = set(schema["properties"])
    assert "request_id" not in asked_for
    assert "model_tokens" not in asked_for


def test_the_model_writes_down_what_it_knows_before_it_chooses() -> None:
    """`known` là field **đầu tiên**, trước `kind`.

    Model sinh JSON từ trái sang phải, nên thứ tự field là thứ tự quyết định. Với `kind` đứng đầu,
    *"Tạo đề … chương Hàm số cho lớp 12A, 10 câu"* hỏi lại 8/8 lần trên gpt-4o-mini; ghi ra thứ đã
    biết trước thì 4/6 nêu plan (`kriky-skill-routing`, 12/10/2026). Đảo thứ tự lại thì test này đỏ.
    """
    order = list(_Proposal.model_json_schema()["properties"])

    assert order.index("known") < order.index("kind")
    assert order[0] == "known"


@pytest.mark.asyncio
async def test_what_the_model_knows_never_leaves_agent(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """`known` là ghi chú của model, không phải hợp đồng: BE không bao giờ thấy nó."""
    model = Scripted([_Proposal(known="môn Toán, khối 12", kind="say", text="vâng")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("chào"))

    assert "known" not in step.model_dump()
    assert "môn Toán" not in step.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["say", "ask_clarify"])
async def test_an_empty_bubble_is_asked_again_not_shown(
    monkeypatch: pytest.MonkeyPatch, on: None, kind: str
) -> None:
    """Đo được khi thêm `known`: model viết câu hỏi vào ghi chú rồi để `text` rỗng.

    Một bong bóng rỗng không được tới màn hình: `propose` hỏi lại model một lần.
    """
    empty = _Proposal(known="Thiếu số câu. Bạn muốn soạn bao nhiêu câu?", kind=kind, text="  ")
    model = Scripted([empty, _Proposal(kind="ask_clarify", text="Bạn muốn bao nhiêu câu?")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("ra đề Toán lớp 10 về mệnh đề"))

    assert (step.kind, step.text) == ("ask_clarify", "Bạn muốn bao nhiêu câu?")
    assert len(model.prompts) == 2


@pytest.mark.asyncio
async def test_two_empty_bubbles_end_in_a_neutral_ask_not_the_mock(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Hai lần trống thì nhờ nói lại -- không lùi về mock của `handlers.next_step`.

    Mock đoán việc bằng từ khoá, và với đúng câu này nó hỏi *"bạn muốn xem lớp nào?"* (review A1):
    một câu hỏi sai việc trông như hợp lệ.
    """
    model = Scripted([_Proposal(kind="ask_clarify", text=""), _Proposal(kind="say", text=" ")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("ra đề Toán lớp 10 về mệnh đề"))

    assert step.kind == "say"
    assert step.text and "lớp nào" not in step.text
    assert step.request_id == "r1"


@pytest.mark.asyncio
async def test_a_plan_keeps_its_steps_in_order_and_its_references_intact(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Một plan đi ngược về mà không bị sửa, kể cả cú pháp tham chiếu.

    `{1.assessment_id}` là một chuỗi BE giải, không phải một chỗ trống để graph điền. Một
    graph nắn lại nó -- bỏ ngoặc, đổi số, thêm khoảng trắng -- sẽ làm `vet_plan` từ chối
    trọn gói cả plan, và giáo viên nhận một lời từ chối cho một plan đúng.
    """
    model = Scripted(
        [
            _Proposal(
                kind="plan",
                text="Được, mình soạn đề ngay.",
                steps=(
                    _Step(
                        tool_name="create_draft",
                        args=(
                            _Argument(param="subject", value="Toán"),
                            _Argument(param="grade", value="12"),
                            _Argument(param="topic_scope", value="ôn tập"),
                            _Argument(param="question_count", value="10"),
                        ),
                        title="Tạo đề trống",
                    ),
                    _Step(
                        tool_name="start_drafting",
                        args=(_Argument(param="assessment_id", value="{1.assessment_id}"),),
                        title="Soạn 10 câu hỏi",
                    ),
                ),
            )
        ]
    )
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_to_plan("tạo đề 10 câu tích phân lớp 12"))

    assert step.kind == "plan"
    assert step.text == "Được, mình soạn đề ngay."
    assert [one.tool_name for one in step.steps] == ["create_draft", "start_drafting"]
    assert step.steps[0].args == {
        "subject": "Toán",
        "grade": "12",
        "topic_scope": "ôn tập",
        "question_count": "10",
    }
    assert step.steps[1].args == {"assessment_id": "{1.assessment_id}"}
    assert [one.title for one in step.steps] == ["Tạo đề trống", "Soạn 10 câu hỏi"]


def _draft_plan(*args: tuple[str, str]) -> _Proposal:
    return _Proposal(
        kind="plan",
        text="Được, mình soạn đề ngay.",
        steps=(
            _Step(
                tool_name="create_draft",
                args=tuple(_Argument(param=key, value=value) for key, value in args),
                title="Tạo đề trống",
            ),
            _Step(
                tool_name="start_drafting",
                args=(_Argument(param="assessment_id", value="{1.assessment_id}"),),
                title="Soạn câu hỏi",
            ),
        ),
    )


_FULL = (("subject", "Toán"), ("grade", "9"), ("topic_scope", "ôn tập"), ("question_count", "6"))


@pytest.mark.asyncio
async def test_a_plan_missing_a_required_argument_is_asked_again(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """`unbiased-model-text` T2b: giá trị nằm ở `known` mà `create_draft` không kèm tham số nào.

    BE `vet_plan` từ chối đúng plan ấy, và giáo viên nhận một lời từ chối cho một câu đã đủ ý. Hỏi
    lại model một lần thì rẻ hơn.
    """
    model = Scripted([_draft_plan(), _draft_plan(*_FULL)])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_to_plan("6 câu ôn tập lớp 9"))

    assert len(model.prompts) == 2
    assert step.steps[0].args == dict(_FULL)


@pytest.mark.asyncio
async def test_a_garbled_argument_is_asked_again(monkeypatch: pytest.MonkeyPatch, on: None) -> None:
    """`unbiased-model-text` T3: *"tỉ lệ th\\x13"* làm `topic_scope` (run-53, run-54) -- chữ hỏng
    thành tên đề."""
    garbled = tuple(
        (key, "tỉ lệ th\x13") if key == "topic_scope" else (key, value) for key, value in _FULL
    )
    model = Scripted([_draft_plan(*garbled), _draft_plan(*_FULL)])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_to_plan("6 câu tỉ lệ thức lớp 7"))

    assert len(model.prompts) == 2
    assert step.steps[0].args == dict(_FULL)


_LIBRARY_TOOL = ToolSpec(name="list_documents", description="Liệt kê tài liệu.", arguments={})


def _library_turn(text: str) -> NextStepRequested:
    return NextStepRequested(
        request_id="r1",
        teacher_name="Cô Lan",
        history=(TurnRecord(kind="teacher", text=text),),
        catalog=(*_CATALOG, _LIBRARY_TOOL),
        plannable=_PLANNABLE,
    )


def _opened_by(tool: str, **args: str) -> _Proposal:
    """`_draft_plan` đầy đủ, mở đầu bằng một bước `tool`."""
    drafting = _draft_plan(*_FULL)
    first = _Step(
        tool_name=tool,
        args=tuple(_Argument(param=key, value=value) for key, value in args.items()),
        title="Mở thư viện",
    )
    return drafting.model_copy(update={"steps": (first, *drafting.steps)})


@pytest.mark.asyncio
async def test_a_plan_opening_with_a_read_calls_the_read_first(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """`unbiased-model-text` T5: nhắc sách, đủ bốn mục -- model nêu `list_documents → create_draft →
    …`, và BE từ chối cả plan vì `list_documents` không có trong catalog pha thực hiện (16/24 lượt,
    run-73). Bước đầu ấy là ý *"đọc trước"*: nó thành lời gọi, không hỏi lại model."""
    model = Scripted([_opened_by("list_documents")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    # Câu không nhắc sách: `_library_first` không đụng tới, chỉ `_reads_first` lật được plan này.
    step = await propose(_library_turn("6 câu ôn tập lớp 9, mở thư viện giúp mình"))

    assert len(model.prompts) == 1
    assert step.kind == "call_tool"
    assert step.tool_name == "list_documents"
    assert step.tool_args == {}
    assert step.steps == ()
    assert step.request_id == "r1"


@pytest.mark.asyncio
async def test_a_plan_opening_with_a_plannable_tool_stays_a_plan(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    model = Scripted([_draft_plan(*_FULL)])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_library_turn("6 câu ôn tập lớp 9"))

    assert step.kind == "plan"
    assert [one.tool_name for one in step.steps] == ["create_draft", "start_drafting"]


@pytest.mark.asyncio
async def test_a_plan_opening_with_an_unknown_tool_is_left_for_be_to_refuse(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Chỉ tool có trong `catalog` lượt này mới được gọi -- một tên bịa không thành lời gọi."""
    model = Scripted([_opened_by("doc_sach_ra")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_library_turn("6 câu ôn tập lớp 9, mở thư viện giúp mình"))

    assert step.kind == "plan"
    assert step.steps[0].tool_name == "doc_sach_ra"


_TOC_TOOL = ToolSpec(
    name="list_chapters", description="Mục lục một tài liệu.", arguments={"document_id": "id"}
)


def _book_plan(**extra: str) -> _Proposal:
    """`_draft_plan` đầy đủ, `create_draft` kèm tham số tài liệu."""
    return _draft_plan(*_FULL, *extra.items())


_READ_D10 = (
    TurnRecord(kind="tool_call", tool_name="list_chapters", tool_args={"document_id": "d10"}),
    TurnRecord(
        kind="tool_result",
        tool_name="list_chapters",
        tool_result={"found": True, "candidates": [{"node": 3, "label": "Chương I. MỆNH ĐỀ"}]},
    ),
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("proposed", "attached", "before", "read"),
    [
        # T5 (`unbiased-model-text`) trên trình duyệt: bấm tên cuốn, model nêu plan không có `nodes`
        # -- BE dừng ở bước 1.
        (_book_plan(document_id="d10"), None, (), True),
        # `nodes` chưa đọc mục lục là số bịa -- BE nhận, đề soạn trên mục sai (run-87, review T5,
        # `unbiased-model-text`).
        (_book_plan(document_id="d10", nodes="1,2,3"), None, (), True),
        # Đã đọc mục lục: plan đi tiếp, đủ `nodes` hay không -- gọi lại là lặp tới trần của BE.
        (_book_plan(document_id="d10", nodes="3,5"), None, _READ_D10, False),
        (_book_plan(document_id="d10"), None, _READ_D10, False),
        # Không tài liệu: đề không sách.
        (_draft_plan(*_FULL), None, (), False),
        # Có chip: thủ tục sách đọc mục lục từ trước, `bind_book` điền `nodes` -- không đụng tới.
        (
            _book_plan(document_id="d10"),
            AttachedDocument(document_id="d10", filename="Toán 10.pdf", state="ready"),
            (),
            False,
        ),
    ],
)
async def test_a_plan_from_a_book_without_its_chapters_reads_them_first(
    monkeypatch: pytest.MonkeyPatch, on: None, proposed: _Proposal, attached, before, read: bool
) -> None:
    model = Scripted([proposed])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))
    request = NextStepRequested(
        request_id="r1",
        history=(TurnRecord(kind="teacher", text="soạn 6 câu ôn tập lớp 9"), *before),
        catalog=(*_CATALOG, _TOC_TOOL),
        plannable=_PLANNABLE,
        attached_document=attached,
    )

    step = await propose(request)

    assert (step.kind == "call_tool") is read
    if read:
        assert step.tool_name == "list_chapters"
        assert step.tool_args == {"document_id": "d10"}


@pytest.mark.asyncio
async def test_no_table_of_contents_tool_no_reading_it(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """`list_chapters` không có trong catalog lượt này thì không gọi nó -- BE sẽ từ chối."""
    model = Scripted([_book_plan(document_id="d10")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_to_plan("soạn 6 câu ôn tập lớp 9"))

    assert step.kind == "plan"


def _grade_asked() -> _Proposal:
    return _Proposal(
        kind="ask_clarify",
        text="Bạn soạn cho khối mấy?",
        choices=("Khối 10", "Khối 11", "Khối 12"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("said", "proposed", "listed"),
    [
        # Nhắc sách, không chip: model hỏi khối -- khối nằm sẵn trong tên tài liệu (T5,
        # `unbiased-model-text`, run-77).
        ("Soạn 10 câu chương 2 trong cuốn sách mình đã tải lên hôm qua", _grade_asked(), True),
        # Nhắc sách, đủ bốn mục: model soạn đề không sách.
        ("Lấy cuốn Toán 10 mình mới tải lên, ra 6 câu ôn tập", _draft_plan(*_FULL), True),
        # Không nhắc sách: câu hỏi lại là câu hỏi lại.
        ("Soạn 10 câu chương 2", _grade_asked(), False),
        # Nhắc sách mà model gọi một tool khác: để nguyên.
        ("Lớp 12A dùng cuốn sách nào?", _wants("get_class", class_id="c-1"), False),
    ],
)
async def test_a_turn_that_opens_the_library_lists_documents_first(
    monkeypatch: pytest.MonkeyPatch, on: None, said: str, proposed: _Proposal, listed: bool
) -> None:
    """`unbiased-model-text` T5: dòng mở thư viện bằng chữ thua nhánh *"còn ? → hỏi lại"* mỗi khi
    model suy được thêm một mục (`tai-lieu-khong-dinh` 24 → 16/24). Bước đầu của lượt nhắc sách do
    code quyết."""
    model = Scripted([proposed])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_library_turn(said))

    assert (step.kind == "call_tool" and step.tool_name == "list_documents") is listed
    if listed:
        assert step.tool_args == {}
        assert step.choices == ()


@pytest.mark.asyncio
async def test_a_book_on_the_chat_never_reopens_the_library(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Chip sẵn sàng: thủ tục sách lo, thư viện không mở lại (T2b, `unbiased-model-text`: 22/24 →
    10/24 khi mở lại)."""
    model = Scripted([_grade_asked()])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))
    request = _library_turn("Soạn 10 câu chương 2 từ sách này").model_copy(
        update={
            "attached_document": AttachedDocument(
                document_id="d1", filename="Toán 10 tập 1.pdf", state="ready"
            )
        }
    )

    step = await propose(request)

    assert step.kind == "ask_clarify"


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["processing", "failed"])
async def test_a_book_not_yet_readable_never_opens_the_library(
    monkeypatch: pytest.MonkeyPatch, on: None, state: str
) -> None:
    """Chip chưa đọc được: dòng báo chip dặn chờ hay đính tài liệu khác -- không mở thư viện."""
    model = Scripted([_grade_asked()])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))
    request = _library_turn("Soạn 10 câu chương 2 từ sách này").model_copy(
        update={
            "attached_document": AttachedDocument(
                document_id="d1", filename="Toán 10 tập 1.pdf", state=state
            )
        }
    )

    step = await propose(request)

    assert step.kind == "ask_clarify"


def _more_questions() -> _Proposal:
    return _Proposal(
        kind="plan",
        text="Mình soạn thêm 5 câu.",
        steps=(
            _Step(
                tool_name="start_drafting",
                args=(
                    _Argument(param="assessment_id", value="a-1"),
                    _Argument(param="question_count", value="5"),
                ),
                title="Soạn thêm câu",
            ),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("said", "proposed"),
    [
        # Review T5 (`unbiased-model-text`): soạn thêm cho đề đã mở là plan hợp lệ -- "sách giáo
        # khoa" không biến nó thành việc mở thư viện.
        ("Soạn thêm 5 câu nữa, bám sát sách giáo khoa", _more_questions()),
        # Lời nói để nguyên: `_BOOK_WORDS` báo nhầm (*"file Word"*) không được ép thành lời gọi.
        ("Xuất đề ra file Word giúp mình", _said("Mình chưa xuất được file Word.")),
    ],
)
async def test_the_library_is_not_forced_on_what_is_not_a_question_or_a_new_draft(
    monkeypatch: pytest.MonkeyPatch, on: None, said: str, proposed: _Proposal
) -> None:
    model = Scripted([proposed])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_library_turn(said))

    assert step.kind == proposed.kind


@pytest.mark.asyncio
async def test_the_library_opens_only_on_a_drafting_turn(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Cổng skill của `_opens_library`: lượt chỉ nạp `lop-va-ket-qua` thì không mở thư viện."""

    async def routed(history: object) -> tuple[str, ...]:
        return ("lop-va-ket-qua",)

    monkeypatch.setattr(skill_router, "choose", routed)
    model = Scripted([_grade_asked()])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_library_turn("Soạn 10 câu chương 2 trong cuốn sách mình đã tải lên"))

    assert step.kind == "ask_clarify"


@pytest.mark.asyncio
async def test_a_read_already_done_is_not_asked_for_again(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Review T5 (`unbiased-model-text`): `list_documents` đã gọi rồi mà plan lại mở bằng nó -- gọi
    lại là lặp tới trần `max_tool_steps` của BE rồi báo lỗi; để plan đi tiếp cho BE từ chối một
    lần."""
    model = Scripted([_opened_by("list_documents")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))
    request = _library_turn("6 câu ôn tập lớp 9, mở thư viện giúp mình")
    request = request.model_copy(
        update={
            "history": (
                *request.history,
                TurnRecord(kind="tool_call", tool_name="list_documents"),
                TurnRecord(kind="tool_result", tool_name="list_documents", tool_result={}),
            )
        }
    )

    step = await propose(request)

    assert step.kind == "plan"


@pytest.mark.asyncio
async def test_a_read_keeps_the_arguments_the_plan_gave_it(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    model = Scripted([_opened_by("list_chapters", document_id="d7")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))
    request = _library_turn("6 câu ôn tập lớp 9").model_copy(
        update={"catalog": (*_CATALOG, _TOC_TOOL)}
    )

    step = await propose(request)

    assert step.kind == "call_tool"
    assert step.tool_name == "list_chapters"
    assert step.tool_args == {"document_id": "d7"}


@pytest.mark.asyncio
async def test_a_tool_that_may_be_planned_is_left_in_the_plan(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Tool vừa gọi được ngay vừa nêu được trong plan: plan mở đầu bằng nó vẫn là plan."""
    model = Scripted([_draft_plan(*_FULL)])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))
    request = _to_plan("6 câu ôn tập lớp 9").model_copy(
        update={"catalog": (*_CATALOG, _PLANNABLE[0])}
    )

    step = await propose(request)

    assert step.kind == "plan"


_DOCUMENTS = {
    "found": True,
    "more": 0,
    "candidates": [
        {"document_id": "d10", "label": "Kết nối tri thức Lớp 10 tập 1.pdf"},
        {"document_id": "d6", "label": "Kết nối tri thức Lớp 6 tập 1.pdf"},
    ],
}


def _after_library(*later: TurnRecord, documents: dict = _DOCUMENTS) -> NextStepRequested:
    """Không chip, giáo viên nhắc sách, BE vừa chạy `list_documents`; `later` nối sau đó."""
    return NextStepRequested(
        request_id="r1",
        history=(
            TurnRecord(kind="teacher", text="Lấy cuốn Toán 10 mình mới tải lên, ra 6 câu ôn tập"),
            TurnRecord(kind="tool_call", tool_name="list_documents"),
            TurnRecord(kind="tool_result", tool_name="list_documents", tool_result=documents),
            *later,
        ),
        catalog=(*_CATALOG, _LIBRARY_TOOL, _TOC_TOOL),
        plannable=_PLANNABLE,
    )


_ASKED_BOOK = TurnRecord(kind="assistant", text="Bạn soạn theo tài liệu nào?")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("said", "before", "read"),
    [
        # Bấm nút tên cuốn: giáo viên đã chọn -- đọc mục lục của đúng cuốn ấy, bằng code.
        ("Kết nối tri thức Lớp 10 tập 1.pdf", (), "d10"),
        # Khác hoa thường, thừa khoảng trắng: vẫn là cuốn ấy.
        ("  kết nối tri thức lớp 10 tập 1.PDF ", (), "d10"),
        # Gõ một câu không trùng tên nào: không chọn hộ.
        ("cuốn lớp 10", (), ""),
        # Đã đọc mục lục cuốn ấy rồi: không đọc lại.
        ("Kết nối tri thức Lớp 10 tập 1.pdf", _READ_D10, ""),
    ],
)
async def test_a_document_the_teacher_picks_has_its_chapters_read(
    monkeypatch: pytest.MonkeyPatch, on: None, said: str, before: tuple, read: str
) -> None:
    """Review T5 (`unbiased-model-text`, hướng iii): sau khi giáo viên bấm tên cuốn, model tự gọi
    `list_chapters` 0/24 -- nó nêu plan, có `nodes` bịa hay không `document_id` (run-87)."""
    model = Scripted([_draft_plan(*_FULL)])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(
        _after_library(_ASKED_BOOK, TurnRecord(kind="teacher", text=said), *before)
    )

    if read:
        assert step.kind == "call_tool"
        assert step.tool_name == "list_chapters"
        assert step.tool_args == {"document_id": read}
    else:
        assert step.kind == "plan"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("documents", "after", "fixed"),
    [
        # Ngay sau danh sách tài liệu: nút là tên tài liệu, câu hỏi phải hỏi tài liệu.
        (_DOCUMENTS, (), True),
        # Một tài liệu cũng vậy -- không chọn hộ (hướng i chưa được duyệt).
        ({**_DOCUMENTS, "candidates": _DOCUMENTS["candidates"][:1]}, (), True),
        # Thư viện rỗng: không có nút nào, câu của model để nguyên.
        ({"found": False, "more": 0, "candidates": []}, (), False),
        # Đã đọc mục lục sau đó: câu hỏi là về mục, không đụng tới.
        (_DOCUMENTS, _READ_D10, False),
        # Review chung sau T5 (`unbiased-model-text`): giáo viên đã nói sau danh sách (*"thôi, không
        # dùng sách"* qua lối "Khác") -- câu hỏi kế tiếp là về khối hay số câu, không phải về tài
        # liệu.
        (
            _DOCUMENTS,
            (_ASKED_BOOK, TurnRecord(kind="teacher", text="thôi, không dùng sách")),
            False,
        ),
    ],
)
async def test_a_question_right_after_the_library_asks_which_document(
    monkeypatch: pytest.MonkeyPatch, on: None, documents: dict, after: tuple, fixed: bool
) -> None:
    """Review T5 (`unbiased-model-text`, hướng ii): chữ model lệch nút 5--17/24 lượt -- *"phần mệnh
    đề nằm ở mục nào?"* với nút là tên tệp (run-83, run-87)."""
    asked = _Proposal(
        kind="ask_clarify",
        text="Phần mệnh đề nằm ở mục nào của cuốn sách?",
        choices=("Chương 1", "Chương 2", "Chương 3"),
    )
    model = Scripted([asked])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_after_library(*after, documents=documents))

    assert step.kind == "ask_clarify"
    assert (step.text == "Bạn soạn theo tài liệu nào?") is fixed


def _asked_naming(tool: str, **args: str) -> _Proposal:
    """Câu hỏi lại mà model điền thêm một lời gọi tool -- `kind` nộp nhầm (run-88)."""
    return _Proposal(
        kind="ask_clarify",
        text="Phần mệnh đề nằm ở mục nào của cuốn sách?",
        choices=("Chương 1", "Chương 2", "Chương 3"),
        tool_name=tool,
        tool_args=tuple(_Argument(param=key, value=value) for key, value in args.items()),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("proposed", "after", "read"),
    [
        # Run-88: 16/24 lượt -- model đã chọn cuốn Lớp 10, chỉ nộp nhầm `kind`.
        (_asked_naming("list_chapters", document_id="d10"), (), "d10"),
        # Tài liệu không có trong danh sách: không gọi một `document_id` bịa.
        (_asked_naming("list_chapters", document_id="d99"), (), ""),
        # Đã đọc mục lục: câu hỏi về chương là câu hỏi thật (`tai-lieu-khong-khop`).
        (_asked_naming("list_chapters", document_id="d10"), _READ_D10, ""),
        # Tool khác: câu hỏi khối mang `list_class` là câu hỏi thật (`thieu-khoi-co-so-cau`).
        (_asked_naming("list_class", name="10"), (), ""),
    ],
)
async def test_a_question_that_names_the_chapters_of_a_listed_document_reads_them(
    monkeypatch: pytest.MonkeyPatch, on: None, proposed: _Proposal, after: tuple, read: str
) -> None:
    model = Scripted([proposed])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_after_library(*after))

    if read:
        assert step.kind == "call_tool"
        assert step.tool_args == {"document_id": read}
    else:
        assert step.kind == "ask_clarify"


_READY_BOOK = AttachedDocument(document_id="d10", filename="Toán 10 tập 1.pdf", state="ready")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("proposed", "later"),
    [
        # `_misfiled_read`: có chip thì thủ tục sách lo việc đọc mục lục.
        (_asked_naming("list_chapters", document_id="d10"), ()),
        # `_picked_book_first`: chữ trùng tên một tài liệu, nhưng đoạn chat đã gắn sách.
        (
            _draft_plan(*_FULL),
            (_ASKED_BOOK, TurnRecord(kind="teacher", text="Kết nối tri thức Lớp 10 tập 1.pdf")),
        ),
        # `_which_book`: câu hỏi ngay sau danh sách, nhưng có chip -- không đè chữ model.
        (_grade_asked(), ()),
    ],
)
async def test_the_rules_for_a_chat_without_a_book_leave_a_bound_chat_alone(
    monkeypatch: pytest.MonkeyPatch, on: None, proposed: _Proposal, later: tuple
) -> None:
    """Review chung sau T5 (`unbiased-model-text`): ba luật chỉ dành cho lượt không chip -- bỏ guard
    chip của chúng thì không test nào đỏ."""
    model = Scripted([proposed])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))
    request = _after_library(*later)
    request = request.model_copy(update={"attached_document": _READY_BOOK})

    step = await propose(request)

    assert step.kind == proposed.kind
    if step.kind == "ask_clarify":
        assert step.text == proposed.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("proposed", "request_of"),
    [
        (_opened_by("list_documents"), lambda: _library_turn("6 câu ôn tập lớp 9")),
        (
            _book_plan(document_id="d10"),
            lambda: _library_turn("6 câu ôn tập").model_copy(
                update={"catalog": (*_CATALOG, _TOC_TOOL)}
            ),
        ),
        (_grade_asked(), lambda: _library_turn("Soạn 10 câu chương 2 trong cuốn sách đã tải")),
        (
            _draft_plan(*_FULL),
            lambda: _after_library(
                _ASKED_BOOK, TurnRecord(kind="teacher", text="Kết nối tri thức Lớp 10 tập 1.pdf")
            ),
        ),
        (_asked_naming("list_chapters", document_id="d10"), lambda: _after_library()),
    ],
)
async def test_a_read_put_in_place_of_a_proposal_keeps_its_cost(
    monkeypatch: pytest.MonkeyPatch, on: None, proposed: _Proposal, request_of
) -> None:
    """Lời gọi do code dựng vẫn là lần gọi model đã trả tiền: số token đi theo."""
    model = WithUsage(proposed, 4321)
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(request_of())

    assert step.kind == "call_tool"
    assert step.model_tokens == 4321


@pytest.mark.asyncio
async def test_a_plan_missing_an_argument_twice_goes_on_to_be(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Thiếu lần hai thì để BE nói lời từ chối của nó -- AGENT không bịa tham số thay model."""
    model = Scripted([_draft_plan(), _draft_plan(("subject", "Toán"))])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_to_plan("6 câu ôn tập lớp 9"))

    assert len(model.prompts) == 2
    assert step.kind == "plan"
    assert step.steps[0].args == {"subject": "Toán"}
    assert step.request_id == "r1"


@pytest.mark.asyncio
async def test_an_optional_argument_is_not_asked_for(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Tham số khai ở `optional` -- như tài liệu khi đoạn chat không gắn sách -- được bỏ trống."""
    plannable = tuple(
        spec.model_copy(
            update={
                "arguments": {**spec.arguments, "document_id": "id tài liệu"},
                "optional": ("document_id",),
            }
        )
        if spec.name == "create_draft"
        else spec
        for spec in _PLANNABLE
    )
    model = Scripted([_draft_plan(*_FULL)])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_to_plan("6 câu ôn tập lớp 9").model_copy(update={"plannable": plannable}))

    assert len(model.prompts) == 1
    assert step.kind == "plan"


@pytest.mark.asyncio
async def test_a_bound_book_needs_no_document_id_from_the_model(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Review T2b (`unbiased-model-text`): đoạn chat gắn sách thì BE `bind_book` điền `document_id`
    trước `vet_plan`.

    Hình dạng catalog như BE gửi ở lượt ấy -- tham số tài liệu **bắt buộc**. Thiếu `document_id`
    thì BE tự lo, nên không phải lý do hỏi lại; thiếu `nodes` thì vẫn hỏi.
    """
    plannable = tuple(
        spec.model_copy(
            update={
                "arguments": {**spec.arguments, "document_id": "id", "nodes": "các node"},
                "optional": (),
            }
        )
        if spec.name == "create_draft"
        else spec
        for spec in _PLANNABLE
    )
    request = _to_plan("6 câu chương 1 từ sách này").model_copy(
        update={
            "plannable": plannable,
            "attached_document": AttachedDocument(document_id="book", filename="Sách.pdf"),
        }
    )
    model = Scripted([_draft_plan(*_FULL, ("nodes", "3")), _draft_plan(*_FULL)])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(request)

    assert len(model.prompts) == 1
    assert "document_id" not in step.steps[0].args

    model = Scripted([_draft_plan(*_FULL), _draft_plan(*_FULL, ("nodes", "3"))])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(request)

    assert len(model.prompts) == 2
    assert step.steps[0].args["nodes"] == "3"


class _Breaks:
    """Lần đầu trả một đề nghị xếp sẵn, lần sau provider hỏng."""

    def __init__(self, first: _Proposal) -> None:
        self.first: _Proposal | None = first
        self.prompts = 0

    def with_structured_output(self, schema: object, **kwargs: object) -> Runnable:
        def answer(messages: object) -> _Proposal:
            self.prompts += 1
            if self.first is None:
                raise RuntimeError("provider down")
            first, self.first = self.first, None
            return first

        return RunnableLambda(answer)


@pytest.mark.asyncio
@pytest.mark.parametrize("second", ["empty", "broken"])
async def test_a_failed_second_ask_keeps_the_first_plan(
    monkeypatch: pytest.MonkeyPatch, on: None, second: str
) -> None:
    """Review T2b (`unbiased-model-text`): lần hỏi lại không bao giờ được làm kết quả tệ hơn khi
    chưa có nó.

    Trước T2b, plan thiếu tham số đi thẳng tới BE -- và ở lượt có sách `bind_book` có thể điền
    nốt. Lần hai im lặng thì `_UNCLEAR`, provider hỏng thì lùi về mock: cả hai đều tệ hơn.
    """
    model: object = (
        Scripted([_draft_plan(("subject", "Toán")), _Proposal(kind="say", text=" ")])
        if second == "empty"
        else _Breaks(_draft_plan(("subject", "Toán")))
    )
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_to_plan("6 câu ôn tập lớp 9"))

    assert step.kind == "plan"
    assert step.steps[0].args == {"subject": "Toán"}
    assert step.request_id == "r1"


def _ask(*choices: str) -> _Proposal:
    return _Proposal(kind="ask_clarify", text="Bạn muốn bao nhiêu câu?", choices=choices)


@pytest.mark.asyncio
async def test_a_question_back_carries_the_models_choices(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """`unbiased-model-text` T3: hỏi lại thì có ít nhất 3 lựa chọn do model đề xuất; BE dựng nút từ
    chúng."""
    model = Scripted([_ask("10 câu", "15 câu", "20 câu")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("soạn đề góc nội tiếp lớp 9"))

    assert step.choices == ("10 câu", "15 câu", "20 câu")
    assert len(model.prompts) == 1


@pytest.mark.asyncio
async def test_what_the_model_writes_comes_back_in_nfc(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Run-57: "tỉ lệ thức" với "ứ" phân rã -- in ra y hệt, mà không khớp chữ nào của BE."""
    split = unicodedata.normalize("NFD", "tỉ lệ thức")
    plan = _draft_plan(*((key, split) if key == "topic_scope" else (key, v) for key, v in _FULL))
    model = Scripted([plan])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_to_plan("6 câu tỉ lệ thức lớp 7"))

    assert step.steps[0].args["topic_scope"] == unicodedata.normalize("NFC", "tỉ lệ thức")


@pytest.mark.asyncio
async def test_choices_never_ride_along_with_a_plain_answer(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Nút chỉ đi cùng một câu hỏi: một lời nói mang nút thì màn hình dựng nó thành thẻ hỏi lại."""
    model = Scripted([_Proposal(kind="say", text="vâng", choices=("a", "b", "c"))])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("chào bạn"))

    assert step.choices == ()


@pytest.mark.asyncio
async def test_a_question_with_too_few_choices_is_asked_again(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Hai lựa chọn, hay lựa chọn trùng nhau, là chưa đủ ba: hỏi lại model một lần."""
    model = Scripted([_ask("10 câu", "10 câu ", "15 câu"), _ask("10 câu", "15 câu", "20 câu")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("soạn đề góc nội tiếp lớp 9"))

    assert len(model.prompts) == 2
    assert step.choices == ("10 câu", "15 câu", "20 câu")


@pytest.mark.asyncio
async def test_a_choice_that_is_a_question_is_not_a_choice(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Run-41: thiếu cả bốn mục thì model bày *"Môn học là gì?"* làm nút -- bấm nó là gửi một câu
    hỏi đi như lời giáo viên. Lựa chọn kết bằng "?" bị bỏ trước khi đếm đủ ba."""
    asking = ("Môn học là gì?", "Khối lớp nào?", "Số câu là bao nhiêu?")
    model = Scripted([_ask(*asking), _ask("khối 6", "khối 7", "khối 8", "Khối lớp nào?")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("mình cần một đề"))

    assert len(model.prompts) == 2
    assert step.choices == ("khối 6", "khối 7", "khối 8")


@pytest.mark.asyncio
async def test_too_few_choices_twice_is_still_a_question(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Thiếu lần hai thì câu hỏi vẫn đi tiếp -- giáo viên vẫn tự ghi được qua lối "Khác". AGENT
    không bịa lựa chọn."""
    model = Scripted([_ask("10 câu"), _ask("10 câu", "15 câu")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("soạn đề góc nội tiếp lớp 9"))

    assert (step.kind, step.choices) == ("ask_clarify", ("10 câu", "15 câu"))
    assert step.request_id == "r1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("history", "enough"),
    [
        # Hai lớp trong candidates: chỉ có hai lựa chọn thật -- đòi ba là mời model bịa lớp thứ ba.
        (
            (
                TurnRecord(kind="teacher", text="lớp 12 thế nào"),
                TurnRecord(kind="tool_call", tool_name="list_class", tool_args={"name": "12"}),
                TurnRecord(
                    kind="tool_result",
                    tool_name="list_class",
                    tool_result={"candidates": [{"name": "12A"}, {"name": "12B"}], "more": 0},
                ),
            ),
            ("12A", "12B"),
        ),
    ],
)
async def test_fewer_than_three_choices_are_enough_when_three_cannot_be_real(
    monkeypatch: pytest.MonkeyPatch, on: None, history: tuple[TurnRecord, ...], enough: tuple
) -> None:
    model = Scripted([_ask(*enough)])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("x").model_copy(update={"history": history}))

    assert len(model.prompts) == 1
    assert step.choices == enough


def test_names_of_items_and_other_are_not_answers() -> None:
    """Review T3 (`unbiased-model-text`): thiếu cả bốn mục thì 15/30 lượt bày *"Môn học"*, *"Khối
    lớp"* -- tên các mục câu hỏi vừa kể -- làm nút; và 58/158 câu hỏi có "Khác" model tự viết, được
    đếm vào đủ ba."""
    question = "Bạn cho mình biết môn học, khối lớp, phạm vi kiến thức và số câu hỏi nhé?"

    kept = _answers(("Môn học", "Khối lớp", "Số câu hỏi", "Khác", "khối 6"), question)

    assert kept == ("khối 6",)


def test_a_value_stays_even_when_the_question_names_it() -> None:
    """Có chữ số là một giá trị: *"Bạn muốn 10, 15 hay 20 câu?"* vẫn cho bấm *"20 câu"*."""
    question = "Bạn muốn 10, 15 hay 20 câu?"

    assert _answers(("10 câu", "15 câu", "20 câu"), question) == ("10 câu", "15 câu", "20 câu")


def test_two_rows_from_an_earlier_turn_are_still_enough() -> None:
    """Review T3 (`unbiased-model-text`): câu hỏi về hai lớp kéo sang lượt sau, giáo viên gõ một tên
    khác, lượt ấy không gọi lại tool. Đòi ba ở đó là ép model bịa lớp thứ ba."""
    history = (
        TurnRecord(kind="teacher", text="lớp 12 thế nào"),
        TurnRecord(kind="tool_call", tool_name="list_class", tool_args={"name": "12"}),
        TurnRecord(
            kind="tool_result",
            tool_name="list_class",
            tool_result={"candidates": [{"name": "12A"}, {"name": "12B"}], "more": 0},
        ),
        TurnRecord(kind="assistant", text="Bạn muốn xem lớp nào?"),
        TurnRecord(kind="teacher", text="lớp chuyên ấy"),
    )

    assert _choices_wanted(_asked("x").model_copy(update={"history": history})) == 2
    # Một plan đã nêu sau danh sách ấy: việc chọn lớp xong rồi, câu hỏi mới lại cần ba.
    planned = (*history[:4], TurnRecord(kind="plan"), TurnRecord(kind="teacher", text="soạn đề"))
    assert _choices_wanted(_asked("x").model_copy(update={"history": planned})) == 3


@pytest.mark.asyncio
async def test_a_second_ask_with_fewer_choices_keeps_the_first(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Review T3 (`unbiased-model-text`): hai lần đều thiếu thì giữ lần nhiều lựa chọn hơn -- lần
    hai có thể còn ít hơn."""
    model = Scripted([_ask("10 câu", "15 câu"), _ask("10 câu")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("soạn đề góc nội tiếp lớp 9"))

    assert step.choices == ("10 câu", "15 câu")


def test_the_schema_tells_the_model_how_to_fill_choices() -> None:
    """Mô tả field đi vào schema structured output -- text model đọc. Review T3
    (`unbiased-model-text`): bỏ hai câu này thì mọi test vẫn xanh."""
    described = _Proposal.model_json_schema()["properties"]["choices"]["description"]

    assert "chép đúng tên trong kết quả tool" in described
    assert "Không đánh dấu lựa chọn nào là nên chọn" in described


@pytest.mark.asyncio
async def test_the_model_is_told_which_tools_it_may_only_plan(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Hai danh mục, và model phải đọc được cái nào là cái nào.

    Pha 1 không gọi được tool ghi, nên nếu mô tả của chúng không tới thì model phải đoán
    tên tham số -- và một plan đoán sai tên tham số bị `vet_plan` từ chối trước khi bước
    nào chạy. Danh sách này là thứ duy nhất làm cho một plan đúng có thể viết ra được.
    """
    model = Scripted([_said("vâng")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    await propose(_to_plan("tạo đề 10 câu"))

    prompt = model.prompts[0]
    assert "create_draft" in prompt
    assert "topic_scope" in prompt
    assert "start_drafting" in prompt
    # Và nó phải đọc ra được rằng đây là nhóm **không gọi ngay**, nếu không nó sẽ gọi
    # `call_tool` với `create_draft` và tiêu một vòng để nhận lại một lời từ chối.
    assert "không gọi ngay" in prompt


@pytest.mark.asyncio
async def test_steps_never_ride_along_with_a_plain_answer(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Model nói `say` mà vẫn kèm bước thì các bước ấy bị bỏ, không đi tiếp.

    Hợp đồng từ chối `steps` ở mọi `kind` khác `plan`, nên để chúng đi qua là biến một
    câu trả lời bình thường thành một `ValidationError` ở giữa một lượt đang chạy.
    """
    model = Scripted(
        [
            _Proposal(
                kind="say",
                text="Đề 12A1 có 10 câu rồi.",
                steps=(_Step(tool_name="create_draft", args=(), title="Tạo đề"),),
            )
        ]
    )
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_to_plan("đề 12A1 mấy câu"))

    assert step.kind == "say"
    assert step.steps == ()


@pytest.mark.asyncio
async def test_the_prompt_carries_the_syntax_without_which_no_plan_works(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Cú pháp `{k.ten_field}` là hợp đồng, không phải văn phong.

    Đây là luật đắt nhất của ADR-25 trong prompt: không có nó thì model không diễn tả được
    một plan hai bước phụ thuộc nhau, nên mọi plan nó viết ra đều bị `vet_plan` từ chối và
    giáo viên nhận một lời từ chối cho một yêu cầu hợp lệ. Nó không được phép mất đi trong
    một lần dọn prompt mà cả bộ test vẫn xanh.
    """
    model = Scripted([_said("vâng")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    await propose(_to_plan("tạo đề 10 câu tích phân lớp 12"))

    prompt = model.prompts[0]
    assert "{k.ten_field}" in prompt
    assert "{1.assessment_id}" in prompt
    # Và luật chống hỏi lại thứ vừa nghe: đo trên trình duyệt thật, model hỏi "phạm vi kiến
    # thức và số câu" cho một câu đã nói cả hai. Khối đọc được từ tên lớp, và nói ra điều ấy
    # là chỗ rẻ nhất để một lượt không chết vì một câu hỏi thừa.
    # Nguyên cụm, không hai chữ rời: "tên lớp" một mình luôn có nhờ câu *"không bịa tên lớp"* của
    # lõi, nên test cũ xanh cả khi luật này mất (review T2, `unbiased-model-text`).
    assert "con số đứng đầu tên lớp là khối" in prompt
    # Và luật "chỉ hỏi những mục bắt buộc": đo trên trình duyệt thật, model hỏi giáo viên có
    # muốn đặt tên cho đề không — một câu hỏi về một mục tuỳ chọn, tốn trọn một lượt.
    # Đo ba lần trên trình duyệt thật: model hỏi tên đề, rồi hỏi độ khó, rồi hỏi phạm vi
    # cho một câu đã nói phạm vi. Luật phải nói tuyệt đối — "đủ thì nêu plan NGAY" — chứ
    # không liệt kê từng mục không được hỏi. Từ ADR-29 (`draft-outline`) thứ nêu ngay là dàn ý,
    # và luật vẫn tuyệt đối như cũ.
    assert "NÊU DÀN Ý NGAY" in prompt
    # `question_count` thuộc `start_drafting`, không thuộc `create_draft`: gửi nó vào bước mở đề
    # là `vet_plan` từ chối trọn gói cả plan. Từ ngày 12/10/2026 skill `soan-de` viết thành quy
    # trình (người dùng chốt), nên luật ấy là **danh sách param của từng bước**, không còn là câu
    # *"ĐỦ BA mục"* -- và chính danh sách ấy là thứ test này canh.
    assert "create_draft — subject, grade, topic_scope" in prompt
    assert "start_drafting — assessment_id = {1.assessment_id}, question_count" in prompt
    # Mục tuỳ chọn không được hỏi: đo ba lần trên trình duyệt, model hỏi tên đề, rồi độ khó.
    assert "không cần gì nữa: độ khó, tên đề" in prompt
    # Và luật đi kèm: chỉ trỏ về phía sau. `vet_plan` từ chối một plan trỏ về phía trước,
    # nên không nói ra là để model tự tìm ra bằng cách bị từ chối.
    assert "ĐỨNG TRƯỚC" in prompt


@pytest.mark.asyncio
async def test_the_prompt_calls_the_two_catalogs_by_the_names_it_uses_for_them(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Luật và nhãn phải khớp nhau, vì chúng nằm ở hai chỗ khác nhau trong cùng một prompt.

    `_SYSTEM` dặn model chọn trong *"tool dùng ngay"* và *"tool nêu được trong plan"*;
    `_compose` mới là chỗ in hai tiêu đề ấy ra. Đổi tiêu đề mà quên sửa luật -- hoặc ngược
    lại -- để lại một prompt dặn model đọc một mục không tồn tại, và nó sẽ đoán mục nào là
    mục nào.
    """
    model = Scripted([_said("vâng")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    await propose(_to_plan("tạo đề 10 câu tích phân lớp 12"))

    prompt = model.prompts[0].lower()
    assert prompt.count("tool dùng ngay") >= 2
    assert prompt.count("tool nêu được trong plan") >= 2


@pytest.mark.asyncio
async def test_json_an_mat_dau_gach_cheo_trong_loi_kriky_noi(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    r"""Chữ Kriky nói trong khung chat đi qua cùng bộ sửa như chữ của đề bài.

    `authoring` không phải ống structured-output duy nhất. `_Proposal.text` cũng ra từ
    `with_structured_output`, cũng qua cùng bộ giải mã JSON, và cũng kết thúc trong
    `MathText` -- `Chat.tsx` dựng hình nó ở năm chỗ. Nên Kriky giải thích một công thức
    thì `\frac` thành form-feed y hệt, rồi dấu đô la lọt ra màn hình (ADR-26).

    Thiếu test này thì check `escape-repair-is-wired-in` là nơi thi hành duy nhất, mà một
    check đọc cây cú pháp chỉ nói được *có gọi hay không*, không nói được *gọi có đúng
    field hay không*.
    """
    model = Scripted(
        [
            _Proposal(
                kind="plan",
                text="Mình tính $\x0crac{1}{2} \x09imes 4$ nhé.",
                steps=(_Step(tool_name="create_draft", title="Tạo đề $\x0crac{1}{3}$"),),
            )
        ]
    )
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("tính giúp mình"))

    assert step.text == r"Mình tính $\frac{1}{2} \times 4$ nhé."
    assert step.steps[0].title == r"Tạo đề $\frac{1}{3}$"


@pytest.mark.asyncio
async def test_the_prompt_is_where_adr_23_reaches_the_real_model(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """ADR-23 trên đường model thật sống **chỉ** trong prompt này, nên nó phải đo được.

    Và nó đã mất một lần, lặng lẽ. Bản prompt trước dặn: *"khi một tool trả `ambiguous: true`
    kèm `candidates`, đó là lúc dùng ask_clarify"* — một điều kiện không tool nào còn trả về
    sau khi `find_class` tách thành `list_class` + `get_class`. Mock trong `handlers.py` đã
    được sửa sang `len(candidates) > 1`, nên **test và demo vẫn xanh trong khi đường thật
    hỏng**: gpt-4o-mini không thấy cờ nào khớp lời dặn thì nó tự chọn một lớp, hoặc tự liệt
    kê tên lớp trong một bước `say` — đúng hai việc ADR-23 cấm. Và `_offered` chỉ gắn nút vào
    `ask_clarify`, nên một bước `say` ra bong bóng chữ không nút.

    Ba khẳng định là ba nửa của cùng một luật: khi nào hỏi lại, ai viết các phương án, và
    `more` nghĩa là gọi lại tool chứ không phải bắt giáo viên gõ lại.
    """
    model = Scripted([_said("vâng")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    await propose(_asked("lớp 12 thế nào"))

    prompt = model.prompts[0]
    assert "ask_clarify" in prompt
    assert "candidates" in prompt
    # Không còn cờ nào đã chết: một điều kiện không tool nào trả về là một điều kiện không
    # bao giờ đúng, và model sẽ làm thứ gì đó khác.
    assert "ambiguous" not in prompt
    assert "your_classes" not in prompt
    # BE viết các phương án, model viết câu hỏi.
    assert "choices" in prompt
    # Và `more` có một đường ra, không chỉ một lời thừa nhận.
    assert "more" in prompt and "name" in prompt
