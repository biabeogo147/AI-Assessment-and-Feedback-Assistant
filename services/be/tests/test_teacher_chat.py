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
from be.models import Assessment, AssessmentState, SchoolClass, Student, Teacher
from be.seed import seed_if_empty
from be.teacher_chat import router as teacher_router
from be.teacher_tools import UnknownTool, execute
from contracts import NAME_CONVERSATION_TASK, ConversationNameCompleted, NextStepCompleted

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

    async def __call__(self, pool, settings, task_name, payload) -> dict:
        # Một cái cửa, nhiều loại việc. Từ khi BE nhờ AGENT đặt tên đoạn chat, bản giả
        # phải phân việc y như cái cửa thật — và việc đặt tên **không** vào `asked`, vì
        # `asked` nghĩa là "trợ lý đã được hỏi những gì", không phải "đã có bao nhiêu job".
        if task_name == NAME_CONVERSATION_TASK:
            return ConversationNameCompleted(
                request_id=payload["request_id"], title="tên do model đặt"
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
