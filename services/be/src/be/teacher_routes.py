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
một cách chia như `withdraw`.

**Phát hành là một biểu mẫu, và nó nhận nhiều lớp một lần.** ADR-02 đòi sáu tham số, nên nó
không thể là một câu hỏi có/không -- và tham số thứ nhất là **lớp**, nên một đề đi tới nhiều
lớp với một bộ hạn **riêng cho mỗi lớp**: 12A học tiết sáng thì mở buổi sáng, 12B học sau
trưa thì mở sau trưa. ADR-02 cũng cho phép **thất bại một phần**, và từ Pha 1 thì điều đó
mới biểu diễn được: trước khi `Publication` có khoá kép, "một lớp nhận được, lớp khác không"
không có chỗ để tồn tại.

**Ba endpoint đọc ở cuối file tồn tại vì giao diện cần, không vì đường ghi cần.** Cho tới
khi có màn hình, giáo viên "xem" một đề bằng cách đọc lại câu trả lời của chat; mà một bảng
10 câu hỏi thì không phải thứ nhét vào một câu trả lời được. Chúng chỉ đọc, không đổi gì, và
chúng đi qua đúng `_owned` mà phần ghi dùng -- nên ADR-22 được canh ở một chỗ cho cả hai.

**Agent không điền hộ biểu mẫu này.** Một model điền sáu mốc thời gian từ chữ "chiều mai" sẽ
tái tạo chính xác hiểu nhầm mà ADR-03 dành cả một tài liệu để ngăn, và giáo viên sẽ bấm xác
nhận vì mấy con số trông hợp lý. Nên BE trả về **lời văn của luật** cùng với biểu mẫu, và trả
lại đúng string đó ở cả ba chỗ -- xem `publication_wording`.
"""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import AwareDatetime, BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from be.agent_gateway import AgentError, validate_question
from be.assessment_state import (
    AssessmentState,
    advance,
    editable,
    may_withdraw,
    readable,
    state_of,
    withdraw,
)
from be.config import Settings, get_settings
from be.db import get_session
from be.drafting import harvest, pending_count
from be.identity import Asking, current_teacher
from be.models import (
    Answer,
    AnswerOption,
    Assessment,
    Attempt,
    DraftBrief,
    Method,
    Publication,
    Question,
    Teacher,
    aware,
)
from be.publication_wording import (
    FAULT_CLOSES_BEFORE_OPENS,
    FAULT_OPENS_IN_THE_PAST,
    FAULT_PHASE_TWO_TOO_EARLY,
    PHASE_ONE,
    PHASE_TWO,
    RECALL_RULE,
    phase_one_note,
    phase_two_note,
)
from be.resolve import Candidate, classes_with_counts
from be.teacher_chat import conversation_of, note_action
from contracts import GeneratedOption, GeneratedQuestion, SolutionMethod, TurnRecord

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["teacher-assessments"])

# Một đề của người khác đọc lên y như một đề không tồn tại (ADR-22). Hai câu trả lời phân
# biệt được sẽ cho bất kỳ ai dò xem các giáo viên khác đang có những gì, chỉ bằng cách thử
# id.
_NO_SUCH = "Không tìm thấy đề này."

# Hai state phát hành được. `PUBLISHED` nằm đây vì **thêm một lớp** là chuyện bình thường:
# ADR-02 nói một đề đi tới nhiều lớp, và `Publication` có khoá kép chính để việc đó khả
# thi -- nhưng bản đầu chỉ cho phép nó trong **một request duy nhất**. Sau đó đề ở
# `PUBLISHED`, và đường duy nhất về `APPROVED` là thu hồi **mọi** lớp, mà `may_withdraw`
# chặn khi đã qua giờ mở của lớp đầu. Nên một đề phát hành cho 12A hôm nay thì **vĩnh
# viễn** không phát hành được cho 12C.
#
# Cái giá của việc nới cổng này là một lỗ khác mở ra, và nó phải được bịt cùng lúc: xem
# `_already_running` -- nhánh ghi đè trước đây *vô tình* an toàn chỉ vì cổng state, không
# vì một luật có tên.
_RELEASABLE = frozenset({AssessmentState.APPROVED, AssessmentState.PUBLISHED})


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


async def _owned(
    session: AsyncSession, asking: Asking, assessment_id: str, *, lock: bool = True
) -> Assessment:
    """Lấy một đề của chính giáo viên đang gọi, hoặc 404.

    Khoá hàng cho tới hết transaction (`FOR UPDATE`) khi `lock`, và đó là nợ do review Pha
    4 chuyển sang. `advance` là một read-modify-write qua hai câu lệnh với một khe ở giữa,
    và nó không có bên phân xử nào -- khác hẳn `fire` và `_record`, hai chỗ đều lấy một
    unique index làm trọng tài. Ở Pha 4 hậu quả nhẹ (hai lần duyệt song song cho hai hàng
    transcript); ở Pha 5 thì `publish` song song `unapprove` là một **lost update** trên
    đúng cột `state`, và lúc đó *"`advance` là cửa duy nhất"* bảo vệ được tính hợp lệ của
    **cạnh** mà không bảo vệ được tính nguyên tử của **phép đổi**.

    `lock=False` cho đường **đọc**. Một `FOR UPDATE` trên một `GET` biến việc mở biểu mẫu
    thành một writer: trên Postgres nó chặn một `publish` hay `unapprove` song song, và
    chặn bằng một màn hình mà giáo viên chỉ đang xem.

    Trên SQLite thì `FOR UPDATE` bị bỏ qua -- không phải lỗi, chỉ là nó không có gì để
    làm: toàn bộ database đã nằm dưới một khoá ghi. Nên mọi test ở đây xanh vì một lý do
    khác với lý do nó xanh trên Postgres, và điều đó đáng nói ra chứ không đáng để trôi.

    Args:
        session: Session của database.
        asking: Ai đang gọi.
        assessment_id: Đề nào.
        lock: False cho một đường chỉ đọc.

    Returns:
        Row đó, đã khoá khi `lock`.

    Raises:
        HTTPException: 404 khi không có đề nào như vậy **hoặc** khi nó thuộc về người
            khác. Một câu cho cả hai, theo ADR-22.
    """
    query = select(Assessment).where(
        Assessment.id == assessment_id, Assessment.teacher_id == asking.teacher_id
    )
    found = await session.scalar(query.with_for_update() if lock else query)
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
    title: str,
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
        title: Tên đề. Thẻ kết quả đọc nó -- `Đã duyệt đề` trần, không nói đề nào, là một
            biên bản trả lời hụt đúng câu hỏi giáo viên sẽ hỏi lại sau một tuần. Trước
            06/10/2026 field này không được ghi, nên thẻ duyệt im lặng về tên đề trong khi
            giao diện đã tính sẵn chỗ để in nó.
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
                    "title": title,
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

    # Lấy lại khoá. `harvest` **tự commit**, và một COMMIT nhả mọi khoá hàng -- nên nếu
    # không đọc lại ở đây thì `advance` + `commit` bên dưới chạy **không có khoá**, tức
    # đúng cái read-modify-write mà `FOR UPDATE` được thêm vào để bảo vệ. Và trạng thái có
    # thể đã đổi trong khe đó, nên đọc lại cũng là đọc lại sự thật chứ không chỉ lấy khoá.
    assessment = await _owned(session, asking, assessment_id)
    if not editable(assessment):
        raise HTTPException(
            status_code=409,
            detail=f"Đề đang ở trạng thái {readable(state_of(assessment))} nên không duyệt được.",
        )

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
    await _note(
        session, asking, assessment_id, title=assessment.title, approved=True, written=written
    )

    return standing


async def _take_back_every_class(
    session: AsyncSession, asking: Asking, assessment: Assessment
) -> None:
    """Thu hồi đề khỏi **mọi** lớp còn giữ nó, rồi hạ state về `đã duyệt`.

    Đây là nửa ADR-02 của một lần bỏ duyệt. `withdraw_from_class` làm việc này cho một
    lớp; hàm này làm cho tất cả, và nó dùng lại đúng hai luật ấy chứ không viết luật mới:
    `may_withdraw` canh giờ mở, và `withdraw` là cửa duy nhất hạ state từ `đã phát hành`.

    **Hoặc tất cả, hoặc không gì cả.** Một lớp đã qua giờ mở thì cả thao tác dừng lại và
    không lớp nào bị thu hồi -- để lại một đề nửa thu hồi nửa không là để lại đúng cái
    trạng thái mà không màn hình nào đọc ra nổi, và giáo viên thì tin rằng mình đã hoàn
    tác. Phép kiểm chạy hết một lượt **trước** khi ghi dòng nào.

    Phép kiểm ấy là `_why_undo_is_shut`, dùng chung với biểu mẫu -- nên câu nút khoá hiện ra
    **trước** cú bấm và câu 409 sau cú bấm không thể lệch nhau. Hai bản cài đặt của cùng một
    luật là hai luật, và cái lệch đầu tiên sẽ là một nút bấm được cho một việc không làm được.

    Args:
        session: Session của database.
        asking: Giáo viên đang hỏi. Dùng để tra tên lớp cho câu từ chối.
        assessment: Đề đang ở `đã phát hành`.

    Raises:
        HTTPException: 409 khi một lớp đã qua giờ mở, kèm tên lớp -- *"một lớp nào đó"*
            là một lời từ chối mà giáo viên không hành động theo được.

    Side effects:
        Đặt `recalled_at` cho mọi hàng còn sống và hạ `assessment.state`. Không commit.
    """
    shut = await _why_undo_is_shut(session, assessment.id, await _classes_of(session, asking))
    if shut:
        raise HTTPException(status_code=409, detail=shut)

    now = _now()
    for one in await _live_publications(session, assessment.id):
        one.recalled_at = now
    withdraw(assessment, still_held=0)


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
            đề chưa duyệt, hoặc khi một lớp đã qua giờ mở -- lúc ấy học sinh đã có thể
            nhìn thấy đề, nên không lấy lại được nữa.

    Side effects:
        Thu hồi mọi lớp còn giữ đề, ghi state mới, và ghi một bước vào hội thoại của
        giáo viên.
    """
    asking = Asking.of(teacher)
    assessment = await _owned(session, asking, assessment_id)

    # Một đề **đã phát hành** cũng bỏ duyệt được, và nó phải thế. Trước đợt 06/10/2026
    # endpoint này trả 409 cho state ấy, với lý lẽ *"thu hồi trước đã"* -- mà màn hình
    # lại vẫn vẽ nút `Hoàn tác`, và `Panel` nuốt mất câu 409, nên cú bấm không làm gì và
    # không nói gì. Đo được trên trình duyệt thật: bấm, im lặng, đề vẫn phát hành.
    #
    # Và cái lý lẽ ấy sai ở chỗ nó bắt giáo viên làm hai việc cho một ý định. Muốn sửa
    # một đề đã phát hành thì đường duy nhất là hoàn tác; bắt họ thu hồi từng lớp trước
    # là bắt họ tự dựng lại một thao tác mà hệ thống biết cách làm trọn.
    if state_of(assessment) is AssessmentState.PUBLISHED:
        await _take_back_every_class(session, asking, assessment)

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
    await _note(
        session,
        asking,
        assessment_id,
        title=assessment.title,
        approved=False,
        written=standing.question_count,
    )

    return standing


