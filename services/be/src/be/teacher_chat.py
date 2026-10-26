"""Chat của giáo viên, nơi BE chạy vòng lặp và AGENT chỉ tư vấn.

Một lượt có **hai pha** (ADR-25). **Pha 1 lên plan**: BE hỏi AGENT bước tiếp theo nên làm
gì, chạy các tool **đọc**, rồi hỏi lại kèm kết quả -- cho tới khi AGENT trả lời bằng lời,
hỏi lại giáo viên, hoặc nêu một **plan**: danh sách việc sẽ làm, có thứ tự. **Pha 2 thực
hiện plan**: BE chạy từng bước **ghi** theo đúng thứ tự ấy và dừng ở bước đầu tiên hỏng.
Xong thì model được hỏi một lần nữa, lần này để **kể lại** những gì đã xảy ra.

AGENT không bao giờ tự chạy gì: nó không giữ credential nào của database, và việc phân
quyền thuộc về process đang giữ session và biết ai đang gọi.

Ba tính chất sinh ra từ cách bố trí đó, chứ không phải từ một prompt:

- **Một đề xuất không phải một hành động.** ADR-05 giữ những việc không đảo lại được ở
  ngoài luồng chat. Ở đây chuyện đó nằm trong cấu trúc: BE quyết định đề xuất nào được
  chạy, và những tool nó đưa ra chỉ làm được những việc đảo lại được. Duyệt và phát hành
  thì không có tool nào cả, và `tools/check_contract.py` giữ nguyên tình trạng ấy.
- **Vòng lặp có điểm dừng.** Hai mức chặn, không phải một: `max_tool_steps` đếm số bước, và
  `turn_budget_seconds` đếm thời gian -- mức chặn thứ hai mới là mức giáo viên thực sự cảm thấy,
  vì tám bước nhanh thì không ai sốt ruột còn ba bước chậm thì có. Chạm phải mức nào cũng được
  nói ra thành lời. Một request không bao giờ về mới là sự cố tệ hơn -- không có gì
  trong log gọi tên được nguyên nhân của nó.
- **Pha 1 không có tool nào ghi.** Catalog chia theo pha, nên một câu hỏi lại không thể
  bỏ lại việc đã làm dở -- đó là cấu trúc, không phải một lời dặn trong prompt, và lời dặn
  thì model quên được.
- **Một lượt tiêu nhiều lời gọi model, và chúng không giống nhau.** Mỗi bước của pha 1 là
  một lời gọi; pha 2 **không** gọi model lần nào; rồi lời kể cuối lượt là một job riêng với
  đầu vào khác hẳn. Invariant "một job của AGENT timeout trước khi BE thôi đợi" áp cho từng
  job trong số đó.

Hội thoại được lưu bền, và chính điều đó làm cho `ask_clarify` trả lời được. Một tin
nhắn mang theo cả luồng hội thoại, nên khi trợ lý hỏi "lớp nào?" và giáo viên đáp "12A",
model thấy lại được câu hỏi của chính nó. Trong khoảng thời gian chưa có gì được lưu,
câu trả lời đó đến mà không còn dấu vết nào của câu đã hỏi, và cái cổng đầu vào của
ADR-05 tồn tại mà thiếu hẳn nửa sau.

Mỗi bước được commit riêng. Một worker chết giữa lượt vì thế chỉ mất đúng bước nó đang
làm chứ không mất cả hội thoại, và connection lấy từ pool được thả ra trước mỗi lần đợi
AGENT. Cái giá phải trả là nửa lượt cũng là một trạng thái mà bảng chứa được: một lượt
lỗi để lại tin nhắn của giáo viên đã lưu mà không có câu trả lời nào bên dưới, và một
lần thử lại thì lưu tin nhắn đó thêm một lần nữa.

Một luật mà cả file tuân theo, học được qua ba lần: **làm việc với giá trị, không bao
giờ với row.** `rollback` làm hết hạn mọi object ORM trong session, và vòng lặp này
rollback giữa các bước gọi tool, nên đọc một attribute của một row nạp từ trước là làm
IO database từ một chỗ mà cầu nối async của SQLAlchemy không với tới được --
`MissingGreenlet`, nổ ở rất xa nguyên nhân của nó.
"""

import asyncio
import logging
import re
import time
import unicodedata
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from be.agent_gateway import AgentError, run_task
from be.config import Settings, get_settings
from be.content_reader import ContentUnavailable, get_reader
from be.db import get_session, session_scope
from be.drafting import _MOST_QUESTIONS, harvest, open_bells
from be.identity import Asking, current_teacher
from be.notices import (
    AGENT_UNAVAILABLE,
    ALREADY_RUNNING,
    BOOK_NOT_READY,
    BOOK_SCOPE_MISSING,
    CEILING_REACHED,
    OUTLINE_REFUSED,
    PLAN_REFUSED,
    REPORT_MISSING,
    TURN_BROKE,
)
from be.outline import MOST_QUESTIONS_ASKED, stored, validate
from be.plan_outcomes import (
    COULD_NOT_CARRY_OVER,
    DID_IT_HAPPEN,
    count_questions,
    step_detail,
    went_wrong,
)
from be.teacher_documents import believed_state
from be.teacher_tools import (
    FORMULA_SECONDS,
    LOOKS_LIKE_REFERENCE,
    PHASE_PLAN,
    PHASE_WORK,
    REFERENCE,
    UnknownTool,
    Unresolvable,
    bind_book,
    catalog_for,
    execute,
    owned_document,
    ready_document,
    resolve_args,
)
from contracts import (
    NAME_CONVERSATION_TASK,
    PROPOSE_NEXT_STEP_TASK,
    AttachedDocument,
    ConversationNameCompleted,
    ConversationNameRequested,
    DocumentState,
    NextStepCompleted,
    NextStepRequested,
    OutlineItem,
    PlanStep,
    ToolSpec,
    TurnRecord,
)
from schema.models import (
    Assessment,
    DraftBrief,
    DraftItem,
    Question,
    Teacher,
    TeacherConversation,
    TeacherTurn,
    aware,
    new_id,
)

logger = logging.getLogger(__name__)

# Trần số bước của một plan. Pha 1 có `max_tool_steps`; pha 2 phải có trần của riêng nó,
# vì mỗi bước ở đây là một tool **ghi**: một plan năm mươi bước `create_draft` lọt qua sẽ để
# lại năm mươi đề rỗng mang tên giáo viên, và không có đường nào xoá chúng.
_MOST_STEPS = 8
# Số lần một lượt chịu trả dàn ý về cho model sửa, lý do gì cũng tính (thử tay 17/10/2026, pha 6
# của plan `backlog-tier-1`): một dàn ý đọc sách mang theo cả phần sách đã đọc, nên mỗi lần gọi lại
# là vài chục nghìn token, mà giáo viên vẫn chưa thấy gì.
_MOST_OUTLINE_REFUSALS = 3
# Số lần chờ đọc công thức trọn `formula_wait_seconds` mà một lượt được cộng giờ (`formulas-on-
# demand`): bằng số phần đọc tối đa của một lần xin, nên mười phần đọc trang mới đều được chờ, còn
# một model đọc lại mãi không kéo lượt qua `turn_lock_stale_seconds`.
MOST_FORMULA_WAITS = 10

router = APIRouter(prefix="/api", tags=["teacher-chat"])

# Câu hệ thống (ADR-30, ngoại lệ 1) sống ở `be/notices.py`: giáo viên nghe chúng khi model không
# có mặt để nói, và chúng không bao giờ mang giọng Kriky.


class Said(BaseModel):
    """Thứ giáo viên vừa gõ, và nói vào đâu.

    Hai field sau loại trừ nhau, và việc đó được **kiểm** chứ không phải được mong: gửi
    cả hai nghĩa là client đang nói hai điều trái nhau — *"nói tiếp đoạn này"* và *"mở
    đoạn mới"* — và chọn hộ một trong hai là chọn hộ một nửa số lần sai.

    Attributes:
        text: Câu vừa gõ.
        conversation_id: Nói vào đoạn chat nào. Thiếu thì vào đoạn đang chạy, y như
            trước khi giáo viên có nhiều đoạn.
        start_new: Mở một đoạn mới. Đây là đường **duy nhất** mở đoạn thứ hai.
        document_id: Chip tài liệu đang đính trong ô nhập (`draft-from-document`). BE chỉ chuyển nó
            cho AGENT khi tài liệu thuộc giáo viên và đã *sẵn sàng*.
    """

    text: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    start_new: bool = False
    document_id: str | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def _one_or_the_other(self) -> "Said":
        """Chặn một request tự mâu thuẫn ngay ở biên.

        Returns:
            Chính nó khi hợp lệ.

        Raises:
            ValueError: Khi vừa chỉ định đoạn chat vừa xin đoạn mới.
        """
        if self.start_new and self.conversation_id is not None:
            raise ValueError("chọn một đoạn chat hoặc mở đoạn mới, không phải cả hai")
        return self


class Turn(BaseModel):
    """Một bước của một lượt, theo đúng cách client nên vẽ nó ra.

    Soi lại `TurnRecord` chứ không dùng lại chính nó: type đó đi qua queue sang AGENT, và
    thêm một field ở đây vì nhu cầu của giao diện là nhét field đó vào một payload mà
    AGENT không dùng được. Sáu field cuối chính là trường hợp đó -- chủ thể của bước, các
    phương án bày ra cùng nó, và cái giá nó tốn đều là để cho màn hình và cho người đi
    debug, và chẳng có nghĩa gì với model.

    `tool_args` vắng mặt có chủ đích. Các tham số vẫn được lưu, vì một vết truy ngược
    không có chúng thì không trả lời được câu hỏi đã hỏi cái gì; chúng không được gửi
    đi, vì không có gì trên màn hình được dựng từ chúng.
    """

    kind: str
    text: str = ""
    tool_name: str = ""
    tool_result: dict = Field(default_factory=dict)
    entity_kind: str = ""
    entity_id: str = ""
    choices: list[str] = Field(default_factory=list)
    more_choices: int = 0
    model_tokens: int = 0
    duration_ms: int = 0
    # Đề mà bước này nói tới đã bị xoá (chỉ đề trống mới xoá được, ADR-33). Thẻ *Đã tạo đề* cũ đọc
    # cờ này để nói *"Đề trống này đã xoá"* thay vì mở một đề không còn (plan `wave-3-draft-panel`).
    entity_gone: bool = False


class Answered(BaseModel):
    """Kết quả của một lượt.

    Attributes:
        kind: Lượt đó kết thúc kiểu gì: `say` hay `ask_clarify`. Một lượt kết thúc bằng thông báo
            hệ thống cũng là `say`; `turns` cho biết đó là lượt `notice`.
        text: Phần chữ để hiện ra. Do model viết, trừ thông báo hệ thống (`be/notices.py`,
            ADR-30).
        choices: Các phương án cho `ask_clarify`, do `_choices` dựng (ADR-23, hậu ký
            `unbiased-model-text` T3). Câu hỏi về một row -- lớp, tài liệu, mục -- thì là mọi nhãn
            BE viết từ chính các row ấy; chữ model viết chỉ đổi thứ tự khi khớp đúng một tên, vì một
            tên lớp bịa ra đến trước mặt giáo viên với cả uy tín của hệ thống đứng sau. Câu hỏi về
            một tham số thì là chữ model đề xuất. Không có "Khác" -- FE tự vẽ lối gõ ấy; rỗng với
            `say`.
        more_choices: Có bao nhiêu candidate nữa đã bị cắt khỏi `choices`, để giao diện
            nói được rằng danh sách này chưa đủ. Một giáo viên có ba mươi lớp mà chỉ được
            cho xem sáu lớp và không được nói gì thêm thì đọc ra là dữ liệu đã mất.
        turns: Mọi bước, theo thứ tự, để giao diện hiện được những gì đã làm chứ không
            chỉ những gì đã nói.
    """

    kind: str
    text: str
    conversation_id: str = ""
    choices: list[str] = Field(default_factory=list)
    more_choices: int = 0
    turns: list[Turn] = Field(default_factory=list)


async def _ask_agent(
    request: Request,
    settings: Settings,
    teacher_name: str,
    catalog: tuple[ToolSpec, ...],
    plannable: tuple[ToolSpec, ...],
    history: list[TurnRecord],
    attached: AttachedDocument | None = None,
) -> NextStepCompleted:
    """Hỏi AGENT một đề xuất.

    Args:
        request: Mang theo pool của queue trên `app.state`.
        settings: Settings của process.
        teacher_name: Trợ lý nên gọi người này thế nào. Một string trần, không phải cái
            row: hàm này được gọi giữa các bước gọi tool, và mỗi bước rollback session để
            thả connection của nó ra, việc đó làm hết hạn mọi object ORM đang gắn vào
            session. Đọc một attribute của một row đã hết hạn ở đây là làm IO database từ
            một chỗ mà cầu nối async của SQLAlchemy không với tới được --
            `MissingGreenlet`, ở rất xa nguyên nhân của nó. Không có id nào đi theo chiều
            nào cả, vì AGENT không resolve thứ gì.
        catalog: Những tool model được gọi ngay, lấy một lần trước vòng lặp.
        plannable: Những tool model được nêu trong một plan nhưng không gọi được bây giờ.
            Pha 1 phải biết chúng tồn tại và nhận tham số nào, nếu không nó đoán -- và một
            plan đoán sai tên tham số bị `vet_plan` từ chối trọn gói (ADR-25).
        history: Mọi thứ đã có tới lúc này, cũ nhất trước.
        attached: Tài liệu đính kèm tin nhắn này, đã kiểm sở hữu và *sẵn sàng*.

    Returns:
        Đề xuất đó.

    Raises:
        AgentError: Khi queue từ chối job hoặc worker không xong kịp giờ.
    """
    asked = NextStepRequested(
        request_id=str(uuid.uuid4()),
        teacher_name=teacher_name,
        history=tuple(history),
        catalog=catalog,
        plannable=plannable,
        attached_document=attached,
    )
    answer = await run_task(
        getattr(request.app.state, "queue_pool", None),
        settings,
        PROPOSE_NEXT_STEP_TASK,
        asked.model_dump(mode="json"),
    )
    return NextStepCompleted.model_validate(answer)


# Tool đọc tài liệu (`draft-from-document`). Một lần gọi bất kỳ cái nào trong đoạn chat là đoạn chat
# **đang nói về một tài liệu**, kể cả ở lượt sau khi chip đã rời ô nhập.
_DOCUMENT_READS = frozenset({"list_documents", "list_chapters", "get_chapter", "read_section"})
# Tool đọc **một cuốn** cụ thể: mục lục hay chữ của nó (`read_section` từ `draft-outline`).
_BOOK_READS = frozenset({"list_chapters", "get_chapter", "read_section"})


def read_allowance(tool_name: str, result: dict, granted: int) -> int:
    """Lượt được thêm bao nhiêu bước sau kết quả này (`draft-outline`). Hàm thuần.

    Một `read_section` trả `parts` -- số phần phạm vi được gộp thành, không vượt số câu xin. Lượt
    cần đủ bước để đọc hết chừng ấy phần **cộng** các bước nó vốn có (mục lục, nộp dàn ý), nên mỗi
    phần là một bước thêm, đếm một lần cho cả lượt: đọc lại phần 1 không mua thêm bước nào. Trần là
    `MOST_QUESTIONS_ASKED` phần -- số phần không bao giờ vượt số câu xin.

    Args:
        tool_name: Tool vừa chạy.
        result: Kết quả của nó.
        granted: Số bước đã cộng thêm trong lượt này.

    Returns:
        Số bước cộng thêm bây giờ, 0 khi không có gì để cộng.
    """
    if tool_name != "read_section" or result.get("found") is not True:
        return 0
    try:
        wanted = min(int(result.get("parts") or 0), MOST_QUESTIONS_ASKED)
    except (TypeError, ValueError):
        return 0
    return max(0, wanted - granted)


# ------------------------------------------------------------------ dàn ý (`draft-outline`)

# Ba việc một dàn ý có thể dành cho, Kriky nói trong `tool_args["for"]` của lượt dàn ý: một đề
# mới, thêm câu cho đề đang có, hay thay một câu của nó (ADR-29). BE cần biết để đánh số câu --
# *"Câu 11–13"* khi soạn thêm, *"Câu 3"* khi thay câu 3 -- và để cổng duyệt so đúng việc.
OUTLINE_FOR = ("new", "more", "replace")


def _outline_book(history: list[TurnRecord], attached: AttachedDocument | None) -> str:
    """Tài liệu mà dàn ý lượt này dựa vào: chip đang gắn, không thì cuốn vừa đọc gần nhất.

    Cùng luật với `bind_book`: lượt đã đọc một cuốn **khác** chip thì chip không phải sách của dàn ý
    (`_read_other_books`) -- số nút nhỏ, khớp nhầm trên cây của cuốn kia là in nhãn bài sai.
    """
    if (
        attached is not None
        and attached.state == DocumentState.READY.value
        and not _read_other_books(history, attached)
    ):
        return attached.document_id
    for turn in reversed(history):
        if turn.kind == "tool_call" and turn.tool_name in _BOOK_READS:
            return str(turn.tool_args.get("document_id") or "").strip()
    return ""


# Kết quả tool **nói đã mở hay soạn đề nào** -- chỉ những dòng này cho biết *đề của đoạn chat*.
# Duyệt hay phát hành cũng ghi đề vào đoạn chat (`conversation_of`), nhưng không làm đề ấy thành đề
# đang soạn (review đợt 3, `draft-outline`).
_DRAFT_RESULTS = frozenset({"create_draft", "start_drafting", "replace_question"})


async def _latest_draft(session: AsyncSession, thread: str) -> tuple[str, int] | None:
    """Đề mới nhất đoạn chat này đã mở hay soạn, và ô cao nhất của nó; `None` khi chưa có đề nào.

    Ô cao nhất, không số câu: `fire` nối câu mới sau `max(ordinal)`, và một ô hỏng để lại lỗ --
    đánh số dàn ý theo số câu thì *"Câu 10"* trên màn hình thành câu 11 trong đề (review đợt 3).
    """
    found = await session.scalar(
        select(TeacherTurn.entity_id)
        .where(
            TeacherTurn.conversation_id == thread,
            TeacherTurn.entity_kind == "assessment",
            TeacherTurn.tool_name.in_(_DRAFT_RESULTS),
        )
        .order_by(TeacherTurn.sequence.desc())
        .limit(1)
    )
    if not found:
        return None
    highest = await session.scalar(
        select(func.max(DraftItem.ordinal)).where(DraftItem.assessment_id == found)
    )
    return found, int(highest or 0)


async def _outline_shape(
    session: AsyncSession, thread: str, step: NextStepCompleted
) -> tuple[str, int, int, str] | str:
    """Dàn ý này dành cho việc gì, câu đầu tiên của nó mang số mấy, được tối đa bao nhiêu câu, và
    cho đề nào.

    Args:
        session: Session của database.
        thread: Đoạn chat.
        step: Lượt dàn ý model nêu.

    Returns:
        `(for, first, most, assessment_id)` -- `assessment_id` rỗng với `for=new` --, hoặc lời từ
        chối cho model đọc.
    """
    purpose = str(step.tool_args.get("for") or "new").strip()
    if purpose not in OUTLINE_FOR:
        return f"for phải là một trong {', '.join(OUTLINE_FOR)}"
    if purpose == "new":
        return purpose, 1, MOST_QUESTIONS_ASKED, ""
    draft = await _latest_draft(session, thread)
    if draft is None or draft[1] == 0:
        return "đoạn chat này chưa có đề nào có câu để soạn thêm hay thay; dùng for=new"
    paper, highest = draft
    if purpose == "more":
        room = min(MOST_QUESTIONS_ASKED, _MOST_QUESTIONS - highest)
        if room <= 0:
            return f"đề đã đủ {_MOST_QUESTIONS} câu, không soạn thêm được"
        return purpose, highest + 1, room, paper
    try:
        question = int(str(step.tool_args.get("question") or "").strip())
    except ValueError:
        return "thay câu thì question là số của câu bị thay"
    there = await session.scalar(
        select(Question.id).where(Question.assessment_id == paper, Question.order_index == question)
    )
    if there is None:
        return f"đề không có câu {question}"
    return purpose, question, 1, paper


