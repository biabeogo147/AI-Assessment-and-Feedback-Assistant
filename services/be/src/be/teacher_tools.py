"""What the teacher's assistant may do, and who checks.

Two layers, and it matters which one is load-bearing.

`catalog_for` decides what a teacher is *told* about, so a tool they may not
use is never described to the model at all. `execute` then dispatches by name,
refusing anything not in the table. But **neither of those is what keeps one
teacher out of another's data.** Every tool in this version is offered to every
teacher, so the catalog check inside `execute` is a test that cannot currently
fail; it is there for the first tool that is not universal.

The layer that does the work is inside each tool: every query filters on
`asking.teacher_id` (ADR-22). That is where to look when reviewing a new tool,
and a tool that skips it is not protected by anything above -- which is why
tools are handed an `Asking` rather than reaching for identity themselves.

Some tools here write. That is not a loosening of ADR-05: its boundary is
about actions that **cannot be taken back**, and creating a draft or filling it
with questions is reversible while the paper is unapproved. What no tool does
is release work to students -- approving (ADR-01) and publishing (ADR-02) are
the teacher's, through the panel and the publish form, and
`tools/check_contract.py` refuses this file if it reaches for the lifecycle at
all.

Two rules every tool obeys:

- **Scope by owner, always.** Every query filters on `teacher_id` (ADR-22).
  A tool that took an id and trusted it would make the catalog the only thing
  standing between one teacher and another's marks.
- **Return a summary, not rows.** "How did 11B do" is forty students times ten
  questions. Aggregating here keeps the prompt small, and keeps a whole class's
  results out of a payload crossing to a service that holds no database
  credentials.
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from be.assessment_state import AssessmentState
from be.config import Settings, get_settings
from be.drafting import _MOST_QUESTIONS, fire, harvest, pending_count, rebrief
from be.identity import Asking
from be.models import (
    Assessment,
    Attempt,
    DraftBrief,
    Publication,
    Question,
    QuestionOutcome,
    SchoolClass,
    Student,
)
from be.resolve import Ambiguous, Candidate, NotFound, Resolved, resolve_class
from contracts import ToolSpec

logger = logging.getLogger(__name__)


class UnknownTool(Exception):
    """A proposal named a tool that does not exist, or is not this teacher's.

    Raised rather than returned so the loop cannot mistake it for a tool that
    ran and found nothing. The loop turns it into a result the model can read
    and recover from, which is a different thing from a lookup that succeeded
    and came back empty.
    """


def _shown(candidate: Candidate) -> dict:
    """Render one candidate class for the model to read.

    Roster size travels with the name because a question offering "12A" and
    "12A" is a question a teacher cannot answer. It is the smallest fact that
    distinguishes two sections of one name.

    Args:
        candidate: A class this teacher owns.

    Returns:
        Its id, name and roster size.
    """
    return {
        "class_id": candidate.class_id,
        "name": candidate.name,
        "student_count": candidate.student_count,
    }


@dataclass(frozen=True)
class Running:
    """What one tool call has to work with.

    A small object rather than a longer parameter list, because the writing
    tools need the queue and the reading ones must not touch it -- and a
    reading tool that was handed a pool would be one refactor away from
    queueing something.

    Attributes:
        session: Database session.
        asking: Who is asking. Every query filters on `asking.teacher_id`.
        pool: The arq pool, or None when the queue was unreachable. Only the
            writing tools read it.
        settings: Process settings supplying the queue name.
    """

    session: AsyncSession
    asking: Asking
    pool: object
    settings: Settings


@dataclass(frozen=True)
class Tool:
    """One tool: how it is described to the model, and what it runs.

    Attributes:
        spec: What the model reads. `spec.name` is what the loop dispatches on.
        run: Takes the running context and the arguments. The identity lives
            in that context rather than being read inside, so there is no path
            where a tool runs without knowing whose data it may touch.
        writes: True when the tool changes something. Not used to decide
            anything yet -- every write here is reversible while the paper is
            unapproved -- but it is what a confirmation gate would read, and
            recording it per tool is cheaper than deducing it later from a
            name.
    """

    spec: ToolSpec
    run: Callable[[Running, dict], Awaitable[dict]]
    writes: bool = False


async def _find_class(running: Running, args: dict) -> dict:
    """Look up one of this teacher's classes by the name they typed.

    Args:
        running: Session and the asking teacher. Every candidate is filtered
            by `running.asking`.
        args: `name`, as the teacher wrote it.

    Returns:
        One of four shapes: the class; `ambiguous` with the candidates it
        could be; not-found with the classes this teacher does have; or, when
        no name was given at all, a refusal that says so. Never a guess
        between candidates -- that refusal is ADR-23, and the loop turns it
        into a question.
    """
    # `or ""` rather than a default, because the model can send `null` and
    # `str(None)` is "none" -- a string that gets searched for, matches any
    # class whose name contains it, and otherwise produces "no class of yours
    # by that name". That is the wrong sentence for a question that named no
    # class, and the wrong answer for one that did.
    session, asking = running.session, running.asking
    typed = str(args.get("name") or "")
    answer = await resolve_class(session, asking, typed)

    if not typed.strip():
        listed = answer.available if isinstance(answer, NotFound) else ()
        return {
            "found": False,
            "ambiguous": False,
            "reason": "chưa có tên lớp nào trong câu hỏi",
            "your_classes": [_shown(candidate) for candidate in listed],
            "more": answer.more if isinstance(answer, NotFound) else 0,
        }

    if isinstance(answer, Resolved):
        return {
            "found": True,
            "class_id": answer.class_id,
            "name": answer.name,
            "student_count": answer.student_count,
        }

    if isinstance(answer, Ambiguous):
        return {
            "found": False,
            "ambiguous": True,
            "reason": "tên đó khớp nhiều lớp, cần hỏi lại giáo viên chọn lớp nào",
            "candidates": [_shown(candidate) for candidate in answer.candidates],
            "more": answer.more,
        }

    return {
        "found": False,
        "ambiguous": False,
        "reason": "không có lớp nào tên đó trong danh sách của bạn",
        "your_classes": [_shown(candidate) for candidate in answer.available],
        "more": answer.more,
    }


async def _assessments_of(session: AsyncSession, asking: Asking, class_id: str) -> list[dict]:
    """List the assessments this teacher published to one class.

    Args:
        session: Database session.
        asking: Whose assessments. Both the class and the assessment are
            filtered by this, so a class id belonging to someone else lists
            nothing rather than listing their papers.
        class_id: Which class.

    Returns:
        Title and id for each, newest first. Empty when the class is not this
        teacher's, which is the same answer as a class with no assessments --
        ADR-22 keeps those two indistinguishable.
    """
    listed = await session.execute(
        select(Assessment.id, Assessment.title)
        .join(Publication, Publication.assessment_id == Assessment.id)
        .join(SchoolClass, SchoolClass.id == Publication.class_id)
        .where(
            Publication.class_id == class_id,
            SchoolClass.teacher_id == asking.teacher_id,
            Assessment.teacher_id == asking.teacher_id,
        )
        .order_by(Assessment.created_at.desc())
    )
    return [{"assessment_id": found, "title": title} for found, title in listed.all()]


async def _class_assessment_summary(running: Running, args: dict) -> dict:
    """Summarise how one class did on one assessment.

    Counts, not rows: how many submitted, the average of their totals **with
    the scale it is out of**, and how many questions are still unresolved. A
    teacher asking "how did they do" wants those numbers, and forty rows of
    marks would not fit in a prompt or in an answer.

    The scale travels with the average deliberately. A mark is per question
    and runs 0 / 0,5 / 1, so an average of 3,4 means 3,4 out of however many
    questions there are -- and a number like that, handed over alone, reads as
    3,4 out of 10 to every teacher in the country.

    Args:
        running: Session and the asking teacher. Both the class and the
            assessment must be theirs.
        args: `class_id` and `assessment_id`.

    Returns:
        The summary, or a not-found answer when either id is not this
        teacher's.
    """
    session, asking = running.session, running.asking
    class_id = str(args.get("class_id", ""))
    assessment_id = str(args.get("assessment_id", ""))

    owns_class = await session.scalar(
        select(SchoolClass.id).where(
            SchoolClass.id == class_id, SchoolClass.teacher_id == asking.teacher_id
        )
    )
    assessment = await session.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.teacher_id == asking.teacher_id
        )
    )
    if owns_class is None or assessment is None:
        # The refusal carries what does exist, the way `find_class` does
        # (ADR-23). An empty refusal is an invitation to invent, and that is
        # not a worry -- it was measured on the first real-model run, where
        # gpt-4o-mini answered a bare not-found by naming four classes that do
        # not exist. It also closes the gap the same run exposed: nothing in
        # the catalog told the model which assessment to ask about, so it had
        # to guess an id.
        return {
            "found": False,
            "reason": "không tìm thấy lớp hoặc đề trong danh sách của bạn",
            "assessments_in_this_class": await _assessments_of(session, asking, class_id),
        }

    publication = await session.scalar(
        select(Publication).where(
            Publication.assessment_id == assessment_id, Publication.class_id == class_id
        )
    )
    if publication is None:
        return {"found": False, "reason": "đề này chưa phát hành cho lớp đó"}
    if publication.recalled_at is not None:
        # ADR-02's withdrawal window. A recalled assessment reads as a normal
        # one unless this is said, and a teacher who withdrew a paper and then
        # asked how it went would be told about attempts that no longer count.
        return {
            "found": True,
            "assessment_title": assessment.title,
            "recalled": True,
            "note": "đề này đã bị thu hồi",
        }

    # An attempt names a student, not a class, so the class filter travels
    # through the roster. Filtering on the students of this class rather than
    # on every attempt of the assessment is what keeps one class's summary from
    # quietly including another's.
    # `Student.class_id` is the student's class *now*. A student who changed
    # class carries their old attempts with them, so this counts them under
    # the new class. Wrong, and not introduced here -- but this is the first
    # caller it affects, so the next person reading a surprising summary has
    # somewhere to start.
    #
    # Only submitted attempts. A paper still being written has no
    # `QuestionOutcome` rows yet -- they are created at submit -- so counting
    # it would add nothing to the total and one to the divisor, quietly
    # dragging the average down while a student is still typing.
    attempts = (
        await session.scalars(
            select(Attempt)
            .join(Student, Student.id == Attempt.student_id)
            .where(
                Attempt.assessment_id == assessment_id,
                Student.class_id == class_id,
                Attempt.submitted_at.is_not(None),
            )
        )
    ).all()
    counting = (
        select(func.count()).select_from(Question).where(Question.assessment_id == assessment_id)
    )
    question_count = await session.scalar(counting) or 0
    if not attempts:
        return {
            "found": True,
            "assessment_title": assessment.title,
            "question_count": question_count,
            "submitted_count": 0,
            "note": "chưa có học sinh nào nộp bài",
        }

    ids = [attempt.id for attempt in attempts]
    marks = (
        await session.scalars(select(QuestionOutcome).where(QuestionOutcome.attempt_id.in_(ids)))
    ).all()
    wrong_still_open = sum(1 for mark in marks if mark.mark == 0 and not mark.closed)
    total = sum(mark.mark for mark in marks)

    # A mark is per question and runs 0 / 0,5 / 1 (ADR-16), so the sum over an
    # attempt is out of `question_count` and not out of ten. That distinction
    # is the whole reason both numbers are returned and the field is not called
    # "điểm trung bình": a Vietnamese teacher reads a bare 3,4 as 3,4/10 and
    # concludes the class failed, when 3,4 out of 5 is 68%.
    average = round(total / len(attempts), 2)
    return {
        "found": True,
        "assessment_title": assessment.title,
        "question_count": question_count,
        "submitted_count": len(attempts),
        "average_total_marks": average,
        "average_out_of": question_count,
        "average_percent": round(100 * average / question_count) if question_count else None,
        "questions_still_open": wrong_still_open,
    }


# What a draft cannot be started without. Not a preference -- the questions
# are written by independent jobs, so a brief still being assembled produces a
# set whose halves answer different questions, and that is a defect nobody
# finds by reading the questions one at a time.
_BRIEF_FIELDS = ("subject", "grade", "topic_scope", "question_count")

# How long each free-text field may be, taken from the columns that store it:
# `Assessment.subject` and `DraftBrief.difficulty` are String(64) and
# `Assessment.grade` is String(16). The model writes these, so they arrive as
# whatever a teacher said -- and `String(n)` is unenforced on SQLite, so a test
# suite cannot discover this for us.
_FIELD_CAPS = {"subject": 64, "grade": 16, "difficulty": 64}

# Said the same way for a draft that is not there and one that belongs to
# someone else (ADR-22).
_NO_SUCH_DRAFT = {
    "started": False,
    "reason": "không có đề nháp nào như vậy trong danh sách của bạn",
}


async def _create_draft(running: Running, args: dict) -> dict:
    """Start an empty draft, once the brief is complete.

    Refuses an incomplete brief and names the fields that are missing. That
    refusal is the mechanism behind "gather the context first": a model told
    to ask before writing can forget, and a tool that will not run without the
    fields cannot be forgotten. Naming them is what lets the assistant ask one
    useful question instead of several vague ones.

    Nothing is queued here. Creating the draft and filling it are separate
    steps, so the brief is readable -- by the teacher, in the panel -- before
    any model call is spent on it.

    Args:
        running: Session and the asking teacher, who becomes the author.
        args: `subject`, `grade`, `topic_scope`, `question_count`, and
            optionally `difficulty` and `title`.

    Returns:
        The new draft's id, or a refusal naming what the brief still needs.

    Side effects:
        Writes an `Assessment` in the empty state and its `DraftBrief`.
    """
    session, asking = running.session, running.asking

    missing = [field for field in _BRIEF_FIELDS if not str(args.get(field) or "").strip()]
    if missing:
        return {
            "created": False,
            "missing": missing,
            "reason": "chưa đủ thông tin để soạn đề; hãy hỏi giáo viên những mục còn thiếu",
        }

    try:
        count = int(str(args["question_count"]).strip())
    except (TypeError, ValueError):
        # Not the same as missing. Reporting "chưa đủ thông tin" for a field
        # the model already filled sends it round to fill the same value again,
        # and the turn spends its whole ceiling discovering that "ba" is not a
        # number.
        return {
            "created": False,
            "missing": [],
            "unreadable": ["question_count"],
            "reason": "question_count phải là một con số, ví dụ 10",
        }

    if not 1 <= count <= _MOST_QUESTIONS:
        return {
            "created": False,
            "missing": [],
            "unreadable": ["question_count"],
            "reason": f"số câu phải từ 1 đến {_MOST_QUESTIONS}",
        }

    # Lengths come from the columns, and the answer is a refusal rather than a
    # silent trim: a truncated `grade` is wrong data that looks like data. The
    # test suite runs on SQLite, where `String(n)` has no effect, so nothing
    # below this line would have failed until a teacher hit Postgres -- which
    # is exactly what "lớp 12 ban khoa học tự nhiên" does to a 16-character
    # column.
    too_long = [
        field for field, cap in _FIELD_CAPS.items() if len(str(args.get(field) or "")) > cap
    ]
    if too_long:
        return {
            "created": False,
            "missing": [],
            "too_long": too_long,
            "reason": (
                "mấy mục này dài quá mức lưu được: "
                + ", ".join(f"{field} tối đa {_FIELD_CAPS[field]} ký tự" for field in too_long)
            ),
        }

    scope = str(args["topic_scope"]).strip()
    draft = Assessment(
        teacher_id=asking.teacher_id,
        # A title the teacher can rename later, so deriving one costs nothing
        # and saves a round of questions about something cosmetic. Trimmed
        # rather than refused for the same reason.
        title=str(args.get("title") or f"Đề {scope}").strip()[:160],
        subject=str(args["subject"]).strip(),
        grade=str(args["grade"]).strip(),
        state=AssessmentState.EMPTY,
        created_at=datetime.now(UTC),
    )
    session.add(draft)
    await session.flush()

    await rebrief(
        session,
        draft.id,
        topic_scope=scope,
        question_count=count,
        difficulty=str(args.get("difficulty") or "").strip(),
    )

    logger.info("teacher %s opened draft %s", asking.teacher_code, draft.id)
    return {
        "created": True,
        "assessment_id": draft.id,
        "title": draft.title,
        "question_count": count,
    }


async def _draft_progress(running: Running, args: dict) -> dict:
    """Collect whatever is finished, and say how far the draft has got.

    The collecting is the point. BE has no background worker, so a question
    only enters a draft when something asks for it -- and before this tool
    existed, nothing did: `start_drafting` queued jobs whose answers expired in
    Redis an hour later, leaving the draft empty and permanently "đang soạn
    dở".

    Args:
        running: Session, the asking teacher, and the queue.
        args: `assessment_id`.

    Returns:
        Counts and the question stems so far, or the same not-found answer a
        draft belonging to someone else produces (ADR-22).

    Side effects:
        Writes any finished questions into the draft.
    """
    session, asking = running.session, running.asking
    assessment_id = str(args.get("assessment_id") or "")

    owned = await session.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.teacher_id == asking.teacher_id
        )
    )
    if owned is None:
        return {"found": False, "reason": _NO_SUCH_DRAFT["reason"]}

    landed = await harvest(session, running.pool, running.settings, assessment_id)
    brief = await session.get(DraftBrief, assessment_id)
    stems = await session.scalars(
        select(Question.stem)
        .where(Question.assessment_id == assessment_id)
        .order_by(Question.order_index)
    )
    still_running = await pending_count(session, assessment_id)

    return {
        "found": True,
        "assessment_id": assessment_id,
        "title": owned.title,
        "state": str(owned.state),
        "asked_for": brief.question_count if brief is not None else 0,
        "written": list(stems),
        "just_landed": landed,
        "still_drafting": still_running,
    }


async def _start_drafting(running: Running, args: dict) -> dict:
    """Queue one job per question of a draft's brief.

    Refuses while anything is still running. Two overlapping rounds is exactly
    the failure the stored brief exists to prevent -- questions written to two
    sets of instructions sharing one paper -- and refusing is cheaper than
    reconciling.

    Args:
        running: Session, the asking teacher, and the queue.
        args: `assessment_id`.

    Returns:
        How many jobs were queued, or a refusal. The refusal for another
        teacher's draft reads exactly like the one for a draft that does not
        exist (ADR-22).

    Side effects:
        Writes jobs onto the queue and a `DraftItem` row for each.
    """
    session, asking = running.session, running.asking
    assessment_id = str(args.get("assessment_id") or "")

    owned = await session.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.teacher_id == asking.teacher_id
        )
    )
    if owned is None:
        return dict(_NO_SUCH_DRAFT)

    # Collected first. Nothing else in BE collects these jobs, so a round that
    # finished while nobody was looking would still read as running -- and the
    # refusal below would then be permanent: the draft could never be worked on
    # again.
    await harvest(session, running.pool, running.settings, assessment_id)

    if await pending_count(session, assessment_id):
        return {
            "started": False,
            "reason": "đề này đang soạn dở; chờ xong rồi hãy soạn thêm",
        }

    try:
        queued = await fire(session, running.pool, running.settings, assessment_id)
    except HTTPException:
        # `fire` calls `assert_editable`, so an approved paper lands here.
        # ADR-01 locks content at approval, and that lock is the reason
        # approving means anything.
        #
        # Deliberately not `refused.detail`. That sentence ends "muốn sửa thì
        # bỏ duyệt trước", which is written for a teacher reading a screen --
        # and the prompt tells the model to relay a reason, so the assistant
        # would offer to unapprove. It has no tool for that, and the check in
        # `tools/check_contract.py` is there to keep it that way, so relaying
        # the sentence would turn a correct refusal into a promise nobody can
        # keep.
        return {
            "started": False,
            "reason": "đề này đã duyệt nên nội dung đã khoá; việc bỏ duyệt làm ở panel bên phải",
        }

    if not queued:
        return {
            "started": False,
            "reason": "chưa soạn được câu nào; có thể đề chưa có brief, hoặc hàng đợi đang hỏng",
        }
    return {"started": True, "queued": queued, "assessment_id": assessment_id}


_TOOLS: tuple[Tool, ...] = (
    Tool(
        spec=ToolSpec(
            name="find_class",
            description=(
                "Tìm một lớp của giáo viên theo tên để lấy class_id. Gọi tool này trước khi hỏi "
                "về kết quả của một lớp, vì các tool khác cần class_id chứ không nhận tên lớp."
            ),
            arguments={"name": "tên lớp như giáo viên vừa nói, ví dụ 12A1"},
        ),
        run=_find_class,
    ),
    Tool(
        spec=ToolSpec(
            name="class_assessment_summary",
            description=(
                "Tóm tắt kết quả một bài kiểm tra trong một lớp: bao nhiêu em đã nộp, tổng điểm "
                "trung bình trên thang bằng số câu, và còn bao nhiêu câu chưa chữa xong. Cần "
                "class_id và assessment_id. Chưa biết assessment_id thì cứ gọi với class_id và một "
                "assessment_id rỗng: kết quả sẽ trả về assessments_in_this_class để bạn chọn đúng "
                "đề rồi gọi lại. TUYỆT ĐỐI không tự đoán assessment_id. Khi nói lại con số, PHẢI "
                "nói kèm thang — average_total_marks là điểm trên average_out_of câu, KHÔNG phải "
                "trên thang 10."
            ),
            arguments={
                "class_id": "id lớp, lấy từ find_class",
                "assessment_id": "id đề",
            },
        ),
        run=_class_assessment_summary,
    ),
    Tool(
        spec=ToolSpec(
            name="create_draft",
            description=(
                "Mo mot de nhap trong. BAT BUOC co du: subject (mon), grade (khoi), topic_scope "
                "(pham vi kien thuc, theo loi giao vien) va question_count (so cau). Thieu muc nao "
                "thi tool tra ve danh sach missing -- hay HOI giao vien nhung muc do roi goi lai, "
                "dung tu doan. difficulty va title la tuy chon. Tool nay KHONG sinh cau hoi; goi "
                "start_drafting sau."
            ),
            arguments={
                "subject": "mon hoc, vi du Toan",
                "grade": "khoi, vi du 12",
                "topic_scope": "pham vi kien thuc theo loi giao vien",
                "question_count": "so cau, 1 den 50",
                "difficulty": "muc do theo loi giao vien (tuy chon)",
                "title": "ten de (tuy chon, he thong tu dat neu bo trong)",
            },
        ),
        run=_create_draft,
        writes=True,
    ),
    Tool(
        spec=ToolSpec(
            name="start_drafting",
            description=(
                "Bat dau sinh cau hoi cho mot de nhap da co brief. Moi cau mot job chay nen, nen "
                "tool tra ve ngay va cau hoi hien dan -- dung cho, hay noi voi giao vien la dang "
                "soan. Tu choi neu de dang soan do hoac da duyet."
            ),
            arguments={"assessment_id": "id de nhap, lay tu create_draft"},
        ),
        run=_start_drafting,
        writes=True,
    ),
    Tool(
        spec=ToolSpec(
            name="draft_progress",
            description=(
                "Xem một đề nháp đã soạn được bao nhiêu câu, và đọc các câu đã có. Gọi tool này "
                "sau start_drafting để biết đã xong chưa — câu hỏi chỉ vào đề khi có ai hỏi tới, "
                "nên không gọi thì đề vẫn trống. still_drafting > 0 nghĩa là còn đang soạn."
            ),
            arguments={"assessment_id": "id đề nháp"},
        ),
        run=_draft_progress,
    ),
)

_BY_NAME = {tool.spec.name: tool for tool in _TOOLS}


def catalog_for(asking: Asking) -> tuple[ToolSpec, ...]:
    """Describe the tools this teacher may use on this turn.

    Every tool is scoped by owner, so the whole list is offered to every
    teacher. The signature still takes the teacher, because the first tool that
    is not available to everyone must narrow this list rather than be stopped
    later -- a tool described to a model is a tool the model will try.

    Args:
        asking: Who is asking.

    Returns:
        The specs the model may choose from.
    """
    return tuple(tool.spec for tool in _TOOLS)


async def execute(
    session: AsyncSession,
    asking: Asking,
    name: str,
    args: dict,
    *,
    pool: object = None,
    settings: Settings | None = None,
) -> dict:
    """Run one tool on this teacher's behalf.

    This is the gate. The catalog said what the model could ask for; this
    decides what happens, and it re-checks ownership inside every tool rather
    than trusting that the catalog was read correctly.

    What this function will never do is change an assessment's state.
    `tools/check_contract.py` refuses this file if it so much as mentions
    `advance` or `withdraw`: the assistant writes content, and a teacher
    decides whether that content may be released (ADR-01, ADR-02, ADR-05).

    Args:
        session: Database session.
        asking: Who is asking.
        name: The tool named in the proposal.
        args: The arguments named in the proposal, unvalidated.
        pool: The arq pool, for the tools that queue work.
        settings: Process settings. Read from the process when not given.

    Returns:
        The tool's result, already summarised.

    Raises:
        UnknownTool: If no tool of that name is available to this teacher.
    """
    tool = _BY_NAME.get(name)
    if tool is None or tool.spec not in catalog_for(asking):
        raise UnknownTool(name)

    logger.info("teacher %s runs %s", asking.teacher_code, name)
    return await tool.run(
        Running(
            session=session,
            asking=asking,
            pool=pool,
            settings=settings or get_settings(),
        ),
        args,
    )
