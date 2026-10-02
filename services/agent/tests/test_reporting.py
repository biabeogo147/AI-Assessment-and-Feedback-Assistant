"""Lời kể sau khi một plan đã chạy: đường model, đường mock, và đường hỏng.

Task này chạy ở **cuối** một lượt, sau khi mọi bước ghi đã commit. Vì thế thứ đáng kiểm
không phải câu chữ — một câu khô vẫn là một câu — mà là ba đường ra của nó đều trả về một
`PlanReportCompleted` hợp lệ. Một exception thoát ra từ đây sẽ biến một lượt đã làm xong
việc thành một lỗi, và giáo viên sẽ thấy một đề có câu hỏi kèm một thông báo thất bại.

Thứ thứ hai đáng kiểm: model **thấy** kết quả từng bước. Một lời kể được viết mà không
đọc kết quả thì không phải lời kể, nó là một câu chúc mừng.
"""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from agent import handlers, llm
from contracts import PlanReportRequested, StepOutcome

DONE = PlanReportRequested(
    request_id="r1",
    said="Tạo đề 10 câu về tích phân cho 12A1",
    outcomes=(
        StepOutcome(title="Tạo đề 10 câu", ok=True, detail='đề "Tích phân 12A1", cần 10 câu'),
        StepOutcome(title="Soạn 10 câu hỏi", ok=True, detail="10 câu bắt đầu soạn"),
    ),
)

BROKE = PlanReportRequested(
    request_id="r2",
    said="Tạo đề 10 câu về tích phân cho 12A1",
    outcomes=(
        StepOutcome(title="Tạo đề 10 câu", ok=True, detail='đề "Tích phân 12A1", cần 10 câu'),
        StepOutcome(title="Soạn 10 câu hỏi", ok=False, detail="chưa làm được bước này"),
    ),
)


@pytest.fixture
def on(monkeypatch):
    """Bật đường model mà không cần API key nào."""
    monkeypatch.setattr(llm, "enabled", lambda: True)


@pytest.mark.asyncio
async def test_the_model_writes_the_closing_line(on, monkeypatch) -> None:
    """Đường thường: model trả về gì thì handler trả về đúng thứ đó, nguyên văn."""
    monkeypatch.setattr(
        llm,
        "chat_models",
        lambda: (GenericFakeChatModel(messages=iter(["Mình đã mở đề và đang soạn 10 câu."])),),
    )

    answer = await handlers.report_plan({}, DONE.model_dump(mode="json"))

    assert answer["text"] == "Mình đã mở đề và đang soạn 10 câu."
    assert answer["request_id"] == "r1"


@pytest.mark.asyncio
async def test_the_model_is_shown_what_each_step_did(on, monkeypatch) -> None:
    """Prompt phải chở kết quả từng bước, kèm dấu cho biết bước nào hỏng.

    Không có chúng thì model đang viết một lời kể về một việc nó không biết đã xảy ra hay
    chưa — và lời kể ấy sẽ luôn nghe như thành công, vì đó là hình dạng mặc định của một
    câu tổng kết.
    """
    seen: list[str] = []

    def listen(messages):
        seen.append("\n".join(str(message.content) for message in messages))
        return AIMessage(content="Mình dừng giữa đường.")

    # Một `RunnableLambda` chứ không một `GenericFakeChatModel` phân lớp lại: đường chạy là
    # `ainvoke`, và model giả kia không đi qua `_call` khi được gọi async, nên một listener
    # gắn vào đó nghe được đúng một chuỗi rỗng.
    monkeypatch.setattr(llm, "chat_models", lambda: (RunnableLambda(listen),))

    await handlers.report_plan({}, BROKE.model_dump(mode="json"))

    prompt = "\n".join(seen)
    assert "Tạo đề 10 câu về tích phân cho 12A1" in prompt
    assert "1. Tạo đề 10 câu: xong" in prompt
    assert "2. Soạn 10 câu hỏi: HỎNG" in prompt
    assert "chưa làm được bước này" in prompt


