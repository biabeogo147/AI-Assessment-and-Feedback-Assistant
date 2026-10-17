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
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import anyio
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import drafting, notices, teacher_chat
from be.config import get_settings
from be.content_reader import MemoryContentReader, bind_reader
from be.db import bind_sessions
from be.identity import Asking
from be.seed import seed_if_empty
from be.teacher_chat import router as teacher_router
from be.teacher_tools import UnknownTool, execute
from contracts import (
    NAME_CONVERSATION_TASK,
    REPORT_PLAN_TASK,
    BlockRef,
    ClarifyQuestion,
    ConversationNameCompleted,
    DocumentState,
    DraftQuestionCompleted,
    GeneratedOption,
    GeneratedQuestion,
    IndexHeader,
    IndexMethod,
    IndexNode,
    NextStepCompleted,
    OutlineItem,
    PlanReportCompleted,
    PlanStep,
    SolutionMethod,
    TitleSource,
)
from schema.ddl import prepare_schema
from schema.models import (
    Assessment,
    AssessmentState,
    Document,
    DraftBrief,
    DraftItem,
    Question,
    SchoolClass,
    Student,
    Teacher,
    TeacherConversation,
    TeacherTurn,
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
                request_id=payload["request_id"], title="đề do model đặt tên"
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


def _outline_shown(monkeypatch, total: int, purpose: str = "new") -> None:
    """Một dàn ý giáo viên đã xem ở lượt trước (ADR-29), cho test **không** nói về cổng duyệt.

    Từ `draft-outline`, plan soạn câu chỉ chạy trên một dàn ý đã hiện. Test về chuông, về tham
    chiếu, về khối bước thì không cần dựng cả lượt dàn ý trước: dàn ý ở đây thay đúng chỗ ấy.
    """

    async def shown(*_args: object) -> dict:
        return {
            "version": 1,
            "first": 1,
            "total": total,
            "for": purpose,
            "document_id": "",
            "items": [
                {
                    "questions": total,
                    "knowledge": "Kiến thức của đề",
                    "formulas": [],
                    "approach": "Chọn đáp án đúng",
                    "source_nodes": [],
                }
            ],
        }

    monkeypatch.setattr(teacher_chat, "_shown_outline", shown)


def _refusal(agent: "ScriptedAgent") -> str:
    """Lý do BE trả về model khi từ chối một plan (ADR-30): kết quả `plan` trong lần hỏi cuối.

    Từ `kriky-writes-every-word` BE không nói câu từ chối với giáo viên nữa; lý do đi về model như
    kết quả một tool, và model nói lại trong cùng lượt.
    """
    results = [
        turn
        for turn in agent.asked[-1]["history"]
        if turn["kind"] == "tool_result" and turn["tool_name"] == "plan"
    ]
    assert results, "BE không trả lý do từ chối plan về model"
    return results[-1]["tool_result"]["error"]


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
            GeneratedOption(label="B", text="sai B", is_correct=False, error_label="lỗi B"),
            GeneratedOption(label="C", text="sai C", is_correct=False, error_label="lỗi C"),
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
        NextStepCompleted(request_id="x", kind="call_tool", tool_name="list_class", tool_args={}),
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
    shown = results[0]["tool_result"]["candidates"]
    assert [one["name"] for one in shown] == ["12A"]


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
                request_id="x", kind="call_tool", tool_name="list_class", tool_args={}
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
    assert body["text"] == notices.CEILING_REACHED
    # Câu của hệ thống, không phải lời Kriky (ADR-30, ngoại lệ 1).
    assert body["turns"][-1]["kind"] == "notice"
    # Đúng con số đã cấu hình, và đọc ra từ config. `<= 8` sẽ cho qua một vòng lặp
    # chỉ chạy một lần, còn viết cứng số 8 sẽ âm thầm xanh với bất cứ ai hạ giá trị
    # cấu hình đó xuống.
    assert len(forever.asked) == get_settings().max_tool_steps


@pytest.mark.asyncio
async def test_a_notice_from_the_agent_is_stored_as_a_system_notice(stack) -> None:
    """AGENT nói câu cố định khi model hỏng, và khai `notice=True` (ADR-30, ngoại lệ 1).

    BE lưu nó thành lượt `notice`, không thành lời Kriky: lượt sau model đọc nó như ghi chú hệ
    thống, và màn hình vẽ nó không avatar (`kriky-writes-every-word`).
    """
    client, _, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x", kind="say", text="Kriky chưa trả lời được lúc này.", notice=True
        ),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12A thế nào"}, headers=TEACHER
    )

    body = reply.json()
    assert [turn["kind"] for turn in body["turns"]] == ["teacher", "notice"]
    assert body["text"] == "Kriky chưa trả lời được lúc này."


@pytest.mark.asyncio
async def test_the_ceiling_streams_a_notice_not_kriky_s_words(stack) -> None:
    """Review pha 5 (`kriky-writes-every-word`): câu trần đi dưới `notice` cả lúc đang chạy, không
    chỉ sau F5 -- sự kiện `say` thì FE vẽ nó như lời Kriky có avatar."""
    _, maker, monkeypatch = stack
    forever = ScriptedAgent(
        *[
            NextStepCompleted(
                request_id="x", kind="call_tool", tool_name="list_class", tool_args={}
            )
            for _ in range(20)
        ]
    )
    monkeypatch.setattr(teacher_chat, "run_task", forever)

    teacher = await _teacher(maker, "GV-001")
    seen = []
    async with maker() as session:
        async for event in teacher_chat.run_turn(
            teacher_chat.Said(text="lớp 12A thế nào"), _request(), teacher, session, get_settings()
        ):
            seen.append(event)

    spoken = [one for one in seen if one.text == notices.CEILING_REACHED]
    assert [one.kind for one in spoken] == ["notice", "done"]
    assert seen[-1].ended_as == "notice"


@pytest.mark.asyncio
async def test_a_turn_that_only_hears_refused_plans_says_where_it_is_stuck(stack) -> None:
    """Review pha 5: model cứ nêu plan BE không nhận tới trần -- câu trần chung bảo *"nói rõ tên
    lớp"* là gợi ý sai, nên thông báo nói chỗ vướng là các bước."""
    client, _, monkeypatch = stack
    refused = _plan(PlanStep(tool_name="list_class", args={"name": "12A"}, title="Tra lớp"))
    agent = ScriptedAgent(*[refused for _ in range(20)])
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "Tạo đề cho 12A"}, headers=TEACHER
    )

    body = reply.json()
    assert body["text"] == notices.PLAN_REFUSED
    assert body["turns"][-1]["kind"] == "notice"
    # Cùng một lý do hai lần liền là dừng: không gọi model tới trần cho cùng một câu thông báo.
    assert len(agent.asked) == 2


@pytest.mark.asyncio
async def test_a_drafting_plan_held_back_twice_stops_the_turn_too(stack) -> None:
    """Review cuối plan: nhánh `guard_drafting` -- soạn khi chưa có dàn ý -- cũng dừng ở lần hai."""
    client, _, monkeypatch = stack
    agent = ScriptedAgent(*[_open_and_draft("") for _ in range(20)])
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "soạn 2 câu"}, headers=TEACHER
    )

    assert reply.json()["text"] == notices.PLAN_REFUSED
    assert len(agent.asked) == 2


@pytest.mark.asyncio
async def test_a_lookup_between_two_refusals_lets_the_model_try_again(stack) -> None:
    """Một bước tra cứu chạy được giữa hai lần từ chối là model đang xoay xở, không phải kẹt: lý
    do cũ quên đi, lần từ chối sau không dừng lượt."""
    client, _, monkeypatch = stack
    refused = _plan(PlanStep(tool_name="list_class", args={"name": "12A"}, title="Tra lớp"))
    looked = NextStepCompleted(
        request_id="x", kind="call_tool", tool_name="list_class", tool_args={}
    )
    said = NextStepCompleted(request_id="x", kind="say", text="Lớp 12A có 3 học sinh.")
    agent = ScriptedAgent(refused, looked, refused, said)
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12A thế nào"}, headers=TEACHER
    )

    assert reply.json()["text"] == "Lớp 12A có 3 học sinh."
    assert len(agent.asked) == 4


@pytest.mark.asyncio
async def test_an_agreement_retyped_after_a_system_notice_still_drafts(stack) -> None:
    """Review pha 5: model hỏng sau *"oke"*, thông báo dặn gửi lại -- gửi lại vẫn là lời đáp dàn
    ý, không phải một lượt soạn bị chặn vì *"chưa thấy dàn ý"*."""
    http, maker, monkeypatch = stack
    down = NextStepCompleted(
        request_id="x", kind="say", text="Kriky chưa trả lời được lúc này.", notice=True
    )
    agent = ScriptedAgent(_outline_step(_outline_item(source_nodes=())), down, _open_and_draft(""))
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _drafting_stack(http, monkeypatch, rings_for=set(), ready_for=set())

    for said in ("soạn 2 câu", "oke", "oke"):
        await http.post("/api/teacher/chat/messages", json={"text": said}, headers=TEACHER)

    async with maker() as session:
        assert await session.scalar(select(DraftBrief)) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(("parts", "extra"), [(5, 5), (20, 10)])
async def test_each_part_to_read_buys_the_turn_one_more_step(stack, parts: int, extra: int) -> None:
    """`draft-outline`: xin N câu thì phạm vi gộp thành tối đa N phần, và lượt phải đọc được hết.

    Mỗi phần `read_section` báo là một bước thêm, tới mười -- trần mười câu mỗi lần xin. Một model
    đọc mãi vẫn dừng ở trần mới, và nói ra như ở trần cũ.
    """
    client, _, monkeypatch = stack
    forever = ScriptedAgent(
        *[
            NextStepCompleted(
                request_id="x", kind="call_tool", tool_name="read_section", tool_args={}
            )
            for _ in range(40)
        ]
    )
    monkeypatch.setattr(teacher_chat, "run_task", forever)

    async def read(*_args, **_kwargs) -> dict:
        return {"found": True, "part": 1, "parts": parts, "more": True, "text": "chữ"}

    monkeypatch.setattr(teacher_chat, "execute", read)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "soạn đề"}, headers=TEACHER
    )

    assert reply.json()["text"] == notices.CEILING_REACHED
    assert len(forever.asked) == get_settings().max_tool_steps + extra


@pytest.mark.parametrize(
    ("tool", "result", "granted", "expected"),
    [
        ("read_section", {"found": True, "parts": 4}, 0, 4),
        ("read_section", {"found": True, "parts": 4}, 4, 0),
        ("read_section", {"found": True, "parts": 6}, 4, 2),
        ("read_section", {"found": False, "reason": "x"}, 0, 0),
        ("read_section", {"found": True, "parts": "rác"}, 0, 0),
        ("list_chapters", {"found": True, "parts": 4}, 0, 0),
    ],
)
def test_only_a_successful_read_buys_steps(
    tool: str, result: dict, granted: int, expected: int
) -> None:
    assert teacher_chat.read_allowance(tool, result, granted) == expected


def test_the_longest_reading_turn_still_ends_before_its_lock_goes_stale() -> None:
    """Một lượt đọc đủ mười phần là lượt dài nhất pha 1 có; khoá của nó không được hết hạn trước."""
    settings = get_settings()
    # Bước cuối có thể bắt đầu ngay trước hạn và đợi trọn một job.
    longest = (
        settings.turn_budget_seconds
        + 10 * settings.read_step_seconds
        + settings.agent_job_timeout_seconds
    )

    assert longest < settings.turn_lock_stale_seconds


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
        NextStepCompleted(request_id="x", kind="call_tool", tool_name="list_class", tool_args={}),
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
    # Đúng hai dòng khớp với "12", kèm số học sinh do BE đếm — không phải con số 45 model khai, và
    # không có hai lớp nó bịa ra. Không phương án model viết nào khớp đúng một tên, nên nút là nhãn
    # BE (`unbiased-model-text` T3). Không có "Khác": FE tự vẽ lối ấy (13/10/2026).
    assert body["choices"] == ["12A (3 học sinh)", "12B (1 học sinh)"]
    assert body["more_choices"] == 0
    # Câu hỏi thì vẫn là lời của model. Nó viết câu hỏi; BE viết các câu trả lời.
    assert body["text"] == "Bạn muốn xem lớp nào?"


