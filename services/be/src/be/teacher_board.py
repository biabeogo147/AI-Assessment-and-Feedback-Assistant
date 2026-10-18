"""Bảng theo dõi của giáo viên: hàng đợi review, điểm gộp theo lớp (plan `dashboard-review-queue`).

Việc 19 và 21 của đợt tất định. Ba màn, cả ba **chỉ đọc**: sửa lời giải chỉ làm ở màn *Ngân hàng câu
hỏi* (22b), và câu đã nằm trong đề đã phát hành không bao giờ đổi (người dùng chốt 18/10/2026).

**Hàng đợi *Cần bạn xem*** có hai loại dòng, cùng trọng lượng -- không xếp nặng nhẹ (ADR-08):

- *Giải thích chưa rõ*, **một dòng mỗi đề**: báo cáo gắn với cả lượt làm bài, không gắn với câu
  (ADR-19), nên gom theo đề. *Đánh dấu đã xem* cũng theo đề: các báo cáo màn 25 đã hiện nhận
  `resolved_at`, và một báo cáo đến sau -- kể cả trong lúc giáo viên đang đọc -- đưa đề vào lại.
  Dòng không ghi lớp (người dùng chốt ở buổi review Figma lần 1).
- *Tỉ lệ sai cao*, **một dòng mỗi câu**: ≥ 70% bài sai ở lần làm đầu, trên 20 bài, và chỉ tính khi
  đề **đã hết giai đoạn 2** ở mọi lớp còn giữ đề -- 70% của 20 bài có thể không còn là 70% của
  50 bài (người dùng chốt 18/10/2026). Câu ở lại tới khi giáo viên đánh dấu đã xem.

**Điểm gộp theo lớp** chỉ tính đề đã hết hạn chữa ở lớp ấy, và quy mỗi bài về thang 10 trước khi
gộp: điểm của một đề là tổng trên số câu (ADR-16), nên đề 6 câu và đề 10 câu không cộng được. Tỉ lệ
sai của một mục kiến thức đếm trên **lượt trả lời** (câu × bài) của mục ấy.

Bài và sổ điểm đọc bằng **join** tới lần phát hành chưa thu hồi, không bằng một danh sách id: một
năm học có thể có hàng chục nghìn bài, và asyncpg dừng ở 32767 tham số một câu lệnh (review pha 1).

Của người khác đọc ra như không có (ADR-22): mọi truy vấn lọc theo giáo viên đang hỏi.
"""

import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from be.db import get_session
from be.identity import Asking, current_teacher
from schema.models import (
    Answer,
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
    aware,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["teacher-board"])

_NO_PAPER = "Không tìm thấy đề này trong danh sách của bạn."
_NO_QUESTION = "Không tìm thấy câu này trong các đề của bạn."
_NO_REPORT = "Không tìm thấy báo cáo này."

# Hai ngưỡng của dòng *tỉ lệ sai cao* (người dùng chốt 18/10/2026): ≥ 70% sai lần đầu, trên 20 bài.
WRONG_RATE = 0.7
MORE_THAN = 20

# Lý do của câu làm đúng ngay lần đầu (`scoring.MarkReason.CORRECT_FIRST_TRY`).
_FIRST_TRY = "đúng-ngay"

# Số mục kiến thức của biểu đồ *tỉ lệ bài sai theo mục kiến thức* (artboard 20).
_TOP_OBJECTIVES = 5


def _now() -> datetime:
    return datetime.now(UTC)


def _over(publication: Publication, now: datetime) -> bool:
    """Đề ở lớp này đã hết giai đoạn 2 (qua hạn chữa). Hàm thuần."""
    return now >= aware(publication.remediation_deadline)


def _tenth(mark: float, question_count: int) -> float:
    """Một bài quy về thang 10 (Decision 1 của plan). Hàm thuần."""
    return mark / question_count * 10 if question_count else 0.0


def _percent(part: int, whole: int) -> int:
    return round(part * 100 / whole) if whole else 0


async def _papers(session: AsyncSession, asking: Asking) -> dict[str, Assessment]:
    rows = await session.scalars(
        select(Assessment).where(Assessment.teacher_id == asking.teacher_id)
    )
    return {one.id: one for one in rows}