class TimingRules(BaseModel):
    """Ba câu luật về thời gian, đúng như BE viết chúng.

    Đi kèm **cả** biểu mẫu, **cả** bản xem trước của hộp xác nhận, và **cả** biên bản sau
    khi phát hành. Giống hệt nhau từng chữ ở ba chỗ, và đó là một tính chất của code chứ
    không phải một việc ai đó phải nhớ: ba chỗ cùng đọc một hằng số trong
    `publication_wording`.

    Vì sao phải thế: ADR-03 nói giờ đóng là hạn **vào**, ADR-15 nói hạn pha 2 thì **cắt
    giữa chừng** -- hai luật đối nhau trên cùng một biểu mẫu. Để FE tự viết lời giải thích
    là có ba bản, và ba cách diễn đạt cho một luật là ba luật.

    Attributes:
        phase_one: Luật của giờ đóng (ADR-03), đã dựng sẵn với số của lần phát hành này.
        phase_two: Luật của hạn pha 2 (ADR-15), ngược lại luật trên.
        recall: Cửa sổ thu hồi (ADR-02), thứ quyết định lần này còn lấy lại được không.
        phase_one_form: **Khuôn** của câu trên, với hai chỗ trống `{closes}` và `{last}`.
            Chỉ biểu mẫu dùng tới: ở đó chưa có giờ nào lúc mở màn, nên một câu dựng sẵn
            chỉ có thể là câu `--:--`, và nó đứng ngay dưới mấy ô nhập trông như sắp đổi
            theo con số vừa gõ mà không bao giờ đổi được. Gửi khuôn thì biểu mẫu điền được
            ngay lúc gõ, và chữ nghĩa vẫn chỉ có một nơi — `publication_wording` dựng câu
            thật bằng đúng khuôn này.
        phase_two_form: Khuôn của câu pha 2, với `{deadline}` và `{rate}`.
        opens_in_the_past: Lời từ chối khi giờ mở không ở tương lai (ADR-02).
        closes_before_opens: Lời từ chối khi giờ đóng không sau giờ mở.
        phase_two_too_early: Lời từ chối khi hạn pha 2 không sau giờ nộp cuối (ADR-15).

    Ba lời từ chối cuối đi lên **cùng biểu mẫu**, không chờ tới lúc bị từ chối. Cổng thật
    vẫn là `_schedule_fault` ở BE — FE không được phép là nơi duy nhất kiểm — nhưng một
    cổng chỉ nói ra sau cú bấm thì giáo viên đã gõ xong sáu ô rồi mới biết mình gõ sai.
    Gửi lời ấy lên thì biểu mẫu nói được **lúc đang gõ**, bằng đúng chữ mà BE sẽ dùng nếu
    cú bấm ấy đi tới nơi.
    """

    phase_one: str = Field(default_factory=phase_one_note)
    phase_two: str = Field(default_factory=phase_two_note)
    recall: str = RECALL_RULE
    phase_one_form: str = PHASE_ONE
    phase_two_form: str = PHASE_TWO
    opens_in_the_past: str = FAULT_OPENS_IN_THE_PAST
    closes_before_opens: str = FAULT_CLOSES_BEFORE_OPENS
    phase_two_too_early: str = FAULT_PHASE_TWO_TOO_EARLY


class ClassOption(BaseModel):
    """Một lớp mà giáo viên này được phát hành cho.

    Attributes:
        class_id: Id để gửi lại.
        name: Tên lớp như giáo viên gọi.
        student_count: Bao nhiêu học sinh, vì đó là thứ phân biệt hai lớp cùng tên
            (ADR-23 dùng đúng con số này cho câu hỏi làm rõ).
        published: Lớp này đã đang giữ đề chưa. Phát hành lại cho cùng một lớp **thay
            thế** điều kiện của lớp đó chứ không thêm một bộ thứ hai.
    """

    class_id: str
    name: str
    student_count: int
    published: bool


class PublishForm(BaseModel):
    """Thứ cần để vẽ biểu mẫu phát hành, không có giá trị nào bịa sẵn.

    Không có mặc định cho sáu tham số, có chủ ý. Một giá trị gợi sẵn là một giá trị giáo
    viên sẽ bấm qua, và ADR-03 ghi rõ hiểu nhầm về giờ đóng gây hại theo chiều **ngược**:
    người muốn bài nộp xong trước 18:00 sẽ đặt giờ đóng 17:45 để bù, tức tự cắt mười lăm
    phút của cả lớp.

    Attributes:
        assessment_id: Đề nào.
        title: Tên đề, để hộp xác nhận đọc lại được.
        state: State hiện tại. Chưa `đã duyệt` thì biểu mẫu không nên mở.
        question_count: Bao nhiêu câu.
        can_publish: Đề này phát hành được chưa.
        reason: Vì sao không, khi `can_publish` là False.
        classes: Các lớp chọn được, kèm lớp nào đã giữ đề.
        rules: Lời văn của luật, cùng string mà hai payload kia trả về.
        undo_blocked: Vì sao `Hoàn tác` không bấm được, hoặc rỗng khi còn lùi được.

            **Biểu mẫu nói trước cú bấm**, cùng khuôn với cách nó chặn một cửa sổ thời
            gian vô lý. Một nút bấm được rồi mới nhận 409 là một nút hứa một việc hệ
            thống đã biết là không làm được — và đường ấy từng tệ hơn thế: `Panel` nuốt
            mất câu 409, nên cú bấm không làm gì và **không nói gì**.

            Câu này do BE viết, như mọi câu luật khác ở đây. FE chỉ hiện nó.
    """

    assessment_id: str
    title: str
    state: AssessmentState
    question_count: int
    can_publish: bool
    reason: str = ""
    classes: tuple[ClassOption, ...] = ()
    rules: TimingRules = TimingRules()
    undo_blocked: str = ""


