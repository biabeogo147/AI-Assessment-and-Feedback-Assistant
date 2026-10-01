"""Mọi bề mặt HTTP mà một học sinh chạm vào.

Ba luật định hình module này, và nói một lần ở đây đáng hơn nhắc lại ở từng route.

Phương án đúng không bao giờ rời khỏi BE trong lúc học sinh còn có thể hành động dựa
trên nó. Nó chỉ xuất hiện sau khi nộp, lúc mà ADR-16 đã biến điểm pha 1 thành một mức
sàn, và dù sao câu hỏi retry cũng là một câu hỏi khác.

Không response nào chở `confidence`, `misconception_code` hay một lý do duyệt (ADR-08).
Error label do giáo viên soạn thì có xuất hiện, nhưng chỉ bên trong hộp thoại lời giải
và trong ngữ cảnh kèm học -- như tài liệu dạy học, không bao giờ như một con số.

Mọi mốc hạn đều được quyết ở đây. Đồng hồ đếm ngược trên màn hình là đồ trang trí; đồng
hồ của server mới là thứ từ chối một câu trả lời muộn và là thứ dừng một round (ADR-15).
"""

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from be.agent_gateway import (
    AgentError,
    ask_for_retry_question,
    collect_result,
    enqueue_task,
    stream_task,
    validate_question,
    validate_retry,
)
from be.config import get_settings
from be.db import get_session
from be.identity import current_student
from be.models import (
    Answer,
    AnswerOption,
    Assessment,
    Attempt,
    ChatMessage,
    PregeneratedItem,
    Publication,
    Question,
    QuestionOutcome,
    RemediationRound,
    Report,
    RoundItem,
    Student,
)
from be.remediation import round_budget_minutes, round_ends_at, will_be_cut
from be.scoring import (
    MAX_ROUNDS_PER_QUESTION,
    MarkReason,
    mark_after_round,
    mark_for_phase_one,
    total,
)
from contracts import (
    EXPLAIN_TURN_TASK,
    GENERATE_RETRY_QUESTION_TASK,
    ChatTurn,
    ExplainTurnCompleted,
    ExplainTurnRequested,
    GeneratedOption,
    GeneratedQuestion,
    RetryQuestionCompleted,
    RetryQuestionRequested,
    SolutionMethod,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["student"])


