"""Tool đọc `last_plan`: kể gọn plan gần nhất của một đoạn chat (ADR-25, hậu ký 22/10/2026).

Lượt kể lại đọc nó thay cho danh sách kết quả mà job `report_plan` cũ nhận trong payload. Nên nó
phải nói đúng điều pha 2 đã nói trên màn hình: cùng trạng thái từng bước, cùng dòng kết quả, và tiến
độ đếm lại từ database lúc hỏi.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.db import bind_sessions
from be.identity import Asking
from be.plan_outcomes import COULD_NOT_CARRY_OVER, plan_summary
from be.seed import seed_if_empty
from be.teacher_tools import PHASE_PLAN, execute
from schema.ddl import prepare_schema
from schema.models import (
    Assessment,
    DraftBrief,
    Question,
    Teacher,
    TeacherConversation,
    TeacherTurn,
)


@pytest_asyncio.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)
    made = async_sessionmaker(engine, expire_on_commit=False)
    async with made() as session:
        await seed_if_empty(session)
    yield made
    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _thread(session, *turns: dict) -> str:
    teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
    thread = TeacherConversation(teacher_id=teacher.id, started_at=datetime.now(UTC))
    session.add(thread)
    await session.flush()
    for sequence, turn in enumerate(turns, start=1):
        session.add(
            TeacherTurn(
                conversation_id=thread.id,
                sequence=sequence,
                created_at=datetime.now(UTC),
                **turn,
            )
        )
    await session.commit()
    return thread.id


async def _paper(session, written: int, asked_for: int) -> str:
    teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
    paper = Assessment(
        teacher_id=teacher.id, title="Đề", subject="Toán", grade="6", created_at=datetime.now(UTC)
    )
    session.add(paper)
    await session.flush()
    session.add(
        DraftBrief(
            assessment_id=paper.id,
            topic_scope="chương 1",
            question_count=asked_for,
            created_at=datetime.now(UTC),
        )
    )
    for order in range(1, written + 1):
        session.add(
            Question(
                assessment_id=paper.id,
                order_index=order,
                stem=f"Câu {order}?",
                learning_objective="x",
            )
        )
    await session.commit()
    return paper.id


def _plan(*titles: str) -> dict:
    return {"kind": "plan", "tool_result": {"steps": list(titles), "total": len(titles)}}


def _ran(tool: str, result: dict) -> list[dict]:
    return [
        {"kind": "tool_call", "tool_name": tool},
        {"kind": "tool_result", "tool_name": tool, "tool_result": result},
    ]


@pytest.mark.asyncio
async def test_a_thread_with_no_plan_says_so(maker) -> None:
    async with maker() as session:
        thread = await _thread(session, {"kind": "teacher", "text": "chào"})
        summary = await plan_summary(session, thread)
    assert summary["found"] is False
    assert summary["reason"]


@pytest.mark.asyncio
async def test_a_plan_that_ran_tells_each_step_and_counts_again(maker) -> None:
    async with maker() as session:
        paper = await _paper(session, written=2, asked_for=3)
        thread = await _thread(
            session,
            {"kind": "teacher", "text": "soạn 3 câu"},
            _plan("Tạo đề trống", "Soạn câu hỏi"),
            *_ran(
                "create_draft",
                {"created": True, "assessment_id": paper, "title": "Đề", "question_count": 3},
            ),
            *_ran(
                "start_drafting",
                {
                    "started": True,
                    "assessment_id": paper,
                    "written": 1,
                    "asked_for": 3,
                    "still_drafting": 2,
                },
            ),
        )
        summary = await plan_summary(session, thread)

    assert summary["found"] is True
    assert summary["steps"] == [
        {"title": "Tạo đề trống", "status": "xong", "detail": '"Đề", cần 3 câu'},
        # Dòng của bước là con số **lúc chạy**, như trên màn hình lúc ấy.
        {
            "title": "Soạn câu hỏi",
            "status": "xong",
            "detail": "đã soạn 1/3 câu, còn 2 câu đang chạy",
        },
    ]
    # Tiến độ là con số **lúc hỏi**: lượt kể lại có thể tới khi job còn chạy.
    assert summary["progress"] == {"written": 2, "asked_for": 3, "still_drafting": 0}


@pytest.mark.asyncio
async def test_a_step_that_broke_stops_the_ones_after_it(maker) -> None:
    async with maker() as session:
        thread = await _thread(
            session,
            {"kind": "teacher", "text": "soạn đề"},
            _plan("Tạo đề trống", "Soạn câu hỏi"),
            *_ran("create_draft", {"created": False, "missing": ["grade"], "reason": "thiếu khối"}),
            # Một lần đọc sau đó không phải bước 2 của plan.
            *_ran("list_class", {"candidates": [], "more": 0}),
        )
        summary = await plan_summary(session, thread)

    assert summary["steps"] == [
        {"title": "Tạo đề trống", "status": "hỏng", "detail": "thiếu thông tin để làm bước này"},
        {"title": "Soạn câu hỏi", "status": "không chạy", "detail": ""},
    ]
    assert "progress" not in summary


@pytest.mark.asyncio
async def test_a_step_that_could_not_carry_over_reads_as_broken(maker) -> None:
    # Hôm nay pha 2 ghi cả bước này (`teacher_chat._go`); trước 22/10/2026 nó không để lại dòng nào.
    async with maker() as session:
        thread = await _thread(
            session,
            {"kind": "teacher", "text": "soạn đề"},
            _plan("Soạn câu hỏi"),
            *_ran(
                "start_drafting",
                {"error": "thiếu dữ liệu", "said": COULD_NOT_CARRY_OVER, "carried": False},
            ),
        )
        summary = await plan_summary(session, thread)

    assert summary["steps"] == [
        {"title": "Soạn câu hỏi", "status": "hỏng", "detail": COULD_NOT_CARRY_OVER}
    ]


@pytest.mark.asyncio
async def test_only_the_latest_plan_and_its_own_steps_are_told(maker) -> None:
    async with maker() as session:
        thread = await _thread(
            session,
            {"kind": "teacher", "text": "lượt 1"},
            _plan("Bước cũ"),
            *_ran("create_draft", {"created": True, "title": "Đề cũ"}),
            {"kind": "teacher", "text": "lượt 2"},
            _plan("Tạo đề trống"),
            *_ran("create_draft", {"created": True, "title": "Đề mới"}),
            {"kind": "teacher", "text": "lượt 3, chưa có plan"},
            *_ran("list_class", {"candidates": [], "more": 0}),
        )
        summary = await plan_summary(session, thread)

    assert summary["steps"] == [{"title": "Tạo đề trống", "status": "xong", "detail": '"Đề mới"'}]


@pytest.mark.asyncio
async def test_the_tool_reads_the_thread_of_the_turn_that_asks(maker) -> None:
    async with maker() as session:
        thread = await _thread(
            session,
            {"kind": "teacher", "text": "soạn đề"},
            _plan("Tạo đề trống"),
            *_ran("create_draft", {"created": True, "title": "Đề"}),
        )
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        asking = Asking.of(teacher)
        told = await execute(
            session, asking, "last_plan", {}, phase=PHASE_PLAN, conversation_id=thread
        )
        alone = await execute(session, asking, "last_plan", {}, phase=PHASE_PLAN)

    assert told["found"] is True
    assert [one["title"] for one in told["steps"]] == ["Tạo đề trống"]
    assert alone["found"] is False


@pytest.mark.asyncio
async def test_a_panel_button_in_the_thread_is_not_a_step_of_the_plan(maker) -> None:
    """Review `report-into-propose` (V3): nút Duyệt của panel ghi `teacher.approve` vào đoạn chat mà
    không có lời giáo viên đi trước; nó không được thành bước 2 của plan."""
    async with maker() as session:
        thread = await _thread(
            session,
            {"kind": "teacher", "text": "soạn đề"},
            _plan("Tạo đề trống", "Soạn câu hỏi"),
            *_ran("create_draft", {"created": True, "title": "Đề"}),
            {
                "kind": "tool_result",
                "tool_name": "teacher.approve",
                "tool_result": {"approved": True},
            },
        )
        summary = await plan_summary(session, thread)

    assert [one["status"] for one in summary["steps"]] == ["xong", "không chạy"]
