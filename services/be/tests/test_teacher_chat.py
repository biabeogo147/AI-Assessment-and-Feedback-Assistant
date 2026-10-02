"""Vòng lặp tool, và hai thứ không bao giờ được phụ thuộc vào model.

BE sở hữu vòng lặp này. AGENT được hỏi bước tiếp theo là gì, mỗi bước một lần, và
BE quyết định có làm hay không. Cách bố trí đó tồn tại để hai tính chất luôn đúng
bất kể model xử sự thế nào:

- **Việc phân quyền chạy ở nơi có session.** Một đề xuất nêu tên lớp của giáo viên
  khác bị executor từ chối, không phải bị prompt từ chối.
- **Vòng lặp có điểm dừng.** Một model cứ xin tool mãi sẽ bị một mức trần cắt
  ngang, và giáo viên được nói cho biết, chứ không bị bỏ lại với một request không
  bao giờ trở về.

Mọi test ở đây đều viết kịch bản cho AGENT thay vì gọi nó thật, đúng như
`test_core_flow.py` làm: ranh giới chính là gateway, và một test thò tay vào
worker sẽ là vết nứt đầu tiên trên bức tường giữa các service.
"""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import teacher_chat
from be.config import get_settings
from be.db import bind_sessions, prepare_schema
from be.identity import Asking
from be.models import (
    Assessment,
    AssessmentState,
    SchoolClass,
    Student,
    Teacher,
    TeacherConversation,
    TeacherTurn,
)
from be.seed import seed_if_empty
from be.teacher_chat import router as teacher_router
from be.teacher_tools import UnknownTool, execute
from contracts import (
    NAME_CONVERSATION_TASK,
    REPORT_PLAN_TASK,
    ConversationNameCompleted,
    NextStepCompleted,
    PlanReportCompleted,
    PlanStep,
)

TEACHER = {"X-Actor": "teacher:GV-001"}
STRANGER = {"X-Actor": "teacher:GV-002"}


