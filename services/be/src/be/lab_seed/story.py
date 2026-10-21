"""Dựng câu chuyện của lab: năm giáo viên, ba mươi lớp, một nghìn học sinh, đề ở mọi trạng thái.

Mỗi giáo viên có chín đề, mỗi đề đứng ở một chặng mà đường thật để lại (`_PLANS`): từ nháp, qua đã
duyệt và sắp mở, tới đang làm pha 1, đang chữa và đã xong. Không có gì gán thẳng một trạng thái hay
một điểm: state đi qua `advance`, mọi `QuestionOutcome` đi qua `be.scoring`, mọi đề đã duyệt có bản
trong ngân hàng (`file_approved`, ADR-28). Nên seed không dựng được một màn mà người dùng thật không
bao giờ thấy.

Một `random.Random` đã gieo hạt quyết mọi thứ ngẫu nhiên; chỉ mốc thời gian đi theo `now`.
"""

import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from be.accounts import next_student_codes, next_teacher_code, usernames_for
from be.assessment_state import advance
from be.lab_seed.papers import TOPICS, Item, Option, Topic, Twin
from be.lab_seed.people import STAFF, student_names
from be.lab_seed.retries import twins
from be.question_bank import file_approved
from be.remediation import round_budget_minutes, round_ends_at
from be.scoring import mark_after_round, mark_for_phase_one
from be.student_routes import greeting
from schema.models import (
    Answer,
    AnswerOption,
    Assessment,
    AssessmentState,
    Attempt,
    ChatMessage,
    Method,
    Publication,
    Question,
    QuestionOutcome,
    RemediationRound,
    Report,
    RoundItem,
    SchoolClass,
    Student,
    Teacher,
    new_id,
)

STUDENTS = 1000
GRADES = ("10", "11", "12")
# Giờ Việt Nam, cố định: trường không đổi giờ theo mùa, và `zoneinfo` trên Windows cần gói tzdata.
_VN = timezone(timedelta(hours=7))
_MAX_ROUNDS = 3


@dataclass(frozen=True)
class _Plan:
    """Một đề trong chín đề của mỗi giáo viên.

    Attributes:
        kind: Chặng của đề, cũng là khoá đếm trong `LabSummary.papers`.
        grade: Khối của đề và của các lớp nhận nó.
        topic: Bộ câu thứ mấy của khối (`papers.TOPICS`).
        title: Tiền tố tên đề.
        classes: Phát hành cho mấy lớp của khối ấy; 0 là chưa phát hành.
        days: Đề mở cách hôm nay bao nhiêu ngày (âm là quá khứ); đề *đang làm* mở 30 phút trước
            nên không dùng.
        hard: Thứ tự (từ 0) của một câu làm khó hơn hẳn, để *tỉ lệ sai cao* của bảng theo dõi có
            một dòng thật; `None` là không có.
    """

    kind: str
    grade: str
    topic: int
    title: str
    classes: int = 0
    days: int = 0
    hard: int | None = None


# Tiền tố khác nhau cho mỗi đề cùng chủ đề: một giáo viên không đặt hai đề trùng tên, và hàng đợi
# của bảng theo dõi chỉ ghi tên đề -- hai tên trùng là hai dòng không phân biệt nổi.
_PLANS = (
    _Plan("nháp", "10", 0, "Đề nháp"),
    _Plan("đang soạn", "11", 1, "Ôn tập chương"),
    _Plan("đã duyệt", "12", 1, "Luyện tập"),
    _Plan("sắp mở", "10", 1, "Kiểm tra 15 phút", classes=2, days=1),
    _Plan("thu hồi một lớp", "11", 0, "Ôn tập", classes=2, days=3),
    _Plan("đang làm", "12", 0, "Kiểm tra 15 phút", classes=1),
    _Plan("đang chữa", "11", 1, "Kiểm tra 15 phút", classes=2, days=-3),
    _Plan("đã xong", "10", 0, "Kiểm tra 15 phút", classes=2, days=-10),
    _Plan("đã xong", "12", 1, "Kiểm tra 15 phút", classes=2, days=-24, hard=2),
)
# Sáu câu trắc nghiệm là một bài 15 phút.
_MINUTES = 15

