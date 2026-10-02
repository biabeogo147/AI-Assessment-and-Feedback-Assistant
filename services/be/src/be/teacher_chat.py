"""Chat của giáo viên, nơi BE chạy vòng lặp và AGENT chỉ tư vấn.

Một lượt là nhiều lượt gọi model. BE hỏi AGENT bước tiếp theo nên làm gì, làm nó hoặc
từ chối nó, rồi hỏi lại kèm kết quả, cho đến khi AGENT trả lời bằng lời hoặc mức trần
chặn lại. AGENT không bao giờ tự chạy gì: nó không giữ credential nào của database, và
việc phân quyền thuộc về process đang giữ session và biết ai đang gọi.

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
- **Mỗi bước là một lượt gọi model**, nên cái invariant rằng một job của AGENT timeout
  trước khi BE thôi đợi là đúng trên đường này.

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
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from be.agent_gateway import AgentError, run_task
from be.config import Settings, get_settings
from be.db import get_session
from be.identity import Asking, current_teacher
from be.models import Teacher, TeacherConversation, TeacherTurn, aware
from be.teacher_tools import UnknownTool, catalog_for, execute
from contracts import (
    PROPOSE_NEXT_STEP_TASK,
    NextStepCompleted,
    NextStepRequested,
    ToolSpec,
    TurnRecord,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["teacher-chat"])

# Câu nói ra khi vòng lặp hết số bước. Nó gọi tên nguyên nhân, vì một giáo viên chỉ được
# nghe "có gì đó sai rồi" thì sẽ hỏi lại đúng câu đó và tiêu đúng lượng ngân sách đó để
# đụng đúng cái mức trần đó.
_CEILING_REACHED = (
    "Mình tra mãi mà chưa ra câu trả lời gọn cho câu này. Bạn thử hỏi cụ thể hơn giúp mình nhé, "
    "ví dụ nói rõ tên lớp và tên bài kiểm tra."
)

_AGENT_UNAVAILABLE = "Trợ lý chưa trả lời được. Bạn thử lại sau một chút nhé."


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
    """

    text: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    start_new: bool = False

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
    AGENT không dùng được. Bốn field cuối chính là trường hợp đó -- chủ thể của bước và
    cái giá nó tốn là để cho màn hình và cho người đi debug, và chẳng có nghĩa gì với
    model.

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
    model_tokens: int = 0
    duration_ms: int = 0