_KHOI = ClarifyQuestion(label="Khối", text="Khối nào?", choices=("Khối 6", "Khối 7", "Khối 8"))
_SO_CAU = ClarifyQuestion(
    label="Số câu", text="Bao nhiêu câu?", choices=("5 câu", "10 câu", "Khác")
)


@pytest.mark.asyncio
async def test_a_question_back_with_several_questions_is_kept_and_read_back(stack) -> None:
    """ADR-32: các câu lưu cùng lượt hỏi, đọc lại sau F5 còn nguyên, mỗi câu nút của riêng nó;
    "Khác" không thành nút (FE tự vẽ lối ấy)."""
    client, _, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x",
            kind="ask_clarify",
            text="Mình cần biết thêm hai điều:",
            questions=(_KHOI, _SO_CAU),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "soạn đề"}, headers=TEACHER
    )
    read = await client.get(
        f"/api/teacher/chat?conversation_id={reply.json()['conversation_id']}", headers=TEACHER
    )

    body = reply.json()
    assert body["kind"] == "ask_clarify"
    assert body["text"] == "Mình cần biết thêm hai điều:"
    assert body["choices"] == []
    last = read.json()["turns"][-1]
    assert last["kind"] == "assistant"
    assert last["tool_result"]["questions"] == [
        {"label": "Khối", "text": "Khối nào?", "choices": ["Khối 6", "Khối 7", "Khối 8"]},
        {"label": "Số câu", "text": "Bao nhiêu câu?", "choices": ["5 câu", "10 câu"]},
    ]


def test_a_question_about_a_row_keeps_the_question_that_names_a_row() -> None:
    """Review pha 6: câu về dòng đứng thứ hai vẫn là câu được giữ -- nút nhãn lớp không được
    nằm dưới *"Bao nhiêu câu?"*."""
    step = NextStepCompleted(
        request_id="x",
        kind="ask_clarify",
        text="Mình cần biết:",
        questions=(
            _SO_CAU,
            ClarifyQuestion(label="Lớp", text="Lớp nào?", choices=("12A", "12B", "12C")),
        ),
    )

    text, choices, several = teacher_chat._questions_of(
        step, True, {"12A": "12A (3 học sinh)", "12B": "12B (0 học sinh)"}
    )

    assert text == "Mình cần biết:\n\nLớp nào?"
    assert choices == ("12A", "12B", "12C")
    assert several == []


def test_blank_or_repeated_labels_are_numbered() -> None:
    """Câu trả lời gộp *"Nhãn: trả lời"* chỉ đọc được khi mỗi nhãn trỏ về một câu."""
    step = NextStepCompleted(
        request_id="x",
        kind="ask_clarify",
        text="",
        questions=(
            ClarifyQuestion(label="Khối", text="Khối nào?", choices=("Khối 6", "Khối 7")),
            ClarifyQuestion(label="Khối", text="Khối nữa?", choices=("Khối 8", "Khối 9")),
            ClarifyQuestion(label=" ", text="Bao nhiêu câu?", choices=("5 câu", "10 câu")),
        ),
    )

    _, _, several = teacher_chat._questions_of(step, False, {})

    assert [one["label"] for one in several] == ["Khối", "Khối (2)", "Câu 3"]


@pytest.mark.asyncio
async def test_a_question_about_a_row_keeps_one_question_with_be_labels(stack) -> None:
    """ADR-32 + ADR-23: nút về một dòng là mọi nhãn BE dựng, và chúng chỉ trả lời được một câu."""
    client, maker, monkeypatch = stack
    async with maker() as session:
        mine = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        session.add(SchoolClass(teacher_id=mine.id, name="12B"))
        await session.commit()
    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="call_tool", tool_name="list_class", tool_args={}),
        NextStepCompleted(
            request_id="x",
            kind="ask_clarify",
            text="Mình cần biết:",
            questions=(
                ClarifyQuestion(label="Lớp", text="Lớp nào?", choices=("12A", "12B", "12C")),
                _SO_CAU,
            ),
        ),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12 thế nào"}, headers=TEACHER
    )

    body = reply.json()
    assert body["text"] == "Mình cần biết:\n\nLớp nào?"
    assert body["choices"][:2] == ["12A (3 học sinh)", "12B (0 học sinh)"]
    assert body["turns"][-1]["tool_result"] == {}


@pytest.mark.asyncio
async def test_a_made_up_class_never_becomes_a_button_on_the_next_turn(stack) -> None:
    """Review T3 (`unbiased-model-text`, chặn): câu hỏi về lớp kéo sang lượt sau.

    Lượt 1 tra lớp rồi hỏi lại. Lượt 2 giáo viên ghi một câu không phải nhãn nào (lối "Khác" của
    thẻ), model hỏi tiếp **không** gọi tool,
    kèm ba chuỗi ADR-23 đã đo là rò. Xét riêng lượt 2 thì không có `candidates`, câu hỏi bị coi là
    về tham số và ba chuỗi ấy thành nút -- bản đầu của T3 làm đúng như vậy.
    """
    client, maker, monkeypatch = stack
    async with maker() as session:
        mine = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        assert mine is not None
        session.add(SchoolClass(teacher_id=mine.id, name="12B"))
        await session.commit()

    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="call_tool", tool_name="list_class", tool_args={}),
        NextStepCompleted(request_id="x", kind="ask_clarify", text="Bạn muốn xem lớp nào?"),
        NextStepCompleted(
            request_id="x",
            kind="ask_clarify",
            text="Bạn nói rõ hơn lớp nào nhé?",
            choices=("12A (45 học sinh)", "12A-1", "11C"),
        ),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    first = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12 thế nào"}, headers=TEACHER
    )
    second = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp chuyên Toán"}, headers=TEACHER
    )

    assert second.json()["choices"] == first.json()["choices"]
    assert not {"12A (45 học sinh)", "12A-1", "11C"} & set(second.json()["choices"])


@pytest.mark.asyncio
async def test_a_question_about_a_number_offers_the_models_options(stack) -> None:
    """`unbiased-model-text` T3: hỏi về một **tham số** thì không có dòng nào để dựng nút -- trước
    T3 câu hỏi ấy không có nút nào và giáo viên phải gõ lại cả câu. Nay nút là chữ model đề xuất (FE
    vẽ "Khác"), và chúng sống qua F5 như nút của câu hỏi về lớp."""
    client, _, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x",
            kind="ask_clarify",
            text="Bạn muốn đề có bao nhiêu câu?",
            choices=("10 câu", "15 câu", "20 câu"),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    live = await client.post(
        "/api/teacher/chat/messages", json={"text": "soạn đề góc nội tiếp lớp 9"}, headers=TEACHER
    )

    assert live.json()["choices"] == ["10 câu", "15 câu", "20 câu"]
    again = await client.get("/api/teacher/chat", headers=TEACHER)
    assert again.json()["choices"] == ["10 câu", "15 câu", "20 câu"]


