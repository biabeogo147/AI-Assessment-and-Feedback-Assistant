"""Đề nháp trống: xoá được, và một đoạn chat không mở đề trống thứ hai (ADR-33).

Việc 15 của plan `wave-3-draft-panel`. Ba luật được canh ở đây:

- **Chỉ đề trống mới xoá được**, và xoá là xoá cứng: đề có câu, có ô đang soạn, đã duyệt, hay của
  người khác đều bị từ chối.
- **Lượt chat cũ biết đề đã xoá** (`entity_gone`), để thẻ *Đã tạo đề* cũ không mở một đề không còn.
- **`create_draft` dùng lại đề trống của chính đoạn chat ấy**; đoạn khác thì vẫn mở đề mới.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.db import bind_sessions
from be.identity import Asking
from be.seed import seed_if_empty
from be.teacher_chat import _current_titles, _visible
from be.teacher_chat import router as chat_router
from be.teacher_routes import router as assessment_router
from be.teacher_tools import PHASE_WORK, execute
from schema.ddl import prepare_schema
from schema.models import (
    Assessment,
    AssessmentState,
    DraftBrief,
    DraftItem,
    Question,
    Teacher,
    TeacherConversation,
    TeacherTurn,
)

TEACHER = {"X-Actor": "teacher:GV-001"}
STRANGER = {"X-Actor": "teacher:GV-002"}

_BRIEF = {"subject": "Toán", "grade": "12", "topic_scope": "chương Hàm số", "title": "Đề 15 phút"}


@pytest_asyncio.fixture
async def stack():
    """Một app có hai giáo viên trên sqlite trong bộ nhớ."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        session.add(Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002"))
        await session.commit()

    app = FastAPI()
    app.include_router(assessment_router)
    app.include_router(chat_router)
    app.state.queue_pool = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker

    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _asking(session) -> Asking:
    teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
    return Asking.of(teacher)


async def _thread(session, asking: Asking) -> str:
    """Một đoạn chat trống của giáo viên GV-001."""
    thread = TeacherConversation(teacher_id=asking.teacher_id, started_at=datetime.now(UTC))
    session.add(thread)
    await session.commit()
    return thread.id


