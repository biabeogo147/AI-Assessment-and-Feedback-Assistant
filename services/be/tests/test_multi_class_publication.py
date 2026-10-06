"""Một đề, nhiều lớp, nhiều cái đồng hồ.

Trước đây việc phát hành là mỗi đề một dòng, và model dữ liệu được viết như thế một cách có
chủ ý: hai bộ hạn chót cùng sống cho một đề từng bị gọi là một state không ai giải
thích nổi cho học sinh. Lập luận đó sai theo một cách rất cụ thể — nó trộn *một đề*
với *một lớp*. Hai bộ hạn chót cho hai lớp khác nhau thì tự giải thích được hoàn
hảo, bởi một học sinh bao giờ cũng chỉ thấy bộ của chính mình: 12A học tiết sáng thì mở
buổi sáng, 12B học sau trưa thì mở sau trưa.

Vậy nên một `Publication` giờ là mỗi (assessment, class) một dòng, và các test ở đây
pin lại hai điều đi theo đó. Mỗi lớp đọc đúng các điều khoản của mình. Và một
`Attempt` ghi lại lớp mà nó được bắt đầu trong đó, vì nếu không, một học sinh chuyển
lớp sẽ bị thay âm thầm các hạn chót của phần việc em đã làm bằng hạn chót của một
lớp khác.

**Từ 06/10/2026, hai cái đồng hồ không còn tới từ MỘT lần phát hành.** `PublishRequest`
nay là một `Schedule` cộng `class_ids`, nên một lần gửi đặt một khung giờ cho mọi lớp
trong lần đó -- biểu mẫu vốn chỉ có một bộ ô nhập và vẫn luôn gửi như thế. Bảng thì
không đổi và vẫn chở được hai đồng hồ: muốn thế thì phát hành hai lần. Các test ở đây
dựng thẳng hàng `Publication`, nên chúng vẫn đo đúng cái chúng vẫn đo -- luật của học
sinh, không phải hình dạng của một request.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import agent_gateway
from be import db as db_module
from be.db import bind_sessions, prepare_schema
from be.models import Assessment, Attempt, Publication, SchoolClass, Student
from be.seed import seed_if_empty
from be.student_routes import router as student_router

MORNING = {"X-Actor": "student:HS2026-1204"}
AFTERNOON = {"X-Actor": "student:HS2026-9101"}


async def _fake_run_task(pool, settings, task_name, payload) -> dict:
    return {"schema_version": 1, "request_id": payload["request_id"], "text": "Trả lời mẫu."}


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """Một database đã seed, cộng một lớp thứ hai nhận cùng đề đó nhưng muộn hơn."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)

        assessment = await session.scalar(select(Assessment))
        first = await session.scalar(select(Publication))
        assert assessment is not None and first is not None

        # Lớp buổi chiều: cùng đề, cùng giáo viên, một cái đồng hồ riêng.
        afternoon = SchoolClass(teacher_id=assessment.teacher_id, name="12B")
        session.add(afternoon)
        await session.flush()
        session.add(
            Student(class_id=afternoon.id, full_name="Bùi Thị Chiều", student_code="HS2026-9101")
        )
        now = datetime.now(UTC)
        session.add(
            Publication(
                assessment_id=assessment.id,
                class_id=afternoon.id,
                opens_at=now + timedelta(hours=4),
                closes_at=now + timedelta(hours=9),
                phase1_minutes=15,
                phase2_minutes_per_question=5,
                remediation_deadline=now + timedelta(hours=20),
                published_at=now,
            )
        )
        await session.commit()

    monkeypatch.setattr(agent_gateway, "run_task", _fake_run_task)

    app = FastAPI()
    app.include_router(student_router)
    app.state.queue_pool = object()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker

    await engine.dispose()
    db_module._SESSION_MAKER = None


@pytest.mark.asyncio
async def test_one_assessment_can_hold_two_sets_of_terms(stack) -> None:
    """Hai dòng, một đề. Primary key cũ làm chuyện này thành bất khả."""
    _, maker = stack

    async with maker() as session:
        published = (await session.scalars(select(Publication))).all()

    assert len(published) == 2
    assert len({row.assessment_id for row in published}) == 1
    assert len({row.class_id for row in published}) == 2
    # Hai cái đồng hồ khác nhau mới là trọng tâm; giống nhau thì chẳng chứng minh gì.
    assert len({row.opens_at for row in published}) == 2


@pytest.mark.asyncio
async def test_each_class_reads_its_own_clock(stack) -> None:
    """Lớp buổi sáng được vào; lớp buổi chiều thì chưa.

    Cùng một đề, cùng một khoảnh khắc, hai câu trả lời — đúng cái điều mà một dòng
    duy nhất cho mỗi đề không diễn đạt được.
    """
    client, _ = stack

    morning = (await client.get("/api/me/assignments", headers=MORNING)).json()
    afternoon = (await client.get("/api/me/assignments", headers=AFTERNOON)).json()

    assert len(morning) == 1
    assert len(afternoon) == 1
    assert morning[0]["assignment_id"] == afternoon[0]["assignment_id"]
    assert morning[0]["opens_at"] != afternoon[0]["opens_at"]
    assert morning[0]["status"] != afternoon[0]["status"]


