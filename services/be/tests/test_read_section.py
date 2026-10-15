"""Kriky đọc chữ của phạm vi trước khi viết dàn ý (`draft-outline`, ADR-29).

Hai loại khẳng định. Phép gộp (`toc.parts`) chỉ **gộp**, không bao giờ chặt một nút, và không cho
nhiều phần hơn số câu giáo viên xin. Và `read_section` chỉ đọc tài liệu **của giáo viên**, **đã sẵn
sàng**, trả từng phần kèm nút nguồn -- thứ dàn ý sẽ trỏ về.

Kho nội dung là `MemoryContentReader`: không Mongo thật nào.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import teacher_tools
from be.content_reader import ContentUnavailable, MemoryContentReader, bind_reader, get_reader
from be.db import bind_sessions
from be.identity import Asking
from be.seed import seed_if_empty
from be.teacher_tools import PHASE_PLAN, execute
from be.toc import parts
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
from schema.models import Document as DocumentRow
from schema.models import Teacher

_BUILT = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)


def _node(ordinal: int, title: str, parent: int | None, level: int, numbering: str) -> IndexNode:
    return IndexNode(
        document_id="book",
        ordinal=ordinal,
        parent_ordinal=parent,
        level=level,
        numbering=numbering,
        title=title,
        title_source=TitleSource.TEXT,
        anchor=BlockRef(page=ordinal + 1, block=0),
        page_start=ordinal + 5,
        page_end=ordinal + 6,
    )


# Chương I có ba bài, chương II một bài. Bài 1 dài gấp đôi các bài khác.
_TREE = [
    _node(0, "CHƯƠNG MỘT", None, 1, "Chương I"),
    _node(1, "Bài A", 0, 2, "Bài 1"),
    _node(2, "Bài B", 0, 2, "Bài 2"),
    _node(3, "Bài C", 0, 2, "Bài 3"),
    _node(4, "CHƯƠNG HAI", None, 1, "Chương II"),
    _node(5, "Bài D", 4, 2, "Bài 4"),
]
_TEXTS = {1: ["chữ A1 " * 50, "chữ A2 " * 50], 2: ["chữ B " * 50], 3: ["chữ C " * 50], 5: ["D"]}


def _chunks() -> list[IndexChunk]:
    out = []
    for node, texts in _TEXTS.items():
        for text in texts:
            out.append(
                IndexChunk(
                    document_id="book",
                    ordinal=len(out),
                    node_ordinal=node,
                    blocks=(BlockRef(page=1, block=len(out)),),
                    text=text,
                    page_start=1,
                    page_end=1,
                    char_count=len(text),
                )
            )
    return out


@pytest_asyncio.fixture
async def stack():
    """Giáo viên có một sách sẵn sàng và một sách đang đọc; người khác có một sách sẵn sàng."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    async with maker() as session:
        await seed_if_empty(session)
        mine = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        stranger = Teacher(full_name="Thầy B", teacher_code="GV-002")
        session.add(stranger)
        await session.flush()
        for document_id, owner, state in (
            ("book", mine.id, DocumentState.READY),
            ("busy", mine.id, DocumentState.PROCESSING),
            ("theirs", stranger.id, DocumentState.READY),
        ):
            session.add(
                DocumentRow(
                    id=document_id,
                    teacher_id=owner,
                    filename=f"{document_id}.pdf",
                    byte_size=10,
                    storage_key=f"k/{document_id}",
                    state=state.value,
                    uploaded_at=now,
                )
            )
        await session.commit()

    reader = MemoryContentReader()
    header = IndexHeader(
        document_id="book",
        raw_started_at=_BUILT,
        method=IndexMethod.RULES,
        node_count=len(_TREE),
        chunk_count=len(_chunks()),
        built_at=_BUILT,
    )
    for document_id in ("book", "busy", "theirs"):
        reader.trees[document_id] = (header.model_copy(update={"document_id": document_id}), _TREE)
        reader.pieces[document_id] = _chunks()
    bind_reader(reader)
    yield maker
    bind_reader(None)
    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _read(maker, **args: object) -> dict:
    async with maker() as session:
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        asked = {key: str(value) for key, value in args.items()}
        return await execute(session, Asking.of(teacher), "read_section", asked, phase=PHASE_PLAN)


# ------------------------------------------------------------------ phép gộp, hàm thuần


def test_parts_never_outnumber_the_questions() -> None:
    assert [len(one) for one in parts([10, 10, 10, 10, 10], 2)] == [3, 2]


