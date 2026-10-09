"""AGENT nộp nội dung, không nộp quyết định.

Đây là invariant *"AGENT emits no routing decision"* trong `AGENTS.md`. Nó từng được canh bởi một
test đọc `GradingCompleted` — thứ chỉ sống trên đường chấm bài cũ mà ADR-20 đã thay thế. Đường ấy
nay đã bị xoá, nên cái lưới cũ chết theo, dù **luật thì không chết**: nó là ràng buộc mà chương
kiến trúc của báo cáo đứng lên.

Bản đầu của tệp này quét `vars(agent.handlers)` và chỉ soi những hàm khai trả về một model. Nó
**hở đúng chỗ cần canh**: sáu điểm vào thật của arq đều khai `-> dict` (vì `AGENTS.md` của service
này bắt thế -- arq serialise kết quả vào Redis), nên không cái nào lọt vào tầm dò. Đã đo: nhét
`out["needs_teacher_review"] = True` vào `handlers.explain` thì bản cũ **vẫn xanh**.

Nên lưới nay căng ở hai lớp, và lớp ngoài mới là lớp thật:

- **Lớp ngoài** gọi thật từng task **đã đăng ký** rồi soi khoá của dict trả về. Dò từ
  `WorkerSettings.functions` chứ không từ namespace, vì danh sách ấy *chính là* sự đăng ký: một
  handler đặt ở module khác, hay bị một decorator bọc, vẫn phải đi qua đó. Và vì nó đo **kết quả**
  chứ không đo mã nguồn, một cái tên khoá dựng động cũng lộ.
- **Lớp trong** soi kiểu của mọi message AGENT khai sẽ trả về, đệ quy qua model lồng và mở cả
  `Optional`/union -- ba chỗ mà một trường phán xử có thể nấp.
"""

import inspect
import re
import typing
from collections.abc import Mapping, Sequence

import pytest

import agent.handlers as handlers
from agent import llm
from agent.worker import WorkerSettings
from contracts import (
    EXPLAIN_TURN_TASK,
    GENERATE_RETRY_QUESTION_TASK,
    NAME_CONVERSATION_TASK,
    PROPOSE_NEXT_STEP_TASK,
    REPORT_PLAN_TASK,
    WRITE_DRAFT_QUESTION_TASK,
    ConversationNameRequested,
    DraftQuestionRequested,
    ExplainTurnRequested,
    GeneratedOption,
    GeneratedQuestion,
    NextStepRequested,
    PlanReportRequested,
    RetryQuestionRequested,
    SolutionMethod,
    StepOutcome,
    ToolSpec,
    TurnRecord,
)

# Một cái tên nói rằng người gửi đã tự phán xử. Mẫu chứ không phải danh sách đóng: bản trước liệt
# đúng năm tên, nên `teacher_review_required` đi lọt mà không ai phải nghĩ lâu. Các gốc từ lấy theo
# `test_authoring.py::test_a_draft_reports_no_verdict`, test đã làm đúng việc này cho **một** hàm.
VERDICT = re.compile(
    r"score|confidence|review|verdict|misconception|approved|difficulty", re.IGNORECASE
)

_QUESTION = GeneratedQuestion(
    stem="Cho hàm số y = x³ − 3x. Hàm số đồng biến trên khoảng nào?",
    options=(
        GeneratedOption(label="A", text="Khoảng (−∞; −1)", is_correct=True),
        GeneratedOption(label="B", text="Khoảng (−1; 1)", error_label="đọc ngược khoảng"),
    ),
    methods=(
        SolutionMethod(title="Xét dấu đạo hàm", body="..."),
        SolutionMethod(title="Thử giá trị", body="..."),
    ),
    learning_objective="Tính đơn điệu của hàm bậc ba",
)