@pytest.mark.asyncio
async def test_an_attempt_remembers_the_class_it_started_in(stack) -> None:
    """Dòng dữ liệu ghi lại bộ điều khoản nào đang chi phối nó."""
    client, maker = stack

    assignments = (await client.get("/api/me/assignments", headers=MORNING)).json()
    started = await client.post(
        f"/api/assignments/{assignments[0]['assignment_id']}/attempts", headers=MORNING
    )
    assert started.status_code == 201

    async with maker() as session:
        attempt = await session.scalar(select(Attempt))
        student = await session.scalar(select(Student).where(Student.student_code == "HS2026-1204"))

    assert attempt is not None and student is not None
    assert attempt.class_id == student.class_id


@pytest.mark.asyncio
async def test_changing_class_does_not_lock_a_student_out_of_work_in_progress(stack) -> None:
    """Vào lại thì đọc lớp của `Attempt`, không đọc lớp hôm nay của học sinh.

    `start_attempt` tra `Publication` trước khi tra `Attempt`, nên cửa vào lúc nào
    cũng được áp theo lớp của ngày hôm nay. Một học sinh chuyển từ lớp sáng sang lớp
    chiều liền bị bảo "chưa tới giờ mở" về một bài em đang làm giữa chừng — và nếu lớp
    mới chẳng có `Publication` nào, thì là "bài này chưa được phát hành".

    ADR-03 vốn đã cấm chuyện này từ phía ngược lại: *"Học sinh đã vào rồi thì không bị
    dừng giữa chừng."* Cửa vào canh việc vào, không canh việc tiếp tục.
    """
    client, maker = stack

    assignments = (await client.get("/api/me/assignments", headers=MORNING)).json()
    assessment_id = assignments[0]["assignment_id"]
    started = await client.post(f"/api/assignments/{assessment_id}/attempts", headers=MORNING)
    assert started.status_code == 201

    async with maker() as session:
        student = await session.scalar(select(Student).where(Student.student_code == "HS2026-1204"))
        afternoon = await session.scalar(select(SchoolClass).where(SchoolClass.name == "12B"))
        assert student is not None and afternoon is not None
        student.class_id = afternoon.id
        await session.commit()

    again = await client.post(f"/api/assignments/{assessment_id}/attempts", headers=MORNING)

    # Trả 201 cho một request không tạo ra gì là một lời nói dối nhỏ mà route này đã
    # nói từ trước thay đổi lần này và vẫn còn nói: status code bị gắn cứng trên
    # decorator trong khi handler có hai kết cục. Được khẳng định theo đúng thực tế
    # chứ không theo điều đáng ra phải thế, để test này vẫn nói về chuyện chuyển lớp.
    assert again.status_code == 201
    assert again.json()["attempt_id"] == started.json()["attempt_id"]


@pytest.mark.asyncio
async def test_the_phase_two_deadline_follows_the_attempt_not_the_student(stack) -> None:
    """Hạn chót được đọc lại ở mọi request, nên test này thật sự có thể đỏ.

    Bản đầu tiên của test này so `ends_at` qua một lần chuyển lớp — nhưng `ends_at` là
    một cột ghi đúng một lần lúc bắt đầu, và route phục vụ nó thì chẳng bao giờ nạp một
    `Publication` nào. Nó sẽ vẫn xanh dù mọi chỗ gọi đều bị trả về dùng lớp hiện tại
    của học sinh.

    `remediation_deadline` thì khác: `/result` đọc nó từ `Publication` mỗi lần. Lớp
    sáng có nó ở +8h còn lớp chiều ở +20h, nên đọc điều khoản của lớp sai sẽ xê dịch nó
    đi mười hai tiếng.
    """
    client, maker = stack

    assignments = (await client.get("/api/me/assignments", headers=MORNING)).json()
    assessment_id = assignments[0]["assignment_id"]
    started = await client.post(f"/api/assignments/{assessment_id}/attempts", headers=MORNING)
    attempt_id = started.json()["attempt_id"]
    await client.post(f"/api/attempts/{attempt_id}/submit", headers=MORNING)

    before = (await client.get(f"/api/attempts/{attempt_id}/result", headers=MORNING)).json()

    async with maker() as session:
        student = await session.scalar(select(Student).where(Student.student_code == "HS2026-1204"))
        afternoon = await session.scalar(select(SchoolClass).where(SchoolClass.name == "12B"))
        assert student is not None and afternoon is not None
        student.class_id = afternoon.id
        await session.commit()

    after = (await client.get(f"/api/attempts/{attempt_id}/result", headers=MORNING)).json()

    assert after["remediation_deadline"] == before["remediation_deadline"]