def test_fewer_units_than_questions_gives_one_part_per_unit() -> None:
    assert parts([5, 5, 5], 8) == [[0], [1], [2]]


def test_parts_keep_reading_order_and_every_unit_once() -> None:
    grouped = parts([100, 1, 1, 1, 100, 1], 3)

    assert [index for one in grouped for index in one] == list(range(6))
    assert all(grouped)


def test_a_long_unit_is_never_split() -> None:
    assert parts([1000, 1], 2) == [[0], [1]]


def test_nothing_to_read_gives_no_parts() -> None:
    assert parts([], 5) == []
    assert parts([3], 0) == []


# ------------------------------------------------------------------ tool đọc


@pytest.mark.asyncio
async def test_a_chapter_for_two_questions_reads_in_two_parts(stack) -> None:
    first = await _read(stack, document_id="book", nodes=0, questions=2, part=1)
    second = await _read(stack, document_id="book", nodes=0, questions=2, part=2)

    assert (first["parts"], first["more"], second["more"]) == (2, True, False)
    # Bài 1 dài gấp đôi: nó đứng riêng một phần, hai bài còn lại chung phần kia.
    assert (first["nodes"], second["nodes"]) == ([1], [2, 3])
    assert first["labels"][0].startswith("Bài 1. Bài A")
    assert "## Chương I. CHƯƠNG MỘT › Bài 1. Bài A" in first["text"]
    assert "chữ A2" in first["text"]


@pytest.mark.asyncio
async def test_a_scope_of_several_chapters_reads_their_lessons_in_order(stack) -> None:
    read = await _read(stack, document_id="book", nodes="4,0", questions=10, part=4)

    # Bốn bài có chữ, mười câu xin: bốn phần, mỗi bài một phần, theo thứ tự đọc.
    assert (read["parts"], read["nodes"], read["more"]) == (4, [5], False)


@pytest.mark.asyncio
async def test_a_part_past_the_last_is_refused(stack) -> None:
    read = await _read(stack, document_id="book", nodes=0, questions=2, part=3)

    assert read["found"] is False
    assert "1 đến 2" in read["reason"]


@pytest.mark.asyncio
@pytest.mark.parametrize("questions", [0, 11])
async def test_more_than_ten_questions_is_not_a_reading_plan(stack, questions: int) -> None:
    read = await _read(stack, document_id="book", nodes=0, questions=questions, part=1)

    assert read["found"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("document_id", ["theirs", "busy", "nowhere"])
async def test_only_my_ready_books_can_be_read(stack, document_id: str) -> None:
    read = await _read(stack, document_id=document_id, nodes=0, questions=2, part=1)

    assert read["found"] is False
    assert "text" not in read


@pytest.mark.asyncio
async def test_a_node_the_tree_does_not_have_is_refused(stack) -> None:
    read = await _read(stack, document_id="book", nodes="0,99", questions=2, part=1)

    assert read["found"] is False


@pytest.mark.asyncio
async def test_nodes_written_with_spaces_are_still_separate_nodes(stack) -> None:
    """*"1 2"* là nút 1 và nút 2, không bao giờ là nút 12."""
    spaced = await _read(stack, document_id="book", nodes="1 2", questions=2, part=1)
    commas = await _read(stack, document_id="book", nodes="2, 1", questions=2, part=1)

    assert spaced["nodes"] == commas["nodes"] == [1]
    assert spaced["parts"] == commas["parts"] == 2


@pytest.mark.asyncio
async def test_a_part_over_its_cap_cuts_every_unit_and_says_so(stack, monkeypatch) -> None:
    monkeypatch.setattr(teacher_tools, "_PART_CHARS", 300)

    read = await _read(stack, document_id="book", nodes=0, questions=1, part=1)

    # Một câu cho cả chương: một phần ba bài, mỗi bài bị cắt và nói ra là bị cắt.
    assert read["nodes"] == [1, 2, 3]
    assert read["text"].count("[… phần sau của mục này không đọc trong lượt này]") == 3
    assert len(read["text"]) < 300 + 3 * 120


@pytest.mark.asyncio
async def test_a_content_store_that_fails_mid_read_says_so(stack, monkeypatch) -> None:
    async def down(*_args: object) -> list:
        raise ContentUnavailable("down")

    monkeypatch.setattr(get_reader(), "chunks", down)

    read = await _read(stack, document_id="book", nodes=0, questions=2, part=1)

    assert read["found"] is False
    assert "tạm thời" in read["reason"]