@pytest.mark.asyncio
async def test_the_options_survive_a_reload(stack) -> None:
    """Các phương án sống sót qua một lần F5.

    Test ngay trên canh cửa POST, và một câu trả lời của POST thì không ai F5. Các phương án
    trước đợt này chỉ sống trong response: `teacher_turns` không có cột nào cho chúng, nên
    `GET /teacher/chat` **không bao giờ** trả `choices`, và một lần tải lại lấy mất các nút,
    bỏ giáo viên lại trước một câu hỏi mà không còn câu trả lời nào bày ra. Đây là chỗ duy
    nhất đo được chuyện đó.
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
        NextStepCompleted(request_id="x", kind="call_tool", tool_name="list_class", tool_args={}),
        NextStepCompleted(request_id="x", kind="ask_clarify", text="Bạn muốn xem lớp nào?"),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    live = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12 thế nào"}, headers=TEACHER
    )
    assert live.status_code == 200
    offered = live.json()["choices"]
    assert offered == ["12A (3 học sinh)", "12B (1 học sinh)"]

    again = await client.get("/api/teacher/chat", headers=TEACHER)

    assert again.status_code == 200
    reread = again.json()
    assert reread["choices"] == offered
    assert reread["more_choices"] == 0
    # Và chúng đi cùng **đúng bước** đã hỏi, không phải một danh sách rời bên cạnh hội thoại.
    assert reread["turns"][-1]["choices"] == offered


@pytest.mark.asyncio
async def test_an_answered_question_no_longer_offers_its_buttons(stack) -> None:
    """Một câu hỏi đã được trả lời thì các nút của nó không còn nghĩa gì.

    Bày lại chúng là mời giáo viên trả lời hai lần một câu -- và lần thứ hai thì câu hỏi đó
    đã không còn là câu hỏi đang mở nữa. Nên chỉ **bước cuối** chở `choices` lên.
    """
    client, maker, monkeypatch = stack
    async with maker() as session:
        mine = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        assert mine is not None
        session.add(SchoolClass(teacher_id=mine.id, name="12B"))
        await session.commit()

    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="call_tool", tool_name="list_class", tool_args={}),
        NextStepCompleted(request_id="x", kind="ask_clarify", text="Bạn muốn xem lớp nào?"),
        NextStepCompleted(request_id="x", kind="say", text="Rõ rồi."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    asked = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12 thế nào"}, headers=TEACHER
    )
    assert asked.json()["choices"]

    answered = await client.post(
        "/api/teacher/chat/messages", json={"text": "12A"}, headers=TEACHER
    )
    assert answered.status_code == 200

    again = await client.get("/api/teacher/chat", headers=TEACHER)
    assert again.json()["choices"] == []


@pytest.mark.asyncio
async def test_the_cut_count_survives_a_reload_too(stack) -> None:
    """Con số *"còn mấy lựa chọn nữa"* cũng phải sống qua F5.

    Nó có một lý do mạnh — một giáo viên có ba mươi lớp mà chỉ được xem sáu lớp, không được
    nói gì thêm, thì đọc ra là dữ liệu đã mất — nhưng trước test này **không chỗ nào** đo nó
    khác 0: ba đột biến một dòng (`_record`, `_visible`, `_read_back` cùng ghi `0`) đều sống
    sót qua cả bộ test. Một cột không ai đo là một cột sẽ lặng lẽ thành số không.
    """
    client, maker, monkeypatch = stack
    async with maker() as session:
        mine = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        assert mine is not None
        # Bảy lớp tất cả, mà một danh sách chỉ chở sáu. `list_class` không khớp tên —
        # nó liệt kê **mọi** lớp rồi `capped` cắt, nên bảy lớp là đủ để `more` khác 0.
        for name in ("12B", "12C", "12D", "12E", "12G", "12H"):
            session.add(SchoolClass(teacher_id=mine.id, name=name))
        await session.commit()

    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="call_tool", tool_name="list_class", tool_args={}),
        NextStepCompleted(request_id="x", kind="ask_clarify", text="Bạn muốn xem lớp nào?"),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    live = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12 thế nào"}, headers=TEACHER
    )
    assert live.status_code == 200
    # Sáu lớp; "Khác" do FE vẽ, không nằm trong nút.
    assert len(live.json()["choices"]) == 6
    assert live.json()["more_choices"] == 1

    again = await client.get("/api/teacher/chat", headers=TEACHER)

    assert again.json()["more_choices"] == 1
    assert again.json()["turns"][-1]["more_choices"] == 1


@pytest.mark.asyncio
async def test_a_plain_answer_carries_no_buttons_even_with_candidates_in_hand(stack) -> None:
    """Một lời **thông báo** không mang theo nút nào, dù tool vừa trả về candidate.

    Ca này có thật và nó không hiếm: giáo viên hỏi *"lớp 12 thế nào"*, `find_class` trả hai
    candidate, rồi model quyết **nói** chứ không hỏi. Gửi `choices` kèm một câu thông báo thì
    màn hình dựng nó thành thẻ hỏi lại, gấp bong bóng thật đi, và bấm một nút gửi
    `"12A (3 học sinh)"` đi như một câu của giáo viên — một câu giáo viên không hề gõ, trả
    lời một câu hỏi không hề được hỏi.

    `step.kind` chỉ BE biết, nên luật này không có chỗ nào khác để đứng.
    """
    client, maker, monkeypatch = stack
    async with maker() as session:
        mine = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        assert mine is not None
        session.add(SchoolClass(teacher_id=mine.id, name="12B"))
        await session.commit()

    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="call_tool", tool_name="list_class", tool_args={}),
        NextStepCompleted(request_id="x", kind="say", text="Bạn có hai lớp 12: 12A và 12B."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    live = await client.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12 thế nào"}, headers=TEACHER
    )

    assert live.status_code == 200
    assert live.json()["kind"] == "say"
    assert live.json()["choices"] == []

    again = await client.get("/api/teacher/chat", headers=TEACHER)
    assert again.json()["choices"] == []
    assert again.json()["turns"][-1]["choices"] == []


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

        ours = await session.scalar(select(SchoolClass).where(SchoolClass.name == "12A"))
        assert ours is not None

        me = Asking.of(mine)
        my_own = await execute(session, me, "get_class", {"class_id": ours.id})
        by_id = await execute(session, me, "get_class", {"class_id": theirs.id})
        missing = await execute(session, me, "get_class", {"class_id": "lop-chua-bao-gio-co"})

        # Danh sách cũng phải im về lớp ấy: `get_class` chặn một id đoán đúng, còn
        # `list_class` là chỗ một cái tên lọt ra nếu filter `teacher_id` biến mất.
        listed = await execute(session, me, "list_class", {})

    # Không có khẳng định đầu tiên này, test vẫn xanh với một `get_class` chẳng bao
    # giờ tìm thấy gì: hai lời từ chối bên dưới là cùng một hằng số, nên đem chúng so
    # với nhau chỉ chứng minh được rằng một hằng số bằng chính nó.
    assert my_own["found"] is True
    assert my_own["name"] == "12A"

    assert by_id == missing
    assert "11B" not in [one["name"] for one in listed["candidates"]]


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


# Ba mục, không bốn: `create_draft` thôi khai số câu. Một đề trống không có số câu nào
# để khai -- con số ấy chỉ có nghĩa lúc `start_drafting` bắt đầu soạn.
_BRIEF = {
    "subject": "Toán",
    "grade": "12",
    "topic_scope": "chương Hàm số",
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
                args={"assessment_id": "{1.assessment_id}", "question_count": "3"},
                title="Soạn câu hỏi",
            ),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _outline_shown(monkeypatch, 3)

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
            PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống"),
            # Đủ tham số nên plan qua được `vet_plan`, nhưng `question_count` không đọc
            # được thành số: tool từ chối lúc chạy, không ghi gì. Đây là ca "hỏng lúc
            # chạy", khác hẳn ca "plan sai từ đầu" ở test ngay dưới.
            PlanStep(
                tool_name="start_drafting",
                args={"assessment_id": "{1.assessment_id}", "question_count": "rất nhiều"},
                title="Soạn câu hỏi",
            ),
            # Bước này là toàn bộ phép đo: nó hợp lệ, nên thứ duy nhất giữ nó không chạy
            # là luật "một bước đỏ thì dừng". Thiếu nó, test xanh với một vòng lặp chạy
            # tiếp qua mọi lỗi. Một `create_draft` chứ không phải `start_drafting` thứ hai:
            # từ `draft-outline` một plan chỉ soạn một lần, theo một dàn ý.
            PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo thêm một đề"),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _outline_shown(monkeypatch, 3)

    answer = await http.post(
        "/api/teacher/chat/messages", json={"text": "Tạo giúp tôi một đề"}, headers=TEACHER
    )

    assert answer.status_code == 200
    kinds = [turn["kind"] for turn in answer.json()["turns"]]
    # Đúng HAI cặp tool_call/tool_result: bước ba không chạy.
    assert kinds.count("tool_call") == 2

    outcomes = agent.reported[0]["outcomes"]
    assert len(outcomes) == 2
    assert outcomes[0]["ok"] is True
    assert outcomes[1]["ok"] is False

    # Lời kể nói bằng lời người, không chở chữ viết cho model. `reason` của
    # `start_drafting` là "question_count phải là một con số, ví dụ 10" — một câu dặn
    # model, chở theo đúng cái tên field mà giáo viên không cần thấy: `question_count`
    # trên màn hình là mặt trong của hệ thống.
    detail = outcomes[1]["detail"]
    assert detail == "một mục trong yêu cầu chưa dùng được"
    assert "hãy hỏi giáo viên" not in detail
    assert "question_count" not in detail


@pytest.mark.asyncio
async def test_a_plan_naming_a_tool_outside_the_working_catalog_runs_nothing(stack) -> None:
    """Plan hỏng thì **không bước nào** chạy, và lý do về model, không về giáo viên.

    Một bước đỏ ở đây sẽ nói sai: với giáo viên, chưa có gì xảy ra cả. Từ ADR-30 BE cũng không nói
    câu từ chối dọn trước: model được nghe lý do và tự nói lại trong cùng lượt.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _plan(
            PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống"),
            PlanStep(tool_name="list_class", args={"name": "12A"}, title="Tra lớp"),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    answer = await http.post(
        "/api/teacher/chat/messages", json={"text": "Tạo đề cho 12A"}, headers=TEACHER
    )

    assert answer.status_code == 200
    body = answer.json()
    assert [turn["kind"] for turn in body["turns"]] == ["teacher", "assistant"]
    assert "list_class" in _refusal(agent)
    assert body["text"] == "hết kịch bản"
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
    # BE không dựng lời kể thay model (ADR-30): một thông báo hệ thống nói vì sao không có lời kể,
    # còn việc đã xảy ra vẫn nằm trong khối bước.
    assert body["text"] == notices.REPORT_MISSING
    kinds = [turn["kind"] for turn in body["turns"]]
    assert kinds[-1] == "notice"
    assert "tool_call" in kinds


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
                args={"assessment_id": "{1.assessment_id}", "question_count": "3"},
                title="Soạn câu hỏi",
            ),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _outline_shown(monkeypatch, 3)

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
    # Bước của plan mang `tool_name` nhưng `result` là `None`: dòng của nó đi trong `detail`, và
    # FE phân biệt nó với bước tra cứu bằng đúng điều này (review pha 1, `kriky-writes-every-word`).
    steps = [one for one in seen if one.kind.startswith("step_")]
    assert [one.tool_name for one in steps] == ["create_draft"] * 2 + ["start_drafting"] * 2
    assert all(one.result is None for one in steps)

    assert seen[-1].ended_as == "report"