@pytest.mark.asyncio
async def test_a_dev_box_without_a_key_still_gets_a_closing_line(monkeypatch) -> None:
    """`LLM_ENABLED=false` không được để lượt kết thúc trong im lặng.

    Mock ghép từ chính `outcomes`, nên nó không thể nói quá: nó không có gì ngoài những
    dòng BE đã viết.
    """
    monkeypatch.setattr(llm, "enabled", lambda: False)

    answer = await handlers.report_plan({}, DONE.model_dump(mode="json"))

    assert answer["text"] == "Mình đã tạo đề 10 câu; soạn 10 câu hỏi."


@pytest.mark.asyncio
async def test_the_mock_says_where_it_stopped(monkeypatch) -> None:
    """Một plan hỏng giữa chừng phải đọc ra là hỏng, kể cả ở đường mock.

    Đây là ca mock dễ nói sai nhất: ghép hết các title lại rồi mừng công là cách một
    lượt dừng ở bước hai được kể như một lượt xong cả hai bước.
    """
    monkeypatch.setattr(llm, "enabled", lambda: False)

    answer = await handlers.report_plan({}, BROKE.model_dump(mode="json"))

    assert answer["text"] == (
        "Mình đã tạo đề 10 câu, nhưng dừng ở bước soạn 10 câu hỏi (chưa làm được bước này)."
    )


@pytest.mark.asyncio
async def test_a_model_that_dies_still_gets_a_closing_line(on, monkeypatch) -> None:
    """Model ném lỗi thì lùi về mock, không ném tiếp lên trên.

    Phép kiểm đáng giá nhất trong file: lúc task này chạy, đề đã được mở và các câu đã
    bắt đầu soạn. Một exception thoát ra đây làm giáo viên đọc một thất bại trong khi
    database nói ngược lại.
    """

    async def dies(request):
        raise RuntimeError("model đi vắng")

    monkeypatch.setattr(handlers, "tell_about", dies)

    answer = await handlers.report_plan({}, DONE.model_dump(mode="json"))

    assert answer["text"] == "Mình đã tạo đề 10 câu; soạn 10 câu hỏi."


def test_the_report_task_is_registered_under_the_name_be_enqueues() -> None:
    """Một task không ai tiêu thụ là một luật tự tắt mà không ai thấy.

    Rớt dòng đăng ký thì BE vẫn enqueue `report_plan`, `run_task` chờ hết giờ, `_report`
    nuốt lỗi và lùi về câu ghép của BE. Lượt chat vẫn xong, không có log đỏ nào ở FE — chỉ
    là câu kết **vĩnh viễn** do BE viết, và luật "câu kết do model viết" của ADR-25 im lặng
    biến mất. Đây là lưới rẻ nhất cho nó; `tools/check_contract.py` sẽ canh phần còn lại
    (luật "báo cáo là một job riêng").
    """
    from agent.worker import WorkerSettings
    from contracts import REPORT_PLAN_TASK

    registered = {one.name: one for one in WorkerSettings.functions}
    assert REPORT_PLAN_TASK in registered
    assert registered[REPORT_PLAN_TASK].coroutine is handlers.report_plan


@pytest.mark.asyncio
async def test_the_prompt_forbids_saying_more_than_the_results_say(on, monkeypatch) -> None:
    """Luật nặng nhất của file này phải có một nơi thi hành.

    Model không thấy đề và không thấy câu hỏi nào — nó chỉ thấy một dãy `ok` và một dòng
    chi tiết. Và câu nó viết đi **thẳng** ra bong bóng chat: BE chỉ `.strip()`. Nên luật
    "không nhận xét chất lượng, không nói một con số không có trong kết quả" là cái lưới
    duy nhất, và một lần dọn prompt làm mất nó thì không gì đỏ lên.
    """
    seen: list[str] = []

    def listen(messages):
        seen.append("\n".join(str(message.content) for message in messages))
        return AIMessage(content="Mình đã mở đề.")

    monkeypatch.setattr(llm, "chat_models", lambda: (RunnableLambda(listen),))

    await handlers.report_plan({}, DONE.model_dump(mode="json"))

    prompt = "\n".join(seen)
    assert "không nhận xét về chất lượng" in prompt
    assert "không nói một con số không có trong kết quả" in prompt
    assert "đang soạn" in prompt
