"""Mỗi câu một mục kiến thức: phép chia (`be/coverage.py`) và chỗ nó được đóng băng (`fire`).

Luật của hậu ký ADR-27, kiểm bằng số: số câu ≤ số mục thì không hai câu chung một mục; nhiều câu
hơn số mục thì không hai câu chung một nhóm đoạn, khi mục còn đủ đoạn để chia; soạn thêm không đổi
mục của câu đã có. Và `fire` ghi mục **trước** khi đẩy job, gửi cho job đoạn của mục mình cùng tiêu
đề mục của các câu khác -- còn khi cây đã dựng lại, nó từ chối thay vì soạn trên cây khác.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import drafting
from be.content_reader import MemoryContentReader, bind_reader
from be.coverage import Unit, assign, slots, units_in_scope
from be.db import bind_sessions
from be.identity import Asking
from be.seed import seed_if_empty
from be.teacher_tools import PHASE_WORK, execute
from contracts import (
    BlockRef,
    DocumentState,
    IndexChunk,
    IndexHeader,
    IndexMethod,
    IndexNode,
    TitleSource,
)
from schema.ddl import prepare_schema
from schema.models import Document, DraftItem, Teacher

_BUILT = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


def _node(ordinal, title, parent, numbering=None):
    return IndexNode(
        document_id="book",
        ordinal=ordinal,
        parent_ordinal=parent,
        level=1 if parent is None else 2,
        numbering=numbering,
        title=title,
        title_source=TitleSource.TEXT,
        anchor=BlockRef(page=1, block=ordinal),
        page_start=1,
        page_end=2,
    )


def _chunk(ordinal, node, chars=100):
    return IndexChunk(
        document_id="book",
        ordinal=ordinal,
        node_ordinal=node,
        blocks=(BlockRef(page=1, block=ordinal),),
        text=f"đoạn {ordinal} của mục {node}",
        page_start=1,
        page_end=1,
        char_count=chars,
    )


# Chương I (mở đầu: đoạn 0) › Bài 1 (đoạn 1, 2) › Bài 2 (đoạn 3); Chương II (đoạn 4).
_NODES = [
    _node(0, "SỐ TỰ NHIÊN", None, "Chương I"),
    _node(1, "Tập hợp", 0, "Bài 1"),
    _node(2, "Ghi số", 0, "Bài 2"),
    _node(3, "SỐ NGUYÊN", None, "Chương II"),
]
_CHUNKS = [_chunk(0, 0, 50), _chunk(1, 1, 300), _chunk(2, 1, 300), _chunk(3, 2), _chunk(4, 3)]


def _units() -> list[Unit]:
    return units_in_scope(_NODES, _CHUNKS, [0])


def test_a_scope_is_its_subtree_and_each_unit_owns_its_own_text() -> None:
    units = _units()

    assert [unit.node for unit in units] == [0, 1, 2]
    assert units[1].title == "Chương I. SỐ TỰ NHIÊN › Bài 1. Tập hợp"
    assert units[1].chunks == ((1, 300), (2, 300))
    # Chương II nằm ngoài phạm vi.
    assert 3 not in [unit.node for unit in units]


@pytest.mark.parametrize("total", [1, 2, 3])
def test_no_two_questions_share_a_unit_while_there_are_enough(total) -> None:
    placed = slots(_units(), total)

    assert len(placed) == total
    assert len({slot.node for slot in placed}) == total


def test_fewer_questions_go_to_the_longer_units_in_reading_order() -> None:
    assert [slot.node for slot in slots(_units(), 2)] == [1, 2]


def test_more_questions_than_units_split_a_unit_into_different_paragraphs() -> None:
    placed = slots(_units(), 4)

    assert len(placed) == 4
    assert {slot.node for slot in placed} == {0, 1, 2}
    # Bài 1 dài nhất nên nhận câu thứ tư -- trên hai nhóm đoạn khác nhau.
    lesson = [slot.chunks for slot in placed if slot.node == 1]
    assert sorted(lesson) == [(1,), (2,)]
    assert len(set(placed)) == 4


def test_drafting_more_keeps_every_frozen_question_where_it_was() -> None:
    first = assign(_units(), 2, {}, [1, 2])
    more = assign(_units(), 3, first, [3])

    assert set(more) == {3}
    assert more[3].node not in {slot.node for slot in first.values()}


def test_a_scope_with_no_text_places_nothing() -> None:
    assert assign([], 5, {}, [1, 2]) == {}


# ------------------------------------------------------------------ fire, với một kho giả


@pytest_asyncio.fixture
async def stack(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        session.add(
            Document(
                id="book",
                teacher_id=teacher.id,
                filename="SGK.pdf",
                byte_size=1,
                storage_key="k",
                state=DocumentState.READY.value,
                uploaded_at=_BUILT,
            )
        )
        await session.commit()

    reader = MemoryContentReader()
    header = IndexHeader(
        document_id="book",
        raw_started_at=_BUILT,
        method=IndexMethod.RULES,
        node_count=len(_NODES),
        chunk_count=len(_CHUNKS),
        built_at=_BUILT,
    )
    reader.trees["book"] = (header, list(_NODES))
    reader.pieces["book"] = list(_CHUNKS)
    bind_reader(reader)

    queued: list[dict] = []

    async def enqueue(_pool, _settings, _task, payload):
        queued.append(payload)
        return f"job-{len(queued)}"

    async def collect(_pool, _settings, _job_id):
        return ("pending", None)

    monkeypatch.setattr(drafting, "enqueue_task", enqueue)
    monkeypatch.setattr(drafting, "collect_result", collect)
    yield maker, reader, queued
    bind_reader(None)
    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _run(maker, name, args):
    async with maker() as session:
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        return await execute(
            session, Asking.of(teacher), name, args, pool=object(), phase=PHASE_WORK
        )


async def _draft(maker, count: str) -> dict:
    made = await _run(
        maker,
        "create_draft",
        {
            "subject": "Toán",
            "grade": "6",
            "topic_scope": "Chương I",
            "document_id": "book",
            "nodes": "0",
        },
    )
    started = await _run(
        maker, "start_drafting", {"assessment_id": made["assessment_id"], "question_count": count}
    )
    return {**made, **started}


@pytest.mark.asyncio
async def test_each_job_gets_its_own_unit_and_hears_what_the_others_cover(stack) -> None:
    maker, _, queued = stack

    started = await _draft(maker, "3")

    assert started["started"] is True
    async with maker() as session:
        rows = list(await session.scalars(select(DraftItem).order_by(DraftItem.ordinal)))
    assert [row.node_ordinal for row in rows] == [0, 1, 2]
    lesson_one = next(job for job in queued if job["focus_title"].endswith("Bài 1. Tập hợp"))
    assert "đoạn 1 của mục 1" in lesson_one["focus_text"]
    assert "đoạn 3" not in lesson_one["focus_text"]
    assert "Chương I. SỐ TỰ NHIÊN › Bài 2. Ghi số" in lesson_one["other_foci"]
    assert lesson_one["focus_title"] not in lesson_one["other_foci"]


@pytest.mark.asyncio
async def test_a_rebuilt_tree_stops_the_drafting_with_a_reason(stack) -> None:
    """Đọc lại tài liệu đánh số lại nút: soạn trên cây mới là soạn sai mục -- từ chối, nói lý do."""
    maker, reader, queued = stack
    made = await _run(
        maker,
        "create_draft",
        {
            "subject": "Toán",
            "grade": "6",
            "topic_scope": "Chương I",
            "document_id": "book",
            "nodes": "0",
        },
    )
    header, nodes = reader.trees["book"]
    reader.trees["book"] = (header.model_copy(update={"built_at": datetime.now(UTC)}), nodes)

    started = await _run(
        maker, "start_drafting", {"assessment_id": made["assessment_id"], "question_count": "2"}
    )

    assert started["started"] is False
    assert "đọc lại" in started["reason"]
    assert queued == []


@pytest.mark.asyncio
async def test_a_draft_without_a_book_is_written_as_before(stack) -> None:
    maker, _, queued = stack
    made = await _run(
        maker, "create_draft", {"subject": "Toán", "grade": "12", "topic_scope": "Hàm số"}
    )

    await _run(
        maker, "start_drafting", {"assessment_id": made["assessment_id"], "question_count": "2"}
    )

    assert [job["focus_title"] for job in queued] == ["", ""]
    async with maker() as session:
        rows = list(await session.scalars(select(DraftItem)))
    assert {row.node_ordinal for row in rows} == {None}


@pytest.mark.asyncio
async def test_drafting_more_leaves_the_first_questions_on_their_units(stack) -> None:
    """Review B4: `fire` lần hai giữ `node_ordinal` của hàng cũ -- bỏ `taken` thì test này đỏ."""
    maker, _, queued = stack
    # Một câu trước: nó về Bài 1, đơn vị dài nhất. Câu thêm phải về đơn vị khác -- phép chia cho
    # tổng 2 cũng chọn Bài 1 trước, nên quên ô cũ là đặt câu mới chồng lên đúng câu ấy.
    first = await _draft(maker, "1")
    async with maker() as session:
        before = {row.ordinal: row.node_ordinal for row in await session.scalars(select(DraftItem))}
        for row in await session.scalars(select(DraftItem)):
            row.status = "ready"
        await session.commit()

    await _run(
        maker, "start_drafting", {"assessment_id": first["assessment_id"], "question_count": "1"}
    )

    async with maker() as session:
        after = {row.ordinal: row.node_ordinal for row in await session.scalars(select(DraftItem))}
    assert before == {1: 1}
    assert after[1] == 1
    assert after[2] != 1


@pytest.mark.asyncio
async def test_a_retry_on_a_rebuilt_tree_stops_with_a_reason(stack) -> None:
    """Review B4: `_refire` gặp cây đã dựng lại thì ô ấy `failed`, kèm lý do đọc được."""
    maker, reader, queued = stack
    first = await _draft(maker, "1")
    header, nodes = reader.trees["book"]
    reader.trees["book"] = (header.model_copy(update={"built_at": datetime.now(UTC)}), nodes)

    async with maker() as session:
        row = await session.scalar(select(DraftItem))
        row.status = "retry"
        await drafting._refire(
            session, object(), drafting.Settings(), first["assessment_id"], [row]
        )
        await session.commit()
        again = await session.scalar(select(DraftItem))

    assert again.status == "failed"
    assert "đọc lại" in again.last_fault
    assert len(queued) == 1
