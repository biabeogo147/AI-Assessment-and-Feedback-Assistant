"""Bảng theo dõi: hàng đợi review và điểm gộp theo lớp (việc 19, 21, plan `dashboard-review-queue`).

Bốn luật người dùng chốt 18/10/2026, mỗi luật một nhóm test:

- **Báo cáo gom theo đề**, và *đã xem* theo đề: báo cáo đến sau đưa đề vào lại.
- **Tỉ lệ sai cao** chỉ khi đề đã hết giai đoạn 2 ở mọi lớp, trên 20 bài, ≥ 70% sai lần đầu; ở lại
  tới khi giáo viên đánh dấu đã xem.
- **Điểm gộp** chỉ tính đề đã hết hạn chữa ở lớp ấy, mỗi bài quy về thang 10.
- **Của người khác đọc như không có** (ADR-22).
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.db import bind_sessions
from be.seed import seed_if_empty
from be.teacher_board import router as board_router
from schema.ddl import prepare_schema
from schema.models import (
    Answer,
    AnswerOption,
    Assessment,
    Attempt,
    BankQuestion,
    ChatMessage,
    Publication,
    Question,
    QuestionOutcome,
    Report,
    SchoolClass,
    Student,
    Teacher,
)

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
    app.include_router(board_router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker
    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _seeded(maker):
    async with maker() as session:
        school_class = await session.scalar(select(SchoolClass))
        paper = await session.scalar(select(Assessment))
        questions = list(
            await session.scalars(
                select(Question)
                .where(Question.assessment_id == paper.id)
                .order_by(Question.order_index)
            )
        )
        return school_class, paper, questions


async def _students(maker, school_class, count: int) -> list[Student]:
    """`count` học sinh mới trong lớp."""
    async with maker() as session:
        made = [
            Student(
                class_id=school_class.id, full_name=f"Học sinh {n:02d}", student_code=f"T{n:03d}"
            )
            for n in range(count)
        ]
        session.add_all(made)
        await session.commit()
        return made


async def _end_phase_two(maker, paper) -> None:
    """Đưa mọi lần phát hành của đề qua hạn chữa."""
    async with maker() as session:
        for one in await session.scalars(
            select(Publication).where(Publication.assessment_id == paper.id)
        ):
            now = datetime.now(UTC)
            one.opens_at = now - timedelta(days=2)
            one.closes_at = now - timedelta(days=2) + timedelta(minutes=15)
            one.remediation_deadline = now - timedelta(minutes=1)
        await session.commit()


async def _hand_in(maker, paper, student, questions, right: list[bool]) -> str:
    """Một bài đã nộp: câu `right[i]` đúng ngay lần đầu, câu còn lại sai và chọn phương án nhiễu."""
    async with maker() as session:
        now = datetime.now(UTC)
        attempt = Attempt(
            assessment_id=paper.id,
            student_id=student.id,
            class_id=student.class_id,
            started_at=now - timedelta(minutes=12),
            ends_at=now + timedelta(minutes=3),
            submitted_at=now,
        )
        session.add(attempt)
        await session.flush()
        for question, ok in zip(questions, right, strict=True):
            option = await session.scalar(
                select(AnswerOption)
                .where(AnswerOption.question_id == question.id, AnswerOption.is_correct == ok)
                .order_by(AnswerOption.label)
            )
            session.add(
                Answer(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    option_id=option.id,
                    saved_at=now,
                )
            )
            session.add(
                QuestionOutcome(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    mark=1.0 if ok else 0.0,
                    reason="đúng-ngay" if ok else "chưa-chữa",
                    closed=ok,
                )
            )
        await session.commit()
        return attempt.id


async def _report(maker, attempt_id: str, note: str = "", minutes_ago: int = 0) -> str:
    async with maker() as session:
        row = Report(
            attempt_id=attempt_id,
            note=note or None,
            created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        )
        session.add(row)
        await session.commit()
        return row.id


# ------------------------------------------------------------------ báo cáo, gom theo đề


@pytest.mark.asyncio
async def test_reports_queue_one_row_per_paper_and_seen_clears_it(stack) -> None:
    """Hai báo cáo của một đề là một dòng; đã xem thì dòng đi; báo cáo mới thì dòng về."""
    http, maker = stack
    school_class, paper, questions = await _seeded(maker)
    first, second = await _students(maker, school_class, 2)
    right = [True] * len(questions)
    wrong_two = [False, False] + [True] * (len(questions) - 2)
    a1 = await _hand_in(maker, paper, first, questions, wrong_two)
    a2 = await _hand_in(maker, paper, second, questions, right)
    r1 = await _report(maker, a1, "Em không hiểu cách 2.", minutes_ago=5)
    r2 = await _report(maker, a2)

    queue = (await http.get("/api/teacher/board", headers=TEACHER)).json()["queue"]

    (row,) = [one for one in queue if one["kind"] == "reports"]
    assert row["assessment_id"] == paper.id and row["title"] == paper.title
    assert row["figure"] == "2 lượt báo cáo"
    # Hàng đợi không ghi lớp (người dùng chốt ở buổi review Figma lần 1).
    assert row["meta"] == "2 học sinh"

    detail = (await http.get(f"/api/teacher/board/reports/{paper.id}", headers=TEACHER)).json()
    assert [one["student"] for one in detail["reports"]] == ["Học sinh 01", "Học sinh 00"]
    assert detail["reports"][1]["note"] == "Em không hiểu cách 2."
    assert detail["reports"][1]["wrong"] == [1, 2]
    assert [(one["order"], one["wrong_by"]) for one in detail["questions"]] == [(1, 1), (2, 1)]
    # Đề seed đã duyệt nên mỗi câu có bản ngân hàng: nút *Chỉnh sửa* có chỗ để mở.
    assert all(one["bank_id"] for one in detail["questions"])
    assert detail["reporters"] == 2 and detail["classes"] == ["12A"]

    seen = await http.post(
        f"/api/teacher/board/reports/{paper.id}/seen",
        json={"report_ids": [r1, r2]},
        headers=TEACHER,
    )
    assert seen.status_code == 204
    queue = (await http.get("/api/teacher/board", headers=TEACHER)).json()["queue"]
    assert not [one for one in queue if one["kind"] == "reports"]

    await _report(maker, a2, "Lại khó hiểu.")
    queue = (await http.get("/api/teacher/board", headers=TEACHER)).json()["queue"]
    (row,) = [one for one in queue if one["kind"] == "reports"]
    assert row["figure"] == "1 lượt báo cáo"


@pytest.mark.asyncio
async def test_the_chat_of_a_report_is_the_owners(stack) -> None:
    """Hộp đọc đoạn chat: đúng thứ tự đã nói; người khác 404."""
    http, maker = stack
    school_class, paper, questions = await _seeded(maker)
    (one,) = await _students(maker, school_class, 1)
    attempt_id = await _hand_in(maker, paper, one, questions, [False] * len(questions))
    async with maker() as session:
        now = datetime.now(UTC)
        session.add_all(
            [
                ChatMessage(
                    attempt_id=attempt_id,
                    sequence=2,
                    role="student",
                    text="Em chưa hiểu.",
                    created_at=now,
                ),
                ChatMessage(
                    attempt_id=attempt_id,
                    sequence=1,
                    role="assistant",
                    text="Chào em.",
                    created_at=now,
                ),
            ]
        )
        await session.commit()
    report_id = await _report(maker, attempt_id)

    body = (await http.get(f"/api/teacher/board/chat/{report_id}", headers=TEACHER)).json()

    assert [(m["role"], m["text"]) for m in body["messages"]] == [
        ("assistant", "Chào em."),
        ("student", "Em chưa hiểu."),
    ]
    assert (body["student"], body["class_name"], body["title"]) == (
        "Học sinh 00",
        "12A",
        paper.title,
    )
    assert (
        await http.get(f"/api/teacher/board/chat/{report_id}", headers=STRANGER)
    ).status_code == 404
    assert (
        await http.get(f"/api/teacher/board/reports/{paper.id}", headers=STRANGER)
    ).status_code == 404
    assert (
        await http.post(
            f"/api/teacher/board/reports/{paper.id}/seen",
            json={"report_ids": [report_id]},
            headers=STRANGER,
        )
    ).status_code == 404


# ------------------------------------------------------------------ tỉ lệ sai cao


async def _class_of_21(maker, wrong_on_first: int):
    """21 bài; `wrong_on_first` bài sai câu 1 ở lần đầu, còn lại đúng hết."""
    school_class, paper, questions = await _seeded(maker)
    students = await _students(maker, school_class, 21)
    for index, student in enumerate(students):
        first_ok = index >= wrong_on_first
        await _hand_in(maker, paper, student, questions, [first_ok] + [True] * (len(questions) - 1))
    return paper, questions


@pytest.mark.asyncio
async def test_a_high_wrong_rate_waits_for_the_end_of_phase_two(stack) -> None:
    """15/21 sai (71%): đang chạy thì chưa vào; hết giai đoạn 2 thì vào; đã xem thì đi mãi."""
    http, maker = stack
    paper, questions = await _class_of_21(maker, 15)

    queue = (await http.get("/api/teacher/board", headers=TEACHER)).json()["queue"]
    assert not [one for one in queue if one["kind"] == "wrong_rate"]

    await _end_phase_two(maker, paper)
    queue = (await http.get("/api/teacher/board", headers=TEACHER)).json()["queue"]
    (row,) = [one for one in queue if one["kind"] == "wrong_rate"]
    assert row["question_id"] == questions[0].id
    assert row["title"] == f"Câu 1 · {questions[0].stem}"
    assert row["figure"] == "71% bài sai"

    detail = (
        await http.get(f"/api/teacher/board/questions/{questions[0].id}", headers=TEACHER)
    ).json()
    assert (detail["submitted"], detail["wrong_percent"], detail["seen"]) == (21, 71, False)
    shares = {one["label"]: one["percent"] for one in detail["options"]}
    right = next(one["label"] for one in detail["options"] if one["is_correct"])
    assert shares[right] == 29 and sum(shares.values()) == 100
    assert detail["bank_id"] and detail["classes"] == ["12A"]

    assert (
        await http.post(f"/api/teacher/board/questions/{questions[0].id}/seen", headers=TEACHER)
    ).status_code == 204
    queue = (await http.get("/api/teacher/board", headers=TEACHER)).json()["queue"]
    assert not [one for one in queue if one["kind"] == "wrong_rate"]


@pytest.mark.asyncio
async def test_a_wrong_rate_needs_more_than_twenty_papers_and_seventy_percent(stack) -> None:
    """14/21 sai (67%) thì không vào."""
    http, maker = stack
    paper, _ = await _class_of_21(maker, 14)
    await _end_phase_two(maker, paper)
    queue = (await http.get("/api/teacher/board", headers=TEACHER)).json()["queue"]
    assert not [one for one in queue if one["kind"] == "wrong_rate"]


@pytest.mark.asyncio
async def test_twenty_papers_are_not_enough(stack) -> None:
    """20 bài đều sai cũng không vào: chưa *trên* 20."""
    http, maker = stack
    school_class, paper, questions = await _seeded(maker)
    for student in await _students(maker, school_class, 20):
        await _hand_in(maker, paper, student, questions, [False] * len(questions))
    await _end_phase_two(maker, paper)
    queue = (await http.get("/api/teacher/board", headers=TEACHER)).json()["queue"]
    assert not [one for one in queue if one["kind"] == "wrong_rate"]


@pytest.mark.asyncio
async def test_a_paper_still_running_in_one_class_keeps_its_rates_out(stack) -> None:
    """Đề phát hành cho hai lớp: một lớp còn chữa bài thì chưa tính tỉ lệ (Decision 2)."""
    http, maker = stack
    paper, _ = await _class_of_21(maker, 21)
    await _end_phase_two(maker, paper)
    # Một lớp, đã xong: dòng có mặt -- để phép thử dưới đây đo đúng một điều.
    queue = (await http.get("/api/teacher/board", headers=TEACHER)).json()["queue"]
    assert [one for one in queue if one["kind"] == "wrong_rate"]
    async with maker() as session:
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        other = SchoolClass(name="12B", teacher_id=teacher.id)
        session.add(other)
        await session.flush()
        now = datetime.now(UTC)
        session.add(
            Publication(
                assessment_id=paper.id,
                class_id=other.id,
                opens_at=now - timedelta(hours=1),
                closes_at=now - timedelta(minutes=30),
                phase1_minutes=15,
                phase2_minutes_per_question=3,
                remediation_deadline=now + timedelta(hours=5),
                published_at=now - timedelta(hours=2),
            )
        )
        await session.commit()

    queue = (await http.get("/api/teacher/board", headers=TEACHER)).json()["queue"]
    assert not [one for one in queue if one["kind"] == "wrong_rate"]


# ------------------------------------------------------------------ điểm gộp


@pytest.mark.asyncio
async def test_class_stats_count_only_finished_papers_on_a_ten_point_scale(stack) -> None:
    """Đang chạy thì lớp chưa có điểm gộp; hết hạn chữa thì có, quy về thang 10."""
    http, maker = stack
    school_class, paper, questions = await _seeded(maker)
    best, worst = await _students(maker, school_class, 2)
    count = len(questions)
    await _hand_in(maker, paper, best, questions, [True] * count)
    await _hand_in(maker, paper, worst, questions, [True] + [False] * (count - 1))

    assert (await http.get("/api/teacher/board", headers=TEACHER)).json()["classes"] == []

    await _end_phase_two(maker, paper)
    body = (await http.get("/api/teacher/board", headers=TEACHER)).json()
    (row,) = body["classes"]
    low = round(10 / count, 1)
    assert (row["name"], row["papers"]) == ("12A", 1)
    assert (row["highest"], row["lowest"]) == (10.0, low)
    assert row["mean"] == round((10 + 10 / count) / 2, 1)
    assert row["weakest"].endswith("% bài sai)")
    assert body["objectives"] and body["objectives"][0]["percent"] > 0


@pytest.mark.asyncio
async def test_bank_ids_follow_both_copy_directions(stack) -> None:
    """Câu lấy từ ngân hàng (việc 17) cũng có `bank_id`, qua `Question.bank_question_id`."""
    http, maker = stack
    _, paper, questions = await _seeded(maker)
    async with maker() as session:
        row = await session.scalar(
            select(BankQuestion).where(BankQuestion.question_id == questions[0].id)
        )
        row.question_id = None
        question = await session.get(Question, questions[0].id)
        question.bank_question_id = row.id
        await session.commit()
        bank_id = row.id

    detail = (
        await http.get(f"/api/teacher/board/questions/{questions[0].id}", headers=TEACHER)
    ).json()
    assert detail["bank_id"] == bank_id
    assert (
        await http.get(f"/api/teacher/board/questions/{questions[0].id}", headers=STRANGER)
    ).status_code == 404
    assert paper.id


# ------------------------------------------------------------------ review pha 1


async def _strangers_paper(maker) -> tuple[str, str]:
    """Một đề của thầy B đã hết giai đoạn 2, 21 bài sai hết, và một báo cáo. Trả (đề, báo cáo)."""
    async with maker() as session:
        other = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-002"))
        now = datetime.now(UTC)
        school_class = SchoolClass(name="10C", teacher_id=other.id)
        paper = Assessment(
            teacher_id=other.id,
            title="Đề của thầy B",
            subject="Toán",
            grade="10",
            state="published",
            created_at=now,
        )
        session.add_all([school_class, paper])
        await session.flush()
        question = Question(
            assessment_id=paper.id, order_index=1, stem="Câu của thầy B?", learning_objective="B"
        )
        session.add(question)
        session.add(
            Publication(
                assessment_id=paper.id,
                class_id=school_class.id,
                opens_at=now - timedelta(days=2),
                closes_at=now - timedelta(days=2),
                phase1_minutes=15,
                phase2_minutes_per_question=3,
                remediation_deadline=now - timedelta(minutes=1),
                published_at=now - timedelta(days=3),
            )
        )
        await session.flush()
        report_id = ""
        for n in range(21):
            student = Student(
                class_id=school_class.id, full_name=f"B {n}", student_code=f"B{n:03d}"
            )
            session.add(student)
            await session.flush()
            attempt = Attempt(
                assessment_id=paper.id,
                student_id=student.id,
                class_id=school_class.id,
                started_at=now - timedelta(days=2),
                ends_at=now - timedelta(days=2),
                submitted_at=now - timedelta(days=2),
            )
            session.add(attempt)
            await session.flush()
            session.add(
                QuestionOutcome(
                    attempt_id=attempt.id, question_id=question.id, mark=0.0, reason="chưa-chữa"
                )
            )
            if n == 0:
                report = Report(attempt_id=attempt.id, note=None, created_at=now)
                session.add(report)
                await session.flush()
                report_id = report.id
        await session.commit()
        return paper.id, report_id


@pytest.mark.asyncio
async def test_another_teachers_queue_never_leaks(stack) -> None:
    """Thầy B có báo cáo và câu sai cao; cô A không thấy gì của thầy, và ngược lại (ADR-22)."""
    http, maker = stack
    paper, questions = await _class_of_21(maker, 21)
    await _end_phase_two(maker, paper)
    their_paper, their_report = await _strangers_paper(maker)

    mine = (await http.get("/api/teacher/board", headers=TEACHER)).json()
    theirs = (await http.get("/api/teacher/board", headers=STRANGER)).json()

    assert {one["assessment_id"] for one in mine["queue"]} == {paper.id}
    assert {one["assessment_id"] for one in theirs["queue"]} == {their_paper}
    assert [one["name"] for one in mine["classes"]] == ["12A"]
    assert [one["name"] for one in theirs["classes"]] == ["10C"]
    assert (
        await http.get(f"/api/teacher/board/chat/{their_report}", headers=TEACHER)
    ).status_code == 404
    assert (
        await http.post(f"/api/teacher/board/questions/{questions[0].id}/seen", headers=STRANGER)
    ).status_code == 404


@pytest.mark.asyncio
async def test_seen_marks_only_the_reports_on_screen(stack) -> None:
    """Báo cáo đến sau lúc màn 25 hiện thì ở lại; báo cáo của đề khác không bị đụng."""
    http, maker = stack
    school_class, paper, questions = await _seeded(maker)
    first, second = await _students(maker, school_class, 2)
    a1 = await _hand_in(maker, paper, first, questions, [True] * len(questions))
    a2 = await _hand_in(maker, paper, second, questions, [True] * len(questions))
    shown = await _report(maker, a1)
    await _report(maker, a2)
    _, their_report = await _strangers_paper(maker)

    await http.post(
        f"/api/teacher/board/reports/{paper.id}/seen",
        json={"report_ids": [shown, their_report]},
        headers=TEACHER,
    )

    async with maker() as session:
        rows = {one.id: one.resolved_at for one in await session.scalars(select(Report))}
    assert rows[shown] is not None
    assert rows[their_report] is None
    assert sum(1 for at in rows.values() if at is None) == 2
    (row,) = [
        one
        for one in (await http.get("/api/teacher/board", headers=TEACHER)).json()["queue"]
        if one["kind"] == "reports"
    ]
    assert row["figure"] == "1 lượt báo cáo"


@pytest.mark.asyncio
async def test_seen_twice_keeps_the_first_mark(stack) -> None:
    http, maker = stack
    _, _, questions = await _seeded(maker)
    url = f"/api/teacher/board/questions/{questions[0].id}/seen"
    assert (await http.post(url, headers=TEACHER)).status_code == 204
    async with maker() as session:
        first = (await session.get(Question, questions[0].id)).wrong_rate_seen_at
    assert (await http.post(url, headers=TEACHER)).status_code == 204
    async with maker() as session:
        again = (await session.get(Question, questions[0].id)).wrong_rate_seen_at
    assert first is not None and again == first


@pytest.mark.asyncio
async def test_a_recalled_publication_counts_for_nothing(stack) -> None:
    """Lần phát hành đã thu hồi không vào điểm gộp, không vào tỉ lệ sai."""
    http, maker = stack
    paper, _ = await _class_of_21(maker, 21)
    await _end_phase_two(maker, paper)
    async with maker() as session:
        for one in await session.scalars(
            select(Publication).where(Publication.assessment_id == paper.id)
        ):
            one.recalled_at = datetime.now(UTC)
        await session.commit()

    body = (await http.get("/api/teacher/board", headers=TEACHER)).json()
    assert body["classes"] == []
    assert not [one for one in body["queue"] if one["kind"] == "wrong_rate"]


@pytest.mark.asyncio
async def test_an_unanswered_question_shows_as_its_own_share(stack) -> None:
    """Bài bỏ trống câu ấy: tỉ lệ bỏ trống cùng mẫu số với các phương án."""
    http, maker = stack
    school_class, paper, questions = await _seeded(maker)
    first, second = await _students(maker, school_class, 2)
    await _hand_in(maker, paper, first, questions, [True] * len(questions))
    blank = await _hand_in(maker, paper, second, questions, [False] * len(questions))
    async with maker() as session:
        answer = await session.scalar(
            select(Answer).where(Answer.attempt_id == blank, Answer.question_id == questions[0].id)
        )
        await session.delete(answer)
        await session.commit()

    detail = (
        await http.get(f"/api/teacher/board/questions/{questions[0].id}", headers=TEACHER)
    ).json()
    assert (detail["submitted"], detail["unanswered"], detail["wrong_percent"]) == (2, 50, 50)
    assert sum(one["percent"] for one in detail["options"]) + detail["unanswered"] == 100


@pytest.mark.asyncio
async def test_class_stats_count_only_the_classes_that_finished(stack) -> None:
    """Đề ở hai lớp: lớp xong có điểm gộp, lớp còn chữa bài chưa có dòng nào."""
    http, maker = stack
    school_class, paper, questions = await _seeded(maker)
    (one,) = await _students(maker, school_class, 1)
    await _hand_in(maker, paper, one, questions, [True] * len(questions))
    await _end_phase_two(maker, paper)
    async with maker() as session:
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        other = SchoolClass(name="12B", teacher_id=teacher.id)
        session.add(other)
        await session.flush()
        now = datetime.now(UTC)
        session.add(
            Publication(
                assessment_id=paper.id,
                class_id=other.id,
                opens_at=now - timedelta(hours=1),
                closes_at=now - timedelta(minutes=30),
                phase1_minutes=15,
                phase2_minutes_per_question=3,
                remediation_deadline=now + timedelta(hours=5),
                published_at=now - timedelta(hours=2),
            )
        )
        await session.commit()

    classes = (await http.get("/api/teacher/board", headers=TEACHER)).json()["classes"]
    assert [(row["name"], row["papers"], row["mean"]) for row in classes] == [("12A", 1, 10.0)]