class Answered(BaseModel):
    """Kết quả của một lượt.

    Attributes:
        kind: Lượt đó kết thúc kiểu gì: `say` hay `ask_clarify`.
        text: Phần chữ để hiện ra. Do model viết.
        choices: Các phương án cho `ask_clarify`, do **BE** viết từ chính các row mà một
            tool trả về (ADR-23). Thứ model tự điền vào `choices` của nó thì bị bỏ qua:
            BE là bên giữ các row, nên một danh sách do model viết thì tốt nhất cũng chỉ
            là một bản sao của chúng, còn tệ nhất là một tên lớp bịa ra đến trước mặt
            giáo viên với cả uy tín của hệ thống đứng sau. Rỗng khi trong lượt này không
            tool nào cho ra candidate, và điều đó làm câu hỏi thành một câu hỏi mở chứ
            không phải một danh sách hỏng.
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
    history: list[TurnRecord],
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
        catalog: Những tool giáo viên này được dùng, lấy một lần trước vòng lặp.
        history: Mọi thứ đã có tới lúc này, cũ nhất trước.

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
    )
    answer = await run_task(
        getattr(request.app.state, "queue_pool", None),
        settings,
        PROPOSE_NEXT_STEP_TASK,
        asked.model_dump(mode="json"),
    )
    return NextStepCompleted.model_validate(answer)


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

    options = [
        f"{entry['name']} ({entry['student_count']} học sinh)"
        for entry in listed
        if isinstance(entry, dict)
        and isinstance(entry.get("name"), str)
        and isinstance(entry.get("student_count"), int)
    ]
    more = result.get("more")
    return options, more if isinstance(more, int) and more > 0 else 0


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

    Một lớp từ `find_class`, hoặc một đề nháp từ `create_draft` và `start_drafting`. Các
    cột chứa đúng những gì các tool thực sự trả về, nên chúng lớn dần theo các tool.

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
    if not any(
        result.get(flag)
        for flag in ("found", "created", "started", "approved", "unapproved", "published")
    ):
        return "", ""
    for key, kind in _ENTITY_KEYS:
        value = result.get(key)
        if isinstance(value, str) and value:
            return kind, value
    return "", ""


async def _owned_conversation(session: AsyncSession, asking: Asking, thread: str) -> str | None:
    """Đoạn chat này có phải của người đang hỏi không.

    `conversation_id` nay là thứ **client gửi lên**, nên nó là một id không tin được —
    khác hẳn mọi id trước đây trong file này, vốn do chính BE tìm ra từ `teacher_id`. Một
    id của người khác mà lọt qua sẽ cho đọc nguyên một hội thoại không phải của mình.

    Trả `None` cho cả hai ca — không tồn tại, và không phải của bạn — vì ADR-22 nói hai ca
    ấy phải đọc ra **y hệt nhau**. Phân biệt được chúng là cho bất kỳ ai dò xem giáo viên
    khác đang có những gì, chỉ bằng cách thử id.

    Args:
        session: Session của database.
        asking: Ai đang hỏi.
        thread: Id client gửi lên.

    Returns:
        Chính id đó khi nó là của người hỏi, ngược lại `None`.
    """
    return await session.scalar(
        select(TeacherConversation.id).where(
            TeacherConversation.id == thread,
            TeacherConversation.teacher_id == asking.teacher_id,
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
        .where(TeacherConversation.teacher_id == asking.teacher_id)
        .order_by(active.desc(), TeacherConversation.id.desc())
        .limit(1)
    )


async def _conversation_of(session: AsyncSession, asking: Asking, assessment_id: str) -> str | None:
    """Đoạn chat nào đã sinh ra đề này.

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

    Returns:
        id của đoạn chat, hoặc None khi đề không sinh ra từ đoạn chat nào — đề seed, hoặc
        đề tạo bằng tay. Caller lùi về đoạn mới nhất chứ không nổ: một đề vẫn phải duyệt
        được.
    """
    return await session.scalar(
        select(TeacherTurn.conversation_id)
        .join(TeacherConversation, TeacherConversation.id == TeacherTurn.conversation_id)
        .where(
            TeacherConversation.teacher_id == asking.teacher_id,
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


def _as_records(turns: list[TeacherTurn]) -> list[TurnRecord]:
    """Biến các bước đã lưu thành phần history mà AGENT đọc.

    Chỉ phần đuôi được gửi đi. Lý do xem ở `_HISTORY_STEPS`, và lưu ý là chỗ bị cắt là
    phần đầu: model cần câu hỏi nó vừa hỏi hơn nhiều so với câu nó hỏi tuần trước.

    Args:
        turns: Các bước đã lưu, cũ nhất trước.

    Returns:
        `_HISTORY_STEPS` bước cuối trong số đó, dưới dạng record của contract.
    """
    return [
        TurnRecord(
            kind=turn.kind,
            text=turn.text,
            tool_name=turn.tool_name,
            tool_args=turn.tool_args or {},
            tool_result=turn.tool_result or {},
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
    Là đoạn **đã sinh ra đề**, suy từ `entity_id` — xem `_conversation_of`. Đề không sinh
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
    thread = (await _conversation_of(session, asking, subject)) if subject else None
    if thread is None:
        thread = await _conversation(session, asking)
    stored = await _stored_turns(session, thread)
    await _record(session, thread, len(stored), record)


def _visible(turn: TeacherTurn) -> Turn:
    """Chiếu một bước đã lưu sang đúng thứ client được xem."""
    return Turn(
        kind=turn.kind,
        text=turn.text,
        tool_name=turn.tool_name,
        tool_result=turn.tool_result or {},
        entity_kind=turn.entity_kind,
        entity_id=turn.entity_id,
        model_tokens=turn.model_tokens,
        duration_ms=turn.duration_ms,
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
    rows = await session.scalars(
        select(TeacherTurn)
        .where(TeacherTurn.conversation_id == conversation_id, TeacherTurn.sequence >= since)
        .order_by(TeacherTurn.sequence)
    )
    return [_visible(turn) for turn in rows]


@router.post("/teacher/chat/messages", response_model=Answered)
async def say_something(
    said: Said,
    request: Request,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Answered:
    """Đi một lượt trong hội thoại của giáo viên.

    Args:
        said: Thứ giáo viên vừa gõ.
        request: Mang theo pool của queue.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database mà mọi tool chạy trên đó.
        settings: Cung cấp `max_tool_steps`.

    Returns:
        Lượt đó kết thúc kiểu gì, kèm các bước của **chính lượt này** đọc lại từ bảng.
        Không phải cả hội thoại: một client đem chúng ghép thêm vào thứ nó đang hiện sẽ vẽ
        lại cả luồng lên trên chính nó.

    Raises:
        HTTPException: 503 khi không với tới được AGENT chút nào. Không sự cố tool nào tới
            được đây: mọi sự cố, dù là tên tool không có hay một query hỏng, đều thành một
            kết quả mà model đọc được và hồi lại được. Đó chính là chỗ khác nhau giữa việc
            trợ lý bị hỏng và việc trợ lý bị nói không.

    Side effects:
        Ghi thêm mọi bước của lượt vào hội thoại của giáo viên và commit từng bước một.
        Đẩy một job của AGENT vào queue cho mỗi bước, và chạy các tool chỉ đọc lên
        database.
    """
    # Identity và catalog đọc một lần, dưới dạng giá trị. Mỗi bước gọi tool rollback
    # session để thả connection của nó ra, và việc đó làm hết hạn mọi object ORM đang gắn
    # vào session -- nên không dòng nào bên dưới được chạm lại vào row `teacher`.
    asking = Asking.of(teacher)
    catalog = catalog_for(asking)

    # id dưới dạng một string trần, đọc một lần -- luật này xem ở docstring của module.
    # Đáng gọi tên cơ chế cho thật chính xác, vì bản đầu tiên của comment này quy tội cho
    # `commit` và như thế là sai: `bind_sessions` dựng các session với
    # `expire_on_commit=False`, nên các lần commit ở đây để các object vẫn dùng được. Thứ
    # làm chúng hết hạn là `rollback` giữa các bước gọi tool, và nó bỏ qua setting đó.
    # Cùng một cách phòng, khác nguyên nhân -- và một bài học ghi lại sai nguyên nhân thì
    # lần sau sẽ được đem áp vào sai chỗ.
    if said.conversation_id is not None:
        thread = await _owned_conversation(session, asking, said.conversation_id)
        # Một đoạn chat không tồn tại và một đoạn của người khác nhận cùng một câu trả
        # lời (ADR-22). `404` chứ không phải mở hộ một đoạn mới: gõ nhầm id rồi được
        # nói vào một nơi khác là mất câu vừa gõ ở một chỗ không ai đi tìm.
        if thread is None:
            raise HTTPException(status_code=404, detail="không tìm thấy đoạn chat này")
    else:
        thread = await _conversation(session, asking, start_new=said.start_new)
    stored = await _stored_turns(session, thread)
    position = len(stored)
    # Chỗ lượt này bắt đầu, để câu trả lời báo cáo được các bước của chính nó chứ không
    # phải cả hội thoại.
    began = position

    # Cả hội thoại, không chỉ tin nhắn này. Trước khi nó được lưu, một giáo viên trả lời
    # chính câu hỏi lại của trợ lý thì gửi câu trả lời đó đi mà không còn dấu vết nào của
    # câu đã hỏi -- nên cái cổng đầu vào của ADR-05 tồn tại mà không có cách nào để trả
    # lời.
    history = _as_records(stored)
    history.append(TurnRecord(kind="teacher", text=said.text))
    position = await _record(session, thread, position, history[-1])

    # Các phương án cho một câu hỏi lại, do BE dựng ra từ kết quả tool gần nhất có cho ra
    # candidate. Một câu hỏi được phép đưa ra những phương án này và không gì khác
    # (ADR-05, ADR-23).
    offered: list[str] = []
    offered_more = 0
    deadline = asyncio.get_running_loop().time() + settings.turn_budget_seconds

    for _ in range(settings.max_tool_steps):
        if asyncio.get_running_loop().time() >= deadline:
            # Mức trần số bước, một mình nó, không phải một lời hứa về thời gian đợi: tám
            # bước nhân với timeout của một job là hơn chín phút, và một browser hay một
            # proxy sẽ cắt connection từ rất lâu trước đó trong khi BE vẫn ghi log là
            # thành công. Đây mới là mức chặn mà giáo viên thực sự cảm thấy.
            logger.warning("turn budget spent for %s", asking.teacher_code)
            break

        started = time.monotonic()
        try:
            step = await _ask_agent(request, settings, asking.full_name, catalog, history)
        except AgentError as unreachable:
            logger.warning("agent unreachable for %s: %s", asking.teacher_code, unreachable)
            raise HTTPException(status_code=503, detail=_AGENT_UNAVAILABLE) from unreachable

        spent_ms = int((time.monotonic() - started) * 1000)

        if step.kind in {"say", "ask_clarify"}:
            history.append(TurnRecord(kind="assistant", text=step.text))
            position = await _record(
                session,
                thread,
                position,
                history[-1],
                duration_ms=spent_ms,
                model_tokens=step.model_tokens,
            )
            if step.choices:
                # Bỏ qua, không phải lọc lại. BE là bên giữ các row; thứ model viết ra ở
                # đây tốt nhất cũng chỉ là một bản sao, còn tệ nhất là một thứ bịa ra.
                logger.info(
                    "ignored %d model-written choice(s) for %s",
                    len(step.choices),
                    asking.teacher_code,
                )
            return Answered(
                kind=step.kind,
                text=step.text,
                conversation_id=thread,
                choices=offered,
                more_choices=offered_more,
                turns=await _rendered(session, thread, began),
            )

        history.append(
            TurnRecord(kind="tool_call", tool_name=step.tool_name, tool_args=step.tool_args)
        )
        position = await _record(
            session,
            thread,
            position,
            history[-1],
            duration_ms=spent_ms,
            model_tokens=step.model_tokens,
        )

        try:
            result = await execute(
                session,
                asking,
                step.tool_name,
                step.tool_args,
                # Các tool ghi thì đẩy việc vào queue; các tool đọc thì không bao giờ
                # chạm vào cái này. Một queue chết vì thế chỉ làm mất việc soạn đề và
                # không gì khác.
                pool=getattr(request.app.state, "queue_pool", None),
                settings=settings,
            )
        except UnknownTool:
            # Trả về cho model dưới dạng dữ liệu, không phải dưới dạng một exception. Nó
            # đã đề xuất một thứ không tồn tại -- thường là một tool nó nhớ lờ mờ từ một
            # bối cảnh khác -- và cách hồi lại là để nó đọc lời từ chối rồi chọn trong
            # đúng cái catalog nó đã được đưa.
            logger.info("refused tool %r for %s", step.tool_name, asking.teacher_code)
            result = {"error": f"không có tool nào tên {step.tool_name}"}
        except Exception:
            # Mọi sự cố khác cũng vậy, và cũng vì đúng lý do đó. Một tool hỏng không phải
            # là trợ lý hỏng: model có thể nói "mình chưa tra được" và giáo viên có thể
            # hỏi chuyện khác, và đó là một lượt tốt hơn một lỗi 500 không có chữ tiếng
            # Việt nào trong đó. Nguyên nhân đi vào log, không đi vào prompt -- một stack
            # trace nằm trong history là văn bản mà model sẽ thử hành động theo.
            logger.exception("tool %r failed for %s", step.tool_name, asking.teacher_code)
            result = {"error": f"tool {step.tool_name} chạy không xong"}
        finally:
            # Thả connection ra giữa các bước. Không có dòng này thì một session giữ một
            # connection lấy từ pool -- và một transaction Postgres nằm không -- xuyên qua
            # mọi lần đợi `run_task` trong cả lượt. Pool rộng 15, nên vài giáo viên đang
            # chat là đủ làm nghẽn mọi request khác trong process, kể cả những request mà
            # học sinh đang poll.
            await session.rollback()

        # Thay hẳn, không gộp vào. Giữ lại candidate của tool trước nghĩa là một câu hỏi
        # về chuyện khác đến nơi mà vẫn còn dính chúng: hỏi về một lớp, rồi hỏi bao nhiêu
        # câu, thì câu hỏi thứ hai về tới với hai tên lớp làm phương án trả lời.
        offered, offered_more = _offered(result)
        history.append(TurnRecord(kind="tool_result", tool_name=step.tool_name, tool_result=result))
        position = await _record(session, thread, position, history[-1])

    # Mức trần. Chạm tới, không phải đâm vào: giáo viên nhận được một câu gọi tên nguyên
    # nhân và gợi ý đúng một việc có ích.
    logger.warning("tool loop hit %d steps for %s", settings.max_tool_steps, asking.teacher_code)
    history.append(TurnRecord(kind="assistant", text=_CEILING_REACHED))
    await _record(session, thread, position, history[-1])
    return Answered(
        kind="say",
        text=_CEILING_REACHED,
        conversation_id=thread,
        turns=await _rendered(session, thread, began),
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
        return Answered(
            kind="say", text="", conversation_id=thread, turns=[_visible(turn) for turn in stored]
        )

    # Có chủ đích không dùng `_conversation`: hàm đó mở một luồng mới khi chưa có luồng
    # nào, và một GET mà ghi dữ liệu là một GET mà một lần prefetch của browser, một cú dò
    # HEAD hay một lần retry có thể nhân lên. Một giáo viên chưa nói gì bao giờ thì có một
    # hội thoại rỗng, và đó đúng là điều mà một danh sách rỗng nói ra.
    thread = await _latest_conversation(session, asking)
    if thread is None:
        return Answered(kind="say", text="", turns=[])

    stored = await _stored_turns(session, thread)
    return Answered(
        kind="say", text="", conversation_id=thread, turns=[_visible(turn) for turn in stored]
    )


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
        .where(TeacherConversation.teacher_id == teacher.id)
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