def _now() -> datetime:
    """Trả về đồng hồ của server, có kèm timezone.

    Returns:
        Thời điểm UTC hiện tại. Mọi phép so sánh mốc hạn trong module này đều đi qua đây,
        để một test chỉ phải lập luận trên một nguồn thời gian duy nhất.
    """
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    """Gắn UTC vào một timestamp đã mất offset của nó khi được lưu.

    SQLite bỏ mất thông tin timezone, nên một giá trị đọc về là naive trong khi cùng giá
    trị đó trên Postgres thì không. So sánh hai hình dạng này với nhau sẽ ném lỗi.

    Args:
        value: Timestamp lấy từ database.

    Returns:
        Đúng khoảnh khắc đó, và được bảo đảm là có timezone.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class OptionOut(BaseModel):
    """Một phương án như học sinh được phép thấy trước khi nộp."""

    option_id: str
    label: str
    text: str


class QuestionOut(BaseModel):
    """Một câu hỏi của Attempt đang chạy."""

    question_id: str
    order: int
    stem: str
    options: list[OptionOut]
    chosen_option_id: str | None = None


class AssignmentOut(BaseModel):
    """Một dòng trong danh sách bài được giao của học sinh."""

    assignment_id: str
    attempt_id: str | None
    title: str
    subject: str
    question_count: int
    phase1_minutes: int
    opens_at: datetime
    closes_at: datetime
    remediation_deadline: datetime
    status: str
    wrong_count: int | None
    actions: list[str]


class AttemptOut(BaseModel):
    """Một Attempt pha 1 vừa được bắt đầu hoặc vừa được làm tiếp."""

    attempt_id: str
    title: str
    started_at: datetime
    ends_at: datetime
    questions: list[QuestionOut]


class SubmitOut(BaseModel):
    """Thứ mà việc kết thúc pha 1 tạo ra."""

    attempt_id: str
    submitted_at: datetime
    phase1_score: float
    question_count: int
    wrong_question_ids: list[str]


class RoundOut(BaseModel):
    """Một mục trong lịch sử remediation của một câu hỏi."""

    index: int
    stem: str
    outcome: str


class ResultItemOut(BaseModel):
    """Một câu hỏi trên bảng điểm."""

    question_id: str
    order: int
    stem: str
    mark: float
    mark_reason: str
    rounds: list[RoundOut]


class ResultOut(BaseModel):
    """Bảng điểm, theo hình dạng mà cả hai màn hình kết quả đều đọc."""

    attempt_id: str
    title: str
    state: str
    total_score: float
    question_count: int
    submitted_at: datetime | None
    remediation_deadline: datetime
    items: list[ResultItemOut]


class ChosenOut(BaseModel):
    """Một phương án được gọi tên bằng label và text, dùng cho panel remediation."""

    label: str
    text: str


class RemediationItemOut(BaseModel):
    """Một câu hỏi học sinh làm sai ở pha 1, theo cách panel trình bày nó.

    Những câu đã đóng vẫn nằm trong danh sách. Panel chính là thứ học sinh đọc lại sau
    khi Attempt kết thúc -- bỏ một câu hỏi ra ngay khoảnh khắc nó an bài sẽ làm trống
    đúng cái màn hình mà trang kết quả gửi em tới.
    """

    question_id: str
    order: int
    stem: str
    chosen: ChosenOut | None
    correct: ChosenOut
    rounds_used: int
    rounds_max: int
    mark: float
    closed: bool


class RemediationOut(BaseModel):
    """Mọi thứ màn hình kèm học cần, ngoài cuộc hội thoại.

    `items` giữ mọi câu hỏi đã sai ở cuối pha 1, đóng hay chưa; còn `open_count` là số
    câu vẫn còn cần một round. Giao diện cần cả hai: một cái để vẽ danh sách, cái kia để
    đặt chữ cho cái nút mở một round và để đếm phần còn lại.
    """

    attempt_id: str
    state: str
    deadline: datetime
    minutes_per_question: int
    round_budget_minutes: int
    open_count: int
    can_start_round: bool
    warn_cut: bool
    open_round_id: str | None
    items: list[RemediationItemOut]


class SolutionOptionOut(BaseModel):
    """Một phương án bên trong hộp thoại lời giải, kèm lỗi sai do giáo viên soạn."""

    label: str
    text: str
    is_correct: bool
    error_label: str | None


class SolutionMethodOut(BaseModel):
    """Một lời giải chi tiết."""

    title: str
    body: str


class SolutionOut(BaseModel):
    """Hộp thoại lời giải cho một câu hỏi."""

    question_id: str
    stem: str
    methods: list[SolutionMethodOut]
    options: list[SolutionOptionOut]


class ChatMessageOut(BaseModel):
    """Một lượt của cuộc hội thoại đã được lưu."""

    message_id: str
    role: str
    text: str
    created_at: datetime


class ChatHistoryOut(BaseModel):
    """Cuộc hội thoại, kèm việc nó còn nhận input hay không."""

    attempt_id: str
    locked: bool
    messages: list[ChatMessageOut]


class ChatPostIn(BaseModel):
    """Một message của học sinh."""

    text: str


class ChatPostOut(BaseModel):
    """Đọc câu trả lời ở đâu."""

    message_id: str
    stream_url: str


class RoundItemOut(BaseModel):
    """Một câu hỏi bên trong một round đang chạy.

    `origin_order` là số thứ tự mà câu hỏi mang trên đề, và đó là thứ màn hình hiển thị.
    Nếu thay vào đó đánh số round theo 1..n thì một học sinh làm sai câu 5 và câu 6 sẽ
    được bảo rằng em đang ở "câu 1" -- trong khi cuộc hội thoại ngay bên cạnh nói là
    câu 5.
    """

    round_item_id: str
    origin_question_id: str
    origin_order: int
    order: int
    stem: str
    options: list[OptionOut]
    chosen_label: str | None


class RoundOpenOut(BaseModel):
    """Một round mà học sinh giờ được phép trả lời."""

    round_id: str
    index: int
    ends_at: datetime
    items: list[RoundItemOut]


class RoundResultItemOut(BaseModel):
    """Một câu hỏi dừng lại ở đâu sau round này."""

    question_id: str
    outcome: str
    new_mark: float
    rounds_used: int
    rounds_left: int


class RoundResultOut(BaseModel):
    """Phán quyết cho một round đã nộp."""

    round_id: str
    per_question: list[RoundResultItemOut]
    attempt_state: str


class AnswerIn(BaseModel):
    """Một lựa chọn đã được lưu."""

    option_id: str


class RoundAnswerIn(BaseModel):
    """Một lựa chọn đã lưu bên trong một round, được gọi tới bằng label."""

    label: str


class SavedOut(BaseModel):
    """Xác nhận rằng một lựa chọn đã được lưu."""

    saved_at: datetime


class ReportIn(BaseModel):
    """Một ghi chú tuỳ chọn gắn kèm một báo cáo."""

    note: str | None = None


class ReportOut(BaseModel):
    """Xác nhận rằng một báo cáo đã được ghi nhận."""

    report_id: str


class MeOut(BaseModel):
    """Danh tính để hiển thị trên thanh trên cùng."""

    student_id: str
    full_name: str
    class_name: str
    student_code: str


async def _load_assessment(session: AsyncSession, assessment_id: str) -> Assessment:
    """Load một đề cùng với câu hỏi, phương án và lời giải của nó.

    Args:
        session: Session của database.
        assessment_id: Đề nào.

    Returns:
        Đề đó.

    Raises:
        HTTPException: 404 khi nó không tồn tại.
    """
    found = await session.scalar(
        select(Assessment)
        .where(Assessment.id == assessment_id)
        .options(
            selectinload(Assessment.questions).selectinload(Question.options),
            selectinload(Assessment.questions).selectinload(Question.methods),
        )
    )
    if found is None:
        raise HTTPException(status_code=404, detail=f"No assessment {assessment_id}")
    return found


async def _owned_attempt(session: AsyncSession, attempt_id: str, student: Student) -> Attempt:
    """Load một Attempt và từ chối nó với bất kỳ ai không phải chủ của nó.

    Args:
        session: Session của database.
        attempt_id: Attempt nào.
        student: Người gọi.

    Returns:
        Attempt đó.

    Raises:
        HTTPException: 404 khi nó không tồn tại hoặc thuộc về người khác. Không phải
            403: nói cho một người lạ biết rằng một id là thật thì đã là một lần rò rỉ.
    """
    found = await session.get(Attempt, attempt_id)
    if found is None or found.student_id != student.id:
        raise HTTPException(status_code=404, detail=f"No attempt {attempt_id}")
    return found


async def _publication(session: AsyncSession, assessment_id: str, class_id: str) -> Publication:
    """Load các điều kiện phát hành chi phối lượt làm một đề của một lớp.

    Giờ cần cả hai nửa của khoá. Một đề được phát hành theo từng lớp, mỗi lớp một cái
    đồng hồ riêng -- 12A buổi sáng, 12B sau giờ trưa -- nên "điều kiện của đề này" không
    phải một câu hỏi có một đáp án.

    Args:
        session: Session của database.
        assessment_id: Đề nào.
        class_id: Điều kiện của lớp nào. Với một Attempt, đây là lớp mà Attempt được bắt
            đầu trong đó, không phải lớp của học sinh ngày hôm nay.

    Returns:
        Dòng Publication của cặp đó.

    Raises:
        HTTPException: 404 khi đề chưa bao giờ được phát hành cho lớp đó, mà với một học
            sinh thì chuyện đó không phân biệt được với việc đề không tồn tại.
    """
    found = await session.get(Publication, (assessment_id, class_id))
    if found is None:
        raise HTTPException(status_code=404, detail="Bài này chưa được phát hành")
    return found


async def _open_round(session: AsyncSession, attempt_id: str) -> RemediationRound | None:
    """Trả về round chưa nộp của một Attempt, nếu nó có.

    Dùng `.one_or_none()` chứ không dùng `.first()`: nhiều nhất một round được mở, một
    partial unique index ép điều đó, và nếu chuyện đó có lúc nào gãy thì hàm này phải ném
    lỗi chứ không được âm thầm chọn một dòng rồi che dòng kia đi.

    Args:
        session: Session của database.
        attempt_id: Attempt nào.

    Returns:
        Round đang mở, hoặc None.

    Raises:
        MultipleResultsFound: Nếu hai round cùng mở một lúc, nghĩa là database này đang
            thiếu cái index đó.
    """
    found = await session.scalars(
        select(RemediationRound).where(
            RemediationRound.attempt_id == attempt_id, RemediationRound.submitted_at.is_(None)
        )
    )
    return found.one_or_none()


async def _outcomes(session: AsyncSession, attempt_id: str) -> dict[str, QuestionOutcome]:
    """Đọc sổ điểm của một Attempt, khoá theo câu hỏi.

    Args:
        session: Session của database.
        attempt_id: Attempt nào.

    Returns:
        Các dòng outcome, theo question id.
    """
    rows = await session.scalars(
        select(QuestionOutcome).where(QuestionOutcome.attempt_id == attempt_id)
    )
    return {row.question_id: row for row in rows}


def _attempt_state(
    outcomes: dict[str, QuestionOutcome],
    submitted: bool,
    deadline: datetime,
    now: datetime,
) -> str:
    """Quyết định hình dạng nào của màn hình kết quả được áp dụng.

    Args:
        outcomes: Sổ điểm.
        submitted: Pha 1 đã kết thúc hay chưa.
        deadline: Hạn của pha 2.
        now: Thời gian của server.

    Returns:
        "đang-làm", "cần-chữa", "đã-hoàn-thành" hoặc "hết-hạn-chữa". ADR-14 làm cho đây
        là những hình dạng khác nhau, chứ không phải một hình dạng với các field rỗng.
    """
    if not submitted:
        return "đang-làm"
    if all(outcome.closed for outcome in outcomes.values()):
        return "đã-hoàn-thành"
    if now > deadline:
        return "hết-hạn-chữa"
    return "cần-chữa"


def _attempt_payload(attempt: Attempt, assessment: Assessment, saved: dict[str, str]) -> AttemptOut:
    """Tạo hình dạng của một Attempt cho màn hình làm bài.

    Dùng chung cho cả việc bắt đầu và việc làm tiếp, nhờ vậy hai đường đó không thể trôi
    dạt thành hiển thị hai thứ khác nhau -- và đặc biệt là không đường nào mọc thêm một
    `is_correct`.

    Args:
        attempt: Dòng Attempt.
        assessment: Đề của nó, đã load câu hỏi và phương án.
        saved: Id phương án đã chọn, theo từng question id.

    Returns:
        Payload, với mọi phương án đã được bóc bỏ đáp án.
    """
    return AttemptOut(
        attempt_id=attempt.id,
        title=assessment.title,
        started_at=_aware(attempt.started_at),
        ends_at=_aware(attempt.ends_at),
        questions=[
            QuestionOut(
                question_id=question.id,
                order=question.order_index,
                stem=question.stem,
                options=[
                    OptionOut(option_id=option.id, label=option.label, text=option.text)
                    for option in question.options
                ],
                chosen_option_id=saved.get(question.id),
            )
            for question in assessment.questions
        ],
    )


@router.get("/me", response_model=MeOut)
async def me(
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    """Báo người gọi là ai, cho dải danh tính mà mọi màn hình đều chở theo.

    Args:
        student: Người gọi.
        session: Session của database.

    Returns:
        Tên, lớp và mã học sinh -- ba thứ mà ADR-13 đòi phải có trên một máy dùng chung
        trong lớp học.
    """
    loaded = await session.scalar(
        select(Student).where(Student.id == student.id).options(selectinload(Student.school_class))
    )
    assert loaded is not None
    return MeOut(
        student_id=loaded.id,
        full_name=loaded.full_name,
        class_name=loaded.school_class.name,
        student_code=loaded.student_code,
    )


@router.get("/me/assignments", response_model=list[AssignmentOut])
async def my_assignments(
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> list[AssignmentOut]:
    """Liệt kê những bài được giao của lớp mà người gọi đang học.

    Status được tính ở đây từ đồng hồ của server, chứ không gửi ra dưới dạng ngày thô để
    client tự diễn giải: nếu không, hai máy có đồng hồ lệch nhau sẽ hiển thị hai state
    khác nhau cho cùng một bài được giao.

    Args:
        student: Người gọi.
        session: Session của database.

    Returns:
        Một dòng cho mỗi đề đã phát hành cho lớp này, mới nhất lên trước.
    """
    now = _now()
    publications = await session.scalars(
        select(Publication).where(Publication.class_id == student.class_id)
    )

    rows: list[AssignmentOut] = []
    for publication in publications:
        assessment = await _load_assessment(session, publication.assessment_id)
        attempt = await session.scalar(
            select(Attempt).where(
                Attempt.assessment_id == assessment.id, Attempt.student_id == student.id
            )
        )
        opens_at = _aware(publication.opens_at)
        closes_at = _aware(publication.closes_at)
        deadline = _aware(publication.remediation_deadline)

        wrong_count: int | None = None
        actions: list[str] = []

        if attempt is None:
            if now < opens_at:
                status = "chưa-tới-giờ-mở"
            elif now > closes_at:
                status = "đã-đóng"
            else:
                status = "đang-mở"
                actions = ["start"]
        elif attempt.submitted_at is None:
            status = "đang-làm"
            actions = ["continue"]
        else:
            outcomes = await _outcomes(session, attempt.id)
            wrong_count = sum(1 for outcome in outcomes.values() if not outcome.closed)
            status = _attempt_state(outcomes, True, deadline, now)
            actions = ["result", "remediate"] if status == "cần-chữa" else ["result"]

        rows.append(
            AssignmentOut(
                assignment_id=assessment.id,
                attempt_id=attempt.id if attempt else None,
                title=assessment.title,
                subject=assessment.subject,
                question_count=len(assessment.questions),
                phase1_minutes=publication.phase1_minutes,
                opens_at=opens_at,
                closes_at=closes_at,
                remediation_deadline=deadline,
                status=status,
                wrong_count=wrong_count,
                actions=actions,
            )
        )

    rows.sort(key=lambda row: row.opens_at, reverse=True)
    return rows


@router.post("/assignments/{assessment_id}/attempts", response_model=AttemptOut, status_code=201)
async def start_attempt(
    assessment_id: str,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> AttemptOut:
    """Bắt đầu pha 1, hoặc trả lại chính Attempt đang làm giữa dở.

    Args:
        assessment_id: Đề nào.
        student: Người gọi.
        session: Session của database.

    Returns:
        Attempt cùng các câu hỏi của nó, phương án đã bóc bỏ đáp án.

    Raises:
        HTTPException: 409 khi chưa tới giờ mở, khi đã qua giờ đóng, hoặc khi pha 1 đã
            được nộp.

    Side effects:
        Tạo một dòng Attempt ở lần gọi đầu tiên.
    """
    # Attempt trước, vì nó mới là thứ quyết định điều kiện nào được áp. Tra Publication
    # trước nó -- với lớp của ngày hôm nay -- có nghĩa là cửa vào bị áp lại lên một bài
    # đang làm giữa dở: một học sinh chuyển từ lớp buổi sáng sang lớp buổi chiều bị bảo
    # "chưa tới giờ mở" về chính phần việc nửa vời của em, hoặc "chưa được phát hành" khi
    # lớp mới chẳng có Publication nào. ADR-03 cấm đúng chuyện đó, nhìn từ phía bên kia:
    # "Học sinh đã vào rồi thì không bị dừng giữa chừng."
    attempt = await session.scalar(
        select(Attempt).where(
            Attempt.assessment_id == assessment_id, Attempt.student_id == student.id
        )
    )
    if attempt is not None and attempt.submitted_at is not None:
        raise HTTPException(status_code=409, detail="Bài này đã nộp")

    governing_class = attempt.class_id if attempt is not None else student.class_id
    publication = await _publication(session, assessment_id, governing_class)
    assessment = await _load_assessment(session, assessment_id)
    now = _now()

    if attempt is None:
        # Cửa này canh việc vào, và chỉ canh việc vào.
        if now < _aware(publication.opens_at):
            raise HTTPException(status_code=409, detail="Chưa tới giờ mở")
        if now > _aware(publication.closes_at):
            raise HTTPException(status_code=409, detail="Đã quá hạn vào làm bài")

        attempt = Attempt(
            assessment_id=assessment_id,
            student_id=student.id,
            class_id=student.class_id,
            started_at=now,
            ends_at=min(
                now + timedelta(minutes=publication.phase1_minutes),
                _aware(publication.closes_at) + timedelta(minutes=publication.phase1_minutes),
            ),
        )
        session.add(attempt)
        try:
            await session.commit()
        except IntegrityError:
            # Hai tab cùng bấm bắt đầu một lúc. Unique constraint đã giữ cho dữ liệu
            # đúng; chỗ này biến cú va chạm đó thành đúng câu trả lời mà tab thứ hai dù
            # sao cũng muốn -- chính cái Attempt đã tồn tại.
            await session.rollback()
            attempt = await session.scalar(
                select(Attempt).where(
                    Attempt.assessment_id == assessment_id, Attempt.student_id == student.id
                )
            )
            if attempt is None:
                raise

    saved = {
        row.question_id: row.option_id
        for row in await session.scalars(select(Answer).where(Answer.attempt_id == attempt.id))
    }

    return _attempt_payload(attempt, assessment, saved)


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
async def resume_attempt(
    attempt_id: str,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> AttemptOut:
    """Đọc lại một Attempt đang làm giữa dở, kèm những lựa chọn đã lưu.

    Tải lại trang không được tốn gì cả. Bắt đầu một Attempt là một POST vì nó tạo ra một
    cái; còn quay lại với nó là cái GET này, nhờ vậy một lần refresh không thể bị nhầm
    thành một lần bắt đầu thứ hai.

    Args:
        attempt_id: Attempt nào.
        student: Người gọi.
        session: Session của database.

    Returns:
        Attempt cùng các câu hỏi của nó, phương án đã bóc bỏ đáp án.

    Raises:
        HTTPException: 404 khi Attempt không phải của người gọi; 409 khi pha 1 đã được
            nộp, vì bài đó không còn trả lời được nữa.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is not None:
        raise HTTPException(status_code=409, detail="Bài này đã nộp")

    assessment = await _load_assessment(session, attempt.assessment_id)
    saved = {
        row.question_id: row.option_id
        for row in await session.scalars(select(Answer).where(Answer.attempt_id == attempt.id))
    }
    return _attempt_payload(attempt, assessment, saved)