async def _live(session: AsyncSession, paper_ids: list[str]) -> list[Publication]:
    """Các lần phát hành **chưa thu hồi** của các đề ấy."""
    if not paper_ids:
        return []
    return list(
        await session.scalars(
            select(Publication).where(
                Publication.assessment_id.in_(paper_ids), Publication.recalled_at.is_(None)
            )
        )
    )


def _graded(teacher_id: str):
    """Sổ điểm của mọi bài **đã nộp** ở một lần phát hành **chưa thu hồi** của giáo viên này.

    Một câu `SELECT` có join, để bên gọi lọc thêm (đề nào) hay gộp (`GROUP BY`). Thu hồi chỉ làm
    được trước giờ mở (ADR-02), nên lần phát hành đã thu hồi không có bài nào; join vẫn loại nó cho
    chắc.
    """
    return (
        select(
            Attempt.id,
            Attempt.assessment_id,
            Attempt.class_id,
            QuestionOutcome.question_id,
            QuestionOutcome.mark,
            QuestionOutcome.reason,
        )
        .select_from(Attempt)
        .join(QuestionOutcome, QuestionOutcome.attempt_id == Attempt.id)
        .join(
            Publication,
            and_(
                Publication.assessment_id == Attempt.assessment_id,
                Publication.class_id == Attempt.class_id,
                Publication.recalled_at.is_(None),
            ),
        )
        .join(Assessment, Assessment.id == Attempt.assessment_id)
        .where(Assessment.teacher_id == teacher_id, Attempt.submitted_at.is_not(None))
    )


async def _outcomes(session: AsyncSession, attempt_ids: list[str]) -> list[QuestionOutcome]:
    if not attempt_ids:
        return []
    return list(
        await session.scalars(
            select(QuestionOutcome).where(QuestionOutcome.attempt_id.in_(attempt_ids))
        )
    )


async def _bank_ids(
    session: AsyncSession, teacher_id: str, questions: list[Question]
) -> dict[str, str]:
    """Dòng ngân hàng của từng câu, để nút *Chỉnh sửa trong Ngân hàng câu hỏi* mở 22b.

    Hai chiều chép (ADR-28, việc 17): câu đã duyệt có bản chép **từ** nó
    (`BankQuestion.question_id`), câu lấy từ ngân hàng nhớ dòng nó chép **từ**
    (`Question.bank_question_id`). Không có thì `""`.
    """
    if not questions:
        return {}
    ids = [one.id for one in questions]
    found = {
        question_id: bank_id
        for bank_id, question_id in await session.execute(
            select(BankQuestion.id, BankQuestion.question_id).where(
                BankQuestion.teacher_id == teacher_id, BankQuestion.question_id.in_(ids)
            )
        )
    }
    return {one.id: found.get(one.id) or one.bank_question_id or "" for one in questions}


# ------------------------------------------------------------------ màn 20 · Bảng theo dõi


class ReviewItem(BaseModel):
    """Một dòng của hàng đợi *Cần bạn xem* (`Review item row`, `657:46`).

    Attributes:
        kind: `reports` (giải thích chưa rõ, một dòng mỗi đề) hay `wrong_rate` (một dòng mỗi câu).
        assessment_id: Đề của dòng.
        question_id: Câu của dòng `wrong_rate`; rỗng ở dòng `reports`.
        title: Dòng đầu -- tên đề, hay *"Câu k · đề bài"*.
        meta: Dòng phụ -- số học sinh đã báo cáo, hay tên đề. Không ghi lớp.
        figure: Cột số liệu -- *"3 lượt báo cáo"*, *"72% bài sai"*.
    """

    kind: Literal["reports", "wrong_rate"]
    assessment_id: str
    question_id: str
    title: str
    meta: str
    figure: str


class ClassStat(BaseModel):
    """Điểm gộp của một lớp (`Class stat row`, `657:55`), trên thang 10.

    Attributes:
        class_id: Lớp nào.
        name: Tên lớp.
        papers: Số đề đã hết hạn chữa ở lớp này.
        mean: Trung bình các bài; `None` khi chưa có bài nào.
        highest: Bài cao nhất.
        lowest: Bài thấp nhất.
        weakest: Mục kiến thức sai nhiều nhất ở lần đầu, kèm tỉ lệ; rỗng khi chưa có bài. Hoà thì
            lấy tên đứng trước, như biểu đồ năm mục.
    """

    class_id: str
    name: str
    papers: int
    mean: float | None
    highest: float | None
    lowest: float | None
    weakest: str


