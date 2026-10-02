"""Hình dạng của một plan, thứ hai service dựa vào để nói cùng một chuyện.

Mấy test này canh hợp đồng của ADR-25: pha 1 trả về một plan, pha 2 chạy nó, rồi một
task riêng kể lại kết quả. Chúng không kiểm pydantic — chúng kiểm những điều khoản mà
một lần sửa vô ý có thể phá mà không bên nào đỏ lên.
"""

import pytest
from pydantic import ValidationError

from contracts import (
    PROPOSE_NEXT_STEP_TASK,
    REPORT_PLAN_TASK,
    NextStepCompleted,
    PlanReportRequested,
    PlanStep,
    StepOutcome,
)


def test_a_plan_needs_at_least_one_step() -> None:
    """Một plan rỗng là một lượt không làm gì mà vẫn hứa sẽ làm."""
    with pytest.raises(ValidationError):
        NextStepCompleted(request_id="r1", kind="plan")


def test_a_plan_carries_the_sentence_said_before_the_work() -> None:
    """Artboard 4 nói một câu trước khối bước, nên plan phải chở được câu ấy."""
    step = PlanStep(tool_name="create_draft", args={}, title="Tạo đề trống")
    planned = NextStepCompleted(
        request_id="r1", kind="plan", text="Được, tôi bắt đầu nhé.", steps=(step,)
    )
    assert planned.text == "Được, tôi bắt đầu nhé."
    assert planned.steps[0].title == "Tạo đề trống"


def test_a_step_refuses_an_argument_that_is_not_a_string() -> None:
    """Model chỉ trả về được chuỗi phẳng, nên `{k.field}` là một chuỗi chứ không phải một kiểu.

    BE là bên duy nhất giải tham chiếu ấy. Nếu `args` nhận object thì structured output của
    nhà cung cấp từ chối cả schema, và chuyện đó đã được ghi ngay trong `propose.py`.
    """
    with pytest.raises(ValidationError):
        PlanStep(tool_name="start_drafting", args={"question_count": 10}, title="Soạn câu hỏi")


def test_a_step_without_a_title_is_refused() -> None:
    """Tiêu đề là thứ giáo viên đọc trên khối bằng chứng; thiếu nó thì bước không hiện được."""
    with pytest.raises(ValidationError):
        PlanStep(tool_name="create_draft", args={}, title="")


def test_a_step_without_a_tool_is_refused() -> None:
    with pytest.raises(ValidationError):
        PlanStep(tool_name="", args={}, title="Làm gì đó")


def test_the_report_task_is_not_the_thinking_task() -> None:
    """Báo cáo là một job riêng vì đầu vào của nó khác: kết quả của plan, không phải catalog.

    Test này canh được đúng một nửa của luật — hai tên không trùng nhau. Nửa còn lại, *một job
    một lời gọi model*, không check nào hôm nay bắt được, và ADR-25 đã nói thẳng điều đó; nó
    được mua bằng một check riêng ở Task 12 của plan.
    """
    assert REPORT_PLAN_TASK != PROPOSE_NEXT_STEP_TASK


def test_the_report_payload_carries_no_identifier_to_look_up() -> None:
    """AGENT không có credential database, nên payload phải tự chứa (ADR-25).

    Kiểm theo **hình dạng** chứ không theo một danh sách tên: thêm `draft_id` hay `thread_id`
    vào payload cũng là thêm một thứ AGENT không tra được, và một test liệt kê tên sẽ không
    thấy chúng.
    """
    fields = set(PlanReportRequested.model_fields)
    looked_up = {name for name in fields if name.endswith("_id") and name != "request_id"}
    assert looked_up == set()
    assert {"said", "outcomes"} <= fields


def test_a_report_of_a_refused_plan_carries_no_outcome() -> None:
    """Plan bị từ chối trước khi chạy bước nào thì không có bước nào để kể."""
    asked = PlanReportRequested(request_id="r1", said="tạo đề")
    assert asked.outcomes == ()


def test_a_step_cannot_be_rewritten_after_it_is_built() -> None:
    """Một message đi qua queue mà sửa được là một message hai bên đọc ra hai nghĩa.

    Gán thật rồi bắt lỗi, không chỉ đọc `model_config`: cờ ấy đúng mà hành vi sai thì test vẫn
    xanh, và chỗ hay sai nhất là một field được thêm sau mà quên mất cấu hình.
    """
    step = PlanStep(tool_name="create_draft", args={"subject": "Toán"}, title="Tạo đề trống")
    with pytest.raises(ValidationError):
        step.title = "Đổi tên"
    with pytest.raises(ValidationError):
        step.tool_name = "start_drafting"

    outcome = StepOutcome(title="Tạo đề trống", ok=True, detail="")
    with pytest.raises(ValidationError):
        outcome.ok = False


def test_only_a_plan_carries_steps() -> None:
    """Một `say` chở theo `steps` là hai câu trả lời trong một message.

    Chặn ở hợp đồng chứ không ở BE: nếu không, mọi nhánh của vòng lặp phải nhớ bỏ qua `steps`,
    và một luật phải nhớ là một luật sẽ quên.
    """
    step = PlanStep(tool_name="create_draft", args={}, title="Tạo đề trống")
    with pytest.raises(ValidationError):
        NextStepCompleted(request_id="r1", kind="say", text="xong rồi", steps=(step,))
