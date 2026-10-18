"""Bảng điểm `.xlsx` của một đề trong một lớp (việc 20, plan `results-xlsx-export`).

Tệp được đọc lại bằng `openpyxl` và soát từng ô: đầu cột, điểm từng câu, tổng, em chưa nộp để
trống. Quyền: chỉ giáo viên tác giả của đề, ở lớp của chính họ, với lần phát hành chưa thu hồi
(ADR-22).
"""

from datetime import UTC, datetime, timedelta
from io import BytesIO
from urllib.parse import unquote

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.db import bind_sessions
from be.results_export import ResultLine, build_workbook
from be.seed import seed_if_empty
from be.teacher_reads import router as reads_router
from schema.ddl import prepare_schema
from schema.models import (
    Assessment,
    Attempt,
    Publication,
    Question,
    QuestionOutcome,
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


async def _hand_in(maker, paper, student, questions, marks) -> None:
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
        for question, mark in zip(questions, marks, strict=True):
            session.add(
                QuestionOutcome(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    mark=mark,
                    reason="đúng-ngay" if mark == 1 else "chưa-chữa",
                    closed=mark == 1,
                )
            )
        await session.commit()


def _url(class_id: str, paper_id: str) -> str:
    return f"/api/teacher/classes/{class_id}/assessments/{paper_id}/results.xlsx"


@pytest.mark.asyncio
async def test_the_sheet_has_every_student_their_marks_and_the_total(stack) -> None:
    """Mỗi học sinh của lớp một dòng theo mã; em chưa nộp để trống, không ghi 0."""
    http, maker = stack
    school_class, paper, students, questions = await _seeded(maker)
    count = len(questions)
    marks = [1.0, 0.5] + [0.0] * (count - 2)
    await _hand_in(maker, paper, students[0], questions, marks)

    answer = await http.get(_url(school_class.id, paper.id), headers=TEACHER)

    assert answer.status_code == 200, answer.text
    assert answer.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    disposition = answer.headers["content-disposition"]
    assert "attachment" in disposition
    assert unquote(disposition.split("filename*=UTF-8''")[1]) == (
        f"Bảng điểm - {paper.title} - {school_class.name}.xlsx"
    )
    sheet = load_workbook(BytesIO(answer.content)).active
    rows = list(sheet.iter_rows(values_only=True))
    assert sheet.title == school_class.name
    assert rows[0] == ("Mã học sinh", "Họ tên", *(f"Câu {n}" for n in range(1, count + 1)), "Tổng")
    assert len(rows) == 1 + len(students)
    first = rows[1]
    assert first[:2] == (students[0].student_code, students[0].full_name)
    assert list(first[2 : 2 + count]) == marks
    assert first[2 + count] == 1.5
    # Em chưa nộp: có dòng, các ô điểm trống.
    blank = rows[2]
    assert blank[:2] == (students[1].student_code, students[1].full_name)
    assert all(cell is None for cell in blank[2:])


@pytest.mark.asyncio
async def test_only_the_author_exports_and_only_while_published(stack) -> None:
    """Người khác 404; lần phát hành đã thu hồi 404 (ADR-22)."""
    http, maker = stack
    school_class, paper, _, _ = await _seeded(maker)

    assert (await http.get(_url(school_class.id, paper.id), headers=STRANGER)).status_code == 404

    async with maker() as session:
        publication = await session.scalar(
            select(Publication).where(Publication.assessment_id == paper.id)
        )
        publication.recalled_at = datetime.now(UTC)
        await session.commit()
    assert (await http.get(_url(school_class.id, paper.id), headers=TEACHER)).status_code == 404


def test_a_sheet_name_drops_what_excel_forbids() -> None:
    """Tên trang tính: bỏ ký tự Excel cấm, tối đa 31 ký tự."""
    data = build_workbook(
        "Lớp 12/A [chuyên] toán nâng cao học kỳ một", 1, [ResultLine("1", "A", [1.0])]
    )
    title = load_workbook(BytesIO(data)).active.title
    assert "/" not in title and "[" not in title and len(title) <= 31


@pytest.mark.asyncio
async def test_rows_follow_the_student_code_whatever_the_insert_order(stack) -> None:
    """Một em có mã nhỏ nhất thêm sau cùng vẫn đứng đầu bảng."""
    http, maker = stack
    school_class, paper, _, _ = await _seeded(maker)
    async with maker() as session:
        session.add(Student(class_id=school_class.id, full_name="Em đến sau", student_code="0001"))
        await session.commit()

    answer = await http.get(_url(school_class.id, paper.id), headers=TEACHER)

    rows = list(load_workbook(BytesIO(answer.content)).active.iter_rows(values_only=True))
    assert rows[1][:2] == ("0001", "Em đến sau")


@pytest.mark.asyncio
async def test_a_teacher_with_a_class_still_cannot_export_someone_elses_paper(stack) -> None:
    """Thầy B có lớp của mình, nhưng đề là của cô A: 404, không phải vì thầy không có lớp nào."""
    http, maker = stack
    _, paper, _, _ = await _seeded(maker)
    async with maker() as session:
        other = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-002"))
        mine = SchoolClass(name="10C", teacher_id=other.id)
        session.add(mine)
        await session.commit()
        class_id = mine.id

    assert (await http.get(_url(class_id, paper.id), headers=STRANGER)).status_code == 404


def test_a_name_that_looks_like_a_formula_stays_text() -> None:
    """Chèn công thức: họ tên *"=1+1"* đọc lại là chữ, không phải công thức."""
    data = build_workbook("12A", 1, [ResultLine("=2+2", '=HYPERLINK("x")', [1.0])])
    sheet = load_workbook(BytesIO(data)).active
    code, name = sheet["A2"], sheet["B2"]
    assert (code.value, code.data_type) == ("=2+2", "s")
    assert (name.value, name.data_type) == ('=HYPERLINK("x")', "s")


def test_a_question_without_a_ledger_row_is_blank_not_zero() -> None:
    data = build_workbook("12A", 2, [ResultLine("1", "A", [1.0, None])])
    rows = list(load_workbook(BytesIO(data)).active.iter_rows(values_only=True))
    assert rows[1] == ("1", "A", 1.0, None, 1.0)


@pytest.mark.asyncio
async def test_a_title_with_quotes_and_newlines_keeps_the_header_whole(stack) -> None:
    """Tên đề có `"` và xuống dòng: header vẫn một dòng, tên ASCII không dấu, tên UTF-8 đủ."""
    http, maker = stack
    school_class, paper, _, _ = await _seeded(maker)
    async with maker() as session:
        row = await session.get(Assessment, paper.id)
        row.title = 'Đề "khó"\nvề đạo hàm/tích phân'
        await session.commit()

    answer = await http.get(_url(school_class.id, paper.id), headers=TEACHER)

    assert answer.status_code == 200
    disposition = answer.headers["content-disposition"]
    plain = disposition.split('filename="')[1].split('"')[0]
    assert plain.startswith("Bang diem - De _kho__ve dao ham_tich phan")
    assert "\n" not in disposition and "/" not in disposition.split("filename*=")[1]
    assert unquote(disposition.split("filename*=UTF-8''")[1]).startswith('Bảng điểm - Đề "khó"')