class ObjectiveRate(BaseModel):
    """Một cột của biểu đồ *tỉ lệ bài sai theo mục kiến thức*."""

    learning_objective: str
    percent: int


class Board(BaseModel):
    """Màn 20 *Bảng theo dõi* (artboard `657:3889`).

    Attributes:
        queue: Hàng đợi, báo cáo mới nhất trước rồi tới tỉ lệ sai -- không xếp nặng nhẹ (ADR-08).
        classes: Mọi lớp có ít nhất một đề đã hết hạn chữa.
        objectives: Năm mục kiến thức sai nhiều nhất ở lần đầu, trên mọi lớp ấy.
    """

    queue: tuple[ReviewItem, ...]
    classes: tuple[ClassStat, ...]
    objectives: tuple[ObjectiveRate, ...]


@router.get("/teacher/board", response_model=Board)
async def board(
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> Board:
    """Hàng đợi review và điểm gộp theo lớp.

    Args:
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        Cả màn 20.
    """
    asking = Asking.of(teacher)
    now = _now()
    papers = await _papers(session, asking)
    classes = {
        one.id: one
        for one in await session.scalars(
            select(SchoolClass).where(SchoolClass.teacher_id == asking.teacher_id)
        )
    }
    live = await _live(session, list(papers))

    queue = [
        *await _report_items(session, papers),
        *await _rate_items(session, asking, papers, live, now),
    ]

    # Điểm gộp: (đề, lớp) đã hết hạn chữa ở lớp ấy. Lọc ở Python: so giờ `aware` một cách chắc chắn
    # trên cả sqlite lẫn Postgres, và số lần phát hành thì nhỏ.
    over = {(one.assessment_id, one.class_id) for one in live if _over(one, now)}
    rows = []
    if over:
        rows = [
            row
            for row in (
                await session.execute(
                    _graded(asking.teacher_id)
                    .add_columns(Question.learning_objective)
                    .join(Question, Question.id == QuestionOutcome.question_id)
                )
            ).all()
            if (row.assessment_id, row.class_id) in over
        ]
    # Thang của một bài là số câu của **đề**, không phải số dòng sổ điểm của bài.
    size = (
        dict(
            (
                await session.execute(
                    select(Question.assessment_id, func.count())
                    .where(Question.assessment_id.in_(sorted({paper for paper, _ in over})))
                    .group_by(Question.assessment_id)
                )
            ).all()
        )
        if over
        else {}
    )

    sums: dict[str, list] = {}
    tally: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    overall: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        entry = sums.setdefault(row.id, [row.class_id, row.assessment_id, 0.0])
        entry[2] += row.mark
        wrong = row.reason != _FIRST_TRY
        for counter in (
            tally[row.class_id][row.learning_objective],
            overall[row.learning_objective],
        ):
            counter[0] += wrong
            counter[1] += 1
    marks: dict[str, list[float]] = defaultdict(list)
    for class_id, paper_id, mark in sums.values():
        marks[class_id].append(_tenth(mark, size.get(paper_id, 0)))

    stats = []
    for class_id in sorted(
        {one for _, one in over if one in classes}, key=lambda one: classes[one].name
    ):
        got = marks.get(class_id, [])
        weakest = ""
        if tally[class_id]:
            name, (wrong, total) = min(
                tally[class_id].items(), key=lambda item: (-item[1][0] / item[1][1], item[0])
            )
            weakest = f"{name} ({_percent(wrong, total)}% bài sai)"
        stats.append(
            ClassStat(
                class_id=class_id,
                name=classes[class_id].name,
                papers=len({paper for paper, one in over if one == class_id}),
                mean=round(sum(got) / len(got), 1) if got else None,
                highest=round(max(got), 1) if got else None,
                lowest=round(min(got), 1) if got else None,
                weakest=weakest,
            )
        )
    objectives = sorted(
        (
            ObjectiveRate(learning_objective=name, percent=_percent(wrong, total))
            for name, (wrong, total) in overall.items()
            if total
        ),
        key=lambda one: (-one.percent, one.learning_objective),
    )[:_TOP_OBJECTIVES]
    return Board(queue=tuple(queue), classes=tuple(stats), objectives=tuple(objectives))


async def _report_items(session: AsyncSession, papers: dict[str, Assessment]) -> list[ReviewItem]:
    """Dòng *giải thích chưa rõ*: mỗi đề có báo cáo chưa xem một dòng, báo cáo mới nhất trước."""
    if not papers:
        return []
    rows = (
        await session.execute(
            select(Report, Attempt)
            .join(Attempt, Attempt.id == Report.attempt_id)
            .where(Attempt.assessment_id.in_(list(papers)), Report.resolved_at.is_(None))
        )
    ).all()
    grouped: dict[str, list[tuple[Report, Attempt]]] = defaultdict(list)
    for report, attempt in rows:
        grouped[attempt.assessment_id].append((report, attempt))
    ordered = sorted(
        grouped.items(),
        key=lambda item: max(aware(report.created_at) for report, _ in item[1]),
        reverse=True,
    )
    items = []
    for paper_id, found in ordered:
        students = len({a.student_id for _, a in found})
        items.append(
            ReviewItem(
                kind="reports",
                assessment_id=paper_id,
                question_id="",
                title=papers[paper_id].title,
                meta=f"{students} học sinh",
                figure=f"{len(found)} lượt báo cáo",
            )
        )
    return items


def _wrong_counts(teacher_id: str):
    """Mỗi câu: số bài đã nộp và số bài sai ở lần đầu, gộp bằng `GROUP BY` ở lần phát hành sống."""
    graded = _graded(teacher_id).subquery()
    return select(
        graded.c.question_id,
        func.count(),
        func.sum(case((graded.c.reason != _FIRST_TRY, 1), else_=0)),
    ).group_by(graded.c.question_id), graded


async def _rate_items(
    session: AsyncSession,
    asking: Asking,
    papers: dict[str, Assessment],
    live: list[Publication],
    now: datetime,
) -> list[ReviewItem]:
    """Dòng *tỉ lệ sai cao*: câu chưa xem của đề đã hết giai đoạn 2 ở **mọi** lớp còn giữ đề.

    Đề sắp theo tên, câu theo số -- không theo tỉ lệ: hàng đợi không xếp nặng nhẹ (ADR-08).
    """
    by_paper: dict[str, list[Publication]] = defaultdict(list)
    for one in live:
        by_paper[one.assessment_id].append(one)
    done = sorted(paper for paper, held in by_paper.items() if all(_over(one, now) for one in held))
    if not done:
        return []
    counts, graded = _wrong_counts(asking.teacher_id)
    tally = {
        question_id: (int(wrong or 0), int(total))
        for question_id, total, wrong in await session.execute(
            counts.where(graded.c.assessment_id.in_(done))
        )
    }
    questions = list(
        await session.scalars(
            select(Question).where(
                Question.assessment_id.in_(done), Question.wrong_rate_seen_at.is_(None)
            )
        )
    )
    questions.sort(key=lambda one: (papers[one.assessment_id].title, one.order_index))
    items = []
    for question in questions:
        wrong, total = tally.get(question.id, (0, 0))
        if total <= MORE_THAN or wrong / total < WRONG_RATE:
            continue
        items.append(
            ReviewItem(
                kind="wrong_rate",
                assessment_id=question.assessment_id,
                question_id=question.id,
                title=f"Câu {question.order_index} · {question.stem}",
                meta=papers[question.assessment_id].title,
                figure=f"{_percent(wrong, total)}% bài sai",
            )
        )
    return items


# ------------------------------------------------------------------ màn 25 · báo cáo của một đề


class ReportCard(BaseModel):
    """Một báo cáo trên màn 25.

    Attributes:
        report_id: Báo cáo nào -- khoá của hộp đọc đoạn chat.
        student: Họ tên học sinh.
        class_name: Lớp của lượt làm bài.
        created_at: Lúc báo cáo.
        note: Lời ghi của học sinh; rỗng khi không ghi.
        wrong: Số câu em ấy làm sai ở lần đầu, tăng dần.
    """

    report_id: str
    student: str
    class_name: str
    created_at: datetime
    note: str
    wrong: tuple[int, ...]


class ReportedQuestion(BaseModel):
    """Một câu học sinh báo cáo đã làm sai.

    Attributes:
        question_id: Câu nào.
        order: Số câu.
        stem: Đề bài.
        wrong_by: Bao nhiêu em báo cáo làm sai câu này.
        bank_id: Dòng ngân hàng của câu; rỗng khi câu chưa có bản (nút ẩn).
    """

    question_id: str
    order: int
    stem: str
    wrong_by: int
    bank_id: str


class PaperReports(BaseModel):
    """Màn 25 (`657:4265`): các báo cáo **chưa xem** của một đề.

    Attributes:
        assessment_id: Đề nào.
        title: Tên đề.
        classes: Các lớp có báo cáo, đã sắp.
        reporters: Số học sinh đã báo cáo.
        reports: Mới nhất trước.
        questions: Câu bị nhiều em báo cáo làm sai nhất trước.
    """

    assessment_id: str
    title: str
    classes: tuple[str, ...]
    reporters: int
    reports: tuple[ReportCard, ...]
    questions: tuple[ReportedQuestion, ...]


async def _owned_paper(session: AsyncSession, asking: Asking, assessment_id: str) -> Assessment:
    paper = await session.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.teacher_id == asking.teacher_id
        )
    )
    if paper is None:
        raise HTTPException(status_code=404, detail=_NO_PAPER)
    return paper


