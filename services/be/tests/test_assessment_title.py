"""Tên đề kiểm tra (ADR-31): tối đa 60 ký tự, đề sách mang tên tệp, giáo viên đổi được.

Ba thứ được canh: tên hệ thống đặt (hàm thuần `be.titles`), route đổi tên với đủ các lời từ chối, và
lượt đọc lại một đoạn chat -- thẻ cũ phải mang tên **hiện tại**, không phải tên lúc tạo.
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
from be.db import bind_sessions
from be.seed import seed_if_empty
from be.teacher_chat import router as chat_router
from be.teacher_routes import router as teacher_router
from be.titles import MOST_TITLE, clipped, default_title, tidy
from schema.ddl import prepare_schema
from schema.models import (
    Assessment,
    AssessmentState,
    Teacher,
    TeacherConversation,
    TeacherTurn,
)

TEACHER = {"X-Actor": "teacher:GV-001"}
STRANGER = {"X-Actor": "teacher:GV-002"}


# ------------------------------------------------------------------ tên hệ thống đặt


def test_a_book_draft_is_named_after_the_book_file() -> None:
    assert default_title(
        "Bài 1. TẬP HỢP (tr. 5–9), CÁCH GHI SỐ TỰ NHIÊN (tr. 9–13)", "SGK 6.pdf"
    ) == ("Đề SGK 6")


def test_a_bookless_draft_keeps_its_scope_without_page_numbers() -> None:
    assert default_title("Bài 1. TẬP HỢP (tr. 5–9)") == "Đề Bài 1. TẬP HỢP"


@pytest.mark.parametrize("length", [MOST_TITLE, MOST_TITLE + 1, 200])
def test_a_long_name_is_cut_at_a_word_and_never_passes_the_cap(length: int) -> None:
    words = ("tỉ lệ thức và dãy tỉ số bằng nhau " * 10)[:length]

    named = clipped(words)

    assert len(named) <= MOST_TITLE
    if len(words.strip()) > MOST_TITLE:
        assert named.endswith("…")
        assert words.startswith(named[:-1])


def test_a_word_that_fits_is_kept_when_the_cut_falls_on_a_space() -> None:
    """Review pha 6: ký tự thứ 60 là khoảng trắng thì 59 ký tự đầu đã trọn từ."""
    head = "a" * 54 + " bcde"
    assert len(head) == MOST_TITLE - 1

    assert clipped(head + " fgh ijk") == head + "…"


def test_quotes_are_dropped_only_when_they_wrap_the_whole_name() -> None:
    assert clipped('"Đề tỉ lệ thức"') == "Đề tỉ lệ thức"
    assert clipped('Ôn tập chương "Số nguyên"') == 'Ôn tập chương "Số nguyên"'


def test_tidying_a_teacher_name_only_folds_whitespace() -> None:
    """Review pha 6: chữ giáo viên gõ chỉ giáo viên sửa -- dấu ngoặc ở cuối là của tên."""
    assert tidy('  Ôn tập   chương "Số nguyên"\n') == 'Ôn tập chương "Số nguyên"'


# ------------------------------------------------------------------ route đổi tên + đọc lại


@pytest_asyncio.fixture
async def stack():
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as session:
        await seed_if_empty(session)
        session.add(Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002"))
        mine = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        now = datetime.now(UTC)
        for paper_id, state in (
            ("open", AssessmentState.HAS_QUESTIONS),
            ("signed", AssessmentState.APPROVED),
        ):
            session.add(
                Assessment(
                    id=paper_id,
                    teacher_id=mine.id,
                    title="Đề Bài 1. TẬP HỢP (tr. 5–9), CÁCH GHI SỐ TỰ NHIÊN (tr. 9–13)",
                    subject="Toán",
                    grade="6",
                    state=state,
                    created_at=now,
                )
            )
        thread = TeacherConversation(teacher_id=mine.id, started_at=now, title="Soạn đề")
        session.add(thread)
        await session.flush()
        for sequence, kind, tool_result in (
            (0, "teacher", {}),
            (1, "tool_call", {}),
            (2, "tool_result", {"created": True, "assessment_id": "open", "title": "Tên cũ"}),
        ):
            session.add(
                TeacherTurn(
                    conversation_id=thread.id,
                    sequence=sequence,
                    kind=kind,
                    text="soạn đề" if kind == "teacher" else "",
                    tool_name="" if kind == "teacher" else "create_draft",
                    tool_result=tool_result,
                    created_at=now,
                )
            )
        await session.commit()
        conversation_id = thread.id

    app = FastAPI()
    app.include_router(teacher_router)
    app.include_router(chat_router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker, conversation_id

    await engine.dispose()
    db_module._SESSION_MAKER = None


@pytest.mark.asyncio
async def test_a_teacher_renames_an_open_draft_and_old_cards_follow(stack) -> None:
    """ADR-31: thẻ cũ trong đoạn chat đọc tên hiện tại -- một đề hai tên trên cùng màn hình là
    hai đề."""
    http, _, conversation_id = stack

    renamed = await http.patch(
        "/api/teacher/assessments/open", json={"title": "  Kiểm tra   Chương I  "}, headers=TEACHER
    )
    read = await http.get(f"/api/teacher/chat?conversation_id={conversation_id}", headers=TEACHER)

    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Kiểm tra Chương I"
    cards = [turn for turn in read.json()["turns"] if turn["kind"] == "tool_result"]
    assert cards[0]["tool_result"]["title"] == "Kiểm tra Chương I"


@pytest.mark.parametrize(
    ("paper", "title", "who", "status"),
    [
        ("open", "x" * (MOST_TITLE + 1), TEACHER, 422),
        ("open", "   ", TEACHER, 400),
        ("signed", "Tên mới", TEACHER, 409),
        ("open", "Tên mới", STRANGER, 404),
        ("missing", "Tên mới", TEACHER, 404),
    ],
)
@pytest.mark.asyncio
async def test_a_rename_is_refused_rather_than_cut(stack, paper, title, who, status) -> None:
    """Chữ giáo viên gõ chỉ giáo viên sửa: quá trần là từ chối, không cắt; đề đã duyệt thì khoá
    (ADR-01); đề của người khác như không có (ADR-22)."""
    http, maker, _ = stack

    answer = await http.patch(
        f"/api/teacher/assessments/{paper}", json={"title": title}, headers=who
    )

    assert answer.status_code == status
    async with maker() as session:
        kept = await session.get(Assessment, "open")
    assert kept.title.startswith("Đề Bài 1.")


@pytest.mark.asyncio
async def test_the_history_sent_to_the_agent_carries_the_current_name(stack) -> None:
    """Kriky gọi đề đúng tên giáo viên vừa đặt, không tên lúc tạo."""
    http, maker, conversation_id = stack
    await http.patch("/api/teacher/assessments/open", json={"title": "Đề mới"}, headers=TEACHER)

    async with maker() as session:
        stored = await teacher_chat._stored_turns(session, conversation_id)
        records = teacher_chat._as_records(
            stored, await teacher_chat._current_titles(session, stored)
        )

    assert records[-1].tool_result["title"] == "Đề mới"