class ScriptedAgent:
    """Trả lời từng bước của vòng lặp bằng một đề xuất đã xếp hàng sẵn.

    Ghi lại những gì nó được hỏi, vì history mà BE gửi đi là cách duy nhất để
    model biết một tool đã trả về gì — và một vòng lặp quên gửi nó sẽ quay tới sát
    mức trần ở mọi lượt mà nhìn từ bên ngoài vẫn thấy đúng.
    """

    def __init__(self, *steps: NextStepCompleted) -> None:
        self.steps = list(steps)
        self.asked: list[dict] = []
        self.reported: list[dict] = []

    async def __call__(self, pool, settings, task_name, payload) -> dict:
        # Một cái cửa, nhiều loại việc. Từ khi BE nhờ AGENT đặt tên đoạn chat, bản giả
        # phải phân việc y như cái cửa thật — và việc đặt tên **không** vào `asked`, vì
        # `asked` nghĩa là "trợ lý đã được hỏi những gì", không phải "đã có bao nhiêu job".
        if task_name == NAME_CONVERSATION_TASK:
            return ConversationNameCompleted(
                request_id=payload["request_id"], title="tên do model đặt"
            ).model_dump(mode="json")
        if task_name == REPORT_PLAN_TASK:
            # Lời kể cuối lượt cũng là một job riêng, nên bản giả phải biết nó —
            # và nó cũng không vào `asked`, vì nó không phải một lần trợ lý được hỏi
            # "làm gì tiếp".
            self.reported.append(payload)
            return PlanReportCompleted(
                request_id=payload["request_id"], text="Mình đã làm xong các bước."
            ).model_dump(mode="json")
        self.asked.append(payload)
        step = (
            self.steps.pop(0)
            if self.steps
            else NextStepCompleted(
                request_id=payload["request_id"], kind="say", text="hết kịch bản"
            )
        )
        return step.model_copy(update={"request_id": payload["request_id"]}).model_dump(mode="json")


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """Một app có giáo viên thứ hai, để "không phải của tôi" là một ca thật sự tồn tại."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        stranger = Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002")
        session.add(stranger)
        await session.flush()
        session.add(SchoolClass(teacher_id=stranger.id, name="11B"))
        session.add(
            Assessment(
                teacher_id=stranger.id,
                title="Đề của người khác",
                subject="Toán",
                grade="11",
                state=AssessmentState.PUBLISHED,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

    app = FastAPI()
    app.include_router(teacher_router)
    app.state.queue_pool = object()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker, monkeypatch

    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _teacher(maker, code: str) -> Teacher:
    async with maker() as session:
        found = await session.scalar(select(Teacher).where(Teacher.teacher_code == code))
        assert found is not None
        return found


def _request():
    """Một `Request` đủ cho `run_turn`: nó chỉ đọc `app.state.queue_pool`."""

    class _App:
        state = SimpleNamespace(queue_pool=object())

    return SimpleNamespace(app=_App())


@pytest.mark.asyncio
async def test_a_turn_runs_a_tool_and_then_answers(stack) -> None:
    """Đường đi bình thường: hỏi, chạy, hỏi lại, trả lời.

    Khẳng định đáng giá là cái thứ hai — kết quả của tool có tới được câu hỏi thứ
    hai hay không. Đó là thứ ngăn model lặp lại chính nó, và nó không nhìn thấy
    được từ câu trả lời cuối.
    """
    client, _, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x", kind="call_tool", tool_name="find_class", tool_args={"name": "12A"}
        ),
        NextStepCompleted(request_id="x", kind="say", text="Lớp 12A có 40 học sinh."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12A thế nào"}, headers=TEACHER
    )

    assert reply.status_code == 200
    body = reply.json()
    assert body["kind"] == "say"
    assert body["text"] == "Lớp 12A có 40 học sinh."

    kinds = [turn["kind"] for turn in body["turns"]]
    assert kinds == ["teacher", "tool_call", "tool_result", "assistant"]

    second_question = agent.asked[1]
    results = [turn for turn in second_question["history"] if turn["kind"] == "tool_result"]
    assert results and results[0]["tool_result"]["name"] == "12A"


@pytest.mark.asyncio
async def test_the_loop_stops_at_its_ceiling_and_says_so(stack) -> None:
    """Một model chỉ biết xin tool sẽ bị cắt ngang, và cắt ra tiếng.

    Im lặng mới là cái hỏng tệ hơn: giáo viên sẽ bị bỏ lại với một request không
    bao giờ trở về, và không dòng log nào nêu ra nguyên nhân.
    """
    client, _, monkeypatch = stack
    forever = ScriptedAgent(
        *[
            NextStepCompleted(
                request_id="x", kind="call_tool", tool_name="find_class", tool_args={"name": "12A"}
            )
            for _ in range(20)
        ]
    )
    monkeypatch.setattr(teacher_chat, "run_task", forever)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12A thế nào"}, headers=TEACHER
    )

    assert reply.status_code == 200
    body = reply.json()
    assert body["kind"] == "say"
    # Đúng câu của mức trần, không phải một câu nào cũng được. `ScriptedAgent`
    # `fallback` sang nói "hết kịch bản" khi hết kịch bản, nên một test chỉ kiểm
    # rằng text không rỗng sẽ báo "mức trần hoạt động tốt" sau một lượt chạy mà
    # mức trần chưa hề bị chạm tới.
    assert body["text"] == teacher_chat._CEILING_REACHED
    # Đúng con số đã cấu hình, và đọc ra từ config. `<= 8` sẽ cho qua một vòng lặp
    # chỉ chạy một lần, còn viết cứng số 8 sẽ âm thầm xanh với bất cứ ai hạ giá trị
    # cấu hình đó xuống.
    assert len(forever.asked) == get_settings().max_tool_steps


@pytest.mark.asyncio
async def test_the_options_are_written_by_be_not_by_the_model(stack) -> None:
    """BE dựng các phương án từ những dòng chính nó đã đọc; phương án của model bị bỏ.

    ADR-05 đòi các phương án trong một câu hỏi làm rõ phải tới từ dữ liệu do hệ
    thống cung cấp, và đây là cách duy nhất để *có* tính chất đó thay vì chỉ xấp xỉ
    nó. Lọc lại những gì model viết là cách thử đầu tiên, và nó rò theo cả hai
    hướng: "12A-1" được cho qua nhờ có một "12A" thật, trong khi một "12A 3 học
    sinh" hợp lệ thì bị ném đi. Cả hai đều được đo thật, không phải tưởng tượng ra.

    Vậy nên model viết câu hỏi và BE viết các câu trả lời. Không có đoạn văn nào để
    lọc, và một tên lớp bịa ra không còn đường nào lên tới màn hình.
    """
    client, maker, monkeypatch = stack
    async with maker() as session:
        mine = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        assert mine is not None
        second = SchoolClass(teacher_id=mine.id, name="12B")
        session.add(second)
        await session.flush()
        session.add(
            Student(class_id=second.id, full_name="Ngô Thị Hai", student_code="HS2026-7001")
        )
        await session.commit()

    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x", kind="call_tool", tool_name="find_class", tool_args={"name": "12"}
        ),
        NextStepCompleted(
            request_id="x",
            kind="ask_clarify",
            text="Bạn muốn xem lớp nào?",
            # Mỗi cái trong số này sai một kiểu khác nhau: một tên thật kèm số học
            # sinh sai, một tên lệch một ký tự so với tên thật, và một lớp chưa bao
            # giờ tồn tại. Không cái nào tới được giáo viên, vì không cái nào được
            # hỏi đến.
            choices=("12A (45 học sinh)", "12A-1", "11C"),
        ),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12 thế nào"}, headers=TEACHER
    )

    assert reply.status_code == 200
    body = reply.json()
    assert body["kind"] == "ask_clarify"
    # Đúng hai dòng khớp với "12", kèm số học sinh do BE đếm — không phải con số 45
    # model khai, và không có hai lớp nó bịa ra.
    assert body["choices"] == ["12A (3 học sinh)", "12B (1 học sinh)"]
    assert body["more_choices"] == 0
    # Câu hỏi thì vẫn là lời của model. Nó viết câu hỏi; BE viết các câu trả lời.
    assert body["text"] == "Bạn muốn xem lớp nào?"


@pytest.mark.asyncio
async def test_a_tool_outside_the_catalog_is_refused(stack) -> None:
    """Catalog chỉ là thứ cho tiện; executor mới là cái cổng.

    Model đọc catalog, và model thì đọc sai. Một đề xuất nêu tên một tool chưa bao
    giờ được chào mời không được phép chạy chỉ vì nó tới với hình dạng đúng.
    """
    client, _, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x", kind="call_tool", tool_name="delete_everything", tool_args={}
        ),
        NextStepCompleted(request_id="x", kind="say", text="Mình chưa làm được việc đó."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "xoá hết đi"}, headers=TEACHER
    )

    assert reply.status_code == 200
    results = [turn for turn in reply.json()["turns"] if turn["kind"] == "tool_result"]
    assert results and "error" in results[0]["tool_result"]


@pytest.mark.asyncio
async def test_a_tool_cannot_reach_another_teachers_class(stack) -> None:
    """Việc giới hạn phạm vi xảy ra lúc thực thi, khi đã có dòng dữ liệu trong tay.

    ADR-22: câu trả lời cho một lớp thuộc về người khác giống y câu trả lời cho một
    lớp không tồn tại. Hai câu trả lời khác nhau sẽ cho bất cứ ai vẽ được bản đồ
    các lớp của trường chỉ bằng cách xem câu nào quay về.
    """
    _, maker, _ = stack
    mine = await _teacher(maker, "GV-001")

    async with maker() as session:
        theirs = await session.scalar(select(SchoolClass).where(SchoolClass.name == "11B"))
        assert theirs is not None

        me = Asking.of(mine)
        my_own = await execute(session, me, "find_class", {"name": "12A"})
        by_name = await execute(session, me, "find_class", {"name": "11B"})
        missing = await execute(session, me, "find_class", {"name": "lớp nào tên này"})

    # Không có khẳng định đầu tiên này, test vẫn xanh với một `find_class` chẳng bao
    # giờ tìm thấy gì: hai lời từ chối bên dưới là cùng một hằng số, nên đem chúng so
    # với nhau chỉ chứng minh được rằng một hằng số bằng chính nó.
    assert my_own["found"] is True
    assert my_own["name"] == "12A"

    assert by_name == missing


@pytest.mark.asyncio
async def test_an_unknown_tool_raises_rather_than_returning_nothing(stack) -> None:
    """`execute` phân biệt "không có tool nào như thế" với "không tìm thấy gì".

    Vòng lặp biến cái thứ nhất thành một kết quả mà model đọc được và hồi lại được.
    Gộp chúng lại sẽ làm một lỗi đánh máy trông như một lớp rỗng.
    """
    _, maker, _ = stack
    mine = await _teacher(maker, "GV-001")

    async with maker() as session:
        with pytest.raises(UnknownTool):
            await execute(session, Asking.of(mine), "no_such_tool", {})


def _plan(*steps: PlanStep, text: str = "Được, tôi bắt đầu nhé.") -> NextStepCompleted:
    """Một plan như model trả về ở cuối pha 1."""
    return NextStepCompleted(request_id="x", kind="plan", text=text, steps=steps)


_BRIEF = {
    "subject": "Toán",
    "grade": "12",
    "topic_scope": "chương Hàm số",
    "question_count": "3",
}


@pytest.mark.asyncio
async def test_a_plan_passes_the_id_from_one_step_into_the_next(stack) -> None:
    """Đường đi hạnh phúc của hai pha: lên plan, chạy, rồi kể lại.

    Bước hai lấy `assessment_id` từ bước một bằng `{1.assessment_id}` — không có cú pháp ấy
    thì một plan hai bước phụ thuộc nhau không diễn tả được, và đó là chỗ ADR-25 đứng hoặc đổ.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _plan(
            PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống"),
            PlanStep(
                tool_name="start_drafting",
                args={"assessment_id": "{1.assessment_id}"},
                title="Soạn câu hỏi",
            ),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    answer = await http.post(
        "/api/teacher/chat/messages", json={"text": "Tạo đề 3 câu Hàm số"}, headers=TEACHER
    )

    assert answer.status_code == 200
    body = answer.json()
    assert body["text"] == "Mình đã làm xong các bước."

    kinds = [turn["kind"] for turn in body["turns"]]
    assert kinds == [
        "teacher",
        "assistant",  # câu nói trước khi bắt tay
        "plan",  # danh sách việc, lưu lại để F5 dựng lại được `bước k/n`
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "assistant",  # lời kể cuối lượt
    ]

    # Plan lưu đủ để vẽ khối bằng chứng mà không cần đoán: tiêu đề từng bước và tổng số.
    kept = next(turn for turn in body["turns"] if turn["kind"] == "plan")
    assert kept["tool_result"] == {"steps": ["Tạo đề trống", "Soạn câu hỏi"], "total": 2}

    # Bước hai nhận đúng id mà bước một vừa sinh ra: đó là cả điểm của `{1.assessment_id}`.
    # Đọc từ bảng, vì `tool_args` cố ý không đi ra tới client — màn hình không cần tham số
    # của một tool, và thứ không cần thì không gửi.
    made = next(turn for turn in body["turns"] if turn["kind"] == "tool_result")
    assert made["tool_result"]["assessment_id"]
    async with maker() as session:
        calls = list(
            await session.scalars(
                select(TeacherTurn)
                .where(TeacherTurn.kind == "tool_call")
                .order_by(TeacherTurn.sequence)
            )
        )
    assert [one.tool_name for one in calls] == ["create_draft", "start_drafting"]
    assert calls[1].tool_args["assessment_id"] == made["tool_result"]["assessment_id"]

    # Lời kể nhận đủ hai bước, theo đúng thứ tự, dưới dạng kết quả chứ không phải một bản
    # tóm tắt do BE viết. Bước hai báo hỏng ở harness này vì `app.state.queue_pool` là một
    # `object()` trần — không có hàng đợi thì không đẩy job được, và đó là một kết quả
    # thật chứ không phải một lỗi của test.
    assert len(agent.reported) == 1
    titles = [one["title"] for one in agent.reported[0]["outcomes"]]
    assert titles == ["Tạo đề trống", "Soạn câu hỏi"]
    assert agent.reported[0]["outcomes"][0]["ok"] is True


@pytest.mark.asyncio
async def test_a_failed_step_stops_the_plan_and_still_reports(stack) -> None:
    """Một bước hỏng thì các bước sau không chạy, nhưng lời kể vẫn phải tới.

    Im lặng ở đây là thứ tệ nhất: giáo viên vừa nhờ một việc, một nửa đã xảy ra, và màn
    hình không nói nửa nào.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _plan(
            # Thiếu `topic_scope` và `question_count`: `create_draft` từ chối, không ghi gì.
            PlanStep(
                tool_name="create_draft",
                args={"subject": "Toán", "grade": "12"},
                title="Tạo đề trống",
            ),
            PlanStep(
                tool_name="start_drafting",
                args={"assessment_id": "{1.assessment_id}"},
                title="Soạn câu hỏi",
            ),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    answer = await http.post(
        "/api/teacher/chat/messages", json={"text": "Tạo giúp tôi một đề"}, headers=TEACHER
    )

    assert answer.status_code == 200
    kinds = [turn["kind"] for turn in answer.json()["turns"]]
    # Đúng MỘT cặp tool_call/tool_result: bước hai không chạy.
    assert kinds.count("tool_call") == 1

    outcomes = agent.reported[0]["outcomes"]
    assert len(outcomes) == 1
    assert outcomes[0]["ok"] is False

    # Lời kể nói bằng lời người, không chở chữ viết cho model. `reason` của `create_draft`
    # là "chưa đủ thông tin để soạn đề; hãy hỏi giáo viên những mục còn thiếu" — một câu
    # dặn model, và in nó ra là để giáo viên đọc trợ lý nói về mình ở ngôi thứ ba. Tên
    # field thì càng không: `question_count` trên màn hình là mặt trong của hệ thống.
    detail = outcomes[0]["detail"]
    assert detail == "thiếu thông tin để làm bước này"
    assert "hãy hỏi giáo viên" not in detail
    assert "question_count" not in detail


@pytest.mark.asyncio
async def test_a_plan_naming_a_tool_outside_the_working_catalog_runs_nothing(stack) -> None:
    """Plan hỏng thì **không bước nào** chạy, và giáo viên nhận một câu nói.

    Một bước đỏ ở đây sẽ nói sai: với giáo viên, chưa có gì xảy ra cả.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _plan(
            PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống"),
            PlanStep(tool_name="find_class", args={"name": "12A"}, title="Tra lớp"),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    answer = await http.post(
        "/api/teacher/chat/messages", json={"text": "Tạo đề cho 12A"}, headers=TEACHER
    )

    assert answer.status_code == 200
    body = answer.json()
    assert [turn["kind"] for turn in body["turns"]] == ["teacher", "assistant"]
    assert "chưa dựng được" in body["text"]
    assert agent.reported == []


@pytest.mark.asyncio
async def test_a_plan_reaching_backwards_past_itself_is_refused_before_it_runs(stack) -> None:
    """`{2.x}` ở bước 1 là một plan nói về tương lai của chính nó."""
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _plan(
            PlanStep(
                tool_name="start_drafting",
                args={"assessment_id": "{2.assessment_id}"},
                title="Soạn câu hỏi",
            ),
            PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống"),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    answer = await http.post("/api/teacher/chat/messages", json={"text": "Tạo đề"}, headers=TEACHER)

    assert [turn["kind"] for turn in answer.json()["turns"]] == ["teacher", "assistant"]


@pytest.mark.asyncio
async def test_the_turn_survives_a_model_that_cannot_tell_what_happened(stack) -> None:
    """Lời kể hỏng không được làm hỏng việc đã làm.

    Các bước đã chạy và đã commit; một exception thoát ra từ phần kể lại sẽ biến lượt ấy
    thành một lỗi 500 và giáo viên mất cả việc vừa nhờ, vì một câu văn.
    """
    http, maker, monkeypatch = stack

    class Mute(ScriptedAgent):
        async def __call__(self, pool, settings, task_name, payload):
            if task_name == REPORT_PLAN_TASK:
                raise RuntimeError("model im lặng")
            return await super().__call__(pool, settings, task_name, payload)

    agent = Mute(_plan(PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống")))
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    answer = await http.post(
        "/api/teacher/chat/messages", json={"text": "Tạo đề 3 câu"}, headers=TEACHER
    )

    assert answer.status_code == 200
    body = answer.json()
    # Đường lùi dựng từ chính các bước đã chạy, nên nó vẫn nói đúng việc đã xảy ra.
    assert "Tạo đề trống" in body["text"]
    assert [turn["kind"] for turn in body["turns"]][-1] == "assistant"


@pytest.mark.asyncio
async def test_the_turn_tells_what_is_happening_while_it_happens(stack) -> None:
    """Dãy sự kiện là lý do `run_turn` là một generator — nên nó phải được đo như một dãy.

    `POST` rút cạn generator rồi chỉ báo trạng thái cuối, nên mọi test đi qua HTTP đều mù
    với `bước k/n`, với `step_started`, với thứ tự. Test này tiêu thụ generator trực tiếp,
    đúng cách đường SSE của Pha E sẽ tiêu thụ nó.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _plan(
            PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống"),
            PlanStep(
                tool_name="start_drafting",
                args={"assessment_id": "{1.assessment_id}"},
                title="Soạn câu hỏi",
            ),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    teacher = await _teacher(maker, "GV-001")
    asked = teacher_chat.Said(text="Tạo đề 3 câu Hàm số")
    seen = []
    async with maker() as session:
        async for event in teacher_chat.run_turn(
            asked, _request(), teacher, session, get_settings()
        ):
            seen.append(event)

    assert [one.kind for one in seen] == [
        "say",  # "Được, tôi bắt đầu nhé."
        "plan",
        "step_started",
        "step_done",
        "step_started",
        "step_failed",  # hàng đợi giả không đẩy được job — xem test id ở trên
        "report",
        "done",
    ]

    # `bước k/n` nói thật: `n` là số bước plan nêu, `k` là bước đang chạy. Đây là con số mà
    # cả plan tĩnh của ADR-25 tồn tại để nói đúng.
    plan_event = next(one for one in seen if one.kind == "plan")
    assert plan_event.total == 2
    assert plan_event.titles == ("Tạo đề trống", "Soạn câu hỏi")
    started = [one for one in seen if one.kind == "step_started"]
    assert [(one.index, one.total) for one in started] == [(1, 2), (2, 2)]
    assert [one.title for one in started] == ["Tạo đề trống", "Soạn câu hỏi"]

    assert seen[-1].ended_as == "report"


@pytest.mark.asyncio
async def test_a_question_back_is_reported_as_a_question_even_without_choices(stack) -> None:
    """Một câu hỏi lại chưa có candidate vẫn là một câu hỏi.

    Suy nhánh kết thúc từ việc `choices` có rỗng hay không thì sai đúng ở ca này: model hỏi
    trước khi gọi tool nào, nên BE chưa có row nào để dựng lựa chọn — và màn hình mất hẳn
    thông tin "đây là một câu hỏi".
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="ask_clarify", text="Bạn muốn mấy câu?")
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    teacher = await _teacher(maker, "GV-001")
    seen = []
    async with maker() as session:
        async for event in teacher_chat.run_turn(
            teacher_chat.Said(text="Soạn đề giúp tôi"), _request(), teacher, session, get_settings()
        ):
            seen.append(event)

    assert [one.kind for one in seen] == ["clarify", "done"]
    assert seen[-1].ended_as == "clarify"
    assert seen[-1].choices == ()


@pytest.mark.asyncio
async def test_nothing_is_announced_before_it_is_written(stack) -> None:
    """Một sự kiện đi trước dòng của nó trong bảng là một lời hứa màn hình không giữ được.

    Mất kết nối ngay sau một `step_started` chưa được ghi thì F5 cho ra ít hơn thứ vừa xem.
    Test đếm số turn trong bảng **tại thời điểm** mỗi sự kiện được phát.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _plan(PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống"))
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    teacher = await _teacher(maker, "GV-001")
    rows_when = []
    async with maker() as session:
        async for event in teacher_chat.run_turn(
            teacher_chat.Said(text="Tạo đề 3 câu"), _request(), teacher, session, get_settings()
        ):
            async with maker() as reader:
                stored = len(list(await reader.scalars(select(TeacherTurn))))
            rows_when.append((event.kind, stored))

    seen = dict()
    for kind, stored in rows_when:
        seen.setdefault(kind, stored)
    # Lúc `plan` được phát, dòng `plan` đã nằm trong bảng; lúc `step_started` được phát,
    # `tool_call` của nó cũng vậy.
    assert seen["plan"] >= 3  # teacher + câu mở đầu + plan
    assert seen["step_started"] >= 4  # thêm tool_call


@pytest.mark.asyncio
async def test_the_planning_phase_sees_the_working_tools_without_being_able_to_call_them(
    stack,
) -> None:
    """Hai danh mục đi cùng một request, và chúng không được trộn vào nhau.

    Pha 1 không gọi được tool ghi, nhưng nó phải **nêu** được chúng trong một plan — kèm
    đúng tên tham số, vì `vet_plan` so tên tham số với spec và từ chối trọn gói cả plan.
    Không gửi `plannable` thì model phải đoán tên tool và tên tham số của những thứ nó
    chưa từng thấy mô tả, và mọi plan nó viết ra đều bị từ chối. Trộn hai danh mục lại thì
    mở đúng cánh cửa ADR-25 đóng: ghi trước khi hỏi.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(NextStepCompleted(request_id="x", kind="say", text="Chào bạn."))
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    await _teacher(maker, "GV-001")

    await http.post("/api/teacher/chat/messages", json={"text": "chào"}, headers=TEACHER)

    asked = agent.asked[0]
    callable_now = {one["name"] for one in asked["catalog"]}
    plannable = {one["name"] for one in asked["plannable"]}
    assert "create_draft" not in callable_now
    assert "start_drafting" not in callable_now
    assert {"create_draft", "start_drafting"} <= plannable
    # Và chiều ngược lại: một tool tra cứu không được nằm trong danh sách "hẹn làm", nếu
    # không model sẽ nhét một bước đọc vào plan và BE phải từ chối nó.
    assert "find_class" not in plannable

    spec = next(one for one in asked["plannable"] if one["name"] == "create_draft")
    assert set(spec["arguments"]) >= {"subject", "grade", "topic_scope", "question_count"}


@pytest.mark.asyncio
async def test_a_reference_that_cannot_be_resolved_does_not_leak_field_names(stack) -> None:
    """Lý do một bước không ghép được dữ liệu là chữ cho log, không phải chữ cho giáo viên.

    `Unresolvable` nói "bước 1 trả về assessment_id rỗng" hoặc trích nguyên văn `{1.id}` —
    đúng thứ một người sửa lỗi cần, và đúng thứ giáo viên không cần. Chuỗi ấy đi qua **ba**
    cửa nếu không ai chặn: `step_failed.detail` ra màn hình, `StepOutcome.detail` vào prompt
    của lời kể (model sẽ nhắc lại nguyên văn), và câu ghép dự phòng của BE.

    Đây là đúng cái lỗ mà `_said_about` đã bịt ở nhánh thường, và nhánh này đi vòng qua nó.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _plan(
            PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống"),
            PlanStep(
                tool_name="start_drafting",
                # Khuôn đúng và trỏ về phía sau, nên `vet_plan` cho qua: field không tồn tại
                # là thứ chỉ biết được lúc chạy, vì `ToolSpec` không chở tên field trả về.
                args={"assessment_id": "{1.khong_co_field_nay}"},
                title="Soạn câu hỏi",
            ),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    await _teacher(maker, "GV-001")

    answer = await http.post(
        "/api/teacher/chat/messages", json={"text": "Tạo đề 3 câu Hàm số"}, headers=TEACHER
    )

    assert answer.status_code == 200
    detail = next(one["detail"] for one in agent.reported[0]["outcomes"] if not one["ok"])
    assert "khong_co_field_nay" not in detail
    assert "{" not in detail
    assert detail == "chưa ghép được dữ liệu từ bước trước"


@pytest.mark.asyncio
async def test_a_turn_reports_only_its_own_rows_even_on_a_gapped_history(stack) -> None:
    """Câu trả lời của một lượt chỉ chở các dòng **của lượt ấy**.

    `began` từng đọc từ **số dòng** của hội thoại, và hai con số ấy chỉ bằng nhau khi dãy
    `sequence` liền mạch từ 0. Một hội thoại dựng tay — hay một dòng bị xoá — làm `began`
    tụt lại, nên câu trả lời chở thêm mấy dòng của lượt trước; client ghép chúng vào sau
    những dòng nó đã vẽ, và cùng một câu hiện **hai lần**. Mất sau một lần F5, nên nó đọc
    như một lỗi render ngẫu nhiên. Đo thấy trên trình duyệt thật.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(NextStepCompleted(request_id="x", kind="say", text="Chào bạn."))
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    teacher = await _teacher(maker, "GV-001")

    # Một hội thoại có sẵn, đánh số **từ 1** — đúng hình dạng một dãy không liền mạch.
    async with maker() as session:
        session.add(
            TeacherConversation(id="c-gap", teacher_id=teacher.id, started_at=datetime.now(UTC))
        )
        await session.flush()
        for index, (kind, text) in enumerate(
            [("teacher", "chào"), ("assistant", "Chào bạn, mình giúp gì được?")], start=1
        ):
            session.add(
                TeacherTurn(
                    conversation_id="c-gap",
                    sequence=index,
                    kind=kind,
                    text=text,
                    created_at=datetime.now(UTC),
                )
            )
        await session.commit()

    answer = await http.post(
        "/api/teacher/chat/messages",
        json={"text": "soạn giúp tôi một đề", "conversation_id": "c-gap"},
        headers=TEACHER,
    )

    assert answer.status_code == 200
    said = [turn["text"] for turn in answer.json()["turns"]]
    # Đúng hai dòng mới, và **không** có dòng nào của lượt trước đi kèm.
    assert said == ["soạn giúp tôi một đề", "Chào bạn."]
    assert "Chào bạn, mình giúp gì được?" not in said