@router.get("/teacher/board/reports/{assessment_id}", response_model=PaperReports)
async def paper_reports(
    assessment_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> PaperReports:
    """Các báo cáo chưa xem của một đề, và những câu các em ấy làm sai.

    Args:
        assessment_id: Đề nào.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        Màn 25.

    Raises:
        HTTPException: 404 khi đề không tồn tại hoặc thuộc về người khác (ADR-22).
    """
    asking = Asking.of(teacher)
    paper = await _owned_paper(session, asking, assessment_id)
    rows = (
        await session.execute(
            select(Report, Attempt, Student, SchoolClass)
            .join(Attempt, Attempt.id == Report.attempt_id)
            .join(Student, Student.id == Attempt.student_id)
            .join(SchoolClass, SchoolClass.id == Attempt.class_id)
            .where(Attempt.assessment_id == assessment_id, Report.resolved_at.is_(None))
        )
    ).all()
    rows.sort(key=lambda row: aware(row[0].created_at), reverse=True)
    questions = {
        one.id: one
        for one in await session.scalars(
            select(Question).where(Question.assessment_id == assessment_id)
        )
    }
    wrong_of: dict[str, set[str]] = defaultdict(set)
    for one in await _outcomes(session, sorted({attempt.id for _, attempt, _, _ in rows})):
        if one.reason != _FIRST_TRY:
            wrong_of[one.attempt_id].add(one.question_id)

    cards = []
    reporters_of: dict[str, set[str]] = defaultdict(set)
    for report, attempt, student, school_class in rows:
        wrong = wrong_of.get(attempt.id, set())
        for question_id in wrong:
            reporters_of[question_id].add(student.id)
        cards.append(
            ReportCard(
                report_id=report.id,
                student=student.full_name,
                class_name=school_class.name,
                created_at=aware(report.created_at),
                note=(report.note or "").strip(),
                wrong=tuple(
                    sorted(questions[one].order_index for one in wrong if one in questions)
                ),
            )
        )
    hit = [questions[one] for one in reporters_of if one in questions]
    banks = await _bank_ids(session, paper.teacher_id, hit)
    reported = sorted(
        (
            ReportedQuestion(
                question_id=one.id,
                order=one.order_index,
                stem=one.stem,
                wrong_by=len(reporters_of[one.id]),
                bank_id=banks[one.id],
            )
            for one in hit
        ),
        key=lambda one: (-one.wrong_by, one.order),
    )
    return PaperReports(
        assessment_id=paper.id,
        title=paper.title,
        classes=tuple(sorted({school_class.name for *_, school_class in rows})),
        reporters=len({student.id for _, _, student, _ in rows}),
        reports=tuple(cards),
        questions=tuple(reported),
    )


class SeenReports(BaseModel):
    """Các báo cáo màn 25 đã hiện cho giáo viên.

    Attributes:
        report_ids: Báo cáo nào. Không phải *mọi báo cáo chưa xem*: một báo cáo đến trong lúc giáo
            viên đang đọc chưa được đọc, nên nó phải ở lại (review pha 1).
    """

    report_ids: list[str] = Field(min_length=1)


@router.post("/teacher/board/reports/{assessment_id}/seen", status_code=204)
async def reports_seen(
    assessment_id: str,
    body: SeenReports,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Đánh dấu đã xem các báo cáo màn 25 đã hiện của một đề (người dùng chốt: theo đề).

    Args:
        assessment_id: Đề nào.
        body: Các báo cáo đã hiện. Id không thuộc đề này bị bỏ qua.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Raises:
        HTTPException: 404 khi đề không tồn tại hoặc thuộc về người khác (ADR-22).

    Side effects:
        Đặt `resolved_at` cho các báo cáo ấy còn chưa xem, rồi commit. Bấm lại không dời mốc.
    """
    await _owned_paper(session, Asking.of(teacher), assessment_id)
    attempts = select(Attempt.id).where(Attempt.assessment_id == assessment_id)
    await session.execute(
        update(Report)
        .where(
            Report.id.in_(body.report_ids),
            Report.attempt_id.in_(attempts),
            Report.resolved_at.is_(None),
        )
        .values(resolved_at=_now())
    )
    await session.commit()
    return Response(status_code=204)


# ------------------------------------------------------------------ màn 29 · câu có tỉ lệ sai cao
# (artboard `29 · Câu có tỉ lệ sai cao`; plan ghi số 26 lúc mở, Figma lấy số 29 vì 26–28 đã có.)


class OptionShare(BaseModel):
    """Một phương án và tỉ lệ chọn nó ở lần làm đầu, trên mọi bài đã nộp."""

    label: str
    text: str
    is_correct: bool
    error_label: str | None
    percent: int


class MethodText(BaseModel):
    title: str
    body: str


class WrongRateQuestion(BaseModel):
    """Màn 29 (`699:5667`): một câu, chỉ đọc, cùng tỉ lệ chọn từng phương án.

    Attributes:
        question_id: Câu nào.
        assessment_id: Đề của câu.
        order: Số câu.
        title: Tên đề.
        stem: Đề bài.
        methods: Các cách giải.
        options: Các phương án, theo nhãn.
        unanswered: Tỉ lệ bài bỏ trống câu này -- cùng mẫu số với `options`, nên các tỉ lệ cộng lại
            đủ 100 (làm tròn từng số thì lệch được một hai điểm).
        submitted: Số bài đã nộp tính tỉ lệ.
        wrong_percent: Tỉ lệ bài sai ở lần đầu.
        classes: Các lớp tính tỉ lệ.
        bank_id: Dòng ngân hàng của câu; rỗng khi chưa có bản.
        seen: Giáo viên đã đánh dấu đã xem.
    """

    question_id: str
    assessment_id: str
    order: int
    title: str
    stem: str
    methods: tuple[MethodText, ...]
    options: tuple[OptionShare, ...]
    unanswered: int
    submitted: int
    wrong_percent: int
    classes: tuple[str, ...]
    bank_id: str
    seen: bool


async def _owned_question(session: AsyncSession, asking: Asking, question_id: str) -> Question:
    question = await session.scalar(
        select(Question)
        .join(Assessment, Assessment.id == Question.assessment_id)
        .where(Question.id == question_id, Assessment.teacher_id == asking.teacher_id)
        .options(selectinload(Question.options), selectinload(Question.methods))
    )
    if question is None:
        raise HTTPException(status_code=404, detail=_NO_QUESTION)
    return question


@router.get("/teacher/board/questions/{question_id}", response_model=WrongRateQuestion)
async def wrong_rate_question(
    question_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> WrongRateQuestion:
    """Một câu của hàng đợi *tỉ lệ sai cao*, chỉ đọc, kèm tỉ lệ chọn từng phương án ở lần đầu.

    Args:
        question_id: Câu nào.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        Màn 29.

    Raises:
        HTTPException: 404 khi câu không thuộc đề nào của giáo viên (ADR-22).
    """
    asking = Asking.of(teacher)
    question = await _owned_question(session, asking, question_id)
    paper = await session.get(Assessment, question.assessment_id)
    counts, graded = _wrong_counts(asking.teacher_id)
    found = (await session.execute(counts.where(graded.c.question_id == question.id))).first()
    total, wrong = (int(found[1]), int(found[2] or 0)) if found else (0, 0)
    # Phương án đã chọn, ở đúng những bài đã tính vào `total`.
    chosen = dict(
        (
            await session.execute(
                select(Answer.option_id, func.count())
                .join(
                    graded,
                    and_(
                        graded.c.id == Answer.attempt_id, graded.c.question_id == Answer.question_id
                    ),
                )
                .where(Answer.question_id == question.id)
                .group_by(Answer.option_id)
            )
        ).all()
    )
    names = sorted(
        set(
            await session.scalars(
                select(SchoolClass.name)
                .join(graded, graded.c.class_id == SchoolClass.id)
                .where(graded.c.question_id == question.id)
                .distinct()
            )
        )
    )
    banks = await _bank_ids(session, paper.teacher_id, [question])
    return WrongRateQuestion(
        question_id=question.id,
        assessment_id=question.assessment_id,
        order=question.order_index,
        title=paper.title,
        stem=question.stem,
        methods=tuple(MethodText(title=one.title, body=one.body) for one in question.methods),
        options=tuple(
            OptionShare(
                label=one.label,
                text=one.text,
                is_correct=one.is_correct,
                error_label=one.error_label,
                percent=_percent(chosen.get(one.id, 0), total),
            )
            for one in question.options
        ),
        unanswered=_percent(total - sum(chosen.values()), total),
        submitted=total,
        wrong_percent=_percent(wrong, total),
        classes=tuple(names),
        bank_id=banks[question.id],
        seen=question.wrong_rate_seen_at is not None,
    )


@router.post("/teacher/board/questions/{question_id}/seen", status_code=204)
async def wrong_rate_seen(
    question_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Đánh dấu đã xem một câu có tỉ lệ sai cao: câu rời hàng đợi mãi.

    Bấm được cả ở câu chưa từng vào hàng đợi: màn 29 mở được từ link, và cờ chỉ nói *giáo viên đã
    xem câu này*. Câu ấy thì không bao giờ vào hàng đợi nữa.

    Args:
        question_id: Câu nào.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Raises:
        HTTPException: 404 khi câu không thuộc đề nào của giáo viên (ADR-22).

    Side effects:
        Đặt `wrong_rate_seen_at` lần đầu, rồi commit. Bấm lại không dời mốc.
    """
    question = await _owned_question(session, Asking.of(teacher), question_id)
    if question.wrong_rate_seen_at is None:
        question.wrong_rate_seen_at = _now()
    await session.commit()
    return Response(status_code=204)


# ------------------------------------------------------------------ hộp đọc đoạn chat


class ChatLine(BaseModel):
    """Một lượt của đoạn chat hỏi trợ lý."""

    role: str
    text: str
    created_at: datetime


class ReportChat(BaseModel):
    """Hộp đọc đoạn chat (artboard 25b): đoạn chat pha 2 của lượt có báo cáo, chỉ đọc.

    Attributes:
        student: Họ tên học sinh.
        title: Tên đề.
        class_name: Lớp của lượt làm bài.
        messages: Theo thứ tự đã nói.
    """

    student: str
    title: str
    class_name: str
    messages: tuple[ChatLine, ...]


@router.get("/teacher/board/chat/{report_id}", response_model=ReportChat)
async def report_chat(
    report_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> ReportChat:
    """Đoạn chat hỏi trợ lý của lượt làm bài có báo cáo này (ADR-19: báo cáo trỏ vào cả đoạn chat).

    Args:
        report_id: Báo cáo nào.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        Hộp đọc đoạn chat.

    Raises:
        HTTPException: 404 khi báo cáo không thuộc đề nào của giáo viên (ADR-22).
    """
    found = (
        await session.execute(
            select(Report, Attempt, Assessment, Student, SchoolClass)
            .join(Attempt, Attempt.id == Report.attempt_id)
            .join(Assessment, Assessment.id == Attempt.assessment_id)
            .join(Student, Student.id == Attempt.student_id)
            .join(SchoolClass, SchoolClass.id == Attempt.class_id)
            .where(Report.id == report_id, Assessment.teacher_id == Asking.of(teacher).teacher_id)
        )
    ).first()
    if found is None:
        raise HTTPException(status_code=404, detail=_NO_REPORT)
    _, attempt, paper, student, school_class = found
    lines = await session.scalars(
        select(ChatMessage)
        .where(ChatMessage.attempt_id == attempt.id)
        .order_by(ChatMessage.sequence)
    )
    return ReportChat(
        student=student.full_name,
        title=paper.title,
        class_name=school_class.name,
        messages=tuple(
            ChatLine(role=one.role, text=one.text, created_at=aware(one.created_at))
            for one in lines
        ),
    )
