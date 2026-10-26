"""Câu làm lại ở pha 2 nhận mục dàn ý của câu gốc (plan `retry-sees-its-outline-item`, hậu ký
ADR-17 26/10/2026).

Mục của một câu là mục của ô soạn ra nó: cùng đề, cùng số thứ tự, đã `ready`. Câu không có ô -- lấy
từ ngân hàng, seed, soạn trước ADR-29 -- chạy như trước. Không có chữ tài liệu nào trong payload.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from be import db as db_module
from be.assessment_state import AssessmentState
from be.db import bind_sessions
from be.seed import seed_if_empty
from be.student_routes import _outline_items, _retry_ask
from schema.ddl import prepare_schema
from schema.models import Assessment, DraftBrief, DraftItem, Question, Teacher

_NOW = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)


def _item(knowledge: str) -> dict:
    return {
        "questions": 1,
        "knowledge": knowledge,
        "formulas": ["$a^m \\cdot a^n = a^{m+n}$"],
        "approach": f"cách làm {knowledge}",
        "source_nodes": [14],
    }


@pytest_asyncio.fixture
async def paper():
    """Một đề ba câu: câu 1, 2 do Kriky soạn theo mục 0 và 1; câu 3 lấy từ ngân hàng."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        teacher = await session.scalar(select(Teacher))
        draft = Assessment(
            teacher_id=teacher.id,
            title="Đề luỹ thừa",
            subject="Toán",
            grade="6",
            state=AssessmentState.PUBLISHED,
            created_at=_NOW,
        )
        session.add(draft)
        await session.flush()
        session.add(
            DraftBrief(
                assessment_id=draft.id,
                topic_scope="luỹ thừa",
                question_count=3,
                outline=[_item("nhân hai luỹ thừa"), _item("chia hai luỹ thừa")],
                created_at=_NOW,
            )
        )
        for ordinal, outline_item, at in ((1, 0, 0), (2, 1, 5)):
            session.add(
                DraftItem(
                    assessment_id=draft.id,
                    ordinal=ordinal,
                    job_id=f"job-{ordinal}-{at}",
                    status="ready",
                    brief_version=1,
                    attempts=1,
                    outline_item=outline_item,
                    created_at=_NOW + timedelta(minutes=at),
                )
            )
        questions = []
        for order, source in ((1, "kriky"), (2, "kriky"), (3, "bank")):
            question = Question(
                assessment_id=draft.id,
                order_index=order,
                stem=f"Câu {order}?",
                learning_objective="luỹ thừa",
                source=source,
            )
            session.add(question)
            questions.append(question)
        # Câu 3 đứng ở số thứ tự có ô `ready` -- nhưng nó là câu ngân hàng, không do ô ấy soạn.
        session.add(
            DraftItem(
                assessment_id=draft.id,
                ordinal=3,
                job_id="job-3",
                status="ready",
                brief_version=1,
                attempts=1,
                outline_item=0,
                created_at=_NOW,
            )
        )
        await session.commit()
    yield maker, questions
    await engine.dispose()
    db_module._SESSION_MAKER = None


@pytest.mark.asyncio
async def test_each_question_gets_the_item_of_the_cell_that_wrote_it(paper) -> None:
    maker, questions = paper
    async with maker() as session:
        found = await _outline_items(session, questions)

    first, second, bank = questions
    assert found[first.id]["item_knowledge"] == "nhân hai luỹ thừa"
    assert found[second.id]["item_knowledge"] == "chia hai luỹ thừa"
    assert found[second.id]["item_formulas"] == ("$a^m \\cdot a^n = a^{m+n}$",)
    assert bank.id not in found


@pytest.mark.asyncio
async def test_a_retry_ask_carries_the_item_and_a_question_without_one_runs_as_before(
    paper,
) -> None:
    maker, questions = paper
    async with maker() as session:
        found = await _outline_items(session, questions)
        rows = await session.scalars(
            select(Question)
            .where(Question.id.in_([one.id for one in questions]))
            .options(selectinload(Question.options), selectinload(Question.methods))
        )
        loaded = {row.id: row for row in rows}
        first, _, bank = questions
        with_item = _retry_ask("att", loaded[first.id], None, 1, (), found.get(first.id))
        without = _retry_ask("att", loaded[bank.id], None, 1, (), found.get(bank.id))

    assert with_item.item_approach == "cách làm nhân hai luỹ thừa"
    assert (without.item_knowledge, without.item_formulas, without.item_approach) == ("", (), "")


class _Queue:
    """Ghi lại payload vào queue."""

    def __init__(self) -> None:
        self.payloads: list[dict] = []

    async def enqueue_job(self, name: str, payload: dict, **_kwargs: object):
        self.payloads.append(payload)
        return type("Queued", (), {"job_id": f"job-{len(self.payloads)}"})()


@pytest.mark.asyncio
async def test_the_job_written_ahead_carries_the_item(paper) -> None:
    """Đường chạy trước (`_write_ahead`): payload thật trong queue mang mục của câu gốc."""
    from be.student_routes import _write_ahead

    maker, questions = paper
    queue = _Queue()
    async with maker() as session:
        rows = await session.scalars(
            select(Question)
            .where(Question.id.in_([one.id for one in questions]))
            .options(selectinload(Question.options), selectinload(Question.methods))
        )
        loaded = sorted(rows, key=lambda row: row.order_index)
        await _write_ahead(session, queue, "att", loaded, {}, 1)

    knowledge = [payload.get("item_knowledge") for payload in queue.payloads]
    assert knowledge == ["nhân hai luỹ thừa", "chia hai luỹ thừa", ""]