# (em hỏi, trợ lý đáp). Trợ lý xưng "mình", gọi "bạn" -- như lời chào thật
# (`student_routes.greeting`) -- và gợi hướng chứ không chép phép tính ra đáp số. Chỗ trống:
# {n} số câu, {objective} mục kiến thức, {first}/{second} tên hai cách giải, {error} nhãn lỗi của
# phương án em đã chọn.
_EXCHANGES = (
    (
        "Em chưa hiểu bước này lắm, giải thích lại giúp em được không ạ?",
        "Mình đi lại từng bước câu {n} nhé. Dạng này thường làm theo hướng “{first}”. Bạn viết "
        "bước đầu tiên ra nháp, rồi so với lựa chọn của mình xem lệch ở đâu.",
    ),
    (
        "Sao đáp án của em lại sai ạ?",
        "Lựa chọn của bạn ở câu {n} khớp với một lỗi hay gặp: {error}. Bạn xem lại đúng bước ấy "
        "trong bài làm nhé.",
    ),
    (
        "Cho em xin một ví dụ tương tự với ạ.",
        "Ở lượt làm lại, bạn sẽ gặp một câu cùng dạng {objective} nhưng khác số. Trước đó, bạn thử "
        "đọc lại cách “{second}” ở bảng bên phải nhé.",
    ),
    (
        "Em làm theo cách khác thì có được không ạ?",
        "Được chứ, miễn là từng bước đúng. Câu {n} có hai hướng: “{first}” và “{second}”. Bạn đang "
        "làm theo hướng nào?",
    ),
    (
        "Bước đầu tiên em nên làm gì ạ?",
        "Với dạng {objective}, bạn bắt đầu theo hướng “{first}”: xác định đúng công thức cần dùng "
        "rồi mới thay số.",
    ),
)
# Câu em để trống thì không có nhãn lỗi nào để nói tới.
_BLANK = "để trống câu này, nên nó được tính là sai"

# --- A7: đủ lời để hai em trong một lớp không viết y hệt nhau; `None` là em không ghi gì.
_REPORT_NOTES = (
    "Giải thích hơi khó hiểu ạ.",
    "Phần ví dụ không giống bài của em.",
    "Em đọc mấy lần vẫn chưa hiểu bước biến đổi.",
    "Trợ lý giải thích nhanh quá, em không theo kịp.",
    "Em hỏi một câu mà trợ lý lại giải thích câu khác.",
    "Lời giải dùng công thức em chưa được học.",
    "Em không hiểu vì sao lại đổi dấu ở bước đó.",
    "Giải thích dài quá, em bị rối.",
    "Em muốn xem lời giải từng bước cụ thể hơn.",
    None,
)


@dataclass
class LabSummary:
    """Những gì seed vừa dựng, để in ra cho người chạy.

    Attributes:
        teachers: (họ tên, SĐT, email) của từng giáo viên.
        classes: Số lớp.
        students: Số học sinh.
        papers: Số đề theo chặng.
        attempts: Số lượt làm bài.
        sample_students: (lớp, tên đăng nhập) của học sinh đầu tiên mỗi lớp.
    """

    teachers: list[tuple[str, str, str]] = field(default_factory=list)
    classes: int = 0
    students: int = 0
    papers: Counter = field(default_factory=Counter)
    attempts: int = 0
    sample_students: list[tuple[str, str]] = field(default_factory=list)


async def seed_lab(
    session: AsyncSession, password_hash: str, now: datetime, *, seed: int = 2026
) -> LabSummary:
    """Dựng toàn bộ dữ liệu lab vào một database rỗng.

    Args:
        session: Session của database. Database phải chưa có lớp nào; người gọi kiểm.
        password_hash: Một mật khẩu đã băm, gán cho **mọi** tài khoản (lab, người dùng chốt
            20/10/2026; plan `lab-deploy-aws`, D4). Băm một lần thay vì một nghìn lần.
        now: Mốc "bây giờ", tz-aware; mọi lịch mở, hạn và lượt làm tính quanh nó.
        seed: Hạt của nguồn ngẫu nhiên.

    Returns:
        Bản tóm tắt để in.

    Side effects:
        Insert giáo viên, lớp, học sinh, đề, câu, phát hành, lượt làm, vòng chữa, chat, báo cáo,
        bản ngân hàng; rồi commit.
    """
    rng = random.Random(seed)
    summary = LabSummary()
    teachers = await _teachers(session, password_hash, summary)
    classes = await _classes(session, teachers, summary)
    roster = await _students(session, rng, classes, password_hash, summary)
    for teacher in teachers:
        for plan in _PLANS:
            chosen = classes[teacher.id][plan.grade][: plan.classes]
            await _paper(session, rng, now, teacher, plan, chosen, roster, summary)
    await session.commit()
    return summary


