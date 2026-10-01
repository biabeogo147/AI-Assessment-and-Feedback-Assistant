"""Hai quyết định mà giáo viên tự bấm: duyệt, và bỏ duyệt.

Đây là chỗ `advance` có caller đầu tiên **trên một đường HTTP**. `drafting` đã gọi nó từ
Pha 2, nhưng chỉ cho một cạnh mà máy tự đi: câu hỏi đầu tiên thu được đưa đề ra khỏi
`EMPTY`. Hai cạnh trong file này thì khác về bản chất -- chúng là lúc một con người nhận
trách nhiệm, nên chúng không bao giờ là một tool (`tools/check_contract.py` giữ nguyên
tình trạng đó) và chúng phải đi qua một request mà giáo viên tự phát ra.

**Duyệt phải thu hoạch trước khi đếm.** BE không có worker chạy nền, nên một job xong vẫn
nằm trong Redis tới khi có ai hỏi, và `DraftItem` chỉ rời `pending` lúc `harvest` chạy.
Nếu endpoint này đếm trước khi thu thì một giáo viên có đủ mười câu đã viết xong vẫn bị
từ chối, mãi mãi, vì con số nó đọc chỉ thay đổi khi có người gọi một endpoint khác. Đây
đúng là lỗi mà review Pha 3 đã bắt ở `start_drafting`, và nó cùng một gốc.

**Bất biến `state` ↔ số câu hỏi được thi hành ở đây, không ở `advance`.** Đếm câu hỏi cần
một session, còn `advance` thì thuần trên một row -- đọc `assessment.questions` bên trong
nó sẽ là một lần lazy-load trong ngữ cảnh async, tức `MissingGreenlet`. Nên bảng `_ALLOWED`
trả lời *"ADR-01 có cạnh này không"*, và endpoint trả lời *"lúc này đi được không"*. Cùng
một cách chia như `withdraw` của Pha 5.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from be.assessment_state import AssessmentState, advance, editable, readable, state_of
from be.config import Settings, get_settings
from be.db import get_session
from be.drafting import harvest, pending_count
from be.identity import Asking, current_teacher
from be.models import Assessment, Question, Teacher
from be.teacher_chat import note_action
from contracts import TurnRecord

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["teacher-assessments"])

# Một đề của người khác đọc lên y như một đề không tồn tại (ADR-22). Hai câu trả lời phân
# biệt được sẽ cho bất kỳ ai dò xem các giáo viên khác đang có những gì, chỉ bằng cách thử
# id.
_NO_SUCH = "Không tìm thấy đề này."


class Approval(BaseModel):
    """Đề đang ở đâu sau khi quyết định đã được áp.

    Cả bốn field đều **đọc lại từ database** sau khi commit, không field nào ghi cứng.
    Bản đầu ghi cứng `still_drafting=0` kèm một lời biện hộ viện ADR-02, và cả hai đều
    sai: một con số ghi cứng thì không test nào làm đỏ được -- `assert còn 0 == 0` chỉ so
    hai hằng số -- còn luật của ADR-02 là *"hộp xác nhận đọc lại đúng giá trị vừa nhập"*,
    nói về sáu tham số phát hành mà giáo viên tự gõ, không nói về số câu hỏi.

    Attributes:
        assessment_id: Đề nào.
        state: State đọc lại từ hàng, nên nó chứng minh được rằng hàng đã đổi.
        question_count: Đề đang có bao nhiêu câu hỏi.
        still_drafting: Còn bao nhiêu vị trí đang có job chạy. Sau một lần duyệt thì nó
            là 0 -- nhưng là 0 **đo được**, không phải 0 khai sẵn: một lần bỏ duyệt có
            thể thấy khác 0 nếu một vòng mới đã bắt đầu, và đó là một tín hiệu đáng thấy.
    """

    assessment_id: str
    state: AssessmentState
    question_count: int
    still_drafting: int


async def _owned(session: AsyncSession, asking: Asking, assessment_id: str) -> Assessment:
    """Lấy một đề của chính giáo viên đang gọi, hoặc 404.

    Args:
        session: Session của database.
        asking: Ai đang gọi.
        assessment_id: Đề nào.

    Returns:
        Row đó.

    Raises:
        HTTPException: 404 khi không có đề nào như vậy **hoặc** khi nó thuộc về người
            khác. Một câu cho cả hai, theo ADR-22.
    """
    found = await session.scalar(
        select(Assessment).where(
            Assessment.id == assessment_id, Assessment.teacher_id == asking.teacher_id
        )
    )
    if found is None:
        raise HTTPException(status_code=404, detail=_NO_SUCH)
    return found


async def _question_count(session: AsyncSession, assessment_id: str) -> int:
    """Đếm số câu hỏi đã nằm trong một đề.

    Args:
        session: Session của database.
        assessment_id: Đề nào.

    Returns:
        Số câu hỏi.
    """
    return (
        await session.scalar(
            select(func.count())
            .select_from(Question)
            .where(Question.assessment_id == assessment_id)
        )
        or 0
    )


async def _as_it_stands(session: AsyncSession, assessment: Assessment) -> Approval:
    """Đọc lại cả ba con số của một đề, sau khi quyết định đã commit.

    Một chỗ cho cả hai endpoint, và đọc thay vì khai: một response khai sẵn state mà nó
    *vừa yêu cầu* thì không chứng minh được hàng đã đổi, nên một test assert lên nó chỉ
    so hai hằng số.

    Args:
        session: Session của database.
        assessment: Row vừa được đổi và commit.

    Returns:
        State cùng hai con số, tất cả đọc từ database.
    """
    return Approval(
        assessment_id=assessment.id,
        state=state_of(assessment),
        question_count=await _question_count(session, assessment.id),
        still_drafting=await pending_count(session, assessment.id),
    )


async def _note(
    session: AsyncSession,
    asking: Asking,
    assessment_id: str,
    *,
    approved: bool,
    written: int,
) -> None:
    """Ghi quyết định vào hội thoại của giáo viên, và không bao giờ làm request gãy.

    Nuốt lỗi có chủ ý, và đây là chỗ hiện thực hoá lựa chọn mà Decision Record đã chọn.
    Lúc này state đã commit rồi: để một lỗi bay ra từ đây thì giáo viên nhận 500 cho một
    việc **đã thành công**, bấm lại thì nhận 409 *"đề đã duyệt"*, và không bao giờ nhận
    được response kèm mấy con số. Mà lỗi đó có thật chứ không chỉ là lý thuyết -- cả
    `_record` lẫn `_conversation` đều `raise` sau khi đường hồi phục đụng độ của chúng
    thất bại lần thứ hai.

    Một transcript thiếu một dòng thì tệ hơn không thiếu, nhưng nó tệ ít hơn hẳn một
    request nói "lỗi" về một việc đã xong. Và nó không im lặng: dòng log là chỗ việc đó
    đi tới.

    Args:
        session: Session của database.
        asking: Ai đã quyết định.
        assessment_id: Đề nào.
        approved: True cho duyệt, False cho bỏ duyệt. Nó chọn tên bước và chọn cờ, nên
            `_subject` của `teacher_chat` liên kết được bước này với đề.
        written: Số câu hỏi lúc đó, để transcript đọc lại được mà không phải join.

    Side effects:
        Mở một hội thoại nếu giáo viên chưa có, chèn một bước và commit. Ghi log thay vì
        raise khi việc đó thất bại.
    """
    verb = "approve" if approved else "unapprove"
    try:
        await note_action(
            session,
            asking,
            TurnRecord(
                kind="tool_result",
                # Có dấu chấm, có chủ ý: đây **không** phải tên một tool. Một bước
                # `tool_result` trong history dạy model rằng cái tên đó gọi được, và
                # `catalog_for` thì không bao giờ cấp nó -- `tools/check_contract.py`
                # giữ cho nó không bao giờ được cấp. Model đề xuất nó thì `execute` raise
                # `UnknownTool` và lượt đó tiêu một step vô ích. Một cái tên không phải
                # identifier hợp lệ thì không mời gọi chuyện đó.
                tool_name=f"teacher.{verb}",
                tool_args={"assessment_id": assessment_id},
                tool_result={
                    verb + "d": True,
                    "assessment_id": assessment_id,
                    "questions": written,
                },
            ),
        )
    except Exception:  # noqa: BLE001 -- xem docstring: một transcript thiếu dòng không được làm gãy một việc đã xong
        logger.exception("could not record the %s of %s in the transcript", verb, assessment_id)


@router.post("/teacher/assessments/{assessment_id}/approve", response_model=Approval)
async def approve(
    assessment_id: str,
    request: Request,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Approval:
    """Duyệt một đề, và từ đó khoá nội dung của nó (ADR-01).

    Thu hoạch trước, rồi mới đếm -- xem docstring của module. Hai lời từ chối ở đây là
    bất biến *`state` ↔ số câu hỏi*: một đề không có câu nào, và một đề còn câu đang
    soạn. Cái thứ hai là cái đáng giá: duyệt trong lúc job còn chạy là duyệt những câu
    hỏi mà giáo viên **chưa từng thấy**, và nó không đỏ ở đâu cả nếu không chặn ở đây --
    những câu đó sẽ lặng lẽ rơi vào một đề đã khoá nội dung.

    Args:
        assessment_id: Đề nào.
        request: Mang theo pool của queue, thứ `harvest` cần để hỏi arq.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.
        settings: Cung cấp tên queue cho lần thu hoạch.

    Returns:
        State mới cùng hai con số mà hộp xác nhận kế tiếp đọc lại.

    Raises:
        HTTPException: 404 khi đề không tồn tại hoặc thuộc về người khác (ADR-22); 409 khi
            đề không có câu hỏi nào, khi còn câu đang soạn, hoặc khi ADR-01 không có cạnh
            nào từ state hiện tại sang `đã duyệt`.

    Side effects:
        Thu hoạch mọi job đã xong vào đề, ghi state mới, và ghi một bước vào hội thoại
        của giáo viên.
    """
    asking = Asking.of(teacher)
    assessment = await _owned(session, asking, assessment_id)

    # Chặn trước khi thu hoạch, vì `harvest` tự commit: một request trả 409 -- tức một
    # request nói *không có gì xảy ra* -- vẫn kịp xoá các vị trí của brief cũ. "Thu rồi
    # mới đếm" chỉ cần đúng với **đếm**.
    #
    # Và phép kiểm ở đây **không** phải "`đã duyệt` với tới được chưa", dù đó là thứ tôi
    # viết đầu tiên và một test đã bắt: chính `harvest` là thứ làm câu trả lời đó đổi,
    # bằng cách đưa đề ra khỏi `EMPTY` khi câu đầu tiên về. Hỏi như vậy thì một đề còn
    # `EMPTY` *chỉ vì chưa ai thu hoạch* bị từ chối oan. Câu hỏi đúng là câu hỏi mà cả
    # `harvest` lẫn việc duyệt cùng cần: **nội dung còn mở không**. Cạnh cuối cùng vẫn do
    # `advance` canh, sau khi đã đếm.
    if not editable(assessment):
        raise HTTPException(
            status_code=409,
            detail=f"Đề đang ở trạng thái {readable(state_of(assessment))} nên không duyệt được.",
        )

    landed = await harvest(session, request.app.state.queue_pool, settings, assessment_id)
    if landed:
        logger.info("harvested %d question(s) of %s on the way to approval", landed, assessment_id)

    still_drafting = await pending_count(session, assessment_id)
    if still_drafting:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Còn {still_drafting} câu đang soạn. Đợi soạn xong rồi duyệt, "
                "để bạn duyệt đúng những câu mình đã đọc."
            ),
        )

    written = await _question_count(session, assessment_id)
    if not written:
        raise HTTPException(
            status_code=409,
            detail="Đề chưa có câu hỏi nào nên không duyệt được. Soạn câu hỏi trước đã.",
        )

    advance(assessment, AssessmentState.APPROVED)
    await session.commit()

    standing = await _as_it_stands(session, assessment)
    await _note(session, asking, assessment_id, approved=True, written=written)

    return standing


@router.post("/teacher/assessments/{assessment_id}/unapprove", response_model=Approval)
async def unapprove(
    assessment_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> Approval:
    """Bỏ duyệt một đề, mở nội dung của nó ra để sửa lại.

    ADR-01 đòi cạnh này phải có: nếu duyệt không bỏ được thì một lỗi chính tả trong câu 4
    sẽ cần một đề mới. Và ADR-01 chỉ riêng ra đây là **thao tác duy nhất hạ một state
    xuống**, nên nó là thao tác đáng được ghi lại nhất -- không có bằng chứng thì "ai đó
    mở lại đề này lúc nào" là câu không trả lời được.

    Không thu hoạch gì. Một đề đã duyệt không còn job nào chạy, vì chính điều kiện để nó
    được duyệt là không còn job nào.

    Args:
        assessment_id: Đề nào.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        State mới cùng số câu hỏi hiện có.

    Raises:
        HTTPException: 404 khi đề không tồn tại hoặc thuộc về người khác (ADR-22); 409 khi
            đề chưa duyệt, hoặc đã phát hành -- một đề đang phát hành thì phải thu hồi
            trước, và thu hồi là cạnh của ADR-02 chứ không phải một lần bỏ duyệt.

    Side effects:
        Ghi state mới và ghi một bước vào hội thoại của giáo viên.
    """
    asking = Asking.of(teacher)
    assessment = await _owned(session, asking, assessment_id)

    # Bảng cạnh không đủ ở đây, và đó là một bài học chứ không phải một ngoại lệ:
    # `_ALLOWED` biết *cạnh nào tồn tại*, không biết *ai đang xin đi*. Cạnh
    # `EMPTY → HAS_QUESTIONS` có thật nhưng nó tồn tại cho `harvest` -- câu hỏi đầu tiên
    # thu được -- nên một lần bỏ duyệt giao hết cho bảng sẽ đi lậu qua đúng cạnh đó và
    # nâng một đề 0 câu lên `đang soạn`, không bao giờ về lại được vì cạnh ngược chưa
    # dựng. Đo được: trước khi có ba dòng này, bỏ duyệt một đề `EMPTY` trả 200 và đề 0
    # câu nhận state `đang soạn`.
    current = state_of(assessment)
    if current is not AssessmentState.APPROVED:
        raise HTTPException(
            status_code=409,
            detail=f"Đề đang ở trạng thái {readable(current)} nên không bỏ duyệt được.",
        )

    advance(assessment, AssessmentState.HAS_QUESTIONS)
    await session.commit()

    standing = await _as_it_stands(session, assessment)
    await _note(session, asking, assessment_id, approved=False, written=standing.question_count)

    return standing