# Một payload tối thiểu cho mỗi task. Dựng tại chỗ chứ không import từ tệp test khác: một ràng buộc
# ngầm giữa hai tệp không liên quan là thứ sẽ gãy vào lúc không ai ngờ.
PAYLOADS: dict[str, dict] = {
    WRITE_DRAFT_QUESTION_TASK: DraftQuestionRequested(
        request_id="de-1:1:1",
        subject="Toán",
        grade="12",
        topic_scope="Tính đơn điệu",
        ordinal=1,
        of_total=1,
        # Có channel thì `_arm_bell` mới lên dây chuông, và chỉ khi ấy việc soi `ring_bell`
        # ở dưới mới soi được gì. Thiếu dòng này thì chuông im và lưới gật đầu với một
        # tiếng chuông chở quyết định.
        progress_channel="progress:de-1",
    ).model_dump(mode="json"),
    GENERATE_RETRY_QUESTION_TASK: RetryQuestionRequested(
        request_id="lam-1:1",
        origin=_QUESTION,
        wrong_option_label="B",
        round_index=1,
    ).model_dump(mode="json"),
    # Ba payload dưới cố ý **đầy**. Bản mỏng của chúng rơi vào nhánh "chưa có gì để nói" --
    # một câu chào, một câu "chưa làm được bước nào" -- và một kết quả rỗng thì không chứng
    # minh được gì về hình dạng kết quả thật.
    EXPLAIN_TURN_TASK: ExplainTurnRequested(
        request_id="chat-1",
        questions=(_QUESTION,),
        question_numbers=(1,),
        chosen_labels={_QUESTION.stem: "B"},
        error_labels={_QUESTION.stem: "đọc ngược khoảng"},
        student_text="Em chưa hiểu vì sao đáp án B sai.",
    ).model_dump(mode="json"),
    PROPOSE_NEXT_STEP_TASK: NextStepRequested(
        request_id="gv-1",
        teacher_name="Cô Lan",
        catalog=(ToolSpec(name="list_class", description="Liệt kê lớp của giáo viên"),),
        history=(TurnRecord(kind="teacher", text="Lớp nào đang học đạo hàm?"),),
    ).model_dump(mode="json"),
    REPORT_PLAN_TASK: PlanReportRequested(
        request_id="gv-2",
        said="tạo đề",
        outcomes=(
            StepOutcome(title="Mở đề nháp", ok=True),
            StepOutcome(title="Soạn câu 3", ok=False, detail="model trả về câu thiếu lời giải"),
        ),
        written=2,
    ).model_dump(mode="json"),
    NAME_CONVERSATION_TASK: ConversationNameRequested(
        request_id="gv-3",
        said="tạo đề",
    ).model_dump(mode="json"),
}


class _Loa:
    """Một Redis giả chỉ biết ghi lại mọi thứ được phát ra."""

    def __init__(self, sổ: list) -> None:
        self._sổ = sổ

    async def publish(self, channel: str, message: object) -> None:
        """Ghi lại một lần phát thay vì gửi đi đâu."""
        self._sổ.append((channel, message))