async def _teachers(
    session: AsyncSession, password_hash: str, summary: LabSummary
) -> list[Teacher]:
    teachers = []
    for staff in STAFF:
        teacher = Teacher(
            full_name=staff.full_name,
            teacher_code=await next_teacher_code(session),
            phone=staff.phone,
            email=staff.email,
            password_hash=password_hash,
        )
        session.add(teacher)
        # Flush từng người: `next_teacher_code` đọc mã lớn nhất đã có trong database.
        await session.flush()
        teachers.append(teacher)
        summary.teachers.append((staff.full_name, staff.phone, staff.email))
    return teachers


async def _classes(
    session: AsyncSession, teachers: list[Teacher], summary: LabSummary
) -> dict[str, dict[str, list[SchoolClass]]]:
    """Hai lớp mỗi khối cho mỗi giáo viên: giáo viên thứ i dạy 10A(2i+1), 10A(2i+2), 11A…, 12A…."""
    classes: dict[str, dict[str, list[SchoolClass]]] = {}
    for index, teacher in enumerate(teachers):
        classes[teacher.id] = {}
        for grade in GRADES:
            pair = [
                SchoolClass(id=new_id(), teacher_id=teacher.id, name=f"{grade}A{2 * index + n}")
                for n in (1, 2)
            ]
            session.add_all(pair)
            classes[teacher.id][grade] = pair
            summary.classes += len(pair)
    await session.flush()
    return classes


async def _students(
    session: AsyncSession,
    rng: random.Random,
    classes: dict[str, dict[str, list[SchoolClass]]],
    password_hash: str,
    summary: LabSummary,
) -> dict[str, list[Student]]:
    """Chia `STUDENTS` em vào các lớp, lớp đầu nhận phần dư: 34 hay 33 em mỗi lớp."""
    every = [cls for by_grade in classes.values() for grade in GRADES for cls in by_grade[grade]]
    names = student_names(rng, STUDENTS)
    codes = await next_student_codes(session, STUDENTS)
    usernames = await usernames_for(session, names)
    size, extra = divmod(STUDENTS, len(every))
    roster: dict[str, list[Student]] = {}
    start = 0
    for position, school_class in enumerate(every):
        end = start + size + (1 if position < extra else 0)
        members = [
            Student(
                id=new_id(),
                class_id=school_class.id,
                full_name=names[i],
                student_code=codes[i],
                username=usernames[i],
                password_hash=password_hash,
            )
            for i in range(start, end)
        ]
        session.add_all(members)
        roster[school_class.id] = members
        summary.sample_students.append((school_class.name, members[0].username or ""))
        start = end
    summary.students = start
    await session.flush()
    return roster


