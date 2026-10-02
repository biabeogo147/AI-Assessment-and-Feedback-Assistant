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

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import drafting, teacher_chat
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
    DraftQuestionCompleted,
    GeneratedOption,
    GeneratedQuestion,
    NextStepCompleted,
    PlanReportCompleted,
    PlanStep,
    SolutionMethod,
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


def _question(job_id: str) -> GeneratedQuestion:
    """Một câu hỏi hợp lệ, khác nhau theo job để `harvest` không coi là trùng."""
    return GeneratedQuestion(
        stem=f"Câu của {job_id}?",
        options=(
            GeneratedOption(label="A", text="đúng", is_correct=True),
            GeneratedOption(label="B", text="sai", is_correct=False, error_label="lỗi B"),
            GeneratedOption(label="C", text="sai", is_correct=False, error_label="lỗi C"),
        ),
        methods=(
            SolutionMethod(title="Cách 1", body="..."),
            SolutionMethod(title="Cách 2", body="..."),
        ),
        learning_objective="hàm số",
    )


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
            # Đủ tham số nên plan qua được `vet_plan`, nhưng `question_count` không đọc
            # được thành số: tool từ chối lúc chạy, không ghi gì. Đây là ca "hỏng lúc
            # chạy", khác hẳn ca "plan sai từ đầu" ở test ngay dưới.
            PlanStep(
                tool_name="create_draft",
                args={
                    "subject": "Toán",
                    "grade": "12",
                    "topic_scope": "đạo hàm",
                    "question_count": "rất nhiều",
                },
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
    assert detail == "một mục trong yêu cầu chưa dùng được"
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


@pytest.mark.asyncio
async def test_the_stream_sends_each_event_as_it_happens(stack) -> None:
    """Cửa SSE phát từng việc, không gửi dồn một lần ở cuối.

    Đây là cả lý do Pha E tồn tại. Cửa `POST` rút cạn generator rồi trả trạng thái cuối, nên
    màn hình nhận cả lượt một lần và dấu `○` của khối bước chưa chạy lần nào. Cùng một
    `run_turn`, hai cửa — nếu cửa này tự dựng một dãy sự kiện riêng thì hai bản sẽ trôi dạt
    khỏi nhau ở đúng chỗ khó thấy nhất.
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
    await _teacher(maker, "GV-001")

    frames = []
    async with http.stream(
        "POST",
        "/api/teacher/chat/messages/stream",
        json={"text": "Tạo đề 3 câu Hàm số"},
        headers=TEACHER,
    ) as answer:
        assert answer.status_code == 200
        assert answer.headers["content-type"].startswith("text/event-stream")
        async for line in answer.aiter_lines():
            if line.startswith("data: "):
                frames.append(json.loads(line[6:]))

    kinds = [one["kind"] for one in frames]
    assert kinds[0] == "say"
    assert "plan" in kinds
    assert kinds.count("step_started") == 2
    assert kinds[-1] == "done"
    assert frames[-1]["ended_as"] == "report"

    # Và mỗi khung là một `TurnEvent` đủ hình dạng, không phải một chuỗi tự chế.
    plan_frame = next(one for one in frames if one["kind"] == "plan")
    assert plan_frame["total"] == 2
    assert plan_frame["titles"] == ["Tạo đề trống", "Soạn câu hỏi"]


@pytest.mark.asyncio
async def test_a_turn_that_breaks_mid_stream_still_says_something(stack) -> None:
    """Lượt gãy sau khi header đã gửi thì không còn status code nào để nói.

    Một màn hình đang đọc stream mà nguồn im lặng sẽ đứng im tới khi người đọc bỏ đi — không
    có vòng quay, không có lỗi, không có gì. Nên mọi đường gãy đều phải ra bằng một khung
    `done`.
    """
    http, maker, monkeypatch = stack

    class Broken(ScriptedAgent):
        async def __call__(self, pool, settings, task_name, payload):
            raise RuntimeError("cái gì đó vỡ")

    monkeypatch.setattr(teacher_chat, "run_task", Broken())
    await _teacher(maker, "GV-001")

    frames = []
    async with http.stream(
        "POST", "/api/teacher/chat/messages/stream", json={"text": "chào"}, headers=TEACHER
    ) as answer:
        async for line in answer.aiter_lines():
            if line.startswith("data: "):
                frames.append(json.loads(line[6:]))

    assert frames[-1]["kind"] == "done"
    assert frames[-1]["ended_as"] == "error"
    assert frames[-1]["text"]


@pytest.mark.asyncio
async def test_the_post_door_does_not_wait_for_the_questions(stack) -> None:
    """Cửa `POST` **không** đợi các câu về, và đó là một quyết định chứ không phải thiếu sót.

    Nó rút cạn generator bên trong một request. Đợi mười câu ở đó nghĩa là một request HTTP
    đứng hàng phút — một proxy hay một browser sẽ cắt nó, và lượt chat biến mất giữa chừng
    dù BE vẫn ghi xong. Đường đợi thuộc về cửa SSE, nơi đứng chờ là việc của nó.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _plan(PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống"))
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    await _teacher(maker, "GV-001")

    waited = []

    async def never(*args, **kwargs):
        waited.append(args)
        raise AssertionError("cửa POST không được đợi câu hỏi")

    monkeypatch.setattr(teacher_chat, "_wait_for_questions", never)

    answer = await http.post(
        "/api/teacher/chat/messages", json={"text": "Tạo đề 3 câu Hàm số"}, headers=TEACHER
    )

    assert answer.status_code == 200
    assert waited == []


@pytest.mark.asyncio
async def test_each_event_is_its_own_sse_frame(stack) -> None:
    """Ranh giới khung là thứ duy nhất của giao thức SSE mà BE phải làm đúng.

    Test cũ tự parse bằng `aiter_lines()` + `startswith("data: ")`, nên nó **không đi qua**
    ranh giới khung: đổi dòng trống kết khung thành một dòng xuống thì nó vẫn xanh, trong
    khi parser thật ở `api.ts` cắt theo dòng trống và sẽ gộp cả lượt thành một khung rồi
    `JSON.parse` nổ. Chỗ này đọc body thô và đếm khung đúng cách client đếm.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _plan(PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống"))
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    await _teacher(maker, "GV-001")

    body = ""
    async with http.stream(
        "POST",
        "/api/teacher/chat/messages/stream",
        json={"text": "Tạo đề 3 câu Hàm số"},
        headers=TEACHER,
    ) as answer:
        async for piece in answer.aiter_text():
            body += piece

    frames = [one for one in body.split("\n\n") if one.strip()]
    assert len(frames) >= 4
    for frame in frames:
        assert frame.startswith("data: ")
        json.loads(frame[6:])


@pytest.mark.asyncio
async def test_the_stream_waits_for_the_questions_and_opens_its_ears_first(stack) -> None:
    """Đường đợi chạy **thật**, và nó subscribe **trước** khi job được đẩy đi.

    Hai luật trong một test, vì chúng chỉ sai cùng nhau:

    - Cửa SSE phải đợi (`watching=True`). Một test chỉ canh *cửa POST không đợi* để lại nửa
      kia không ai giữ.
    - Việc mở tai phải xảy ra trước việc đẩy job. Pub/sub của Redis không giữ lịch sử, và
      trên một máy dev không có API key thì một câu "soạn xong" trong vài micro-giây — mọi
      tiếng chuông rơi vào phòng trống, khối bước đứng im trọn ba phút rồi mới kể. Review
      Pha F đo được rằng đường thật chưa dùng tham số `start` dựng ra cho đúng luật ấy.

    Và nó **không** monkeypatch `_wait_for_questions`: năm đột biến một dòng bên trong hàm ấy
    từng sống sót qua cả bộ test vì không test nào chạy qua nó.
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
    await _teacher(maker, "GV-001")

    order = _drafting_stack(http, monkeypatch, rings_for={1, 2, 3}, ready_for={1, 2, 3})

    frames = []
    async with http.stream(
        "POST",
        "/api/teacher/chat/messages/stream",
        json={"text": "Tạo đề 3 câu Hàm số"},
        headers=TEACHER,
    ) as answer:
        async for line in answer.aiter_lines():
            if line.startswith("data: "):
                frames.append(json.loads(line[6:]))

    # Mở tai trước khi job đi. Đảo thứ tự lại là mất mọi tiếng chuông của một worker nhanh.
    assert order[0] == "subscribe"
    assert "fire" in order
    assert order.index("subscribe") < order.index("fire")

    kinds = [one["kind"] for one in frames]
    # `progress` nằm **giữa** `step_started` và `step_done` của bước soạn câu: số câu là tiến
    # độ bên trong MỘT bước, nên bước ấy phải còn đang mở lúc con số tới.
    started = [i for i, one in enumerate(kinds) if one == "step_started"]
    closed = [i for i, one in enumerate(kinds) if one == "step_done"]
    progress = [i for i, one in enumerate(kinds) if one == "progress"]
    assert progress, "không có khung tiến độ nào"
    assert started[-1] < progress[0] <= progress[-1] < closed[-1]

    # Và con số đi lên tới đủ: lần thu cuối sau vòng nghe là thứ giữ cho `3/3` không bị mất.
    last = [one for one in frames if one["kind"] == "progress"][-1]
    assert last["index"] == 3
    assert last["total"] == 3

    # Dòng kết quả của bước soạn nói con số thật, không nói số job đã đẩy đi.
    closing = [one for one in frames if one["kind"] == "step_done"][-1]
    assert closing["detail"] == "đã soạn 3/3 câu"


def _drafting_stack(
    http,
    monkeypatch,
    rings_for: set[int],
    ready_for: set[int],
    failed_for: frozenset[int] = frozenset(),
) -> list[str]:
    """Dựng một hàng đợi giả rung chuông cho `rings_for` và trả kết quả cho `ready_for`.

    Hai tập hợp tách nhau là cả ý nghĩa của nó: chuông **không bền**, nên một job xong mà
    tiếng chuông của nó rơi mất là chuyện thường ngày — và đề vẫn phải đủ câu.

    Args:
        http: Client, để với tới `app.state`.
        monkeypatch: Để thay `collect_result` và mức kiên nhẫn.
        rings_for: Những `ordinal` có chuông.
        ready_for: Những `ordinal` rồi sẽ có kết quả đọc được.
        failed_for: Những `ordinal` mà chính job đã nổ — rời `pending` mà không mang câu nào.

    Returns:
        Một list ghi thứ tự các việc đã xảy ra (`subscribe`, `fire`).
    """
    order: list[str] = []
    bells: list[bytes] = []
    # Một câu chỉ **đọc được** sau khi tiếng chuông của nó tới. Không mô phỏng chuyện đó thì
    # mọi kết quả có sẵn ngay từ tiếng chuông đầu, lần thu đầu lấy hết, và test không phân
    # biệt được "thu theo từng tiếng chuông" với "thu một lần ở cuối".
    revealed: set[int] = set()
    silence: list[int] = []

    class Ears:
        async def subscribe(self, channel: str) -> None:
            order.append("subscribe")

        async def get_message(self, ignore_subscribe_messages: bool, timeout: float):
            if bells:
                rung = bells.pop(0)
                revealed.add(int(rung))
                return {"type": "message", "data": rung}
            silence.append(1)
            if len(silence) >= 2:
                # Im lặng một lúc rồi những câu còn lại cũng xong — nhưng chuông của chúng
                # đã rơi mất. Đây là ca mà lần thu sau vòng nghe sinh ra để cứu.
                revealed.update(ready_for | failed_for)
            return None

        async def unsubscribe(self, channel: str) -> None:
            order.append("unsubscribe")

        async def aclose(self) -> None:
            pass

    class Queue:
        def pubsub(self) -> Ears:
            return Ears()

        async def enqueue_job(self, name: str, payload: dict, _queue_name: str):
            order.append("fire")
            if payload["ordinal"] in rings_for:
                bells.append(str(payload["ordinal"]).encode())
            return type("Queued", (), {"job_id": f"job-{payload['ordinal']}"})()

    http._transport.app.state.queue_pool = Queue()

    async def collected(pool, settings, job_id):
        ordinal = int(job_id.rsplit("-", 1)[1])
        if ordinal in failed_for and ordinal in revealed:
            return "failed", None
        if ordinal not in ready_for or ordinal not in revealed:
            return "pending", None
        return "ready", DraftQuestionCompleted(
            request_id="r", question=_question(job_id)
        ).model_dump(mode="json")

    monkeypatch.setattr(drafting, "collect_result", collected)
    # Không ai đợi ba phút trong một test. Đây là hạn cho **sự im lặng**, nên 0,5 giây là đủ
    # để vòng nghe đi hết rồi thu lần cuối.
    monkeypatch.setattr(teacher_chat, "_WAIT_FOR_QUESTIONS_SECONDS", 0.5)
    return order


async def _drafting_frames(http) -> list[dict]:
    """Chạy một lượt soạn đề qua cửa SSE và trả về các khung đã nhận."""
    frames = []
    async with http.stream(
        "POST",
        "/api/teacher/chat/messages/stream",
        json={"text": "Tạo đề 3 câu Hàm số"},
        headers=TEACHER,
    ) as answer:
        async for line in answer.aiter_lines():
            if line.startswith("data: "):
                frames.append(json.loads(line[6:]))
    return frames


@pytest.mark.asyncio
async def test_a_lost_last_bell_still_ends_with_every_question_in(stack) -> None:
    """Tiếng chuông cuối rơi mất thì **lần thu sau vòng nghe** là thứ cứu con số.

    Chuông không bền: một tiếng rơi vào lúc người nghe đang bận là chuyện thường. Không có
    lần thu cuối ấy thì một đề đủ ba câu kết thúc lượt ở `2/3`, và lời kể nói sai theo.

    Và các con số ở giữa phải lên dần: nếu không thu ở mỗi tiếng chuông mà chỉ thu một lần ở
    cuối thì màn hình đứng ở `0/3` suốt rồi nhảy một phát — mất đúng cái mà Pha E làm ra.
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
    await _teacher(maker, "GV-001")
    _drafting_stack(http, monkeypatch, rings_for={1, 2}, ready_for={1, 2, 3})

    frames = await _drafting_frames(http)

    counts = [one["index"] for one in frames if one["kind"] == "progress"]
    assert counts[-1] == 3, f"thiếu lần thu cuối: {counts}"
    assert 1 in counts and 2 in counts, f"không thu theo từng tiếng chuông: {counts}"
    closing = [one for one in frames if one["kind"] == "step_done"][-1]
    assert closing["detail"] == "đã soạn 3/3 câu"


@pytest.mark.asyncio
async def test_a_draft_that_stops_short_says_it_stopped(stack) -> None:
    """Hết chuông mà vẫn thiếu câu thì dòng kết quả nói **dừng**, không nói đã soạn đủ.

    Một `đã soạn 3/3 câu` cho một đề có hai câu đi thẳng vào prompt báo cáo, và model được
    bảo rằng đề đã xong rồi mời giáo viên duyệt. Duyệt một đề thiếu câu là phát hành một bài
    kiểm tra dở — đúng cái hại ADR-01 khoá nội dung để chặn.
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
    await _teacher(maker, "GV-001")
    # Câu thứ ba: chính job đã nổ, nên nó rời `pending` mà không mang theo câu nào.
    _drafting_stack(
        http, monkeypatch, rings_for={1, 2}, ready_for={1, 2}, failed_for=frozenset({3})
    )

    frames = await _drafting_frames(http)

    closing = [one for one in frames if one["kind"] == "step_done"][-1]
    assert closing["detail"] == "dừng ở 2/3 câu"


@pytest.mark.asyncio
async def test_a_plan_missing_an_argument_is_refused_before_anything_runs(stack) -> None:
    """Thiếu một tham số là plan sai từ đầu, và không bước nào được chạy.

    Mọi tham số được mô tả cho model đều là tham số **bắt buộc** — catalog chỉ nêu những thứ
    tool thật sự cần. Đo trên trình duyệt thật: model nêu `start_drafting` không kèm
    `assessment_id`, bước ấy chạy với tay không, và lượt để lại một **đề rỗng** mang tên
    giáo viên cùng một câu kể vòng vo. Từ chối trọn gói là cách duy nhất không có gì kịp ghi.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _plan(
            PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống"),
            PlanStep(tool_name="start_drafting", args={}, title="Soạn câu hỏi"),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    await _teacher(maker, "GV-001")

    answer = await http.post(
        "/api/teacher/chat/messages", json={"text": "Tạo đề 3 câu Hàm số"}, headers=TEACHER
    )

    assert answer.status_code == 200
    kinds = [turn["kind"] for turn in answer.json()["turns"]]
    assert "tool_call" not in kinds
    async with maker() as session:
        made = list(await session.scalars(select(Assessment)))
    # Chỉ còn đề của seed; không đề rỗng nào mới sinh ra.
    assert all(one.title != "Hàm số" for one in made)
