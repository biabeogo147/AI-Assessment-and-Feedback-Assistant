"""Các màn của rail giáo viên: lớp, đề, kết quả, bài làm, ngân hàng (plan `teacher-rail-screens`).

Việc 18 của đợt tất định. Trước module này bốn mục của rail -- *Bảng theo dõi*, *Danh sách lớp
học*, *Các bài kiểm tra*, *Ngân hàng câu hỏi* -- không dẫn đi đâu: dữ liệu lớp chỉ đọc được qua
chat (`list_class`, `get_class`), và ngân hàng câu hỏi chưa có đường đọc nào (ADR-28).

Hai luật đứng trên mọi route ở đây:

- **Của người khác đọc ra như không có** (ADR-22): mọi truy vấn lọc theo giáo viên đang hỏi, và
  một lớp, đề, học sinh không thuộc họ là 404, cùng một câu với thứ không tồn tại.
- **Màn hình không quyết luật** (`services/fe/AGENTS.md`): nhãn trạng thái, *đề đang mở*, ba cột
  tiến độ, ghi chú của một bài -- mọi thứ phụ thuộc giờ BE hay vòng đời đề -- dựng ở đây, theo giờ
  của BE, và FE chỉ vẽ.

Một route ghi duy nhất: sửa **bản trong ngân hàng** của một câu (màn 22b). Câu đã nằm trong đề, kể
cả đề đã phát hành, không đổi (người dùng chốt 18/10/2026).
"""

import logging
from collections import defaultdict
from datetime import UTC, datetime
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from be.agent_gateway import AgentError, validate_question
from be.db import get_session
from be.identity import Asking, current_teacher
from be.remediation import attempt_state
from be.results_export import ResultLine, attachment, build_workbook
from be.teacher_chat import conversation_of
from be.teacher_routes import QuestionEdit
from contracts import GeneratedOption, GeneratedQuestion, SolutionMethod
from schema.models import (
    Answer,
    AnswerOption,
    Assessment,
    AssessmentState,
    Attempt,
    BankQuestion,
    DraftItem,
    Publication,
    Question,
    QuestionOutcome,
    RemediationRound,
    Report,
    SchoolClass,
    Student,
    Teacher,
    aware,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["teacher-reads"])

_NO_CLASS = "Không tìm thấy lớp này trong danh sách của bạn."
_NO_PAPER = "Không tìm thấy đề này trong danh sách của bạn."
_NO_STUDENT = "Không tìm thấy học sinh này trong lớp."
_NO_BANK = "Không tìm thấy câu này trong ngân hàng của bạn."

# Nhãn của một đề ở một lớp, theo giờ BE (Decision 3 của plan). Một chỗ cho màn 10 và màn 21.
_NOT_YET = "Chưa tới giờ mở"
_OPEN = "Đang mở"
_REMEDIATING = "Đang chữa bài"
_OVER = "Đã kết thúc"

# Mã của từng chặng, đi cùng nhãn: FE chọn màu và quyết dòng *"chữa tới"* theo mã, không theo chữ
# -- đổi chữ nhãn thì màn hình không lặng lẽ sai (review FE, plan `teacher-rail-screens`).
_PHASE_CODE = {_NOT_YET: "not_yet", _OPEN: "open", _REMEDIATING: "remediating", _OVER: "over"}


def _now() -> datetime:
    return datetime.now(UTC)


def _phase_of(publication: Publication, now: datetime) -> str:
    """Đề ở lớp này ở chặng nào: chưa mở, đang mở, đang chữa bài, đã kết thúc. Hàm thuần."""
    if now < aware(publication.opens_at):
        return _NOT_YET
    if now < aware(publication.closes_at):
        return _OPEN
    if now < aware(publication.remediation_deadline):
        return _REMEDIATING
    return _OVER


def _is_running(publication: Publication, now: datetime) -> bool:
    """*Đề đang mở* của Decision 2: đã tới giờ mở và chưa qua hạn chữa. Hàm thuần."""
    return aware(publication.opens_at) <= now < aware(publication.remediation_deadline)


async def _classes(session: AsyncSession, asking: Asking) -> list[SchoolClass]:
    return list(
        await session.scalars(
            select(SchoolClass)
            .where(SchoolClass.teacher_id == asking.teacher_id)
            .options(selectinload(SchoolClass.students))
            .order_by(SchoolClass.name)
        )
    )