async def _paper(
    session: AsyncSession,
    rng: random.Random,
    now: datetime,
    teacher: Teacher,
    plan: _Plan,
    chosen: list[SchoolClass],
    roster: dict[str, list[Student]],
    summary: LabSummary,
) -> None:
    """Một đề, đưa tới chặng của `plan`, kèm phát hành và lượt làm của các lớp nhận nó."""
    topic = TOPICS[plan.grade][plan.topic]
    minutes = _MINUTES
    windows = [_window(now, plan, position) for position in range(len(chosen))]
    created = min((w["published_at"] for w in windows), default=now) - timedelta(days=1)
    assessment = Assessment(
        id=new_id(),
        teacher_id=teacher.id,
        title=f"{plan.title} — {topic.name}",
        subject="Toán",
        grade=plan.grade,
        state=AssessmentState.EMPTY,
        created_at=created - timedelta(hours=rng.randint(1, 48)),
    )
    session.add(assessment)
    summary.papers[plan.kind] += 1
    if plan.kind == "nháp":
        await session.flush()
        return

    questions = _questions(session, rng, assessment, topic)
    items = dict(zip((q.id for q in questions), topic.items, strict=True))
    advance(assessment, AssessmentState.HAS_QUESTIONS)
    await session.flush()
    if plan.kind == "đang soạn":
        return
    advance(assessment, AssessmentState.APPROVED)
    await file_approved(session, assessment)
    if not chosen:
        await session.flush()
        return

    advance(assessment, AssessmentState.PUBLISHED)
    difficulty = [rng.uniform(-0.15, 0.15) for _ in questions]
    if plan.hard is not None:
        difficulty[plan.hard] += 0.4
    for position, (school_class, window) in enumerate(zip(chosen, windows, strict=True)):
        recalled = plan.kind == "thu hồi một lớp" and position == 0
        session.add(
            Publication(
                assessment_id=assessment.id,
                class_id=school_class.id,
                phase1_minutes=minutes,
                phase2_minutes_per_question=5,
                recalled_at=now - timedelta(hours=2) if recalled else None,
                **window,
            )
        )
        if plan.kind in ("đang làm", "đang chữa", "đã xong"):
            summary.attempts += await _attempts(
                session,
                rng,
                now,
                plan.kind,
                assessment,
                school_class,
                roster[school_class.id],
                questions,
                items,
                difficulty,
                window,
                minutes,
            )
    await session.flush()


def _window(now: datetime, plan: _Plan, position: int) -> dict[str, datetime]:
    """Năm mốc của một lần phát hành cho lớp thứ `position`; hai lớp mở lệch nhau hai tiếng."""
    if plan.kind == "đang làm":
        # Phải đang mở đúng lúc seed, nên đi theo đồng hồ -- chỉ làm tròn tới 15 phút.
        opens = _quarter(now - timedelta(minutes=30))
        return {
            "opens_at": opens,
            "closes_at": opens + timedelta(hours=2),
            "remediation_deadline": _vn_at(now, 2, 22),
            "published_at": opens - timedelta(days=1),
        }
    opens = _vn_at(now, plan.days, 7, 30) + timedelta(hours=2 * position)
    closes = opens + timedelta(hours=2)
    # Hạn chữa là 22 giờ của một ngày, như giáo viên thật đặt -- không phải một phút lẻ.
    deadline = _vn_at(now, plan.days + 3, 22)
    if plan.kind == "đang chữa":
        deadline = _vn_at(now, 2, 22)
    return {
        "opens_at": opens,
        "closes_at": closes,
        "remediation_deadline": deadline,
        "published_at": min(opens, now) - timedelta(days=1, hours=position),
    }


def _vn_at(now: datetime, days: int, hour: int, minute: int = 0) -> datetime:
    """`hour:minute` giờ Việt Nam, `days` ngày tính từ hôm nay (âm là quá khứ), về lại UTC."""
    day = (now.astimezone(_VN) + timedelta(days=days)).date()
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=_VN).astimezone(now.tzinfo)


def _quarter(moment: datetime) -> datetime:
    """Làm tròn xuống tới 15 phút."""
    return moment.replace(minute=moment.minute - moment.minute % 15, second=0, microsecond=0)


def _questions(
    session: AsyncSession, rng: random.Random, assessment: Assessment, topic: Topic
) -> list[Question]:
    """Sáu câu của bộ `topic` vào đề, phương án đã xáo, kèm cách giải."""
    questions = []
    for order, item in enumerate(topic.items, start=1):
        question = Question(
            id=new_id(),
            assessment_id=assessment.id,
            order_index=order,
            stem=item.stem,
            learning_objective=item.objective,
        )
        question.options = [
            AnswerOption(id=new_id(), label=label, text=text, is_correct=correct, error_label=error)
            for label, text, correct, error in _shuffled(rng, item.options)
        ]
        question.methods = [
            Method(order_index=index, title=title, body=body)
            for index, (title, body) in enumerate(item.methods, start=1)
        ]
        session.add(question)
        questions.append(question)
    return questions