# Tool soạn câu: chỉ chạy trên một dàn ý giáo viên đã xem (ADR-29).
_DRAFTING_TOOLS = frozenset({"start_drafting", "replace_question"})


async def _shown_outline(session: AsyncSession, thread: str, began: int) -> dict | None:
    """Dàn ý đã hiện ở lượt **ngay trước** lượt này, và chưa thành câu lần nào.

    Đọc từ database, không từ cửa sổ `_HISTORY_STEPS`. *"Ngay trước"* là luật duy nhất BE chứng
    minh được: câu giáo viên vừa gõ là câu đáp lại dàn ý ấy. Thử tay 15/10/2026: một dàn ý soạn
    thêm còn bỏ dở từ mấy lượt trước được dùng cho lời xin *"soạn thêm 2 câu về …"* mới gõ -- giáo
    viên chưa thấy dàn ý nào cho lời xin ấy. Kriky đã đáp một câu nào sau dàn ý thì dàn ý ấy đã
    qua, Kriky nêu lại. Câu giáo viên gõ mà chưa được đáp (lượt hỏng, hàng mồ côi) thì không tính:
    lượt hỏng mời giáo viên gõ lại, và gõ lại *"oke"* không được thành ngõ cụt (review đợt 6). Thông
    báo hệ thống cũng không tính: nó dặn gửi lại, nó không đáp dàn ý (review pha 5,
    `kriky-writes-every-word`).
    *"Chưa thành câu"* đọc `outline_version` mà bước soạn ghi vào kết quả của nó -- một dàn ý soạn
    hai lần là hai đề giáo viên chỉ duyệt một.

    Args:
        session: Session của database.
        thread: Đoạn chat.
        began: Số thứ tự của dòng đầu tiên của lượt này.

    Returns:
        `tool_result` của lượt dàn ý ấy, hoặc `None`.
    """
    row = await session.scalar(
        select(TeacherTurn)
        .where(
            TeacherTurn.conversation_id == thread,
            TeacherTurn.kind == "outline",
            TeacherTurn.sequence < began,
        )
        .order_by(TeacherTurn.sequence.desc())
        .limit(1)
    )
    if row is None:
        return None
    answered = await session.scalar(
        select(func.count())
        .select_from(TeacherTurn)
        .where(
            TeacherTurn.conversation_id == thread,
            TeacherTurn.sequence > row.sequence,
            TeacherTurn.sequence < began,
            TeacherTurn.kind.not_in(("teacher", "notice")),
        )
    )
    if answered:
        return None
    shown = dict(row.tool_result or {})
    used = await session.scalars(
        select(TeacherTurn.tool_result).where(
            TeacherTurn.conversation_id == thread,
            TeacherTurn.kind == "tool_result",
            TeacherTurn.tool_name.in_(_DRAFTING_TOOLS),
            TeacherTurn.sequence > row.sequence,
        )
    )
    if any((one or {}).get("outline_version") == shown.get("version") for one in used):
        return None
    return shown


async def guard_drafting(
    session: AsyncSession, thread: str, began: int, steps: tuple[PlanStep, ...]
) -> tuple[tuple[PlanStep, ...], dict | None] | str:
    """Cổng duyệt của ADR-29 cho một plan, và các tham số BE điền hộ từ dàn ý.

    Plan không soạn câu nào (không `start_drafting`, không `replace_question`) đi qua nguyên vẹn.
    Plan có soạn thì phải có một dàn ý đã xem (`_shown_outline`) **đúng việc**: mở đề mới cần dàn
    ý `for=new`, soạn thêm cho đề đang có cần `for=more`, thay câu cần `for=replace`. Rồi BE điền
    thứ nó biết mà không phải đoán (Decision *BE điền hộ*): số câu là tổng của dàn ý, đề là đề
    mới nhất của đoạn chat, tài liệu và các nút của `create_draft` lấy từ dàn ý.

    Args:
        session: Session của database.
        thread: Đoạn chat.
        began: Dòng đầu tiên của lượt này.
        steps: Các bước model nêu, đã qua `vet_plan`.

    Returns:
        `(các bước đã điền, dàn ý)`, hoặc lời từ chối cho model đọc.
    """
    drafting = [one for one in steps if one.tool_name in _DRAFTING_TOOLS]
    if not drafting:
        return steps, None
    # Đề để trống thì BE điền đề mới nhất, nên trống không phải một đề khác (review đợt 6).
    targets = {str(one.args.get("assessment_id") or "").strip() for one in drafting} - {""}
    only_start = all(one.tool_name == "start_drafting" for one in drafting)
    opens = any(one.tool_name == "create_draft" for one in steps)
    if len(drafting) > 1 and only_start and len(targets) <= 1 and not opens:
        # Thử tay 15/10/2026: dàn ý soạn thêm 2 câu ra plan hai bước `start_drafting`, mỗi câu
        # một bước. Cùng một đề thì đó là **một** lần soạn theo một dàn ý: gộp thành bước đầu,
        # số câu để BE điền từ dàn ý (`draft-outline`); tên bước nói cả lần soạn, không câu đầu.
        first = drafting[0].model_copy(
            update={
                "args": {
                    **drafting[0].args,
                    "assessment_id": next(iter(targets), ""),
                    "question_count": "",
                },
                "title": "Soạn câu hỏi theo dàn ý",
            }
        )
        steps = tuple(
            first if one is drafting[0] else one
            for one in steps
            if one.tool_name != "start_drafting" or one is drafting[0]
        )
        drafting = [first]
    if len(drafting) > 1:
        # Một dàn ý giáo viên duyệt là **một** lần soạn: hai bước soạn trong một plan là hai đề
        # (hay hai lượt) từ một lần duyệt (review đợt 3).
        return "một plan chỉ soạn một lần, theo một dàn ý; tách việc kia sang lượt sau"
    shown = await _shown_outline(session, thread, began)
    if shown is None:
        return (
            "giáo viên chưa thấy dàn ý nào cho lần soạn này: nêu dàn ý (kind outline) trước; "
            "câu hỏi chỉ được soạn ở lượt sau, khi giáo viên đã đồng ý"
        )
    replaces = any(one.tool_name == "replace_question" for one in steps)
    if opens and replaces:
        # Thay một câu là trên đề đã có: mở đề mới rồi thay là để lại một đề rỗng (review đợt 5).
        return "thay câu là trên đề đã có, không mở đề mới; plan chỉ một bước replace_question"
    wanted = "replace" if replaces else "new" if opens else "more"
    purpose = shown.get("for", "new")
    if purpose != wanted:
        if purpose == "new":
            return "dàn ý đã xem là cho một đề mới: plan cần create_draft rồi start_drafting"
        return (
            f"dàn ý đã xem là dàn ý for={purpose}, còn plan này là for={wanted}; "
            "nêu lại dàn ý cho đúng việc"
        )
    book = str(shown.get("document_id") or "")
    paper = str(shown.get("assessment_id") or "")
    sources = sorted(
        {node for item in shown.get("items", []) for node in item.get("source_nodes", [])}
    )
    out = []
    for one in steps:
        args = dict(one.args)
        if one.tool_name == "create_draft":
            # Đề mở trên đúng cuốn dàn ý đã đọc, hoặc không cuốn nào khi dàn ý không theo sách.
            chosen = str(args.get("document_id") or "").strip()
            if not chosen and book:
                args["document_id"] = book
            elif chosen != book:
                return (
                    "plan mở đề trên một tài liệu khác tài liệu của dàn ý đã xem; "
                    "mở đề đúng tài liệu ấy, hoặc nêu dàn ý mới"
                )
            if book and not str(args.get("nodes") or "").strip() and sources:
                args["nodes"] = ",".join(str(node) for node in sources)
        if one.tool_name == "replace_question":
            # Câu bị thay là câu dàn ý đã viết cho -- BE biết, không phải đoán.
            asked_for = str(args.get("question_number") or "").strip()
            meant = str(shown.get("first") or "")
            if not asked_for:
                args["question_number"] = meant
            elif asked_for != meant:
                return (
                    f"dàn ý giáo viên đã xem là để thay câu {meant}, plan lại thay câu {asked_for}"
                )
        if one.tool_name == "start_drafting":
            # Số câu là tổng của dàn ý đã xem: trống thì BE điền; một con số khác là plan soạn
            # khác thứ giáo viên đã đọc. Chữ không đọc được thì để tool từ chối như mọi tham số.
            asked = str(args.get("question_count") or "").strip()
            total = str(shown.get("total") or "")
            if not asked:
                args["question_count"] = total
            elif asked.isdigit() and asked != total:
                return (
                    f"dàn ý giáo viên đã xem có {total} câu, plan lại xin {asked}; "
                    "soạn đúng dàn ý, hoặc nêu dàn ý mới"
                )
        if one.tool_name in _DRAFTING_TOOLS and not opens:
            # Soạn thêm hay thay câu: đúng đề dàn ý được viết cho.
            asked_for = str(args.get("assessment_id") or "").strip()
            if not asked_for:
                args["assessment_id"] = paper
            elif asked_for != paper:
                return "plan soạn cho một đề khác đề của dàn ý đã xem; soạn đúng đề ấy"
        out.append(one.model_copy(update={"args": args}))
    return tuple(out), shown


async def outline_turn(
    session: AsyncSession,
    asking: Asking,
    thread: str,
    step: NextStepCompleted,
    history: list[TurnRecord],
    attached: AttachedDocument | None,
) -> TurnRecord | dict:
    """Kiểm các mục của một dàn ý model nêu và dựng lượt dàn ý BE sẽ lưu và in ra (ADR-29,
    ADR-30). Lời Kriky đi nguyên vẹn: BE không đối chiếu nó với các mục (hậu ký 20/10/2026 của
    ADR-30).

    Args:
        session: Session của database.
        asking: Ai đang hỏi.
        thread: Đoạn chat.
        step: Lượt `outline` model nêu.
        history: Mọi bước tới giờ của lượt, để tìm cuốn sách vừa đọc.
        attached: Chip đang gắn, khi có.

    Returns:
        `TurnRecord(kind="outline")` với `text` là lời Kriky (ADR-30) và `tool_result` là các
        mục; hoặc `{"error": lý do}` để model sửa dàn ý trong cùng lượt.
    """
    shape = await _outline_shape(session, thread, step)
    if isinstance(shape, str):
        return {"error": shape}
    purpose, first, most, paper = shape
    document_id = _outline_book(history, attached)
    if paper:
        # Soạn thêm hay thay câu là trên **đề đã có**: sách của dàn ý là sách của đề, không phải
        # chip đang gắn. Thử tay 15/10/2026: chip tự đính lúc tải sách lên làm dàn ý thay câu của
        # một đề không sách bị đòi bài nguồn (`draft-outline`).
        brief = await session.get(DraftBrief, paper)
        document_id = brief.document_id if brief is not None else ""
    known: set[int] | None = None
    if document_id:
        owned = await ready_document(session, asking, document_id)
        if owned is None:
            return {"error": "dàn ý trỏ về một tài liệu không có trong thư viện của giáo viên"}
        try:
            found = await get_reader().tree(owned.id)
        except ContentUnavailable:
            return {"error": "kho nội dung tài liệu tạm thời không đọc được"}
        nodes = found[1] if found else []
        known = {node.ordinal for node in nodes}
    items: list[OutlineItem] = list(step.outline)
    # Chỉ các mục, thứ job soạn câu nhận. Lời Kriky không bị so với chúng (hậu ký 20/10/2026 của
    # ADR-30): luật ấy và luật hình dạng công thức từng trả về 59 dàn ý trong bốn vòng thử tay
    # đầu-cuối, và giáo viên chỉ thấy một câu hệ thống thay cho lời Kriky. Lời trống thì vẫn trả
    # về: đó là một bong bóng rỗng, không phải một cách nói.
    wrong = validate(items, known, most=most) or (
        None if step.text.strip() else "lời dàn ý trống: viết lời trình bày dàn ý cho giáo viên"
    )
    if wrong is not None:
        return {"error": wrong}
    version = 1 + int(
        await session.scalar(
            select(func.count())
            .select_from(TeacherTurn)
            .where(TeacherTurn.conversation_id == thread, TeacherTurn.kind == "outline")
        )
        or 0
    )
    kept = stored(items, version=version, first=first, document_id=document_id)
    # Việc và đề của dàn ý đi cùng nó: cổng duyệt so plan với **chính** đề này, không với đề mới
    # nhất lúc plan chạy (review đợt 3).
    kept["for"] = purpose
    kept["assessment_id"] = paper
    # Môn, khối, phạm vi của dàn ý, lúc model còn đủ bốn mục: lượt *"oke"* sau đó dựng plan từ chính
    # dàn ý, không từ trí nhớ của model (thử tay 15/10/2026, `draft-outline`).
    kept["brief"] = await _filled_brief(
        session,
        thread,
        paper,
        {key: str(step.tool_args.get(key) or "").strip() for key in _BRIEF_KEYS},
    )
    return TurnRecord(
        kind="outline",
        # Lời Kriky, nguyên văn (ADR-30): BE không dựng lại, không sửa.
        text=step.text.strip(),
        tool_result=kept,
    )


# Lời cho **giáo viên** trên dòng ✕ khi `error` chở tên tool (`said`, plan `backlog-tier-1`).
_SAID_NOT_NOW = "Kriky gọi một việc không làm được ở bước này"
_SAID_BROKE = "Việc này chạy không xong"

_BRIEF_KEYS = ("subject", "grade", "topic_scope")


async def _filled_brief(
    session: AsyncSession, thread: str, paper: str, brief: dict[str, str]
) -> dict[str, str]:
    """Môn, khối, phạm vi của một dàn ý, lấp chỗ trống từ dàn ý trước của đoạn chat.

    Thử tay 16-17/10/2026: Haiku để trống `known` từ lượt thứ hai (plan `backlog-tier-1`, pha 1;
    phần còn hở ở backlog *Dàn ý lưu `brief` rỗng khi không có dàn ý trước nào để lấp*), nên dàn ý
    sửa lưu `brief` rỗng -- *"oke"* lùi về plan của model thay vì plan dựng từ dàn ý
    (`approved_plan`). Database giữ đủ `tool_result` của mọi dàn ý, nên chỗ trống lấy từ
    dàn ý gần nhất có giá trị; dàn ý cho đề đã có (*thêm*, *thay*) thì lấy cả từ chính đề ấy.
    Model ghi giá trị nào thì giá trị ấy thắng.

    Chỉ các dàn ý **cùng đề** (`assessment_id`, rỗng là đề mới), và chỉ **sau lần `create_draft`
    thành công gần nhất**: đề trước đã được tạo thì dàn ý trước nó là của đề khác -- *"soạn thêm
    một đề mới lớp 8"* từng được lấp khối 7 của đề cũ (review code pha 5). Một plan mà
    `create_draft` hỏng không tạo đề nào, nên không phải mốc; và dàn ý *soạn thêm cho đề X* không
    cho dàn ý đề mới mượn (review code vòng 2, plan `backlog-tier-1`).

    Args:
        session: Session của database.
        thread: Đoạn chat.
        paper: Đề của dàn ý; rỗng với dàn ý cho đề mới.
        brief: Thứ model ghi lượt này, có thể có ô rỗng.

    Returns:
        `brief` với các ô rỗng đã lấp được.
    """
    if all(brief.values()):
        return brief
    filled = dict(brief)
    made = await session.execute(
        select(TeacherTurn.sequence, TeacherTurn.tool_result).where(
            TeacherTurn.conversation_id == thread,
            TeacherTurn.kind == "tool_result",
            TeacherTurn.tool_name == "create_draft",
        )
    )
    since = max((at for at, result in made if (result or {}).get("created") is True), default=-1)
    earlier = await session.scalars(
        select(TeacherTurn.tool_result)
        .where(
            TeacherTurn.conversation_id == thread,
            TeacherTurn.kind == "outline",
            TeacherTurn.sequence > since,
        )
        .order_by(TeacherTurn.sequence.desc())
    )
    for result in earlier:
        if str((result or {}).get("assessment_id") or "") != paper:
            continue
        before = (result or {}).get("brief") or {}
        for key in _BRIEF_KEYS:
            if not filled[key] and str(before.get(key) or "").strip():
                filled[key] = str(before[key]).strip()
        if all(filled.values()):
            return filled
    if paper:
        assessment = await session.get(Assessment, paper)
        draft = await session.get(DraftBrief, paper)
        known = {
            "subject": assessment.subject if assessment is not None else "",
            "grade": assessment.grade if assessment is not None else "",
            "topic_scope": draft.topic_scope if draft is not None else "",
        }
        for key in _BRIEF_KEYS:
            if not filled[key]:
                filled[key] = str(known[key] or "").strip()
    return filled


async def _last_chip(session: AsyncSession, thread: str) -> str:
    """Chip tài liệu gần nhất giáo viên đã đính trong đoạn chat này, rỗng khi chưa từng có.

    Args:
        session: Session của database.
        thread: Đoạn chat.

    Returns:
        `document_id` của câu giáo viên gần nhất có chip.
    """
    found = await session.scalar(
        select(TeacherTurn.document_id)
        .where(TeacherTurn.conversation_id == thread, TeacherTurn.document_id != "")
        .order_by(TeacherTurn.sequence.desc())
        .limit(1)
    )
    return found or ""


async def _read_documents_before(session: AsyncSession, thread: str) -> bool:
    """Đoạn chat này đã từng gọi một tool đọc tài liệu chưa -- đọc từ database, cả đoạn chat.

    FE xoá chip ngay khi gửi, và một đoạn chat chọn sách qua `list_documents` thì không có chip
    nào. Đọc từ database chứ không từ cửa sổ `_HISTORY_STEPS`: một đoạn chat dài không được quên
    rằng nó đang nói về một cuốn sách (review B3, `draft-from-document`, B5).

    Args:
        session: Session của database.
        thread: Đoạn chat.

    Returns:
        True khi có một bước `tool_call` của `list_documents`, `list_chapters` hay `get_chapter`.
    """
    found = await session.scalar(
        select(TeacherTurn.id)
        .where(
            TeacherTurn.conversation_id == thread,
            TeacherTurn.kind == "tool_call",
            TeacherTurn.tool_name.in_(_DOCUMENT_READS),
        )
        .limit(1)
    )
    return found is not None


def _read_other_books(history: list[TurnRecord], attached: AttachedDocument) -> bool:
    """Lượt này đã đọc mục lục của một cuốn **khác** cuốn đang gắn chưa.

    Khi đã đọc, một `nodes` model gửi có thể là số của cuốn kia; điền `document_id` của cuốn đang
    gắn vào đó là mở đề trên một mục khác hẳn của một sách khác (review B7, `draft-from-document`).
    Không điền gì -- để `vet_plan` từ chối nếu model quên.

    Args:
        history: Các bản ghi đã gửi AGENT.
        attached: Cuốn đang gắn.

    Returns:
        True khi có một lần `list_chapters`/`get_chapter`/`read_section` với `document_id` khác.
    """
    return any(
        turn.kind == "tool_call"
        and turn.tool_name in _BOOK_READS
        and str(turn.tool_args.get("document_id") or "") not in {"", attached.document_id}
        for turn in history
    )