class Schedule(BaseModel):
    """Năm tham số thời gian của ADR-02, dùng chung cho **mọi** lớp của một lần phát hành.

    Tham số thứ nhất của ADR-02 là **lớp**, và nó rời khỏi đây: một lần phát hành có một
    khung giờ, còn danh sách lớp là `class_ids` của `PublishRequest`.

    **Đây là siết hợp đồng cho khớp thực tế, không đổi hành vi.** Biểu mẫu phát hành
    (`PublishSettings.schedules()`) đã gửi cùng một bộ năm giá trị cho mọi lớp từ đầu --
    trên màn hình chỉ có một bộ ô nhập. Hợp đồng cũ cho phép diễn tả một thứ giao diện
    không dựng được, và cái giá là thật: màn hình phải in giờ *"của từng lớp"* cho một con
    số chung, và câu an toàn trên thẻ hứa một mốc thu hồi mà giáo viên không đọc ra nổi là
    mốc nào.

    Attributes:
        opens_at: Giờ mở. Phải ở tương lai và trước giờ đóng (ADR-02).
        closes_at: Hạn **vào**, không phải hạn nộp (ADR-03).
        phase1_minutes: Thời gian làm bài, tính từ lúc học sinh vào.
        phase2_minutes_per_question: Một **tỉ lệ**, không phải một khoảng (ADR-15).
        remediation_deadline: Mốc tuyệt đối kết thúc pha 2, phải sau giờ đóng.
    """

    # `AwareDatetime`, không phải `datetime`: một giá trị naive thì BE không có cách nào
    # biết nó là giờ nào. Trước khi có ràng buộc này, `2026-10-01T08:00` được nhận và hiểu
    # là 08:00 UTC, tức 15:00 ở Việt Nam -- một giáo viên đặt tiết sáng nhận được tiết
    # chiều, âm thầm. Một 422 ở đây là phép kiểm rẻ nhất có thể.
    opens_at: AwareDatetime
    closes_at: AwareDatetime
    phase1_minutes: int = Field(gt=0, le=600)
    phase2_minutes_per_question: int = Field(gt=0, le=120)
    remediation_deadline: AwareDatetime


class PublishRequest(BaseModel):
    """Phát hành một đề cho một hoặc nhiều lớp.

    Attributes:
        schedule: Một khung giờ cho cả lần phát hành này.
        class_ids: Những lớp nhận đề. Không rỗng.
        preview: True thì tính toàn bộ rồi trả kết quả mà **không ghi gì**. Đây là thứ
            hộp xác nhận của ADR-02 đọc: nó phải đọc lại đúng giá trị vừa nhập, và cách
            duy nhất chắc chắn đúng là để cùng một đoạn code tính ra chúng. Một hộp xác
            nhận tự tính lại là một bản cài đặt thứ hai của cùng một luật.
    """

    schedule: Schedule
    class_ids: tuple[str, ...] = Field(min_length=1)
    preview: bool = False

    @model_validator(mode="after")
    def _each_class_at_most_once(self) -> "PublishRequest":
        """Từ chối một lớp xuất hiện hai lần trong cùng một yêu cầu.

        Một lớp hai lần nay **không** dựng ra hai giờ mở khác nhau được nữa -- khung giờ
        là một -- nhưng nó vẫn là một yêu cầu nói dối: kết quả trả về hai dòng
        `published=True` cho một hàng trong database, và hộp xác nhận của ADR-02 đọc lại
        một danh sách dài hơn thứ thật sự xảy ra.

        Returns:
            Chính nó, khi không lớp nào trùng.

        Raises:
            ValueError: Khi một `class_id` xuất hiện nhiều hơn một lần.
        """
        if len(set(self.class_ids)) != len(self.class_ids):
            raise ValueError("mỗi lớp chỉ được xuất hiện một lần trong một lần phát hành")
        return self


class ClassResult(BaseModel):
    """Một lớp đã nhận được đề hay không, và vì sao không.

    Attributes:
        class_id: Lớp nào.
        class_name: Tên lớp, để biên bản đọc được mà không phải join.
        published: Lớp này nhận được chưa.
        reason: Vì sao không.
        opens_at: Giờ mở đã ghi, đọc lại từ thứ sẽ được lưu.
        closes_at: Hạn vào đã ghi.
        remediation_deadline: Hạn pha 2 đã ghi.
        withdrawable_until: Thu hồi được tới lúc nào. Bằng `opens_at`, nêu ra riêng vì
            đó là con số mà giáo viên cần biết chứ không phải suy ra.
        phase_one_note: Luật của pha 1 **đã điền số thật của lớp này** — kể cả giờ nộp
            cuối, thứ là một phép tính. ADR-02 đòi hộp xác nhận đọc lại giá trị thật, nên
            con số ấy do BE tính một lần chứ không do mỗi màn hình tự tính.
        phase_two_note: Luật của pha 2, cũng đã điền số, và nó **ngược lại** câu trên.
    """

    class_id: str
    class_name: str = ""
    published: bool
    reason: str = ""
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    remediation_deadline: datetime | None = None
    withdrawable_until: datetime | None = None
    phase_one_note: str = ""
    phase_two_note: str = ""


class PublishResult(BaseModel):
    """Biên bản của một lần phát hành, từng lớp một.

    Attributes:
        assessment_id: Đề nào.
        state: State sau lệnh này, đọc lại từ hàng.
        preview: True khi không có gì được ghi.
        classes: Kết quả từng lớp, cùng thứ tự với yêu cầu.
        rules: Lời văn của luật, **cùng string** mà biểu mẫu đã trả về.
    """

    assessment_id: str
    state: AssessmentState
    preview: bool
    classes: tuple[ClassResult, ...]
    rules: TimingRules = TimingRules()


def _now() -> datetime:
    return datetime.now(UTC)


async def _classes_of(session: AsyncSession, asking: Asking) -> dict[str, Candidate]:
    """Các lớp của giáo viên đang gọi, tra theo id, kèm số học sinh.

    Dùng `resolve.classes_with_counts` thay vì tự viết câu query: nó đã đếm học sinh
    bằng một `outerjoin` và đã sắp theo `(name, id)`. Viết lại ở đây là có hai câu
    query cho một câu hỏi, và chúng sẽ lệch nhau ở đúng chỗ khó thấy nhất -- con số học
    sinh, thứ mà ADR-23 dùng để phân biệt hai lớp cùng tên.

    Trả `Candidate` chứ không trả hàng ORM, có chủ ý: `len(row.students)` trong ngữ cảnh
    async là một lazy-load, tức `MissingGreenlet` -- cùng cái bẫy mà cả file này tránh
    bằng cách làm việc với giá trị.

    Args:
        session: Session của database.
        asking: Ai đang gọi.

    Returns:
        Tra theo `class_id`, thứ tự chèn theo tên lớp.
    """
    return {row.class_id: row for row in await classes_with_counts(session, asking)}


async def _live_publications(session: AsyncSession, assessment_id: str) -> list[Publication]:
    """Các lần phát hành **chưa** bị thu hồi của một đề.

    Một hàng đã thu hồi vẫn ở lại làm sổ sách, nên mọi câu hỏi dạng "lớp nào đang giữ đề
    này" đều phải lọc nó ra -- nếu không thì thu hồi lớp cuối cùng sẽ không bao giờ đưa
    đề về `đã duyệt`.

    Args:
        session: Session của database.
        assessment_id: Đề nào.

    Returns:
        Các hàng còn hiệu lực.
    """
    return list(
        await session.scalars(
            select(Publication).where(
                Publication.assessment_id == assessment_id,
                Publication.recalled_at.is_(None),
            )
        )
    )


