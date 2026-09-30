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

Every tool here only reads, which is how this version satisfies ADR-05 without
building a confirmation gate: there is no irreversible action to guard. When a
writing tool arrives it does not belong in this list -- it belongs behind the
publish form, which ADR-05 says the chat flow may never stand in for.

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

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from be.identity import Asking
from be.models import (
    Assessment,
    Attempt,
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


async def _find_class(session: AsyncSession, asking: Asking, args: dict) -> dict:
    """Look up one of this teacher's classes by the name they typed.

    Args:
        session: Database session.
        asking: Who is asking. Every candidate is filtered by this.
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


async def _class_assessment_summary(session: AsyncSession, asking: Asking, args: dict) -> dict:
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
        session: Database session.
        asking: Who is asking. Both the class and the assessment must be
            theirs.
        args: `class_id` and `assessment_id`.

    Returns:
        The summary, or a not-found answer when either id is not this
        teacher's.
    """
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


@dataclass(frozen=True)
class Tool:
    """One tool: how it is described to the model, and what it runs.

    Attributes:
        spec: What the model reads. `spec.name` is what the loop dispatches on.
        run: Takes the session, the asking teacher and the arguments. It is
            handed the teacher rather than reading one, so there is no path
            where a tool runs without knowing whose data it may touch.
    """

    spec: ToolSpec
    run: Callable[[AsyncSession, Asking, dict], Awaitable[dict]]


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
)

_BY_NAME = {tool.spec.name: tool for tool in _TOOLS}


def catalog_for(asking: Asking) -> tuple[ToolSpec, ...]:
    """Describe the tools this teacher may use on this turn.

    Every tool in this version is read-only and scoped by owner, so the whole
    list is offered to every teacher. The signature still takes the teacher,
    because the first tool that is not available to everyone must narrow this
    list rather than be stopped later -- a tool described to a model is a tool
    the model will try.

    Args:
        asking: Who is asking.

    Returns:
        The specs the model may choose from.
    """
    return tuple(tool.spec for tool in _TOOLS)


async def execute(session: AsyncSession, asking: Asking, name: str, args: dict) -> dict:
    """Run one tool on this teacher's behalf.

    This is the gate. The catalog said what the model could ask for; this
    decides what happens, and it re-checks ownership inside every tool rather
    than trusting that the catalog was read correctly.

    Args:
        session: Database session.
        asking: Who is asking.
        name: The tool named in the proposal.
        args: The arguments named in the proposal, unvalidated.

    Returns:
        The tool's result, already summarised.

    Raises:
        UnknownTool: If no tool of that name is available to this teacher.
    """
    tool = _BY_NAME.get(name)
    if tool is None or tool.spec not in catalog_for(asking):
        raise UnknownTool(name)

    logger.info("teacher %s runs %s", asking.teacher_code, name)
    return await tool.run(session, asking, args)
