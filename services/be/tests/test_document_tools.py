"""Kriky đọc thư viện và mục lục của giáo viên, và mở đề với phạm vi là các mục ấy
(`draft-from-document`).

Ba loại khẳng định. Tool đọc chỉ thấy tài liệu **của giáo viên** và **đã sẵn sàng** -- tài liệu của
người khác và tài liệu chưa có cây đọc lên y như nhau (ADR-22). Phương án của một câu hỏi lại là chữ
**BE** dựng từ cây (ADR-23, ADR-27). Và `create_draft` đóng băng tài liệu, các nút và phiên bản cây
vào `DraftBrief`, rồi `rebrief` thay **cả** phạm vi ấy khi brief đổi.

Kho nội dung là `MemoryContentReader`: không Mongo thật nào.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.content_reader import MemoryContentReader, bind_reader
from be.db import bind_sessions
from be.drafting import rebrief
from be.identity import Asking
from be.seed import seed_if_empty
from be.teacher_chat import _offered, vet_plan
from be.teacher_tools import PHASE_PLAN, PHASE_WORK, bind_book, catalog_for, execute
from contracts import (
    BlockRef,
    DocumentState,
    IndexChunk,
    IndexHeader,
    IndexMethod,
    IndexNode,
    PlanStep,
    TitleSource,
)
from schema.ddl import prepare_schema
from schema.models import Document as DocumentRow
from schema.models import DraftBrief, Teacher

_BUILT = datetime(2026, 10, 12, 9, 0, 0, 123000, tzinfo=UTC)


def _node(ordinal: int, title: str, parent: int | None, level: int, numbering: str | None):
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
        page_end=ordinal + 7,
        printed_start=ordinal + 3,
        printed_end=ordinal + 5,
        summary="Tóm tắt " + title,
    )


_TREE = [
    _node(0, "TẬP HỢP CÁC SỐ TỰ NHIÊN", None, 1, "Chương I"),
    _node(1, "Tập hợp", 0, 2, "Bài 1"),
    _node(2, "Cách ghi số tự nhiên", 0, 2, "Bài 2"),
    _node(3, "SỐ NGUYÊN", None, 1, "Chương II"),
]


@pytest_asyncio.fixture
async def stack():
    """Database đã seed: giáo viên có một sách sẵn sàng, một sách đang đọc; người khác có một."""
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
        for document_id, owner, state, name in (
            ("book", mine.id, DocumentState.READY, "SGK Toán 6.pdf"),
            ("busy", mine.id, DocumentState.PROCESSING, "Đang đọc.pdf"),
            ("theirs", stranger.id, DocumentState.READY, "Của người khác.pdf"),
        ):
            session.add(
                DocumentRow(
                    id=document_id,
                    teacher_id=owner,
                    filename=name,
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
        chunk_count=1,
        built_at=_BUILT,
    )
    reader.trees["book"] = (header, list(_TREE))
    reader.trees["theirs"] = (header.model_copy(update={"document_id": "theirs"}), list(_TREE))
    reader.pieces["book"] = [
        IndexChunk(
            document_id="book",
            ordinal=0,
            node_ordinal=1,
            blocks=(BlockRef(page=1, block=0),),
            text="Tập hợp là …",
            page_start=1,
            page_end=1,
            char_count=11,
        )
    ]
    bind_reader(reader)
    yield maker, reader
    bind_reader(None)
    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _run(maker, name: str, args: dict, phase: int = PHASE_PLAN) -> dict:
    async with maker() as session:
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        return await execute(session, Asking.of(teacher), name, args, phase=phase)


@pytest.mark.asyncio
async def test_the_library_lists_only_my_ready_documents(stack) -> None:
    maker, _ = stack

    found = await _run(maker, "list_documents", {})

    assert found == {"candidates": [{"document_id": "book", "label": "SGK Toán 6.pdf"}], "more": 0}


@pytest.mark.asyncio
async def test_chapters_are_the_roots_labelled_the_way_a_teacher_reads_them(stack) -> None:
    maker, _ = stack

    found = await _run(maker, "list_chapters", {"document_id": "book"})

    assert [one["node"] for one in found["candidates"]] == [0, 3]
    first = found["candidates"][0]
    # Trang **in**, không phải trang tệp: giáo viên lật sách theo số in.
    assert first["label"] == "Chương I. TẬP HỢP CÁC SỐ TỰ NHIÊN (tr. 3–5)"
    assert first["children"] == 2
    assert first["summary"].startswith("Tóm tắt")


@pytest.mark.asyncio
async def test_a_chapter_opens_into_its_lessons(stack) -> None:
    maker, _ = stack

    found = await _run(maker, "get_chapter", {"document_id": "book", "node": "0"})

    assert [one["label"] for one in found["candidates"]] == [
        "Bài 1. Tập hợp (tr. 4–6)",
        "Bài 2. Cách ghi số tự nhiên (tr. 5–7)",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("document_id", ["theirs", "busy", "nope"])
async def test_someone_elses_book_reads_like_a_book_that_is_not_there(stack, document_id) -> None:
    """ADR-22: của người khác, chưa sẵn sàng, không tồn tại -- một câu trả lời."""
    maker, _ = stack

    found = await _run(maker, "list_chapters", {"document_id": document_id})

    assert found["found"] is False
    assert "không có tài liệu sẵn sàng" in found["reason"]


@pytest.mark.asyncio
async def test_a_content_store_that_went_away_is_said_not_raised(stack) -> None:
    maker, reader = stack
    reader.broken = True

    found = await _run(maker, "list_chapters", {"document_id": "book"})

    assert found == {"found": False, "reason": "kho nội dung tài liệu tạm thời không đọc được"}


def test_the_buttons_of_a_question_about_chapters_are_written_by_be() -> None:
    """ADR-23 cho nút mới: `label` của BE thành nút, chữ model không bao giờ."""
    options, more = _offered(
        {
            "candidates": [
                {"node": 0, "label": "Chương I. TẬP HỢP (tr. 3–5)"},
                {"node": 3, "title": "chữ model bịa"},
            ],
            "more": 2,
        }
    )

    assert options == ["Chương I. TẬP HỢP (tr. 3–5)"]
    assert more == 2


@pytest.mark.asyncio
async def test_a_draft_freezes_its_book_its_chapters_and_the_tree_it_read(stack) -> None:
    maker, _ = stack
    brief = {"subject": "Toán", "grade": "6", "topic_scope": "chương I"}

    made = await _run(
        maker, "create_draft", {**brief, "document_id": "book", "nodes": "0"}, PHASE_WORK
    )

    assert made["created"] is True
    async with maker() as session:
        frozen = await session.get(DraftBrief, made["assessment_id"])
    assert (frozen.document_id, frozen.scope_nodes) == ("book", [0])
    # Phiên bản cây là `built_at` **đọc từ kho**, đúng tới mili giây (review B2,
    # `draft-from-document`).
    assert frozen.index_built_at.replace(tzinfo=UTC) == _BUILT
    # Đề theo sách mang tên tệp sách (ADR-31), không phải chuỗi nhãn bài của phạm vi.
    assert made["title"] == "Đề SGK Toán 6"


@pytest.mark.asyncio
async def test_a_book_without_chapters_named_is_refused_not_read_as_the_whole_book(stack) -> None:
    """Review B5 (`draft-from-document`): model nêu plan ngay mà bỏ qua mục lục sẽ gửi
    `topic_scope="chương 1"` không kèm `nodes`. Hiểu thiếu là *cả cuốn* thì đề rải câu khắp sách mà
    không ai từ chối."""
    maker, _ = stack
    brief = {"subject": "Toán", "grade": "6", "topic_scope": "chương 1"}

    made = await _run(maker, "create_draft", {**brief, "document_id": "book"}, PHASE_WORK)

    assert made["created"] is False
    assert "thiếu nodes" in made["reason"]
    async with maker() as session:
        assert await session.scalar(select(DraftBrief)) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("extra", "said"),
    [
        ({"document_id": "book", "nodes": "7"}, "không có mục [7]"),
        ({"document_id": "theirs", "nodes": "0"}, "không có tài liệu sẵn sàng"),
        ({"document_id": "book", "nodes": "chương 1"}, "các số node"),
    ],
)
async def test_a_scope_that_is_not_in_the_book_opens_nothing(stack, extra, said) -> None:
    maker, _ = stack
    brief = {"subject": "Toán", "grade": "6", "topic_scope": "chương 7"}

    made = await _run(maker, "create_draft", {**brief, **extra}, PHASE_WORK)

    assert made["created"] is False
    assert said in made["reason"]


@pytest.mark.asyncio
async def test_a_new_brief_replaces_the_book_scope_too(stack) -> None:
    """Review B1 (`draft-from-document`): `rebrief` không được giữ phạm vi tài liệu của brief cũ."""
    maker, _ = stack
    brief = {"subject": "Toán", "grade": "6", "topic_scope": "chương I"}
    made = await _run(
        maker, "create_draft", {**brief, "document_id": "book", "nodes": "0"}, PHASE_WORK
    )

    async with maker() as session:
        await rebrief(session, made["assessment_id"], topic_scope="tự do", question_count=3)
        frozen = await session.get(DraftBrief, made["assessment_id"])

    assert (frozen.document_id, frozen.scope_nodes, frozen.index_built_at) == ("", [], None)


def test_a_plan_without_a_book_is_still_a_whole_plan() -> None:
    """Tham số tài liệu là **tuỳ chọn**: một plan không sách không bị `vet_plan` từ chối."""
    asking = Asking(teacher_id="t", teacher_code="GV-001", full_name="Cô Lan")
    steps = (
        PlanStep(
            tool_name="create_draft",
            args={"subject": "Toán", "grade": "12", "topic_scope": "Hàm số"},
            title="Tạo đề trống",
        ),
    )

    assert vet_plan(steps, catalog_for(asking, PHASE_WORK, documents=True)) is None
    # Còn một tham số bắt buộc thì vẫn bắt buộc.
    short = (PlanStep(tool_name="create_draft", args={"subject": "Toán"}, title="Tạo đề"),)
    assert vet_plan(short, catalog_for(asking, PHASE_WORK, documents=True)) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scope", "nodes"),
    [
        ("Chương I. TẬP HỢP CÁC SỐ TỰ NHIÊN (tr. 3–5)", "0"),
        ("chương i. tập hợp các số tự nhiên", "0"),
        ("Bài 1. Tập hợp; Bài 2. Cách ghi số tự nhiên", "1,2"),
        ("chương 1", None),
        ("Bài 1. Tập hợp; chương 9", None),
    ],
)
async def test_a_forgotten_book_is_filled_only_from_labels_be_wrote(stack, scope, nodes) -> None:
    """gpt-4o-mini quên `document_id`/`nodes` ~1/5 lượt (đo 12/10/2026). BE điền `document_id` của
    cuốn đang gắn, và `nodes` **chỉ** khi `topic_scope` đúng là nhãn BE đã dựng -- không đoán."""
    steps = (
        PlanStep(
            tool_name="create_draft",
            args={"subject": "Toán", "grade": "6", "topic_scope": scope},
            title="Tạo đề trống",
        ),
        PlanStep(tool_name="start_drafting", args={"question_count": "10"}, title="Soạn câu"),
    )

    filled = await bind_book(steps, "book")

    assert filled[0].args["document_id"] == "book"
    assert filled[0].args.get("nodes") == nodes
    assert filled[1] == steps[1]


@pytest.mark.asyncio
async def test_nodes_the_model_did_send_are_kept(stack) -> None:
    steps = (
        PlanStep(
            tool_name="create_draft",
            args={
                "topic_scope": "Chương I. TẬP HỢP CÁC SỐ TỰ NHIÊN",
                "nodes": "3",
                "document_id": "book",
            },
            title="Tạo đề trống",
        ),
    )

    assert (await bind_book(steps, "book"))[0].args["nodes"] == "3"


@pytest.mark.asyncio
async def test_two_units_with_one_name_are_told_apart_only_by_their_pages(stack) -> None:
    """Review B7 (`draft-from-document`): SGK có hai mục *"LUYỆN TẬP CHUNG"*. Tên trần trỏ tới hai
    mục thì không điền gì -- chọn cái đầu là đoán; nhãn đầy đủ (có khoảng trang) của nút bấm thì ra
    đúng một mục."""
    _, reader = stack
    header, nodes = reader.trees["book"]
    twins = [_node(4, "LUYỆN TẬP CHUNG", 0, 2, None), _node(5, "LUYỆN TẬP CHUNG", 0, 2, None)]
    reader.trees["book"] = (header, [*nodes, *twins])

    def asked(scope: str) -> tuple[PlanStep, ...]:
        return (PlanStep(tool_name="create_draft", args={"topic_scope": scope}, title="Tạo đề"),)

    bare = await bind_book(asked("LUYỆN TẬP CHUNG"), "book")
    second = await bind_book(asked("LUYỆN TẬP CHUNG (tr. 8–10)"), "book")

    assert "nodes" not in bare[0].args
    assert second[0].args["nodes"] == "5"


@pytest.mark.asyncio
async def test_a_step_that_chose_another_book_is_left_alone(stack) -> None:
    """Review B7 (`draft-from-document`): model chọn cuốn khác qua `list_documents` -- khớp nhãn
    trên cây của cuốn đang gắn là gắn nhầm sách."""
    steps = (
        PlanStep(
            tool_name="create_draft",
            args={"topic_scope": "Chương I. TẬP HỢP CÁC SỐ TỰ NHIÊN", "document_id": "other"},
            title="Tạo đề",
        ),
    )

    assert (await bind_book(steps, "book")) == steps


@pytest.mark.asyncio
async def test_an_empty_book_id_is_filled_not_kept(stack) -> None:
    """Review B7 (`draft-from-document`): `""` qua `vet_plan` (chỉ kiểm có mặt) rồi thành đề không
    sách."""
    steps = (
        PlanStep(
            tool_name="create_draft",
            args={"topic_scope": "Chương I. TẬP HỢP CÁC SỐ TỰ NHIÊN", "document_id": ""},
            title="Tạo đề",
        ),
    )

    filled = await bind_book(steps, "book")

    assert filled[0].args["document_id"] == "book"
    assert filled[0].args["nodes"] == "0"


def test_a_numbering_that_carries_its_own_dot_gets_no_second_one() -> None:
    """Review B7 (`draft-from-document`): `numbering` kiểu *"1."*, *"I."* đã có dấu chấm -- không ra
    *"1.. MÔ TẢ"*."""
    from be.teacher_tools import node_label

    assert node_label(_node(2, "MÔ TẢ TẬP HỢP", 1, 3, "1.")) == "1. MÔ TẢ TẬP HỢP (tr. 5–7)"
    assert node_label(_node(1, "Tập hợp", 0, 2, "Bài 1")) == "Bài 1. Tập hợp (tr. 4–6)"