def _option(entry: dict) -> str:
    """Một nút bấm từ một candidate: lớp kèm sĩ số, hoặc `label` BE đã dựng (`draft-from-document`).

    `label` là của **BE** -- `node_label` hay tên tệp trong `teacher_tools` -- nên luật ADR-23 vẫn
    nguyên: không chuỗi nào trên nút đi qua tay model.

    Args:
        entry: Một dòng trong `candidates`.

    Returns:
        Chữ trên nút, rỗng khi dòng không có hình dạng nào trong hai.
    """
    name, count = entry.get("name"), entry.get("student_count")
    if isinstance(name, str) and isinstance(count, int):
        return f"{name} ({count} học sinh)"
    label = entry.get("label")
    return label if isinstance(label, str) else ""


def _offered(result: dict) -> tuple[list[str], int]:
    """Dựng các phương án cho một câu hỏi lại, từ chính kết quả của một tool.

    BE viết chúng, không phải model. Lọc lại thứ model viết là cách làm đầu tiên và nó rò
    cả hai chiều, đo được chứ không phải đoán: "12A-1" lọt qua nhờ dựa vào một "12A"
    thật, "12A (45 học sinh)" lọt qua với một con số học sinh không ai đếm, còn một
    "12A 3 học sinh" hoàn toàn tử tế thì bị ném đi. Mọi lỗ đó bịt lại cùng một lúc khi
    không còn văn bản tự do nào để đi soi -- model viết câu hỏi, BE viết các câu trả lời.

    Args:
        result: Giá trị trả về của một tool. Chỉ `candidates` sinh ra phương án --
            một danh sách không-tìm-thấy là context để trợ lý nhắc tới, không phải một
            bộ phương án để bấm vào. `more` cũng được đọc, nhưng chỉ để đếm phần bị
            cắt, nên nó không thêm được một phương án nào.

    Returns:
        Các phương án, và có bao nhiêu candidate nữa đã bị cắt. Con số đó đi kèm để câu
        hỏi thừa nhận được rằng danh sách chưa đủ -- một giáo viên có ba mươi lớp mà chỉ
        được cho xem sáu lớp, không được nói gì thêm, thì đọc ra là dữ liệu đã mất.
    """
    listed = result.get("candidates")
    if not isinstance(listed, list):
        return [], 0

    options = [_option(entry) for entry in listed if isinstance(entry, dict)]
    options = [one for one in options if one]
    more = result.get("more")
    return options, more if isinstance(more, int) and more > 0 else 0


# Chữ của lối *"Khác"*. Từ 13/10/2026 (người dùng chốt) nó **không** còn là một nút BE gửi: FE tự
# vẽ "Khác…" dưới mọi thẻ có lựa chọn, bấm vào là mở ô để giáo viên ghi rõ, và câu họ ghi mới là
# câu trả lời. BE giữ chữ này để loại "Khác" model tự viết khỏi nút (`_choices`), và để đọc nút đã
# lưu của các đoạn chat cũ -- ở đó "Khác" còn nằm cuối (`_rows_in_play`).
OTHER_CHOICE = "Khác"

# Trần cho phương án model viết ở câu hỏi về **tham số** -- cùng trần sáu với danh sách lớp
# (`resolve._MOST_CANDIDATES`): một câu hỏi trả lời được, không phải một danh sách phải đọc.
_MOST_CHOICES = 6


def _spaced(text: str) -> str:
    return " ".join(text.split())


def _named(result: dict) -> dict[str, str]:
    """Chữ model có thể viết để chọn một phương án BE đã dựng, trỏ về đúng phương án ấy.

    Một phương án nhận hai tên: chính chữ trên nút, và `name` của dòng -- tên lớp không kèm sĩ số,
    thứ model đọc được trong `candidates`. Một tên trỏ tới **hai** phương án -- hai lớp trùng tên
    -- thì bị bỏ: chỉ giáo viên phân biệt được chúng, bằng sĩ số (ADR-23).

    Args:
        result: Giá trị trả về của một tool.

    Returns:
        Tên (đã gộp khoảng trắng) → chữ trên nút; rỗng khi kết quả không có `candidates`.
    """
    listed = result.get("candidates")
    if not isinstance(listed, list):
        return {}
    keyed: dict[str, set[str]] = {}
    for entry in listed:
        if not isinstance(entry, dict):
            continue
        option = _option(entry)
        if not option:
            continue
        for key in {option, entry.get("name")}:
            if isinstance(key, str) and key.strip():
                keyed.setdefault(_spaced(key), set()).add(option)
    return {key: next(iter(options)) for key, options in keyed.items() if len(options) == 1}


def _choices(proposed: tuple[str, ...], offered: list[str], named: dict[str, str]) -> list[str]:
    """Các nút của một câu hỏi lại: ít nhất ba khi dữ liệu cho phép.

    Hai loại câu hỏi, hai nguồn (`unbiased-model-text` T3, người dùng chốt 12/10/2026):

    - Hỏi về một **dòng** -- lớp, tài liệu, mục -- tức có `candidates` đang được hỏi (`offered`).
      Nút là **mọi** nhãn BE dựng, như ADR-23: *"trả về tất cả"*, một dòng bị giấu là lớp giáo viên
      đang cần. Phương án model viết chỉ được làm một việc: khớp **đúng** một tên trong `named` thì
      dòng ấy đứng lên đầu (review T3 -- bản đầu bày đúng tập con model chọn, và giấu dòng thật mà
      không báo). Không khớp mờ: bản lọc đầu của ADR-23 rò hai chiều (*"12A-1"* lọt nhờ *"12A"*).
    - Hỏi về một **tham số** -- số câu, khối, phạm vi -- không có dòng nào để dựng nút. Trước T3
      câu hỏi ấy không có nút nào và giáo viên phải gõ lại cả câu; nay nút là chữ model đề xuất,
      gộp trùng (không phân biệt hoa thường), có trần.

    Args:
        proposed: `choices` model trả về.
        offered: Nhãn BE dựng từ `candidates` đang được hỏi, có thể rỗng.
        named: `_named` của cùng kết quả ấy.

    Returns:
        Chữ trên các nút, theo thứ tự bày; rỗng khi không có lựa chọn thật nào. Không có "Khác":
        FE tự vẽ lối ấy (xem `OTHER_CHOICE`).
    """
    if offered:
        picked: list[str] = []
        for one in proposed:
            option = named.get(_spaced(one))
            if option is not None and option not in picked:
                picked.append(option)
        chosen = [*picked, *(one for one in offered if one not in picked)]
    else:
        chosen = []
        seen = {OTHER_CHOICE.casefold()}
        for one in proposed:
            text = _spaced(one)
            if text and text.casefold() not in seen:
                seen.add(text.casefold())
                chosen.append(text)
        chosen = chosen[:_MOST_CHOICES]
    # Không lựa chọn thật nào -- model chỉ đưa tên mục -- thì không nút nào, và FE không vẽ thẻ.
    return chosen


def _questions_of(
    step: NextStepCompleted, about_a_row: bool, named: dict[str, str]
) -> tuple[str, tuple[str, ...], list[dict]]:
    """Lời, nút và các câu của một câu hỏi lại, sau luật một-lượt-một-câu-về-dòng (ADR-32). Hàm
    thuần.

    Nhiều câu thì mỗi câu một bộ nút, dựng như nút của một câu hỏi về **tham số** (`_choices` không
    có `offered`). Câu hỏi về một **dòng** -- có `candidates` đang được hỏi -- thì một lượt chỉ một
    câu: nút phải là mọi nhãn BE dựng (ADR-23), và các nhãn ấy chỉ trả lời được một câu. Giữ câu
    có lựa chọn gọi đúng một dòng -- không thì câu đầu --, gộp lời mở với nó; các câu khác bỏ, model
    hỏi lại ở lượt sau. Giữ câu đầu một cách mù quáng thì *"Bao nhiêu câu?"* mang nút *"12A (3 học
    sinh)"* (review pha 6).

    Nhãn trống hay trùng được đánh số: câu trả lời gộp *"Nhãn: trả lời"* chỉ đọc được khi mỗi nhãn
    trỏ về một câu.

    Args:
        step: Đề nghị model vừa nêu.
        about_a_row: Lượt này có `candidates` đang được hỏi không.
        named: Tên trỏ về từng dòng đang được hỏi (`_named`).

    Returns:
        `(lời, nút model đề xuất, các câu đã dựng nút)`; các câu rỗng khi lượt là một câu hỏi.
    """
    if not step.questions:
        return step.text, step.choices, []
    if about_a_row:
        first = next(
            (
                one
                for one in step.questions
                if any(_spaced(choice) in named for choice in one.choices)
            ),
            step.questions[0],
        )
        lead = step.text.strip()
        joined = f"{lead}\n\n{first.text}" if lead and lead != first.text else first.text
        return joined, first.choices, []
    several, seen = [], set()
    for index, one in enumerate(step.questions, start=1):
        label = one.label.strip() or f"Câu {index}"
        if label in seen:
            label = f"{label} ({index})"
        seen.add(label)
        several.append({"label": label, "text": one.text, "choices": _choices(one.choices, [], {})})
    return step.text, (), several


def _rows_in_play(stored: list[TeacherTurn], said: str) -> dict:
    """Kết quả tool mà một câu hỏi về dòng của lượt trước còn đang hỏi, hay `{}`.

    Review T3 (`unbiased-model-text`): câu hỏi về một lớp không xong trong một lượt -- giáo viên ghi
    ở lối "Khác", hay gõ một tên khác, và model hỏi lại mà **không** gọi tool. Xét theo riêng lượt
    này thì không có `candidates` nào, câu hỏi bị coi là về tham số, và chữ model viết thành nút:
    *"12A-1"*, *"12A (45 học sinh)"* -- đúng chuỗi ADR-23 đo là rò. Nên câu hỏi còn **mở** khi câu
    hỏi lại gần nhất bày đúng nhãn BE dựng từ một kết quả có `candidates` đứng trước nó, và câu giáo
    viên vừa gõ không phải một trong các nhãn ấy -- bấm một nhãn là đã trả lời xong.

    Args:
        stored: Các bước đã lưu của đoạn chat, cũ nhất trước, **chưa** gồm câu giáo viên vừa gõ.
        said: Câu giáo viên vừa gõ.

    Returns:
        Kết quả tool để dựng lại nút, hay `{}` khi không câu hỏi về dòng nào còn mở.
    """
    # Một dàn ý hay một plan đứng sau câu hỏi là câu hỏi ấy đã qua: model đã đi tiếp mà không cần
    # câu trả lời (review đợt 3, plan `backlog-tier-1`).
    last = next(
        (turn for turn in reversed(stored) if turn.kind in {"assistant", "outline", "plan"}), None
    )
    asked = last if last is not None and last.kind == "assistant" else None
    shown = [one for one in (asked.choices if asked is not None else None) or [] if one]
    rows = [one for one in shown if one != OTHER_CHOICE]
    if not rows:
        return {}
    before = stored[: stored.index(asked)]
    result = next(
        (
            turn.tool_result
            for turn in reversed(before)
            if turn.kind == "tool_result"
            and isinstance((turn.tool_result or {}).get("candidates"), list)
        ),
        None,
    )
    if result is None:
        return {}
    labels, _ = _offered(result)
    if not set(rows) <= set(labels) or _spaced(said) in labels:
        return {}
    return result


# Bao nhiêu bước trong quá khứ được gửi sang model. Toàn bộ bản ghi hội thoại được gửi
# lại ở mỗi bước của mỗi lượt, nên một history không chặn sẽ làm một hội thoại kéo dài
# trở nên đắt theo bình phương -- và những lượt cũ nhất là những lượt ít khả năng còn
# quan trọng nhất. Là một hằng số chứ không phải một setting: chưa có gì để một người vận
# hành tinh chỉnh, và một setting không ai đọc là một lời hứa mà config không giữ.
_HISTORY_STEPS = 40

# Một kết quả tool nói về entity nào, dùng cho cái row ghi lại bước đó. Chủ thể là thứ
# giao diện vẽ ra và là thứ một câu hỏi sau này liên kết tới; câu nói công bố nó thì
# không.
#
# `assessment_id` từng bị lấy ra khỏi đây một lần, khi một lượt review chỉ ra rằng không
# tool nào trả về nó và nhánh đó không với tới được. Giờ `create_draft` trả về nó, nên nó
# quay lại -- và đây là lượt đầu tiên mà chủ thể là một đề chứ không phải một lớp, thứ mà
# `Action result card` cần để vẽ được bất cứ gì về việc soạn đề.
_ENTITY_KEYS = (("class_id", "class"), ("assessment_id", "assessment"))


def _subject(result: dict) -> tuple[str, str]:
    """Gọi tên entity mà một kết quả tool nói về, khi nó có nói về một entity.

    Một lớp từ `get_class`, hoặc một đề nháp từ `create_draft` và `start_drafting`. Các
    cột chứa đúng những gì các tool thực sự trả về, nên chúng lớn dần theo các tool.

    `list_class` thì không: nó trả về một **danh sách**, và một bước nói về nhiều lớp thì
    không nói về lớp nào cả. Chủ thể của nó là lựa chọn giáo viên sắp đưa ra, không phải
    một dòng trong database.

    Một kết quả có nói về thứ gì đó khi nó nói là nó thành công, và cả tool lẫn endpoint
    đều nói điều đó bằng một cờ: `found` cho một lần tra cứu, `created` cho một đề nháp
    mới, `started` cho một vòng sinh câu hỏi, `approved`/`unapproved`/`published` cho ba quyết
    định của giáo viên. Liệt kê các cờ thì hơn là đi soi tên tool, vì cái tên không phải
    thứ mang theo id.

    Args:
        result: Giá trị trả về của một tool.

    Returns:
        Loại và id, hoặc hai string rỗng. Chỉ một kết quả thành công mới có chủ thể: một
        lời từ chối thì không nói về gì cả, và ghi lại các tham số của nó như một entity
        là tạo ra những liên kết trỏ tới những row chưa bao giờ được tìm thấy.
    """
    if not any(result.get(flag) for flag in DID_IT_HAPPEN):
        return "", ""
    for key, kind in _ENTITY_KEYS:
        value = result.get(key)
        if isinstance(value, str) and value:
            return kind, value
    return "", ""


# Cái tên nằm trên một hàng rộng 228px của rail, và `title` là `String(120)`. Cắt ở 60:
# quá con số đó thì không ai đọc hết, và một chuỗi bị cắt giữa chừng trông như một lỗi.
_TITLE_LIMIT = 60


def _tidy(title: str) -> str:
    """Dọn một cái tên model vừa viết.

    Model được bảo là đừng dùng dấu ngoặc kép và đừng chấm câu, và model vẫn làm cả hai.
    Một prompt là một lời nhờ, không phải một ràng buộc -- nên chỗ ràng buộc là đây.

    Args:
        title: Nguyên văn model trả về.

    Returns:
        Một dòng đã dọn, dài nhất `_TITLE_LIMIT` ký tự. Rỗng khi không còn gì.
    """
    cleaned = " ".join(title.split()).strip().strip('"').strip("'").rstrip(".").strip()
    return cleaned[:_TITLE_LIMIT]


# Chỉ các cụm **chữ**, bỏ dấu câu và bỏ cả chữ số. `[^\W\d_]` là "ký tự chữ" theo Unicode.
#
# Chữ số bị bỏ vì nó là token dễ trùng nhất mà **nghĩa** thì không trùng: câu "soạn 10 câu
# đạo hàm" và một tiêu đề bịa "Đề 15 phút lớp 10" chung đúng một chữ "10", một bên là số
# câu một bên là số lớp -- và thế là một cái tên bịa trọn gói đi lọt.
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def _echoes(said: str, title: str) -> bool:
    """Cái tên này có nói về câu đã gõ không, hay model vừa bịa ra một việc?

    Đo được trên trình duyệt thật: giáo viên gõ *"Chào bạn"* và rail hiện *"Tạo đề kiểm tra
    15 phút"*. Không khâu nào bắt được, vì cái tên ấy **tuân thủ** mọi luật của prompt --
    sáu từ, viết thường, không ngoặc kép, không chấm câu. `_tidy` chỉ dọn hình thức, và
    hình thức thì không sai.

    Nên phép kiểm phải hỏi một câu khác: *cái tên có chung chữ nào với câu đã gõ không*.
    Bịa trọn gói thì không có chữ nào chung. Một bản rút gọn, một bản diễn đạt lại, hay một
    cái tên ghép từ chính câu ấy thì luôn có.

    Cố ý **không** bỏ hư từ. Mục tiêu là bắt chuyện bịa trọn gói, không phải chấm điểm cái
    tên: một tiêu đề chung đúng một hư từ với câu đã gõ vẫn là một tiêu đề đọc được, còn
    một tiêu đề không chung chữ nào thì nói về một đoạn chat khác.

    Args:
        said: Câu đầu tiên của giáo viên.
        title: Tên model vừa viết, đã dọn.

    Returns:
        True khi hai chuỗi chung ít nhất một từ.
    """
    # Chuẩn hoá NFC hai phía. Bàn phím tiếng Việt trên iOS và macOS sinh **NFD**: dấu là
    # một ký tự tổ hợp riêng, và ký tự ấy không phải "ký tự chữ", nên regex băm "Soạn" ra
    # thành "Soa" + "n". Một bên NFD gặp một bên NFC thì không từ nào khớp từ nào, và việc
    # đặt tên **tắt hoàn toàn** mà dấu vết duy nhất là một dòng log.
    spoken = {one.casefold() for one in _WORD.findall(unicodedata.normalize("NFC", said))}
    return any(
        one.casefold() in spoken for one in _WORD.findall(unicodedata.normalize("NFC", title))
    )


async def _name_the_thread(
    session: AsyncSession, request: Request, settings: Settings, thread: str, said: str
) -> None:
    """Đặt tên cho một đoạn chat vừa mở, sau khi lượt đầu của nó đã xong.

    Chạy **sau** lượt nói, không phải trước: trước thì giáo viên chờ thêm một lời gọi model
    nữa mới thấy câu trả lời, mà cái tên thì chỉ có ích sau khi có đoạn chat thứ hai.

    `run_task` chờ kết quả thay vì bắn rồi quên, vì BE **không có worker chạy nền** -- một
    job không ai thu thì cái tên không bao giờ được ghi.

    Nuốt mọi lỗi. Task này đứng ở cuối một lượt đã thành công và đã commit từng bước; một
    exception thoát ra từ đây sẽ biến lượt ấy thành một lỗi 500 và giáo viên mất cả việc
    vừa nhờ, vì một dòng chữ trên rail. Đường lùi là câu đầu cắt ngắn, và nó luôn có.

    Args:
        session: Session của database. Hàm này commit.
        request: Request đang chạy, để lấy pool của hàng đợi.
        settings: Cấu hình, cho timeout của job.
        thread: Đoạn chat nào.
        said: Câu đầu tiên của giáo viên.

    Side effects:
        Ghi `title` lên hàng hội thoại và commit. Không làm gì khi hàng đã có tên.
    """
    row = await session.get(TeacherConversation, thread)
    if row is None or row.title:
        return

    title = _tidy(said)
    asked = new_id()
    try:
        answer = await run_task(
            getattr(request.app.state, "queue_pool", None),
            settings,
            NAME_CONVERSATION_TASK,
            ConversationNameRequested(request_id=asked, said=said).model_dump(mode="json"),
        )
        completed = ConversationNameCompleted.model_validate(answer)
        written = _tidy(completed.title)
        if completed.request_id != asked:
            # Câu trả lời của một job khác. Chưa đo được lần nào, nhưng không có phép kiểm
            # này thì nó sẽ là một cái tên sai **không để lại dấu vết nào** -- hai đoạn
            # chat mở cùng lúc, và một trong hai mang tên của đoạn kia.
            logger.warning("naming answer for %s did not match the job asked", thread)
        elif _echoes(said, written):
            title = written
        else:
            # Model bịa trọn gói. Giữ câu đầu cắt ngắn -- nó luôn đúng về đoạn chat này,
            # kể cả khi nó kém duyên hơn một cái tên model viết.
            logger.info("ignored an invented title for %s: %r", thread, written)
    except Exception:  # noqa: BLE001 -- xem docstring
        logger.exception("could not name conversation %s", thread)

    row.title = title
    session.add(row)
    await session.commit()