async def _created_in(session, thread: str, asking: Asking, args: dict = _BRIEF) -> dict:
    """Chạy `create_draft` trong một đoạn chat, rồi ghi bước ấy lại như vòng lượt vẫn ghi."""
    result = await execute(
        session, asking, "create_draft", dict(args), phase=PHASE_WORK, conversation_id=thread
    )
    count = len(
        list(
            await session.scalars(select(TeacherTurn).where(TeacherTurn.conversation_id == thread))
        )
    )
    session.add(
        TeacherTurn(
            conversation_id=thread,
            sequence=count + 1,
            kind="tool_result",
            tool_name="create_draft",
            tool_result=result,
            entity_kind="assessment",
            entity_id=result["assessment_id"],
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()
    return result


# ------------------------------------------------------------------ xoá


@pytest.mark.asyncio
async def test_an_empty_draft_is_erased_for_good(stack) -> None:
    http, maker = stack
    async with maker() as session:
        asking = await _asking(session)
        made = await _created_in(session, await _thread(session, asking), asking)

    detail = (
        await http.get(f"/api/teacher/assessments/{made['assessment_id']}", headers=TEACHER)
    ).json()
    erased = await http.delete(f"/api/teacher/assessments/{made['assessment_id']}", headers=TEACHER)

    # BE nói panel có hiện link *Xoá đề* hay không; panel không tự suy.
    assert detail["erasable"] is True
    assert erased.status_code == 204
    async with maker() as session:
        assert await session.get(Assessment, made["assessment_id"]) is None
        assert await session.get(DraftBrief, made["assessment_id"]) is None


@pytest.mark.asyncio
async def test_only_an_empty_draft_can_be_erased(stack) -> None:
    """Đề có câu, có ô đang soạn, đã duyệt: 409 kèm lý do; của người khác: 404 (ADR-22)."""
    http, maker = stack
    async with maker() as session:
        asking = await _asking(session)
        thread = await _thread(session, asking)
        with_question = (await _created_in(session, thread, asking))["assessment_id"]
        session.add(
            Question(
                assessment_id=with_question,
                order_index=1,
                stem="Câu 1?",
                learning_objective="hàm số",
            )
        )
        drafting = (await _created_in(session, await _thread(session, asking), asking))[
            "assessment_id"
        ]
        # Brief xin một câu, như một đề đang soạn thật: `harvest` xoá ô vượt `question_count`.
        (await session.get(DraftBrief, drafting)).question_count = 1
        session.add(
            DraftItem(
                assessment_id=drafting,
                ordinal=1,
                job_id="j",
                status="pending",
                created_at=datetime.now(UTC),
            )
        )
        approved = (await _created_in(session, await _thread(session, asking), asking))[
            "assessment_id"
        ]
        (await session.get(Assessment, approved)).state = AssessmentState.APPROVED
        stranger = (await _created_in(session, await _thread(session, asking), asking))[
            "assessment_id"
        ]
        await session.commit()

    refused = {
        key: await http.delete(f"/api/teacher/assessments/{paper}", headers=TEACHER)
        for key, paper in [("question", with_question), ("slot", drafting), ("approved", approved)]
    }
    foreign = await http.delete(f"/api/teacher/assessments/{stranger}", headers=STRANGER)

    assert {key: one.status_code for key, one in refused.items()} == {
        "question": 409,
        "slot": 409,
        "approved": 409,
    }
    assert "đang soạn" in refused["slot"].json()["detail"]
    detail = (await http.get(f"/api/teacher/assessments/{drafting}", headers=TEACHER)).json()
    assert detail["erasable"] is False
    assert foreign.status_code == 404
    async with maker() as session:
        for paper in (with_question, drafting, approved, stranger):
            assert await session.get(Assessment, paper) is not None


@pytest.mark.asyncio
async def test_an_old_turn_knows_its_draft_was_erased(stack) -> None:
    """Đọc lại đoạn chat sau khi xoá: bước của đề đã xoá mang `entity_gone`, đề còn thì không."""
    http, maker = stack
    async with maker() as session:
        asking = await _asking(session)
        thread = await _thread(session, asking)
        gone = (await _created_in(session, thread, asking))["assessment_id"]
        kept = (await _created_in(session, await _thread(session, asking), asking, _BRIEF))[
            "assessment_id"
        ]
    await http.delete(f"/api/teacher/assessments/{gone}", headers=TEACHER)

    async with maker() as session:
        turns = list(await session.scalars(select(TeacherTurn).order_by(TeacherTurn.created_at)))
        titles = await _current_titles(session, turns)
        shown = {turn.entity_id: _visible(turn, titles).entity_gone for turn in turns}

    assert shown == {gone: True, kept: False}


# ------------------------------------------------------------------ dùng lại


@pytest.mark.asyncio
async def test_a_second_create_in_the_same_chat_reuses_its_empty_draft(stack) -> None:
    _http, maker = stack
    async with maker() as session:
        asking = await _asking(session)
        thread = await _thread(session, asking)
        first = await _created_in(session, thread, asking)
        second = await _created_in(
            session, thread, asking, {**_BRIEF, "topic_scope": "chương Đạo hàm", "title": "Đề mới"}
        )
        brief = await session.get(DraftBrief, first["assessment_id"])
        drafts = list(await session.scalars(select(Assessment.id)))

    assert second["assessment_id"] == first["assessment_id"]
    assert second["reused"] is True
    assert second["title"] == "Đề mới"
    assert brief.topic_scope == "chương Đạo hàm"
    assert drafts.count(first["assessment_id"]) == 1


@pytest.mark.asyncio
async def test_another_chat_or_a_draft_with_questions_gets_a_new_draft(stack) -> None:
    """Đoạn chat khác thì đề mới; đề của đoạn này đã có câu thì cũng đề mới."""
    _http, maker = stack
    async with maker() as session:
        asking = await _asking(session)
        thread = await _thread(session, asking)
        first = (await _created_in(session, thread, asking))["assessment_id"]
        elsewhere = await _created_in(session, await _thread(session, asking), asking)
        session.add(
            Question(assessment_id=first, order_index=1, stem="Câu 1?", learning_objective="x")
        )
        (await session.get(Assessment, first)).state = AssessmentState.HAS_QUESTIONS
        await session.commit()
        again = await _created_in(session, thread, asking)

    assert elsewhere["assessment_id"] != first
    assert "reused" not in elsewhere
    assert again["assessment_id"] not in (first, elsewhere["assessment_id"])


@pytest.mark.asyncio
async def test_an_empty_draft_whose_every_job_failed_can_be_erased(stack) -> None:
    """Mọi job đều hỏng: đề vẫn trống, ô hỏng không chặn xoá, và đi cùng đề (review pha 4)."""
    http, maker = stack
    async with maker() as session:
        asking = await _asking(session)
        paper = (await _created_in(session, await _thread(session, asking), asking))[
            "assessment_id"
        ]
        session.add(
            DraftItem(
                assessment_id=paper,
                ordinal=1,
                job_id="j",
                status="failed",
                attempts=3,
                last_fault="model không soạn được câu này",
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

    detail = (await http.get(f"/api/teacher/assessments/{paper}", headers=TEACHER)).json()
    erased = await http.delete(f"/api/teacher/assessments/{paper}", headers=TEACHER)

    assert detail["erasable"] is True
    assert erased.status_code == 204
    async with maker() as session:
        left = list(
            await session.scalars(select(DraftItem).where(DraftItem.assessment_id == paper))
        )
    assert left == []


@pytest.mark.asyncio
async def test_reusing_an_empty_draft_drops_its_old_outline_and_failed_slots(stack) -> None:
    """Dùng lại thì lần soạn sau bắt đầu từ ô 1, theo brief mới: không mang dàn ý, ô hỏng cũ."""
    _http, maker = stack
    async with maker() as session:
        asking = await _asking(session)
        thread = await _thread(session, asking)
        paper = (await _created_in(session, thread, asking))["assessment_id"]
        brief = await session.get(DraftBrief, paper)
        brief.outline = [{"knowledge": "cũ", "questions": 1, "version": 1}]
        before = brief.version
        session.add(
            DraftItem(
                assessment_id=paper,
                ordinal=1,
                job_id="j",
                status="failed",
                attempts=3,
                last_fault="model không soạn được câu này",
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

        again = await _created_in(session, thread, asking)
        brief = await session.get(DraftBrief, paper, populate_existing=True)
        slots = list(
            await session.scalars(select(DraftItem).where(DraftItem.assessment_id == paper))
        )

    assert again["assessment_id"] == paper
    assert brief.outline == []
    assert brief.version == before + 1
    assert slots == []


@pytest.mark.asyncio
async def test_with_two_empty_drafts_the_newest_is_reused(stack) -> None:
    _http, maker = stack
    async with maker() as session:
        asking = await _asking(session)
        thread = await _thread(session, asking)
        older = (await _created_in(session, thread, asking))["assessment_id"]
        # Một đề trống thứ hai trong cùng đoạn, mới hơn (dữ liệu từ trước khi có luật dùng lại).
        newer = Assessment(
            teacher_id=asking.teacher_id,
            title="Đề thứ hai",
            subject="Toán",
            grade="12",
            state=AssessmentState.EMPTY,
            created_at=datetime.now(UTC),
        )
        session.add(newer)
        await session.flush()
        session.add(
            TeacherTurn(
                conversation_id=thread,
                sequence=99,
                kind="tool_result",
                tool_name="create_draft",
                tool_result={"created": True, "assessment_id": newer.id, "title": newer.title},
                entity_kind="assessment",
                entity_id=newer.id,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

        again = await _created_in(session, thread, asking)

    assert again["assessment_id"] == newer.id != older


@pytest.mark.asyncio
async def test_the_chat_read_route_marks_the_erased_draft(stack) -> None:
    """`entity_gone` đi tới FE qua đúng route đọc đoạn chat, không chỉ qua hàm."""
    http, maker = stack
    async with maker() as session:
        asking = await _asking(session)
        thread = await _thread(session, asking)
        paper = (await _created_in(session, thread, asking))["assessment_id"]
    await http.delete(f"/api/teacher/assessments/{paper}", headers=TEACHER)

    read = await http.get(f"/api/teacher/chat?conversation_id={thread}", headers=TEACHER)

    assert read.status_code == 200
    turns = [one for one in read.json()["turns"] if one["tool_name"] == "create_draft"]
    assert [one["entity_gone"] for one in turns] == [True]
