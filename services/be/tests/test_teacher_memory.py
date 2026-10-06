"""Cuộc hội thoại sống sót qua request, và nó mua được những gì.

Trước khi có bảng này, endpoint nhận một câu rồi quên luôn. Cái giá dễ thấy là
reload một cái là mất lượt. Cái giá thật thì lớn hơn: một giáo viên trả lời đúng
câu hỏi làm rõ của trợ lý đã gửi câu trả lời đó đi mà không mang theo dấu vết nào
của điều vừa được hỏi, nên cổng đầu vào của ADR-05 tồn tại mà không có cách nào để
trả lời.

Vậy nên các test ở đây không thật sự nói về chuyện lưu trữ. Chúng nói về việc một
cuộc hội thoại là *một* thứ xuyên nhiều request, và về việc dòng dữ liệu sau đó đủ
đầy để trả lời "nó đã thật sự làm gì" — câu hỏi mà với một agent tự chọn bước đi
của mình thì không thể trả lời chỉ bằng mấy lời thoại.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import teacher_chat
from be.db import bind_sessions, prepare_schema
from be.identity import Asking
from be.models import SchoolClass, Student, Teacher, TeacherConversation, TeacherTurn
from be.seed import seed_if_empty
from be.teacher_chat import router as teacher_router
from contracts import (
    NAME_CONVERSATION_TASK,
    ConversationNameCompleted,
    NextStepCompleted,
    TurnRecord,
)

TEACHER = {"X-Actor": "teacher:GV-001"}


class ScriptedAgent:
    """Trả lời từng bước bằng một đề xuất xếp sẵn, và ghi lại những gì nó được hỏi.

    `takes` là khoảng thời gian mỗi câu trả lời giả vờ cần tới. Một bản `mock` trả
    lời tức thì làm `duration_ms` làm tròn về không, mà con số đó không phân biệt
    được với một khoảng thời gian không ai đo — nên một test nói về phép đo thì phải
    cho nó thứ gì đó để mà đo.
    """

    def __init__(self, *steps: NextStepCompleted, takes: float = 0.0) -> None:
        self.steps = list(steps)
        self.takes = takes
        self.asked: list[dict] = []

    async def __call__(self, pool, settings, task_name, payload) -> dict:
        # Một cái cửa, nhiều loại việc. Từ khi BE nhờ AGENT đặt tên đoạn chat, bản giả
        # phải phân việc y như cái cửa thật — và việc đặt tên **không** vào `asked`, vì
        # `asked` nghĩa là "trợ lý đã được hỏi những gì", không phải "đã có bao nhiêu job".
        if task_name == NAME_CONVERSATION_TASK:
            return ConversationNameCompleted(
                request_id=payload["request_id"], title="đề do model đặt tên"
            ).model_dump(mode="json")
        self.asked.append(payload)
        if self.takes:
            await asyncio.sleep(self.takes)
        step = (
            self.steps.pop(0)
            if self.steps
            else NextStepCompleted(request_id=payload["request_id"], kind="say", text="xong")
        )
        return step.model_copy(update={"request_id": payload["request_id"]}).model_dump(mode="json")


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """Một app trên database in-memory đã seed, kèm một lớp thứ hai để còn có chỗ nói mơ hồ."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        teacher = await session.scalar(select(SchoolClass))
        assert teacher is not None
        second = SchoolClass(teacher_id=teacher.teacher_id, name="12B")
        session.add(second)
        await session.flush()
        session.add(Student(class_id=second.id, full_name="Đỗ Văn Ba", student_code="HS2026-8001"))
        await session.commit()

    app = FastAPI()
    app.include_router(teacher_router)
    app.state.queue_pool = object()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker, monkeypatch

    await engine.dispose()
    db_module._SESSION_MAKER = None


@pytest.mark.asyncio
async def test_a_second_message_carries_the_first_one_with_it(stack) -> None:
    """Câu hỏi làm rõ trở thành thứ có thể trả lời được.

    Đây là toàn bộ lý do bảng này tồn tại. Trợ lý hỏi "lớp nào?", giáo viên đáp
    "12A", và model phải thấy được câu hỏi của chính nó mới hiểu nổi hai chữ đó.
    Trước khi cuộc hội thoại được lưu, request thứ hai tới nơi chỉ mang theo "12A".
    """
    client, _, monkeypatch = stack
    agent = ScriptedAgent(
        NextStepCompleted(request_id="x", kind="ask_clarify", text="Bạn muốn xem lớp nào?"),
        NextStepCompleted(request_id="x", kind="say", text="Lớp 12A nhé."),
    )
    monkeypatch.setattr(teacher_chat, "run_task", agent)

    await client.post("/api/teacher/chat/messages", json={"text": "xem điểm"}, headers=TEACHER)
    await client.post("/api/teacher/chat/messages", json={"text": "12A"}, headers=TEACHER)

    second = agent.asked[1]["history"]
    said = [turn["text"] for turn in second]
    assert "xem điểm" in said
    assert "Bạn muốn xem lớp nào?" in said
    assert "12A" in said


@pytest.mark.asyncio
async def test_the_conversation_reads_back_after_the_request_is_gone(stack) -> None:
    """Reload một cái vẫn thấy đúng cuộc hội thoại đó, đúng thứ tự đó."""
    client, _, monkeypatch = stack
    monkeypatch.setattr(
        teacher_chat,
        "run_task",
        ScriptedAgent(NextStepCompleted(request_id="x", kind="say", text="Chào bạn.")),
    )

    await client.post("/api/teacher/chat/messages", json={"text": "chào"}, headers=TEACHER)

    read = await client.get("/api/teacher/chat", headers=TEACHER)

    assert read.status_code == 200
    turns = read.json()["turns"]
    assert [turn["kind"] for turn in turns] == ["teacher", "assistant"]
    assert turns[0]["text"] == "chào"
    assert turns[1]["text"] == "Chào bạn."