@pytest.mark.asyncio
async def test_a_lookup_before_the_plan_shows_while_it_runs(stack) -> None:
    """Bước tra cứu của pha lên plan cũng phát `step_*`, mang đúng thứ client đọc lại sau F5.

    `kriky-writes-every-word`: đọc sách mất mười mấy giây, và trước bản này màn hình đứng im suốt
    lúc ấy. Sự kiện mang `tool_name` và `tool_result` **đã bỏ chữ sách** (`_client_result`), không
    `index`/`total` -- `bước k/n` chỉ đếm bước của plan (ADR-25).
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="call_tool", tool_name="read_section", tool_args={}),
        NextStepCompleted(request_id="x", kind="say", text="Mình đã đọc xong bài."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    read = {"found": True, "part": 1, "parts": 2, "more": True, "labels": ["Bài 1"], "text": "chữ"}

    async def execute(*_args, **_kwargs) -> dict:
        return dict(read)

    monkeypatch.setattr(teacher_chat, "execute", execute)

    teacher = await _teacher(maker, "GV-001")
    asked = teacher_chat.Said(text="đọc bài 1 giúp mình")
    seen = []
    async with maker() as session:
        async for event in teacher_chat.run_turn(
            asked, _request(), teacher, session, get_settings()
        ):
            seen.append(event)

    assert [one.kind for one in seen] == ["step_started", "step_done", "say", "done"]
    started, done = seen[0], seen[1]
    assert (started.tool_name, started.index, started.total) == ("read_section", 0, 0)
    assert done.tool_name == "read_section"
    assert "text" not in done.result and done.result["elided"] is True
    assert done.result["labels"] == ["Bài 1"]

    # Sau F5, client đọc đúng kết quả ấy -- hai đường, một dòng.
    turns = (await http.get("/api/teacher/chat", headers=TEACHER)).json()["turns"]
    stored = next(one for one in turns if one["kind"] == "tool_result")
    assert stored["tool_result"] == done.result


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
    # Không row nào, model không đề xuất gì: không nút nào, và FE không vẽ thẻ (review T3,
    # `unbiased-model-text`). Vẫn là một câu hỏi: `ended_as` ở trên.
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
    assert "list_class" not in plannable

    spec = next(one for one in asked["plannable"] if one["name"] == "create_draft")
    assert set(spec["arguments"]) >= {"subject", "grade", "topic_scope"}
    soan = next(one for one in asked["plannable"] if one["name"] == "start_drafting")
    assert "question_count" in soan["arguments"]


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
                args={"assessment_id": "{1.khong_co_field_nay}", "question_count": "3"},
                title="Soạn câu hỏi",
            ),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _outline_shown(monkeypatch, 3)
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
                args={"assessment_id": "{1.assessment_id}", "question_count": "3"},
                title="Soạn câu hỏi",
            ),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _outline_shown(monkeypatch, 3)
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
                args={"assessment_id": "{1.assessment_id}", "question_count": "3"},
                title="Soạn câu hỏi",
            ),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _outline_shown(monkeypatch, 3)
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


@pytest.mark.asyncio
async def test_a_finished_drafting_step_carries_the_real_counts(stack) -> None:
    """Bước soạn khi đóng lại đã **biết số câu thật**, và con số ấy nằm trong row.

    Đây là nguyên nhân gốc của chuyện Kriky nói *"đã soạn xong"* mà màn hình không có thẻ
    nào: `_start_drafting` trả `started/queued/assessment_id` và không một con số nào, nên
    không có gì dựng nổi thẻ kết quả — mà panel đề thì chỉ mở được từ một nút trên thẻ.

    Và con số phải vào **row**, không chỉ vào khung SSE. Ghi sau khi `_record` chạy thì màn
    hình đang mở có thẻ còn một lần F5 thì không, tức hai đường của cùng một lượt nói hai
    chuyện khác nhau.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _plan(
            PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống"),
            PlanStep(
                tool_name="start_drafting",
                args={"assessment_id": "{1.assessment_id}", "question_count": "3"},
                title="Soạn câu hỏi",
            ),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _outline_shown(monkeypatch, 3)
    await _teacher(maker, "GV-001")

    _drafting_stack(http, monkeypatch, rings_for={1, 2, 3}, ready_for={1, 2, 3})

    async with http.stream(
        "POST",
        "/api/teacher/chat/messages/stream",
        json={"text": "Tạo đề 3 câu Hàm số"},
        headers=TEACHER,
    ) as answer:
        async for _ in answer.aiter_lines():
            pass

    async with maker() as session:
        row = await session.scalar(
            select(TeacherTurn)
            .where(TeacherTurn.kind == "tool_result", TeacherTurn.tool_name == "start_drafting")
            .order_by(TeacherTurn.sequence.desc())
        )
    assert row is not None
    assert row.tool_result["written"] == 3
    assert row.tool_result["asked_for"] == 3
    assert row.tool_result["still_drafting"] == 0

    # Và đọc lại bằng đúng cửa mà một lần F5 đi qua.
    again = await http.get("/api/teacher/chat", headers=TEACHER)
    assert again.status_code == 200
    drafted = [
        one
        for one in again.json()["turns"]
        if one["kind"] == "tool_result" and one["tool_name"] == "start_drafting"
    ]
    assert drafted and drafted[-1]["tool_result"]["written"] == 3


@pytest.mark.asyncio
async def test_the_post_door_adds_no_counts_it_did_not_wait_for(stack) -> None:
    """Cửa `POST` không đợi, nên nó **không** nói một con số nào về số câu.

    Thẻ kết quả mọc từ chính ba con số ấy, nên cửa này điền chúng bằng một giá trị đoán là
    dựng một thẻ `Đã thêm 0 câu vào đề` cho một đề sắp có đủ câu — đúng cái hại mà vòng
    trước đã đo được một lần ở lời kể.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _plan(
            PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống"),
            PlanStep(
                tool_name="start_drafting",
                args={"assessment_id": "{1.assessment_id}", "question_count": "3"},
                title="Soạn câu hỏi",
            ),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _outline_shown(monkeypatch, 3)
    await _teacher(maker, "GV-001")

    answer = await http.post(
        "/api/teacher/chat/messages", json={"text": "Tạo đề 3 câu Hàm số"}, headers=TEACHER
    )

    assert answer.status_code == 200
    drafted = [
        one
        for one in answer.json()["turns"]
        if one["kind"] == "tool_result" and one["tool_name"] == "start_drafting"
    ]
    assert drafted
    assert "written" not in drafted[-1]["tool_result"]
    assert "asked_for" not in drafted[-1]["tool_result"]


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
                args={"assessment_id": "{1.assessment_id}", "question_count": "3"},
                title="Soạn câu hỏi",
            ),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _outline_shown(monkeypatch, 3)
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
                args={"assessment_id": "{1.assessment_id}", "question_count": "3"},
                title="Soạn câu hỏi",
            ),
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _outline_shown(monkeypatch, 3)
    await _teacher(maker, "GV-001")
    # Câu thứ ba: chính job đã nổ, nên nó rời `pending` mà không mang theo câu nào. Job nổ nay
    # được hỏi lại có trần (plan `backlog-tier-1`); trần một lần để ô hết lượt ngay trong lượt chat.
    monkeypatch.setattr(drafting, "_MOST_ATTEMPTS", 1)
    _drafting_stack(
        http, monkeypatch, rings_for={1, 2}, ready_for={1, 2}, failed_for=frozenset({3})
    )

    frames = await _drafting_frames(http)

    closing = [one for one in frames if one["kind"] == "step_done"][-1]
    assert closing["detail"] == "dừng ở 2/3 câu"


@pytest.mark.asyncio
async def test_an_extra_argument_is_dropped_not_fatal(stack) -> None:
    """Một tham số **lạ** chỉ bị bỏ; plan vẫn chạy.

    Đây là ranh giới giữa hai ca dễ gộp nhầm. *Thiếu* một tham số là plan sai từ đầu — bước
    ấy sẽ chạy với tay không và để lại rác, nên từ chối trọn gói. *Thừa* một tham số thì
    không làm bước nào ghi sai: BE chỉ đưa cho tool những thứ tool nhận.

    Gộp hai ca lại đúng là hồi quy đã đo được: mô tả `create_draft` còn nhắc `title`, nên
    chính mô tả ấy mời model gửi một thứ `vet_plan` giết — và giáo viên nhận *"mình chưa dựng
    được các bước"* cho một yêu cầu hoàn toàn hợp lệ, lần gõ lại cũng hỏng y vậy.

    Và tham số lạ **không được ghi vào lịch sử**: lịch sử là thứ model đọc ở lượt sau, nên
    giữ nó lại là dạy model rằng lần sau cứ gửi tiếp.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _plan(
            PlanStep(
                tool_name="create_draft",
                args={**_BRIEF, "title": "Đề tự đặt tên", "difficulty": "cơ bản"},
                title="Tạo đề trống",
            )
        )
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    await _teacher(maker, "GV-001")

    answer = await http.post(
        "/api/teacher/chat/messages", json={"text": "Tạo đề 3 câu Hàm số"}, headers=TEACHER
    )

    assert answer.status_code == 200
    turns = answer.json()["turns"]
    made = next(one for one in turns if one["kind"] == "tool_result")
    assert made["tool_result"]["created"] is True

    async with maker() as session:
        call = await session.scalar(
            select(TeacherTurn)
            .where(TeacherTurn.kind == "tool_call")
            .order_by(TeacherTurn.sequence.desc())
        )
    assert call is not None
    assert set(call.tool_args) == set(_BRIEF)


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


async def _the_thread(maker) -> str:
    """Id của đoạn chat duy nhất đang có. Dùng sau một lượt đã chạy."""
    async with maker() as session:
        threads = list(await session.scalars(select(TeacherConversation)))
    assert len(threads) == 1, f"cần đúng một đoạn chat, thấy {len(threads)}"
    return threads[0].id


@pytest.mark.asyncio
async def test_a_second_turn_in_the_same_thread_is_refused_while_the_first_runs(stack) -> None:
    """Hai tab cùng một đoạn chat: tab sau bị từ chối, không chen vào.

    Không có khoá thì hai plan chạy xen kẽ trong một đoạn: dãy bước trộn lẫn theo thời gian
    chứ không theo lượt, và `create_draft` -- thứ không idempotent -- để lại hai đề nháp
    trống, một cái không bao giờ được soạn.

    Khoá được giữ bằng tay chứ không bằng cách chạy hai lượt song song thật: cuộc đua thật
    phụ thuộc vào thời điểm, và một test phụ thuộc thời điểm là một test sẽ đỏ vào một ngày
    không liên quan gì tới luật nó canh.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="say", text="Lớp 12A có 40 học sinh."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    await _teacher(maker, "GV-001")

    first = await http.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12A thế nào"}, headers=TEACHER
    )
    assert first.status_code == 200
    thread = await _the_thread(maker)

    async with maker() as session:
        assert await teacher_chat._hold_the_thread(session, thread, 600) is not None

    refused = await http.post(
        "/api/teacher/chat/messages",
        json={"text": "tạo cho tôi một đề", "conversation_id": thread},
        headers=TEACHER,
    )

    assert refused.status_code == 409
    assert refused.json()["detail"] == notices.ALREADY_RUNNING


@pytest.mark.asyncio
async def test_a_refused_turn_leaves_nothing_behind(stack) -> None:
    """Lời từ chối **không** ghi câu giáo viên vừa gõ.

    Khoá đặt trước `_record` chính vì ca này: ghi trước rồi từ chối sau để lại một hàng
    `kind="teacher"` mồ côi, và một lần F5 dựng nó lại thành một câu hỏi không có câu trả
    lời nào -- đúng cái màn hình nói dối mà cả ADR-25 được viết để tránh.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="say", text="Lớp 12A có 40 học sinh."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    await _teacher(maker, "GV-001")

    await http.post("/api/teacher/chat/messages", json={"text": "lớp 12A thế nào"}, headers=TEACHER)
    thread = await _the_thread(maker)
    async with maker() as session:
        before = list(await session.scalars(select(TeacherTurn)))
        assert await teacher_chat._hold_the_thread(session, thread, 600) is not None

    await http.post(
        "/api/teacher/chat/messages",
        json={"text": "câu này không được ghi", "conversation_id": thread},
        headers=TEACHER,
    )

    async with maker() as session:
        after = list(await session.scalars(select(TeacherTurn)))
    assert len(after) == len(before)
    assert all("không được ghi" not in one.text for one in after)


@pytest.mark.asyncio
async def test_a_lock_left_by_a_dead_process_stops_blocking(stack) -> None:
    """Một process chết giữa lượt không chạy `finally` nào, nên cửa sổ quá hạn là đường duy nhất.

    Không có nó thì đoạn chat ấy bị chặn vĩnh viễn và không có lệnh nào để gỡ -- một giáo
    viên mất hẳn một đoạn chat vì một lần BE restart.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="say", text="Lớp 12A có 40 học sinh."),
        NextStepCompleted(request_id="x", kind="say", text="Vẫn trả lời được."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    await _teacher(maker, "GV-001")

    await http.post("/api/teacher/chat/messages", json={"text": "lớp 12A thế nào"}, headers=TEACHER)
    thread = await _the_thread(maker)

    # Một khoá của mười một phút trước, tức quá `TURN_LOCK_STALE_SECONDS=600`.
    async with maker() as session:
        await session.execute(
            update(TeacherConversation)
            .where(TeacherConversation.id == thread)
            .values(running_since=datetime.now(UTC) - timedelta(seconds=660))
        )
        await session.commit()

    again = await http.post(
        "/api/teacher/chat/messages",
        json={"text": "lớp 12A thế nào", "conversation_id": thread},
        headers=TEACHER,
    )

    assert again.status_code == 200
    assert again.json()["text"] == "Vẫn trả lời được."
    # Và lượt vừa chạy đã nhả khoá lúc nó xong, nên đoạn chat lại rảnh.
    async with maker() as session:
        free = await session.scalar(
            select(TeacherConversation.running_since).where(TeacherConversation.id == thread)
        )
    assert free is None


@pytest.mark.asyncio
async def test_a_turn_cut_mid_way_still_lets_go_of_the_thread(stack) -> None:
    """Giáo viên đóng tab giữa lượt không được để lại một đoạn chat bị khoá.

    Đây là ca ngược của khoá, và một lưới chặn tốt mà không nhả thì tệ hơn không có lưới: đoạn
    chat ấy sẽ từ chối mọi câu suốt `TURN_LOCK_STALE_SECONDS`, tức mười phút im lặng cho một
    việc giáo viên làm hàng ngày.

    **Cancel phải theo kiểu anyio, không phải `task.cancel()`.** Cửa SSE chạy trong một cancel
    scope của anyio, và scope ấy *level-triggered*: sau khi cancel, mọi `await` mới bên trong
    raise `CancelledError` ngay. Một bản `asyncio.Task.cancel()` trần thì **xanh cả khi code
    sai** -- ở đó `CancelledError` được giao đúng một lần, nên các `await` trong `finally` vẫn
    chạy xong. Bản đầu của test này đã viết như vậy, và nó bỏ lọt đúng lỗi mà review tìm ra
    ngày 10/10/2026.
    """
    import asyncio

    _, maker, monkeypatch = stack
    started = asyncio.Event()

    async def never_answers(*args, **kwargs):
        started.set()
        await asyncio.sleep(3600)

    monkeypatch.setattr(teacher_chat, "run_task", never_answers)
    teacher = await _teacher(maker, "GV-001")
    asked = teacher_chat.Said(text="tạo đề 10 câu tích phân")

    async def consume():
        async with maker() as session:
            async for _ in teacher_chat.run_turn(
                asked, _request(), teacher, session, get_settings()
            ):
                pass

    async with anyio.create_task_group() as tg:
        tg.start_soon(consume)
        await asyncio.wait_for(started.wait(), timeout=5)
        async with maker() as session:
            while_running = await session.scalar(select(TeacherConversation.running_since))
        assert while_running is not None, "khoá phải đang được giữ trong lúc lượt chạy"
        tg.cancel_scope.cancel()

    async with maker() as session:
        after = await session.scalar(select(TeacherConversation.running_since))
    assert after is None


@pytest.mark.asyncio
async def test_a_turn_that_breaks_still_lets_go_of_the_thread(stack) -> None:
    """Lượt hỏng cũng phải nhả khoá, và đó là lý do `_let_go_of_the_thread` rollback trước.

    Một `AgentError` ở pha 1 thành 503 và lượt chết giữa một session đang lỗi. Không rollback
    thì câu `UPDATE` nhả khoá không chạy nổi, và một lần AGENT ngã làm giáo viên mất đoạn chat
    trong mười phút.
    """

    async def agent_is_down(*args, **kwargs):
        raise teacher_chat.AgentError("hàng đợi chưa sẵn sàng")

    http, maker, monkeypatch = stack
    monkeypatch.setattr(teacher_chat, "run_task", agent_is_down)
    await _teacher(maker, "GV-001")

    broke = await http.post(
        "/api/teacher/chat/messages", json={"text": "lớp 12A thế nào"}, headers=TEACHER
    )

    assert broke.status_code == 503
    async with maker() as session:
        after = await session.scalar(select(TeacherConversation.running_since))
    assert after is None


@pytest.mark.asyncio
async def test_the_stream_says_the_refusal_instead_of_a_status_code(stack) -> None:
    """Cửa SSE không còn status code nào để từ chối bằng, nên nó phải **nói** ra.

    Header đã gửi đi trước khi lượt bắt đầu, nên 409 về dưới dạng một khung `done` mang
    `ended_as="error"`. Chữ phải là nguyên văn câu của BE: màn hình in thẳng thứ nó nhận được
    (`Chat.tsx`), nên một câu rỗng ở đây là một ô nhập khoá lại mà không nói vì sao.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="say", text="Lớp 12A có 40 học sinh."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    await _teacher(maker, "GV-001")

    await http.post("/api/teacher/chat/messages", json={"text": "lớp 12A thế nào"}, headers=TEACHER)
    thread = await _the_thread(maker)
    async with maker() as session:
        assert await teacher_chat._hold_the_thread(session, thread, 600) is not None

    async with http.stream(
        "POST",
        "/api/teacher/chat/messages/stream",
        json={"text": "tạo cho tôi một đề", "conversation_id": thread},
        headers=TEACHER,
    ) as answer:
        assert answer.status_code == 200
        frames = [line async for line in answer.aiter_lines()]

    said = [json.loads(one[len("data: ") :]) for one in frames if one.startswith("data: ")]
    assert [one["kind"] for one in said] == ["done"]
    assert said[0]["ended_as"] == "error"
    assert said[0]["text"] == notices.ALREADY_RUNNING


@pytest.mark.asyncio
async def test_a_turn_that_outlived_its_lock_does_not_wipe_the_next_ones(stack) -> None:
    """Nhả khoá phải có thẻ, nếu không một lượt đã quá hạn xoá khoá của người đang giữ.

    Kịch bản đo được bằng ba câu lệnh dưới đây: lượt A giữ khoá lúc t0 rồi sống lâu hơn cửa sổ
    quá hạn; tab B thấy khoá đã quá hạn nên giành được, ghi t1; A xong và nhả. Một câu
    `UPDATE ... WHERE id = :thread` vô điều kiện khi ấy xoá **khoá của B**, và tab C gửi ngay
    sau đó sẽ được đi -- trả lại đúng hai plan cài răng lược mà cả luật này tồn tại để diệt.

    Đây là ca mà ba test kia không chạm tới: gỡ hai dòng fencing khỏi `_let_go_of_the_thread`
    thì cả bộ test vẫn xanh. Đo ngày 10/10/2026.
    """
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="say", text="Lớp 12A có 40 học sinh."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    await _teacher(maker, "GV-001")
    await http.post("/api/teacher/chat/messages", json={"text": "lớp 12A thế nào"}, headers=TEACHER)
    thread = await _the_thread(maker)

    async with maker() as session:
        # Lượt A giữ khoá.
        a = await teacher_chat._hold_the_thread(session, thread, 600)
        assert a is not None

        # Rồi A sống lâu hơn cửa sổ, nên B giành được: khoá nay là của B.
        b = datetime.now(UTC)
        await session.execute(
            update(TeacherConversation)
            .where(TeacherConversation.id == thread)
            .values(running_since=b)
        )
        await session.commit()

        # A xong và nhả khoá của **chính nó**.
        await teacher_chat._let_go_of_the_thread(session, thread, a)

        still = await session.scalar(
            select(TeacherConversation.running_since).where(TeacherConversation.id == thread)
        )

    assert still is not None, "khoá của B đã bị lượt A xoá mất"


async def _a_book(maker, teacher_code: str, document_id: str) -> None:
    """Một tài liệu đã sẵn sàng trong thư viện của giáo viên này."""
    async with maker() as session:
        owner = await session.scalar(select(Teacher).where(Teacher.teacher_code == teacher_code))
        session.add(
            Document(
                id=document_id,
                teacher_id=owner.id,
                filename="SGK Toán 6.pdf",
                byte_size=10,
                storage_key=f"k/{document_id}",
                state=DocumentState.READY.value,
                uploaded_at=datetime.now(UTC),
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_the_chip_on_the_message_reaches_the_assistant(stack) -> None:
    """`draft-from-document`: chip đang đính đi tới AGENT, và mở ra hai tool đọc mục lục."""
    client, maker, monkeypatch = stack
    await _a_book(maker, "GV-001", "book")
    agent = ScriptedAgent(NextStepCompleted(request_id="x", kind="say", text="Rõ rồi."))
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages",
        json={"text": "soạn 10 câu chương 1", "document_id": "book"},
        headers=TEACHER,
    )

    assert reply.status_code == 200
    asked = agent.asked[0]
    assert asked["attached_document"] == {
        "document_id": "book",
        "filename": "SGK Toán 6.pdf",
        "state": "ready",
    }
    offered = {spec["name"] for spec in asked["catalog"]}
    assert {"list_chapters", "get_chapter"} <= offered


@pytest.mark.asyncio
async def test_someone_elses_chip_is_as_if_nothing_was_attached(stack) -> None:
    """Chip trỏ tới sách của người khác: AGENT không nghe gì về nó, và không thấy tool mục lục."""
    client, maker, monkeypatch = stack
    await _a_book(maker, "GV-002", "theirs")
    agent = ScriptedAgent(NextStepCompleted(request_id="x", kind="say", text="Rõ rồi."))
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    await client.post(
        "/api/teacher/chat/messages",
        json={"text": "soạn 10 câu chương 1", "document_id": "theirs"},
        headers=TEACHER,
    )

    asked = agent.asked[0]
    assert asked["attached_document"] is None
    assert not {"list_chapters", "get_chapter"} & {spec["name"] for spec in asked["catalog"]}
    create = next(spec for spec in asked["plannable"] if spec["name"] == "create_draft")
    assert "document_id" not in create["arguments"]


def _bound_book() -> MemoryContentReader:
    """Một cây hai chương cho tài liệu `book`, đặt vào reader của process."""
    built = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
    nodes = [
        IndexNode(
            document_id="book",
            ordinal=ordinal,
            level=1,
            numbering=numbering,
            title=title,
            title_source=TitleSource.TEXT,
            anchor=BlockRef(page=ordinal + 1, block=0),
            page_start=ordinal + 1,
            page_end=ordinal + 2,
        )
        for ordinal, numbering, title in (
            (0, "Chương I", "SỐ TỰ NHIÊN"),
            (1, "Chương II", "SỐ NGUYÊN"),
        )
    ]
    reader = MemoryContentReader()
    reader.trees["book"] = (
        IndexHeader(
            document_id="book",
            raw_started_at=built,
            method=IndexMethod.RULES,
            node_count=2,
            chunk_count=0,
            built_at=built,
        ),
        nodes,
    )
    bind_reader(reader)
    return reader


@pytest.mark.asyncio
async def test_the_book_survives_the_chip_leaving_the_composer(stack) -> None:
    """Review B3 (`draft-from-document`): lượt 1 có chip và hỏi lại bằng tên chương; lượt 2 -- giáo
    viên bấm nút, **không** còn chip -- vẫn mở đề với tài liệu. Trước bản sửa, pha 2 cắt
    `document_id` và đề mở ra trơn."""
    client, maker, monkeypatch = stack
    await _a_book(maker, "GV-001", "book")
    _bound_book()
    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x",
            kind="call_tool",
            tool_name="list_chapters",
            tool_args={"document_id": "book"},
        ),
        NextStepCompleted(request_id="x", kind="ask_clarify", text="Bạn muốn chương nào?"),
        NextStepCompleted(
            request_id="x",
            kind="plan",
            text="Được, mình soạn đề ngay.",
            steps=(
                PlanStep(
                    tool_name="create_draft",
                    args={
                        "subject": "Toán",
                        "grade": "6",
                        "topic_scope": "Chương I",
                        "document_id": "book",
                        "nodes": "0",
                    },
                    title="Tạo đề trống",
                ),
            ),
        ),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    first = await client.post(
        "/api/teacher/chat/messages",
        json={"text": "soạn đề từ sách này", "document_id": "book"},
        headers=TEACHER,
    )
    assert first.json()["choices"] == [
        "Chương I. SỐ TỰ NHIÊN (tr. 1–2)",
        "Chương II. SỐ NGUYÊN (tr. 2–3)",
    ]
    second = await client.post(
        "/api/teacher/chat/messages",
        json={
            "text": "Chương I. SỐ TỰ NHIÊN (tr. 1–2)",
            "conversation_id": first.json()["conversation_id"],
        },
        headers=TEACHER,
    )

    assert second.status_code == 200
    # Lượt 2 thấy tham số tài liệu dù không có chip ...
    create = next(spec for spec in agent.asked[-1]["plannable"] if spec["name"] == "create_draft")
    assert "document_id" in create["arguments"]
    # ... và đề mở ra **mang** tài liệu.
    async with maker() as session:
        brief = await session.scalar(select(DraftBrief))
    assert (brief.document_id, brief.scope_nodes) == ("book", [0])
    bind_reader(None)


@pytest.mark.asyncio
async def test_opening_the_library_mid_turn_brings_the_chapters_into_view(stack) -> None:
    """Không chip, model gọi `list_documents`: bước kế tiếp mới thấy `list_chapters`."""
    client, maker, monkeypatch = stack
    await _a_book(maker, "GV-001", "book")
    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x", kind="call_tool", tool_name="list_documents", tool_args={}
        ),
        NextStepCompleted(request_id="x", kind="say", text="Bạn có một cuốn sách."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    await client.post(
        "/api/teacher/chat/messages", json={"text": "soạn từ sách của mình"}, headers=TEACHER
    )

    before, after = ({spec["name"] for spec in one["catalog"]} for one in agent.asked[:2])
    assert "list_chapters" not in before
    assert {"list_chapters", "get_chapter"} <= after


@pytest.mark.asyncio
async def test_the_book_survives_a_turn_that_never_opened_it(stack) -> None:
    """Review B4 (`draft-from-document`): lượt 1 có chip nhưng Kriky hỏi lại ngay, không gọi tool
    đọc nào; lượt 2 không còn chip vẫn biết cuốn sách -- chip được lưu cùng câu của giáo viên, không
    chỉ sống một lượt."""
    client, maker, monkeypatch = stack
    await _a_book(maker, "GV-001", "book")
    _bound_book()
    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="ask_clarify", text="Đề cho khối mấy?"),
        NextStepCompleted(
            request_id="x",
            kind="plan",
            text="Được, mình soạn đề ngay.",
            steps=(
                PlanStep(
                    tool_name="create_draft",
                    args={
                        "subject": "Toán",
                        "grade": "6",
                        "topic_scope": "cả sách",
                        "document_id": "book",
                        "nodes": "0,1",
                    },
                    title="Tạo đề trống",
                ),
            ),
        ),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    first = await client.post(
        "/api/teacher/chat/messages",
        json={"text": "soạn 10 câu từ sách này", "document_id": "book"},
        headers=TEACHER,
    )
    await client.post(
        "/api/teacher/chat/messages",
        json={"text": "lớp 6", "conversation_id": first.json()["conversation_id"]},
        headers=TEACHER,
    )

    assert agent.asked[-1]["attached_document"]["document_id"] == "book"
    async with maker() as session:
        brief = await session.scalar(select(DraftBrief))
    assert brief.document_id == "book"
    bind_reader(None)