# Lý do một plan không dùng được, **cho model** (ADR-30): BE không nói thay Kriky. Lời từ chối của
# `vet_plan` cộng một câu về tài liệu khi đó là nguyên nhân, để model nói với giáo viên đúng chỗ
# vướng -- *"nói lại"* chung chung thì nói lại bao nhiêu lần cũng không qua (review B7,
# `draft-from-document`).
_BOOK_SCOPE_MISSING = (
    "đoạn chat này soạn theo tài liệu {filename}: create_draft cần nodes là chương hay bài của tài "
    "liệu ấy; chưa biết thì hỏi giáo viên chương hay bài nào, hoặc bảo họ mở đoạn chat mới nếu "
    "muốn đề không theo tài liệu"
)
_BOOK_NOT_READY = (
    "tài liệu {filename} chưa dùng được để soạn đề (đang xử lý hoặc xử lý không thành): nói với "
    "giáo viên chờ tài liệu sẵn sàng, hoặc đính tài liệu khác"
)


def vet_plan(steps: tuple[PlanStep, ...], allowed: tuple[ToolSpec, ...]) -> str | None:
    """Kiểm một plan **trước** khi chạy bước nào.

    Bốn thứ kiểm được mà không cần chạy gì: plan không dài quá trần, mỗi tool có trong catalog
    pha thực hiện, **đủ** tham số mà spec nêu, và mỗi tham chiếu `{k.field}` **đúng khuôn** và
    trỏ về **phía sau**. Một tham số *lạ* thì chỉ bị bỏ, vì nó không làm bước nào ghi sai —
    giết cả plan vì nó là đổi một lời từ chối cho giáo viên lấy một thứ không ai mất.

    Bắt được bốn thứ kia ở đây nghĩa là không có bước nào kịp ghi trước khi cái sai lộ ra --
    mà một bước đã ghi thì để lại rác không xoá được, đúng thứ ADR-25 sinh ra để diệt.

    Thứ **không** kiểm được ở đây: field được trỏ tới có thật trong kết quả của bước `k` hay
    không. `ToolSpec` chở tên tham số chứ không chở tên field trả về, nên luật ấy chỉ thi
    hành được lúc chạy, trong `resolve_args`. Muốn nó thành phép kiểm tĩnh thì `ToolSpec`
    phải chở thêm dữ liệu -- một việc có thật, chưa làm, và không được nói là đã làm.

    Args:
        steps: Các bước model đề nghị, theo thứ tự.
        allowed: Catalog của pha thực hiện.

    Returns:
        None khi plan dùng được, hoặc một câu nói vì sao nó không dùng được -- **để log**,
        không để in ra màn hình.
    """
    if len(steps) > _MOST_STEPS:
        return f"plan có {len(steps)} bước, quá trần {_MOST_STEPS}"

    by_name = {spec.name: spec for spec in allowed}
    for index, step in enumerate(steps, start=1):
        spec = by_name.get(step.tool_name)
        if spec is None:
            return f"bước {index} gọi {step.tool_name}, không có trong catalog pha thực hiện"
        missing = set(spec.arguments) - set(step.args) - set(spec.optional)
        if missing:
            # Mọi tham số được mô tả cho model đều là tham số **bắt buộc**, trừ những cái spec khai
            # tường minh ở `optional` (`draft-from-document`): catalog chỉ nêu những thứ tool thật
            # sự cần. Thiếu một cái là một bước sẽ chạy với tay không -- đo trên trình duyệt thật,
            # model nêu `start_drafting` không kèm `assessment_id`, bước ấy hỏng, và lượt để lại một
            # đề rỗng mang tên giáo viên. Từ chối trọn gói ở đây là cách duy nhất không có gì kịp
            # ghi.
            return f"bước {index} thiếu tham số {sorted(missing)} của {step.tool_name}"
        for key, value in step.args.items():
            if key not in spec.arguments:
                # Bỏ qua, **không** giết cả plan. Một tham số lạ không làm bước nào ghi sai:
                # `execute` chỉ đưa cho tool những thứ tool nhận. Còn từ chối vì nó thì giáo
                # viên nhận "mình chưa dựng được các bước" cho một yêu cầu hoàn toàn hợp lệ,
                # và lần gõ lại cũng hỏng y vậy — đo được khi mô tả `create_draft` còn nhắc
                # `title`, nên chính mô tả ấy mời model gửi một thứ `vet_plan` giết.
                logger.info("step %d sent an argument outside the spec: %s", index, key)
                continue
            found = REFERENCE.match(value.strip())
            if found is None and key.endswith("_id") and value.strip().isdigit():
                # Mọi id là uuid, không bao giờ là số trần: `"1"` là model viết số bước thay cho
                # tham chiếu `{1.assessment_id}` -- chạy thì bước ấy đọc "không có đề nào như vậy"
                # (plan `backlog-tier-1`).
                return (
                    f"bước {index} gửi {key}={value}: id là chuỗi trong kết quả một bước trước, "
                    f"viết là {{k.{key}}}, không phải số thứ tự bước"
                )
            if found is None:
                # Trông như tham chiếu mà sai khuôn thì là lỗi của model, không phải chữ
                # của giáo viên -- cùng một luật `resolve_args` dùng lúc chạy, và phép
                # kiểm tĩnh không được phép nhẹ hơn phép kiểm runtime.
                if LOOKS_LIKE_REFERENCE.search(value):
                    return f"bước {index} viết sai khuôn tham chiếu ở {key}: {value}"
                continue
            points_at = int(found.group(1))
            if not 1 <= points_at < index:
                return f"bước {index} trỏ tới bước {points_at}, chưa chạy lúc nó cần"
    return None


# Lượt kể lại được đọc tối đa ngần này lần trước khi nói (ADR-25, hậu ký 22/10/2026): đủ cho
# `last_plan` rồi một tool đọc nữa, không đủ để lượt kể lại thành một vòng tra cứu thứ hai.
_MOST_TELLING_READS = 2


async def _tell_after_plan(
    request: Request,
    session: AsyncSession,
    settings: Settings,
    asking: Asking,
    thread: str,
    history: list[TurnRecord],
) -> tuple[str, bool]:
    """Lượt kể lại: hỏi `propose` thêm một lần sau khi plan đã chạy (ADR-25, hậu ký 22/10/2026).

    Thay cho job `report_plan` cũ. Model đọc lịch sử đã có kết quả từng bước, được cấp **chỉ tool
    đọc** của pha 1 -- trong đó có `last_plan` -- và không tool nào để nêu plan (`plannable` rỗng).
    Kể hay không là việc của skill (`soan-de.md` bước 6): một câu nói thành câu kết, im lặng thì
    lượt kết thúc không câu kết. Các lần đọc ở đây không ghi vào `teacher_turns`: chúng là tra cứu
    của riêng lời kể, và ghi chúng thì một lần F5 vẽ thêm bước vào khối bước của plan.

    Hỏng thì không ném: lượt không bao giờ chết vì phần kể lại, đúng như `_name_the_thread`.

    Args:
        request: Mang theo pool của queue.
        session: Session của database, cho các tool đọc.
        settings: Settings của process.
        asking: Giáo viên của lượt.
        thread: Đoạn chat.
        history: Lịch sử của lượt, đã có kết quả pha 2.

    Returns:
        `(câu kết, hỏng)`. Câu rỗng mà không hỏng là model chọn không nói gì.
    """
    reading = catalog_for(asking, PHASE_PLAN)
    seen = list(history)
    try:
        for read in range(_MOST_TELLING_READS + 1):
            # Lần cuối không còn tool nào: model đã đọc tới trần, giờ chỉ nói hay im (review plan
            # `report-into-propose`: lần thứ ba còn catalog thì một lần đọc nữa thành im lặng).
            offered = reading if read < _MOST_TELLING_READS else ()
            step = await _ask_agent(request, settings, asking.full_name, offered, (), seen)
            if step.notice:
                # Câu hệ thống của AGENT (model hỏng, hay hai lần không ra lời) không phải câu kết:
                # nó đi dưới `notice` của BE, không dưới giọng Kriky (ADR-30).
                logger.warning("telling after the plan came back as a notice in %s", thread)
                return "", True
            if step.kind == "call_tool" and offered:
                try:
                    result = await execute(
                        session,
                        asking,
                        step.tool_name,
                        step.tool_args,
                        pool=getattr(request.app.state, "queue_pool", None),
                        settings=settings,
                        phase=PHASE_PLAN,
                        conversation_id=thread,
                    )
                except UnknownTool:
                    result = {
                        "error": f"không có tool nào tên {step.tool_name}",
                        "said": _SAID_NOT_NOW,
                    }
                except Exception:  # noqa: BLE001 -- như pha 1: model đọc lỗi rồi nói tiếp
                    logger.exception("a read of the telling turn failed in %s", thread)
                    result = {
                        "error": f"tool {step.tool_name} chạy không xong",
                        "said": _SAID_BROKE,
                    }
                finally:
                    await session.rollback()
                result.pop(FORMULA_SECONDS, None)
                seen.append(
                    TurnRecord(kind="tool_call", tool_name=step.tool_name, tool_args=step.tool_args)
                )
                seen.append(
                    TurnRecord(kind="tool_result", tool_name=step.tool_name, tool_result=result)
                )
                continue
            if step.kind == "say":
                return step.text.strip(), False
            if step.kind == "ask_clarify":
                # Lượt kể lại không vẽ thẻ hỏi lại: nút và các câu rơi, chữ ở lại thành câu kết.
                asked = step.text.strip() or " ".join(one.text for one in step.questions).strip()
                return asked, False
            # Plan hay dàn ý: lượt kể lại không mở thêm việc nào.
            logger.info("telling after the plan ended as %s, saying nothing", step.kind)
            return "", False
    except Exception:  # noqa: BLE001 -- xem docstring
        logger.exception("could not tell about the plan in %s", thread)
        return "", True
    return "", False


async def _owned_conversation(session: AsyncSession, asking: Asking, thread: str) -> str | None:
    """Đoạn chat này có phải của người đang hỏi không.

    `conversation_id` nay là thứ **client gửi lên**, nên nó là một id không tin được —
    khác hẳn mọi id trước đây trong file này, vốn do chính BE tìm ra từ `teacher_id`. Một
    id của người khác mà lọt qua sẽ cho đọc nguyên một hội thoại không phải của mình.

    Trả `None` cho cả hai ca — không tồn tại, và không phải của bạn — vì ADR-22 nói hai ca
    ấy phải đọc ra **y hệt nhau**. Phân biệt được chúng là cho bất kỳ ai dò xem giáo viên
    khác đang có những gì, chỉ bằng cách thử id.

    Một đoạn **đã xoá** cũng trả `None`, và cùng một hàm này canh cả hai cửa: đọc lại nó ra
    404, và một câu mới không bao giờ rơi vào nó. Gộp vào đây chứ không viết hai lần ở hai
    chỗ, vì hai bản sao của một luật là hai thứ chờ lệch đi.

    Args:
        session: Session của database.
        asking: Ai đang hỏi.
        thread: Id client gửi lên.

    Returns:
        Chính id đó khi nó là của người hỏi và chưa bị xoá, ngược lại `None`.
    """
    return await session.scalar(
        select(TeacherConversation.id).where(
            TeacherConversation.id == thread,
            TeacherConversation.teacher_id == asking.teacher_id,
            TeacherConversation.deleted_at.is_(None),
        )
    )


def _spoke_at():
    """Lần nói cuối của mỗi hội thoại, dưới dạng một subquery ghép được.

    Hai nơi cần đúng con số này: `_latest_conversation` chọn luồng đang chạy, và danh
    sách trên rail sắp các luồng theo nó. Một biểu thức, hai người gọi — vì hai bản của
    cùng một phép sắp xếp là hai bản sẽ lệch nhau, và lúc lệch thì luồng đứng đầu danh
    sách không còn là luồng mà một tin nhắn không ghi id sẽ rơi vào.

    Returns:
        Subquery hai cột: `conversation_id` và `at`.
    """
    return (
        select(
            TeacherTurn.conversation_id.label("conversation_id"),
            func.max(TeacherTurn.created_at).label("at"),
        )
        .group_by(TeacherTurn.conversation_id)
        .subquery()
    )


async def _latest_conversation(session: AsyncSession, asking: Asking) -> str | None:
    """Tìm id của hội thoại **đang chạy** của giáo viên này, nếu họ có một hội thoại.

    Đang chạy nghĩa là *vừa nói trong đó gần đây nhất*, không phải *mở gần đây nhất*. Hai
    thứ đó khác nhau ngay khi có luồng thứ hai: một giáo viên mở luồng mới hôm qua rồi
    quay lại luồng cũ nói tiếp thì luồng cũ mới là luồng họ đang ở.

    Bản trước sắp theo `started_at` rồi tới `id`, và `id` là một UUID — tức một khoá phân
    giải hoà **xác định nhưng tuỳ tiện**. Một thời gian dài điều đó không hại gì vì mỗi
    giáo viên chỉ có một luồng. Nó hại ngay ở luồng thứ hai, và phép đo chỉ ra chỗ tệ
    nhất: `datetime.now()` trên Windows nhảy từng bước ~15ms, nên hai luồng mở sát nhau có
    `started_at` **bằng nhau** và luồng được chọn là luồng có UUID lớn hơn. Bấm *Đoạn chat
    mới* rồi gõ một câu, và một nửa số lần câu ấy rơi vào luồng cũ.

    Nên khoá sắp xếp là `COALESCE(lần nói cuối, started_at)`. Một luồng vừa mở chưa có
    bước nào thì lấy chính giờ mở của nó — và giờ đó mới hơn lần nói cuối của mọi luồng
    cũ, nên luồng vừa mở thắng, đúng như người bấm nút mong đợi.

    Args:
        session: Session của database.
        asking: Hội thoại của ai.

    Returns:
        id đó, hoặc None khi giáo viên chưa nói gì bao giờ.
    """
    spoke = _spoke_at()
    active = func.coalesce(spoke.c.at, TeacherConversation.started_at)
    return await session.scalar(
        select(TeacherConversation.id)
        .join(spoke, spoke.c.conversation_id == TeacherConversation.id, isouter=True)
        .where(
            TeacherConversation.teacher_id == asking.teacher_id,
            TeacherConversation.deleted_at.is_(None),
        )
        .order_by(active.desc(), TeacherConversation.id.desc())
        .limit(1)
    )


async def conversation_of(session: AsyncSession, asking: Asking, assessment_id: str) -> str | None:
    """Đoạn chat nào đã sinh ra đề này.

    Public vì `teacher_routes` cũng cần nó: panel đề mở từ bên trong đoạn chat của nó,
    nên `AssessmentDetail` phải nói được đoạn ấy là đoạn nào.

    Từ khi giáo viên mở được nhiều đoạn chat, *"ghi vào hội thoại đang chạy"* thôi không
    còn là một câu rõ nghĩa: duyệt và phát hành xảy ra **ngoài** khung chat, nên phải có
    một câu trả lời cho *"ngoài khung chat thì là khung nào"*.

    Câu trả lời suy ra được từ dữ liệu đã có. `_subject` đã ghi `entity_kind` và
    `entity_id` lên mỗi bước `tool_result` từ Pha 2, nên đề nào sinh ra từ đoạn nào là một
    sự thật đã nằm sẵn trong bảng — không cần cột mới, và không cần một tham số mới trên
    hai endpoint duyệt/phát hành.

    Lấy bước **sớm nhất**: một đề được nhắc tới trong nhiều đoạn chat thì đoạn đã tạo ra
    nó là đoạn nói về nó trước tiên.

    Lọc theo `teacher_id` dù `assessment_id` đã đủ hiếm: hai bảng nối nhau qua một id mà
    không ai kiểm chủ sở hữu là đúng cái lỗ mà ADR-22 dành cả một tài liệu để bịt.

    Args:
        session: Session của database.
        asking: Ai đang hỏi.
        assessment_id: Đề nào.

    Đoạn chat đã **xoá** đọc ra như không có: caller lùi về đoạn đang chạy, nên biên bản
    duyệt rơi vào một nơi giáo viên nhìn thấy được. Ghi nó vào một đoạn đã ẩn thì ADR-24 đạt
    về chữ — row vẫn tồn tại — và hỏng về việc: không ai mở được nó ra để đọc.

    Returns:
        id của đoạn chat, hoặc None khi đề không sinh ra từ đoạn chat nào — đề seed, đề tạo
        bằng tay, hoặc đoạn sinh ra nó đã bị xoá. Caller lùi về đoạn mới nhất chứ không nổ:
        một đề vẫn phải duyệt được.
    """
    return await session.scalar(
        select(TeacherTurn.conversation_id)
        .join(TeacherConversation, TeacherConversation.id == TeacherTurn.conversation_id)
        .where(
            TeacherConversation.teacher_id == asking.teacher_id,
            TeacherConversation.deleted_at.is_(None),
            TeacherTurn.entity_kind == "assessment",
            TeacherTurn.entity_id == assessment_id,
        )
        .order_by(TeacherTurn.created_at, TeacherTurn.id)
        .limit(1)
    )


async def _conversation(session: AsyncSession, asking: Asking, *, start_new: bool = False) -> str:
    """Tìm hội thoại đang chạy của giáo viên này, hoặc mở một hội thoại mới.

    Docstring cũ ở đây viết: *"mở một luồng mới chưa phải là thứ giáo viên xin được. Khi
    nó trở thành một thứ xin được thì đây là hàm duy nhất phải đổi."* Nay nó xin được, và
    đây đúng là hàm đã đổi — thêm một tham số, không thêm một đường thứ hai.

    `start_new` là **duy nhất** đường mở luồng thứ hai. Nói tiếp mà âm thầm mở luồng mới
    nghĩa là trợ lý quên sạch những gì vừa nói, nên mặc định vẫn là dùng lại luồng mới
    nhất, y như trước.

    Args:
        session: Session của database.
        asking: Hội thoại của ai.
        start_new: Mở một luồng mới kể cả khi giáo viên đã có luồng.

    Returns:
        id của nó, dưới dạng string. Không phải cái row: các caller commit giữa các bước
        và `rollback` làm hết hạn các object ORM, nên một row đưa ra từ đây sẽ nổ
        `MissingGreenlet` ở lần đọc attribute tiếp theo.

    Side effects:
        Chèn một row khi giáo viên chưa từng nói gì trước đó, hoặc khi `start_new`.
    """
    for attempt in range(2):
        found = None if start_new else await _latest_conversation(session, asking)
        if found is not None:
            return found

        started = TeacherConversation(teacher_id=asking.teacher_id, started_at=datetime.now(UTC))
        session.add(started)
        try:
            # Commit, không phải flush. Hai request của cùng giáo viên này đến cùng lúc
            # là chuyện thường ngày -- một màn hình đang tải trong lúc họ gõ -- và bên
            # thua hồi lại bằng cách đọc row của bên thắng. Một lần flush để row đó vô
            # hình ở ngoài transaction của chính nó, nên bên thua sẽ không tìm thấy gì và
            # bỏ cuộc: đường hồi phục tồn tại mà không bao giờ chạy. Tìm ra bằng một test
            # bắn hai request một lúc, không phải bằng cách đọc hàm này.
            await session.commit()
        except IntegrityError:
            await session.rollback()
            if attempt:
                raise
            continue
        return started.id

    raise AssertionError("unreachable: the loop returns or raises")


async def _stored_turns(session: AsyncSession, conversation_id: str) -> list[TeacherTurn]:
    """Đọc lại một hội thoại, cũ nhất trước."""
    rows = await session.scalars(
        select(TeacherTurn)
        .where(TeacherTurn.conversation_id == conversation_id)
        .order_by(TeacherTurn.sequence)
    )
    return list(rows)


