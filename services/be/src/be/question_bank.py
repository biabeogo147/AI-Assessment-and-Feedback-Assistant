"""Ngân hàng câu hỏi của giáo viên: đường ghi (ADR-28).

Câu vào ngân hàng **lúc đề được duyệt**, vì duyệt là giáo viên đã kiểm mọi câu trong đề. Không
tool nào của Kriky ghi vào đây. Từ 18/10/2026 có một đường ghi thứ hai, của chính giáo viên: màn
*Ngân hàng câu hỏi* sửa **bản trong ngân hàng** (`teacher_reads.edit_bank_question`), câu trong đề
không đổi. Đường đọc của màn ấy cũng ở `teacher_reads` (plan `teacher-rail-screens`). Kriky rút câu
từ ngân hàng khi soạn đề thì chưa có (việc 17).

**Một chỗ còn hở:** duyệt lại một đề ghi đè bản ngân hàng theo `question_id`, nên một bản đã sửa
tay ở màn ngân hàng mất khi đề gốc được bỏ duyệt rồi duyệt lại. Chờ người dùng chốt (backlog).

Ba luật, mỗi hàm một luật:

- `file_approved` -- duyệt chép mọi câu của đề; duyệt lại thì **ghi đè** bản của cùng câu, khoá
  theo `BankQuestion.question_id`. Mỗi câu trong đề có nhiều nhất một bản.
- `release` -- xoá câu khỏi đề **không** xoá nó khỏi ngân hàng: dòng ở lại, chỉ thôi trỏ về câu.
- `in_bank` -- câu nào đang có bản. Hộp thoại xoá câu đọc nó để nói đúng điều sắp xảy ra.

Không hàm nào commit. Caller commit cùng việc đã kéo theo nó -- đổi state, hay xoá câu -- để hai
việc hoặc cùng xảy ra, hoặc cùng không: một đề đã duyệt mà ngân hàng thiếu câu của nó là một sự
thật nửa vời mà không màn hình nào báo.
"""

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from schema.models import Assessment, BankQuestion, Question


async def file_approved(session: AsyncSession, assessment: Assessment) -> int:
    """Chép mọi câu của một đề vừa duyệt vào ngân hàng của giáo viên soạn nó.

    Câu chưa có bản thì thêm; câu đã có bản -- đề từng được duyệt, bị bỏ duyệt, rồi duyệt lại
    -- thì bản ấy bị ghi đè bằng nội dung hiện tại. Lần duyệt gần nhất là lần kiểm gần nhất, và
    giáo viên bỏ duyệt thường để sửa một chỗ sai: giữ bản cũ là giữ chỗ sai trong kho.

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
            .where(Question.assessment_id == assessment.id)
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

    *Có bản trong ngân hàng* không phải nguồn *"Lấy từ ngân hàng câu hỏi"*: đây là câu Kriky soạn
    đã từng được duyệt và chép vào kho, không phải câu rút từ kho ra (ADR-28).

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