def _schedule_fault(wanted: Schedule, now: datetime) -> str:
    """Lý do một khung giờ không dùng được, hoặc chuỗi rỗng.

    Trả về **lý do** chứ không raise, vì ADR-02 cho phép thất bại một phần: một lớp không
    nhận được đề thì những lớp còn lại vẫn nhận. Một `HTTPException` ở đây sẽ biến toàn
    bộ yêu cầu thành một lần từ chối, tức biến một điều khoản của ADR-02 thành không
    biểu diễn được.

    Khung giờ nay chung cho mọi lớp, nên một khung giờ sai làm **mọi** lớp trượt -- và đó
    đúng là câu trả lời đúng: không còn chuyện lớp này đúng giờ còn lớp kia sai giờ.

    Args:
        wanted: Khung giờ của lần phát hành này.
        now: Bây giờ, tz-aware.

    Returns:
        Một câu tiếng Việt, hoặc rỗng khi bộ tham số dùng được.
    """
    opens_at = aware(wanted.opens_at).astimezone(UTC)
    closes_at = aware(wanted.closes_at).astimezone(UTC)
    deadline = aware(wanted.remediation_deadline).astimezone(UTC)

    if opens_at <= now:
        # ADR-02: giờ mở phải ở tương lai. Không có luật này thì cửa sổ thu hồi dài
        # không giây nào mà chẳng ai vi phạm luật gì.
        return FAULT_OPENS_IN_THE_PAST
    if closes_at <= opens_at:
        return FAULT_CLOSES_BEFORE_OPENS
    # ADR-15: hạn pha 2 "dài hơn hẳn hạn của pha 1". Mốc đúng là giờ **nộp cuối** của pha
    # 1 -- `closes_at + phase1_minutes` -- chứ không phải giờ đóng: người vào đúng giây giờ
    # đóng vẫn còn cả `phase1_minutes` để làm. So với giờ đóng thì bản trước nhận một hạn
    # pha 2 chỉ sau giờ đóng một phút, và hai câu luật trong **cùng một payload** tự phủ
    # định nhau -- đo được: pha 1 chạy tới 15:28 trong khi pha 2 đóng lúc 14:29. Chính con
    # số mà comment cũ nêu tên lại là con số nó không dùng.
    last_submission = closes_at + timedelta(minutes=wanted.phase1_minutes)
    if deadline <= last_submission:
        return FAULT_PHASE_TWO_TOO_EARLY
    return ""


async def _already_running(session: AsyncSession, existing: Publication, now: datetime) -> str:
    """Lý do không được ghi đè một lần phát hành đang sống, hoặc chuỗi rỗng.

    Tồn tại vì cổng state vừa được nới ra cho phép thêm lớp. Trước đó nhánh ghi đè **vô
    tình** an toàn: đề ở `PUBLISHED` thì cả request bị từ chối, nên không ai tới được chỗ
    ghi đè một lớp đang làm bài. An toàn nhờ một tác dụng phụ không phải an toàn.

    Hai lý do, và chúng là hai thứ khác nhau:

    - **Đã qua giờ mở.** Ghi lại `opens_at`/`closes_at` lúc đó là sửa hạn dưới chân học
      sinh đang làm, và nó còn mở một đường đi vòng qua ADR-02: đặt `recalled_at = None`
      cộng một `opens_at` mới ở tương lai thì `may_withdraw` lại cho thu hồi một lần phát
      hành mà học sinh **đã** vào.
    - **Đã có người làm bài.** Đủ để chặn kể cả khi đồng hồ nói chưa tới giờ mở -- một
      `Attempt` tồn tại là bằng chứng mạnh hơn một mốc thời gian.

    Args:
        session: Session của database.
        existing: Hàng `Publication` đang có của lớp đó.
        now: Bây giờ, tz-aware.

    Returns:
        Một câu tiếng Việt, hoặc rỗng khi ghi đè được.
    """
    if existing.recalled_at is not None:
        # Đã thu hồi thì không còn gì đang chạy: phát hành lại là một lần phát hành mới.
        return ""
    if not may_withdraw(aware(existing.opens_at), now):
        return "lớp này đã qua giờ mở nên không đổi được cài đặt phát hành"
    started = await session.scalar(
        select(func.count())
        .select_from(Attempt)
        .where(
            Attempt.assessment_id == existing.assessment_id,
            Attempt.class_id == existing.class_id,
        )
    )
    if started:
        return "lớp này đã có học sinh làm bài nên không đổi được cài đặt phát hành"
    return ""


async def _publish_one(
    session: AsyncSession,
    assessment_id: str,
    class_id: str,
    wanted: Schedule,
    *,
    owned: dict[str, Candidate],
    now: datetime,
    write: bool,
) -> ClassResult:
    """Áp khung giờ chung cho một lớp, hoặc nói vì sao không.

    Args:
        session: Session của database.
        assessment_id: Đề nào.
        class_id: Lớp nào.
        wanted: Khung giờ chung của lần phát hành này.
        owned: Các lớp của giáo viên, tra theo id. Lớp không có trong đây đọc lên y như
            một lớp không tồn tại (ADR-22).
        now: Bây giờ, tz-aware.
        write: False thì chỉ tính, không ghi gì.

    Returns:
        Kết quả của riêng lớp này.

    Side effects:
        Khi `write`, thêm hoặc thay thế một hàng `Publication`. Không commit.
    """
    school_class = owned.get(class_id)
    if school_class is None:
        return ClassResult(class_id=class_id, published=False, reason="không tìm thấy lớp")

    fault = _schedule_fault(wanted, now)
    if fault:
        return ClassResult(
            class_id=class_id, class_name=school_class.name, published=False, reason=fault
        )

    # Chuẩn hoá về UTC **trước** mọi việc khác, và đây là ca duy nhất mà SQLite và
    # Postgres cho hai kết quả khác nhau. Dialect SQLite bỏ `tzinfo` mà **không** chuyển
    # đổi, nên một `19:23+07:00` ghi xuống thành `19:23` naive rồi đọc lại thành `19:23Z`
    # -- muộn hơn bảy giờ so với điều giáo viên đặt. Postgres `timestamptz` thì lưu đúng.
    # Đo được trước khi sửa. `aware()` không cứu được: nó **gắn nhãn**, không chuyển đổi,
    # nên nó là sai công cụ cho việc chuẩn hoá đầu vào.
    #
    # Và hộp xác nhận không bắt được lỗi này mà còn **che** nó: nó đọc lại đúng chuỗi vừa
    # gõ, nên "đọc lại đúng giá trị vừa nhập" của ADR-02 nhìn ra vẫn đúng.
    opens_at = aware(wanted.opens_at).astimezone(UTC)
    closes_at = aware(wanted.closes_at).astimezone(UTC)
    deadline = aware(wanted.remediation_deadline).astimezone(UTC)

    settled = ClassResult(
        class_id=class_id,
        class_name=school_class.name,
        published=True,
        opens_at=opens_at,
        closes_at=closes_at,
        remediation_deadline=deadline,
        withdrawable_until=opens_at,
        # Hai câu luật, đã điền số của **lớp này**. Đây là lý do `preview` tồn tại: hộp
        # xác nhận đọc lại đúng mấy câu này, và chúng do cùng đoạn code tính ra -- nên
        # "giống hệt nhau ở ba nơi" đúng cả với phần số, không chỉ với phần chữ.
        # Hai câu luật in theo **múi giờ giáo viên vừa gõ**, không theo UTC. Lưu thì lưu
        # UTC; hiện thì phải hiện bằng con số họ đang đọc. Tìm ra bằng một lượt chạy
        # thật: gửi 08:45+07:00 thì câu luật in "01:45", và một giáo viên đọc con số đó
        # thì nó không nói gì cả -- đúng loại hiểu nhầm mà ADR-03 dành cả tài liệu để
        # ngăn. Không test nào thấy được, vì mọi test đều gửi UTC nên giờ hiện trùng giờ
        # gửi. Offset đi kèm request chính là múi giờ người gửi đang đọc.
        phase_one_note=phase_one_note(aware(wanted.closes_at), wanted.phase1_minutes),
        phase_two_note=phase_two_note(
            aware(wanted.remediation_deadline), wanted.phase2_minutes_per_question
        ),
    )
    # Phép kiểm này chạy **trước** nhánh preview, và thứ tự đó là cả điều khoản của
    # ADR-02. Trước đây nó nằm sau: một lớp đã qua giờ mở được preview báo `published`
    # rồi lần gửi thật mới từ chối, nên hộp xác nhận hứa một việc mà hệ thống đã biết là
    # không làm được. "Hộp xác nhận đọc lại giá trị thật" chỉ đúng khi preview đi qua
    # đúng những cổng mà lần ghi sẽ đi qua.
    #
    # Tìm ra bằng một lượt chạy thật **qua giao diện**: bấm xem trước, hộp hiện ra đầy
    # đủ hai câu luật, bấm phát hành và nhận lại một dòng từ chối. Không test nào thấy,
    # vì mọi test preview đều dùng lớp chưa phát hành bao giờ.
    existing = await session.get(Publication, (assessment_id, class_id))
    if existing is not None and (running := await _already_running(session, existing, now)):
        return ClassResult(
            class_id=class_id, class_name=school_class.name, published=False, reason=running
        )

    if not write:
        return settled

    if existing is None:
        session.add(
            Publication(
                assessment_id=assessment_id,
                class_id=class_id,
                opens_at=opens_at,
                closes_at=closes_at,
                phase1_minutes=wanted.phase1_minutes,
                phase2_minutes_per_question=wanted.phase2_minutes_per_question,
                remediation_deadline=deadline,
                published_at=now,
            )
        )
    else:
        # Phát hành lại cho **cùng** một lớp thay thế điều kiện của lớp đó chứ không thêm
        # một bộ thứ hai -- vẫn là luật ban đầu của bảng này, chỉ áp ở đúng cấp mà nó
        # thực sự nói về. Và nó xoá `recalled_at`: phát hành lại sau khi thu hồi là một
        # lần phát hành mới, không phải một lần hồi sinh lần cũ.
        existing.opens_at = opens_at
        existing.closes_at = closes_at
        existing.phase1_minutes = wanted.phase1_minutes
        existing.phase2_minutes_per_question = wanted.phase2_minutes_per_question
        existing.remediation_deadline = deadline
        existing.published_at = now
        existing.recalled_at = None
    return settled


