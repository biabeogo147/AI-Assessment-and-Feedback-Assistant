"""Ngân hàng câu hỏi của giáo viên: đường ghi (ADR-28).

Câu vào ngân hàng **lúc đề được duyệt**, vì duyệt là giáo viên đã kiểm mọi câu trong đề. Không
tool nào của Kriky ghi vào đây. Từ 18/10/2026 có một đường ghi thứ hai, của chính giáo viên: màn
*Ngân hàng câu hỏi* sửa **bản trong ngân hàng** (`teacher_reads.edit_bank_question`), câu trong đề
không đổi. Đường đọc của màn ấy cũng ở `teacher_reads` (plan `teacher-rail-screens`).

Chiều ngược lại -- **giáo viên lấy câu từ ngân hàng vào một đề còn mở** -- có từ việc 17 (plan
`question-bank-into-draft`): `take_into` chép câu thành một `Question` mang `source="bank"`, và
`picker` liệt kê ngân hàng cho hộp chọn. Kriky rút câu từ ngân hàng khi soạn thì chưa có (chạm
AGENT, đang khoá).

**Một chỗ còn hở:** duyệt lại một đề ghi đè bản ngân hàng theo `question_id`, nên một bản đã sửa
tay ở màn ngân hàng mất khi đề gốc được bỏ duyệt rồi duyệt lại. Chờ người dùng chốt (backlog).

Sáu luật, mỗi hàm một luật:

- `file_approved` -- duyệt chép mọi câu **Kriky soạn** của đề; duyệt lại thì **ghi đè** bản của
  cùng câu, khoá theo `BankQuestion.question_id`. Mỗi câu trong đề có nhiều nhất một bản. Câu lấy từ
  ngân hàng không chép lại: bản của nó đã có, và chép là hai bản của một câu.
- `release` -- xoá câu khỏi đề **không** xoá nó khỏi ngân hàng: dòng ở lại, chỉ thôi trỏ về câu.
- `in_bank` -- câu nào đang có bản. Hộp thoại xoá câu đọc nó để nói đúng điều sắp xảy ra.
- `picker` -- ngân hàng của giáo viên, mỗi câu kèm cờ *đã có trong đề này*.
- `choose` -- câu đã chọn phải là câu trong ngân hàng của chủ đề; câu đã có trong đề bị bỏ qua.
- `take_into` -- chép các câu ấy vào cuối đề, mỗi câu một ô soạn đã xong.

Không hàm nào commit. Caller commit cùng việc đã kéo theo nó -- đổi state, hay xoá câu -- để hai
việc hoặc cùng xảy ra, hoặc cùng không: một đề đã duyệt mà ngân hàng thiếu câu của nó là một sự
thật nửa vời mà không màn hình nào báo.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from be.assessment_state import AssessmentState, advance
from schema.models import (
    AnswerOption,
    Assessment,
    BankQuestion,
    DraftBrief,
    DraftItem,
    Method,
    Question,
)

# `Question.source` của câu giáo viên lấy từ ngân hàng; câu Kriky soạn mang `"kriky"`.
BANK = "bank"


async def file_approved(session: AsyncSession, assessment: Assessment) -> int:
    """Chép mọi câu Kriky soạn của một đề vừa duyệt vào ngân hàng của giáo viên soạn nó.

    Câu chưa có bản thì thêm; câu đã có bản -- đề từng được duyệt, bị bỏ duyệt, rồi duyệt lại
    -- thì bản ấy bị ghi đè bằng nội dung hiện tại. Lần duyệt gần nhất là lần kiểm gần nhất, và
    giáo viên bỏ duyệt thường để sửa một chỗ sai: giữ bản cũ là giữ chỗ sai trong kho.

    Câu `source="bank"` bị bỏ qua (việc 17): bản ngân hàng của nó đã có, và chép là hai bản của
    một câu; ghi đè dòng gốc thì một lần sửa trong đề lặng lẽ đổi ngân hàng, ngược điều người dùng
    chốt cho màn 22b.

    Args:
        session: Session của database. Không commit ở đây.
        assessment: Đề vừa được duyệt. Chủ của nó là chủ của ngân hàng.

    Returns:
        Số câu đã ghi, kể cả câu ghi đè.

    Side effects:
        Thêm hoặc ghi đè các dòng `BankQuestion`.
    """
    # `populate_existing`: route duyệt đã giữ các câu này trong identity map từ trước lần
    # `harvest` tự commit, và session không expire khi commit -- không có cờ này thì lần chép
    # đọc lại bản trong bộ nhớ chứ không phải bản trong database.
    questions = list(
        await session.scalars(
            select(Question)
            .where(Question.assessment_id == assessment.id, Question.source != BANK)
            .options(selectinload(Question.options), selectinload(Question.methods))
            .execution_options(populate_existing=True)
        )
    )
    filed = {
        row.question_id: row
        for row in await session.scalars(
            select(BankQuestion).where(
                BankQuestion.teacher_id == assessment.teacher_id,
                BankQuestion.question_id.in_([one.id for one in questions]),
            )
        )
    }
    now = datetime.now(UTC)

    for question in questions:
        options = [
            {
                "label": one.label,
                "text": one.text,
                "is_correct": one.is_correct,
                "error_label": one.error_label,
            }
            for one in question.options
        ]
        methods = [{"title": one.title, "body": one.body} for one in question.methods]

        row = filed.get(question.id)
        if row is None:
            session.add(
                BankQuestion(
                    teacher_id=assessment.teacher_id,
                    question_id=question.id,
                    assessment_id=assessment.id,
                    stem=question.stem,
                    learning_objective=question.learning_objective,
                    options=options,
                    methods=methods,
                    created_at=now,
                    approved_at=now,
                )
            )
            continue
        # List mới, không sửa tại chỗ: cột JSON không theo dõi thay đổi bên trong một list.
        row.stem = question.stem
        row.learning_objective = question.learning_objective
        row.options = options
        row.methods = methods
        row.approved_at = now

    await session.flush()
    return len(questions)


async def in_bank(session: AsyncSession, teacher_id: str, question_ids: Iterable[str]) -> set[str]:
    """Trong các câu này, câu nào đang có bản trong ngân hàng của giáo viên này.

    Chỉ chiều **câu → kho**: câu Kriky soạn đã từng được duyệt và chép vào kho (ADR-28). Câu rút
    từ kho ra (`Question.bank_question_id`, việc 17) không có ở đây; `QuestionRead.in_bank` của
    panel gộp cả hai chiều.

    Args:
        session: Session của database.
        teacher_id: Chủ ngân hàng.
        question_ids: Các câu cần hỏi.

    Returns:
        Id của những câu có bản. Câu không có thì vắng mặt.
    """
    wanted = list(question_ids)
    if not wanted:
        return set()
    found = await session.scalars(
        select(BankQuestion.question_id).where(
            BankQuestion.teacher_id == teacher_id, BankQuestion.question_id.in_(wanted)
        )
    )
    return {one for one in found if one is not None}


async def release(session: AsyncSession, teacher_id: str, question_id: str) -> None:
    """Thả bản trong ngân hàng của một câu sắp bị xoá khỏi đề. Bản ấy ở lại.

    Chạy **trước** khi xoá câu. Khoá ngoại `question_id` có `ondelete="SET NULL"` nên Postgres
    tự làm việc này, nhưng SQLite của phần lớn test không bật khoá ngoại -- nói thẳng ở đây thì
    luật *xoá trong đề không xoá ngân hàng* đứng trong code, không chỉ trong DDL. Hàm này không có
    test riêng: `test_delete_question.py` bật khoá ngoại, nên ở đó `SET NULL` làm cùng việc.

    Args:
        session: Session của database. Không commit ở đây.
        teacher_id: Chủ ngân hàng.
        question_id: Câu sắp bị xoá.

    Side effects:
        Đặt `BankQuestion.question_id` về `NULL` cho dòng đang trỏ vào câu, nếu có.
    """
    await session.execute(
        update(BankQuestion)
        .where(BankQuestion.teacher_id == teacher_id, BankQuestion.question_id == question_id)
        .values(question_id=None)
    )


@dataclass(frozen=True)
class Pickable:
    """Một câu ngân hàng trong hộp chọn (artboard 19b).

    Attributes:
        row: Dòng ngân hàng.
        from_title: Tên đề câu này được duyệt cùng -- dòng phụ của hộp chọn.
        in_this_paper: Câu đã nằm trong đề đang mở: lấy vào trước đó, hay chính đề này là nơi câu
            được duyệt. Hộp chọn khoá dòng ấy.
    """

    row: BankQuestion
    from_title: str
    in_this_paper: bool


async def _already_in(session: AsyncSession, assessment_id: str) -> set[str]:
    """Những dòng ngân hàng đã có mặt trong một đề, theo cả hai chiều chép.

    Args:
        session: Session của database.
        assessment_id: Đề nào.

    Returns:
        Id dòng ngân hàng: câu của đề chép **từ** dòng ấy (`Question.bank_question_id`), hay dòng
        ấy chép **từ** một câu của đề (`BankQuestion.question_id`).
    """
    taken = set(
        await session.scalars(
            select(Question.bank_question_id).where(
                Question.assessment_id == assessment_id, Question.bank_question_id.is_not(None)
            )
        )
    )
    born_here = await session.scalars(
        select(BankQuestion.id)
        .join(Question, Question.id == BankQuestion.question_id)
        .where(Question.assessment_id == assessment_id)
    )
    return taken | set(born_here)


async def picker(session: AsyncSession, assessment: Assessment) -> list[Pickable]:
    """Ngân hàng của chủ đề, mới duyệt trước, cho hộp chọn của panel.

    Args:
        session: Session của database.
        assessment: Đề đang mở. Chủ của nó là chủ ngân hàng.

    Returns:
        Mọi câu trong ngân hàng của giáo viên ấy.
    """
    rows = list(
        await session.execute(
            select(BankQuestion, Assessment.title)
            .join(Assessment, Assessment.id == BankQuestion.assessment_id)
            .where(BankQuestion.teacher_id == assessment.teacher_id)
            .order_by(BankQuestion.approved_at.desc(), BankQuestion.id)
        )
    )
    here = await _already_in(session, assessment.id)
    return [
        Pickable(row=row, from_title=title, in_this_paper=row.id in here) for row, title in rows
    ]


async def choose(
    session: AsyncSession, assessment: Assessment, bank_ids: Sequence[str]
) -> list[BankQuestion]:
    """Các dòng ngân hàng sẽ chép vào đề, theo thứ tự đã chọn: bỏ qua câu đã có trong đề.

    Câu đã có không phải lỗi -- hai tab cùng thêm một câu là chuyện thường. Trần số câu của một đề
    là việc của bên gọi (`drafting.too_many`): `drafting` đã import module này. Ô hỏng của một đề
    trống cũng vậy -- bên gọi dọn chúng trước, như khi dùng lại đề trống.

    Args:
        session: Session của database.
        assessment: Đề đích.
        bank_ids: Các dòng ngân hàng đã chọn.

    Returns:
        Những dòng còn phải chép.

    Raises:
        HTTPException: 404 khi một id không phải câu trong ngân hàng của chủ đề (ADR-22).
    """
    wanted = list(dict.fromkeys(bank_ids))
    found = {
        row.id: row
        for row in await session.scalars(
            select(BankQuestion).where(
                BankQuestion.teacher_id == assessment.teacher_id, BankQuestion.id.in_(wanted)
            )
        )
    }
    if len(found) != len(wanted):
        raise HTTPException(
            status_code=404, detail="Không tìm thấy câu này trong ngân hàng của bạn."
        )
    here = await _already_in(session, assessment.id)
    return [found[one] for one in wanted if one not in here]


async def take_into(
    session: AsyncSession, assessment: Assessment, rows: Sequence[BankQuestion]
) -> None:
    """Chép các câu ngân hàng vào cuối một đề còn mở, theo thứ tự cho sẵn.

    Mỗi câu thành một `Question` mang `source="bank"` và `bank_question_id`, cùng phương án và lời
    giải chép từ JSON của dòng ngân hàng, và **một ô `DraftItem` đã `ready`**: `fire` đặt câu Kriky
    soạn thêm sau ô cao nhất, nên câu không có ô thì lần soạn sau ghi đè lên số của nó.

    Bên gọi đã khoá đề, đã chặn đề không sửa được, đề còn câu đang soạn, và tổng vượt trần.

    Args:
        session: Session của database. Không commit ở đây.
        assessment: Đề đích, đã khoá.
        rows: Kết quả của `choose`.

    Side effects:
        Thêm câu, phương án, lời giải, ô soạn; nâng `brief.question_count`; đề trống sang *có câu*.
    """
    if not rows:
        return
    # Sau cả câu lẫn ô cao nhất: một ô hỏng ở cuối đề vẫn giữ số của nó.
    last = max(
        await session.scalar(
            select(func.max(Question.order_index)).where(Question.assessment_id == assessment.id)
        )
        or 0,
        await session.scalar(
            select(func.max(DraftItem.ordinal)).where(DraftItem.assessment_id == assessment.id)
        )
        or 0,
    )
    # Khoá brief sau đề và đọc lại từ database, như `fire`: `harvest` vừa nạp nó vào identity map,
    # và một `fire` song song đọc-sửa-ghi `question_count` (review pha 1).
    brief = await session.scalar(
        select(DraftBrief)
        .where(DraftBrief.assessment_id == assessment.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = datetime.now(UTC)

    for offset, row in enumerate(rows, start=1):
        order = last + offset
        question = Question(
            assessment_id=assessment.id,
            order_index=order,
            stem=row.stem,
            learning_objective=row.learning_objective,
            source=BANK,
            bank_question_id=row.id,
        )
        session.add(question)
        await session.flush()
        for option in row.options:
            session.add(
                AnswerOption(
                    question_id=question.id,
                    label=option["label"],
                    text=option["text"],
                    is_correct=option["is_correct"],
                    error_label=option.get("error_label"),
                )
            )
        for index, method in enumerate(row.methods, start=1):
            session.add(
                Method(
                    question_id=question.id,
                    order_index=index,
                    title=method["title"],
                    body=method["body"],
                )
            )
        session.add(
            DraftItem(
                assessment_id=assessment.id,
                ordinal=order,
                job_id=f"bank:{row.id}",
                status="ready",
                attempts=1,
                brief_version=brief.version if brief is not None else 1,
                created_at=now,
            )
        )

    # `harvest` coi ô vượt `question_count` là ô cũ, và xoá câu trừ con số này: không nâng thì xoá
    # một câu ngân hàng làm ô Kriky đang soạn ở cuối đề thành ô cũ.
    if brief is not None:
        brief.question_count = max(brief.question_count, last + len(rows))
    if AssessmentState(assessment.state) is AssessmentState.EMPTY:
        advance(assessment, AssessmentState.HAS_QUESTIONS)
    await session.flush()