async def _live_publications(
    session: AsyncSession, asking: Asking, class_ids: list[str]
) -> list[tuple[Publication, Assessment]]:
    """Các lần phát hành **chưa thu hồi** của giáo viên này cho các lớp ấy, kèm đề."""
    if not class_ids:
        return []
    rows = await session.execute(
        select(Publication, Assessment)
        .join(Assessment, Assessment.id == Publication.assessment_id)
        .where(
            Publication.class_id.in_(class_ids),
            Publication.recalled_at.is_(None),
            Assessment.teacher_id == asking.teacher_id,
        )
        .order_by(Publication.opens_at.desc())
    )
    return [(publication, assessment) for publication, assessment in rows.all()]


def _courses(papers: list[Assessment]) -> str:
    """*Khối / môn* của một lớp, suy từ các đề đã phát hành cho lớp (Decision 1). Hàm thuần.

    Các cặp *môn khối* khác nhau theo thứ tự gặp, nối bằng dấu phẩy; lớp chưa nhận đề nào là
    chuỗi rỗng và màn hình ghi *"—"*. Không đoán từ tên lớp: *"Ôn thi HSG 12"* không chở khối nào.
    """
    seen: list[str] = []
    for paper in papers:
        named = f"{paper.subject} {paper.grade}".strip()
        if named and named not in seen:
            seen.append(named)
    return ", ".join(seen)


async def _submitted(
    session: AsyncSession, assessment_ids: list[str], student_ids: list[str], class_ids: list[str]
) -> dict[tuple[str, str], Attempt]:
    """Bài **đã nộp** của các học sinh ấy cho các đề ấy, **làm ở các lớp ấy**, theo (đề, học sinh).

    Lọc theo `Attempt.class_id`, không theo lớp hiện tại của học sinh: một em chuyển lớp mang bài cũ
    theo, và bài ấy thuộc lần phát hành cho lớp cũ -- hạn chữa, trạng thái đều của lớp cũ (docstring
    `Attempt`, review pha 1).
    """
    if not assessment_ids or not student_ids or not class_ids:
        return {}
    rows = await session.scalars(
        select(Attempt).where(
            Attempt.assessment_id.in_(assessment_ids),
            Attempt.student_id.in_(student_ids),
            Attempt.class_id.in_(class_ids),
            Attempt.submitted_at.is_not(None),
        )
    )
    return {(one.assessment_id, one.student_id): one for one in rows}


async def _outcomes(
    session: AsyncSession, attempt_ids: list[str]
) -> dict[str, dict[str, QuestionOutcome]]:
    """Sổ điểm của từng bài, theo id bài rồi id câu."""
    found: dict[str, dict[str, QuestionOutcome]] = defaultdict(dict)
    if not attempt_ids:
        return found
    for row in await session.scalars(
        select(QuestionOutcome).where(QuestionOutcome.attempt_id.in_(attempt_ids))
    ):
        found[row.attempt_id][row.question_id] = row
    return found


# ------------------------------------------------------------------ màn 9 · Danh sách lớp học


class PaperProgress(BaseModel):
    """Ba con số tiến độ của một đề đang mở trong một lớp -- một dòng của popover (`665:62`)."""

    assessment_id: str
    title: str
    not_submitted: int
    phase_one: int
    phase_two: int


class ClassRow(BaseModel):
    """Một dòng của màn 9.

    Attributes:
        courses: *Khối / môn* (Decision 1); rỗng khi lớp chưa nhận đề nào.
        open_count: Số đề đang mở (Decision 2).
        not_submitted, phase_one, phase_two: Ba cột tiến độ, cộng trên mọi đề đang mở; `None` khi
            lớp không có đề đang mở nào -- màn hình ghi *"—"*, không phải *"0"*.
        by_paper: Ba con số ấy theo từng đề, cho popover khi rê chuột.
    """

    class_id: str
    name: str
    student_count: int
    courses: str
    open_count: int
    not_submitted: int | None
    phase_one: int | None
    phase_two: int | None
    by_paper: tuple[PaperProgress, ...] = ()


class ClassList(BaseModel):
    classes: tuple[ClassRow, ...]
    student_total: int