async def _note_publication(
    session: AsyncSession,
    asking: Asking,
    assessment_id: str,
    landed: list[ClassResult],
) -> None:
    """Ghi lần phát hành vào hội thoại của giáo viên.

    Cùng luật với `_note`: nuốt lỗi và log, vì lúc này các hàng `Publication` đã commit
    rồi và một transcript thiếu một dòng tệ ít hơn hẳn một request nói "lỗi" về một việc
    đã xong.

    Ghi **tên lớp**, không chỉ id. Một dòng transcript nói "đã phát hành cho 2 lớp" là
    một dòng không trả lời được câu hỏi duy nhất giáo viên sẽ hỏi lại sau một tuần.

    Args:
        session: Session của database.
        asking: Ai đã phát hành.
        assessment_id: Đề nào.
        landed: Những lớp đã nhận được.

    Side effects:
        Chèn một bước và commit, hoặc ghi log khi việc đó thất bại.
    """
    try:
        await note_action(
            session,
            asking,
            TurnRecord(
                kind="tool_result",
                # Dấu chấm, cùng lý do với `teacher.approve`: đây không phải tên một tool,
                # và một bước `tool_result` trong history dạy model rằng cái tên đó gọi
                # được.
                tool_name="teacher.publish",
                tool_args={"assessment_id": assessment_id},
                tool_result={
                    "published": True,
                    "assessment_id": assessment_id,
                    "classes": [row.class_name or row.class_id for row in landed],
                },
            ),
        )
    except Exception:  # noqa: BLE001 -- xem docstring
        logger.exception("could not record the publication of %s", assessment_id)


async def _why_undo_is_shut(
    session: AsyncSession, assessment_id: str, owned: dict[str, Candidate]
) -> str:
    """Vì sao `Hoàn tác` không bấm được, hoặc chuỗi rỗng.

    Cùng phép kiểm mà `_take_back_every_class` chạy, hỏi trước một nhịp. Hai chỗ dùng chung
    `may_withdraw` nên chúng không lệch được: nếu hàm này nói còn lùi được mà cú bấm lại
    nhận 409 thì biểu mẫu đang nói dối, và đó là lỗi tệ hơn một nút khoá nhầm.

    Args:
        session: Session của database.
        assessment_id: Đề nào.
        owned: Các lớp của giáo viên, tra theo id -- để câu từ chối gọi tên lớp.

    Returns:
        Một câu tiếng Việt, hoặc rỗng khi mọi lớp còn chưa tới giờ mở.
    """
    now = _now()
    opened = [
        one
        for one in await _live_publications(session, assessment_id)
        if not may_withdraw(aware(one.opens_at), now)
    ]
    if not opened:
        return ""
    which = ", ".join(
        sorted(
            owned[one.class_id].name if one.class_id in owned else one.class_id for one in opened
        )
    )
    return f"Đã qua giờ mở của lớp {which} nên không hoàn tác được nữa. {RECALL_RULE}"