async def _attempts(
    session: AsyncSession,
    rng: random.Random,
    now: datetime,
    kind: str,
    assessment: Assessment,
    school_class: SchoolClass,
    students: list[Student],
    questions: list[Question],
    items: dict[str, Item],
    difficulty: list[float],
    window: dict[str, datetime],
    minutes: int,
) -> int:
    """Lượt làm của một lớp trên một đề, theo chặng. Trả số lượt đã tạo."""
    level = rng.uniform(0.45, 0.85)
    made = 0
    notes = iter(rng.sample(_REPORT_NOTES, len(_REPORT_NOTES)))
    for student in students:
        ability = min(0.97, max(0.1, rng.gauss(level, 0.16)))
        odds = [min(0.98, max(0.03, ability - d)) for d in difficulty]
        roll = rng.random()
        if kind == "đang làm":
            if roll < 0.4:
                started = window["opens_at"] + timedelta(minutes=rng.uniform(0, 12))
                finished = min(started + timedelta(minutes=rng.uniform(5, minutes - 1)), now)
                attempt = await _phase_one(
                    session, assessment, school_class, student, started, minutes
                )
                _submit(session, rng, attempt, questions, odds, started, finished)
            elif roll < 0.6:
                started = now - timedelta(minutes=rng.uniform(1, minutes - 2))
                attempt = await _phase_one(
                    session, assessment, school_class, student, started, minutes
                )
                _answer(session, rng, attempt, questions[: rng.randint(0, 4)], odds, started, now)
            else:
                continue
            made += 1
            continue

        if roll < 0.05:
            continue  # vắng
        started = window["opens_at"] + timedelta(minutes=rng.uniform(0, 40))
        finished = started + timedelta(minutes=rng.uniform(6, minutes))
        attempt = await _phase_one(session, assessment, school_class, student, started, minutes)
        outcomes, chosen = _submit(session, rng, attempt, questions, odds, started, finished)
        made += 1
        if all(outcome.closed for outcome in outcomes.values()):
            continue
        behaviour = rng.random()
        if behaviour < (0.35 if kind == "đang chữa" else 0.25):
            continue  # chưa vào chữa
        rounds = rng.randint(1, _MAX_ROUNDS) if behaviour < 0.85 else 1
        leave_open = kind == "đang chữa" and behaviour >= 0.7
        _remediate(
            session,
            rng,
            now,
            attempt,
            questions,
            items,
            odds,
            outcomes,
            chosen,
            window,
            finished,
            rounds,
            leave_open,
        )
        if rng.random() < 0.06:
            _report(session, rng, now, attempt, kind, finished, next(notes, None))
    return made


async def _phase_one(
    session: AsyncSession,
    assessment: Assessment,
    school_class: SchoolClass,
    student: Student,
    started: datetime,
    minutes: int,
) -> Attempt:
    """Mở một lượt làm như `student_routes.start_attempt` mở: hạn là giờ vào cộng thời lượng."""
    attempt = Attempt(
        id=new_id(),
        assessment_id=assessment.id,
        student_id=student.id,
        class_id=school_class.id,
        started_at=started,
        ends_at=started + timedelta(minutes=minutes),
    )
    session.add(attempt)
    # Flush ngay: `answers`, `question_outcomes`, `rounds`… trỏ vào `attempts` bằng khoá ngoại mà
    # không có relationship ORM, nên unit of work không tự biết phải insert lượt làm trước.
    await session.flush()
    return attempt


def _submit(
    session: AsyncSession,
    rng: random.Random,
    attempt: Attempt,
    questions: list[Question],
    odds: list[float],
    started: datetime,
    finished: datetime,
) -> tuple[dict[str, QuestionOutcome], dict[str, str]]:
    """Chọn đáp án rồi nộp pha 1, chấm bằng `mark_for_phase_one` như route nộp bài.

    Trả sổ điểm theo câu, và câu → phương án em đã chọn.
    """
    chosen = _answer(session, rng, attempt, questions, odds, started, finished)
    outcomes = {}
    for question in questions:
        correct = next(option for option in question.options if option.is_correct)
        mark, reason, closed = mark_for_phase_one(chosen.get(question.id) == correct.id)
        outcomes[question.id] = QuestionOutcome(
            attempt_id=attempt.id,
            question_id=question.id,
            mark=mark,
            reason=reason.value,
            rounds_used=0,
            closed=closed,
        )
    session.add_all(outcomes.values())
    attempt.submitted_at = finished
    return outcomes, chosen