@router.put("/attempts/{attempt_id}/answers/{question_id}", response_model=SavedOut)
async def save_answer(
    attempt_id: str,
    question_id: str,
    body: AnswerIn,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> SavedOut:
    """Lưu một lựa chọn của pha 1.

    Args:
        attempt_id: Attempt nào.
        question_id: Câu hỏi nào.
        body: Phương án đã chọn.
        student: Người gọi.
        session: Session của database.

    Returns:
        Lựa chọn đã được lưu vào lúc nào.

    Raises:
        HTTPException: 409 sau mốc hạn của chính Attempt đó hoặc khi nó đã nộp; 400 khi
            phương án thuộc về một câu hỏi khác.

    Side effects:
        Insert hoặc update một dòng answer.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is not None:
        raise HTTPException(status_code=409, detail="Bài đã nộp")
    now = _now()
    if now > _aware(attempt.ends_at):
        raise HTTPException(status_code=409, detail="Hết giờ làm bài")

    option = await session.get(AnswerOption, body.option_id)
    if option is None or option.question_id != question_id:
        raise HTTPException(status_code=400, detail="Phương án không thuộc câu này")

    existing = await session.scalar(
        select(Answer).where(Answer.attempt_id == attempt_id, Answer.question_id == question_id)
    )
    if existing is None:
        session.add(
            Answer(
                attempt_id=attempt_id,
                question_id=question_id,
                option_id=body.option_id,
                saved_at=now,
            )
        )
    else:
        existing.option_id = body.option_id
        existing.saved_at = now
    await session.commit()
    return SavedOut(saved_at=now)


@router.post("/attempts/{attempt_id}/submit", response_model=SubmitOut)
async def submit_attempt(
    attempt_id: str,
    request: Request,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> SubmitOut:
    """Kết thúc pha 1 và chấm mọi câu hỏi.

    Việc chấm chỉ là một phép so sánh và chạy ngay trong dòng (ADR-20), nên không có state
    "đang được chấm" nào nằm giữa lần gọi này và bảng điểm.

    Args:
        attempt_id: Attempt nào.
        student: Người gọi.
        session: Session của database.

    Returns:
        Điểm sàn và những câu hỏi còn đang mở.

    Raises:
        HTTPException: 409 khi pha 1 đã được nộp rồi.

    Side effects:
        Ghi sổ điểm và đóng mốc thời gian nộp lên Attempt.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is not None:
        raise HTTPException(status_code=409, detail="Bài này đã nộp")

    assessment = await _load_assessment(session, attempt.assessment_id)
    chosen = {
        row.question_id: row.option_id
        for row in await session.scalars(select(Answer).where(Answer.attempt_id == attempt_id))
    }

    now = _now()
    wrong: list[str] = []
    marks: list[float] = []
    for question in assessment.questions:
        correct_id = next(option.id for option in question.options if option.is_correct)
        is_correct = chosen.get(question.id) == correct_id
        mark, reason, closed = mark_for_phase_one(is_correct)
        marks.append(mark)
        if not closed:
            wrong.append(question.id)
        session.add(
            QuestionOutcome(
                attempt_id=attempt_id,
                question_id=question.id,
                mark=mark,
                reason=reason.value,
                rounds_used=0,
                closed=closed,
            )
        )

    attempt.submitted_at = now
    await session.commit()

    # Bước chạy trước. Viết câu hỏi của một round tốn của model gần hai mươi giây, và
    # ADR-14 đưa học sinh tới màn hình kèm học trước khi em mở được một round -- vài phút
    # đọc và hỏi. Khởi động ngay lúc này có nghĩa là thời gian chờ được tiêu vào một việc
    # em tự chọn làm. Không có gì ở đây được await để lấy câu trả lời, và không có gì ở
    # đây có thể làm cho lần nộp bài thất bại.
    await _write_ahead(
        session,
        request.app.state.queue_pool,
        attempt_id,
        [question for question in assessment.questions if question.id in set(wrong)],
        chosen,
        round_index=1,
    )

    return SubmitOut(
        attempt_id=attempt_id,
        submitted_at=now,
        phase1_score=total(marks),
        question_count=len(assessment.questions),
        wrong_question_ids=wrong,
    )


@router.get("/attempts/{attempt_id}/result", response_model=ResultOut)
async def attempt_result(
    attempt_id: str,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> ResultOut:
    """Trả về bảng điểm, kèm cả câu hỏi của từng round retry.

    Câu hỏi của chính một round được in ra vì nó là một câu hỏi khác với câu gốc (ADR-17);
    một bảng điểm chỉ hiện stem của pha 1 sẽ cho học sinh 0.5 mà không nói em đã làm đúng
    cái gì.

    Args:
        attempt_id: Attempt nào.
        student: Người gọi.
        session: Session của database.

    Returns:
        Một dòng cho mỗi câu hỏi, mỗi dòng kèm các round của nó.

    Raises:
        HTTPException: 409 trong lúc pha 1 vẫn còn đang chạy.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is None:
        raise HTTPException(status_code=409, detail="Bài chưa nộp")

    assessment = await _load_assessment(session, attempt.assessment_id)
    publication = await _publication(session, attempt.assessment_id, attempt.class_id)
    outcomes = await _outcomes(session, attempt_id)

    rounds = await session.scalars(
        select(RemediationRound)
        .where(RemediationRound.attempt_id == attempt_id)
        .options(selectinload(RemediationRound.items))
        .order_by(RemediationRound.index)
    )
    history: dict[str, list[RoundOut]] = {}
    for rnd in rounds:
        if rnd.submitted_at is None:
            continue
        for item in rnd.items:
            history.setdefault(item.origin_question_id, []).append(
                RoundOut(index=rnd.index, stem=item.stem, outcome=item.outcome or "chưa-trả-lời")
            )

    items = [
        ResultItemOut(
            question_id=question.id,
            order=question.order_index,
            stem=question.stem,
            mark=outcomes[question.id].mark,
            mark_reason=outcomes[question.id].reason,
            rounds=history.get(question.id, []),
        )
        for question in assessment.questions
        if question.id in outcomes
    ]

    return ResultOut(
        attempt_id=attempt_id,
        title=assessment.title,
        state=_attempt_state(outcomes, True, _aware(publication.remediation_deadline), _now()),
        total_score=total([item.mark for item in items]),
        question_count=len(items),
        submitted_at=_aware(attempt.submitted_at),
        remediation_deadline=_aware(publication.remediation_deadline),
        items=items,
    )


@router.get("/attempts/{attempt_id}/remediation", response_model=RemediationOut)
async def remediation_panel(
    attempt_id: str,
    request: Request,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> RemediationOut:
    """Trả về mọi câu hỏi còn mở, kèm thứ đã chọn và thứ đáng ra là đúng.

    `warn_cut` được tính ở đây chứ không để client tính: so budget của round với thời gian
    còn lại là luật của ADR-15, và nó chọn ra hình dạng nào của cửa vào round sẽ xuất hiện.

    Args:
        attempt_id: Attempt nào.
        student: Người gọi.
        session: Session của database.

    Returns:
        Payload của panel cho màn hình kèm học.

    Raises:
        HTTPException: 409 trong lúc pha 1 vẫn còn đang chạy.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is None:
        raise HTTPException(status_code=409, detail="Bài chưa nộp")

    assessment = await _load_assessment(session, attempt.assessment_id)
    publication = await _publication(session, attempt.assessment_id, attempt.class_id)
    outcomes = await _outcomes(session, attempt_id)
    chosen = {
        row.question_id: row.option_id
        for row in await session.scalars(select(Answer).where(Answer.attempt_id == attempt_id))
    }

    items: list[RemediationItemOut] = []
    for question in assessment.questions:
        outcome = outcomes.get(question.id)
        if outcome is None or outcome.reason == MarkReason.CORRECT_FIRST_TRY:
            continue
        picked = next((o for o in question.options if o.id == chosen.get(question.id)), None)
        correct = next(o for o in question.options if o.is_correct)
        items.append(
            RemediationItemOut(
                question_id=question.id,
                order=question.order_index,
                stem=question.stem,
                chosen=ChosenOut(label=picked.label, text=picked.text) if picked else None,
                correct=ChosenOut(label=correct.label, text=correct.text),
                rounds_used=outcome.rounds_used,
                rounds_max=MAX_ROUNDS_PER_QUESTION,
                mark=outcome.mark,
                closed=outcome.closed,
            )
        )

    open_count = sum(1 for item in items if not item.closed)
    now = _now()
    deadline = _aware(publication.remediation_deadline)

    budget = round_budget_minutes(publication.phase2_minutes_per_question, open_count)
    open_round = await _open_round(session, attempt_id)

    # Màn hình này là nơi học sinh tiêu thời gian chờ, nên đây cũng là nơi phần việc đã
    # xong được harvest. BE không có background worker nào; một kết quả không ai nhặt lên
    # là một kết quả sẽ hết hạn.
    pool = request.app.state.queue_pool
    await _harvest(session, pool, attempt_id)

    # Không có gì được viết trước trong lúc một round đang mở, và chính cái chốt đó là
    # toàn bộ lý do `open_round` được đọc trước khối này chứ không phải sau. `rounds_used`
    # không nhích cho tới khi round được nộp, nên trong lúc một round đang chạy thì index
    # tiếp theo vẫn đọc ra là index của round *hiện tại* -- mà round đó đã có câu hỏi của
    # nó rồi. Mọi job đẩy vào queue ở đây sẽ được trả lời, được lưu, không bao giờ được
    # dùng, và thành mồ côi ngay khoảnh khắc round được nộp. Màn hình round gọi endpoint
    # này lúc mount, nên đó là một lần cho mỗi round, cho mỗi câu còn mở, để chẳng được gì.
    still_open = [
        question
        for question in assessment.questions
        if (outcome := outcomes.get(question.id)) is not None and not outcome.closed
    ]
    if still_open and open_round is None and now < deadline:
        await _write_ahead(
            session,
            pool,
            attempt_id,
            still_open,
            chosen,
            round_index=max(outcomes[q.id].rounds_used for q in still_open) + 1,
            spent=await _spent_stems(session, attempt_id),
        )

    return RemediationOut(
        attempt_id=attempt_id,
        state=_attempt_state(outcomes, True, deadline, now),
        deadline=deadline,
        minutes_per_question=publication.phase2_minutes_per_question,
        round_budget_minutes=budget,
        open_count=open_count,
        can_start_round=open_count > 0 and now < deadline and open_round is None,
        warn_cut=open_count > 0 and will_be_cut(now, budget, deadline),
        open_round_id=open_round.id if open_round else None,
        items=items,
    )


@router.get("/questions/{question_id}/solution", response_model=SolutionOut)
async def question_solution(
    question_id: str,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> SolutionOut:
    """Trả về các lời giải chi tiết và phần mapping Distractor do giáo viên soạn.

    Args:
        question_id: Câu hỏi nào.
        student: Người gọi.
        session: Session của database.

    Returns:
        Payload của hộp thoại lời giải.

    Raises:
        HTTPException: 404 khi câu hỏi không nằm trong một đề mà học sinh này có Attempt;
            409 trong lúc Attempt đó còn chưa nộp, vì đáp án đúng nằm trong payload này.
    """
    question = await session.scalar(
        select(Question)
        .where(Question.id == question_id)
        .options(selectinload(Question.options), selectinload(Question.methods))
    )
    if question is None:
        raise HTTPException(status_code=404, detail=f"No question {question_id}")

    attempt = await session.scalar(
        select(Attempt).where(
            Attempt.assessment_id == question.assessment_id, Attempt.student_id == student.id
        )
    )
    if attempt is None:
        raise HTTPException(status_code=404, detail=f"No question {question_id}")
    if attempt.submitted_at is None:
        raise HTTPException(status_code=409, detail="Lời giải chỉ mở sau khi nộp bài")

    return SolutionOut(
        question_id=question.id,
        stem=question.stem,
        methods=[SolutionMethodOut(title=m.title, body=m.body) for m in question.methods],
        options=[
            SolutionOptionOut(
                label=o.label, text=o.text, is_correct=o.is_correct, error_label=o.error_label
            )
            for o in question.options
        ],
    )


async def _chat_context(
    session: AsyncSession, attempt: Attempt
) -> tuple[list[GeneratedQuestion], list[int], dict[str, str], dict[str, str]]:
    """Dựng những gì AGENT cần để nói về Attempt này.

    Payload này tự chứa đủ: AGENT không giữ credential nào của database, nên các câu hỏi,
    các error label do giáo viên soạn và những lựa chọn của học sinh đều đi theo job.

    Args:
        session: Session của database.
        attempt: Attempt đang được bàn tới.

    Returns:
        Những câu hỏi còn mở, số thứ tự mà từng câu mang trên đề, label phương án đã chọn
        theo từng stem, và error label do giáo viên soạn theo từng stem. Những số thứ tự
        đi theo vì trợ lý nói "câu 5" ra miệng, và nó không có cách nào khác để biết câu
        hỏi đó là câu thứ năm.
    """
    assessment = await _load_assessment(session, attempt.assessment_id)
    outcomes = await _outcomes(session, attempt.id)
    chosen = {
        row.question_id: row.option_id
        for row in await session.scalars(select(Answer).where(Answer.attempt_id == attempt.id))
    }

    questions: list[GeneratedQuestion] = []
    numbers: list[int] = []
    chosen_labels: dict[str, str] = {}
    error_labels: dict[str, str] = {}

    for question in assessment.questions:
        outcome = outcomes.get(question.id)
        if outcome is None or outcome.closed:
            continue
        questions.append(
            GeneratedQuestion(
                stem=question.stem,
                options=tuple(
                    GeneratedOption(
                        label=o.label,
                        text=o.text,
                        is_correct=o.is_correct,
                        error_label=o.error_label,
                    )
                    for o in question.options
                ),
                methods=tuple(SolutionMethod(title=m.title, body=m.body) for m in question.methods),
                learning_objective=question.learning_objective,
            )
        )
        numbers.append(question.order_index)
        picked = next((o for o in question.options if o.id == chosen.get(question.id)), None)
        if picked is not None:
            chosen_labels[question.stem] = picked.label
            if picked.error_label:
                error_labels[question.stem] = picked.error_label

    return questions, numbers, chosen_labels, error_labels


async def _history(session: AsyncSession, attempt_id: str) -> list[ChatMessage]:
    """Đọc cuộc hội thoại đã lưu theo đúng thứ tự.

    Args:
        session: Session của database.
        attempt_id: Attempt nào.

    Returns:
        Các message, cũ nhất lên trước.
    """
    rows = await session.scalars(
        select(ChatMessage)
        .where(ChatMessage.attempt_id == attempt_id)
        .order_by(ChatMessage.sequence)
    )
    return list(rows)


async def _is_locked(session: AsyncSession, attempt: Attempt) -> bool:
    """Cho biết cuộc hội thoại có còn nhận input hay không.

    Args:
        session: Session của database.
        attempt: Attempt đó.

    Returns:
        True khi mọi câu hỏi đã đóng, hoặc khi hạn của pha 2 đã đi qua. Một cuộc hội thoại
        đã khoá thì vẫn đọc được -- đó chính là toàn bộ ý nghĩa của hình dạng "đã xong" của
        màn hình kèm học.
    """
    publication = await _publication(session, attempt.assessment_id, attempt.class_id)
    outcomes = await _outcomes(session, attempt.id)
    state = _attempt_state(
        outcomes, attempt.submitted_at is not None, _aware(publication.remediation_deadline), _now()
    )
    return state in {"đã-hoàn-thành", "hết-hạn-chữa"}


@router.get("/attempts/{attempt_id}/chat", response_model=ChatHistoryOut)
async def chat_history(
    attempt_id: str,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> ChatHistoryOut:
    """Trả về cuộc hội thoại, và việc nó còn mở hay không.

    Args:
        attempt_id: Attempt nào.
        student: Người gọi.
        session: Session của database.

    Returns:
        Các message đã lưu, cũ nhất lên trước, kèm cờ khoá mà màn hình "đã xong" đọc.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    messages = await _history(session, attempt_id)
    return ChatHistoryOut(
        attempt_id=attempt_id,
        locked=await _is_locked(session, attempt),
        messages=[
            ChatMessageOut(
                message_id=m.id, role=m.role, text=m.text, created_at=_aware(m.created_at)
            )
            for m in messages
        ],
    )


@router.post("/attempts/{attempt_id}/chat/messages", response_model=ChatPostOut, status_code=202)
async def post_chat_message(
    attempt_id: str,
    body: ChatPostIn,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> ChatPostOut:
    """Lưu lượt của học sinh và nói câu trả lời sẽ tới ở đâu.

    Args:
        attempt_id: Attempt nào.
        body: Nội dung message. Rỗng được cho phép đúng một lần, để kéo lượt mở đầu của
            trợ lý về.
        student: Người gọi.
        session: Session của database.

    Returns:
        Id message đã lưu và stream để đọc câu trả lời.

    Raises:
        HTTPException: 409 trong lúc pha 1 chưa nộp, hoặc khi Attempt đã kết thúc.

    Side effects:
        Insert một dòng chat.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is None:
        raise HTTPException(status_code=409, detail="Phần chữa mở sau khi nộp bài")
    if await _is_locked(session, attempt):
        raise HTTPException(status_code=409, detail="Bài đã kết thúc")

    history = await _history(session, attempt_id)
    text = body.text.strip()
    if text:
        message = ChatMessage(
            attempt_id=attempt_id,
            sequence=len(history) + 1,
            role="student",
            text=text,
            created_at=_now(),
        )
        session.add(message)
        await session.commit()
        message_id = message.id
    else:
        message_id = "opening"

    return ChatPostOut(
        message_id=message_id,
        stream_url=f"/api/attempts/{attempt_id}/chat/stream",
    )


def _retry_ask(
    attempt_id: str,
    question: Question,
    picked_option_id: str | None,
    round_index: int,
    previous_stems: tuple[str, ...],
) -> RetryQuestionRequested:
    """Dựng lời yêu cầu cho round tiếp theo của một câu hỏi.

    Một chỗ duy nhất, vì giờ lời yêu cầu đó được tạo từ hai nơi: viết trước lúc bài được
    nộp, và viết ngay tại chỗ khi không có câu đã sinh trước. Hai bản sao sẽ trôi dạt khỏi
    nhau, và thứ chúng trôi dạt về chính là điều AGENT được kể về lỗi sai của học sinh.

    Args:
        attempt_id: Attempt của ai.
        question: Câu hỏi pha 1 đang được remediation, đã load phương án.
        picked_option_id: Thứ học sinh đã chọn, hoặc None nếu không chọn gì.
        round_index: Đây sẽ là round thứ mấy, đếm từ 1.
        previous_stems: Những stem đã dùng cho câu hỏi này.

    Returns:
        Lời yêu cầu, sẵn sàng để serialise.
    """
    picked = next((o for o in question.options if o.id == picked_option_id), None)
    origin = GeneratedQuestion(
        stem=question.stem,
        options=tuple(
            GeneratedOption(
                label=o.label, text=o.text, is_correct=o.is_correct, error_label=o.error_label
            )
            for o in question.options
        ),
        methods=tuple(SolutionMethod(title=m.title, body=m.body) for m in question.methods),
        learning_objective=question.learning_objective,
    )
    return RetryQuestionRequested(
        request_id=f"{attempt_id}:{question.id}:{round_index}",
        origin=origin,
        wrong_option_label=picked.label if picked else "",
        error_label=picked.error_label if picked else None,
        round_index=round_index,
        previous_stems=previous_stems,
    )


async def _round_item(
    session: AsyncSession,
    rnd: RemediationRound,
    question: Question,
    order: int,
    generated: GeneratedQuestion,
) -> RoundItemOut:
    """Lưu một câu hỏi của một round và mô tả nó cho client.

    Dùng chung cho cả hai đường mà một câu hỏi có thể tới -- viết trước, hay viết ngay tại
    chỗ -- vì thứ được lưu xuống không được phép phụ thuộc vào việc nó được viết lúc nào.
    Phương án đúng được giữ ở phía server, và đó là thứ cho phép BE chấm round mà không
    phải hỏi AGENT bất cứ điều gì (ADR-20).

    Args:
        session: Session của database. Được flush, không commit.
        rnd: Round đang được mở.
        question: Câu hỏi pha 1 đang được remediation.
        order: Vị trí trong round này, tính từ 1.
        generated: Câu hỏi sẽ được đặt ra.

    Returns:
        Góc nhìn của client về nó, đã bỏ phần đáp án.
    """
    item = RoundItem(
        round_id=rnd.id,
        origin_question_id=question.id,
        order_index=order,
        stem=generated.stem,
        options=[option.model_dump() for option in generated.options],
        methods=[method.model_dump() for method in generated.methods],
    )
    session.add(item)
    await session.flush()
    return RoundItemOut(
        round_item_id=item.id,
        origin_question_id=question.id,
        origin_order=question.order_index,
        order=order,
        stem=generated.stem,
        options=[
            OptionOut(option_id=option.label, label=option.label, text=option.text)
            for option in generated.options
        ],
        chosen_label=None,
    )


async def _spent_stems(session: AsyncSession, attempt_id: str) -> dict[str, list[str]]:
    """Đọc lại xem Attempt này đã dùng những stem nào, theo từng câu hỏi.

    Args:
        session: Session của database.
        attempt_id: Attempt của ai.

    Returns:
        question_id -> những stem đã được đặt ra cho nó.
    """
    rows = await session.scalars(
        select(RoundItem)
        .join(RemediationRound, RoundItem.round_id == RemediationRound.id)
        .where(RemediationRound.attempt_id == attempt_id)
    )
    spent: dict[str, list[str]] = {}
    for row in rows:
        spent.setdefault(row.origin_question_id, []).append(row.stem)
    return spent


async def _harvest(session: AsyncSession, pool: object, attempt_id: str) -> None:
    """Chuyển những job đã xong vào bảng, và quên đi những job đã hết hạn.

    Được gọi từ chính những màn hình học sinh đi qua trong lúc phần việc đang chạy, vì BE
    không có background worker nào và một kết quả không ai harvest là một kết quả sẽ hết
    hạn. Kết quả của job sống một giờ; hạn của pha 2 có thể cách đó nhiều ngày, nên "câu
    trả lời đã mất" là một cái kết bình thường, không phải một trường hợp góc.

    Một dòng đã mất thì bị **xoá** chứ không bị đánh cờ, và điều đó để lại đúng một luật
    cho phần ghi ở dưới: một câu hỏi không có dòng cho round nó cần thì được đẩy một job
    vào queue. Khi đó "chưa bao giờ bắt đầu" và "đã bắt đầu nhưng mất" đi cùng một đường,
    và không có state thứ ba nào phải lập luận về. Còn một job *đã chạy và thất bại* thì
    được giữ lại và được đánh dấu, vì hỏi lại sẽ nhận đúng cái thất bại đó -- và một dòng
    cứ bị xoá là một job cứ bị đẩy lại vào queue, mỗi lần học sinh mở một màn hình, suốt
    chừng nào cái bug còn đó.

    **Mọi thứ được kiểm ở đây, trên đường vào.** ADR-18 và ADR-17 từng được ép trong
    `ask_for_retry_question`, mà chỉ đường viết-ngay-tại-chỗ đi qua đó -- nên việc viết
    trước sẽ âm thầm trở thành một lối đi vòng qua chúng, và từ pha này trở đi, viết trước
    mới là đường *bình thường*, không phải fallback. Một câu hỏi không đạt thì bị bỏ, và
    việc đó đưa nó về lại queue theo đúng cái luật duy nhất đã dùng cho một câu bị mất.

    Args:
        session: Session của database. Được hàm này commit.
        pool: Pool arq, hoặc None.
        attempt_id: Attempt của ai.

    Side effects:
        Điền vào, đánh dấu, hoặc xoá các dòng.
    """
    settings = get_settings()
    waiting = list(
        await session.scalars(
            select(PregeneratedItem).where(
                PregeneratedItem.attempt_id == attempt_id,
                PregeneratedItem.status == "pending",
            )
        )
    )
    if not waiting:
        return

    spent = await _spent_stems(session, attempt_id)
    origins = {
        question.id: question.stem
        for question in await session.scalars(
            select(Question).where(Question.id.in_({row.origin_question_id for row in waiting}))
        )
    }

    changed = False
    for row in waiting:
        state, raw = await collect_result(pool, settings, row.job_id)
        if state == "pending":
            continue
        changed = True

        if state == "failed":
            logger.warning("pregenerated job %s failed inside AGENT", row.job_id)
            row.status = "failed"
            continue

        if state == "gone":
            logger.info("pregenerated job %s aged out; asking again", row.job_id)
            await session.delete(row)
            continue

        question = RetryQuestionCompleted.model_validate(raw).question
        try:
            validate_question(question)
            validate_retry(
                question,
                origins.get(row.origin_question_id, ""),
                spent.get(row.origin_question_id, []),
            )
        except AgentError as exc:
            logger.warning("pregenerated question rejected: %s", exc)
            await session.delete(row)
            continue

        row.stem = question.stem
        row.options = [option.model_dump() for option in question.options]
        row.methods = [method.model_dump() for method in question.methods]
        row.status = "ready"

    if changed:
        await session.commit()


async def _write_ahead(
    session: AsyncSession,
    pool: object,
    attempt_id: str,
    questions: list[Question],
    chosen: dict[str, str],
    round_index: int,
    spent: dict[str, list[str]] | None = None,
) -> None:
    """Đẩy vào queue câu hỏi của round tiếp theo cho mọi câu còn mở mà chưa có.

    Không ai chờ việc này. Một queue đang chết chỉ làm mất bước chạy trước và không mất gì
    khác: `start_round` vẫn viết một câu hỏi ngay tại chỗ khi không có câu nào được sinh
    trước, đúng như nó đã làm trước khi mọi thứ này tồn tại.

    Args:
        session: Session của database. Được hàm này commit.
        pool: Pool arq, hoặc None.
        attempt_id: Attempt của ai.
        questions: Những câu hỏi còn mở.
        chosen: question_id -> option_id, thứ học sinh đã chọn ở pha 1.
        round_index: Round nào đang được viết.
        spent: Những stem đã dùng theo từng câu hỏi, khi có.

    Side effects:
        Đẩy một job vào queue cho mỗi câu hỏi cần, và insert một dòng `pending` cho mỗi
        câu đó.
    """
    settings = get_settings()
    already = set(
        await session.scalars(
            select(PregeneratedItem.origin_question_id).where(
                PregeneratedItem.attempt_id == attempt_id,
                PregeneratedItem.round_index == round_index,
            )
        )
    )

    for question in questions:
        if question.id in already:
            continue

        ask = _retry_ask(
            attempt_id,
            question,
            chosen.get(question.id),
            round_index,
            tuple((spent or {}).get(question.id, ())),
        )
        job_id = await enqueue_task(
            pool, settings, GENERATE_RETRY_QUESTION_TASK, ask.model_dump(mode="json")
        )
        if job_id is None:
            continue

        session.add(
            PregeneratedItem(
                attempt_id=attempt_id,
                origin_question_id=question.id,
                round_index=round_index,
                job_id=job_id,
                status="pending",
                created_at=_now(),
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            # Hai tab poll ở đúng cùng một khoảnh khắc và cả hai đều lọt qua lần kiểm ở
            # trên. Dòng kia tốt y như dòng này.
            await session.rollback()


# Những lời đầu tiên của trợ lý. Cố định một cách có chủ ý: chỗ này từng đi qua model như
# mọi lượt khác -- một job, một lần chờ, một stream -- để tạo ra một câu gần như không
# thay đổi. Một lần gọi model bỏ đi trên mỗi bài được nộp. Phần duy nhất khác nhau giữa
# hai học sinh là các em sai những câu nào, và đó là việc format string, không phải thứ
# đáng đi hỏi một model.
_GREETING = (
    "Mình là trợ lý Kriky, bạn có thể hỏi mình để giải đáp các thắc mắc trong bài làm vừa rồi."
)


def _greeting(numbers: tuple[int, ...] | list[int]) -> str:
    """Viết lượt mở đầu.

    Args:
        numbers: Số thứ tự trên đề của từng câu học sinh làm sai, theo thứ tự.

    Returns:
        Lời chào, có gọi tên những câu đó để học sinh biết mình được mời cái gì trước khi
        em hỏi.
    """
    if not numbers:
        return _GREETING

    said = [f"câu {number}" for number in numbers]
    if len(said) == 1:
        return f"{_GREETING} Bài này bạn sai {said[0]} — nó đang ở bảng bên phải."

    # "câu 3, câu 5 và câu 7" -- kiểu liệt kê bằng dấu phẩy mà tiếng Việt thật sự dùng,
    # không phải "và" giữa từng cặp. Và "cả hai" chỉ đúng khi có đúng hai câu, mà đó là
    # thứ dữ liệu mẫu đang có, nên cũng là thứ dễ mặc định sai theo.
    named = f"{', '.join(said[:-1])} và {said[-1]}"
    how_many = "cả hai" if len(said) == 2 else "tất cả"
    return (
        f"{_GREETING} Bài này bạn sai {named} — {how_many} đang ở bảng bên phải, "
        "hỏi câu nào trước cũng được."
    )


def _event(name: str, text: str) -> str:
    """Viết một server-sent event.

    Một dòng `data:` không được chứa newline, mà một model đang viết văn xuôi thì sinh ra
    rất nhiều newline. Định dạng trên đường truyền cho chuyện đó không phải thứ ta được
    tự phát minh: SSE nói hãy lặp lại field đó, và phía đọc nối các dòng lại với newline
    ở giữa.

    Args:
        name: Tên event -- `chunk`, `done` hoặc `error`.
        text: Payload, kể cả các newline trong đó.

    Returns:
        Một event hoàn chỉnh, kết thúc bằng một dòng trống.
    """
    body = "\n".join(f"data: {line}" for line in text.split("\n"))
    return f"event: {name}\n{body}\n\n"


def _sse(text: str, message_id: str) -> AsyncIterator[str]:
    """Biến một lượt trọn vẹn thành một stream server-sent event.

    Dùng khi câu trả lời tới nguyên một cục: một lượt được phát lại, hoặc một model không
    stream. Từng chữ được rót ra ở đây, nhờ vậy cả hai đường trông giống nhau với phía đọc.

    Args:
        text: Lời của trợ lý.
        message_id: Message đã lưu, được gửi kèm event đóng để client đối chiếu được với
            lịch sử mà nó tải lại.

    Returns:
        Một async iterator yield một event `chunk` cho mỗi từ, rồi `done`.
    """

    async def events() -> AsyncIterator[str]:
        for word in text.split(" "):
            yield _event("chunk", word + " ")
        yield _event("done", message_id)

    return events()


def _replay(message: ChatMessage) -> AsyncIterator[str]:
    """Stream lại một lượt đã có sẵn, thay vì đi xin một lượt mới.

    Args:
        message: Lượt của trợ lý được lưu gần nhất.

    Returns:
        Đúng cái stream event mà một lượt mới cũng sẽ tạo ra.
    """
    return _sse(message.text, message.id)


@router.get("/attempts/{attempt_id}/chat/stream")
async def stream_reply(
    attempt_id: str,
    request: Request,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Stream lượt tiếp theo của trợ lý, từng chữ một.

    Lượt đó được đi xin, được **lưu**, rồi mới được stream. Server-sent event là chất xúc
    tác cho cảm giác về câu trả lời, không phải một nguồn sự thật thứ hai: một lần mất kết
    nối làm mất phần hoạt ảnh, không bao giờ làm mất message.

    Args:
        attempt_id: Attempt nào.
        request: Dùng để với tới pool arq dùng chung.
        student: Người gọi.
        session: Session của database.

    Returns:
        Một text/event-stream gồm các event `chunk` rồi tới `done`.

    Raises:
        HTTPException: 409 trong lúc pha 1 chưa nộp hoặc khi Attempt đã kết thúc; 503 khi
            không tới được AGENT.

    Side effects:
        Đẩy một job của AGENT vào queue và insert một dòng chat.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is None:
        raise HTTPException(status_code=409, detail="Phần chữa mở sau khi nộp bài")
    if await _is_locked(session, attempt):
        raise HTTPException(status_code=409, detail="Bài đã kết thúc")

    history = await _history(session, attempt_id)
    # Đang là lượt của ai, do phía server quyết. Nếu không, một client mở stream hai lần
    # -- một effect bị render đôi, một lần refresh vì mất kiên nhẫn -- sẽ lưu hai lời
    # chào, và cuộc hội thoại đọc ra như thể trợ lý chào xong rồi chào lại lần nữa.
    if history and history[-1].role != "student":
        return StreamingResponse(_replay(history[-1]), media_type="text/event-stream")

    questions, numbers, chosen_labels, error_labels = await _chat_context(session, attempt)
    last_student = next((m.text for m in reversed(history) if m.role == "student"), "")

    if not history:
        # Lượt mở đầu không bao giờ tới AGENT. Xem `_greeting`: nó là một câu cố định cộng
        # với một danh sách số, và trả tiền cho một model để viết nó một lần trên mỗi bài
        # thì chẳng mua được gì.
        opening = ChatMessage(
            attempt_id=attempt_id,
            sequence=1,
            role="assistant",
            text=_greeting(numbers),
            created_at=_now(),
        )
        #
        # Cái chốt ở trên không giúp được gì ở đây: nó cần một lịch sử để đọc, mà cả hai
        # request đang đua đều thấy một lịch sử rỗng. StrictMode của React mở stream này
        # hai lần một cách có chủ ý, nên đây là trường hợp bình thường chứ không phải
        # trường hợp xui. Unique index là thứ quyết định, và bên thua thì phát lại.
        session.add(opening)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await _history(session, attempt_id)
            if existing:
                return StreamingResponse(_replay(existing[0]), media_type="text/event-stream")
            # Thua cuộc đua và không đọc được dòng của bên thắng từ session này. Vô hại:
            # lời chào là cùng một câu dù theo đường nào, nên học sinh vẫn đọc đúng thứ đã
            # được lưu mà không có dòng thứ hai nào bị ghi.
            return StreamingResponse(_sse(opening.text, "opening"), media_type="text/event-stream")
        return StreamingResponse(_sse(opening.text, opening.id), media_type="text/event-stream")

    pool = request.app.state.queue_pool
    if pool is None:
        # Cái lỗi duy nhất biết được trước khi stream mở ra, nên nó vẫn được một status
        # code chứ không phải một event mà chẳng ai tạo kiểu hiển thị cho.
        raise HTTPException(
            status_code=503, detail="Trợ lý chưa trả lời được: hàng đợi chưa sẵn sàng"
        )

    channel = f"aiafa:stream:{uuid4().hex}"
    payload = ExplainTurnRequested(
        request_id=attempt_id,
        questions=tuple(questions),
        question_numbers=tuple(numbers),
        chosen_labels=chosen_labels,
        error_labels=error_labels,
        history=tuple(ChatTurn(role=m.role, text=m.text) for m in history),
        student_text=last_student if history and history[-1].role == "student" else "",
        stream_channel=channel,
    )
    settings = get_settings()

    async def events() -> AsyncIterator[str]:
        """Chuyển tiếp câu trả lời ngay khi nó được viết, rồi lưu nó lại.

        Việc lưu xảy ra khi câu trả lời đã trọn vẹn, tức là sau khi mảnh cuối cùng đã đi
        ra. Vì vậy một học sinh đóng tab giữa lúc đang trả lời chỉ làm tốn một lần gọi
        model và lần sau nhận một lượt mới -- lượt đó không bao giờ bị lưu nửa vời, và
        cũng không bao giờ bị lưu hai lần.
        """
        spoke = False
        reply: ExplainTurnCompleted | None = None
        try:
            async for kind, value in stream_task(
                pool,
                settings,
                EXPLAIN_TURN_TASK,
                payload.model_dump(mode="json"),
                channel,
                settings.stream_silence_timeout_seconds,
            ):
                if kind == "chunk":
                    spoke = True
                    yield _event("chunk", str(value))
                else:
                    reply = ExplainTurnCompleted.model_validate(value)
        except AgentError as exc:
            # Quá muộn cho một 503: response đã bắt đầu ngay khoảnh khắc generator này bắt
            # đầu. Thay vào đó, client được nói cho biết ngay trong stream.
            yield _event("error", f"Trợ lý chưa trả lời được: {exc}")
            return

        if reply is None:
            yield _event("error", "Trợ lý chưa trả lời được")
            return

        stored = ChatMessage(
            attempt_id=attempt_id,
            sequence=len(history) + 1,
            role="assistant",
            text=reply.text,
            created_at=_now(),
        )
        session.add(stored)
        await session.commit()

        if not spoke:
            # Không có gì được publish -- nội dung đã soạn sẵn, hoặc một provider không
            # stream. Nói cả cục ra ngay bây giờ. Làm việc này sau khi đã có mảnh nào đi
            # ra rồi sẽ hiển thị cùng những chữ đó hai lần.
            async for event in _sse(reply.text, stored.id):
                yield event
            return

        yield _event("done", stored.id)

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/attempts/{attempt_id}/rounds", response_model=RoundOpenOut, status_code=201)
async def start_round(
    attempt_id: str,
    request: Request,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> RoundOpenOut:
    """Mở một round remediation phủ mọi câu hỏi còn mở.

    Args:
        attempt_id: Attempt nào.
        request: Dùng để với tới pool arq dùng chung.
        student: Người gọi.
        session: Session của database.

    Returns:
        Round đó, với một câu hỏi được sinh ra cho mỗi câu còn mở.

    Raises:
        HTTPException: 409 khi đã qua hạn pha 2, khi không còn gì phải chữa, hoặc khi đang
            có một round khác mở; 503 khi không tới được AGENT hoặc khi AGENT trả về một
            câu hỏi phạm ADR-18.

    Side effects:
        Đẩy một job của AGENT vào queue cho mỗi câu còn mở, và ghi round xuống.
    """
    attempt = await _owned_attempt(session, attempt_id, student)
    if attempt.submitted_at is None:
        raise HTTPException(status_code=409, detail="Bài chưa nộp")

    publication = await _publication(session, attempt.assessment_id, attempt.class_id)
    deadline = _aware(publication.remediation_deadline)
    now = _now()
    if now >= deadline:
        raise HTTPException(status_code=409, detail="Đã hết hạn chữa bài")

    if await _open_round(session, attempt_id) is not None:
        raise HTTPException(status_code=409, detail="Đang có một lượt chưa nộp")

    assessment = await _load_assessment(session, attempt.assessment_id)
    outcomes = await _outcomes(session, attempt_id)
    open_questions = [q for q in assessment.questions if not outcomes[q.id].closed]
    if not open_questions:
        raise HTTPException(status_code=409, detail="Không còn câu nào phải làm lại")

    index = (
        1
        + (
            await session.scalar(
                select(RemediationRound)
                .where(RemediationRound.attempt_id == attempt_id)
                .order_by(RemediationRound.index.desc())
                .limit(1)
            )
            or RemediationRound(index=0)
        ).index
    )

    budget = round_budget_minutes(publication.phase2_minutes_per_question, len(open_questions))
    rnd = RemediationRound(
        attempt_id=attempt_id,
        index=index,
        started_at=now,
        ends_at=round_ends_at(now, budget, deadline),
    )
    session.add(rnd)
    try:
        await session.flush()
    except IntegrityError as exc:
        # Lần kiểm ở trên cho cả hai tab đi qua; chỉ có index là thứ chỉ cho một tab lọt.
        # Hai cái đồng hồ cho một học sinh là một state mà ADR-15 không gán cho ý nghĩa nào.
        await session.rollback()
        raise HTTPException(status_code=409, detail="Đang có một lượt chưa nộp") from exc

    spent = await _spent_stems(session, attempt_id)
    chosen = {
        row.question_id: row.option_id
        for row in await session.scalars(select(Answer).where(Answer.attempt_id == attempt_id))
    }

    # Mọi thứ mà bước chạy trước đã làm xong thì lúc này đã nằm trong bảng; lần gọi này
    # bắt lấy những gì vừa đáp xuống trong những khoảnh khắc cuối trước khi nút được bấm.
    pool = request.app.state.queue_pool
    await _harvest(session, pool, attempt_id)
    ready = {
        row.origin_question_id: row
        for row in await session.scalars(
            select(PregeneratedItem).where(
                PregeneratedItem.attempt_id == attempt_id,
                PregeneratedItem.status == "ready",
            )
        )
    }

    items: list[RoundItemOut] = []
    for order, question in enumerate(open_questions, start=1):
        waiting = ready.get(question.id)
        if waiting is not None and waiting.round_index == outcomes[question.id].rounds_used + 1:
            generated = GeneratedQuestion(
                stem=waiting.stem,
                options=tuple(GeneratedOption(**option) for option in waiting.options),
                methods=tuple(SolutionMethod(**method) for method in waiting.methods),
                learning_objective=question.learning_objective,
            )
            await session.delete(waiting)
            items.append(await _round_item(session, rnd, question, order, generated))
            continue

        # Không có gì được viết trước, hoặc thứ viết trước lại thuộc về một round khác.
        # Con đường cũ, không đổi: hỏi ngay bây giờ và để học sinh ngồi chờ.
        ask = _retry_ask(
            attempt_id,
            question,
            chosen.get(question.id),
            outcomes[question.id].rounds_used + 1,
            tuple(spent.get(question.id, ())),
        )
        try:
            generated = await ask_for_retry_question(
                pool,
                get_settings(),
                ask,
                question.stem,
                spent.get(question.id, []),
            )
        except AgentError as exc:
            raise HTTPException(
                status_code=503, detail=f"Chưa sinh được đề lượt này: {exc}"
            ) from exc

        item = RoundItem(
            round_id=rnd.id,
            origin_question_id=question.id,
            order_index=order,
            stem=generated.stem,
            options=[o.model_dump() for o in generated.options],
            methods=[m.model_dump() for m in generated.methods],
        )
        session.add(item)
        await session.flush()
        items.append(
            RoundItemOut(
                round_item_id=item.id,
                origin_question_id=question.id,
                origin_order=question.order_index,
                order=order,
                stem=generated.stem,
                options=[
                    OptionOut(option_id=o.label, label=o.label, text=o.text)
                    for o in generated.options
                ],
                chosen_label=None,
            )
        )

    await session.commit()
    return RoundOpenOut(round_id=rnd.id, index=rnd.index, ends_at=_aware(rnd.ends_at), items=items)


async def _owned_round(
    session: AsyncSession, round_id: str, student: Student
) -> tuple[RemediationRound, Attempt]:
    """Load một round và Attempt mà nó thuộc về, từ chối round của học sinh khác.

    Args:
        session: Session của database.
        round_id: Round nào.
        student: Người gọi.

    Returns:
        Round đó và Attempt của nó.

    Raises:
        HTTPException: 404 khi round không tồn tại hoặc không phải của người gọi.
    """
    rnd = await session.scalar(
        select(RemediationRound)
        .where(RemediationRound.id == round_id)
        .options(selectinload(RemediationRound.items))
    )
    if rnd is None:
        raise HTTPException(status_code=404, detail=f"No round {round_id}")
    attempt = await _owned_attempt(session, rnd.attempt_id, student)
    return rnd, attempt


@router.put("/rounds/{round_id}/answers/{item_id}", response_model=SavedOut)
async def save_round_answer(
    round_id: str,
    item_id: str,
    body: RoundAnswerIn,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> SavedOut:
    """Lưu một lựa chọn bên trong một round đang chạy.

    Args:
        round_id: Round nào.
        item_id: Câu hỏi nào của round đó.
        body: Label đã chọn.
        student: Người gọi.
        session: Session của database.

    Returns:
        Lựa chọn đã được lưu vào lúc nào.

    Raises:
        HTTPException: 409 khi round đã nộp hoặc đồng hồ của nó đã chạy hết; 404 khi item
            không thuộc round này.

    Side effects:
        Update một round item.
    """
    rnd, _ = await _owned_round(session, round_id, student)
    if rnd.submitted_at is not None:
        raise HTTPException(status_code=409, detail="Lượt đã nộp")
    now = _now()
    if now > _aware(rnd.ends_at):
        raise HTTPException(status_code=409, detail="Lượt đã DỪNG vì hết giờ")

    item = next((i for i in rnd.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"No item {item_id}")

    item.chosen_label = body.label
    await session.commit()
    return SavedOut(saved_at=now)


@router.post("/rounds/{round_id}/submit", response_model=RoundResultOut)
async def submit_round(
    round_id: str,
    request: Request,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> RoundResultOut:
    """Chấm một round và dịch chuyển mục sổ điểm của từng câu hỏi.

    Một câu trả lời đúng thì đóng ở nửa điểm; một câu đã hết round thì đóng ở không; mọi
    trường hợp khác vẫn mở để còn một round nữa. Điểm không bao giờ tụt, vì pha 1 đã đặt
    mức sàn (ADR-16).

    Args:
        round_id: Round nào.
        student: Người gọi.
        session: Session của database.

    Returns:
        Từng câu hỏi dừng lại ở đâu, và state của Attempt.

    Raises:
        HTTPException: 409 khi round đã được nộp rồi.

    Side effects:
        Đóng mốc thời gian lên round, ghi outcome lên các item của nó, cập nhật sổ điểm.
    """
    rnd, attempt = await _owned_round(session, round_id, student)
    if rnd.submitted_at is not None:
        raise HTTPException(status_code=409, detail="Lượt này đã nộp")

    outcomes = await _outcomes(session, attempt.id)
    now = _now()
    results: list[RoundResultItemOut] = []

    for item in rnd.items:
        correct_label = next((o["label"] for o in item.options if o.get("is_correct")), None)
        is_correct = item.chosen_label is not None and item.chosen_label == correct_label
        item.outcome = "đúng" if is_correct else "sai"

        outcome = outcomes[item.origin_question_id]
        if outcome.closed:
            # Đã an bài từ một round trước. Chấm lại nó có thể mở lại một câu đã đóng, mà
            # một câu hỏi chỉ đóng một lần.
            continue
        outcome.rounds_used += 1
        mark, reason, closed = mark_after_round(is_correct, outcome.rounds_used)
        outcome.mark = max(outcome.mark, mark)
        outcome.reason = reason.value
        outcome.closed = closed

        results.append(
            RoundResultItemOut(
                question_id=item.origin_question_id,
                outcome=item.outcome,
                new_mark=outcome.mark,
                rounds_used=outcome.rounds_used,
                rounds_left=max(0, MAX_ROUNDS_PER_QUESTION - outcome.rounds_used),
            )
        )

    rnd.submitted_at = now
    await session.commit()

    publication = await _publication(session, attempt.assessment_id, attempt.class_id)

    # Vẫn bước chạy trước đó, nhưng cho round sau round này. Một học sinh làm sai sắp quay
    # lại màn hình kèm học, và đó một lần nữa là nơi việc chờ diễn ra.
    still_open = [
        question
        for question in (await _load_assessment(session, attempt.assessment_id)).questions
        if (outcome := outcomes.get(question.id)) is not None and not outcome.closed
    ]
    if still_open and now < _aware(publication.remediation_deadline):
        chosen = {
            row.question_id: row.option_id
            for row in await session.scalars(select(Answer).where(Answer.attempt_id == attempt.id))
        }
        await _write_ahead(
            session,
            request.app.state.queue_pool,
            attempt.id,
            still_open,
            chosen,
            round_index=max(outcomes[q.id].rounds_used for q in still_open) + 1,
            spent=await _spent_stems(session, attempt.id),
        )

    return RoundResultOut(
        round_id=round_id,
        per_question=results,
        attempt_state=_attempt_state(outcomes, True, _aware(publication.remediation_deadline), now),
    )


@router.post("/attempts/{attempt_id}/reports", response_model=ReportOut, status_code=201)
async def file_report(
    attempt_id: str,
    body: ReportIn,
    student: Student = Depends(current_student),
    session: AsyncSession = Depends(get_session),
) -> ReportOut:
    """Ghi nhận một báo cáo kiểu "trợ lý giải thích khó theo".

    Báo cáo có phạm vi là Attempt, không phải một message: trợ lý làm việc trên cả đề, nên
    chỉ vào một lượt duy nhất sẽ hứa với giáo viên một thứ hẹp hơn điều đã xảy ra (ADR-19).
    Nó không chặn gì cả.

    Args:
        attempt_id: Attempt nào.
        body: Một ghi chú tuỳ chọn.
        student: Người gọi.
        session: Session của database.

    Returns:
        Id của báo cáo đã lưu.

    Side effects:
        Insert một dòng report.
    """
    await _owned_attempt(session, attempt_id, student)
    report = Report(attempt_id=attempt_id, note=body.note, created_at=_now())
    session.add(report)
    await session.commit()
    return ReportOut(report_id=report.id)