@router.get("/teacher/assessments/{assessment_id}/publish-form", response_model=PublishForm)
async def publish_form(
    assessment_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> PublishForm:
    """Những gì cần để vẽ biểu mẫu phát hành, kèm lời văn của luật.

    Không trả giá trị gợi sẵn cho sáu tham số nào. Một giá trị gợi sẵn là một giá trị
    giáo viên sẽ bấm qua, và đây đúng là chỗ ADR-03 nói hiểu nhầm gây hại.

    Args:
        assessment_id: Đề nào.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        Trạng thái đề, danh sách lớp, và ba câu luật.

    Raises:
        HTTPException: 404 khi đề không tồn tại hoặc thuộc về người khác (ADR-22).
    """
    asking = Asking.of(teacher)
    assessment = await _owned(session, asking, assessment_id, lock=False)

    written = await _question_count(session, assessment_id)
    current = state_of(assessment)
    holding = {row.class_id for row in await _live_publications(session, assessment_id)}

    reason = ""
    if current not in _RELEASABLE:
        reason = (
            f"Đề đang ở trạng thái {readable(current)}; chỉ đề đã duyệt hoặc đang phát hành "
            "mới phát hành được."
        )

    owned = await _classes_of(session, asking)
    classes = tuple(
        ClassOption(
            class_id=row.class_id,
            name=row.name,
            student_count=row.student_count,
            published=row.class_id in holding,
        )
        for row in owned.values()
    )

    return PublishForm(
        assessment_id=assessment_id,
        title=assessment.title,
        state=current,
        question_count=written,
        can_publish=not reason,
        reason=reason,
        classes=classes,
        undo_blocked=await _why_undo_is_shut(session, assessment_id, owned),
    )


@router.post("/teacher/assessments/{assessment_id}/publications", response_model=PublishResult)
async def publish(
    assessment_id: str,
    wanted: PublishRequest,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> PublishResult:
    """Phát hành một đề cho một hoặc nhiều lớp, mỗi lớp một bộ hạn riêng.

    **Từ chối đề chưa duyệt**, và đây là chỗ dòng *"Teacher approves an assessment before
    release"* trong bảng Invariants của `AGENTS.md` chuyển từ đúng-về-chữ sang
    đúng-về-tinh-thần: trước Pha 5 không đường HTTP nào phát hành được đề chưa duyệt, vì
    không đường HTTP nào phát hành cả.

    **Thất bại một phần là chuyện bình thường, không phải lỗi.** ADR-02 cho phép một lớp
    nhận được và lớp khác không, nên một bộ tham số sai giờ trả về lý do của riêng lớp đó
    chứ không làm cả yêu cầu trượt. Một `HTTPException` cho một lớp sai sẽ biến điều khoản
    ấy thành không biểu diễn được.

    Args:
        assessment_id: Đề nào.
        wanted: Một khung giờ, danh sách lớp, cùng cờ `preview`.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        Kết quả từng lớp, cùng lời văn của luật. `preview` thì không ghi gì.

    Raises:
        HTTPException: 404 khi đề không tồn tại hoặc thuộc về người khác (ADR-22); 409 khi
            đề chưa duyệt. Một lớp sai thì **không** raise -- nó là một dòng trong
            `classes`.

    Side effects:
        Khi không `preview`: thêm hoặc thay thế một hàng `Publication` cho mỗi lớp nhận
        được, đưa đề sang `đã phát hành`, và ghi một bước vào hội thoại của giáo viên.
    """
    asking = Asking.of(teacher)
    assessment = await _owned(session, asking, assessment_id)

    current = state_of(assessment)
    if current not in _RELEASABLE:
        raise HTTPException(
            status_code=409,
            detail=f"Đề đang ở trạng thái {readable(current)} nên không phát hành được.",
        )

    now = _now()
    owned = await _classes_of(session, asking)
    results = tuple(
        [
            await _publish_one(
                session,
                assessment_id,
                one,
                wanted.schedule,
                owned=owned,
                now=now,
                write=not wanted.preview,
            )
            for one in wanted.class_ids
        ]
    )

    if wanted.preview:
        # Không ghi gì, và không commit gì. Cùng một đoạn code đã tính ra mấy mốc thời
        # gian mà hộp xác nhận sẽ đọc, nên "đọc lại đúng giá trị vừa nhập" là một tính
        # chất của code chứ không phải một việc FE phải làm đúng.
        return PublishResult(
            assessment_id=assessment_id, state=current, preview=True, classes=results
        )

    landed = [row for row in results if row.published]
    # Chỉ tiến cạnh khi đang ở `đã duyệt`. Thêm một lớp vào một đề **đã** phát hành là
    # chuyện bình thường, và `_ALLOWED[PUBLISHED]` để rỗng nên `advance` sẽ từ chối
    # `đã phát hành → đã phát hành` -- đúng như nó phải làm: không có cạnh đó. Cái cần ở
    # đây không phải một cạnh mới mà là **không đi cạnh nào**.
    if landed and current is AssessmentState.APPROVED:
        advance(assessment, AssessmentState.PUBLISHED)
    await session.commit()

    if landed:
        await _note_publication(session, asking, assessment_id, landed)

    return PublishResult(
        assessment_id=assessment_id,
        state=state_of(assessment),
        preview=False,
        classes=results,
    )


@router.post(
    "/teacher/assessments/{assessment_id}/publications/{class_id}/withdraw",
    response_model=PublishResult,
)
async def withdraw_from_class(
    assessment_id: str,
    class_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> PublishResult:
    """Thu hồi đề khỏi **một** lớp, nếu chưa tới giờ mở của lớp đó.

    Thu hồi **mềm**: hàng `Publication` ở lại với `recalled_at` đã đặt. Xoá hàng đi sẽ mất
    luôn bằng chứng rằng đề từng được phát hành cho lớp ấy, và `published_at`/`recalled_at`
    tồn tại chính là để làm sổ sách đó. Với học sinh thì không khác gì: `_publication` và
    đường liệt kê bài đều coi một hàng đã thu hồi y như chưa bao giờ phát hành.

    Đề chỉ về `đã duyệt` khi **không lớp nào còn giữ** nó. Thu hồi 12B trong lúc 12A vẫn
    đang làm thì đề vẫn đang phát hành, và một đề về `đã duyệt` lúc đó là đúng cái hại mà
    ADR-02 ngăn.

    Args:
        assessment_id: Đề nào.
        class_id: Lớp nào.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        State sau lệnh này, kèm một dòng cho lớp vừa thu hồi.

    Raises:
        HTTPException: 404 khi đề không tồn tại, thuộc về người khác, hoặc chưa phát hành
            cho lớp đó; 409 khi đã qua giờ mở của lớp đó -- lúc ấy học sinh đã có thể vào
            làm, nên phát hành không lấy lại được nữa.

    Side effects:
        Đặt `recalled_at`, và đưa đề về `đã duyệt` khi lớp này là lớp cuối cùng.
    """
    asking = Asking.of(teacher)
    assessment = await _owned(session, asking, assessment_id)

    row = await session.get(Publication, (assessment_id, class_id))
    if row is None or row.recalled_at is not None:
        raise HTTPException(status_code=404, detail="Đề này chưa phát hành cho lớp đó.")

    now = _now()
    opens_at = aware(row.opens_at)
    if not may_withdraw(opens_at, now):
        raise HTTPException(
            status_code=409,
            detail=(f"Đã qua giờ mở của lớp này nên không thu hồi được nữa. {RECALL_RULE}"),
        )

    row.recalled_at = now
    still_held = len(
        [
            one
            for one in await _live_publications(session, assessment_id)
            if one.class_id != class_id
        ]
    )
    withdraw(assessment, still_held=still_held)
    await session.commit()

    named = (await _classes_of(session, asking)).get(class_id)
    return PublishResult(
        assessment_id=assessment_id,
        state=state_of(assessment),
        preview=False,
        classes=(
            ClassResult(
                class_id=class_id,
                class_name=named.name if named else "",
                published=False,
                reason="đã thu hồi",
                withdrawable_until=opens_at,
            ),
        ),
    )


class TeacherMe(BaseModel):
    """Giáo viên đang đăng nhập, cho dải trên cùng.

    Phía học sinh có `GET /api/me` từ lâu; phía giáo viên thì không, nên tên người dùng chỉ
    đi **vào** prompt của AGENT mà không bao giờ đi ra. Một dải trên cùng không có tên là một
    dải không trả lời được câu hỏi *"máy này đang là ai"* -- mà ADR-13 nói phòng máy là dùng
    chung.

    Không có `class_count`: dải trên không vẽ con số đó, và một field không ai vẽ là một field
    sẽ lệch trong im lặng.

    Attributes:
        teacher_id: Id, cho mọi thứ khác cần.
        full_name: Cách gọi người đó.
        teacher_code: Mã, thứ dải trên hiện cạnh tên.
    """

    teacher_id: str
    full_name: str
    teacher_code: str


class OptionRead(BaseModel):
    """Một phương án, đọc cho giáo viên.

    Khác bản của học sinh ở đúng hai field, và hai field đó là lý do endpoint này không dùng
    lại được route của học sinh: `is_correct` và `error_label` là thứ **chỉ giáo viên** được
    thấy trước khi nộp bài.

    Attributes:
        label: Chữ cái.
        text: Nội dung phương án.
        is_correct: Phương án đúng, thứ thẻ câu hỏi đánh dấu.
        error_label: Lỗi mà distractor này đại diện (ADR-18). None trên phương án đúng.
    """

    label: str
    text: str
    is_correct: bool
    error_label: str | None = None


class MethodRead(BaseModel):
    """Một cách giải.

    Attributes:
        title: Tên ngắn của cách làm.
        body: Các bước.
    """

    title: str
    body: str


class QuestionRead(BaseModel):
    """Một câu hỏi, đủ để vẽ một thẻ.

    `methods` đi kèm chứ không nằm sau một lần gọi nữa, vì thẻ in *"Lời giải · 2 cách"* ngay
    khi còn thu gọn -- con số đó là `len(methods)`. Tách ra thì một panel mười thẻ phải gọi
    mười request chỉ để đếm.

    Attributes:
        question_id: Id của câu.
        order: Số câu học sinh nhìn thấy.
        stem: Đề bài.
        learning_objective: Câu hỏi kiểm cái gì.
        options: Các phương án, đã sắp theo nhãn.
        methods: Các lời giải, đã sắp theo thứ tự.
    """

    question_id: str
    order: int
    stem: str
    learning_objective: str
    options: tuple[OptionRead, ...] = ()
    methods: tuple[MethodRead, ...] = ()


class AssessmentDetail(BaseModel):
    """Một đề, đủ để vẽ cả panel bên phải.

    `topic_scope` tới từ `DraftBrief` chứ không từ `Assessment`, và đó là chỗ duy nhất có nó --
    nó là phần *"Chương Hàm số"* trên dòng meta của thiết kế. Rỗng khi đề không sinh từ một
    brief, vì không phải đề nào cũng do chat soạn ra.

    Attributes:
        assessment_id: Đề nào.
        title: Tên đề.
        subject: Môn.
        grade: Khối.
        state: Vòng đời ADR-01. Giao diện suy *sửa được hay không* từ đây, không tự quyết.
        question_count: Số câu, đếm từ hàng chứ không khai sẵn.
        still_drafting: Còn bao nhiêu vị trí đang có job chạy.
        topic_scope: Phạm vi giáo viên đã giới hạn, bằng lời của họ.
        difficulty: Mức độ, bằng lời của họ. Rỗng khi không nói.
        conversation_id: Đoạn chat đã sinh ra đề này. Panel sống bên trong đoạn chat của
            nó, nên một link trỏ thẳng vào đề cần con số này để về đúng chỗ. Rỗng khi đề
            không sinh ra từ đoạn chat nào -- đề seed, hoặc đề tạo bằng tay.
        questions: Các câu, đã sắp theo thứ tự.
    """

    assessment_id: str
    title: str
    subject: str
    grade: str
    state: AssessmentState
    question_count: int
    still_drafting: int
    topic_scope: str = ""
    difficulty: str = ""
    conversation_id: str = ""
    questions: tuple[QuestionRead, ...] = ()


class PublishedTo(BaseModel):
    """Sáu tham số **đã đặt** cho một lớp, đọc lại được.

    Tồn tại vì không có nó thì một lần tải lại trang là mất hết: `publish-form` chỉ nói lớp nào
    *đang giữ* đề, không nói giữ với giờ nào. Giáo viên muốn biết "12A mở lúc mấy giờ" sẽ chỉ
    còn cách đi hỏi học sinh.

    Hai câu note gọi **đúng** hai hàm trong `publication_wording`, không in lại bằng chữ khác --
    nên luật *"ba nơi giống hệt nhau từng chữ"* của ADR-03 nay là bốn nơi mà vẫn một nguồn.

    Attributes:
        class_id: Lớp nào.
        class_name: Tên lớp.
        student_count: Bao nhiêu học sinh.
        opens_at: Giờ mở, UTC.
        closes_at: Hạn **vào**, UTC.
        phase1_minutes: Thời gian làm bài.
        phase2_minutes_per_question: Một tỉ lệ, không phải một khoảng (ADR-15).
        remediation_deadline: Mốc tuyệt đối kết thúc pha 2, UTC.
        withdrawable_until: Thu hồi được tới lúc nào. Bằng `opens_at`, nêu riêng vì đó là con số
            giáo viên cần biết chứ không phải suy ra.
        phase_one_note: Câu luật pha 1, đã điền số.
        phase_two_note: Câu luật pha 2, đã điền số, và nó ngược lại câu trên.
    """

    class_id: str
    class_name: str
    student_count: int
    opens_at: datetime
    closes_at: datetime
    phase1_minutes: int
    phase2_minutes_per_question: int
    remediation_deadline: datetime
    withdrawable_until: datetime
    phase_one_note: str
    phase_two_note: str


class Publications(BaseModel):
    """Đề này đang phát hành cho những lớp nào, với giờ nào.

    Attributes:
        assessment_id: Đề nào.
        classes: Các lớp **chưa** thu hồi. Một lần thu hồi đọc lên y như chưa bao giờ phát hành.
        rules: Ba câu luật, cùng string mà biểu mẫu và biên bản trả về.
    """

    assessment_id: str
    classes: tuple[PublishedTo, ...] = ()
    rules: TimingRules = TimingRules()


@router.get("/teacher/me", response_model=TeacherMe)
async def who_am_i(teacher: Teacher = Depends(current_teacher)) -> TeacherMe:
    """Giáo viên đang gọi là ai.

    Args:
        teacher: Được resolve từ header actor (ADR-13).

    Returns:
        Ba giá trị mà dải trên cùng cần.
    """
    return TeacherMe(
        teacher_id=teacher.id, full_name=teacher.full_name, teacher_code=teacher.teacher_code
    )


@router.get("/teacher/assessments/{assessment_id}", response_model=AssessmentDetail)
async def assessment_detail(
    assessment_id: str,
    request: Request,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AssessmentDetail:
    """Nội dung một đề: câu hỏi, phương án, lời giải.

    Nạp bằng `selectinload` chứ không để quan hệ tự lazy-load: cả file này làm việc với giá trị
    vì một lần lazy-load trong ngữ cảnh async là `MissingGreenlet`, nổ ở rất xa nguyên nhân.

    **Đọc là một lần quan sát, và quan sát là lúc thu hoạch.** BE không có worker chạy nền
    (ADR-25), nên câu hỏi do AGENT viết chỉ vào đề khi có ai đó hỏi tới nó. Trước ADR-25 chỗ
    làm việc ấy là tool `draft_progress`; tool đó nay đã bỏ hẳn -- SSE kể tiến độ, nên một
    tool chỉ để ngó là một tool không ai gọi -- và món nợ thu hoạch rơi đúng vào đây: `harvest`
    chạy ở route này và ở chính `start_drafting`. Không thu ở đây thì panel của giáo viên hiện
    *0 câu* cho tới khi họ bấm Duyệt, dù mười câu đã nằm sẵn trong Redis. Đo thấy trên trình
    duyệt thật.

    Một GET có ghi, và điều đó được cân nhắc: thứ nó ghi là kết quả **đã có**, việc thu lặp
    lại không sinh thêm gì, và lựa chọn còn lại là để giáo viên nhìn một cái đề trống trong
    khi hệ thống đã làm xong việc. Đường đẩy xuống (SSE) chỉ cắt độ trễ, không thay chỗ này.

    Args:
        assessment_id: Đề nào.
        request: Mang theo pool của queue.
        settings: Cho timeout khi đọc kết quả job.

    Returns:
        Đề, kèm mọi câu hỏi đã sắp thứ tự.

    Raises:
        HTTPException: 404 khi đề không tồn tại **hoặc** thuộc về người khác (ADR-22).
    """
    asking = Asking.of(teacher)
    assessment = await _owned(session, asking, assessment_id, lock=False)

    landed = await harvest(session, request.app.state.queue_pool, settings, assessment_id)
    if landed:
        logger.info("harvested %d question(s) of %s on a read", landed, assessment_id)

    rows = await session.scalars(
        select(Question)
        .where(Question.assessment_id == assessment_id)
        .order_by(Question.order_index)
        .options(selectinload(Question.options), selectinload(Question.methods))
    )
    questions = tuple(
        QuestionRead(
            question_id=row.id,
            order=row.order_index,
            stem=row.stem,
            learning_objective=row.learning_objective,
            options=tuple(
                OptionRead(
                    label=one.label,
                    text=one.text,
                    is_correct=one.is_correct,
                    error_label=one.error_label,
                )
                for one in row.options
            ),
            methods=tuple(MethodRead(title=one.title, body=one.body) for one in row.methods),
        )
        for row in rows
    )

    brief = await session.get(DraftBrief, assessment_id)
    return AssessmentDetail(
        assessment_id=assessment_id,
        title=assessment.title,
        subject=assessment.subject,
        grade=assessment.grade,
        state=state_of(assessment),
        question_count=len(questions),
        still_drafting=await pending_count(session, assessment_id),
        topic_scope=brief.topic_scope if brief is not None else "",
        difficulty=brief.difficulty if brief is not None else "",
        conversation_id=await conversation_of(session, asking, assessment_id) or "",
        questions=questions,
    )


class OptionEdit(BaseModel):
    """Một phương án như giáo viên vừa sửa.

    Attributes:
        label: Chữ cái. Cả bộ phương án bị thay, nên nhãn đi theo payload chứ không
            đối chiếu với nhãn cũ; hai nhãn trùng nhau thì bị từ chối, vì cột có
            `UniqueConstraint(question_id, label)`.
        text: Nội dung.
        is_correct: Phương án đúng. Đúng một phương án mỗi câu (ADR-18).
        error_label: Lỗi mà phương án nhiễu này đại diện (ADR-18). Gửi kèm cho
            phương án **đúng** thì bị bỏ, không bị từ chối — `models.py` để cột ấy
            null ở đúng dòng của đáp án đúng.
    """

    label: str
    text: str
    is_correct: bool
    error_label: str | None = None


class MethodEdit(BaseModel):
    """Một cách giải như giáo viên vừa sửa."""

    title: str
    body: str


class QuestionEdit(BaseModel):
    """Toàn bộ chữ của một câu hỏi, gửi lên cùng một lúc.

    Gửi **cả câu** chứ không gửi từng mảnh, và đó là chủ ý: ADR-18 là một luật về *quan hệ
    giữa các mảnh* — đúng một phương án đúng, mọi phương án nhiễu có nhãn lỗi, hơn một lời
    giải. Nhận từng mảnh rời thì mỗi lần sửa là một lần câu hỏi đi qua một trạng thái không
    ai kiểm được, và luật ấy chỉ còn đúng ở những khoảnh khắc may mắn.

    Attributes:
        stem: Đề bài.
        learning_objective: Câu hỏi kiểm cái gì.
        options: Các phương án, đủ bộ.
        methods: Các lời giải, đủ bộ.
    """

    stem: str
    learning_objective: str
    options: tuple[OptionEdit, ...]
    methods: tuple[MethodEdit, ...]


@router.patch(
    "/teacher/assessments/{assessment_id}/questions/{question_id}",
    response_model=QuestionRead,
)
async def edit_question(
    assessment_id: str,
    question_id: str,
    wanted: QuestionEdit,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> QuestionRead:
    """Sửa chữ của một câu hỏi trong một đề còn mở.

    Nút *Sửa* đã có trên panel từ lâu và **không có `onClick`** — một nút chết. Đây là đường
    nó nối vào.

    **Cổng ADR-01**: chỉ sửa được khi đề còn `editable`. Đề đã duyệt thì nội dung khoá, và
    chính cái khoá đó là lý do việc duyệt có nghĩa; đường mở lại là *Hoàn tác* ở chân panel.

    **Và một câu sửa tay phải qua đúng cái lưới mà một câu model viết phải qua.** Cùng một
    `validate_question` -- nay chỉ còn ADR-18, vì lưới cú pháp toán đã bị gỡ: chữ sai cú
    pháp đi thẳng tới giáo viên để họ sửa tay, chứ không bị chặn. Không phải một bản kiểm thứ hai
    viết riêng cho đường này — hai bản kiểm của cùng một luật là hai thứ chờ lệch nhau, và
    bản lỏng hơn sẽ là bản người ta đi qua.

    Args:
        assessment_id: Đề nào.
        question_id: Câu nào.
        wanted: Toàn bộ chữ của câu, sau khi sửa.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        Câu hỏi sau khi sửa, đúng hình dạng panel đang vẽ.

    Raises:
        HTTPException: 404 khi đề hoặc câu không tồn tại, hoặc thuộc về người khác (ADR-22);
            409 khi đề đã khoá nội dung, hoặc câu đã có người trả lời; 422 khi câu sửa xong
            vi phạm ADR-18. Cú pháp toán **không** nằm trong danh sách này: lưới ấy đã bị gỡ.

    Side effects:
        Thay chữ của câu, thay cả bộ phương án và bộ lời giải, rồi commit.
    """
    asking = Asking.of(teacher)
    assessment = await _owned(session, asking, assessment_id)

    if not editable(assessment):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Đề đang ở trạng thái {readable(state_of(assessment))} nên không sửa được. "
                "Hoàn tác việc duyệt trước đã."
            ),
        )

    question = await session.scalar(
        select(Question).where(Question.id == question_id, Question.assessment_id == assessment_id)
    )
    if question is None:
        raise HTTPException(status_code=404, detail=_NO_SUCH)

    # **Không sửa một câu đã có người làm.** `AnswerOption.id` là `new_id()`, nên thay cả
    # bộ phương án sinh ra id mới kể cả khi giáo viên chỉ đổi một dấu phẩy — và mọi
    # `Answer.option_id` của câu ấy thành mồ côi. Trên SQLite nó im lặng; trên Postgres,
    # `DELETE FROM options` nổ `ForeignKeyViolation` và giáo viên nhận một 500 không có
    # chữ tiếng Việt nào.
    #
    # Hôm nay ca ấy chưa tới được, vì ADR-02 chỉ cho thu hồi trước giờ mở nên một đề quay
    # về `HAS_QUESTIONS` thì chưa ai làm. Nhưng đó là một luật đứng ở **một file khác**
    # (`may_withdraw`), và một ngày nào đó cạnh `published → approved` được nới thì hàng
    # mồ côi tới mà không ai báo. Phép kiểm phải ở ngay chỗ có thể vỡ.
    answered = await session.scalar(
        select(func.count())
        .select_from(Answer)
        .join(AnswerOption, Answer.option_id == AnswerOption.id)
        .where(AnswerOption.question_id == question_id)
    )
    if answered:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Đã có {answered} lượt trả lời cho câu này nên không sửa được. "
                "Sửa một câu đã có người làm sẽ làm hỏng bài của họ."
            ),
        )

    # Dựng lại hình dạng mà `validate_question` nhận, rồi gọi **chính nó**.
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

    question.stem = wanted.stem
    question.learning_objective = wanted.learning_objective

    # Thay cả bộ chứ không vá từng dòng: `label` là khoá, và một lần sửa đổi nhãn sẽ để lại
    # những hàng mồ côi mà không ai đi tìm.
    for row in await session.scalars(
        select(AnswerOption).where(AnswerOption.question_id == question_id)
    ):
        await session.delete(row)
    for row in await session.scalars(select(Method).where(Method.question_id == question_id)):
        await session.delete(row)
    await session.flush()

    for one in wanted.options:
        session.add(
            AnswerOption(
                question_id=question_id,
                label=one.label,
                text=one.text,
                is_correct=one.is_correct,
                error_label=None if one.is_correct else (one.error_label or None),
            )
        )
    for index, one in enumerate(wanted.methods):
        session.add(
            Method(question_id=question_id, order_index=index, title=one.title, body=one.body)
        )
    await session.commit()

    fresh = await session.scalar(
        select(Question)
        .where(Question.id == question_id)
        .options(selectinload(Question.options), selectinload(Question.methods))
    )
    return QuestionRead(
        question_id=fresh.id,
        order=fresh.order_index,
        stem=fresh.stem,
        learning_objective=fresh.learning_objective,
        options=tuple(
            OptionRead(
                label=one.label,
                text=one.text,
                is_correct=one.is_correct,
                error_label=one.error_label,
            )
            for one in sorted(fresh.options, key=lambda one: one.label)
        ),
        methods=tuple(
            MethodRead(title=one.title, body=one.body)
            for one in sorted(fresh.methods, key=lambda one: one.order_index)
        ),
    )


@router.get("/teacher/assessments/{assessment_id}/publications", response_model=Publications)
async def publications_of(
    assessment_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> Publications:
    """Đề này đang phát hành cho lớp nào, với giờ nào.

    Args:
        assessment_id: Đề nào.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        Một dòng cho mỗi lớp **chưa** thu hồi, sắp theo tên lớp.

    Raises:
        HTTPException: 404 khi đề không tồn tại hoặc thuộc về người khác (ADR-22).
    """
    asking = Asking.of(teacher)
    await _owned(session, asking, assessment_id, lock=False)

    named = await _classes_of(session, asking)
    live = await _live_publications(session, assessment_id)
    rows = []
    for row in sorted(
        live, key=lambda one: named[one.class_id].name if one.class_id in named else ""
    ):
        at = named.get(row.class_id)
        closes_at, deadline = aware(row.closes_at), aware(row.remediation_deadline)
        rows.append(
            PublishedTo(
                class_id=row.class_id,
                class_name=at.name if at else "",
                student_count=at.student_count if at else 0,
                opens_at=aware(row.opens_at),
                closes_at=closes_at,
                phase1_minutes=row.phase1_minutes,
                phase2_minutes_per_question=row.phase2_minutes_per_question,
                remediation_deadline=deadline,
                withdrawable_until=aware(row.opens_at),
                phase_one_note=phase_one_note(closes_at, row.phase1_minutes),
                phase_two_note=phase_two_note(deadline, row.phase2_minutes_per_question),
            )
        )
    return Publications(assessment_id=assessment_id, classes=tuple(rows))