def _answer(
    session: AsyncSession,
    rng: random.Random,
    attempt: Attempt,
    questions: list[Question],
    odds: list[float],
    started: datetime,
    until: datetime,
) -> dict[str, str]:
    """Lưu lựa chọn cho từng câu trong `questions`; vài câu bỏ trống. Trả câu → phương án."""
    chosen = {}
    span = max((until - started).total_seconds(), 1.0)
    for index, question in enumerate(questions):
        if rng.random() < 0.02:
            continue  # bỏ trống
        correct = rng.random() < odds[index]
        pool = [option for option in question.options if option.is_correct == correct]
        option = rng.choice(pool)
        chosen[question.id] = option.id
        saved = started + timedelta(seconds=span * (index + rng.random()) / max(len(questions), 1))
        session.add(
            Answer(
                attempt_id=attempt.id, question_id=question.id, option_id=option.id, saved_at=saved
            )
        )
    return chosen


def _remediate(
    session: AsyncSession,
    rng: random.Random,
    now: datetime,
    attempt: Attempt,
    questions: list[Question],
    items: dict[str, Item],
    odds: list[float],
    outcomes: dict[str, QuestionOutcome],
    chosen: dict[str, str],
    window: dict[str, datetime],
    submitted: datetime,
    rounds: int,
    leave_open: bool,
) -> None:
    """Chat với trợ lý rồi làm vài vòng chữa; mỗi vòng phủ mọi câu còn mở (ADR-17).

    Chấm vòng như `student_routes.submit_round`: `rounds_used` tăng, `mark_after_round` quyết, điểm
    chỉ tăng. `leave_open` để lại một vòng đang làm dở ở cuối, còn giờ.
    """
    deadline = window["remediation_deadline"]
    latest = min(now, deadline) - timedelta(minutes=20)
    clock = submitted + timedelta(minutes=rng.uniform(2, 30))
    if clock >= latest:
        return
    wrong = [q for q in questions if not outcomes[q.id].closed]
    numbers = [q.order_index for q in wrong]
    picked = next((o for o in wrong[0].options if o.id == chosen.get(wrong[0].id)), None)
    error = picked.error_label if picked is not None and picked.error_label else _BLANK
    clock = _chat(session, rng, attempt, wrong[0], items[wrong[0].id], error, numbers, clock)
    done = clock
    for index in range(1, rounds + 1 + (1 if leave_open else 0)):
        still_open = [q for q in questions if not outcomes[q.id].closed]
        if not still_open:
            return
        opening = index == rounds + 1
        # Vòng đang mở bắt đầu vài phút trước, nhưng không trước lúc vòng trước nộp xong.
        started = max(now - timedelta(minutes=rng.uniform(1, 4)), done) if opening else clock
        if not opening and started >= latest:
            return
        budget = round_budget_minutes(5, len(still_open))
        rnd = RemediationRound(
            id=new_id(),
            attempt_id=attempt.id,
            index=index,
            started_at=started,
            ends_at=round_ends_at(started, budget, deadline),
        )
        session.add(rnd)
        for order, question in enumerate(still_open, start=1):
            position = questions.index(question)
            correct = rng.random() < min(0.9, odds[position] + 0.1)
            # Vòng thứ k của một câu dùng đề song sinh thứ k: không vòng nào lặp đề cũ (ADR-17).
            twin = twins(items[question.id])[outcomes[question.id].rounds_used]
            shown = _shuffled(rng, twin.options)
            label = _twin_label(rng, shown, correct)
            item = _round_item(rnd, question, items[question.id], twin, shown, order)
            if opening:
                item.chosen_label = label if rng.random() < 0.5 else None
                session.add(item)
                continue
            item.chosen_label = label
            item.outcome = "đúng" if correct else "sai"
            session.add(item)
            outcome = outcomes[question.id]
            outcome.rounds_used += 1
            mark, reason, closed = mark_after_round(correct, outcome.rounds_used)
            outcome.mark = max(outcome.mark, mark)
            outcome.reason = reason.value
            outcome.closed = closed
        if opening:
            return
        rnd.submitted_at = min(
            started + timedelta(minutes=rng.uniform(1, budget)),
            rnd.ends_at,
            now - timedelta(minutes=1),
        )
        done = rnd.submitted_at + timedelta(seconds=30)
        clock = _awake(rng, rnd.submitted_at + timedelta(hours=rng.uniform(0.5, 20)))