@pytest.mark.asyncio
async def test_a_new_chip_that_cannot_be_used_does_not_fall_back_to_the_old_one(stack) -> None:
    """Review B5 (`draft-from-document`): chip mới trỏ tới sách chưa sẵn sàng thì lượt này **không**
    có sách -- không lặng lẽ soạn từ chip cũ trong khi giáo viên vừa chỉ một cuốn khác."""
    client, maker, monkeypatch = stack
    await _a_book(maker, "GV-001", "old")
    await _a_book(maker, "GV-001", "new")
    async with maker() as session:
        newer = await session.get(Document, "new")
        newer.state = DocumentState.PROCESSING.value
        await session.commit()
    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="say", text="Rõ rồi."),
        NextStepCompleted(request_id="x", kind="say", text="Rõ rồi."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    first = await client.post(
        "/api/teacher/chat/messages",
        json={"text": "dùng sách này", "document_id": "old"},
        headers=TEACHER,
    )
    await client.post(
        "/api/teacher/chat/messages",
        json={
            "text": "đổi sang sách kia",
            "document_id": "new",
            "conversation_id": first.json()["conversation_id"],
        },
        headers=TEACHER,
    )

    assert agent.asked[0]["attached_document"]["document_id"] == "old"
    # Review B6 (`draft-from-document`): chip chưa sẵn sàng vẫn tới AGENT, **đánh dấu** chưa sẵn
    # sàng -- không bị bỏ lặng lẽ, và không lùi về sách cũ. Không có mục lục nào để đọc nên tool mục
    # lục không hiện.
    assert agent.asked[-1]["attached_document"] == {
        "document_id": "new",
        "filename": "SGK Toán 6.pdf",
        "state": "processing",
    }
    assert "list_chapters" not in {spec["name"] for spec in agent.asked[-1]["catalog"]}


@pytest.mark.asyncio
async def test_a_conversation_bound_to_a_book_cannot_open_a_bookless_draft(stack) -> None:
    """Review B6 (`draft-from-document`): chip sẵn sàng thì `document_id` của `create_draft` là
    **bắt buộc** -- model bỏ nó là `vet_plan` từ chối, chứ không lặng lẽ mở một đề không sách trong
    đoạn chat về sách."""
    client, maker, monkeypatch = stack
    await _a_book(maker, "GV-001", "book")
    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x",
            kind="plan",
            text="Được, mình soạn đề ngay.",
            steps=(
                PlanStep(
                    tool_name="create_draft",
                    args={"subject": "Toán", "grade": "6", "topic_scope": "chương 1"},
                    title="Tạo đề trống",
                ),
            ),
        ),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    await client.post(
        "/api/teacher/chat/messages",
        json={"text": "soạn 10 câu chương 1", "document_id": "book"},
        headers=TEACHER,
    )

    create = next(spec for spec in agent.asked[0]["plannable"] if spec["name"] == "create_draft")
    assert create["optional"] == []
    async with maker() as session:
        assert (
            await session.scalar(select(Assessment).where(Assessment.title == "Đề chương 1"))
            is None
        )