@pytest.fixture(autouse=True)
def off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tắt đường model cho mọi test trong tệp này.

    Bắt buộc, không phải cho gọn: `conftest.py` chỉ thay `llm.chat_models`, **không** thay
    `llm.enabled`, nên `llm.enabled()` đọc `.env` của máy đang chạy. Thiếu dòng dưới thì trên một
    máy có `LLM_ENABLED=true` test này đi nhánh gọi model và xanh vì một lý do khác hẳn lý do nó
    được viết ra. Cùng cái bẫy mà `test_propose_handler.py` đã ghi lại.
    """
    monkeypatch.setattr(llm, "enabled", lambda: False)


def _registered() -> dict[str, object]:
    """Các task arq thật sự đăng ký, theo tên.

    Returns:
        Ánh xạ từ tên task sang coroutine chạy nó.
    """
    return {one.name: one.coroutine for one in WorkerSettings.functions}


def _verdicts_in(value: object, path: str = "") -> set[str]:
    """Mọi chỗ mang tên phán xử trong một cấu trúc đã serialise, kể cả khoá lồng.

    Soi **cả khoá lẫn giá trị chuỗi**, vì một quyết định không nhất thiết phải là một trường:
    ghép `"needs_teacher_review=true"` vào cuối một câu trả lời cũng là phát ra nó, và một list
    các cặp `{"name": ..., "value": ...}` thì khoá chỉ là `name`/`value`. Đi qua `Mapping` và
    `Sequence` chứ không riêng `dict`/`list`, vì một `UserDict` vẫn qua được arq.

    Args:
        value: Một mapping, một dãy, hoặc một giá trị lá.
        path: Đường đi đã qua, dùng để thông báo chỉ đúng chỗ.

    Returns:
        Tập các đường dẫn tới chỗ vi phạm.
    """
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, inner in value.items():
            here = f"{path}.{key}" if path else str(key)
            if VERDICT.search(str(key)):
                found.add(here)
            found |= _verdicts_in(inner, here)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            found |= _verdicts_in(item, f"{path}[]")
    elif isinstance(value, str) and VERDICT.search(value):
        found.add(f"{path}=<{value[:40]}>")
    return found


def _fields_of(annotation: object, seen: frozenset[object] = frozenset()) -> set[str]:
    """Mọi tên trường của một model, đệ quy qua model lồng và qua union.

    Args:
        annotation: Một annotation trả về bất kỳ.
        seen: Các kiểu đã đi qua, để một model tự tham chiếu không làm hàm chạy mãi.

    Returns:
        Tập tên trường, mỗi cái có tiền tố là đường đi tới nó.
    """
    if annotation in seen:
        return set()
    seen = seen | {annotation}

    parts = typing.get_args(annotation)
    if parts:
        return {name for part in parts for name in _fields_of(part, seen)}

    if not hasattr(annotation, "model_fields"):
        return set()

    names: set[str] = set()
    for field, spec in annotation.model_fields.items():
        names.add(field)
        names |= {f"{field}.{deeper}" for deeper in _fields_of(spec.annotation, seen)}
    return names


def test_every_registered_task_has_a_payload_here() -> None:
    """Một task mới phải kéo theo payload, nếu không hai test dưới bỏ sót nó."""
    assert set(_registered()) == set(PAYLOADS), (
        "WorkerSettings.functions và PAYLOADS lệch nhau; thêm payload cho task mới"
    )


def test_the_queue_has_no_second_door() -> None:
    """Không đường đăng ký nào khác, vì `_registered()` chỉ nhìn `functions`.

    arq còn chạy `cron_jobs` và `after_job_end`. Một task đặt ở đó vẫn phát ra Redis mà lưới
    trên không thấy, nên hai cửa ấy phải đóng -- hoặc được canh riêng.
    """
    assert not getattr(WorkerSettings, "cron_jobs", []), (
        "có cron job: thêm nó vào PAYLOADS hoặc canh riêng"
    )
    assert WorkerSettings.after_job_end is handlers.ring_bell, (
        "after_job_end đổi rồi; kiểm xem thứ nó phát ra có mang quyết định không"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("model_on", [False, True], ids=["mô hình tắt", "mô hình bật"])
async def test_no_registered_task_returns_a_verdict(
    monkeypatch: pytest.MonkeyPatch, model_on: bool
) -> None:
    """Lớp ngoài: thứ thật sự lên queue không mang một quyết định nào.

    Chạy **hai lần**, và lần thứ hai mới là lần đáng giá. Cả sáu handler mở đầu bằng
    `if not llm.enabled(): return <đường dọn sẵn>`, nên nếu chỉ chạy với model tắt thì toàn bộ
    mã sau dòng ấy -- tức đúng đường chạy thật -- chưa bao giờ bị soi. Lần bật dùng model giả
    của `conftest.py`, nên vẫn không cần mạng và không cần khoá nào.

    Chuông tiến độ cũng được soi ở đây: nó là một kênh **ra Redis thật**, và một quyết định đi
    qua đó thì không có mặt trong giá trị trả về.
    """
    monkeypatch.setattr(llm, "enabled", lambda: model_on)
    rung: list[tuple[str, object]] = []
    ctx: dict = {"redis": _Loa(rung)}

    for name, run in _registered().items():
        answer = await run(ctx, PAYLOADS[name])

        assert type(answer) is dict, f"task {name} trả {type(answer).__name__}, không phải dict"
        offenders = _verdicts_in(answer)
        assert not offenders, f"task {name} nộp một quyết định: {sorted(offenders)}"

        await handlers.ring_bell(ctx)
        heard = {chỗ for channel, message in rung for chỗ in _verdicts_in([channel, message])}
        assert not heard, f"task {name} rung một quyết định ra Redis: {sorted(heard)}"


def test_no_message_agent_returns_declares_a_verdict_field() -> None:
    """Lớp trong: không kiểu message nào AGENT khai trả về có chỗ để đặt một phán xử."""
    returned = {
        name: typing.get_type_hints(fn).get("return")
        for name, fn in vars(handlers).items()
        if not name.startswith("_") and inspect.isfunction(fn)
    }
    # Chốt đếm **số hàm trả về một message**, không đếm số hàm có annotation. Phần lớn hàm ở
    # đây khai `-> dict` hoặc `-> str`, nên đếm kiểu sau cho một con số to mà rỗng nghĩa: mọi
    # message có thể biến mất khỏi module và chốt vẫn qua.
    checked = {
        name: hint for name, hint in returned.items() if hint is not None and _fields_of(hint)
    }
    assert len(checked) >= 6, f"chỉ dò được {len(checked)} hàm trả message, phép dò đã hỏng"

    offenders = {
        f"{name}.{field}"
        for name, hint in checked.items()
        for field in _fields_of(hint)
        if VERDICT.search(field.rsplit(".", 1)[-1])
    }
    assert not offenders, f"AGENT khai một trường phán xử: {sorted(offenders)}"