def _chat(
    session: AsyncSession,
    rng: random.Random,
    attempt: Attempt,
    first_wrong: Question,
    item: Item,
    error: str,
    numbers: list[int],
    clock: datetime,
) -> datetime:
    """Ba lượt chat ở màn kèm học trước vòng đầu. Trả giờ kế.

    Lượt đầu là đúng câu đường thật ghi (`student_routes.greeting`); rồi một cặp em hỏi, trợ lý
    đáp (`_EXCHANGES`) về câu sai đầu tiên.
    """
    ask, answer = rng.choice(_EXCHANGES)
    lines = (
        ("assistant", greeting(numbers)),
        ("student", ask),
        (
            "assistant",
            answer.format(
                n=first_wrong.order_index,
                objective=item.objective[0].lower() + item.objective[1:],
                first=item.methods[0][0],
                second=item.methods[1][0],
                error=error,
            ),
        ),
    )
    for sequence, (role, text) in enumerate(lines, start=1):
        clock += timedelta(seconds=rng.uniform(20, 120))
        session.add(
            ChatMessage(
                attempt_id=attempt.id, sequence=sequence, role=role, text=text, created_at=clock
            )
        )
    return clock + timedelta(minutes=rng.uniform(1, 5))


def _shuffled(rng: random.Random, options: tuple[Option, ...]) -> list[Option]:
    """Xáo thứ tự phương án rồi đánh nhãn lại A, B, C, D.

    Câu viết tay để phương án đúng ở A cho dễ đọc; giữ nguyên thì học sinh thử tay đoán ra sau hai
    câu, và cả pha 1 lẫn vòng chữa mất nghĩa.
    """
    order = list(options)
    rng.shuffle(order)
    labels = [label for label, *_ in options]
    return [
        (label, text, correct, error)
        for label, (_, text, correct, error) in zip(labels, order, strict=True)
    ]


def _twin_label(rng: random.Random, options: list[Option], correct: bool) -> str:
    pool = [label for label, _, is_correct, _ in options if is_correct == correct]
    return rng.choice(pool)


def _round_item(
    rnd: RemediationRound,
    question: Question,
    item: Item,
    twin: Twin,
    options: list[Option],
    order: int,
) -> RoundItem:
    """Đề song sinh `twin` của `question` cho vòng `rnd`, cùng hình dạng JSON AGENT trả về."""
    methods = twin.methods or item.methods
    return RoundItem(
        round_id=rnd.id,
        origin_question_id=question.id,
        order_index=order,
        stem=twin.stem,
        options=[
            {"label": label, "text": text, "is_correct": correct, "error_label": error}
            for label, text, correct, error in options
        ],
        methods=[{"title": title, "body": body} for title, body in methods],
    )


def _report(
    session: AsyncSession,
    rng: random.Random,
    now: datetime,
    attempt: Attempt,
    kind: str,
    submitted: datetime,
    note: str | None,
) -> None:
    """Một báo cáo *giải thích chưa rõ* (ADR-19); đề đã xong thì phần lớn giáo viên đã xem.

    Rơi vào giờ đêm thì dời sang sáng hôm sau; dời quá bây giờ thì em chưa kịp báo -- bỏ.
    """
    created = _awake(rng, submitted + timedelta(hours=rng.uniform(1, 30)))
    if created > now - timedelta(minutes=30):
        return
    resolved = kind == "đã xong" and rng.random() < 0.6
    session.add(
        Report(
            attempt_id=attempt.id,
            note=note,
            created_at=created,
            resolved_at=created + timedelta(days=1) if resolved else None,
        )
    )


def _awake(rng: random.Random, moment: datetime) -> datetime:
    """Dời một mốc rơi vào đêm (22:30 tới 6:30 giờ Việt Nam) sang sáng hôm sau, 6:30 tới 9:00."""
    local = moment.astimezone(_VN)
    minutes = local.hour * 60 + local.minute
    if 6 * 60 + 30 <= minutes < 22 * 60 + 30:
        return moment
    day = local.date() if minutes < 6 * 60 + 30 else local.date() + timedelta(days=1)
    morning = datetime(day.year, day.month, day.day, 6, 30, tzinfo=_VN)
    return (morning + timedelta(minutes=rng.uniform(0, 150))).astimezone(moment.tzinfo)