@pytest.mark.asyncio
async def test_a_tool_step_stores_what_it_ran_and_what_came_back(stack) -> None:
    """Vết chạy chính là biên bản, nên một câu SELECT trả lời được "nó đã làm gì".

    Chỉ lưu lời thoại sẽ để phần giữa của mọi lượt thành vô hình: giáo viên báo "nó
    trả lời sai" mà lượt gọi tool sinh ra câu trả lời đó thì chẳng nằm ở đâu cả.
    """
    client, maker, monkeypatch = stack
    async with maker() as session:
        wanted = await session.scalar(select(SchoolClass).where(SchoolClass.name == "12B"))
        assert wanted is not None
        class_id = wanted.id

    monkeypatch.setattr(
        teacher_chat,
        "run_task",
        ScriptedAgent(
            NextStepCompleted(
                request_id="x",
                kind="call_tool",
                tool_name="get_class",
                tool_args={"class_id": class_id},
            ),
            NextStepCompleted(request_id="x", kind="say", text="Lớp 12B có 1 học sinh."),
        ),
    )

    await client.post("/api/teacher/chat/messages", json={"text": "lớp 12B"}, headers=TEACHER)

    async with maker() as session:
        stored = (await session.scalars(select(TeacherTurn).order_by(TeacherTurn.sequence))).all()

    assert [turn.kind for turn in stored] == ["teacher", "tool_call", "tool_result", "assistant"]

    ran = stored[1]
    assert ran.tool_name == "get_class"
    assert ran.tool_args == {"class_id": class_id}

    came_back = stored[2]
    assert came_back.tool_result["found"] is True
    assert came_back.tool_result["name"] == "12B"
    # Đối tượng của bước đó — thứ mà giao diện vẽ ra và thứ một câu hỏi sau này trỏ
    # tới — chứ không phải câu văn thông báo về nó.
    assert came_back.entity_kind == "class"
    assert came_back.entity_id == came_back.tool_result["class_id"]


@pytest.mark.asyncio
async def test_what_a_call_cost_travels_from_agent_into_the_row(stack) -> None:
    """Số `token` mà AGENT báo về đúng là số được lưu.

    Bản đầu tiên của test này khẳng định `model_tokens >= 0` trên một bản `mock`
    chẳng bao giờ gán giá trị đó — một cột mặc định 0 đem so với 0, và nó vẫn xanh
    ngay cả khi xoá sạch cả field. Nó bán cho ta cảm giác an toàn mà không trả lại
    gì. Bản này nêu đúng một con số và theo nó đi qua AGENT, qua contract, qua BE,
    tới cái bảng.
    """
    client, maker, monkeypatch = stack
    monkeypatch.setattr(
        teacher_chat,
        "run_task",
        ScriptedAgent(
            NextStepCompleted(request_id="x", kind="say", text="rồi", model_tokens=1234),
            takes=0.05,
        ),
    )

    await client.post("/api/teacher/chat/messages", json={"text": "chào"}, headers=TEACHER)

    async with maker() as session:
        spoken = await session.scalar(select(TeacherTurn).where(TeacherTurn.kind == "assistant"))

    assert spoken is not None
    assert spoken.model_tokens == 1234
    # Bản `mock` ngốn 50ms còn khẳng định chỉ đòi 30, vì `int()` trên số millisecond
    # đã trôi qua thì cắt phần thập phân, và một máy đang tải nặng còn làm tròn giấc
    # ngủ xuống. Điều được khẳng định là "cái này đã được đo", không phải "cái này
    # đúng 50" — một số 0 trơ ra mới là thứ một bước ghi ở ngoài vùng bấm giờ sẽ cho.
    # Khẳng định đúng y con số sleep chính là cách test này từng đỏ, trước khi được
    # nới ra.
    assert spoken.duration_ms >= 30


@pytest.mark.asyncio
async def test_two_steps_cannot_claim_the_same_position(stack) -> None:
    """Ràng buộc tính duy nhất đã chặn chuyện học sinh bị chào hai lần.

    Hai request có thể tới cùng một vị trí với cùng một con đếm trong tay, vì đọc con
    đếm và chèn dòng mới là hai câu lệnh, giữa chúng có một khoảng hở.
    """
    _, maker, _ = stack

    async with maker() as session:
        conversation = TeacherConversation(teacher_id="whoever", started_at=datetime.now(UTC))
        session.add(conversation)
        await session.flush()

        for _ in range(2):
            session.add(
                TeacherTurn(
                    conversation_id=conversation.id,
                    sequence=0,
                    kind="teacher",
                    text="cùng một chỗ",
                    created_at=datetime.now(UTC),
                )
            )

        with pytest.raises(IntegrityError):
            await session.flush()


