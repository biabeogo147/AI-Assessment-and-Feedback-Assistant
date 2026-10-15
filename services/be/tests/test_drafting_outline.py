"""Mỗi câu một mục dàn ý (`draft-outline`, ADR-29): `fire` gán mục trước khi job nào chạy, và mỗi
job nhận đúng mục của nó -- không chữ tài liệu nào.

Ba loại khẳng định. Gán theo đúng thứ tự giáo viên đã đọc (*"Câu 2–3"* là ô 2 và 3). Soạn thêm nối
mục mới mà không xáo mục của câu đã có. Và một ô bắn lại mang lại đúng mục của nó.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import drafting
from be.assessment_state import AssessmentState
from be.config import get_settings
from be.db import bind_sessions
from be.drafting import item_fields, place_items
from be.seed import seed_if_empty
from schema.ddl import prepare_schema
from schema.models import Assessment, DraftBrief, DraftItem, Teacher


class FakeQueue:
    """Ghi lại những gì đã vào queue."""

    def __init__(self) -> None:
        self.payloads: list[dict] = []

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str):
        self.payloads.append(payload)
        return type("Queued", (), {"job_id": f"job-{len(self.payloads)}"})()


def _outline(*items: tuple[int, str], version: int = 1) -> dict:
    return {
        "version": version,
        "first": 1,
        "total": sum(count for count, _ in items),
        "for": "new",
        "document_id": "",
        "items": [
            {
                "questions": count,
                "knowledge": knowledge,
                "formulas": [f"${knowledge[0]}$"],
                "approach": f"cách làm {knowledge}",
                "source_nodes": [],
            }
            for count, knowledge in items
        ],
    }


@pytest_asyncio.fixture
async def stack():
    """Một đề nháp rỗng có brief, chưa có dàn ý nào."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        teacher = await session.scalar(select(Teacher))
        draft = Assessment(
            teacher_id=teacher.id,
            title="Nháp",
            subject="Toán",
            grade="6",
            state=AssessmentState.EMPTY,
            created_at=datetime.now(UTC),
        )
        session.add(draft)
        await session.flush()
        session.add(
            DraftBrief(
                assessment_id=draft.id,
                topic_scope="Chương I",
                question_count=0,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
        draft_id = draft.id
    yield maker, draft_id, FakeQueue()
    await engine.dispose()
    db_module._SESSION_MAKER = None


# ------------------------------------------------------------------ hàm thuần


def test_an_item_of_k_questions_takes_k_slots_in_reading_order() -> None:
    placed = place_items(_outline((1, "A"), (2, "B")), first_index=0, start=0)

    assert placed == {1: (0, 1), 2: (1, 1), 3: (1, 2)}


def test_more_questions_start_after_the_last_slot_and_the_last_item() -> None:
    assert place_items(_outline((2, "C")), first_index=2, start=3) == {4: (2, 1), 5: (2, 2)}


def test_a_slot_from_before_the_outline_gets_no_item_fields() -> None:
    brief = DraftBrief(assessment_id="a", topic_scope="x", question_count=1, outline=[])

    assert item_fields(brief, None, 1) == {}


# ------------------------------------------------------------------ fire


@pytest.mark.asyncio
async def test_a_job_receives_exactly_its_outline_item(stack) -> None:
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(
            session, queue, get_settings(), draft_id, 3, _outline((1, "A"), (2, "B"))
        )

    by_ordinal = {one["ordinal"]: one for one in queue.payloads}
    assert by_ordinal[1]["item_knowledge"] == "A"
    assert by_ordinal[1]["item_formulas"] == ["$A$"]
    assert by_ordinal[1]["item_approach"] == "cách làm A"
    assert (by_ordinal[1]["item_part"], by_ordinal[1]["item_parts"]) == (1, 1)
    assert by_ordinal[1]["other_items"] == ["B"]
    # Hai câu chung mục B biết mình là câu thứ mấy của mục.
    assert [(by_ordinal[n]["item_part"], by_ordinal[n]["item_parts"]) for n in (2, 3)] == [
        (1, 2),
        (2, 2),
    ]
    # Không chữ tài liệu nào (ADR-29).
    assert all(one["focus_text"] == "" for one in queue.payloads)

    async with maker() as session:
        brief = await session.get(DraftBrief, draft_id)
        rows = {row.ordinal: row for row in await session.scalars(select(DraftItem))}
    assert [item["knowledge"] for item in brief.outline] == ["A", "B"]
    assert all(item["version"] == 1 for item in brief.outline)
    assert {n: (row.outline_item, row.item_part) for n, row in rows.items()} == {
        1: (0, 1),
        2: (1, 1),
        3: (1, 2),
    }


@pytest.mark.asyncio
async def test_drafting_more_appends_items_and_leaves_the_first_questions_alone(stack) -> None:
    maker, draft_id, queue = stack
    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 2, _outline((2, "A")))
        rows = list(await session.scalars(select(DraftItem)))
        for row in rows:
            row.status = "ready"
        await session.commit()

    async with maker() as session:
        await drafting.fire(
            session, queue, get_settings(), draft_id, 1, _outline((1, "C"), version=2)
        )

    added = queue.payloads[-1]
    assert (added["ordinal"], added["item_knowledge"], added["other_items"]) == (3, "C", ["A"])
    async with maker() as session:
        brief = await session.get(DraftBrief, draft_id)
        rows = {row.ordinal: row.outline_item for row in await session.scalars(select(DraftItem))}
    assert [(item["knowledge"], item["version"]) for item in brief.outline] == [
        ("A", 1),
        ("C", 2),
    ]
    assert rows == {1: 0, 2: 0, 3: 1}


@pytest.mark.asyncio
async def test_a_slot_fired_again_carries_its_own_item_again(stack) -> None:
    maker, draft_id, queue = stack
    async with maker() as session:
        await drafting.fire(
            session, queue, get_settings(), draft_id, 2, _outline((1, "A"), (1, "B"))
        )
        second = await session.scalar(select(DraftItem).where(DraftItem.ordinal == 2))
        second.status = "retry"
        await session.commit()

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 0)

    again = queue.payloads[-1]
    assert (again["ordinal"], again["item_knowledge"], again["other_items"]) == (2, "B", ["A"])


def test_two_items_on_the_same_knowledge_do_not_tell_each_other_to_stay_away() -> None:
    """Cùng bài, khác cách làm là được phép: job không bị dặn né chính kiến thức của nó."""
    same = [
        {"questions": 1, "knowledge": "A", "formulas": [], "approach": "cách 1"},
        {"questions": 1, "knowledge": "A", "formulas": [], "approach": "cách 2"},
        {"questions": 1, "knowledge": "B", "formulas": [], "approach": "cách 3"},
    ]
    brief = DraftBrief(assessment_id="a", topic_scope="x", question_count=3, outline=same)

    assert item_fields(brief, 1, 1)["other_items"] == ("B",)
