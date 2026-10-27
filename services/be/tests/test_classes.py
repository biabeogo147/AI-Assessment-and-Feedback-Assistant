"""Tạo lớp (plan `tao-lop`, hậu ký ADR-13 ngày 27/10/2026): nút *Tạo lớp* của màn 9 và tool
`create_class` của Kriky đi qua một hàm, nên một luật tên.

Seed có lớp 12A của GV-001.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.classes import router as classes_router
from be.db import bind_sessions
from be.identity import Asking
from be.plan_outcomes import step_detail
from be.resolve import tidy_name
from be.seed import seed_if_empty
from be.teacher_reads import router as reads_router
from be.teacher_tools import PHASE_PLAN, PHASE_WORK, catalog_for, execute
from schema.ddl import prepare_schema
from schema.models import Assessment, Publication, SchoolClass, Teacher

TEACHER = {"X-Actor": "teacher:GV-001"}
STRANGER = {"X-Actor": "teacher:GV-002"}


@pytest_asyncio.fixture
async def stack():
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        session.add(Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002"))
        await session.commit()
    app = FastAPI()
    for router in (classes_router, reads_router):
        app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker
    await engine.dispose()
    db_module._SESSION_MAKER = None


@pytest.mark.parametrize(
    ("raw", "kept"),
    [
        ("12C", "12C"),
        ("  Lớp   12C ", "12C"),
        ("lớp: 10A1", "10A1"),
        ("Câu lạc bộ Toán", "Câu lạc bộ Toán"),
        ("Lớp chuyên Toán", "Lớp chuyên Toán"),
        ("Lopez CLB", "Lopez CLB"),
    ],
)
def test_a_class_name_is_kept_the_way_the_screen_prints_it(raw: str, kept: str) -> None:
    """Màn hình tự thêm *Lớp* trước tên bắt đầu bằng số: lưu *"Lớp 12C"* là in *"Lớp Lớp 12C"*."""
    assert tidy_name(raw) == kept


@pytest.mark.asyncio
async def test_a_new_class_is_empty_and_shows_on_the_class_list(stack) -> None:
    client, _ = stack

    created = await client.post("/api/teacher/classes", headers=TEACHER, json={"name": "Lớp 12C"})

    assert created.status_code == 201
    assert created.json()["name"] == "12C"
    listed = (await client.get("/api/teacher/classes", headers=TEACHER)).json()["classes"]
    new = next(one for one in listed if one["class_id"] == created.json()["class_id"])
    assert (new["name"], new["student_count"]) == ("12C", 0)
    detail = await client.get(f"/api/teacher/classes/{new['class_id']}", headers=TEACHER)
    assert detail.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("again", ["12A", "lớp 12a", "12 A"])
async def test_a_teacher_cannot_open_a_second_class_of_the_same_name(stack, again: str) -> None:
    """So bằng `normalise`, đúng phép so `list_class` dùng: Kriky không phải hỏi lại vì tên."""
    client, maker = stack

    refused = await client.post("/api/teacher/classes", headers=TEACHER, json={"name": again})

    assert refused.status_code == 409
    assert refused.json()["detail"] == 'Bạn đã có lớp "12A".'
    async with maker() as session:
        assert len(list(await session.scalars(select(SchoolClass)))) == 1


@pytest.mark.asyncio
async def test_another_teacher_may_have_a_class_of_the_same_name(stack) -> None:
    client, _ = stack

    created = await client.post("/api/teacher/classes", headers=STRANGER, json={"name": "12A"})

    assert created.status_code == 201
    mine = (await client.get("/api/teacher/classes", headers=TEACHER)).json()["classes"]
    assert created.json()["class_id"] not in {one["class_id"] for one in mine}


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "said"), [("   ", "trống"), ("x" * 65, "dài quá 64")])
async def test_an_empty_or_long_name_is_refused_in_words(stack, name: str, said: str) -> None:
    client, _ = stack

    refused = await client.post("/api/teacher/classes", headers=TEACHER, json={"name": name})

    assert refused.status_code == 422
    assert said in refused.json()["detail"]


async def _run(maker, name: str, args: dict, phase: int) -> dict:
    async with maker() as session:
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        found = await execute(session, Asking.of(teacher), name, args, phase=phase)
        # Đúng như `teacher_chat.run_the_step`: rollback sau mỗi bước. Tool ghi phải tự commit;
        # bản đầu của test commit thay nó, và che mất một lớp không bao giờ được lưu.
        await session.rollback()
        return found


@pytest.mark.asyncio
async def test_a_body_without_a_name_is_refused_in_words(stack) -> None:
    """Thiếu `name` là tên rỗng: `detail` là một câu hộp tạo lớp in được, không phải mảng lỗi."""
    client, _ = stack

    refused = await client.post("/api/teacher/classes", headers=TEACHER, json={})

    assert refused.status_code == 422
    assert refused.json()["detail"] == "Tên lớp đang trống."


@pytest.mark.asyncio
async def test_kriky_creates_a_class_only_inside_a_plan_and_list_class_finds_it(stack) -> None:
    """`create_class` là tool ghi: chỉ chạy ở pha thực hiện plan (ADR-25)."""
    _, maker = stack
    async with maker() as session:
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        asking = Asking.of(teacher)
    assert "create_class" not in {one.name for one in catalog_for(asking, PHASE_PLAN)}

    made = await _run(maker, "create_class", {"name": "12C"}, PHASE_WORK)
    found = await _run(maker, "list_class", {"name": "12C"}, PHASE_PLAN)

    assert made["created"] is True
    assert [one["class_id"] for one in found["candidates"]] == [made["class_id"]]
    assert step_detail("create_class", made) == 'lớp "12C", chưa có học sinh'


@pytest.mark.asyncio
async def test_kriky_is_refused_a_duplicate_name_in_words_for_the_teacher(stack) -> None:
    _, maker = stack

    refused = await _run(maker, "create_class", {"name": "lớp 12A"}, PHASE_WORK)

    assert refused["created"] is False
    assert refused["said"] == 'Bạn đã có lớp "12A".'
    assert step_detail("create_class", refused) == 'Bạn đã có lớp "12A".'


# ------------------------------------------------- xoá lớp rỗng (plan `erase-empty-class`)


async def _new_class(client: AsyncClient, name: str) -> str:
    created = await client.post("/api/teacher/classes", headers=TEACHER, json={"name": name})
    assert created.status_code == 201
    return created.json()["class_id"]


@pytest.mark.asyncio
async def test_an_empty_class_is_erasable_and_erasing_it_drops_it_from_the_list(stack) -> None:
    client, maker = stack
    class_id = await _new_class(client, "12C")
    detail = (await client.get(f"/api/teacher/classes/{class_id}", headers=TEACHER)).json()
    assert detail["erasable"] is True

    erased = await client.delete(f"/api/teacher/classes/{class_id}", headers=TEACHER)

    assert erased.status_code == 204
    async with maker() as session:
        assert await session.get(SchoolClass, class_id) is None
    gone = await client.get(f"/api/teacher/classes/{class_id}", headers=TEACHER)
    assert gone.status_code == 404
    # Tên đã thôi bị giữ: tạo lại cùng tên được.
    assert await _new_class(client, "12C")


@pytest.mark.asyncio
async def test_a_class_with_students_is_not_erasable(stack) -> None:
    client, maker = stack
    async with maker() as session:
        seeded = await session.scalar(select(SchoolClass).where(SchoolClass.name == "12A"))
        class_id = seeded.id
    detail = (await client.get(f"/api/teacher/classes/{class_id}", headers=TEACHER)).json()
    assert detail["erasable"] is False

    refused = await client.delete(f"/api/teacher/classes/{class_id}", headers=TEACHER)

    assert refused.status_code == 409
    assert refused.json()["detail"].endswith("học sinh nên không xoá được.")
    async with maker() as session:
        assert await session.get(SchoolClass, class_id) is not None


@pytest.mark.asyncio
async def test_a_class_that_received_a_paper_is_not_erasable_even_without_students(stack) -> None:
    """Hàng `Publication` ở lại sau thu hồi: lớp ấy có lịch sử, không phải lớp rỗng."""
    client, maker = stack
    class_id = await _new_class(client, "12C")
    async with maker() as session:
        paper = await session.scalar(select(Assessment).limit(1))
        now = datetime.now(UTC)
        session.add(
            Publication(
                assessment_id=paper.id,
                class_id=class_id,
                opens_at=now,
                closes_at=now,
                phase1_minutes=15,
                phase2_minutes_per_question=5,
                remediation_deadline=now,
                published_at=now,
                recalled_at=now,
            )
        )
        await session.commit()

    detail = (await client.get(f"/api/teacher/classes/{class_id}", headers=TEACHER)).json()
    refused = await client.delete(f"/api/teacher/classes/{class_id}", headers=TEACHER)

    assert detail["erasable"] is False
    assert (refused.status_code, refused.json()["detail"]) == (
        409,
        "Lớp đã nhận đề nên không xoá được.",
    )


@pytest.mark.asyncio
async def test_another_teachers_class_is_not_found_and_stays(stack) -> None:
    client, maker = stack
    class_id = await _new_class(client, "12C")

    refused = await client.delete(f"/api/teacher/classes/{class_id}", headers=STRANGER)

    assert refused.status_code == 404
    async with maker() as session:
        assert await session.get(SchoolClass, class_id) is not None