@pytest.mark.asyncio
async def test_one_teacher_never_sees_another_conversation(stack) -> None:
    """Việc đọc lại cũng bị giới hạn theo chủ sở hữu như mọi thứ khác (ADR-22).

    Bản đầu tiên của test này hỏi dưới danh nghĩa `GV-404`, một mã không thuộc về ai,
    và khẳng định 401 — thứ mà `current_teacher` trả về trước khi endpoint này kịp
    chạy. Nó sẽ vẫn xanh dù có xoá bỏ bộ lọc theo chủ sở hữu. Nên giáo viên thứ hai ở
    đây là người có thật, và điều được khẳng định là một giáo viên thật thấy một cuộc
    hội thoại rỗng chứ không thấy hội thoại của người khác.
    """
    client, maker, monkeypatch = stack
    async with maker() as session:
        session.add(Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002"))
        await session.commit()

    monkeypatch.setattr(
        teacher_chat,
        "run_task",
        ScriptedAgent(NextStepCompleted(request_id="x", kind="say", text="của GV-001")),
    )
    await client.post("/api/teacher/chat/messages", json={"text": "riêng tôi"}, headers=TEACHER)

    mine = await client.get("/api/teacher/chat", headers=TEACHER)
    theirs = await client.get("/api/teacher/chat", headers={"X-Actor": "teacher:GV-002"})

    assert [turn["text"] for turn in mine.json()["turns"]] == ["riêng tôi", "của GV-001"]
    assert theirs.json()["turns"] == []


@pytest.mark.asyncio
async def test_a_step_aimed_at_a_taken_position_moves_to_the_next_free_one(stack) -> None:
    """Nửa còn lại — phần hồi phục — của bài học mà `chat_messages` đã dạy.

    Đọc vị trí và chèn vào vị trí đó là hai câu lệnh có khoảng hở ở giữa, nên hai
    request của một giáo viên có thể cùng nhắm vào một vị trí — StrictMode của React
    bắn hai lần theo đúng thiết kế, và một giáo viên mất kiên nhẫn cũng vậy. Unique
    index là thứ phân định; bên thua nhận vị trí trống tiếp theo thay vì hỏng.

    Được test bằng cách cố ý nhắm hai lần, không phải bằng cách cho đua. Ở đây một
    cuộc đua là thứ không quan sát được: SQLite in-memory chạy trên `StaticPool`, một
    connection dùng chung cho mọi session, nên hai request song song không có isolation
    nào giữa chúng và kết quả nói về cái pool nhiều hơn là về đoạn code này. Nhắm hai
    lần chạy đúng nhánh đó và nói ra một điều đúng.
    """
    _, maker, _ = stack

    async with maker() as session:
        teacher = await session.scalar(select(Teacher))
        assert teacher is not None
        asking = Asking.of(teacher)

        thread = await teacher_chat._conversation(session, asking)

        first = await teacher_chat._record(
            session, thread, 0, TurnRecord(kind="teacher", text="một")
        )
        # Lại đúng vị trí đó, như một request thứ hai đang nắm một con đếm đã cũ.
        second = await teacher_chat._record(
            session, thread, 0, TurnRecord(kind="teacher", text="hai")
        )

        stored = (await session.scalars(select(TeacherTurn).order_by(TeacherTurn.sequence))).all()

    assert first == 1
    assert second == 2
    assert [turn.sequence for turn in stored] == [0, 1]
    assert [turn.text for turn in stored] == ["một", "hai"]


@pytest.mark.asyncio
async def test_a_teacher_keeps_one_conversation_across_messages(stack) -> None:
    """Hỏi lần nữa thì nhận lại đúng luồng đang chạy, không phải một luồng mới.

    Luật này từng do **schema** cưỡng chế: `teacher_conversations` có một
    `UniqueConstraint("teacher_id")`, nên một lần chèn thứ hai bị database từ chối.
    Constraint ấy đã đi, vì giáo viên nay mở được luồng thứ hai. Luật thì ở lại, và
    nay nó nằm trong `_conversation`: **nói tiếp** không bao giờ được âm thầm mở một
    luồng mới, vì một luồng mới nghĩa là trợ lý quên sạch những gì vừa nói.

    Nên test này không đổi phần kiểm, chỉ đổi thứ nó đang canh: từ một constraint
    sang một hàm. Và nó là nửa còn lại của
    `test_a_new_conversation_starts_a_second_thread` ngay dưới — một hàm mở luồng
    mới **khi được xin**, và chỉ khi được xin.
    """
    _, maker, _ = stack

    async with maker() as session:
        teacher = await session.scalar(select(Teacher))
        assert teacher is not None
        asking = Asking.of(teacher)

        first = await teacher_chat._conversation(session, asking)
        again = await teacher_chat._conversation(session, asking)

        started = (await session.scalars(select(TeacherConversation))).all()

    assert first == again
    assert len(started) == 1


@pytest.mark.asyncio
async def test_a_new_conversation_starts_a_second_thread(stack) -> None:
    """Xin một luồng mới thì được một luồng mới, và luồng cũ ở nguyên đó.

    Nửa còn lại của test trên. `schema` từng cấm chuyện này ở tầng database; nay hai
    hàng cùng `teacher_id` là hợp lệ, và `_latest_conversation` phải trỏ sang cái vừa
    mở — nếu không thì nút *Đoạn chat mới* mở một luồng mà không ai nói vào được.

    Luồng cũ mang một bước của **hôm qua**, đúng hình dạng một luồng thật: `start_new`
    chỉ xảy ra khi giáo viên đã nói ở đâu đó rồi. Và đó cũng là thứ làm phép kiểm cuối
    có nghĩa — một luồng vừa mở phải thắng một luồng nói lần cuối hôm qua.
    """
    _, maker, _ = stack

    async with maker() as session:
        teacher = await session.scalar(select(Teacher))
        assert teacher is not None
        asking = Asking.of(teacher)

        first = await teacher_chat._conversation(session, asking)
        session.add(
            TeacherTurn(
                conversation_id=first,
                sequence=0,
                kind="teacher",
                text="hôm qua tôi nói ở đây",
                created_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        await session.commit()

        second = await teacher_chat._conversation(session, asking, start_new=True)
        latest = await teacher_chat._latest_conversation(session, asking)

        started = (await session.scalars(select(TeacherConversation))).all()

    assert first != second
    assert len(started) == 2
    # Luồng đang chạy là luồng vừa mở, không phải luồng có UUID lớn hơn. Khoá sắp xếp là
    # lần nói cuối, và một luồng chưa nói câu nào thì lấy chính giờ mở của nó.
    assert latest == second


@pytest.mark.asyncio
async def test_a_teacher_who_only_reads_starts_no_conversation(stack) -> None:
    """Một lượt GET thì không ghi.

    `_conversation` tạo một luồng khi chưa có luồng nào, điều đó đúng với một tin nhắn
    và sai với một lượt đọc: một lượt prefetch của trình duyệt, một cú HEAD dò đường
    hay một lần `retry` đều để lại một dòng, và hai trong số đó đua với một POST là
    cách dễ nhất để một giáo viên có hai luồng.
    """
    client, maker, _ = stack

    read = await client.get("/api/teacher/chat", headers=TEACHER)

    assert read.status_code == 200
    assert read.json()["turns"] == []

    async with maker() as session:
        started = (await session.scalars(select(TeacherConversation))).all()

    assert started == []


@pytest.mark.asyncio
async def test_the_rail_lists_conversations_newest_spoken_first(stack) -> None:
    """Danh sách sắp theo **lần nói cuối**, không theo giờ mở.

    Một đoạn chat mở từ tuần trước mà hôm nay vừa nói tiếp thì đứng đầu, vì đó là chỗ
    người ta đi tìm nó. Sắp theo giờ mở thì đoạn đang dùng nhiều nhất lại trôi xuống dưới
    cùng — và trên một rail chỉ hiện vài dòng, trôi xuống dưới nghĩa là biến mất.
    """
    client, maker, _ = stack

    async with maker() as session:
        teacher = await session.scalar(select(Teacher))
        assert teacher is not None
        for name, opened, spoke in (
            (
                "cũ nhưng vừa nói",
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 9, 30, tzinfo=UTC),
            ),
            (
                "mới mở, nói lâu rồi",
                datetime(2026, 9, 1, tzinfo=UTC),
                datetime(2026, 9, 2, tzinfo=UTC),
            ),
        ):
            thread = TeacherConversation(teacher_id=teacher.id, started_at=opened, title=name)
            session.add(thread)
            await session.flush()
            session.add(
                TeacherTurn(
                    conversation_id=thread.id,
                    sequence=0,
                    kind="teacher",
                    text=name,
                    created_at=spoke,
                )
            )
        await session.commit()

    listed = await client.get("/api/teacher/conversations", headers=TEACHER)

    assert listed.status_code == 200
    assert [one["title"] for one in listed.json()] == ["cũ nhưng vừa nói", "mới mở, nói lâu rồi"]


@pytest.mark.asyncio
async def test_an_empty_conversation_never_reaches_the_rail(stack) -> None:
    """Một hàng chưa có bước nào không lên danh sách.

    Nó không có gì để vẽ và không có đường nào xoá, nên nó chỉ có thể là rác: `start_new`
    ghi bước đầu tiên trong cùng request, nên một hàng rỗng nghĩa là một request đã chết
    giữa chừng. Người dùng đã chốt *"danh sách không bao giờ có đoạn chat rỗng"*.
    """
    client, maker, _ = stack

    async with maker() as session:
        teacher = await session.scalar(select(Teacher))
        assert teacher is not None
        session.add(TeacherConversation(teacher_id=teacher.id, started_at=datetime.now(UTC)))
        await session.commit()

    listed = await client.get("/api/teacher/conversations", headers=TEACHER)

    assert listed.status_code == 200
    assert listed.json() == []


@pytest.mark.asyncio
async def test_one_teacher_never_lists_another_teachers_conversations(stack) -> None:
    """ADR-22, và ở đây luật ấy là **cấu trúc**: endpoint không nhận id nào cả.

    Không có tham số nào để truyền một id của người khác vào, nên không có đường nào để
    bịt — đó là hình dạng rẻ nhất của luật này.
    """
    client, maker, _ = stack

    async with maker() as session:
        mine = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        stranger = Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002")
        session.add(stranger)
        await session.flush()
        for who, name in ((mine, "của tôi"), (stranger, "của người khác")):
            thread = TeacherConversation(
                teacher_id=who.id, started_at=datetime.now(UTC), title=name
            )
            session.add(thread)
            await session.flush()
            session.add(
                TeacherTurn(
                    conversation_id=thread.id,
                    sequence=0,
                    kind="teacher",
                    text=name,
                    created_at=datetime.now(UTC),
                )
            )
        await session.commit()

    listed = await client.get("/api/teacher/conversations", headers=TEACHER)

    assert [one["title"] for one in listed.json()] == ["của tôi"]


@pytest.mark.asyncio
async def test_two_conversations_keep_two_histories(stack) -> None:
    """Hai đoạn chat song song không lẫn vào nhau.

    Đây là lý do cả đợt này tồn tại. Nếu lịch sử lẫn nhau thì nhiều đoạn chat còn tệ hơn
    một đoạn: trợ lý đọc một hội thoại chắp vá của hai việc không liên quan, và giáo viên
    không có cách nào biết điều đó đang xảy ra.
    """
    client, _, monkeypatch = stack
    monkeypatch.setattr(teacher_chat, "run_task", ScriptedAgent())

    first = await client.post(
        "/api/teacher/chat/messages", json={"text": "việc thứ nhất"}, headers=TEACHER
    )
    second = await client.post(
        "/api/teacher/chat/messages",
        json={"text": "việc thứ hai", "start_new": True},
        headers=TEACHER,
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["conversation_id"] != second.json()["conversation_id"]

    older = await client.get(
        "/api/teacher/chat",
        params={"conversation_id": first.json()["conversation_id"]},
        headers=TEACHER,
    )
    newer = await client.get(
        "/api/teacher/chat",
        params={"conversation_id": second.json()["conversation_id"]},
        headers=TEACHER,
    )

    assert [turn["text"] for turn in older.json()["turns"] if turn["kind"] == "teacher"] == [
        "việc thứ nhất"
    ]
    assert [turn["text"] for turn in newer.json()["turns"] if turn["kind"] == "teacher"] == [
        "việc thứ hai"
    ]


@pytest.mark.asyncio
async def test_another_teachers_conversation_reads_as_absent(stack) -> None:
    """ADR-22 trên một id **do client gửi**.

    Mọi id trước đây trong file này đều do BE tự tìm ra từ `teacher_id`, nên luật sở hữu
    là cấu trúc. `conversation_id` là id đầu tiên đi ngược chiều, và nó phải được kiểm —
    một id của người khác đọc ra y hệt một id không tồn tại, vì phân biệt được hai ca ấy
    là cho bất kỳ ai dò xem giáo viên khác đang có những gì.
    """
    client, maker, monkeypatch = stack
    monkeypatch.setattr(teacher_chat, "run_task", ScriptedAgent())

    async with maker() as session:
        stranger = Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002")
        session.add(stranger)
        await session.flush()
        thread = TeacherConversation(
            teacher_id=stranger.id, started_at=datetime.now(UTC), title="của người khác"
        )
        session.add(thread)
        await session.flush()
        session.add(
            TeacherTurn(
                conversation_id=thread.id,
                sequence=0,
                kind="teacher",
                text="bí mật",
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
        theirs = thread.id

    read = await client.get(
        "/api/teacher/chat", params={"conversation_id": theirs}, headers=TEACHER
    )
    made_up = await client.get(
        "/api/teacher/chat", params={"conversation_id": "khong-ton-tai"}, headers=TEACHER
    )
    said = await client.post(
        "/api/teacher/chat/messages",
        json={"text": "chen vao", "conversation_id": theirs},
        headers=TEACHER,
    )

    assert read.status_code == 404
    assert read.json() == made_up.json()
    assert said.status_code == 404


@pytest.mark.asyncio
async def test_asking_for_both_a_thread_and_a_new_one_is_refused(stack) -> None:
    """Gửi cả `conversation_id` lẫn `start_new` là một request tự mâu thuẫn.

    Chọn hộ một trong hai là chọn hộ sai một nửa số lần, và cái sai ấy im lặng: câu vừa gõ
    rơi vào một đoạn chat khác chỗ người ta tưởng. `422` ở biên rẻ hơn hẳn.
    """
    client, _, monkeypatch = stack
    monkeypatch.setattr(teacher_chat, "run_task", ScriptedAgent())

    opened = await client.post(
        "/api/teacher/chat/messages", json={"text": "mở một đoạn"}, headers=TEACHER
    )
    both = await client.post(
        "/api/teacher/chat/messages",
        json={
            "text": "vừa cái này vừa cái kia",
            "conversation_id": opened.json()["conversation_id"],
            "start_new": True,
        },
        headers=TEACHER,
    )

    assert both.status_code == 422


@pytest.mark.asyncio
async def test_the_first_message_names_the_thread(stack) -> None:
    """Lượt đầu tiên đặt tên cho đoạn chat; lượt thứ hai không đổi tên nữa.

    Đổi tên theo câu mới nhất sẽ làm rail nhảy chữ sau mỗi tin nhắn, và một hàng vừa đọc
    xong đã mang tên khác là một hàng không ai tìm lại được.
    """
    client, maker, monkeypatch = stack
    monkeypatch.setattr(teacher_chat, "run_task", ScriptedAgent())

    opened = await client.post(
        "/api/teacher/chat/messages", json={"text": "soạn đề đạo hàm"}, headers=TEACHER
    )
    await client.post("/api/teacher/chat/messages", json={"text": "thêm hai câu"}, headers=TEACHER)

    async with maker() as session:
        row = await session.get(TeacherConversation, opened.json()["conversation_id"])
    assert row is not None
    assert row.title == "đề do model đặt tên"


@pytest.mark.asyncio
async def test_a_thread_still_gets_a_name_when_the_model_cannot(stack) -> None:
    """Model hỏng thì tên là câu đầu cắt ngắn, và lượt nói **vẫn thành công**.

    Đây là ca đáng giá nhất của phần đặt tên. Nó chạy ở cuối một lượt đã xong và đã commit
    từng bước; một lỗi thoát ra từ đây sẽ biến lượt ấy thành 500 và giáo viên mất cả việc
    vừa nhờ, vì một dòng chữ trên rail.
    """
    client, maker, monkeypatch = stack

    class Grumpy(ScriptedAgent):
        async def __call__(self, pool, settings, task_name, payload) -> dict:
            if task_name == NAME_CONVERSATION_TASK:
                raise RuntimeError("AGENT đi vắng")
            return await super().__call__(pool, settings, task_name, payload)

    monkeypatch.setattr(teacher_chat, "run_task", Grumpy())

    said = "soạn cho tôi một đề về đạo hàm của đa thức dành cho lớp 12 ban cơ bản nhé"
    opened = await client.post("/api/teacher/chat/messages", json={"text": said}, headers=TEACHER)

    assert opened.status_code == 200, opened.text
    async with maker() as session:
        row = await session.get(TeacherConversation, opened.json()["conversation_id"])
    assert row is not None
    assert row.title == said[:60]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("wrote", "kept"),
    [
        ('"Đề đạo hàm"', "Đề đạo hàm"),
        ("Đề đạo hàm.", "Đề đạo hàm"),
        ("  Đề   đạo\n hàm  ", "Đề đạo hàm"),
        ("đạo " + "x" * 300, "đạo " + "x" * 56),
        ("   ", "soạn đề đạo hàm"),
    ],
)
async def test_a_model_written_title_is_tidied_before_it_is_stored(stack, wrote, kept) -> None:
    """Prompt là một lời nhờ, không phải một ràng buộc.

    Model được bảo đừng dùng dấu ngoặc kép và đừng chấm câu, và model vẫn làm cả hai. Chỗ
    ràng buộc là BE, vì BE biết chuỗi này sẽ nằm ở đâu: một hàng rộng 228px. Rỗng thì lùi
    về câu đầu — một hàng không tên là một hàng không bấm vào được.
    """
    client, maker, monkeypatch = stack

    class Sloppy(ScriptedAgent):
        async def __call__(self, pool, settings, task_name, payload) -> dict:
            if task_name == NAME_CONVERSATION_TASK:
                return ConversationNameCompleted(
                    request_id=payload["request_id"], title=wrote
                ).model_dump(mode="json")
            return await super().__call__(pool, settings, task_name, payload)

    monkeypatch.setattr(teacher_chat, "run_task", Sloppy())

    opened = await client.post(
        "/api/teacher/chat/messages", json={"text": "soạn đề đạo hàm"}, headers=TEACHER
    )

    async with maker() as session:
        row = await session.get(TeacherConversation, opened.json()["conversation_id"])
    assert row is not None
    assert row.title == kept


@pytest.mark.asyncio
async def test_a_greeting_is_not_named_after_a_job_nobody_asked_for(stack) -> None:
    """Một lời chào không biến thành một việc model tự nghĩ ra.

    Đo được trên trình duyệt thật: giáo viên gõ *"Chào bạn"* và rail hiện *"Tạo đề kiểm tra
    15 phút"*. Prompt cũ nói *"gọi tên VIỆC, không chào hỏi"* mà không cho đường ra nào cho
    một câu không chứa việc nào, nên model buộc phải bịa — và nguồn chữ duy nhất trong tầm
    với là chính hai ví dụ của prompt.

    Cái tên sai ấy **tuân thủ** mọi luật còn lại: sáu từ, viết thường, không ngoặc kép,
    không chấm câu. Nên `_tidy` không bắt được, và không phép kiểm hình thức nào bắt được.
    Phép kiểm phải hỏi một câu khác: *cái tên có chung chữ nào với câu đã gõ không*.
    """
    client, maker, monkeypatch = stack

    class Inventive(ScriptedAgent):
        async def __call__(self, pool, settings, task_name, payload) -> dict:
            if task_name == NAME_CONVERSATION_TASK:
                return ConversationNameCompleted(
                    request_id=payload["request_id"], title="Tạo đề kiểm tra 15 phút"
                ).model_dump(mode="json")
            return await super().__call__(pool, settings, task_name, payload)

    monkeypatch.setattr(teacher_chat, "run_task", Inventive())

    opened = await client.post(
        "/api/teacher/chat/messages", json={"text": "Chào bạn"}, headers=TEACHER
    )

    assert opened.status_code == 200, opened.text
    async with maker() as session:
        row = await session.get(TeacherConversation, opened.json()["conversation_id"])
    assert row is not None
    assert row.title == "Chào bạn"


@pytest.mark.asyncio
async def test_a_naming_answer_from_another_job_is_ignored(stack) -> None:
    """Tên của một job khác không được đeo vào đoạn chat này.

    Chưa đo được lần nào, và đó chính là lý do nó đáng một test: nếu xảy ra, nó là một cái
    tên sai **không để lại dấu vết nào** — hai đoạn chat mở gần nhau, một trong hai mang tên
    của đoạn kia, và không có gì trên màn hình nói rằng đã có chuyện gì.
    """
    client, maker, monkeypatch = stack

    class Mixed(ScriptedAgent):
        async def __call__(self, pool, settings, task_name, payload) -> dict:
            if task_name == NAME_CONVERSATION_TASK:
                # Tên này **có** chung chữ với câu đã gõ, nên nó đi lọt `_echoes`. Thứ duy
                # nhất sai là nó trả lời một câu hỏi khác.
                return ConversationNameCompleted(
                    request_id="một-job-nào-đó", title="soạn đề đạo hàm lớp khác"
                ).model_dump(mode="json")
            return await super().__call__(pool, settings, task_name, payload)

    monkeypatch.setattr(teacher_chat, "run_task", Mixed())

    opened = await client.post(
        "/api/teacher/chat/messages", json={"text": "soạn đề đạo hàm"}, headers=TEACHER
    )

    async with maker() as session:
        row = await session.get(TeacherConversation, opened.json()["conversation_id"])
    assert row is not None
    assert row.title == "soạn đề đạo hàm"


@pytest.mark.parametrize(
    ("said", "title", "echoes"),
    [
        # Ca đã đo hỏng trên trình duyệt.
        ("Chào bạn", "Tạo đề kiểm tra 15 phút", False),
        # Một lời chào dài hơn hai từ. Lời chào tiếng Việt gần như luôn có một hư từ, và
        # một cái tên bịa kiểu "Đề kiểm tra lớp 12 có 10 câu" rất dễ chứa đúng hư từ ấy —
        # nhưng nó **không** được đi lọt chỉ nhờ chữ "có".
        ("Chào bạn, bạn có khỏe không", "Đề kiểm tra lớp 12 có 10 câu", True),
        # Chữ số không chứng minh gì: một bên là số câu, một bên là số lớp.
        ("Soạn giúp mình 10 câu đạo hàm", "Đề 15 phút lớp 10", False),
        # Tên tốt thì luôn chung chữ.
        ("Soạn giúp mình 10 câu về đạo hàm cho 12A1", "Soạn đề đạo hàm 12A1", True),
        ("Lớp 11B làm bài vừa rồi thế nào", "Kết quả lớp 11B", True),
        ("Chào buổi sáng nhé", "Chào buổi sáng", True),
    ],
)
def test_echoes_catches_a_title_made_up_whole(said, title, echoes) -> None:
    """Chốt kiểm bắt **bịa trọn gói**, không chấm điểm cái tên.

    Hai ca ở giữa là hai lỗ review đo được. Lỗ thứ hai đã bịt bằng cách thôi tính chữ số
    là một từ chung. Lỗ thứ nhất thì **vẫn mở** và nằm đây có chủ ý: bịt nó cần một danh
    sách hư từ, mà một danh sách hư từ là một thứ phải nuôi, và nó đổi phép kiểm từ *"có
    bịa không"* thành *"tên này hay không"* — một câu hỏi khác hẳn, và không phải câu hỏi
    chốt kiểm này sinh ra để trả lời. Ghi lại thành test để lần sau ai siết thì biết mình
    đang siết cái gì.
    """
    assert teacher_chat._echoes(said, title) is echoes


def test_echoes_survives_a_keyboard_that_types_nfd() -> None:
    """Bàn phím tiếng Việt trên iOS và macOS sinh **NFD**, AGENT trả **NFC**.

    Dấu trong NFD là một ký tự tổ hợp riêng và nó không phải "ký tự chữ", nên regex băm
    "Soạn" thành "Soa" + "n". Không chuẩn hoá thì một bên NFD gặp một bên NFC là **không
    từ nào khớp từ nào**: việc đặt tên tắt hoàn toàn, mọi đoạn chat mang câu đầu cắt 60 ký
    tự, và dấu vết duy nhất là một dòng log.
    """
    import unicodedata

    said = unicodedata.normalize("NFD", "Soạn đề đạo hàm")
    assert said != "Soạn đề đạo hàm"
    assert teacher_chat._echoes(said, "đề đạo hàm 12A1") is True


async def _a_thread(maker, *, title: str = "Đoạn cũ", code: str = "GV-001") -> str:
    """Một đoạn chat đã có một bước, tức một đoạn đã lên rail.

    Args:
        maker: Session maker của test.
        title: Tên đặt sẵn.
        code: Mã giáo viên sở hữu.

    Returns:
        Id của đoạn.
    """
    async with maker() as session:
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == code))
        assert teacher is not None
        thread = TeacherConversation(
            teacher_id=teacher.id, started_at=datetime(2026, 9, 1, tzinfo=UTC), title=title
        )
        session.add(thread)
        await session.flush()
        session.add(
            TeacherTurn(
                conversation_id=thread.id,
                sequence=0,
                kind="teacher",
                text="một câu đã nói",
                created_at=datetime(2026, 9, 2, tzinfo=UTC),
            )
        )
        await session.commit()
        return thread.id


@pytest.mark.asyncio
async def test_a_renamed_conversation_keeps_the_name_the_teacher_typed(stack) -> None:
    """Tên giáo viên gõ thắng tên model đã đặt, và nó sống qua một lần đọc lại.

    Tên vốn do model đặt **một lần** sau lượt đầu và không ai sửa được. Rail là chỗ giáo viên
    đi tìm lại việc cũ, nên một cái tên model đặt sai là một đoạn chat mất tích.
    """
    client, maker, _ = stack
    thread = await _a_thread(maker, title="Tên model đặt sai")

    renamed = await client.patch(
        f"/api/teacher/conversations/{thread}",
        json={"title": '  "Đề giữa kỳ 12A."  '},
        headers=TEACHER,
    )

    assert renamed.status_code == 200
    # Dọn bằng chính `_tidy` của đường đặt tên tự động: cùng một cột, cùng một giới hạn, nên
    # cùng một hàm dọn — chứ không phải một luật thứ hai chờ lệch đi.
    assert renamed.json()["title"] == "Đề giữa kỳ 12A"

    listed = await client.get("/api/teacher/conversations", headers=TEACHER)
    assert [one["title"] for one in listed.json()] == ["Đề giữa kỳ 12A"]


@pytest.mark.asyncio
async def test_a_title_that_is_only_spaces_is_refused(stack) -> None:
    """Gõ về rỗng bị từ chối, vì cột rỗng đã có nghĩa riêng.

    Rỗng nghĩa là *chưa đặt tên* — một đoạn vừa mở chưa có gì để đặt tên theo. Cho phép gõ
    về rỗng là trộn chuyện ấy với *"tôi đặt tên là không gì cả"*, và rail sẽ vẽ ra nhãn dự
    phòng `Đoạn chat` như thể model chưa kịp chạy.
    """
    client, maker, _ = stack
    thread = await _a_thread(maker, title="Tên cũ")

    refused = await client.patch(
        f"/api/teacher/conversations/{thread}", json={"title": "   "}, headers=TEACHER
    )

    assert refused.status_code == 400
    listed = await client.get("/api/teacher/conversations", headers=TEACHER)
    assert [one["title"] for one in listed.json()] == ["Tên cũ"]


@pytest.mark.asyncio
async def test_a_deleted_conversation_leaves_the_rail(stack) -> None:
    """Xoá rồi thì đoạn rời rail, và đọc lại ra **y như một đoạn không tồn tại**."""
    client, maker, _ = stack
    gone = await _a_thread(maker, title="Gõ nhầm")
    kept = await _a_thread(maker, title="Đoạn thật")

    erased = await client.delete(f"/api/teacher/conversations/{gone}", headers=TEACHER)

    assert erased.status_code == 204
    listed = await client.get("/api/teacher/conversations", headers=TEACHER)
    assert [one["title"] for one in listed.json()] == ["Đoạn thật"]
    assert (
        await client.get(f"/api/teacher/chat?conversation_id={gone}", headers=TEACHER)
    ).status_code == 404
    # Xoá hai lần ra 404: lần thứ hai thật sự không tìm thấy gì.
    assert (
        await client.delete(f"/api/teacher/conversations/{gone}", headers=TEACHER)
    ).status_code == 404
    assert (
        await client.get(f"/api/teacher/chat?conversation_id={kept}", headers=TEACHER)
    ).status_code == 200


@pytest.mark.asyncio
async def test_a_deleted_conversation_keeps_its_turns(stack) -> None:
    """Xoá là **xoá mềm**, và lý do là ADR-24.

    Biên bản duyệt đề là một row `teacher_turns` của chính đoạn đã sinh ra đề. Xoá thật thì
    một cú dọn nhà phá mất bằng chứng cho một cuộc đi tìm của tháng sau — mà người đang bấm
    nút chỉ muốn một đoạn gõ nhầm biến khỏi mắt mình. Hai đòi hỏi ấy cùng được, miễn là
    "biến đi" không có nghĩa là "mất hẳn".
    """
    client, maker, _ = stack
    thread = await _a_thread(maker, title="Có biên bản trong này")

    assert (
        await client.delete(f"/api/teacher/conversations/{thread}", headers=TEACHER)
    ).status_code == 204

    async with maker() as session:
        kept = list(
            await session.scalars(select(TeacherTurn).where(TeacherTurn.conversation_id == thread))
        )
    assert len(kept) == 1


@pytest.mark.asyncio
async def test_a_new_turn_never_lands_in_a_deleted_conversation(stack) -> None:
    """Một câu mới không rơi vào một đoạn đã xoá.

    `_owned_conversation` canh cả hai cửa bằng một mệnh đề, nên luật này không phải một bản
    sao đặt cạnh luật kia. Không có nó thì một tab còn mở từ trước lúc xoá vẫn gửi được câu
    vào đó, và câu ấy đi vào một nơi không còn đường nào mở ra.
    """
    client, maker, monkeypatch = stack
    thread = await _a_thread(maker, title="Đã xoá")
    monkeypatch.setattr(
        teacher_chat,
        "run_task",
        ScriptedAgent(NextStepCompleted(request_id="x", kind="say", text="Chào bạn.")),
    )

    assert (
        await client.delete(f"/api/teacher/conversations/{thread}", headers=TEACHER)
    ).status_code == 204

    refused = await client.post(
        "/api/teacher/chat/messages",
        json={"text": "còn đó không", "conversation_id": thread},
        headers=TEACHER,
    )

    assert refused.status_code == 404


@pytest.mark.asyncio
async def test_one_teacher_cannot_delete_or_rename_anothers_conversation(stack) -> None:
    """Đoạn của người khác và đoạn không tồn tại đọc ra y hệt nhau (ADR-22).

    Phân biệt được chúng là cho bất kỳ ai dò xem giáo viên khác đang có những gì, chỉ bằng
    cách thử id — và ở đây cái giá còn cao hơn một lần đọc: hai endpoint này **ghi**.
    """
    client, maker, _ = stack
    async with maker() as session:
        stranger = Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002")
        session.add(stranger)
        await session.commit()
    theirs = await _a_thread(maker, title="Của người khác", code="GV-002")

    assert (
        await client.delete(f"/api/teacher/conversations/{theirs}", headers=TEACHER)
    ).status_code == 404
    assert (
        await client.patch(
            f"/api/teacher/conversations/{theirs}", json={"title": "của tôi"}, headers=TEACHER
        )
    ).status_code == 404

    async with maker() as session:
        row = await session.get(TeacherConversation, theirs)
        assert row is not None
        assert row.title == "Của người khác"
        assert row.deleted_at is None


@pytest.mark.asyncio
async def test_a_deleted_conversation_is_not_the_running_one(stack) -> None:
    """Xoá đoạn **duy nhất** rồi nói tiếp thì câu mới mở một đoạn khác.

    Đây là cửa không mang id: `POST /teacher/chat/messages` thiếu `conversation_id` đi qua
    `_latest_conversation`, không qua `_owned_conversation`. Thiếu mệnh đề lọc ở đó thì câu
    vừa gõ rơi vào chính đoạn vừa xoá — một nơi không còn trên rail và không mở lại được, và
    giáo viên không được báo gì cả.
    """
    client, maker, monkeypatch = stack
    thread = await _a_thread(maker, title="Đã xoá")
    monkeypatch.setattr(
        teacher_chat,
        "run_task",
        ScriptedAgent(NextStepCompleted(request_id="x", kind="say", text="Chào bạn.")),
    )

    assert (
        await client.delete(f"/api/teacher/conversations/{thread}", headers=TEACHER)
    ).status_code == 204

    # Đọc mà không có id: không thấy gì, chứ không thấy đoạn đã xoá.
    empty = await client.get("/api/teacher/chat", headers=TEACHER)
    assert empty.status_code == 200
    assert empty.json()["turns"] == []

    spoken = await client.post(
        "/api/teacher/chat/messages", json={"text": "chào bạn"}, headers=TEACHER
    )

    assert spoken.status_code == 200
    assert spoken.json()["conversation_id"] != thread


@pytest.mark.asyncio
async def test_a_record_never_lands_in_a_deleted_conversation(stack) -> None:
    """Biên bản của một đề rơi vào một đoạn giáo viên **mở ra được**.

    Duyệt và phát hành xảy ra ngoài khung chat, nên `note_action` phải tự tìm đoạn. Nó hỏi
    `conversation_of`, và nếu hàm ấy trả về một đoạn đã xoá thì ADR-24 đạt về chữ — row vẫn
    tồn tại — mà hỏng về việc: không ai mở được nó ra đọc, và `AssessmentDetail` sẽ chỉ tới
    một id mà `GET /teacher/chat?conversation_id=` ấy trả 404.
    """
    client, maker, _ = stack
    gone = await _a_thread(maker, title="Đoạn đã xoá")
    async with maker() as session:
        teacher = await session.scalar(select(Teacher))
        assert teacher is not None
        session.add(
            TeacherTurn(
                conversation_id=gone,
                sequence=1,
                kind="tool_result",
                tool_name="create_draft",
                tool_result={"created": True, "assessment_id": "p1"},
                entity_kind="assessment",
                entity_id="p1",
                created_at=datetime(2026, 9, 2, tzinfo=UTC),
            )
        )
        await session.commit()
        asking = Asking.of(teacher)

    assert (
        await client.delete(f"/api/teacher/conversations/{gone}", headers=TEACHER)
    ).status_code == 204

    async with maker() as session:
        assert await teacher_chat.conversation_of(session, asking, "p1") is None
        await teacher_chat.note_action(
            session,
            asking,
            TurnRecord(
                kind="tool_result",
                tool_name="teacher.approve",
                tool_result={"approved": True, "assessment_id": "p1"},
            ),
        )

    listed = await client.get("/api/teacher/conversations", headers=TEACHER)
    landed = [one["conversation_id"] for one in listed.json()]
    assert gone not in landed
    # Và nó rơi vào một đoạn **đọc được**, không rơi vào hư không.
    assert landed
    kept = await client.get(f"/api/teacher/chat?conversation_id={landed[0]}", headers=TEACHER)
    assert kept.status_code == 200
    assert any(one["tool_name"] == "teacher.approve" for one in kept.json()["turns"])