def _without_text(result: dict) -> dict:
    """Kết quả `read_section` bỏ chữ, giữ dấu đã đọc gì: phần nào, nút nào, tên bài nào."""
    kept = {key: value for key, value in result.items() if key != "text"}
    return {**kept, "elided": True} if "text" in result else kept


def _shrunk(turn: TeacherTurn, latest_outline: int | None, kept_reads: set[int]) -> dict:
    """`tool_result` của một bước đã lưu, như lượt **sau** cần đọc nó (`draft-outline`).

    Hai thứ to được thu lại. Chữ một phần đọc (`teacher_tools._PART_CHARS`, tới mười phần một
    lượt) chỉ giữ khi nó **chưa thành dàn ý** (`kept_reads`): đọc rồi hỏi lại giáo viên thì lượt
    sau viết dàn ý từ chữ ấy, không đọc lại. Đọc **trước** dàn ý mới nhất thì dàn ý đã chở nó --
    chỉ còn dấu *đã đọc gì*. Và một dàn ý đã bị thay chỉ còn số bản: mục của nó không còn là thứ
    giáo viên đang duyệt.
    """
    result = dict(turn.tool_result or {})
    if turn.kind == "tool_result" and turn.tool_name == "read_section":
        return result if turn.sequence in kept_reads else _without_text(result)
    if turn.kind == "outline" and turn.sequence != latest_outline:
        return {"version": result.get("version"), "superseded": True}
    return result


async def _current_titles(session: AsyncSession, turns: list[TeacherTurn]) -> dict[str, str]:
    """Tên **hiện tại** của mọi đề các bước này nhắc tới (ADR-31), một truy vấn cho cả đoạn chat.

    Kết quả một bước ghi tên đề lúc bước ấy chạy. Giáo viên đổi tên rồi thì thẻ cũ, dòng bước cũ và
    lịch sử gửi AGENT phải đọc tên mới -- hai tên cho một đề trên cùng màn hình là hai đề.
    """
    ids: set[str] = set()
    for turn in turns:
        _named_papers(turn.tool_result, ids)
        # Cả đề mà bước **nói về**, có tên hay không: thiếu trong kết quả là đề đã xoá (`_visible`).
        if turn.entity_kind == "assessment" and turn.entity_id:
            ids.add(turn.entity_id)
    if not ids:
        return {}
    rows = await session.execute(
        select(Assessment.id, Assessment.title).where(Assessment.id.in_(ids))
    )
    return {one: title for one, title in rows.all()}


def _named_papers(value: object, into: set[str]) -> None:
    """Gom id của mọi đề mang tên trong một kết quả bước, kể cả lồng trong danh sách. Hàm thuần.

    `list_assessment` trả `assessments: [{assessment_id, title}]`: chỉ nhìn cấp ngoài thì tên lồng
    giữ nguyên tên cũ sau khi giáo viên đổi tên (review code 17/10, plan `backlog-tier-1`).
    """
    if isinstance(value, dict):
        if value.get("assessment_id") and "title" in value:
            into.add(str(value["assessment_id"]))
        for inner in value.values():
            _named_papers(inner, into)
    elif isinstance(value, list):
        for inner in value:
            _named_papers(inner, into)


def _titled(result: dict, titles: dict[str, str]) -> dict:
    """Một kết quả bước mang tên hiện tại của mọi đề nó nhắc tới, ở mọi cấp (ADR-31). Hàm thuần."""

    def renamed(value: object) -> object:
        if isinstance(value, dict):
            out = {key: renamed(inner) for key, inner in value.items()}
            found = titles.get(str(value.get("assessment_id") or ""))
            if found is not None and "title" in value:
                out["title"] = found
            return out
        if isinstance(value, list):
            return [renamed(inner) for inner in value]
        return value

    return renamed(result)


def _as_records(turns: list[TeacherTurn], titles: dict[str, str] | None = None) -> list[TurnRecord]:
    """Biến các bước đã lưu thành phần history mà AGENT đọc.

    Chỉ phần đuôi được gửi đi. Lý do xem ở `_HISTORY_STEPS`, và lưu ý là chỗ bị cắt là
    phần đầu: model cần câu hỏi nó vừa hỏi hơn nhiều so với câu nó hỏi tuần trước.

    Mọi bước đã lưu đều thuộc một lượt **trước** -- hàm này chạy lúc lượt bắt đầu --, nên chữ đã đọc
    và dàn ý đã bị thay được thu lại ở đây (`_shrunk`); bước của lượt đang chạy nằm trong bộ nhớ,
    nguyên vẹn.

    Args:
        turns: Các bước đã lưu, cũ nhất trước.
        titles: Tên hiện tại của các đề (`_current_titles`), để Kriky gọi đề đúng tên giáo viên vừa
            đặt.

    Returns:
        `_HISTORY_STEPS` bước cuối trong số đó, dưới dạng record của contract.
    """
    titles = titles or {}
    outlines = [turn.sequence for turn in turns if turn.kind == "outline"]
    latest_outline = outlines[-1] if outlines else None
    # Chữ đọc sau dàn ý mới nhất còn đang chờ thành dàn ý; giữ tối đa `MOST_QUESTIONS_ASKED` phần
    # mới nhất -- vài lượt đọc liền không có dàn ý không được cộng dồn thành cả cuốn sách.
    unwritten = [
        turn.sequence
        for turn in turns
        if turn.kind == "tool_result"
        and turn.tool_name == "read_section"
        and (latest_outline is None or turn.sequence > latest_outline)
    ]
    kept_reads = set(unwritten[-MOST_QUESTIONS_ASKED:])
    return [
        TurnRecord(
            kind=turn.kind,
            text=turn.text,
            tool_name=turn.tool_name,
            tool_args=turn.tool_args or {},
            tool_result=_titled(_shrunk(turn, latest_outline, kept_reads), titles),
        )
        for turn in turns[-_HISTORY_STEPS:]
    ]


