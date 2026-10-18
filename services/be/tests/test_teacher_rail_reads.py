"""Các màn của rail giáo viên đọc đúng số, và chỉ của chính giáo viên (plan `teacher-rail-screens`).

Việc 18 của đợt tất định. Dữ liệu là seed -- lớp 12A, một đề đang mở có câu trong ngân hàng --
cộng bài làm ghi thẳng vào database, để mỗi con số trên màn hình có một phép đếm biết trước.
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
from be.teacher_reads import router as reads_router
from schema.ddl import prepare_schema
from schema.models import (
    Assessment,
    AssessmentState,
    Attempt,
    BankQuestion,
    DraftItem,
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
    app.include_router(reads_router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker
    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _seeded(maker):
    """Lớp, đề, học sinh và câu của seed."""
    async with maker() as session:
        school_class = await session.scalar(select(SchoolClass))
        paper = await session.scalar(select(Assessment))
        students = list(
            await session.scalars(
                select(Student)
                .where(Student.class_id == school_class.id)
                .order_by(Student.student_code)
            )
        )
        questions = list(
            await session.scalars(
                select(Question)
                .where(Question.assessment_id == paper.id)
                .order_by(Question.order_index)
            )
        )
        return school_class, paper, students, questions


async def _hand_in(maker, paper, student, questions, marks, closed=None):
    """Một bài đã nộp, với điểm từng câu và cờ đóng (mặc định: câu đủ 1 điểm thì đóng)."""
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
        for index, (question, mark) in enumerate(zip(questions, marks, strict=True)):
            session.add(
                QuestionOutcome(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    mark=mark,
                    reason="đúng-ngay" if mark == 1 else "chưa-chữa",
                    closed=closed[index] if closed is not None else mark == 1,
                )
            )
        await session.commit()
        return attempt.id


# ------------------------------------------------------------------ màn 9, 10


@pytest.mark.asyncio
async def test_the_class_list_counts_progress_on_the_running_paper(stack) -> None:
    http, maker = stack
    school_class, paper, students, questions = await _seeded(maker)
    perfect = [1.0] * len(questions)
    half = [1.0] * (len(questions) - 1) + [0.0]
    await _hand_in(maker, paper, students[0], questions, perfect)
    await _hand_in(maker, paper, students[1], questions, half)

    body = (await http.get("/api/teacher/classes", headers=TEACHER)).json()

    (row,) = body["classes"]
    assert row["name"] == "12A"
    assert row["courses"] == "Toán 12"
    assert row["open_count"] == 1
    assert (row["not_submitted"], row["phase_one"], row["phase_two"]) == (
        len(students) - 2,
        1,
        1,
    )
    assert row["by_paper"][0]["title"] == paper.title
    assert body["student_total"] == len(students)


@pytest.mark.asyncio
async def test_a_class_with_nothing_running_shows_no_progress_numbers(stack) -> None:
    """Đề đã qua hạn chữa thì không còn *đang mở*: ba cột là `None`, màn hình ghi *"—"*."""
    http, maker = stack
    async with maker() as session:
        publication = await session.scalar(select(Publication))
        publication.remediation_deadline = datetime.now(UTC) - timedelta(minutes=1)
        publication.closes_at = datetime.now(UTC) - timedelta(minutes=2)
        await session.commit()

    (row,) = (await http.get("/api/teacher/classes", headers=TEACHER)).json()["classes"]

    assert row["open_count"] == 0
    assert row["not_submitted"] is None and row["by_paper"] == []


@pytest.mark.asyncio
async def test_class_detail_lists_papers_and_students_and_is_the_owners(stack) -> None:
    http, maker = stack
    school_class, paper, students, questions = await _seeded(maker)
    await _hand_in(maker, paper, students[0], questions, [1.0] * len(questions))

    mine = await http.get(f"/api/teacher/classes/{school_class.id}", headers=TEACHER)
    theirs = await http.get(f"/api/teacher/classes/{school_class.id}", headers=STRANGER)

    body = mine.json()
    assert body["papers"][0]["status"] == "Đang mở"
    assert body["papers"][0]["submitted"] == 1
    assert [one["student_code"] for one in body["students"]] == sorted(
        one.student_code for one in students
    )
    assert theirs.status_code == 404


# ------------------------------------------------------------------ màn 21


@pytest.mark.asyncio
async def test_the_paper_list_labels_each_paper_by_the_clock_and_its_lifecycle(stack) -> None:
    http, maker = stack
    async with maker() as session:
        owner = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        session.add(
            Assessment(
                teacher_id=owner.id,
                title="Đề nháp",
                subject="Toán",
                grade="11",
                state=AssessmentState.HAS_QUESTIONS,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

    body = (await http.get("/api/teacher/assessments", headers=TEACHER)).json()

    shown = {one["title"]: one for one in body["papers"]}
    assert shown["Đề nháp"]["status"] == "Chưa duyệt"
    assert shown["Đề nháp"]["shows_results"] is False
    published = shown["Kiểm tra 15 phút — Hàm số"]
    assert published["status"] == "Đang mở"
    assert published["classes"] == ["12A"]
    assert published["shows_results"] is True
    assert body["running"] == 1
    assert (await http.get("/api/teacher/assessments", headers=STRANGER)).json()["papers"] == []


# ------------------------------------------------------------------ màn 11, 23


@pytest.mark.asyncio
async def test_class_results_give_the_four_numbers_and_the_distribution(stack) -> None:
    http, maker = stack
    school_class, paper, students, questions = await _seeded(maker)
    count = len(questions)
    await _hand_in(maker, paper, students[0], questions, [1.0] * count)
    await _hand_in(maker, paper, students[1], questions, [1.0] * (count - 1) + [0.5])
    await _hand_in(maker, paper, students[2], questions, [0.0] * count)

    body = (
        await http.get(
            f"/api/teacher/classes/{school_class.id}/assessments/{paper.id}/results",
            headers=TEACHER,
        )
    ).json()

    assert body["submitted"] == 3
    assert body["highest"] == count and body["lowest"] == 0
    assert body["median"] == count - 0.5
    # N ô như artboard 11: bài trọn điểm gộp vào ô cuối, không có ô riêng.
    assert len(body["distribution"]) == count
    assert body["distribution"][count - 1] == 2 and body["distribution"][0] == 1
    assert [one["mark"] for one in body["rows"]] == [count, count - 0.5, 0]
    assert body["rows"][0]["first_try"] == count
    assert body["rows"][0]["note"] == "Đã chữa xong"
    assert body["rows"][2]["note"] == "Còn câu chữa"


@pytest.mark.asyncio
async def test_a_students_work_shows_each_answer_and_counts_reports(stack) -> None:
    http, maker = stack
    school_class, paper, students, questions = await _seeded(maker)
    attempt = await _hand_in(
        maker, paper, students[0], questions, [1.0] + [0.0] * (len(questions) - 1)
    )
    async with maker() as session:
        session.add(Report(attempt_id=attempt, created_at=datetime.now(UTC)))
        await session.commit()

    path = f"/api/teacher/classes/{school_class.id}/assessments/{paper.id}"
    body = (await http.get(f"{path}/students/{students[0].id}", headers=TEACHER)).json()
    unknown = await http.get(f"{path}/students/nobody", headers=TEACHER)
    foreign = await http.get(f"{path}/students/{students[0].id}", headers=STRANGER)

    assert body["full_name"] == students[0].full_name
    assert (body["mark"], body["first_try"], body["reports"]) == (1.0, 1, 1)
    assert len(body["items"]) == len(questions)
    assert body["items"][0]["correct"].startswith(("A.", "B.", "C.", "D."))
    assert unknown.status_code == 404 and foreign.status_code == 404


# ------------------------------------------------------------------ màn 22, 22b


@pytest.mark.asyncio
async def test_editing_a_bank_question_leaves_the_paper_alone(stack) -> None:
    """Chỉ bản trong ngân hàng đổi; câu trong đề đã phát hành giữ nguyên (người dùng chốt 18/10)."""
    http, maker = stack
    listed = (await http.get("/api/teacher/bank", headers=TEACHER)).json()
    first = listed["questions"][0]
    detail = (await http.get(f"/api/teacher/bank/{first['bank_id']}", headers=TEACHER)).json()
    edited = {
        "stem": detail["stem"] + " (bản ngân hàng)",
        "learning_objective": detail["learning_objective"],
        "options": detail["options"],
        "methods": detail["methods"],
    }

    saved = await http.patch(f"/api/teacher/bank/{first['bank_id']}", json=edited, headers=TEACHER)
    broken = await http.patch(
        f"/api/teacher/bank/{first['bank_id']}",
        json={**edited, "methods": edited["methods"][:1]},
        headers=TEACHER,
    )
    foreign = await http.get(f"/api/teacher/bank/{first['bank_id']}", headers=STRANGER)

    assert listed["approvals"] == 1 and first["course"] == "Toán 12"
    assert saved.status_code == 200 and saved.json()["stem"].endswith("(bản ngân hàng)")
    assert broken.status_code == 422
    assert foreign.status_code == 404
    async with maker() as session:
        row = await session.get(BankQuestion, first["bank_id"])
        question = await session.get(Question, row.question_id)
    assert not question.stem.endswith("(bản ngân hàng)")


# ------------------------------------------------------------------ ca biên (review pha 1)


async def _second_class(maker, name="12B"):
    """Một lớp thứ hai của GV-001, có một học sinh."""
    async with maker() as session:
        owner = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        other = SchoolClass(teacher_id=owner.id, name=name)
        session.add(other)
        await session.flush()
        session.add(Student(class_id=other.id, full_name="Học Sinh B", student_code=f"B-{name}"))
        await session.commit()
        return other.id


async def _publish(maker, paper_id, class_id, opens_in_hours):
    async with maker() as session:
        now = datetime.now(UTC)
        session.add(
            Publication(
                assessment_id=paper_id,
                class_id=class_id,
                opens_at=now + timedelta(hours=opens_in_hours),
                closes_at=now + timedelta(hours=opens_in_hours + 1),
                phase1_minutes=15,
                phase2_minutes_per_question=5,
                remediation_deadline=now + timedelta(hours=opens_in_hours + 3),
                published_at=now,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_results_and_bank_edits_are_the_owners_and_need_a_publication(stack) -> None:
    http, maker = stack
    school_class, paper, _students, _questions = await _seeded(maker)
    other = await _second_class(maker)
    path = f"/api/teacher/classes/{school_class.id}/assessments/{paper.id}/results"
    bank = (await http.get("/api/teacher/bank", headers=TEACHER)).json()["questions"][0]

    foreign = await http.get(path, headers=STRANGER)
    unpublished = await http.get(
        f"/api/teacher/classes/{other}/assessments/{paper.id}/results", headers=TEACHER
    )
    edit = await http.patch(
        f"/api/teacher/bank/{bank['bank_id']}",
        json={"stem": "x", "learning_objective": "x", "options": [], "methods": []},
        headers=STRANGER,
    )

    assert foreign.status_code == 404
    assert unpublished.status_code == 404
    assert edit.status_code == 404


@pytest.mark.asyncio
async def test_a_recalled_publication_reads_as_never_published(stack) -> None:
    http, maker = stack
    school_class, paper, _students, _questions = await _seeded(maker)
    async with maker() as session:
        (await session.scalar(select(Publication))).recalled_at = datetime.now(UTC)
        await session.commit()

    classes = (await http.get("/api/teacher/classes", headers=TEACHER)).json()["classes"]
    detail = (await http.get(f"/api/teacher/classes/{school_class.id}", headers=TEACHER)).json()
    papers = (await http.get("/api/teacher/assessments", headers=TEACHER)).json()["papers"]

    assert classes[0]["open_count"] == 0 and classes[0]["courses"] == ""
    assert detail["papers"] == []
    assert papers[0]["classes"] == [] and papers[0]["shows_results"] is False


@pytest.mark.asyncio
async def test_a_paper_not_yet_open_is_not_running(stack) -> None:
    """Chưa tới giờ mở: không tính vào *đề đang mở*, nhãn *Chưa tới giờ mở*, chưa có kết quả."""
    http, maker = stack
    async with maker() as session:
        publication = await session.scalar(select(Publication))
        now = datetime.now(UTC)
        publication.opens_at = now + timedelta(hours=1)
        publication.closes_at = now + timedelta(hours=2)
        await session.commit()

    (row,) = (await http.get("/api/teacher/classes", headers=TEACHER)).json()["classes"]
    (paper,) = (await http.get("/api/teacher/assessments", headers=TEACHER)).json()["papers"]

    assert row["open_count"] == 0 and row["not_submitted"] is None
    assert paper["status"] == "Chưa tới giờ mở" and paper["recallable"] is True
    assert paper["first_class_id"] == "" and paper["shows_results"] is False


@pytest.mark.asyncio
async def test_a_half_mark_falls_in_the_bin_below(stack) -> None:
    http, maker = stack
    school_class, paper, students, questions = await _seeded(maker)
    count = len(questions)
    await _hand_in(maker, paper, students[0], questions, [1.0] * (count - 1) + [0.5])

    body = (
        await http.get(
            f"/api/teacher/classes/{school_class.id}/assessments/{paper.id}/results",
            headers=TEACHER,
        )
    ).json()

    assert body["distribution"][count - 1] == 1 and sum(body["distribution"]) == 1
    assert body["rows"][0]["note"] == "Còn câu chữa"


@pytest.mark.asyncio
async def test_drafting_and_empty_papers_get_their_own_labels(stack) -> None:
    http, maker = stack
    async with maker() as session:
        owner = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        now = datetime.now(UTC)
        empty = Assessment(
            teacher_id=owner.id,
            title="Trống",
            subject="Toán",
            grade="10",
            state=AssessmentState.EMPTY,
            created_at=now,
        )
        busy = Assessment(
            teacher_id=owner.id,
            title="Đang soạn",
            subject="Toán",
            grade="10",
            state=AssessmentState.EMPTY,
            created_at=now,
        )
        session.add_all([empty, busy])
        await session.flush()
        session.add(
            DraftItem(
                assessment_id=busy.id, ordinal=1, job_id="j", status="pending", created_at=now
            )
        )
        await session.commit()

    papers = (await http.get("/api/teacher/assessments", headers=TEACHER)).json()["papers"]
    shown = {one["title"]: one["status"] for one in papers}

    assert shown["Trống"] == "Đề trống"
    assert shown["Đang soạn"] == "Đang soạn"


@pytest.mark.asyncio
async def test_a_paper_in_two_classes_reads_by_its_liveliest_class(stack) -> None:
    """12A đang mở, 12B chưa tới giờ: đề *Đang mở*, và *Xem kết quả* mở 12A, lớp đã qua giờ mở."""
    http, maker = stack
    school_class, paper, _students, _questions = await _seeded(maker)
    other = await _second_class(maker, name="10A")
    await _publish(maker, paper.id, other, opens_in_hours=5)

    (row,) = (await http.get("/api/teacher/assessments", headers=TEACHER)).json()["papers"]

    assert row["classes"] == ["10A", "12A"]
    assert row["status"] == "Đang mở"
    assert row["first_class_id"] == school_class.id
