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

from types import SimpleNamespace

import pytest
from langchain_core.runnables import Runnable, RunnableLambda

from agent import llm
from agent.graphs.propose import _Argument, _Proposal, _Step, propose
from contracts import NextStepRequested, ToolSpec, TurnRecord

_CATALOG = (
    ToolSpec(
        name="find_class",
        description="Tìm lớp của giáo viên theo tên.",
        arguments={"name": "tên lớp, ví dụ 12A1"},
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
        tool_args=tuple(_Argument(name=key, value=value) for key, value in args.items()),
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
    model = Scripted([_wants("find_class", name="12A1")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("lớp 12A1 làm bài hôm qua thế nào"))

    assert step.kind == "call_tool"
    assert step.tool_name == "find_class"
    assert step.tool_args == {"name": "12A1"}


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
    assert "find_class" in prompt
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
            TurnRecord(kind="tool_call", tool_name="find_class", tool_args={"name": "12A1"}),
            TurnRecord(
                kind="tool_result",
                tool_name="find_class",
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
                            _Argument(name="subject", value="Toán"),
                            _Argument(name="question_count", value="10"),
                        ),
                        title="Tạo đề trống",
                    ),
                    _Step(
                        tool_name="start_drafting",
                        args=(_Argument(name="assessment_id", value="{1.assessment_id}"),),
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
    assert step.steps[0].args == {"subject": "Toán", "question_count": "10"}
    assert step.steps[1].args == {"assessment_id": "{1.assessment_id}"}
    assert [one.title for one in step.steps] == ["Tạo đề trống", "Soạn 10 câu hỏi"]


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
    assert "lớp 12A" in prompt and "khối" in prompt
    # Và luật "chỉ hỏi bốn mục bắt buộc": đo trên trình duyệt thật, model hỏi giáo viên có
    # muốn đặt tên cho đề không — một câu hỏi về một mục tuỳ chọn, tốn trọn một lượt.
    # Đo ba lần trên trình duyệt thật: model hỏi tên đề, rồi hỏi độ khó, rồi hỏi phạm vi
    # cho một câu đã nói phạm vi. Luật phải nói tuyệt đối — "đủ bốn mục thì nêu plan NGAY" —
    # chứ không liệt kê từng mục không được hỏi.
    assert "ĐỦ BỐN MỤC THÌ NÊU PLAN NGAY" in prompt
    assert "KHÔNG bắt buộc" in prompt
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
    thì `rac` thành form-feed y hệt, rồi dấu đô la lọt ra màn hình (ADR-26).

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