@pytest.mark.asyncio
async def test_reading_the_contents_mid_turn_keeps_the_book_required(stack) -> None:
    """Review B7 (`draft-from-document`): đúng luồng skill dặn -- `list_chapters` trước, plan sau --
    tham số tài liệu vẫn **bắt buộc** ở bước plan; trước bản sửa, tính lại catalog giữa lượt làm
    chúng tuỳ chọn lại."""
    client, maker, monkeypatch = stack
    await _a_book(maker, "GV-001", "book")
    _bound_book()
    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x",
            kind="call_tool",
            tool_name="list_chapters",
            tool_args={"document_id": "book"},
        ),
        NextStepCompleted(request_id="x", kind="say", text="Rõ rồi."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    await client.post(
        "/api/teacher/chat/messages",
        json={"text": "soạn 10 câu chương 1", "document_id": "book"},
        headers=TEACHER,
    )

    create = next(spec for spec in agent.asked[-1]["plannable"] if spec["name"] == "create_draft")
    assert create["optional"] == []
    bind_reader(None)


@pytest.mark.asyncio
async def test_a_unit_read_from_another_book_is_not_pinned_on_the_attached_one(stack) -> None:
    """Review B7 (`draft-from-document`): chip là `book`, model đọc mục lục của `other` rồi gửi
    `nodes` mà quên `document_id`. Điền `book` vào là mở đề trên một mục của sách khác -- nay không
    điền, và lời từ chối nói lý do thay cho câu chung."""
    client, maker, monkeypatch = stack
    await _a_book(maker, "GV-001", "book")
    await _a_book(maker, "GV-001", "other")
    reader = _bound_book()
    reader.trees["other"] = reader.trees["book"]
    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x",
            kind="call_tool",
            tool_name="list_chapters",
            tool_args={"document_id": "other"},
        ),
        NextStepCompleted(
            request_id="x",
            kind="plan",
            text="Được.",
            steps=(
                PlanStep(
                    tool_name="create_draft",
                    args={
                        "subject": "Toán",
                        "grade": "6",
                        "topic_scope": "Chương II",
                        "nodes": "1",
                    },
                    title="Tạo đề trống",
                ),
            ),
        ),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages",
        json={"text": "soạn từ cuốn kia", "document_id": "book"},
        headers=TEACHER,
    )

    async with maker() as session:
        assert await session.scalar(select(DraftBrief)) is None
    assert "chương hay bài của tài liệu" in _refusal(agent)
    assert reply.json()["text"] == "hết kịch bản"
    bind_reader(None)


@pytest.mark.asyncio
async def test_a_chip_whose_job_died_is_read_as_failed_like_the_library(stack) -> None:
    """Review B7 (`draft-from-document`): cột còn `processing` mãi khi job chết; thư viện đọc ra *xử
    lý hỏng*, khung chat phải đọc y vậy -- không bảo giáo viên chờ một thứ không bao giờ tới."""
    client, maker, monkeypatch = stack
    await _a_book(maker, "GV-001", "dead")
    async with maker() as session:
        row = await session.get(Document, "dead")
        row.state = DocumentState.PROCESSING.value
        row.uploaded_at = datetime.now(UTC) - timedelta(hours=2)
        await session.commit()
    agent = ScriptedAgent(NextStepCompleted(request_id="x", kind="say", text="Rõ rồi."))
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    await client.post(
        "/api/teacher/chat/messages",
        json={"text": "soạn đề từ file này", "document_id": "dead"},
        headers=TEACHER,
    )

    assert agent.asked[0]["attached_document"]["state"] == "failed"


@pytest.mark.asyncio
async def test_a_chip_not_yet_usable_takes_draft_opening_off_the_table(stack) -> None:
    """Review B7 (`draft-from-document`): chip chưa dùng được mà model vẫn mở đề không sách -- lời
    dặn không giữ được nó, nên `create_draft` rời catalog lượt ấy; nêu nó thì lời từ chối gọi đúng
    tên tài liệu."""
    client, maker, monkeypatch = stack
    await _a_book(maker, "GV-001", "busy")
    async with maker() as session:
        row = await session.get(Document, "busy")
        row.state = DocumentState.PROCESSING.value
        await session.commit()
    agent = ScriptedAgent(
        NextStepCompleted(
            request_id="x",
            kind="plan",
            text="Được.",
            steps=(
                PlanStep(
                    tool_name="create_draft",
                    args={"subject": "Toán", "grade": "6", "topic_scope": "chương 1"},
                    title="Tạo đề trống",
                ),
            ),
        ),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages",
        json={"text": "soạn đề từ file này", "document_id": "busy"},
        headers=TEACHER,
    )

    assert "create_draft" not in {spec["name"] for spec in agent.asked[0]["plannable"]}
    assert "chưa dùng được" in _refusal(agent)
    assert reply.json()["text"] == "hết kịch bản"
    async with maker() as session:
        assert await session.scalar(select(DraftBrief)) is None


# ------------------------------------------------------------------ dàn ý (`draft-outline`)


def _outline_item(**overrides: object) -> OutlineItem:
    fields: dict[str, object] = {
        "questions": 2,
        "knowledge": "Đọc và viết số tự nhiên",
        "formulas": ("$\\overline{ab} = 10a + b$",),
        "approach": "Cho một số, chọn cách đọc đúng",
        "source_nodes": (0,),
    }
    fields.update(overrides)
    return OutlineItem.model_validate(fields)


def _outline_step(*items: OutlineItem, first: int | None = None, **args: str) -> NextStepCompleted:
    """Một lượt dàn ý model nêu: các mục, và **lời Kriky** khớp chúng (ADR-30).

    Lời nêu `Câu k` đầu mỗi mục, một công thức của mục và một câu hỏi -- đủ để qua phép đối chiếu
    nhẹ của `outline.check_message`. Câu đầu suy từ việc: đề mới là 1, thay câu là chính câu ấy,
    soạn thêm là 3 (các test soạn thêm chạy trên một đề 2 câu); `first` ghi đè.
    """
    outline = items or (_outline_item(),)
    purpose = args.get("for", "new")
    number = first or (
        int(args["question"]) if purpose == "replace" else 3 if purpose == "more" else 1
    )
    lines = ["Mình đã đọc chương I, đề xuất dàn ý thế này:", ""]
    for item in outline:
        span = (
            f"Câu {number}"
            if item.questions == 1
            else f"Câu {number}–{number + item.questions - 1}"
        )
        formula = f" {item.formulas[0]}" if item.formulas else ""
        lines.append(f"- **{span}:** {item.knowledge}{formula}")
        number += item.questions
    lines += ["", "Bạn đồng ý với dàn ý này không?"]
    return NextStepCompleted(
        request_id="x",
        kind="outline",
        text="\n".join(lines),
        outline=outline,
        tool_args=dict(args),
    )


@pytest.mark.asyncio
async def test_the_outline_shown_is_kriky_s_own_words_and_the_items_are_stored(stack) -> None:
    """ADR-30: lời dàn ý trên màn hình là lời Kriky viết, nguyên văn; các mục -- thứ đi vào job --
    lưu cạnh nó; và một lần F5 cho lại đúng lời ấy."""
    client, maker, monkeypatch = stack
    await _a_book(maker, "GV-001", "book")
    _bound_book()
    step = _outline_step()
    monkeypatch.setattr(teacher_chat, "run_task", ScriptedAgent(step))

    reply = await client.post(
        "/api/teacher/chat/messages",
        json={"text": "soạn 2 câu chương 1", "document_id": "book"},
        headers=TEACHER,
    )

    async with maker() as session:
        row = await session.scalar(select(TeacherTurn).where(TeacherTurn.kind == "outline"))
    expected = step.text
    assert reply.json()["text"] == expected
    assert row.text == expected
    assert row.tool_result["items"] == [_outline_item().model_dump(mode="json")]
    assert (row.tool_result["for"], row.tool_result["first"]) == ("new", 1)
    assert row.tool_result["document_id"] == "book"
    again = await client.get("/api/teacher/chat", headers=TEACHER)
    assert [one["text"] for one in again.json()["turns"] if one["kind"] == "outline"] == [expected]
    bind_reader(None)


@pytest.mark.asyncio
async def test_an_outline_be_refuses_goes_back_to_the_model_not_to_the_teacher(stack) -> None:
    client, maker, monkeypatch = stack
    await _a_book(maker, "GV-001", "book")
    _bound_book()
    agent = ScriptedAgent(
        _outline_step(_outline_item(source_nodes=(99,))),
        _outline_step(),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages",
        json={"text": "soạn 2 câu chương 1", "document_id": "book"},
        headers=TEACHER,
    )

    # Lần hỏi thứ hai mang lời từ chối của BE; giáo viên chỉ thấy bản đúng.
    assert len(agent.asked) == 2
    told = agent.asked[1]["history"][-1]
    assert told["tool_name"] == "outline" and "[99]" in told["tool_result"]["error"]
    assert reply.json()["text"] == _outline_step().text
    async with maker() as session:
        names = list(await session.scalars(select(TeacherTurn.tool_name)))
    assert "outline" not in names
    bind_reader(None)