@router.get("/teacher/classes", response_model=ClassList)
async def list_classes(
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> ClassList:
    """Mọi lớp của giáo viên, kèm tiến độ trên các đề đang mở (màn 9, `180:753`)."""
    asking = Asking.of(teacher)
    now = _now()
    classes = await _classes(session, asking)
    published = await _live_publications(session, asking, [one.id for one in classes])
    running = [(p, a) for p, a in published if _is_running(p, now)]
    students = [student.id for one in classes for student in one.students]
    done = await _submitted(
        session, list({a.id for _, a in running}), students, [one.id for one in classes]
    )
    states = await _outcomes(session, [one.id for one in done.values()])

    rows: list[ClassRow] = []
    for one in classes:
        mine = [(p, a) for p, a in published if p.class_id == one.id]
        live = [(p, a) for p, a in mine if _is_running(p, now)]
        papers: list[PaperProgress] = []
        for publication, paper in live:
            not_submitted = phase_one = phase_two = 0
            for student in one.students:
                attempt = done.get((paper.id, student.id))
                if attempt is None:
                    not_submitted += 1
                    continue
                state = attempt_state(
                    states.get(attempt.id, {}),
                    True,
                    aware(publication.remediation_deadline),
                    now,
                )
                if state == "đã-hoàn-thành":
                    phase_two += 1
                else:
                    phase_one += 1
            papers.append(
                PaperProgress(
                    assessment_id=paper.id,
                    title=paper.title,
                    not_submitted=not_submitted,
                    phase_one=phase_one,
                    phase_two=phase_two,
                )
            )
        rows.append(
            ClassRow(
                class_id=one.id,
                name=one.name,
                student_count=len(one.students),
                courses=_courses([paper for _, paper in mine]),
                open_count=len(live),
                not_submitted=sum(p.not_submitted for p in papers) if papers else None,
                phase_one=sum(p.phase_one for p in papers) if papers else None,
                phase_two=sum(p.phase_two for p in papers) if papers else None,
                by_paper=tuple(papers),
            )
        )
    return ClassList(classes=tuple(rows), student_total=len(students))


# ------------------------------------------------------------------ màn 10 · Chi tiết lớp


class PaperInClass(BaseModel):
    """Một đề đã phát hành cho lớp: một dòng của bảng trên màn 10."""

    assessment_id: str
    title: str
    status: str
    phase: str
    opens_at: datetime
    closes_at: datetime
    submitted: int
    student_count: int


class StudentRow(BaseModel):
    student_id: str
    full_name: str
    student_code: str
    # Trống ở học sinh có trước việc 22 (`sign-in-and-accounts`), tới lần *Đặt lại mật khẩu* đầu.
    username: str | None


class ClassDetail(BaseModel):
    class_id: str
    name: str
    student_count: int
    courses: str
    papers: tuple[PaperInClass, ...]
    students: tuple[StudentRow, ...]


def _roster_order(student: Student) -> tuple[int, int, str]:
    """Thứ tự trong lớp: mã số (việc 22) theo giá trị, `10` sau `9`; rồi mã cũ `HS2026-…`."""
    code = student.student_code
    return (0, int(code), code) if code.isdigit() else (1, 0, code)


async def _owned_class(session: AsyncSession, asking: Asking, class_id: str) -> SchoolClass:
    found = await session.scalar(
        select(SchoolClass)
        .where(SchoolClass.id == class_id, SchoolClass.teacher_id == asking.teacher_id)
        .options(selectinload(SchoolClass.students))
    )
    if found is None:
        raise HTTPException(status_code=404, detail=_NO_CLASS)
    return found


@router.get("/teacher/classes/{class_id}", response_model=ClassDetail)
async def class_detail(
    class_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> ClassDetail:
    """Một lớp: các đề đã phát hành cho lớp, và học sinh (màn 10, `183:874`)."""
    asking = Asking.of(teacher)
    now = _now()
    school_class = await _owned_class(session, asking, class_id)
    published = await _live_publications(session, asking, [class_id])
    students = sorted(school_class.students, key=_roster_order)
    done = await _submitted(
        session, [paper.id for _, paper in published], [one.id for one in students], [class_id]
    )
    return ClassDetail(
        class_id=class_id,
        name=school_class.name,
        student_count=len(students),
        courses=_courses([paper for _, paper in published]),
        papers=tuple(
            PaperInClass(
                assessment_id=paper.id,
                title=paper.title,
                status=_phase_of(publication, now),
                phase=_PHASE_CODE[_phase_of(publication, now)],
                opens_at=aware(publication.opens_at),
                closes_at=aware(publication.closes_at),
                submitted=sum(1 for (aid, _sid) in done if aid == paper.id),
                student_count=len(students),
            )
            for publication, paper in published
        ),
        students=tuple(
            StudentRow(
                student_id=one.id,
                full_name=one.full_name,
                student_code=one.student_code,
                username=one.username,
            )
            for one in students
        ),
    )


# ------------------------------------------------------------------ màn 21 · Các bài kiểm tra


class PaperRow(BaseModel):
    """Một đề trên màn 21.

    Attributes:
        status: Nhãn theo vòng đời và giờ BE (Decision 3).
        phase: Mã chặng của nhãn (`not_yet`, `open`, `remediating`, `over`); rỗng khi đề chưa phát
            hành.
        classes: Tên các lớp đang giữ đề (chưa thu hồi), theo tên.
        first_class_id: Lớp đầu theo tên **trong số lớp đã qua giờ mở** -- *Xem kết quả* mở lớp ấy
            (Decision 4), để không mở ra một màn kết quả trống; rỗng khi chưa lớp nào mở.
        opens_at, remediation_deadline: Mốc mở sớm nhất và hạn chữa muộn nhất trên các lớp.
        recallable: Còn thu hồi được ở mọi lớp (chưa lớp nào tới giờ mở).
        shows_results: Hành động của dòng là *Xem kết quả* (đề đã tới giờ mở ở ít nhất một lớp);
            không thì là *Mở đoạn chat*.
        conversation_id: Đoạn chat đã sinh ra đề, cho *Mở đoạn chat*; rỗng khi không có.
    """

    assessment_id: str
    title: str
    status: str
    phase: str
    classes: tuple[str, ...]
    first_class_id: str
    opens_at: datetime | None
    remediation_deadline: datetime | None
    recallable: bool
    shows_results: bool
    conversation_id: str


class PaperList(BaseModel):
    papers: tuple[PaperRow, ...]
    running: int


def _paper_status(paper: Assessment, phases: list[str], drafting: bool) -> str:
    """Nhãn một đề trên màn 21 (Decision 3). Hàm thuần.

    Đề đã phát hành lấy chặng **đang diễn ra nhất** trên các lớp: một lớp đang mở thì cả đề đang
    mở, dù lớp khác đã xong.
    """
    if phases:
        for phase in (_OPEN, _REMEDIATING, _NOT_YET):
            if phase in phases:
                return phase
        return _OVER
    state = AssessmentState(paper.state)
    if drafting:
        return "Đang soạn"
    if state is AssessmentState.EMPTY:
        return "Đề trống"
    if state is AssessmentState.HAS_QUESTIONS:
        return "Chưa duyệt"
    return "Đã duyệt"


@router.get("/teacher/assessments", response_model=PaperList)
async def list_papers(
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> PaperList:
    """Mọi đề của giáo viên, mới nhất trước (màn 21, `655:4929`)."""
    asking = Asking.of(teacher)
    now = _now()
    papers = list(
        await session.scalars(
            select(Assessment)
            .where(Assessment.teacher_id == asking.teacher_id)
            .order_by(Assessment.created_at.desc())
        )
    )
    classes = {one.id: one.name for one in await _classes(session, asking)}
    published = await _live_publications(session, asking, list(classes))
    drafting = set(
        await session.scalars(
            select(DraftItem.assessment_id).where(
                DraftItem.assessment_id.in_([one.id for one in papers]),
                DraftItem.status.in_(("pending", "retry")),
            )
        )
    )

    rows: list[PaperRow] = []
    for paper in papers:
        mine = sorted(
            ((p, classes[p.class_id]) for p, a in published if a.id == paper.id),
            key=lambda pair: pair[1],
        )
        phases = [_phase_of(p, now) for p, _ in mine]
        status = _paper_status(paper, phases, paper.id in drafting)
        rows.append(
            PaperRow(
                assessment_id=paper.id,
                title=paper.title,
                status=status,
                phase=_PHASE_CODE.get(status, ""),
                classes=tuple(name for _, name in mine),
                first_class_id=next(
                    (p.class_id for p, _ in mine if _phase_of(p, now) != _NOT_YET), ""
                ),
                opens_at=min((aware(p.opens_at) for p, _ in mine), default=None),
                remediation_deadline=max(
                    (aware(p.remediation_deadline) for p, _ in mine), default=None
                ),
                recallable=bool(mine) and all(phase == _NOT_YET for phase in phases),
                shows_results=any(phase != _NOT_YET for phase in phases),
                conversation_id=await conversation_of(session, asking, paper.id) or "",
            )
        )
    running = sum(1 for one in rows if one.status in (_OPEN, _REMEDIATING))
    return PaperList(papers=tuple(rows), running=running)


# -------------------------------------------------------------- màn 11 · Kết quả một đề trong lớp


class ResultRow(BaseModel):
    """Một bài đã nộp trên màn 11.

    Attributes:
        mark: Tổng điểm, trên thang `question_count` (ADR-16: mỗi câu 1 / 0,5 / 0).
        first_try: Số câu đúng ngay lần đầu.
        minutes: Thời gian làm pha 1, làm tròn phút.
        note: Bài đang ở đâu của giai đoạn 2, theo `attempt_state`: *Còn câu chữa*, *Đã chữa xong*,
            *Hết hạn chữa*.
    """

    student_id: str
    full_name: str
    mark: float
    first_try: int
    minutes: int
    submitted_at: datetime
    note: str


class ClassResults(BaseModel):
    """Kết quả một đề trong một lớp (màn 11, `205:1000`).

    `distribution` có `question_count` ô: ô `k` đếm bài có tổng điểm trong [k, k+1), và bài trọn
    điểm gộp vào ô cuối -- như artboard 11 (thang 10, ô 0..9). Thống kê chỉ tính bài đã nộp; rỗng
    khi chưa ai nộp.
    """

    assessment_id: str
    title: str
    class_id: str
    class_name: str
    question_count: int
    submitted: int
    student_count: int
    closes_at: datetime
    highest: float | None
    mean: float | None
    median: float | None
    lowest: float | None
    distribution: tuple[int, ...]
    rows: tuple[ResultRow, ...]


_NOTES = {
    "cần-chữa": "Còn câu chữa",
    "đã-hoàn-thành": "Đã chữa xong",
    "hết-hạn-chữa": "Hết hạn chữa",
}


async def _paper_in_class(
    session: AsyncSession, asking: Asking, class_id: str, assessment_id: str
) -> tuple[SchoolClass, Assessment, Publication]:
    school_class = await _owned_class(session, asking, class_id)
    paper = await session.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.teacher_id == asking.teacher_id
        )
    )
    publication = await session.scalar(
        select(Publication).where(
            Publication.assessment_id == assessment_id,
            Publication.class_id == class_id,
            Publication.recalled_at.is_(None),
        )
    )
    if paper is None or publication is None:
        raise HTTPException(status_code=404, detail=_NO_PAPER)
    return school_class, paper, publication


@router.get(
    "/teacher/classes/{class_id}/assessments/{assessment_id}/results",
    response_model=ClassResults,
)
async def class_results(
    class_id: str,
    assessment_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> ClassResults:
    """Điểm của một lớp ở một đề: bốn con số, phân bố, và từng bài đã nộp."""
    asking = Asking.of(teacher)
    now = _now()
    school_class, paper, publication = await _paper_in_class(
        session, asking, class_id, assessment_id
    )
    question_count = (
        await session.scalar(
            select(func.count())
            .select_from(Question)
            .where(Question.assessment_id == assessment_id)
        )
        or 0
    )
    names = {one.id: one.full_name for one in school_class.students}
    done = await _submitted(session, [assessment_id], list(names), [class_id])
    states = await _outcomes(session, [one.id for one in done.values()])

    rows: list[ResultRow] = []
    for (_aid, student_id), attempt in done.items():
        outcomes = states.get(attempt.id, {})
        state = attempt_state(outcomes, True, aware(publication.remediation_deadline), now)
        rows.append(
            ResultRow(
                student_id=student_id,
                full_name=names[student_id],
                mark=round(sum(one.mark for one in outcomes.values()), 2),
                first_try=sum(1 for one in outcomes.values() if one.reason == "đúng-ngay"),
                minutes=round(
                    (aware(attempt.submitted_at) - aware(attempt.started_at)).total_seconds() / 60
                ),
                submitted_at=aware(attempt.submitted_at),
                note=_NOTES.get(state, ""),
            )
        )
    rows.sort(key=lambda one: (-one.mark, one.full_name))
    marks = [one.mark for one in rows]
    bins = [0] * max(question_count, 1)
    for mark in marks:
        bins[min(int(mark), len(bins) - 1)] += 1
    return ClassResults(
        assessment_id=assessment_id,
        title=paper.title,
        class_id=class_id,
        class_name=school_class.name,
        question_count=question_count,
        submitted=len(rows),
        student_count=len(names),
        closes_at=aware(publication.closes_at),
        highest=max(marks) if marks else None,
        mean=round(sum(marks) / len(marks), 2) if marks else None,
        median=median(marks) if marks else None,
        lowest=min(marks) if marks else None,
        distribution=tuple(bins) if marks else (),
        rows=tuple(rows),
    )


_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/teacher/classes/{class_id}/assessments/{assessment_id}/results.xlsx")
async def results_xlsx(
    class_id: str,
    assessment_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Bảng điểm của một đề trong một lớp, thành tệp `.xlsx` (việc 20, plan `results-xlsx-export`).

    Cùng cửa với màn 11 (`_paper_in_class`): chỉ giáo viên **tác giả** của đề, ở lớp của chính họ,
    với lần phát hành chưa thu hồi (ADR-22). Mỗi học sinh của lớp một dòng theo mã học sinh; em chưa
    nộp để trống các ô điểm. Như màn 11: danh sách là học sinh **đang** ở lớp, và bài lấy theo
    `Attempt.class_id` -- em chuyển vào lớp mà làm bài ở lớp cũ có dòng trống, em đã chuyển đi không
    có dòng.

    Args:
        class_id: Lớp nào.
        assessment_id: Đề nào.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        Tệp, kèm `Content-Disposition` có tên tệp UTF-8.

    Raises:
        HTTPException: 404 khi lớp hay đề không thuộc giáo viên, hoặc đề chưa phát hành cho lớp.
    """
    asking = Asking.of(teacher)
    school_class, paper, _ = await _paper_in_class(session, asking, class_id, assessment_id)
    questions = list(
        await session.scalars(
            select(Question.id)
            .where(Question.assessment_id == assessment_id)
            .order_by(Question.order_index)
        )
    )
    students = sorted(school_class.students, key=_roster_order)
    done = await _submitted(session, [assessment_id], [one.id for one in students], [class_id])
    states = await _outcomes(session, [one.id for one in done.values()])
    lines = []
    for student in students:
        attempt = done.get((assessment_id, student.id))
        marks = None
        if attempt is not None:
            outcomes = states.get(attempt.id, {})
            # Câu không có dòng sổ điểm thì trống, không 0 (Decision 1 của plan). Nộp bài ghi một
            # dòng cho mọi câu (`student_routes`), nên ca này gần như không xảy ra.
            marks = [outcomes[one].mark if one in outcomes else None for one in questions]
        lines.append(ResultLine(student.student_code, student.full_name, marks))
    data = build_workbook(school_class.name, len(questions), lines)
    name = f"Bảng điểm - {paper.title} - {school_class.name}.xlsx"
    return Response(content=data, media_type=_XLSX, headers=attachment(name))


# -------------------------------------------------------------- màn 23 · Bài làm của một học sinh


class WorkItem(BaseModel):
    """Một câu trên màn 23: em chọn gì, đáp án là gì, điểm bao nhiêu."""

    order: int
    stem: str
    chosen: str
    correct: str
    mark: float


class StudentWork(BaseModel):
    """Bài làm của một học sinh ở một đề (màn 23, `656:4089`).

    Attributes:
        state: `attempt_state` của bài; `None` khi em chưa nộp.
        note: Chữ của trạng thái ấy, **cùng bảng** với cột ghi chú của màn 11; rỗng khi chưa nộp.
        rounds_done: Số lượt chữa đã nộp.
        reports: Số lần em báo *giải thích chưa rõ* trong bài này (ADR-19).
    """

    student_id: str
    full_name: str
    student_code: str
    assessment_id: str
    title: str
    class_id: str
    class_name: str
    question_count: int
    submitted_at: datetime | None
    state: str | None
    note: str
    mark: float
    first_try: int
    rounds_done: int
    reports: int
    items: tuple[WorkItem, ...]


@router.get(
    "/teacher/classes/{class_id}/assessments/{assessment_id}/students/{student_id}",
    response_model=StudentWork,
)
async def student_work(
    class_id: str,
    assessment_id: str,
    student_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> StudentWork:
    """Một học sinh đã làm đề này thế nào, từng câu."""
    asking = Asking.of(teacher)
    now = _now()
    school_class, paper, publication = await _paper_in_class(
        session, asking, class_id, assessment_id
    )
    student = next((one for one in school_class.students if one.id == student_id), None)
    if student is None:
        raise HTTPException(status_code=404, detail=_NO_STUDENT)
    questions = list(
        await session.scalars(
            select(Question)
            .where(Question.assessment_id == assessment_id)
            .options(selectinload(Question.options))
            .order_by(Question.order_index)
        )
    )
    attempt = (await _submitted(session, [assessment_id], [student_id], [class_id])).get(
        (assessment_id, student_id)
    )
    outcomes = (await _outcomes(session, [attempt.id] if attempt else [])).get(
        attempt.id if attempt else "", {}
    )
    chose: dict[str, str] = {}
    rounds = reports = 0
    if attempt is not None:
        chose = {
            question_id: option_id
            for question_id, option_id in await session.execute(
                select(Answer.question_id, Answer.option_id).where(Answer.attempt_id == attempt.id)
            )
        }
        rounds = (
            await session.scalar(
                select(func.count())
                .select_from(RemediationRound)
                .where(
                    RemediationRound.attempt_id == attempt.id,
                    RemediationRound.submitted_at.is_not(None),
                )
            )
            or 0
        )
        reports = (
            await session.scalar(
                select(func.count()).select_from(Report).where(Report.attempt_id == attempt.id)
            )
            or 0
        )

    state = (
        attempt_state(outcomes, True, aware(publication.remediation_deadline), now)
        if attempt
        else None
    )

    def shown(option: AnswerOption | None) -> str:
        return f"{option.label}. {option.text}" if option is not None else ""

    items = []
    for question in questions:
        by_id = {one.id: one for one in question.options}
        right = next((one for one in question.options if one.is_correct), None)
        outcome = outcomes.get(question.id)
        items.append(
            WorkItem(
                order=question.order_index,
                stem=question.stem,
                chosen=shown(by_id.get(chose.get(question.id, ""))),
                correct=shown(right),
                mark=outcome.mark if outcome is not None else 0.0,
            )
        )
    return StudentWork(
        student_id=student.id,
        full_name=student.full_name,
        student_code=student.student_code,
        assessment_id=assessment_id,
        title=paper.title,
        class_id=class_id,
        class_name=school_class.name,
        question_count=len(questions),
        submitted_at=aware(attempt.submitted_at) if attempt else None,
        state=state,
        note=_NOTES.get(state or "", ""),
        mark=round(sum(one.mark for one in outcomes.values()), 2),
        first_try=sum(1 for one in outcomes.values() if one.reason == "đúng-ngay"),
        rounds_done=rounds,
        reports=reports,
        items=tuple(items),
    )


# ------------------------------------------------------------------ màn 22, 22b · Ngân hàng câu hỏi


class BankRow(BaseModel):
    bank_id: str
    stem: str
    learning_objective: str
    course: str


class BankList(BaseModel):
    """Ngân hàng câu hỏi của giáo viên (màn 22, `655:5226`). `approvals` là số đề góp câu vào."""

    questions: tuple[BankRow, ...]
    approvals: int


class BankOption(BaseModel):
    label: str
    text: str
    is_correct: bool
    error_label: str | None = None


class BankMethod(BaseModel):
    title: str
    body: str


class BankDetail(BaseModel):
    bank_id: str
    stem: str
    learning_objective: str
    course: str
    options: tuple[BankOption, ...]
    methods: tuple[BankMethod, ...]


async def _bank_rows(
    session: AsyncSession, asking: Asking, bank_id: str | None = None
) -> list[tuple[BankQuestion, Assessment]]:
    query = (
        select(BankQuestion, Assessment)
        .join(Assessment, Assessment.id == BankQuestion.assessment_id)
        .where(BankQuestion.teacher_id == asking.teacher_id)
        .order_by(BankQuestion.approved_at.desc(), BankQuestion.id)
    )
    if bank_id is not None:
        query = query.where(BankQuestion.id == bank_id)
    return [(row, paper) for row, paper in (await session.execute(query)).all()]


def _bank_detail(row: BankQuestion, paper: Assessment) -> BankDetail:
    return BankDetail(
        bank_id=row.id,
        stem=row.stem,
        learning_objective=row.learning_objective,
        course=f"{paper.subject} {paper.grade}".strip(),
        options=tuple(BankOption(**one) for one in row.options or []),
        methods=tuple(BankMethod(**one) for one in row.methods or []),
    )


@router.get("/teacher/bank", response_model=BankList)
async def list_bank(
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> BankList:
    """Mọi câu trong ngân hàng của giáo viên, mới duyệt trước."""
    rows = await _bank_rows(session, Asking.of(teacher))
    return BankList(
        questions=tuple(
            BankRow(
                bank_id=row.id,
                stem=row.stem,
                learning_objective=row.learning_objective,
                course=f"{paper.subject} {paper.grade}".strip(),
            )
            for row, paper in rows
        ),
        approvals=len({paper.id for _, paper in rows}),
    )


@router.get("/teacher/bank/{bank_id}", response_model=BankDetail)
async def bank_question(
    bank_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> BankDetail:
    """Một câu trong ngân hàng, đủ phương án và lời giải (màn 22b)."""
    found = await _bank_rows(session, Asking.of(teacher), bank_id)
    if not found:
        raise HTTPException(status_code=404, detail=_NO_BANK)
    return _bank_detail(*found[0])


@router.patch("/teacher/bank/{bank_id}", response_model=BankDetail)
async def edit_bank_question(
    bank_id: str,
    wanted: QuestionEdit,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> BankDetail:
    """Sửa **bản trong ngân hàng** của một câu (màn 22b, `666:5816`).

    Chỉ bản ngân hàng đổi: câu đã nằm trong đề -- kể cả đề đã phát hành, có bài làm -- giữ nguyên,
    và đề sau lấy câu này sẽ dùng bản mới (người dùng chốt 18/10/2026). Kiểm ADR-18 bằng **chính**
    `validate_question`, như đường sửa câu trong đề.

    Raises:
        HTTPException: 404 khi câu không có trong ngân hàng của người gọi (ADR-22); 422 khi bản sửa
            phá ADR-18.
    """
    found = await _bank_rows(session, Asking.of(teacher), bank_id)
    if not found:
        raise HTTPException(status_code=404, detail=_NO_BANK)
    row, paper = found[0]
    try:
        validate_question(
            GeneratedQuestion(
                stem=wanted.stem,
                options=tuple(
                    GeneratedOption(
                        label=one.label,
                        text=one.text,
                        is_correct=one.is_correct,
                        error_label=one.error_label or "",
                    )
                    for one in wanted.options
                ),
                methods=tuple(
                    SolutionMethod(title=one.title, body=one.body) for one in wanted.methods
                ),
                learning_objective=wanted.learning_objective,
            )
        )
    except (AgentError, ValueError) as refused:
        raise HTTPException(status_code=422, detail=str(refused)) from refused

    before = (row.stem, row.learning_objective, row.options, row.methods)
    # List mới, không sửa tại chỗ: cột JSON không theo dõi thay đổi bên trong một list.
    row.stem = wanted.stem
    row.learning_objective = wanted.learning_objective
    row.options = [
        {
            "label": one.label,
            "text": one.text,
            "is_correct": one.is_correct,
            "error_label": None if one.is_correct else (one.error_label or None),
        }
        for one in wanted.options
    ]
    row.methods = [{"title": one.title, "body": one.body} for one in wanted.methods]
    # Dấu để `question_bank.file_approved` biết bản này của giáo viên: duyệt lại không chép đè. Chỉ
    # khi nội dung đổi thật: bấm Lưu không sửa gì mà cũng đặt dấu là khoá bản này khỏi đề gốc mãi.
    if (row.stem, row.learning_objective, row.options, row.methods) != before:
        row.edited_at = _now()
    await session.commit()
    logger.info("teacher %s edited bank question %s", teacher.teacher_code, bank_id)
    return _bank_detail(row, paper)