async def _record(
    session: AsyncSession,
    conversation_id: str,
    sequence: int,
    record: TurnRecord,
    *,
    duration_ms: int = 0,
    model_tokens: int = 0,
    choices: list[str] | None = None,
    more_choices: int = 0,
    document_id: str = "",
) -> int:
    """Ghi thêm một bước vào hội thoại rồi commit nó.

    Commit theo từng bước chứ không theo từng lượt, nên một worker chết giữa vòng lặp chỉ
    mất đúng bước nó đang làm chứ không mất cả hội thoại. Đó cũng là thứ thả connection
    lấy từ pool ra trước lần đợi AGENT tiếp theo.

    Đọc vị trí và chèn vào vị trí đó là hai câu lệnh có một khe ở giữa, nên hai request
    của cùng một giáo viên có thể cùng nhắm vào một vị trí. Unique index là bên phân xử,
    và bên thua lấy vị trí trống tiếp theo chứ không nổ: `chat_messages` đặt tiền lệ cho
    cái constraint, còn `student_routes` đặt tiền lệ cho đường hồi phục -- bắt chước đúng
    nửa đầu thì biến một cú double-click bình thường thành một lỗi 500 không có chữ tiếng
    Việt nào trong đó.

    Args:
        session: Session của database.
        conversation_id: Hội thoại nào.
        sequence: Vị trí cần nhắm tới. Chỉ là gợi ý: giá trị trả về mới là chỗ bước đó
            thực sự rơi vào.
        record: Bước đó.
        duration_ms: Lượt gọi model sinh ra nó mất bao lâu.
        model_tokens: Lượt gọi đó tiêu bao nhiêu.
        choices: Các phương án bày ra cùng bước này, nếu nó là một câu hỏi lại. Đi vào
            đây chứ không vào `record` vì `TurnRecord` là payload sang AGENT và model
            không dùng được chúng — y như `duration_ms` ngay trên.
        more_choices: Bao nhiêu phương án nữa đã bị cắt.
        document_id: Chip tài liệu của câu giáo viên này, đã kiểm sở hữu (`draft-from-document`).

    Returns:
        Vị trí sau bước này, thứ caller dùng cho bước tiếp theo.

    Raises:
        IntegrityError: Nếu vị trí đó vẫn bị chiếm sau khi đã đọc lại, và điều đó sẽ có
            nghĩa là một chuyện khác chứ không phải một cuộc đua.

    Side effects:
        Chèn và commit. Rollback một lần khi có đụng độ.
    """
    kind, entity_id = _subject(record.tool_result)

    for attempt in range(2):
        session.add(
            TeacherTurn(
                conversation_id=conversation_id,
                sequence=sequence,
                kind=record.kind,
                text=record.text,
                tool_name=record.tool_name,
                tool_args=dict(record.tool_args),
                tool_result=dict(record.tool_result),
                entity_kind=kind,
                entity_id=entity_id,
                choices=list(choices or []),
                more_choices=more_choices,
                document_id=document_id,
                duration_ms=duration_ms,
                model_tokens=model_tokens,
                created_at=datetime.now(UTC),
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            if attempt:
                raise
            taken = await session.scalar(
                select(func.max(TeacherTurn.sequence)).where(
                    TeacherTurn.conversation_id == conversation_id
                )
            )
            sequence = (taken or 0) + 1
            continue
        return sequence + 1

    raise AssertionError("unreachable: the loop returns or raises")


async def note_action(session: AsyncSession, asking: Asking, record: TurnRecord) -> None:
    """Ghi một hành động của giáo viên vào hội thoại đang chạy của họ.

    Tồn tại cho những quyết định **không** đi qua khung chat. Duyệt và phát hành nằm
    sau một nút và một hộp xác nhận (ADR-05), nên chúng không bao giờ là một bước do
    model đề xuất -- nhưng chúng vẫn thuộc về cùng một dòng thời gian, vì thứ giáo viên
    đọc lại sau một tuần là *đã xảy ra những gì*, không phải *thứ gì đi qua đường nào*.
    ADR-01 còn đòi thẳng điều đó cho việc bỏ duyệt, thao tác duy nhất hạ một state
    xuống.

    Vị trí được tính ở đây chứ không phải ở caller, vì việc xử lý hai request cùng nhắm
    một vị trí nằm trong `_record` và một caller thứ hai tự tính vị trí sẽ là một bản
    sao của luật đó, chờ lệch đi.

    **Đoạn chat nào** là câu hỏi mà nhiều luồng làm cho khó. Không phải đoạn mới nhất:
    giáo viên đang đọc một đoạn cũ, bấm *Duyệt*, rồi sẽ không tìm thấy biên bản ở đâu cả.
    Là đoạn **đã sinh ra đề**, suy từ `entity_id` — xem `conversation_of`. Đề không sinh
    ra từ đoạn nào thì lùi về mới nhất.

    Args:
        session: Session của database. Hàm này commit.
        asking: Ai đang làm.
        record: Bước cần ghi. `tool_result` của nó nên mang một cờ thành công và một
            `assessment_id`, vì đó là thứ `_subject` đọc để liên kết bước này với đề --
            và cũng là thứ quyết định biên bản rơi vào đoạn chat nào.

    Side effects:
        Mở một hội thoại nếu giáo viên chưa có, rồi chèn một bước và commit.
    """
    _, subject = _subject(record.tool_result)
    thread = (await conversation_of(session, asking, subject)) if subject else None
    if thread is None:
        thread = await _conversation(session, asking)
    stored = await _stored_turns(session, thread)
    await _record(session, thread, len(stored), record)


def _client_result(tool_name: str, result: dict) -> dict:
    """`tool_result` như client được xem: chữ một phần đọc (`read_section`) không tới client.

    Một chỗ cho hai đường -- sự kiện bước lúc lượt đang chạy và lượt đọc lại sau F5 -- vì hai
    đường của cùng một bước phải vẽ cùng một dòng (`kriky-writes-every-word`).
    """
    result = dict(result)
    return _without_text(result) if tool_name == "read_section" else result


def _visible(turn: TeacherTurn, titles: dict[str, str] | None = None) -> Turn:
    """Chiếu một bước đã lưu sang đúng thứ client được xem.

    Chữ một phần đọc (`read_section`) không tới client: màn hình không vẽ nó, và mười phần một lượt
    là cả trăm nghìn ký tự đi mỗi lần tải lại đoạn chat. Tên đề là tên hiện tại (`titles`, ADR-31).
    `titles` cũng nói đề nào còn: `_current_titles` gom mọi `entity_id` về đề, nên một đề vắng mặt
    là đề đã xoá (ADR-33). Không có `titles` thì không nói gì về chuyện còn hay mất.
    """
    result = _titled(_client_result(turn.tool_name, turn.tool_result or {}), titles or {})
    gone = (
        titles is not None
        and turn.entity_kind == "assessment"
        and bool(turn.entity_id)
        and turn.entity_id not in titles
    )
    return Turn(
        kind=turn.kind,
        text=turn.text,
        tool_name=turn.tool_name,
        tool_result=result,
        entity_kind=turn.entity_kind,
        entity_id=turn.entity_id,
        choices=list(turn.choices or []),
        more_choices=turn.more_choices,
        model_tokens=turn.model_tokens,
        duration_ms=turn.duration_ms,
        entity_gone=gone,
    )


def _read_back(
    conversation_id: str, stored: "list[TeacherTurn]", titles: dict[str, str] | None = None
) -> "Answered":
    """Dựng câu trả lời cho một lần **đọc lại** một đoạn chat.

    Chỗ duy nhất quyết việc các phương án của một câu hỏi lại có còn được bày ra hay không.
    Chỉ bước **cuối cùng** được chở `choices` lên: một câu hỏi đã được trả lời thì các nút
    của nó không còn nghĩa gì, và bày lại chúng là mời giáo viên trả lời hai lần một câu.

    Args:
        conversation_id: Đoạn nào.
        stored: Mọi bước của đoạn, theo thứ tự.
        titles: Tên hiện tại của các đề (`_current_titles`).

    Returns:
        Câu trả lời. `kind` là "say" và `text` rỗng, vì đọc không phải một lượt.
    """
    last = stored[-1] if stored else None
    return Answered(
        kind="say",
        text="",
        conversation_id=conversation_id,
        choices=list(last.choices or []) if last else [],
        more_choices=last.more_choices if last else 0,
        turns=[_visible(turn, titles) for turn in stored],
    )


async def _rendered(session: AsyncSession, conversation_id: str, since: int) -> list[Turn]:
    """Đọc lại các bước của một lượt, cho câu trả lời báo cáo về lượt đó.

    Đọc từ bảng chứ không dựng ra từ history trong bộ nhớ, vì hai lý do. History giữ cả
    hội thoại -- model cần cái context đó -- nên dựng câu trả lời từ nó thì trả về mọi
    bước cũ như thể chúng vừa mới xảy ra, và một client đem chúng ghép thêm vào sẽ vẽ lại
    cả hội thoại lên trên chính nó. Và cái row đã lưu là chỗ duy nhất chủ thể và cái giá
    của bước đó sống.

    Args:
        session: Session của database.
        conversation_id: Hội thoại nào.
        since: Vị trí đầu tiên thuộc về lượt này.

    Returns:
        Các bước của lượt này, theo thứ tự.
    """
    rows = list(
        await session.scalars(
            select(TeacherTurn)
            .where(TeacherTurn.conversation_id == conversation_id, TeacherTurn.sequence >= since)
            .order_by(TeacherTurn.sequence)
        )
    )
    titles = await _current_titles(session, rows)
    return [_visible(turn, titles) for turn in rows]


class TurnEvent(BaseModel):
    """Một việc vừa xảy ra trong lượt này, đủ để vẽ ngay mà không cần đọc lại database.

    Lượt là một **dãy sự kiện**, không phải một khuôn cố định: harness tiêm context và tool,
    còn model quyết nói lúc nào, tra lúc nào, hỏi lúc nào (ADR-25). Màn hình vẽ theo đúng
    thứ tự nhận được.

    Attributes:
        kind: `say`, `clarify`, `plan`, `step_started`, `step_done`, `step_failed`, `report`,
            `notice` (thông báo hệ thống khi model không có mặt để nói -- ADR-30, ngoại lệ 1) hay
            `done`.
        text: Lời, cho `say`, `clarify`, `report`, `notice` và `done`.
        choices: Phương án của một câu hỏi lại, do `_choices` dựng (ADR-23, T3,
            `unbiased-model-text`), không "Khác".
        more_choices: Bao nhiêu candidate đã bị cắt khỏi `choices`.
        conversation_id: Lượt này nằm trong đoạn chat nào.
        ended_as: Lượt kết thúc bằng nhánh nào -- `say`, `clarify`, `outline` (dàn ý, ADR-29),
            `report`, `notice`, hay `plan` (plan đã chạy mà lượt kể lại chọn im, ADR-25 hậu ký
            22/10/2026). Chỉ có ở sự kiện `done`. Suy nó từ việc `choices` có rỗng hay
            không thì sai ở đúng ca một câu hỏi lại chưa có candidate nào: nó là câu hỏi, mà bị báo
            về như một câu trả lời.
        title: Câu tiếng Việt của một bước, cho ba sự kiện `step_*`.
        detail: Dòng kết quả của một bước, hoặc lý do nó hỏng.
        index: Bước thứ mấy, đếm từ 1.
        total: Plan có bao nhiêu bước. Đây là `n` của `bước k/n`, và nó nói thật được
            chính vì plan có trước khi chạy.
        titles: Tiêu đề của từng bước, chỉ ở sự kiện `plan`. Khối bằng chứng vẽ được cả
            danh sách việc trước khi bước đầu tiên chạy.
        began: Lượt này bắt đầu ở vị trí nào trong hội thoại.
        tool_name: Tool của bước, cho ba sự kiện `step_*` (`kriky-writes-every-word`). FE đặt tên
            bước từ đây bằng đúng bảng nó dùng sau F5, nên tên không đổi lúc lượt xong.
        result: Kết quả của một bước tra cứu ở pha lên plan, cho `step_done`/`step_failed` --
            đúng thứ client đọc lại sau F5 (`_client_result`), nên dòng kết quả cũng không đổi.
            Bước của plan để `None` (lên dây là `null`): dòng của chúng đi trong `detail`. Một
            dict rỗng mặc định thì không phân biệt được hai loại bước (review pha 1,
            `kriky-writes-every-word`).
    """

    kind: str
    text: str = ""
    choices: tuple[str, ...] = ()
    more_choices: int = 0
    conversation_id: str = ""
    ended_as: str = ""
    title: str = ""
    detail: str = ""
    index: int = 0
    total: int = 0
    titles: tuple[str, ...] = ()
    began: int = 0
    tool_name: str = ""
    result: dict[str, object] | None = None


# **Im lặng** bao lâu thì thôi đợi -- không phải trần cho cả khoảng đợi. Đồng hồ được đặt
# lại sau mỗi tiếng chuông, nên một vòng soạn mười câu vẫn đi tới cùng dù mất vài phút, còn
# một worker chết thì bị bỏ sau ngần này giây. Hết hạn thì lượt vẫn kể lại, chỉ là kể một
# cái đề đang soạn dở.
#
# Hệ quả cần nhớ: channel dùng chung cho cả đề, nên chuông của một tab khác cũng gia hạn
# đồng hồ này. Trần thật của một lượt vì thế là trần của client -- và nó phải lớn hơn tổng
# chuỗi kiên nhẫn của BE, nếu không client cắt trước và lượt mất câu kết.
_WAIT_FOR_QUESTIONS_SECONDS = 180.0


def paper_now(result: dict) -> str:
    """Id đề mà **một** kết quả vừa nói tới, hoặc chuỗi rỗng.

    Args:
        result: Thứ một tool vừa trả về.

    Returns:
        Id đề, hoặc rỗng.
    """
    found = result.get("assessment_id")
    return found if isinstance(found, str) else ""


async def _replacement_outcome(session: AsyncSession, paper: str, result: dict) -> dict:
    """Kết quả của một bước thay câu sau khi đợi: đã thay, còn đang soạn, hay câu cũ ở lại.

    Câu cũ ở lại khi câu mới không đạt (`drafting._keep_the_old`). Không nói ra điều đó thì bước
    báo *"đã soạn N/N câu"* và Kriky kể là đã thay -- trong khi đề vẫn là câu cũ (review đợt 5,
    `draft-outline`).

    Args:
        session: Session của database.
        paper: Đề.
        result: Kết quả `replace_question`, đã có ba con số đếm.

    Returns:
        Kết quả đã sửa; dòng kết quả do `plan_outcomes.step_detail` đọc từ nó.
    """
    number = result.get("question_number")
    standing = await session.scalar(
        select(Question.id).where(Question.assessment_id == paper, Question.order_index == number)
    )
    await session.rollback()
    if standing is not None and standing != result.get("replaced_question_id"):
        return {**result, "replaced": True}
    if result.get("still_drafting"):
        return {**result, "replaced": False}
    kept = f"câu {number} giữ nguyên: câu mới soạn không đạt"
    return {**result, "started": False, "replaced": False, "reason": kept}


async def _wait_for_questions(
    request: Request,
    session: AsyncSession,
    settings: Settings,
    assessment_id: str,
    thread: str,
    start: Callable[[], Awaitable[None]] | None = None,
) -> AsyncIterator[TurnEvent]:
    """Nghe chuông tiến độ, thu hoạch, và phát `progress` cho tới khi hết câu đang soạn.

    Đây là nửa thứ hai của điều kiện "pha 2 xong" (ADR-25): plan chạy hết **và** không còn
    câu nào đang soạn. Nửa này mất hàng phút, nên nó chỉ chạy ở cửa SSE.

    Ba điều đáng nói về hình dạng của nó:

    - **Thu hoạch rồi mới đếm**, ở mỗi tiếng chuông. Chuông chỉ nói "có thứ để lấy"; chính
      `harvest` mới đưa câu vào đề. Khung `progress` đầu tiên là ngoại lệ có chủ ý: nó phát
      con số **đang có** ngay khi bắt đầu đợi, để màn hình có một mốc thay vì một khoảng
      trống — nó không khẳng định vừa thu được gì.
    - **Một lần thu cuối, sau vòng lặp.** Chuông không bền: tiếng cuối cùng có thể rơi vào
      khoảnh khắc người nghe đang bận. Không có lần thu ấy thì một đề xong đủ mười câu vẫn
      có thể kết thúc lượt ở `9/10`.
    - **Hết hạn thì vẫn kể.** Một lượt chat không được treo mãi vì một worker chết; nó kể
      lại những gì đang có, và lần quan sát sau sẽ đưa nốt phần còn lại vào đề.

    Args:
        request: Mang theo pool của queue.
        session: Session của database.
        settings: Cho timeout khi đọc kết quả job.
        assessment_id: Đề đang được soạn.
        thread: Đoạn chat, để gắn vào sự kiện.
        start: Việc mở vòng soạn — chạy **sau khi đã subscribe**. Pub/sub không giữ lịch sử,
            nên đẩy job trước là trao cho worker cơ hội nói vào một căn phòng trống.

    Yields:
        `progress` mỗi khi số câu đổi.

    Side effects:
        Ghi câu hỏi vào đề qua `harvest`.
    """
    pool = getattr(request.app.state, "queue_pool", None)

    async with open_bells(pool, assessment_id, _WAIT_FOR_QUESTIONS_SECONDS) as bells:
        # **Trong** khối, nên nó chạy sau khi đã subscribe. Đó là cả lý do `open_bells` là
        # một context manager: thân một async generator không chạy cho tới lần lặp đầu, nên
        # một tham số `start` kiểu cũ im lặng không chạy lần nào khi chưa có chuông để lặp.
        if start is not None:
            await start()

        written, asked_for, running = await count_questions(session, assessment_id)
        if running == 0:
            # Không có gì để đợi: hoặc vòng soạn chưa mở được, hoặc nó đã xong trước cả
            # tiếng chuông đầu tiên. Cả hai đều không phải lỗi.
            return
        yield TurnEvent(kind="progress", index=written, total=asked_for, conversation_id=thread)

        async for _ in bells:
            await harvest(session, pool, settings, assessment_id)
            now, asked_for, running = await count_questions(session, assessment_id)
            if now != written:
                # Chỉ phát khi con số **đổi**. Chuông không phải một bộ đếm: một vị trí thử
                # lại rung thêm một lần cho cùng số thứ tự, và hai tab cùng nghe thì cả hai
                # cùng thu — nên cùng một con số tới hai lần là chuyện thường. Phát lại nó
                # là bắt màn hình nhấp nháy mà không nói thêm điều gì.
                written = now
                yield TurnEvent(
                    kind="progress", index=written, total=asked_for, conversation_id=thread
                )
            if running == 0:
                return

    # Hết kiên nhẫn, hoặc tiếng chuông cuối rơi mất. Thu một lần nữa trước khi đi.
    landed = await harvest(session, pool, settings, assessment_id)
    if landed:
        written, asked_for, _ = await count_questions(session, assessment_id)
        yield TurnEvent(kind="progress", index=written, total=asked_for, conversation_id=thread)


async def _thread_for(session: AsyncSession, asking: Asking, said: "Said") -> str:
    """Tìm ra đoạn chat mà lượt này thuộc về, hoặc mở một đoạn mới.

    Tách khỏi thân lượt vì khoá phải đặt **trước** khi bất cứ thứ gì được ghi, và muốn
    khoá thì phải biết khoá cái gì.

    Args:
        session: Session của database.
        asking: Ai đang hỏi.
        said: Thứ giáo viên vừa gõ, mang theo `conversation_id` nếu có.

    Returns:
        Id của đoạn chat.

    Raises:
        HTTPException: 404 khi id ấy không phải của giáo viên này (ADR-22).
    """
    if said.conversation_id is not None:
        thread = await _owned_conversation(session, asking, said.conversation_id)
        # Một đoạn chat không tồn tại và một đoạn của người khác nhận cùng một câu trả lời
        # (ADR-22). `404` chứ không phải mở hộ một đoạn mới: gõ nhầm id rồi được nói vào
        # một nơi khác là mất câu vừa gõ ở một chỗ không ai đi tìm.
        if thread is None:
            raise HTTPException(status_code=404, detail="không tìm thấy đoạn chat này")
        return thread
    return await _conversation(session, asking, start_new=said.start_new)


async def _hold_the_thread(
    session: AsyncSession, thread: str, stale_seconds: int
) -> datetime | None:
    """Nhận khoá "đoạn chat này đang chạy một lượt", nếu nó đang rảnh.

    **Một câu lệnh, không hai.** Đọc rồi ghi là đúng cuộc đua đang đi sửa: hai tab đọc cùng
    một `None` rồi cùng ghi, và cả hai cùng tin mình giữ khoá. Một `UPDATE ... WHERE` để
    database phân xử, và `rowcount` nói ai thắng.

    Điều kiện quá hạn nằm trong cùng câu lệnh ấy chứ không phải một đường dọn riêng: một
    process chết giữa một lượt không chạy `finally` nào, nên nếu chỉ hỏi `IS NULL` thì đoạn
    chat đó bị chặn vĩnh viễn và không có lệnh nào để gỡ.

    Args:
        session: Session của database.
        thread: Đoạn chat nào.
        stale_seconds: Một khoá cũ hơn mức này coi như đã rơi.

    Returns:
        Mốc vừa ghi -- **thẻ** của khoá này -- hoặc `None` khi đoạn chat đang chạy một lượt
        khác. Thẻ ấy là thứ `_let_go_of_the_thread` cần để nhả đúng khoá của mình.

    Side effects:
        Ghi `running_since` và commit.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=stale_seconds)
    taken = await session.execute(
        update(TeacherConversation)
        .where(
            TeacherConversation.id == thread,
            or_(
                TeacherConversation.running_since.is_(None),
                TeacherConversation.running_since < cutoff,
            ),
        )
        .values(running_since=now)
    )
    await session.commit()
    return now if taken.rowcount else None


async def _let_go_of_the_thread(session: AsyncSession, thread: str, mine: datetime) -> None:
    """Nhả khoá của một đoạn chat, kể cả khi lượt vừa rồi hỏng hoặc bị cắt.

    **`shield=True` là phần chịu lực, không phải một sự cẩn thận thừa.** Cửa SSE chạy trong
    một cancel scope của anyio, và cancel scope của anyio là *level-triggered*: sau khi scope
    đã bị cancel, **mọi** `await` mới bên trong nó raise `CancelledError` ngay. Giáo viên đóng
    tab giữa lượt là đúng ca đó, và lượt nằm trong một `await` gần như suốt thời gian sống của
    nó. Không có shield thì câu `await session.rollback()` ngay dưới đây chết ngay, câu `UPDATE`
    không bao giờ chạy, `except Exception` **không** bắt được (`CancelledError` là
    `BaseException` từ 3.8), và đoạn chat ấy bị chặn suốt `turn_lock_stale_seconds` -- mười
    phút im lặng cho một việc giáo viên làm hàng ngày. Đo được ngày 10/10/2026.

    **Nhả có fencing.** `WHERE running_since = :mine` chứ không chỉ `WHERE id = :thread`: một
    lượt sống lâu hơn cửa sổ quá hạn sẽ thấy khoá của mình đã bị một lượt khác giành đi, và
    một câu nhả vô điều kiện khi đó xoá khoá của người đang giữ -- trả lại đúng hai plan cài
    răng lược mà cả luật này tồn tại để diệt.

    `rollback` trước đã: lượt có thể đã chết giữa một câu lệnh, và một session đang lỗi thì
    không nhận thêm câu nào. Không mất gì khi làm vậy -- mọi bước của một lượt đều đã commit
    xong từ trước: `_record`, `harvest`, `rebrief` và `drafting.start` tự commit cả bốn.

    Nuốt lỗi còn lại là có chủ đích, và nó an toàn vì có đường thứ hai: không nhả được thì
    cửa sổ quá hạn nhả hộ. Ném ra sẽ thay một lượt **đã xong** bằng một lỗi 500.

    Args:
        session: Session của database.
        thread: Đoạn chat nào.
        mine: Thẻ `_hold_the_thread` trả về, tức mốc chính lượt này đã ghi.

    Side effects:
        Rollback, rồi ghi `running_since = NULL` và commit -- trong một scope không bị cancel.
    """
    with anyio.CancelScope(shield=True):
        try:
            await session.rollback()
            await session.execute(
                update(TeacherConversation)
                .where(
                    TeacherConversation.id == thread,
                    TeacherConversation.running_since == mine,
                )
                .values(running_since=None)
            )
            await session.commit()
        except Exception:  # noqa: BLE001 -- xem docstring
            logger.exception("could not release the turn lock on %s", thread)


async def run_turn(
    said: "Said",
    request: Request,
    teacher: Teacher,
    session: AsyncSession,
    settings: Settings,
    watching: bool = False,
) -> AsyncIterator[TurnEvent]:
    """Đi một lượt, sau khi đã giữ được đoạn chat cho riêng lượt ấy.

    **Một đoạn chat chạy nhiều nhất một lượt** (ADR-25). Hai tab cùng một đoạn là chuyện
    bình thường, và không có khoá thì chúng chen vào nhau: dãy bước của hai plan trộn lẫn
    theo thời gian chứ không theo lượt, và `create_draft` -- thứ không idempotent -- để lại
    hai đề nháp trống, một cái không bao giờ được soạn.

    Khoá đặt **trước** khi câu giáo viên vừa gõ được ghi xuống. Ngược lại thì một lượt bị từ
    chối vẫn để lại một hàng `kind="teacher"` mồ côi, và một lần F5 dựng nó lại thành một câu
    hỏi không có câu trả lời nào.

    Args:
        said: Thứ giáo viên vừa gõ.
        request: Mang theo pool của queue.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database mà mọi tool chạy trên đó.
        settings: Cung cấp ngân sách của pha 1 và cửa sổ quá hạn của khoá.
        watching: Có ai đang xem không -- xem `_go`.

    Yields:
        Từng `TurnEvent` theo thứ tự xảy ra. Sự kiện cuối luôn là `done`.

    Raises:
        HTTPException: 404 khi đoạn chat không phải của giáo viên này (ADR-22), 409 khi đoạn
            ấy đang chạy một lượt khác, 503 khi không với tới được AGENT chút nào.

    Side effects:
        Giữ rồi nhả khoá của đoạn chat; mọi thứ khác xem `_go`.
    """
    asking = Asking.of(teacher)
    thread = await _thread_for(session, asking, said)
    mine = await _hold_the_thread(session, thread, settings.turn_lock_stale_seconds)
    if mine is None:
        raise HTTPException(status_code=409, detail=ALREADY_RUNNING)
    try:
        async for event in _go(said, request, session, settings, thread, asking, watching):
            yield event
    finally:
        await _let_go_of_the_thread(session, thread, mine)


async def _go(
    said: "Said",
    request: Request,
    session: AsyncSession,
    settings: Settings,
    thread: str,
    asking: Asking,
    watching: bool = False,
) -> AsyncIterator[TurnEvent]:
    """Đi một lượt của giáo viên, phát ra từng việc ngay khi nó xảy ra.

    Hai pha (ADR-25). **Pha 1 lên plan**: model tra cứu bằng tool đọc, hỏi lại khi thiếu dữ
    kiện, và kết thúc bằng một câu nói, một câu hỏi lại, hoặc một plan. **Pha 2 thực hiện
    plan**: BE chạy từng bước ghi theo thứ tự, dừng ở bước đầu tiên hỏng, rồi nhờ model kể
    lại kết quả.

    Ranh giới pha là cấu trúc chứ không phải một lời dặn: pha 1 được cấp một catalog **không
    có tool ghi nào**, nên một câu hỏi lại không thể bỏ lại việc đã làm dở. Trước ADR-25 thì
    chuyện ấy xảy ra được, và database còn một đề rỗng sinh ra đúng theo đường đó.

    Đây là generator chứ không phải một hàm trả về một lần, vì cùng một lượt đi ra **hai
    cửa**: `POST` rút cạn nó rồi trả một `Answered`, còn đường SSE forward từng sự kiện. Một
    bản cài đặt, hai cửa -- hai bản sẽ trôi dạt khỏi nhau ở đúng chỗ khó thấy nhất.

    Args:
        said: Thứ giáo viên vừa gõ.
        request: Mang theo pool của queue.
        session: Session của database mà mọi tool chạy trên đó.
        settings: Cung cấp `max_tool_steps` và ngân sách thời gian của pha 1.
        thread: Đoạn chat đã tìm ra và đã giữ khoá -- xem `run_turn`.
        asking: Ai đang hỏi.
        watching: Có ai đang xem không. True thì lượt **đợi** các câu hỏi về trước khi để
            model kể lại, và phát `progress` mỗi lần có thêm câu. Cửa `POST` để False: nó
            rút cạn generator trong một request, và một request đứng chờ hàng phút sẽ bị
            cắt ở đâu đó giữa đường.

    Yields:
        Từng `TurnEvent` theo thứ tự xảy ra. Sự kiện cuối luôn là `done`.

    Raises:
        HTTPException: 503 khi không với tới được AGENT chút nào.

    Side effects:
        Ghi mọi bước của lượt vào hội thoại và commit từng bước; chạy các tool.
    """
    planning = catalog_for(asking, PHASE_PLAN)
    working = catalog_for(asking, PHASE_WORK)

    stored = await _stored_turns(session, thread)
    # Vị trí kế tiếp đọc từ **số thứ tự lớn nhất**, không từ số dòng. Hai con số ấy chỉ bằng
    # nhau khi dãy liền mạch từ 0, và một dãy không liền mạch thì `began` tụt lại phía sau:
    # câu trả lời của lượt này sẽ chở theo mấy dòng của lượt trước, client ghép thêm vào
    # những dòng nó đã vẽ, và cùng một câu hiện hai lần. Đo thấy trên trình duyệt thật.
    position = stored[-1].sequence + 1 if stored else 0
    began = position

    history = _as_records(stored, await _current_titles(session, stored))
    history.append(TurnRecord(kind="teacher", text=said.text))
    # Chip đang đính, khi nó thuộc giáo viên và đã sẵn sàng; không thì như chưa đính
    # (`draft-from-document`). Chip của câu này, khi nó là của giáo viên -- **kể cả** khi tài liệu
    # còn đang xử lý: lưu nó cùng câu thì lượt sau dùng được khi sách đã sẵn sàng (review B6).
    owned = await owned_document(session, asking, said.document_id or "")
    position = await _record(
        session, thread, position, history[-1], document_id=owned.id if owned else ""
    )
    if owned is None and not said.document_id:
        # Không có chip ở câu này: đoạn chat vẫn nói về chip **gần nhất** của nó, đọc từ
        # database chứ không từ cửa sổ `_HISTORY_STEPS` -- một đoạn chat dài không được
        # quên cuốn sách giữa chừng (review B4, `draft-from-document`).
        # Có chip mà chip không dùng được (chưa sẵn sàng, không phải của mình) thì **không** lùi về
        # chip cũ: giáo viên vừa chỉ một cuốn khác, soạn từ cuốn trước là soạn sai sách.
        owned = await owned_document(session, asking, await _last_chip(session, thread))
    attached = (
        AttachedDocument(
            document_id=owned.id,
            filename=owned.filename,
            state=believed_state(owned, settings.document_stale_after_seconds),
        )
        if owned
        else None
    )
    # Gắn với một cuốn sách **sẵn sàng**: tool mục lục hiện ra và `document_id` thành bắt buộc.
    # Chưa sẵn sàng thì không -- chưa có mục lục nào để đọc, AGENT được báo để nói ra điều ấy.
    bound = attached is not None and attached.state == DocumentState.READY.value
    if bound or await _read_documents_before(session, thread):
        planning = catalog_for(asking, PHASE_PLAN, documents=True, bound=bound)
        working = catalog_for(asking, PHASE_WORK, documents=True, bound=bound)
    if attached is not None and not bound:
        # Chip có mà chưa dùng được (đang xử lý, hỏng): lời dặn *đừng soạn không sách* không giữ
        # được model, nên `create_draft` **không có mặt** lượt này -- thứ không nhìn thấy thì không
        # nêu được (review B7, `draft-from-document`). Soạn thêm câu cho đề đã có vẫn được.
        working = tuple(spec for spec in working if spec.name != "create_draft")

    # Câu hỏi về một dòng mà lượt trước để ngỏ vẫn là câu hỏi về dòng ấy (review T3,
    # `unbiased-model-text`): chữ model viết không bao giờ thành nút chỉ vì lượt này chưa gọi tool
    # nào.
    in_play = _rows_in_play(stored, said.text)
    offered, offered_more = _offered(in_play)
    offered_named: dict[str, str] = _named(in_play)
    deadline = asyncio.get_running_loop().time() + settings.turn_budget_seconds
    formula_room = MOST_FORMULA_WAITS * settings.formula_wait_seconds
    plan: tuple[PlanStep, ...] = ()
    # Trần bước **động** (`draft-outline`): mỗi phần đọc `read_section` báo cho lượt thêm một bước
    # và `read_step_seconds` giây, tới mười phần.
    allowed, taken, granted = settings.max_tool_steps, 0, 0
    # Dàn ý đã xem mà plan lượt này soạn theo (ADR-29); `guard_drafting` tìm nó.
    outline: dict | None = None

    # ---------------------------------------------------------------- pha 1: lên plan
    # Thông báo cho mức trần khi bước cuối là một plan bị từ chối: nói đúng chỗ vướng thay cho câu
    # trần chung (review pha 5, `kriky-writes-every-word`). Và lý do từ chối lần trước: model nghe
    # cùng một lý do hai lần liền mà vẫn nêu lại plan ấy thì nó đang kẹt -- thử tay 17/10/2026 thấy
    # nó nêu tám lần, tám lần gọi model cho cùng một câu thông báo. Lần thứ hai là dừng.
    stuck = ""
    refused = ""
    outlines_refused = 0
    # Token của những lượt gọi model không thành dòng nào (dàn ý hay plan bị trả về): chúng vẫn
    # tốn, nên cộng vào dòng được ghi kế tiếp thay vì mất khỏi sổ (review đợt 3, plan
    # `backlog-tier-1`).
    owed = 0
    while taken < allowed:
        taken += 1
        if asyncio.get_running_loop().time() >= deadline:
            # Mức trần số bước, một mình nó, không phải một lời hứa về thời gian đợi: tám
            # bước nhân với timeout của một job là hơn chín phút, và một browser hay một
            # proxy sẽ cắt connection từ rất lâu trước đó trong khi BE vẫn ghi log là
            # thành công. Đây mới là mức chặn mà giáo viên thực sự cảm thấy.
            logger.warning("turn budget spent for %s", asking.teacher_code)
            break

        started = time.monotonic()
        try:
            step = await _ask_agent(
                request, settings, asking.full_name, planning, working, history, attached
            )
        except AgentError as unreachable:
            logger.warning("agent unreachable for %s: %s", asking.teacher_code, unreachable)
            raise HTTPException(status_code=503, detail=AGENT_UNAVAILABLE) from unreachable

        spent_ms = int((time.monotonic() - started) * 1000)

        if step.kind in {"say", "ask_clarify"}:
            # Các phương án chỉ đi cùng một **câu hỏi lại**. Bản đầu gửi chúng cho cả `say`,
            # và ca đó có thật: giáo viên hỏi *"lớp 12 thế nào"*, `list_class` trả hai
            # candidate, rồi model **nói** chứ không hỏi. Một lời thông báo mang theo hai cái
            # nút thì màn hình dựng nó thành thẻ hỏi lại, gấp bong bóng thật đi, và bấm một
            # nút gửi `"12A (3 học sinh)"` đi như một câu của giáo viên. Đường live đã sai
            # như vậy từ trước; từ khi có cột trong database thì nó còn sống qua cả F5 — nên
            # chỗ chặn phải là đây, nơi duy nhất biết `step.kind`.
            asking_back = step.kind == "ask_clarify"
            asked_text, asked_choices, several = _questions_of(step, bool(offered), offered_named)
            # `unbiased-model-text` T3: câu hỏi về một dòng giữ nhãn BE, câu hỏi về tham số lấy chữ
            # model đề xuất -- xem `_choices`. "Khác" do FE vẽ, không nằm trong nút.
            buttons = _choices(asked_choices, offered, offered_named) if asking_back else []
            # Model không trả lời được, nên AGENT nói một câu hệ thống (ADR-30, ngoại lệ 1): lưu
            # thành `notice`, không thành lời Kriky.
            spoken = "notice" if step.notice and not asking_back else "assistant"
            history.append(
                TurnRecord(
                    kind=spoken,
                    text=asked_text,
                    tool_result={"questions": several} if several else {},
                )
            )
            position = await _record(
                session,
                thread,
                position,
                history[-1],
                duration_ms=spent_ms,
                model_tokens=step.model_tokens + owed,
                choices=buttons,
                more_choices=offered_more if asking_back else 0,
            )
            if asking_back and offered and asked_choices:
                # Câu hỏi về một dòng: bao nhiêu chữ model viết khớp đúng một dòng, tức được đưa
                # lên đầu; phần còn lại bị bỏ, nút vẫn là mọi nhãn BE.
                logger.info(
                    "%d of %d model-written choice(s) named a row for %s",
                    sum(_spaced(one) in offered_named for one in asked_choices),
                    len(asked_choices),
                    asking.teacher_code,
                )
            yield TurnEvent(
                kind="clarify" if asking_back else "notice" if spoken == "notice" else "say",
                text=asked_text,
                choices=tuple(buttons),
                more_choices=offered_more if asking_back else 0,
                conversation_id=thread,
            )
            if began == 0:
                await _name_the_thread(session, request, settings, thread, said.text)
            yield TurnEvent(
                kind="done",
                text=asked_text,
                choices=tuple(buttons),
                more_choices=offered_more if asking_back else 0,
                conversation_id=thread,
                ended_as="clarify" if asking_back else "notice" if spoken == "notice" else "say",
                began=began,
            )
            return

        if step.kind == "outline":
            # ADR-29, ADR-30: BE kiểm các mục (không kiểm lời Kriky), lưu rồi mới in
            # -- các mục là thứ các job sẽ nhận. Dàn ý hỏng thì trả lý do cho model như một kết quả
            # tool, để nó sửa trong cùng lượt; **không lưu**: giáo viên chưa thấy gì, và một lời từ
            # chối nội bộ không phải một bước để vẽ lên khối bằng chứng sau F5.
            shown = await outline_turn(session, asking, thread, step, history, attached)
            if isinstance(shown, dict):
                logger.info("refused an outline for %s: %s", asking.teacher_code, shown)
                history.append(
                    TurnRecord(kind="tool_result", tool_name="outline", tool_result=shown)
                )
                # Cùng mẫu với plan bị từ chối: một lý do đã về model mà nó vẫn nêu lại dàn ý ấy
                # thì nó đang kẹt -- dừng ở lần hai (plan `backlog-tier-1`).
                stuck = OUTLINE_REFUSED
                owed += step.model_tokens
                reason = str(shown.get("error", ""))
                if reason == refused:
                    logger.warning("same outline refusal twice for %s", asking.teacher_code)
                    break
                # Lý do đổi mỗi lần cũng là kẹt: thử tay 17/10/2026 (pha 6), lời trả về xen kẽ
                # *mục 2* rồi *mục 3* nên luật *cùng lý do hai lần* không bắt, bảy lượt gọi model,
                # mỗi lượt gần 40 nghìn token. Lần thứ ba bị trả về là dừng, lý do gì cũng vậy.
                outlines_refused += 1
                if outlines_refused >= _MOST_OUTLINE_REFUSALS:
                    logger.warning(
                        "outline refused %d times for %s", outlines_refused, asking.teacher_code
                    )
                    break
                refused = reason
                continue
            history.append(shown)
            position = await _record(
                session,
                thread,
                position,
                history[-1],
                duration_ms=spent_ms,
                model_tokens=step.model_tokens + owed,
            )
            yield TurnEvent(kind="say", text=shown.text, conversation_id=thread)
            if began == 0:
                await _name_the_thread(session, request, settings, thread, said.text)
            yield TurnEvent(
                kind="done",
                text=shown.text,
                conversation_id=thread,
                ended_as="outline",
                began=began,
            )
            return

        if step.kind == "plan":
            if bound and attached is not None and not _read_other_books(history, attached):
                # Tham số tài liệu BE biết mà không phải đoán -- điền trước khi kiểm
                # (`draft-from-document`).
                step = step.model_copy(
                    update={"steps": await bind_book(step.steps, attached.document_id)}
                )
            # Cổng duyệt của ADR-29 **trước** `vet_plan`: nó điền các tham số BE biết từ dàn ý,
            # và `vet_plan` từ chối một plan thiếu tham số. Không có dàn ý đã xem thì lời từ chối
            # về với model như một kết quả tool -- việc đúng là nêu dàn ý, ngay trong lượt này.
            guarded = await guard_drafting(session, thread, began, step.steps)
            if isinstance(guarded, str):
                logger.info("held back a drafting plan for %s: %s", asking.teacher_code, guarded)
                history.append(
                    TurnRecord(kind="tool_result", tool_name="plan", tool_result={"error": guarded})
                )
                stuck = PLAN_REFUSED
                owed += step.model_tokens
                if guarded == refused:
                    logger.warning("same drafting refusal twice for %s", asking.teacher_code)
                    break
                refused = guarded
                continue
            step = step.model_copy(update={"steps": guarded[0]})
            outline = guarded[1]
            wrong = vet_plan(step.steps, working)
            if wrong is None:
                plan = step.steps
                if step.text:
                    history.append(TurnRecord(kind="assistant", text=step.text))
                    position = await _record(
                        session,
                        thread,
                        position,
                        history[-1],
                        duration_ms=spent_ms,
                        model_tokens=step.model_tokens + owed,
                    )
                    owed = 0
                    yield TurnEvent(kind="say", text=step.text, conversation_id=thread)

                # Plan được **lưu** trước khi phát đi. `bước k/n` phải dựng lại được sau
                # một lần F5, và một con số không có chỗ nào lưu là một con số chỉ đúng
                # chừng nào không ai tải lại trang. Các tiêu đề đi cùng, vì khối bằng
                # chứng vẽ cả danh sách việc trước khi bước đầu tiên chạy.
                history.append(
                    TurnRecord(
                        kind="plan",
                        tool_result={
                            "steps": [one.title for one in plan],
                            "total": len(plan),
                        },
                    )
                )
                # Plan không kèm lời thì token của lượt nêu nó nằm ở đây, không thì đã ở lời trên.
                position = await _record(
                    session,
                    thread,
                    position,
                    history[-1],
                    model_tokens=owed + (0 if step.text else step.model_tokens),
                )
                owed = 0
                yield TurnEvent(
                    kind="plan",
                    total=len(plan),
                    conversation_id=thread,
                    titles=tuple(one.title for one in plan),
                )
                break

            # Plan hỏng thì **không bước nào chạy**, và lý do về model như một kết quả tool -- model
            # sửa plan, hay nói với giáo viên chỗ vướng, trong cùng lượt (ADR-30: BE không nói thay
            # Kriky). Trần bước vẫn là lưới cuối.
            logger.warning("refused a plan for %s: %s", asking.teacher_code, wrong)
            why = wrong
            stuck = PLAN_REFUSED
            owed += step.model_tokens
            if bound and attached is not None and "create_draft" in wrong:
                why = f"{wrong}; {_BOOK_SCOPE_MISSING.format(filename=attached.filename)}"
                stuck = BOOK_SCOPE_MISSING.format(filename=attached.filename)
            elif attached is not None and not bound and "create_draft" in wrong:
                why = f"{wrong}; {_BOOK_NOT_READY.format(filename=attached.filename)}"
                stuck = BOOK_NOT_READY.format(filename=attached.filename)
            history.append(
                TurnRecord(kind="tool_result", tool_name="plan", tool_result={"error": why})
            )
            if why == refused:
                logger.warning("same plan refusal twice for %s", asking.teacher_code)
                break
            refused = why
            continue

        stuck = ""
        refused = ""
        history.append(
            TurnRecord(kind="tool_call", tool_name=step.tool_name, tool_args=step.tool_args)
        )
        position = await _record(
            session,
            thread,
            position,
            history[-1],
            duration_ms=spent_ms,
            model_tokens=step.model_tokens + owed,
        )
        owed = 0
        # Bước tra cứu cũng hiện **lúc đang chạy** (`kriky-writes-every-word`): đọc sách mất mười
        # mấy giây, và trước đây màn hình đứng im suốt lúc ấy rồi bật ra cả khối khi lượt xong.
        # Không `index`/`total`: `bước k/n` đếm bước của plan (ADR-25), và plan chưa có.
        yield TurnEvent(kind="step_started", tool_name=step.tool_name, conversation_id=thread)

        try:
            result = await execute(
                session,
                asking,
                step.tool_name,
                step.tool_args,
                pool=getattr(request.app.state, "queue_pool", None),
                settings=settings,
                phase=PHASE_PLAN,
                conversation_id=thread,
            )
        except UnknownTool:
            # Trả về cho model dưới dạng dữ liệu, không phải dưới dạng một exception. Cách
            # hồi lại là để nó đọc lời từ chối rồi chọn lại trong đúng cái catalog nó đã
            # được đưa.
            #
            # Hai lời từ chối, không một. Từ Pha C model **thấy** mô tả của các tool ghi, để
            # nêu được chúng trong plan. Bảo nó rằng `create_draft` không tồn tại, ngay sau
            # khi nó vừa đọc mô tả của `create_draft`, là dạy nó một điều sai: kết luận hợp
            # lý nhất là "hệ thống này không tạo đề được", và nó sẽ nói câu đó với giáo viên
            # thay vì sửa thành một plan.
            logger.info("refused tool %r for %s", step.tool_name, asking.teacher_code)
            result = {
                "error": (
                    f"{step.tool_name} chỉ nêu được trong plan, không gọi ngay"
                    if step.tool_name in {spec.name for spec in working}
                    else f"không có tool nào tên {step.tool_name}"
                ),
                # Dòng ✕ in `said` trước `error`: tên tool là chữ cho model (review code pha 5).
                "said": _SAID_NOT_NOW,
            }
        except Exception:
            # Mọi sự cố khác cũng vậy, và cũng vì đúng lý do đó. Một tool hỏng không phải
            # là trợ lý hỏng: model có thể nói "mình chưa tra được" và giáo viên có thể
            # hỏi chuyện khác, và đó là một lượt tốt hơn một lỗi 500 không có chữ tiếng
            # Việt nào trong đó.
            logger.exception("tool %r failed for %s", step.tool_name, asking.teacher_code)
            result = {"error": f"tool {step.tool_name} chạy không xong", "said": _SAID_BROKE}
        finally:
            # Thả connection ra giữa các bước. Không có dòng này thì một session giữ một
            # connection lấy từ pool -- và một transaction Postgres nằm không -- xuyên qua
            # mọi lần đợi `run_task` trong cả lượt.
            await session.rollback()

        # Thay hẳn, không gộp vào. Giữ lại candidate của tool trước nghĩa là một câu hỏi
        # về chuyện khác đến nơi mà vẫn còn dính chúng.
        # Giờ chờ `services/document` đọc công thức (`formulas-on-demand`) là giờ của chính bước
        # đọc ấy, không phải giờ model loay hoay: lượt được cộng đúng chừng ấy. Gỡ ra trước khi
        # kết quả vào lịch sử -- model và database không thấy nó.
        # Có trần tổng: mỗi lần đọc thiếu công thức có thể chờ trọn `formula_wait_seconds`, và một
        # model đọc lại mãi không được kéo lượt quá khoá của nó (review pha 3).
        waited = min(float(result.pop(FORMULA_SECONDS, 0) or 0), formula_room)
        formula_room -= waited
        deadline += waited
        offered, offered_more = _offered(result)
        offered_named = _named(result)
        history.append(TurnRecord(kind="tool_result", tool_name=step.tool_name, tool_result=result))
        more = read_allowance(step.tool_name, result, granted)
        if more:
            granted += more
            allowed += more
            deadline += more * settings.read_step_seconds
        if step.tool_name in _DOCUMENT_READS:
            # Không có chip mà model vừa mở thư viện: từ bước sau, tool đọc mục lục và tham số tài
            # liệu của `create_draft` mới hiện ra (`draft-from-document`) -- trước đó chúng chỉ mời
            # hỏi thừa. `bound` đi theo: đọc mục lục giữa lượt -- đúng luồng skill dặn -- không được
            # làm tham số tài liệu thành tuỳ chọn trở lại (review B7).
            planning = catalog_for(asking, PHASE_PLAN, documents=True, bound=bound)
            working = catalog_for(asking, PHASE_WORK, documents=True, bound=bound)
        position = await _record(session, thread, position, history[-1])
        # Phát **sau** khi đã ghi, như bước của plan: F5 ngay sau đó phải cho ra đúng dòng này.
        yield TurnEvent(
            kind="step_failed" if went_wrong(result) else "step_done",
            tool_name=step.tool_name,
            result=_client_result(step.tool_name, result),
            conversation_id=thread,
        )

    if not plan:
        # Mức trần. Chạm tới, không phải đâm vào: giáo viên nhận được một câu gọi tên
        # nguyên nhân và gợi ý đúng một việc có ích.
        if not stuck:
            logger.warning("tool loop hit %d steps for %s", allowed, asking.teacher_code)
        history.append(TurnRecord(kind="notice", text=stuck or CEILING_REACHED))
        await _record(session, thread, position, history[-1], model_tokens=owed)
        yield TurnEvent(kind="notice", text=history[-1].text, conversation_id=thread)
        if began == 0:
            await _name_the_thread(session, request, settings, thread, said.text)
        yield TurnEvent(
            kind="done",
            text=history[-1].text,
            conversation_id=thread,
            ended_as="notice",
            began=began,
        )
        return

    # ------------------------------------------------------------ pha 2: chạy plan
    done: list[dict] = []
    for index, step_of_plan in enumerate(plan, start=1):
        try:
            args = resolve_args(step_of_plan.args, done)
        except Unresolvable as missing:
            # `str(missing)` gọi tên field và trích nguyên văn cú pháp tham chiếu --
            # "bước 1 trả về assessment_id rỗng". Đó là chữ để một người sửa lỗi đọc trong
            # log, không phải chữ để giáo viên đọc trên màn hình, và nó cũng không được đi
            # vào prompt của lời kể: model sẽ nhắc lại nguyên văn.
            logger.warning("step %d of a plan could not resolve: %s", index, missing)
            # Ghi cả bước này vào lịch sử, như mọi bước khác: không có dòng nào thì `last_plan`
            # (lượt kể lại, ADR-25 hậu ký 22/10/2026) đọc nó thành *không chạy* thay vì *hỏng*.
            history.append(
                # Không chở tham số chưa ghép (`{1.assessment_id}`): model đọc lại dòng này sau.
                TurnRecord(kind="tool_call", tool_name=step_of_plan.tool_name, tool_args={})
            )
            position = await _record(session, thread, position, history[-1])
            history.append(
                TurnRecord(
                    kind="tool_result",
                    tool_name=step_of_plan.tool_name,
                    tool_result={
                        "error": "bước này cần dữ liệu từ bước trước mà bước ấy không trả về",
                        "said": COULD_NOT_CARRY_OVER,
                        "carried": False,
                    },
                )
            )
            position = await _record(session, thread, position, history[-1])
            yield TurnEvent(
                kind="step_failed",
                title=step_of_plan.title,
                tool_name=step_of_plan.tool_name,
                detail=COULD_NOT_CARRY_OVER,
                index=index,
                total=len(plan),
                conversation_id=thread,
            )
            break

        # Chỉ những thứ tool thật sự nhận. Một tham số lạ đã được `vet_plan` bỏ qua, nhưng
        # nó vẫn nằm trong `args` cho tới đây, và ghi nó vào lịch sử là dạy model rằng lần
        # sau cứ gửi tiếp.
        known = {spec.name: spec for spec in working}.get(step_of_plan.tool_name)
        if known is not None:
            args = {key: value for key, value in args.items() if key in known.arguments}

        history.append(
            TurnRecord(kind="tool_call", tool_name=step_of_plan.tool_name, tool_args=args)
        )
        position = await _record(session, thread, position, history[-1])
        # Phát **sau** khi đã ghi. Một sự kiện đi trước dòng của nó trong bảng nghĩa là một
        # lần F5 ngay sau đó cho ra ít hơn thứ vừa xem -- và màn hình đã hứa dựng lại được
        # đúng những gì nó đang hiện.
        yield TurnEvent(
            kind="step_started",
            title=step_of_plan.title,
            tool_name=step_of_plan.tool_name,
            index=index,
            total=len(plan),
            conversation_id=thread,
        )

        # Bước này sắp mở một vòng soạn thì **mở tai trước đã**. Pub/sub của Redis không giữ
        # lịch sử: job chạy xong trước khi ai subscribe thì tiếng chuông của nó rơi vào một
        # căn phòng trống, và trên máy dev không có API key thì một câu "soạn xong" trong vài
        # micro-giây — mất **mọi** tiếng chuông, khối bước đứng im trọn ba phút rồi mới kể.
        # ADR-25 nói thẳng thứ tự này; `listen_for_progress(start=...)` tồn tại để nó nằm
        # trong một hàm chứ không nằm trong trí nhớ người viết. Review Pha F bắt được rằng
        # đường thật chưa dùng nó.
        #
        # Biết trước được vì `start_drafting` nhận đúng cái id đề trong tham số của nó.
        # Thay một câu (`draft-outline`) cũng mở một vòng soạn: một job, một tiếng chuông.
        opening_a_round = watching and step_of_plan.tool_name in _DRAFTING_TOOLS
        paper = args.get("assessment_id", "") if opening_a_round else ""
        held: dict[str, dict] = {}

        async def run_the_step(
            held: dict[str, dict] = held,
            step_of_plan: PlanStep = step_of_plan,
            args: dict[str, str] = args,
            index: int = index,
        ) -> None:
            # Mọi thứ của vòng lặp đi vào qua tham số mặc định. Closure bắt **biến**, không
            # bắt giá trị, nên một coroutine dựng ở vòng này mà chạy ở vòng sau sẽ chạy với
            # bước của vòng sau -- ở đây nó luôn chạy ngay, nhưng luật thì không nên dựa vào
            # một thứ "luôn đúng hôm nay".
            try:
                held["result"] = await execute(
                    session,
                    asking,
                    step_of_plan.tool_name,
                    args,
                    pool=getattr(request.app.state, "queue_pool", None),
                    settings=settings,
                    phase=PHASE_WORK,
                    outline=outline if step_of_plan.tool_name in _DRAFTING_TOOLS else None,
                    conversation_id=thread,
                )
            except UnknownTool:
                held["result"] = {
                    "error": f"không có tool nào tên {step_of_plan.tool_name}",
                    "said": _SAID_NOT_NOW,
                }
            except Exception:
                logger.exception("step %d of a plan failed for %s", index, asking.teacher_code)
                held["result"] = {"error": f"bước {index} chạy không xong"}
            finally:
                await session.rollback()

        if paper:
            # Một khối: subscribe → chạy bước (đẩy job) → nghe chuông → thu hoạch. Các câu
            # đang được viết trong lúc bước này vẫn **đang mở**, và ADR-25 nói số câu là tiến
            # độ bên trong MỘT bước, không phải một con số thứ hai ở đâu khác.
            async for event in _wait_for_questions(
                request, session, settings, paper, thread, start=run_the_step
            ):
                yield event
            result = held.get("result", {"error": f"bước {index} chạy không xong"})
            if not went_wrong(result):
                # `count_questions` **thả connection** khi đếm xong. An toàn ở đây vì mọi
                # thứ trước nó đã commit (`_record` và `harvest` tự commit cả hai) -- nhưng
                # một caller tương lai có việc chưa commit thì sẽ mất nó, nên đừng gọi hàm
                # ấy giữa một chuỗi ghi.
                counted_now = await count_questions(session, paper)

                # Và ba con số ấy đi **vào chính kết quả của bước**, vài dòng trước `_record`.
                # Lý do: `_start_drafting` chỉ trả `started/queued/assessment_id` — không một
                # con số nào — nên màn hình không dựng nổi thẻ kết quả từ nó, và một lượt soạn
                # đề **thành công** kết thúc không có thẻ nào, tức không có cửa nào vào đề vừa
                # soạn. Làm giàu ở đây chứ không ở FE vì FE không được quyết luật; và làm giàu
                # **trước** khi ghi row chứ không sau, vì ghi sau thì SSE thấy con số còn một
                # lần F5 thì không, và hai đường của cùng một lượt sẽ nói hai chuyện.
                written_now, asked_now, running_now = counted_now
                result = {
                    **result,
                    "written": written_now,
                    "asked_for": asked_now,
                    "still_drafting": running_now,
                }
                if step_of_plan.tool_name == "replace_question":
                    result = await _replacement_outcome(session, paper, result)
        else:
            await run_the_step()
            result = held.get("result", {"error": f"bước {index} chạy không xong"})

        history.append(
            TurnRecord(kind="tool_result", tool_name=step_of_plan.tool_name, tool_result=result)
        )
        position = await _record(session, thread, position, history[-1])
        done.append(result)

        broke = went_wrong(result)
        # Một luật cho cả dòng trên màn hình lúc chạy lẫn dòng `last_plan` kể lại sau đó.
        detail = step_detail(step_of_plan.tool_name, result)

        yield TurnEvent(
            kind="step_failed" if broke else "step_done",
            title=step_of_plan.title,
            tool_name=step_of_plan.tool_name,
            detail=detail,
            index=index,
            total=len(plan),
            conversation_id=thread,
        )
        if broke:
            # Dừng plan. Chạy tiếp một bước dựa trên một bước vừa hỏng là làm việc trên
            # một thế giới không còn như plan tưởng.
            break

    # ------------------------------------------------------------ lượt kể lại
    #
    # Việc **đợi** nằm trong vòng lặp trên, ở đúng bước đã mở nó. Chỗ này chỉ hỏi model thêm một
    # lần, trên **cả hai** cửa (ADR-25, hậu ký 22/10/2026): tiến độ soạn do `last_plan` đếm lại lúc
    # model hỏi, không do BE dựng sẵn.
    telling, failed = await _tell_after_plan(request, session, settings, asking, thread, history)
    # Model không kể được thì hệ thống nói vì sao (ADR-30, ngoại lệ 1): lưu thành `notice`, và
    # kết quả từng bước vẫn nằm trong khối bước. Model chọn im thì không câu kết, không thông báo.
    if telling:
        history.append(TurnRecord(kind="assistant", text=telling))
        shown = "report"
    elif failed:
        history.append(TurnRecord(kind="notice", text=REPORT_MISSING))
        shown = "notice"
    else:
        shown = "plan"
    if shown != "plan":
        await _record(session, thread, position, history[-1])
        yield TurnEvent(kind=shown, text=history[-1].text, conversation_id=thread)
    if began == 0:
        await _name_the_thread(session, request, settings, thread, said.text)
    yield TurnEvent(
        kind="done",
        text=telling or (REPORT_MISSING if failed else ""),
        conversation_id=thread,
        ended_as=shown,
        began=began,
    )


@router.post("/teacher/chat/messages", response_model=Answered)
async def say_something(
    said: "Said",
    request: Request,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Answered:
    """Đi một lượt trong hội thoại của giáo viên, rồi trả về khi nó xong.

    Cửa này **rút cạn** `run_turn` và báo cáo trạng thái cuối. Đường SSE của Pha E sẽ
    forward từng sự kiện của chính generator ấy, nên hai cửa sẽ không nói hai chuyện.

    Args:
        said: Thứ giáo viên vừa gõ.
        request: Mang theo pool của queue.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.
        settings: Settings của process.

    Returns:
        Lượt đó kết thúc kiểu gì, kèm các bước của **chính lượt này** đọc lại từ bảng.

    Raises:
        HTTPException: 404 cho một đoạn chat không phải của mình, 409 khi đoạn chat đang
            chạy một lượt khác, 503 khi không với tới được AGENT.
    """
    last: TurnEvent | None = None
    async for event in run_turn(said, request, teacher, session, settings):
        if event.kind == "done":
            last = event
    if last is None:
        # Không bao giờ xảy ra: mọi đường ra của generator đều phát `done`. Nổ ở đây chứ
        # không dựng một `Answered` rỗng -- một 200 với thân rỗng là một lượt bịa ra, và
        # người sửa sau sẽ đi tìm nguyên nhân ở phía client.
        raise RuntimeError("run_turn ended without a done event")
    return Answered(
        kind="ask_clarify" if last.ended_as == "clarify" else "say",
        text=last.text,
        conversation_id=last.conversation_id,
        choices=list(last.choices),
        more_choices=last.more_choices,
        turns=await _rendered(session, last.conversation_id, last.began),
    )


def _as_sse(event: TurnEvent) -> str:
    """Một sự kiện dưới dạng một khung `text/event-stream`.

    Dùng `data:` một dòng với JSON, không dùng `event:` theo loại: client đọc `kind` trong
    chính payload, nên thêm một trục phân loại thứ hai ở tầng giao thức là hai nguồn sự thật
    cho cùng một câu hỏi.

    Args:
        event: Sự kiện vừa xảy ra.

    Returns:
        Chuỗi đã có dòng trống kết khung.
    """
    return f"data: {event.model_dump_json()}\n\n"


@router.post("/teacher/chat/messages/stream")
async def say_something_streaming(
    said: "Said",
    request: Request,
    teacher: Teacher = Depends(current_teacher),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """Đi một lượt và phát từng việc ra ngay khi nó xảy ra.

    Cùng một `run_turn` với cửa `POST`, chỉ khác hai điều, và cả hai đều đáng nói:

    **`watching=True`** — lượt này đợi các câu hỏi về rồi mới để model kể lại (ADR-25). Cửa
    `POST` không đợi, vì nó rút cạn generator bên trong một request và một request đứng chờ
    hàng phút sẽ bị cắt ở đâu đó giữa đường.

    **Session của riêng nó.** Một session lấy qua `Depends` sống theo request và bị đóng khi
    response kết thúc — ở đây "kết thúc" là sau cả vòng soạn đề, nên nó giữ một connection
    suốt thời gian ấy. Mở session của chính đường này giữ quyền sở hữu rõ ràng và cho phép
    thả connection giữa các lần đợi.

    **Thứ nó KHÔNG làm: giữ lượt sống khi giáo viên đóng tab.** Starlette cancel generator
    khi client ngắt kết nối, nên lượt **bị cắt** ngay chỗ nó đang đợi: không câu kết, và nếu
    là lượt đầu thì đoạn chat cũng chưa có tên. ADR-25 đòi *"đóng tab giữa pha 2 thì lượt
    vẫn ghi đủ, và báo cáo viết ở lần quan sát kế tiếp"* — cả hai nửa đều **chưa làm**, và
    làm được thì phải đẩy pha 2 sang một job arq cùng một cờ *"lượt này đã báo cáo chưa"*
    trong `teacher_turns`. Món nợ ghi ở plan; đừng đọc docstring này thành một lời hứa.

    Args:
        said: Thứ giáo viên vừa gõ.
        request: Mang theo pool của queue.
        teacher: Được resolve từ header actor (ADR-13).
        settings: Settings của process.

    Returns:
        Một `text/event-stream`, mỗi khung là một `TurnEvent` dưới dạng JSON.
    """

    async def frames() -> AsyncIterator[str]:
        async with session_scope() as session:
            try:
                async for event in run_turn(
                    said, request, teacher, session, settings, watching=True
                ):
                    yield _as_sse(event)
            except HTTPException as refused:
                # 404/409/503 không còn gửi được bằng status code: header đã đi rồi, và
                # 409 -- *đoạn chat đang chạy một lượt khác* -- là ca thường gặp nhất ở đây,
                # vì hai tab cùng một đoạn là chuyện bình thường. Gửi nó
                # thành một sự kiện để màn hình nói ra được, thay vì đứng im tới timeout.
                yield _as_sse(TurnEvent(kind="done", text=str(refused.detail), ended_as="error"))
            except Exception:
                logger.exception("a streamed turn broke for %s", teacher.teacher_code)
                yield _as_sse(TurnEvent(kind="done", text=TURN_BROKE, ended_as="error"))

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            # Một proxy gom buffer sẽ giữ cả stream lại tới lúc nó xong, và khi đó SSE
            # không hơn gì một POST chậm.
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/teacher/chat", response_model=Answered)
async def read_conversation(
    conversation_id: str | None = None,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> Answered:
    """Đọc lại một hội thoại của giáo viên này.

    Thiếu `conversation_id` thì vẫn là **hội thoại đang chạy**, y như trước khi giáo viên
    có nhiều đoạn. Giữ nguyên mặc định ấy là có chủ ý: nó là thứ sáu test hiện có dựa
    vào, và sáu test ấy chính là bằng chứng rằng đợt thêm nhiều luồng không làm vỡ hành
    vi cũ.

    Giới hạn theo chủ sở hữu (ADR-22). Khi không có id thì luật ấy là **cấu trúc** —
    hội thoại được tìm qua `teacher_id`. Khi có id thì nó là một phép kiểm thật, và một
    id của người khác đọc ra **y hệt** một id không tồn tại.

    Args:
        conversation_id: Đoạn chat nào. Thiếu thì lấy đoạn đang chạy.
        teacher: Được resolve từ header actor.
        session: Session của database.

    Returns:
        Mọi bước đã có tới lúc này. `kind` là "say" và `text` rỗng, vì đọc không phải một
        lượt -- việc trả lời request này không nói ra điều gì cả.

    Raises:
        HTTPException: 404 khi đoạn chat không tồn tại **hoặc** thuộc về người khác.
    """
    asking = Asking.of(teacher)
    if conversation_id is not None:
        thread = await _owned_conversation(session, asking, conversation_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="không tìm thấy đoạn chat này")
        stored = await _stored_turns(session, thread)
        return _read_back(thread, stored, await _current_titles(session, stored))

    # Có chủ đích không dùng `_conversation`: hàm đó mở một luồng mới khi chưa có luồng
    # nào, và một GET mà ghi dữ liệu là một GET mà một lần prefetch của browser, một cú dò
    # HEAD hay một lần retry có thể nhân lên. Một giáo viên chưa nói gì bao giờ thì có một
    # hội thoại rỗng, và đó đúng là điều mà một danh sách rỗng nói ra.
    thread = await _latest_conversation(session, asking)
    if thread is None:
        return Answered(kind="say", text="", turns=[])

    stored = await _stored_turns(session, thread)
    return _read_back(thread, stored, await _current_titles(session, stored))


class ConversationRead(BaseModel):
    """Một đoạn chat trên rail.

    Attributes:
        conversation_id: Đoạn nào.
        title: Tên model đã đặt, hoặc câu đầu cắt ngắn khi model không đặt được. Rỗng chỉ
            trong một khoảnh khắc: giữa lúc luồng được mở và lúc lượt đầu tiên xong.
        started_at: Lúc mở, UTC.
        last_spoke_at: Lần nói cuối, UTC. Rail nhóm theo con số **này** chứ không theo giờ
            mở: một đoạn mở từ tuần trước mà hôm nay vừa nói tiếp thì thuộc về *Hôm nay*,
            và đó là chỗ người ta đi tìm nó.
    """

    conversation_id: str
    title: str
    started_at: datetime
    last_spoke_at: datetime


@router.get("/teacher/conversations", response_model=list[ConversationRead])
async def conversations(
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> list[ConversationRead]:
    """Mọi đoạn chat của giáo viên đang gọi, mới nói nhất lên đầu.

    Chỉ những đoạn **đã có ít nhất một bước**. Một hàng rỗng không có gì để vẽ và không có
    đường nào xoá, nên nó chỉ có thể là rác — mà `start_new` ghi bước đầu tiên ngay trong
    cùng request, nên một hàng rỗng nghĩa là một request đã chết giữa chừng. `JOIN` thay
    cho `LEFT JOIN` là cách rẻ nhất để rác đó không bao giờ lên màn hình.

    Lọc theo `teacher_id`, nên không có id nào một caller truyền vào để với tới đoạn chat
    của người khác (ADR-22) — ở đây luật ấy là **cấu trúc**: endpoint không nhận id nào cả.

    Args:
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        Một dòng cho mỗi đoạn chat, sắp theo lần nói cuối.
    """
    spoke = _spoke_at()
    rows = await session.execute(
        select(
            TeacherConversation.id,
            TeacherConversation.title,
            TeacherConversation.started_at,
            spoke.c.at,
        )
        .join(spoke, spoke.c.conversation_id == TeacherConversation.id)
        .where(
            TeacherConversation.teacher_id == teacher.id,
            TeacherConversation.deleted_at.is_(None),
        )
        .order_by(spoke.c.at.desc(), TeacherConversation.id.desc())
    )
    return [
        ConversationRead(
            conversation_id=row.id,
            title=row.title,
            started_at=aware(row.started_at),
            last_spoke_at=aware(row.at),
        )
        for row in rows
    ]


class Renaming(BaseModel):
    """Tên mới cho một đoạn chat.

    Attributes:
        title: Tên giáo viên gõ. Dọn bằng `_tidy` y như tên model viết — cùng một cột,
            cùng một giới hạn, nên cùng một hàm dọn. Rỗng sau khi dọn thì bị từ chối: cột
            rỗng có nghĩa riêng của nó (*chưa đặt tên*), và cho phép gõ về rỗng là trộn
            *"tôi chưa đặt"* với *"tôi đặt tên là không gì cả"*.
    """

    title: str


@router.patch("/teacher/conversations/{conversation_id}", response_model=ConversationRead)
async def rename_conversation(
    conversation_id: str,
    renaming: Renaming,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> ConversationRead:
    """Đổi tên một đoạn chat.

    Tên vốn do model đặt một lần sau lượt đầu (`_name_the_thread`) và trước đợt này không
    ai sửa được. Một cái tên model đặt sai thì đứng đó mãi, và rail là chỗ giáo viên đi tìm
    lại việc cũ — nên một cái tên sai là một đoạn chat mất tích.

    Args:
        conversation_id: Đoạn nào.
        renaming: Tên mới.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        Hàng của đoạn ấy sau khi đổi, đủ để rail vẽ lại mà không gọi thêm.

    Raises:
        HTTPException: 404 khi đoạn không tồn tại, của người khác, hoặc đã xoá (ADR-22);
            400 khi tên dọn xong còn rỗng.

    Side effects:
        Cập nhật một row và commit.
    """
    asking = Asking.of(teacher)
    thread = await _owned_conversation(session, asking, conversation_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="không tìm thấy đoạn chat này")

    named = _tidy(renaming.title)
    if not named:
        raise HTTPException(status_code=400, detail="tên đoạn chat không được để trống")

    row = await session.get(TeacherConversation, thread)
    if row is None:  # pragma: no cover - `_owned_conversation` vừa thấy nó
        raise HTTPException(status_code=404, detail="không tìm thấy đoạn chat này")
    # Đọc `started_at` **trước** khi commit. Commit làm hết hạn các object ORM, và một lần
    # đọc attribute sau đó là một lazy load — thứ nổ `MissingGreenlet` trên session async.
    # `_conversation` đã chép lại đúng bài học này trong docstring của nó.
    started = row.started_at
    row.title = named
    await session.commit()

    spoke = await session.scalar(
        select(func.max(TeacherTurn.created_at)).where(TeacherTurn.conversation_id == thread)
    )
    return ConversationRead(
        conversation_id=thread,
        title=named,
        started_at=aware(started),
        last_spoke_at=aware(spoke or started),
    )


@router.delete("/teacher/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Xoá một đoạn chat khỏi mắt giáo viên.

    **Xoá mềm**, và lý do nằm ở chỗ hai đòi hỏi kéo ngược nhau. Giáo viên muốn một đoạn gõ
    nhầm biến đi; ADR-24 lại đòi biên bản duyệt đề giữ được, và biên bản ấy là một row
    `teacher_turns` của chính đoạn này. Xoá thật thì một cú dọn nhà phá mất bằng chứng cho
    một cuộc đi tìm sau này, mà cuộc đi tìm ấy là chuyện của tháng sau chứ không phải của
    người đang bấm nút. Nên đoạn đã xoá đọc ra **y như một đoạn không tồn tại** — rời rail,
    `GET` ra 404, không nhận câu mới nào — còn các lượt của nó nằm nguyên trong bảng.

    Không trả về gì: `204`. Rail tự bỏ hàng đó đi, và không có trạng thái nào của đoạn đã
    xoá mà client cần biết.

    Args:
        conversation_id: Đoạn nào.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Raises:
        HTTPException: 404 khi đoạn không tồn tại, của người khác, hoặc đã xoá (ADR-22).
            Xoá hai lần vì thế ra 404 chứ không ra 204 — lần thứ hai thật sự không tìm thấy
            gì, và nói ngược lại là nói rằng vừa xoá được một thứ đã không còn.

    Side effects:
        Cập nhật một row và commit.
    """
    asking = Asking.of(teacher)
    thread = await _owned_conversation(session, asking, conversation_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="không tìm thấy đoạn chat này")

    row = await session.get(TeacherConversation, thread)
    if row is None:  # pragma: no cover - `_owned_conversation` vừa thấy nó
        raise HTTPException(status_code=404, detail="không tìm thấy đoạn chat này")
    row.deleted_at = datetime.now(UTC)
    await session.commit()