@pytest.mark.asyncio
async def test_an_outline_without_a_book_points_at_no_lesson(stack) -> None:
    client, maker, monkeypatch = stack
    step = _outline_step(_outline_item(source_nodes=()))
    monkeypatch.setattr(teacher_chat, "run_task", ScriptedAgent(step))

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "soạn 2 câu Toán 6"}, headers=TEACHER
    )

    assert "Theo:" not in reply.json()["text"]
    async with maker() as session:
        row = await session.scalar(select(TeacherTurn).where(TeacherTurn.kind == "outline"))
    assert row.tool_result["document_id"] == ""


@pytest.mark.asyncio
async def test_a_message_that_drifts_from_its_outline_goes_back_to_the_model(stack) -> None:
    """ADR-30: lời không nhắc câu đầu của mục, hay không hỏi giáo viên, bị trả về model như một kết
    quả tool; giáo viên chỉ thấy lời đã khớp các mục."""
    client, _, monkeypatch = stack
    drifted = NextStepCompleted(
        request_id="x",
        kind="outline",
        text="Mình soạn hai câu về đọc số tự nhiên nhé.",
        outline=(_outline_item(source_nodes=()),),
    )
    good = _outline_step(_outline_item(source_nodes=()))
    agent = ScriptedAgent(drifted, good)
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "soạn 2 câu"}, headers=TEACHER
    )

    told = agent.asked[1]["history"][-1]
    assert told["tool_name"] == "outline" and "Câu 1" in told["tool_result"]["error"]
    assert reply.json()["text"] == good.text


@pytest.mark.asyncio
async def test_an_outline_refused_twice_for_the_same_reason_stops_the_turn(stack) -> None:
    """Review code 17/10 (plan `backlog-tier-1`): dàn ý bị trả về cũng dừng ở lần hai như plan --
    không gọi model tới trần cho cùng một lời từ chối."""
    client, _, monkeypatch = stack
    drifted = NextStepCompleted(
        request_id="x",
        kind="outline",
        text="Mình soạn hai câu về đọc số tự nhiên nhé.",
        outline=(_outline_item(source_nodes=()),),
    )
    agent = ScriptedAgent(*[drifted for _ in range(20)])
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    reply = await client.post(
        "/api/teacher/chat/messages", json={"text": "soạn 2 câu"}, headers=TEACHER
    )

    body = reply.json()
    assert body["text"] == notices.OUTLINE_REFUSED
    assert body["turns"][-1]["kind"] == "notice"
    assert len(agent.asked) == 2


@pytest.mark.asyncio
async def test_each_new_outline_in_a_thread_is_the_next_version(stack) -> None:
    client, maker, monkeypatch = stack
    bookless = _outline_step(_outline_item(source_nodes=()))
    monkeypatch.setattr(teacher_chat, "run_task", ScriptedAgent(bookless, bookless))

    await client.post("/api/teacher/chat/messages", json={"text": "soạn 2 câu"}, headers=TEACHER)
    await client.post("/api/teacher/chat/messages", json={"text": "câu 2 đổi đi"}, headers=TEACHER)

    # Lời do Kriky viết không mang số bản (ADR-30); số bản sống ở chính lượt dàn ý.
    async with maker() as session:
        kept = list(
            await session.scalars(
                select(TeacherTurn.tool_result)
                .where(TeacherTurn.kind == "outline")
                .order_by(TeacherTurn.sequence)
            )
        )
    assert [one["version"] for one in kept] == [1, 2]


@pytest.mark.asyncio
async def test_a_revised_outline_with_an_empty_brief_keeps_the_earlier_one(stack) -> None:
    """Backlog *Haiku để trống known*: dàn ý sửa không mang môn, khối, phạm vi thì lấy của dàn ý
    trước -- *"oke"* sau đó dựng plan từ dàn ý, không lùi về plan của model."""
    client, maker, monkeypatch = stack
    first = _outline_step(
        _outline_item(source_nodes=()), subject="Toán", grade="7", topic_scope="tỉ lệ thức"
    )
    second = _outline_step(_outline_item(source_nodes=()), subject="Toán")
    monkeypatch.setattr(teacher_chat, "run_task", ScriptedAgent(first, second))

    await client.post("/api/teacher/chat/messages", json={"text": "soạn 2 câu"}, headers=TEACHER)
    await client.post("/api/teacher/chat/messages", json={"text": "câu 2 đổi đi"}, headers=TEACHER)

    async with maker() as session:
        kept = list(
            await session.scalars(
                select(TeacherTurn.tool_result)
                .where(TeacherTurn.kind == "outline")
                .order_by(TeacherTurn.sequence)
            )
        )
    assert kept[1]["brief"] == {"subject": "Toán", "grade": "7", "topic_scope": "tỉ lệ thức"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("args", "error"),
    [({"for": "more"}, "chưa có đề"), ({"for": "khác"}, "for phải là")],
)
async def test_an_outline_for_a_draft_that_is_not_there_is_refused(
    stack, args: dict, error: str
) -> None:
    client, _, monkeypatch = stack
    agent = ScriptedAgent(_outline_step(_outline_item(source_nodes=()), **args))
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    await client.post("/api/teacher/chat/messages", json={"text": "soạn thêm"}, headers=TEACHER)

    assert error in agent.asked[1]["history"][-1]["tool_result"]["error"]


def _open_and_draft(count: str) -> NextStepCompleted:
    return _plan(
        PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề trống"),
        PlanStep(
            tool_name="start_drafting",
            args={"assessment_id": "{1.assessment_id}", "question_count": count},
            title="Soạn câu hỏi",
        ),
    )


@pytest.mark.asyncio
async def test_no_question_is_drafted_before_the_teacher_has_seen_an_outline(stack) -> None:
    """ADR-29: plan soạn câu mà chưa có dàn ý nào hiện ở lượt trước thì về lại với model."""
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(_open_and_draft("3"))
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    await http.post("/api/teacher/chat/messages", json={"text": "soạn 3 câu"}, headers=TEACHER)

    told = agent.asked[1]["history"][-1]
    assert told["tool_name"] == "plan" and "dàn ý" in told["tool_result"]["error"]
    async with maker() as session:
        assert await session.scalar(select(DraftBrief)) is None


@pytest.mark.asyncio
async def test_an_outline_seen_last_turn_becomes_the_draft_once_and_only_once(stack) -> None:
    http, maker, monkeypatch = stack
    bookless = _outline_step(_outline_item(source_nodes=()))
    agent = ScriptedAgent(bookless, _open_and_draft(""), _open_and_draft(""))
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _drafting_stack(http, monkeypatch, rings_for=set(), ready_for=set())

    await http.post("/api/teacher/chat/messages", json={"text": "soạn 2 câu"}, headers=TEACHER)
    await http.post("/api/teacher/chat/messages", json={"text": "oke"}, headers=TEACHER)

    async with maker() as session:
        brief = await session.scalar(select(DraftBrief))
        rows = list(await session.scalars(select(DraftItem).order_by(DraftItem.ordinal)))
    # Số câu BE điền từ dàn ý (2), và mỗi câu nhận mục của nó.
    assert [item["knowledge"] for item in brief.outline] == ["Đọc và viết số tự nhiên"]
    assert [(row.outline_item, row.item_part) for row in rows] == [(0, 1), (0, 2)]

    # Cùng dàn ý ấy, plan thứ hai: không soạn lần nữa.
    await http.post("/api/teacher/chat/messages", json={"text": "soạn lại đi"}, headers=TEACHER)
    told = agent.asked[-1]["history"][-1]
    assert told["tool_name"] == "plan" and "chưa thấy dàn ý" in told["tool_result"]["error"]


@pytest.mark.asyncio
async def test_an_outline_from_before_the_last_teacher_message_is_not_an_approval(stack) -> None:
    """Thử tay 15/10/2026: dàn ý bỏ dở mấy lượt trước không được dùng cho một lời xin mới gõ."""
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(
        _outline_step(_outline_item(source_nodes=())),
        NextStepCompleted(request_id="x", kind="say", text="Bạn muốn đổi gì?"),
        _open_and_draft(""),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    await http.post("/api/teacher/chat/messages", json={"text": "soạn 2 câu"}, headers=TEACHER)
    await http.post("/api/teacher/chat/messages", json={"text": "khoan đã"}, headers=TEACHER)
    await http.post("/api/teacher/chat/messages", json={"text": "soạn 2 câu"}, headers=TEACHER)

    told = agent.asked[-1]["history"][-1]
    assert told["tool_name"] == "plan" and "chưa thấy dàn ý" in told["tool_result"]["error"]
    async with maker() as session:
        assert await session.scalar(select(DraftBrief)) is None


@pytest.mark.asyncio
async def test_an_agreement_retyped_after_a_turn_that_never_answered_still_drafts(
    stack,
) -> None:
    """Review đợt 6: lượt *"oke"* hỏng trước khi Kriky đáp để lại một câu mồ côi; gõ lại vẫn
    duyệt."""
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(_outline_step(_outline_item(source_nodes=())), _open_and_draft(""))
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _drafting_stack(http, monkeypatch, rings_for=set(), ready_for=set())

    await http.post("/api/teacher/chat/messages", json={"text": "soạn 2 câu"}, headers=TEACHER)
    async with maker() as session:
        last = await session.scalar(select(func.max(TeacherTurn.sequence)))
        session.add(
            TeacherTurn(
                conversation_id=(await session.scalar(select(TeacherTurn.conversation_id))),
                sequence=last + 1,
                kind="teacher",
                text="oke",
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
    await http.post("/api/teacher/chat/messages", json={"text": "oke"}, headers=TEACHER)

    async with maker() as session:
        assert await session.scalar(select(DraftBrief)) is not None


@pytest.mark.asyncio
async def test_a_plan_asking_for_more_questions_than_the_outline_is_refused(stack) -> None:
    http, _, monkeypatch = stack
    agent = ScriptedAgent(_outline_step(_outline_item(source_nodes=())), _open_and_draft("5"))
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    await http.post("/api/teacher/chat/messages", json={"text": "soạn 2 câu"}, headers=TEACHER)
    await http.post("/api/teacher/chat/messages", json={"text": "oke"}, headers=TEACHER)

    told = agent.asked[-1]["history"][-1]
    assert "có 2 câu, plan lại xin 5" in told["tool_result"]["error"]


@pytest.mark.asyncio
async def test_drafting_more_needs_an_outline_for_more_and_finds_the_draft_itself(stack) -> None:
    """Soạn thêm: dàn ý `for=more`, và BE điền `assessment_id` của đề mới nhất khi model quên."""
    http, maker, monkeypatch = stack
    bookless = _outline_item(source_nodes=())
    more = _outline_step(_outline_item(questions=1, source_nodes=()), **{"for": "more"})
    only_more = _plan(
        PlanStep(
            tool_name="start_drafting",
            args={"assessment_id": "", "question_count": ""},
            title="Soạn thêm câu",
        )
    )
    agent = ScriptedAgent(_outline_step(bookless), _open_and_draft(""), more, only_more)
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _drafting_stack(http, monkeypatch, rings_for=set(), ready_for={1, 2})

    for said in ("soạn 2 câu", "oke"):
        await http.post("/api/teacher/chat/messages", json={"text": said}, headers=TEACHER)

    # Hai câu đầu về đề -- `for=more` cần đề đã có câu. Cửa POST không nghe chuông, nên kết quả
    # được trả thẳng cho `harvest`.
    async def ready(pool, settings, job_id):
        return "ready", DraftQuestionCompleted(
            request_id="r", question=_question(job_id)
        ).model_dump(mode="json")

    monkeypatch.setattr(drafting, "collect_result", ready)
    async with maker() as session:
        draft = await session.scalar(select(DraftBrief))
        await drafting.harvest(session, None, get_settings(), draft.assessment_id)
    for said in ("soạn thêm 1 câu", "oke"):
        reply = await http.post("/api/teacher/chat/messages", json={"text": said}, headers=TEACHER)

    assert "Câu 3:" in agent.asked[3]["history"][-2]["text"]  # dàn ý đếm tiếp từ câu 3
    async with maker() as session:
        rows = list(await session.scalars(select(DraftItem).order_by(DraftItem.ordinal)))
    assert [(row.ordinal, row.outline_item) for row in rows] == [(1, 0), (2, 0), (3, 1)]
    assert reply.status_code == 200


@pytest.mark.asyncio
async def test_one_outline_drafts_once_even_inside_one_plan(stack) -> None:
    """Review đợt 3 (`draft-outline`): hai cặp mở-đề-rồi-soạn trong một plan là hai đề từ một lần
    duyệt."""
    http, maker, monkeypatch = stack
    twice = _plan(*_open_and_draft("").steps, *_open_and_draft("").steps)
    agent = ScriptedAgent(_outline_step(_outline_item(source_nodes=())), twice)
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    for said in ("soạn 2 câu", "oke"):
        await http.post("/api/teacher/chat/messages", json={"text": said}, headers=TEACHER)

    assert "một plan chỉ soạn một lần" in agent.asked[-1]["history"][-1]["tool_result"]["error"]
    async with maker() as session:
        assert await session.scalar(select(DraftBrief)) is None


@pytest.mark.asyncio
async def test_a_bookless_outline_cannot_open_a_draft_on_a_book(stack) -> None:
    http, maker, monkeypatch = stack
    await _a_book(maker, "GV-001", "book")
    _bound_book()
    on_a_book = _plan(
        PlanStep(
            tool_name="create_draft",
            args={**_BRIEF, "document_id": "book", "nodes": "0"},
            title="Tạo đề",
        ),
        *_open_and_draft("").steps[1:],
    )
    agent = ScriptedAgent(_outline_step(_outline_item(source_nodes=())), on_a_book)
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    for said in ("soạn 2 câu", "oke"):
        await http.post("/api/teacher/chat/messages", json={"text": said}, headers=TEACHER)

    told = agent.asked[-1]["history"][-1]["tool_result"]["error"]
    assert "tài liệu khác tài liệu của dàn ý" in told
    bind_reader(None)


@pytest.mark.asyncio
async def test_a_new_outline_cannot_be_drafted_without_opening_a_draft(stack) -> None:
    http, _, monkeypatch = stack
    only_draft = _plan(*_open_and_draft("").steps[1:])
    agent = ScriptedAgent(_outline_step(_outline_item(source_nodes=())), only_draft)
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    for said in ("soạn 2 câu", "oke"):
        await http.post("/api/teacher/chat/messages", json={"text": said}, headers=TEACHER)

    told = agent.asked[-1]["history"][-1]["tool_result"]["error"]
    assert "cần create_draft rồi start_drafting" in told


@pytest.mark.asyncio
async def test_more_questions_are_numbered_after_the_highest_slot_not_the_count(stack) -> None:
    """Ô hỏng để lại lỗ: dàn ý soạn thêm đánh số theo ô cao nhất, đúng chỗ `fire` sẽ đặt câu."""
    http, maker, monkeypatch = stack
    agent = ScriptedAgent(_outline_step(_outline_item(source_nodes=())), _open_and_draft(""))
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _drafting_stack(http, monkeypatch, rings_for=set(), ready_for=set())
    for said in ("soạn 2 câu", "oke"):
        await http.post("/api/teacher/chat/messages", json={"text": said}, headers=TEACHER)
    async with maker() as session:
        brief = await session.scalar(select(DraftBrief))
        # Câu 1 về đề, câu 2 hỏng hẳn.
        rows = list(await session.scalars(select(DraftItem).order_by(DraftItem.ordinal)))
        rows[1].status = "failed"
        await session.commit()
        thread = await _the_thread(maker)
        shape = await teacher_chat._outline_shape(
            session,
            thread,
            _outline_step(_outline_item(source_nodes=()), **{"for": "more"}),
        )

    assert shape[:2] == ("more", 3)
    assert shape[3] == brief.assessment_id


@pytest.mark.asyncio
async def test_replacing_a_question_goes_through_its_own_outline(stack) -> None:
    """ADR-29: *"thay câu 2"* -- dàn ý một mục cho đúng câu 2, đồng ý, rồi ô 2 soạn lại; câu cũ ở
    lại tới khi câu mới về."""
    http, maker, monkeypatch = stack
    replace_two = _outline_step(
        _outline_item(questions=1, source_nodes=()), **{"for": "replace", "question": "2"}
    )
    replace_plan = _plan(
        PlanStep(
            tool_name="replace_question",
            args={"assessment_id": "", "question_number": ""},
            title="Thay câu 2",
        )
    )
    agent = ScriptedAgent(
        _outline_step(_outline_item(source_nodes=())),
        _open_and_draft(""),
        replace_two,
        replace_plan,
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _drafting_stack(http, monkeypatch, rings_for=set(), ready_for={1, 2})
    for said in ("soạn 2 câu", "oke"):
        await http.post("/api/teacher/chat/messages", json={"text": said}, headers=TEACHER)

    async def ready(pool, settings, job_id):
        return "ready", DraftQuestionCompleted(
            request_id="r", question=_question(job_id)
        ).model_dump(mode="json")

    monkeypatch.setattr(drafting, "collect_result", ready)
    async with maker() as session:
        brief = await session.scalar(select(DraftBrief))
        await drafting.harvest(session, None, get_settings(), brief.assessment_id)

    shown = await http.post(
        "/api/teacher/chat/messages", json={"text": "thay câu 2 đi"}, headers=TEACHER
    )
    assert "Câu 2:" in shown.json()["text"]
    await http.post("/api/teacher/chat/messages", json={"text": "oke"}, headers=TEACHER)

    async with maker() as session:
        row = await session.scalar(select(DraftItem).where(DraftItem.ordinal == 2))
        kept = await session.scalar(
            select(Question).where(
                Question.assessment_id == brief.assessment_id, Question.order_index == 2
            )
        )
    assert (row.status, row.replacing) == ("pending", True)
    assert kept is not None


@pytest.mark.asyncio
async def test_a_plan_cannot_open_a_draft_and_replace_a_question_in_it(stack) -> None:
    http, maker, monkeypatch = stack
    open_and_replace = _plan(
        PlanStep(tool_name="create_draft", args=_BRIEF, title="Tạo đề"),
        PlanStep(
            tool_name="replace_question",
            args={"assessment_id": "{1.assessment_id}", "question_number": "1"},
            title="Thay câu 1",
        ),
    )
    agent = ScriptedAgent(open_and_replace)
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _outline_shown(monkeypatch, 1, purpose="replace")

    await http.post("/api/teacher/chat/messages", json={"text": "thay câu 1"}, headers=TEACHER)

    assert "không mở đề mới" in agent.asked[-1]["history"][-1]["tool_result"]["error"]
    async with maker() as session:
        assert await session.scalar(select(DraftBrief)) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("standing", "running", "said", "replaced"),
    [
        ("new", 0, "đã thay câu 2", True),
        ("old", 1, "câu 2 mới còn đang soạn", False),
        ("old", 0, "câu 2 giữ nguyên: câu mới soạn không đạt", False),
    ],
)
async def test_a_replacement_step_says_whether_the_question_changed(
    stack, standing: str, running: int, said: str, replaced: bool
) -> None:
    """Review đợt 5 (`draft-outline`): câu mới không đạt thì bước không được báo là đã thay."""
    _, maker, _ = stack
    async with maker() as session:
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        paper = Assessment(
            teacher_id=teacher.id,
            title="Đề",
            subject="Toán",
            grade="6",
            state=AssessmentState.HAS_QUESTIONS,
            created_at=datetime.now(UTC),
        )
        session.add(paper)
        await session.flush()
        question = Question(
            assessment_id=paper.id, order_index=2, stem="Câu hai", learning_objective="x"
        )
        session.add(question)
        await session.commit()
        before = {
            "started": True,
            "question_number": 2,
            "replaced_question_id": question.id if standing == "old" else "id-cũ",
            "still_drafting": running,
        }
        result, detail = await teacher_chat._replacement_outcome(session, paper.id, before, "")

    assert detail == said
    assert result["replaced"] is replaced
    assert (result["started"] is False) == (detail.endswith("không đạt"))


@pytest.mark.asyncio
async def test_replacing_in_a_bookless_draft_needs_no_lesson_even_with_a_chip(stack) -> None:
    """Thử tay 15/10/2026 (`draft-outline`): chip sách đính vào câu *"thay câu 2"* của một đề không
    sách -- dàn ý thay câu theo sách của **đề**, nên không bị đòi bài nguồn."""
    http, maker, monkeypatch = stack
    await _a_book(maker, "GV-001", "book")
    _bound_book()
    replace_two = _outline_step(
        _outline_item(questions=1, source_nodes=()), **{"for": "replace", "question": "2"}
    )
    agent = ScriptedAgent(
        _outline_step(_outline_item(source_nodes=())), _open_and_draft(""), replace_two
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)
    _drafting_stack(http, monkeypatch, rings_for=set(), ready_for={1, 2})
    for said in ("soạn 2 câu", "oke"):
        await http.post("/api/teacher/chat/messages", json={"text": said}, headers=TEACHER)

    async def ready(pool, settings, job_id):
        return "ready", DraftQuestionCompleted(
            request_id="r", question=_question(job_id)
        ).model_dump(mode="json")

    monkeypatch.setattr(drafting, "collect_result", ready)
    async with maker() as session:
        brief = await session.scalar(select(DraftBrief))
        await drafting.harvest(session, None, get_settings(), brief.assessment_id)

    shown = await http.post(
        "/api/teacher/chat/messages",
        json={"text": "thay câu 2", "document_id": "book"},
        headers=TEACHER,
    )

    assert "Câu 2:" in shown.json()["text"]
    bind_reader(None)


async def _guarded_more(maker, first: str, second: str):
    two = (
        PlanStep(
            tool_name="start_drafting",
            args={"assessment_id": first, "question_count": "1"},
            title="Soạn câu 6",
        ),
        PlanStep(
            tool_name="start_drafting",
            args={"assessment_id": second, "question_count": "1"},
            title="Soạn câu 7",
        ),
    )

    async def shown(*_args: object) -> dict:
        return {"version": 2, "for": "more", "total": 2, "assessment_id": "p1", "items": []}

    async with maker() as session:
        teacher_chat_shown = teacher_chat._shown_outline
        teacher_chat._shown_outline = shown
        try:
            return await teacher_chat.guard_drafting(session, "t", 5, two)
        finally:
            teacher_chat._shown_outline = teacher_chat_shown


@pytest.mark.asyncio
@pytest.mark.parametrize(("first", "second"), [("p1", "p1"), ("", "p1")])
async def test_more_questions_planned_one_step_each_become_one_step(
    stack, first: str, second: str
) -> None:
    """Thử tay 15/10/2026 (`draft-outline`): soạn thêm 2 câu ra hai bước `start_drafting` cho cùng
    một đề -- một lần soạn theo một dàn ý, nên gộp thành một bước. Đề để trống là đề BE điền, không
    phải một đề khác (review đợt 6)."""
    _, maker, _ = stack

    steps, _ = await _guarded_more(maker, first, second)

    assert [(one.tool_name, one.args["question_count"]) for one in steps] == [
        ("start_drafting", "2")
    ]
    assert steps[0].title == "Soạn câu hỏi theo dàn ý"


@pytest.mark.asyncio
async def test_drafting_steps_on_two_papers_are_not_merged(stack) -> None:
    _, maker, _ = stack

    refused = await _guarded_more(maker, "p1", "p2")

    assert isinstance(refused, str) and "một plan chỉ soạn một lần" in refused
