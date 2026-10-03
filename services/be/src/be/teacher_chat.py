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
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from be.agent_gateway import AgentError, run_task
from be.config import Settings, get_settings
from be.db import get_session, session_scope
from be.drafting import harvest, open_bells, pending_count
from be.identity import Asking, current_teacher
from be.models import (
    DraftBrief,
    Question,
    Teacher,
    TeacherConversation,
    TeacherTurn,
    aware,
    new_id,
)
from be.teacher_tools import (
    LOOKS_LIKE_REFERENCE,
    PHASE_PLAN,
    PHASE_WORK,
    REFERENCE,
    UnknownTool,
    Unresolvable,
    catalog_for,
    execute,
    resolve_args,
)
from contracts import (
    NAME_CONVERSATION_TASK,
    PROPOSE_NEXT_STEP_TASK,
    REPORT_PLAN_TASK,
    ConversationNameCompleted,
    ConversationNameRequested,
    NextStepCompleted,
    NextStepRequested,
    PlanReportCompleted,
    PlanReportRequested,
    PlanStep,
    StepOutcome,
    ToolSpec,
    TurnRecord,
)

logger = logging.getLogger(__name__)

# Trần số bước của một plan. Pha 1 có `max_tool_steps`; pha 2 phải có trần của riêng nó,
# vì mỗi bước ở đây là một tool **ghi**: một plan năm mươi bước `create_draft` lọt qua sẽ để
# lại năm mươi đề rỗng mang tên giáo viên, và không có đường nào xoá chúng.
_MOST_STEPS = 8

router = APIRouter(prefix="/api", tags=["teacher-chat"])

# Câu nói ra khi vòng lặp hết số bước. Nó gọi tên nguyên nhân, vì một giáo viên chỉ được
# nghe "có gì đó sai rồi" thì sẽ hỏi lại đúng câu đó và tiêu đúng lượng ngân sách đó để
# đụng đúng cái mức trần đó.
_CEILING_REACHED = (
    "Mình tra mãi mà chưa ra câu trả lời gọn cho câu này. Bạn thử hỏi cụ thể hơn giúp mình nhé, "
    "ví dụ nói rõ tên lớp và tên bài kiểm tra."
)

# Câu cho một lượt gãy giữa stream. Header đã gửi đi rồi, nên không còn status code nào
# để nói, và một màn hình không nghe gì nữa sẽ đứng im tới khi người đọc bỏ đi.
_TURN_BROKE = "Lượt này hỏng giữa chừng. Bạn thử gửi lại câu vừa rồi nhé."

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
    plannable: tuple[ToolSpec, ...],
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
        catalog: Những tool model được gọi ngay, lấy một lần trước vòng lặp.
        plannable: Những tool model được nêu trong một plan nhưng không gọi được bây giờ.
            Pha 1 phải biết chúng tồn tại và nhận tham số nào, nếu không nó đoán -- và một
            plan đoán sai tên tham số bị `vet_plan` từ chối trọn gói (ADR-25).
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
        plannable=plannable,
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


# Sáu cờ, một câu hỏi: việc đó có xảy ra không. Mọi tool trả lời bằng đúng một trong
# chúng, và hai chỗ cần biết câu trả lời -- `_subject` để quyết có chủ thể hay không, và
# `_went_wrong` để quyết bước đó hỏng hay xong -- đọc chung danh sách này.
_DID_IT_HAPPEN = ("found", "created", "started", "approved", "unapproved", "published")


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
    if not any(result.get(flag) for flag in _DID_IT_HAPPEN):
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


# Câu BE nói khi một plan không dùng được. Nó nói **cái gì** sai chứ không nói "có lỗi":
# giáo viên không sửa được một plan họ chưa bao giờ thấy, nên câu này là lời xin lỗi kèm
# một đề nghị gõ lại, không phải một mã lỗi.
_PLAN_REFUSED = "Mình chưa dựng được các bước cho việc này. Bạn nói lại giúp mình một lần nữa nhé."


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
        missing = set(spec.arguments) - set(step.args)
        if missing:
            # Mọi tham số được mô tả cho model đều là tham số **bắt buộc**: catalog chỉ nêu
            # những thứ tool thật sự cần. Thiếu một cái là một bước sẽ chạy với tay không --
            # đo trên trình duyệt thật, model nêu `start_drafting` không kèm `assessment_id`,
            # bước ấy hỏng, và lượt để lại một đề rỗng mang tên giáo viên. Từ chối trọn gói ở
            # đây là cách duy nhất không có gì kịp ghi.
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


async def _report(
    request: Request,
    settings: Settings,
    said: str,
    outcomes: list[StepOutcome],
    counted: tuple[int, int, int] = (0, 0, 0),
) -> str:
    """Nhờ model kể lại những gì plan vừa làm.

    Một lời gọi riêng vì đầu vào của nó khác: nó đọc kết quả của cả plan, không đọc catalog
    (ADR-25). Hỏng thì lùi về một câu dựng từ chính `outcomes` -- lượt không bao giờ chết vì
    phần kể lại, đúng như `_name_the_thread`.

    Args:
        request: Mang theo pool của queue.
        settings: Cho timeout của job.
        said: Câu giáo viên đã gõ.
        outcomes: Các bước đã chạy, theo thứ tự.
        counted: `(đã có, xin bao nhiêu, còn đang soạn)` câu, đếm từ database. Ba con số này
            làm cho luật *"nói đang soạn hay nói đã xong"* thành **dữ liệu** thay vì một câu
            cứng trong prompt -- câu cứng ấy đúng hay sai tuỳ vào thời điểm báo cáo chạy, và
            thời điểm ấy vừa đổi khi cửa SSE bắt đầu đợi các câu về.

    Returns:
        Câu kết để hiện trên màn hình. Không bao giờ rỗng.
    """
    fallback = "; ".join(
        f"{one.title}{'' if not one.detail else f' — {one.detail}'}" for one in outcomes
    )
    fallback = fallback or "Mình chưa làm được bước nào."
    try:
        answer = await run_task(
            getattr(request.app.state, "queue_pool", None),
            settings,
            REPORT_PLAN_TASK,
            PlanReportRequested(
                request_id=new_id(),
                said=said,
                outcomes=tuple(outcomes),
                written=counted[0],
                asked_for=counted[1],
                still_drafting=counted[2],
            ).model_dump(mode="json"),
        )
        written = PlanReportCompleted.model_validate(answer).text.strip()
        return written or fallback
    except Exception:  # noqa: BLE001 -- xem docstring
        logger.exception("could not report the plan for %s", said[:40])
        return fallback


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
    choices: list[str] | None = None,
    more_choices: int = 0,
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


def _visible(turn: TeacherTurn) -> Turn:
    """Chiếu một bước đã lưu sang đúng thứ client được xem."""
    return Turn(
        kind=turn.kind,
        text=turn.text,
        tool_name=turn.tool_name,
        tool_result=turn.tool_result or {},
        entity_kind=turn.entity_kind,
        entity_id=turn.entity_id,
        choices=list(turn.choices or []),
        more_choices=turn.more_choices,
        model_tokens=turn.model_tokens,
        duration_ms=turn.duration_ms,
    )


def _read_back(conversation_id: str, stored: "list[TeacherTurn]") -> "Answered":
    """Dựng câu trả lời cho một lần **đọc lại** một đoạn chat.

    Chỗ duy nhất quyết việc các phương án của một câu hỏi lại có còn được bày ra hay không.
    Chỉ bước **cuối cùng** được chở `choices` lên: một câu hỏi đã được trả lời thì các nút
    của nó không còn nghĩa gì, và bày lại chúng là mời giáo viên trả lời hai lần một câu.

    Args:
        conversation_id: Đoạn nào.
        stored: Mọi bước của đoạn, theo thứ tự.

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
        turns=[_visible(turn) for turn in stored],
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


class TurnEvent(BaseModel):
    """Một việc vừa xảy ra trong lượt này, đủ để vẽ ngay mà không cần đọc lại database.

    Lượt là một **dãy sự kiện**, không phải một khuôn cố định: harness tiêm context và tool,
    còn model quyết nói lúc nào, tra lúc nào, hỏi lúc nào (ADR-25). Màn hình vẽ theo đúng
    thứ tự nhận được.

    Attributes:
        kind: `say`, `clarify`, `plan`, `step_started`, `step_done`, `step_failed`, `report`
            hay `done`.
        text: Lời, cho `say`, `clarify`, `report` và `done`.
        choices: Phương án của một câu hỏi lại, do BE dựng từ dữ liệu (ADR-23).
        more_choices: Bao nhiêu candidate đã bị cắt khỏi `choices`.
        conversation_id: Lượt này nằm trong đoạn chat nào.
        ended_as: Lượt kết thúc bằng nhánh nào -- `say`, `clarify` hay `report`. Chỉ có ở sự kiện
            `done`. Suy nó từ việc `choices` có rỗng hay không thì sai ở đúng ca một câu hỏi lại
            chưa có candidate nào: nó là câu hỏi, mà bị báo về như một câu trả lời.
        title: Câu tiếng Việt của một bước, cho ba sự kiện `step_*`.
        detail: Dòng kết quả của một bước, hoặc lý do nó hỏng.
        index: Bước thứ mấy, đếm từ 1.
        total: Plan có bao nhiêu bước. Đây là `n` của `bước k/n`, và nó nói thật được
            chính vì plan có trước khi chạy.
        titles: Tiêu đề của từng bước, chỉ ở sự kiện `plan`. Khối bằng chứng vẽ được cả
            danh sách việc trước khi bước đầu tiên chạy.
        began: Lượt này bắt đầu ở vị trí nào trong hội thoại.
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


# Câu nói cho giáo viên khi một bước hỏng. `reason` của một tool là văn bản viết **cho
# model** -- "hãy hỏi giáo viên những mục còn thiếu", "question_count phải là một con số" --
# và in nó ra màn hình là để giáo viên đọc trợ lý nói về mình ở ngôi thứ ba, kèm một
# identifier tiếng Anh. Nguyên nhân đi vào log; chỗ này nói bằng lời người.
_WHY_IT_STOPPED = "chưa làm được bước này"

# Bước sau cần một giá trị bước trước không đưa được. Một câu, không phải `str(Unresolvable)`:
# cái sau gọi tên field và trích cú pháp tham chiếu, tức là mở mặt trong của hệ thống ra cho
# người không cần thấy nó -- và nó còn đi vào prompt của lời kể, nơi model sẽ nhắc lại.
_COULD_NOT_CARRY_OVER = "chưa ghép được dữ liệu từ bước trước"


def _said_about(result: dict) -> str:
    """Một dòng tiếng Việt kể kết quả của một bước, dựng từ **con số** của chính kết quả ấy.

    Không bao giờ in `reason` hay `error` nguyên văn: cả hai là chữ viết cho model đọc, và
    chúng chở cả tên field lẫn lời dặn model phải làm gì tiếp. Một màn hình in chúng ra là
    một màn hình để lộ mặt trong của hệ thống cho người không cần thấy nó.

    Args:
        result: Thứ tool vừa trả về.

    Returns:
        Dòng để hiện dưới tiêu đề bước. Rỗng khi kết quả không có con số nào đáng nói.
    """
    if result.get("error") or _went_wrong(result):
        if result.get("missing"):
            return "thiếu thông tin để làm bước này"
        if result.get("unreadable") or result.get("too_long"):
            return "một mục trong yêu cầu chưa dùng được"
        return _WHY_IT_STOPPED
    if "queued" in result:
        return f"{result['queued']} câu bắt đầu soạn"
    if "title" in result:
        asked = result.get("question_count")
        named = f'đề "{result["title"]}"'
        return named if asked is None else f"{named}, cần {asked} câu"
    return ""


def _went_wrong(result: dict) -> bool:
    """Bước đó hỏng hay xong.

    Dùng chung đúng một danh sách cờ với `_subject`, vì hai danh sách trong một file là định
    nghĩa của trôi dạt -- và chúng **đã** lệch nhau một lần: bản đầu của hàm này biết ba cờ
    trong khi `_subject` biết sáu, nên một bước phát hành hỏng sẽ được báo là xong.

    Args:
        result: Thứ tool vừa trả về.

    Returns:
        True khi việc không xảy ra.
    """
    return bool(result.get("error")) or any(result.get(flag) is False for flag in _DID_IT_HAPPEN)


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


def _how_many(counted: tuple[int, int, int]) -> str:
    """Dòng kết quả của bước soạn câu, viết từ ba con số đã đếm.

    Nó thay cho dòng `— N câu bắt đầu soạn` của lúc vừa bắn job: tới cuối bước thì con số
    đáng nói là **số câu thật sự đã có**, không phải số job đã đẩy đi.

    Args:
        counted: `(đã có, xin bao nhiêu, còn đang soạn)`.

    Returns:
        Dòng tiếng Việt để hiện dưới tiêu đề bước.
    """
    written, asked_for, running = counted
    if running:
        return f"đã soạn {written}/{asked_for} câu, còn {running} câu đang chạy"
    if asked_for and written < asked_for:
        return f"dừng ở {written}/{asked_for} câu"
    return f"đã soạn {written}/{asked_for} câu"


def _paper_in(results: list[dict]) -> str:
    """Id của đề mà plan vừa đụng tới, nếu có.

    Đọc từ kết quả các bước chứ không từ tên tool: `create_draft` và `start_drafting` đều
    trả `assessment_id`, và cái cuối cùng là cái đang được soạn.

    Args:
        results: Kết quả từng bước, theo thứ tự đã chạy.

    Returns:
        Id đề, hoặc chuỗi rỗng khi lượt này không đụng tới đề nào.
    """
    for result in reversed(results):
        found = result.get("assessment_id")
        if isinstance(found, str) and found:
            return found
    return ""


async def _count_questions(session: AsyncSession, assessment_id: str) -> tuple[int, int, int]:
    """Đếm `(đã có, xin bao nhiêu, còn đang soạn)` câu của một đề.

    Đếm từ **database**, không đếm từ số tiếng chuông đã nghe: chuông có thể mất, và một vị
    trí thử lại rung hai lần. Một con số dựng từ số lần nghe là đúng loại con số mà ADR-25
    mở đầu bằng cách phê phán.

    Args:
        session: Session của database.
        assessment_id: Đề nào.

    Returns:
        Ba con số. Không có brief thì `xin bao nhiêu` là 0 — hàm này đếm theo id, nó không
        kiểm đề có tồn tại hay không.
    """
    written = await session.scalar(
        select(func.count()).select_from(Question).where(Question.assessment_id == assessment_id)
    )
    brief = await session.get(DraftBrief, assessment_id)
    running = await pending_count(session, assessment_id)
    counted = int(written or 0), int(brief.question_count if brief else 0), running
    # Thả connection ra ngay. Ba câu select này mở một transaction, và chỗ gọi nó rồi đứng
    # đợi tiếng chuông kế tiếp -- hàng chục giây một connection Postgres nằm `idle in
    # transaction`, nhân với số tab đang mở. Cùng luật mà vòng lặp tool đã giữ sau mỗi bước.
    await session.rollback()
    return counted


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

        written, asked_for, running = await _count_questions(session, assessment_id)
        if running == 0:
            # Không có gì để đợi: hoặc vòng soạn chưa mở được, hoặc nó đã xong trước cả
            # tiếng chuông đầu tiên. Cả hai đều không phải lỗi.
            return
        yield TurnEvent(kind="progress", index=written, total=asked_for, conversation_id=thread)

        async for _ in bells:
            await harvest(session, pool, settings, assessment_id)
            now, asked_for, running = await _count_questions(session, assessment_id)
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
        written, asked_for, _ = await _count_questions(session, assessment_id)
        yield TurnEvent(kind="progress", index=written, total=asked_for, conversation_id=thread)


async def run_turn(
    said: "Said",
    request: Request,
    teacher: Teacher,
    session: AsyncSession,
    settings: Settings,
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
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database mà mọi tool chạy trên đó.
        settings: Cung cấp `max_tool_steps` và ngân sách thời gian của pha 1.
        watching: Có ai đang xem không. True thì lượt **đợi** các câu hỏi về trước khi để
            model kể lại, và phát `progress` mỗi lần có thêm câu. Cửa `POST` để False: nó
            rút cạn generator trong một request, và một request đứng chờ hàng phút sẽ bị
            cắt ở đâu đó giữa đường.

    Yields:
        Từng `TurnEvent` theo thứ tự xảy ra. Sự kiện cuối luôn là `done`.

    Raises:
        HTTPException: 404 khi đoạn chat không phải của giáo viên này (ADR-22), 503 khi
            không với tới được AGENT chút nào.

    Side effects:
        Ghi mọi bước của lượt vào hội thoại và commit từng bước; chạy các tool.
    """
    asking = Asking.of(teacher)
    planning = catalog_for(asking, PHASE_PLAN)
    working = catalog_for(asking, PHASE_WORK)

    if said.conversation_id is not None:
        thread = await _owned_conversation(session, asking, said.conversation_id)
        # Một đoạn chat không tồn tại và một đoạn của người khác nhận cùng một câu trả lời
        # (ADR-22). `404` chứ không phải mở hộ một đoạn mới: gõ nhầm id rồi được nói vào
        # một nơi khác là mất câu vừa gõ ở một chỗ không ai đi tìm.
        if thread is None:
            raise HTTPException(status_code=404, detail="không tìm thấy đoạn chat này")
    else:
        thread = await _conversation(session, asking, start_new=said.start_new)

    stored = await _stored_turns(session, thread)
    # Vị trí kế tiếp đọc từ **số thứ tự lớn nhất**, không từ số dòng. Hai con số ấy chỉ bằng
    # nhau khi dãy liền mạch từ 0, và một dãy không liền mạch thì `began` tụt lại phía sau:
    # câu trả lời của lượt này sẽ chở theo mấy dòng của lượt trước, client ghép thêm vào
    # những dòng nó đã vẽ, và cùng một câu hiện hai lần. Đo thấy trên trình duyệt thật.
    position = stored[-1].sequence + 1 if stored else 0
    began = position

    history = _as_records(stored)
    history.append(TurnRecord(kind="teacher", text=said.text))
    position = await _record(session, thread, position, history[-1])

    offered: list[str] = []
    offered_more = 0
    deadline = asyncio.get_running_loop().time() + settings.turn_budget_seconds
    plan: tuple[PlanStep, ...] = ()

    # ---------------------------------------------------------------- pha 1: lên plan
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
            step = await _ask_agent(request, settings, asking.full_name, planning, working, history)
        except AgentError as unreachable:
            logger.warning("agent unreachable for %s: %s", asking.teacher_code, unreachable)
            raise HTTPException(status_code=503, detail=_AGENT_UNAVAILABLE) from unreachable

        spent_ms = int((time.monotonic() - started) * 1000)

        if step.kind in {"say", "ask_clarify"}:
            # Các phương án chỉ đi cùng một **câu hỏi lại**. Bản đầu gửi chúng cho cả `say`,
            # và ca đó có thật: giáo viên hỏi *"lớp 12 thế nào"*, `find_class` trả hai
            # candidate, rồi model **nói** chứ không hỏi. Một lời thông báo mang theo hai cái
            # nút thì màn hình dựng nó thành thẻ hỏi lại, gấp bong bóng thật đi, và bấm một
            # nút gửi `"12A (3 học sinh)"` đi như một câu của giáo viên. Đường live đã sai
            # như vậy từ trước; từ khi có cột trong database thì nó còn sống qua cả F5 — nên
            # chỗ chặn phải là đây, nơi duy nhất biết `step.kind`.
            asking_back = step.kind == "ask_clarify"
            bare: list[str] = []
            history.append(TurnRecord(kind="assistant", text=step.text))
            position = await _record(
                session,
                thread,
                position,
                history[-1],
                duration_ms=spent_ms,
                model_tokens=step.model_tokens,
                choices=offered if asking_back else bare,
                more_choices=offered_more if asking_back else 0,
            )
            if step.choices:
                # Bỏ qua, không phải lọc lại. BE là bên giữ các row; thứ model viết ra ở
                # đây tốt nhất cũng chỉ là một bản sao, còn tệ nhất là một thứ bịa ra.
                logger.info(
                    "ignored %d model-written choice(s) for %s",
                    len(step.choices),
                    asking.teacher_code,
                )
            yield TurnEvent(
                kind="clarify" if asking_back else "say",
                text=step.text,
                choices=tuple(offered) if asking_back else (),
                more_choices=offered_more if asking_back else 0,
                conversation_id=thread,
            )
            if began == 0:
                await _name_the_thread(session, request, settings, thread, said.text)
            yield TurnEvent(
                kind="done",
                text=step.text,
                choices=tuple(offered) if asking_back else (),
                more_choices=offered_more if asking_back else 0,
                conversation_id=thread,
                ended_as="clarify" if asking_back else "say",
                began=began,
            )
            return

        if step.kind == "plan":
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
                        model_tokens=step.model_tokens,
                    )
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
                position = await _record(session, thread, position, history[-1])
                yield TurnEvent(
                    kind="plan",
                    total=len(plan),
                    conversation_id=thread,
                    titles=tuple(one.title for one in plan),
                )
                break

            # Plan hỏng thì **không bước nào chạy**, và giáo viên nhận một câu nói chứ
            # không phải một bước đỏ: với họ, chưa có gì xảy ra cả.
            logger.warning("refused a plan for %s: %s", asking.teacher_code, wrong)
            history.append(TurnRecord(kind="assistant", text=_PLAN_REFUSED))
            position = await _record(session, thread, position, history[-1])
            yield TurnEvent(kind="say", text=_PLAN_REFUSED, conversation_id=thread)
            if began == 0:
                await _name_the_thread(session, request, settings, thread, said.text)
            yield TurnEvent(
                kind="done",
                text=_PLAN_REFUSED,
                conversation_id=thread,
                ended_as="say",
                began=began,
            )
            return

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
                pool=getattr(request.app.state, "queue_pool", None),
                settings=settings,
                phase=PHASE_PLAN,
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
                )
            }
        except Exception:
            # Mọi sự cố khác cũng vậy, và cũng vì đúng lý do đó. Một tool hỏng không phải
            # là trợ lý hỏng: model có thể nói "mình chưa tra được" và giáo viên có thể
            # hỏi chuyện khác, và đó là một lượt tốt hơn một lỗi 500 không có chữ tiếng
            # Việt nào trong đó.
            logger.exception("tool %r failed for %s", step.tool_name, asking.teacher_code)
            result = {"error": f"tool {step.tool_name} chạy không xong"}
        finally:
            # Thả connection ra giữa các bước. Không có dòng này thì một session giữ một
            # connection lấy từ pool -- và một transaction Postgres nằm không -- xuyên qua
            # mọi lần đợi `run_task` trong cả lượt.
            await session.rollback()

        # Thay hẳn, không gộp vào. Giữ lại candidate của tool trước nghĩa là một câu hỏi
        # về chuyện khác đến nơi mà vẫn còn dính chúng.
        offered, offered_more = _offered(result)
        history.append(TurnRecord(kind="tool_result", tool_name=step.tool_name, tool_result=result))
        position = await _record(session, thread, position, history[-1])

    if not plan:
        # Mức trần. Chạm tới, không phải đâm vào: giáo viên nhận được một câu gọi tên
        # nguyên nhân và gợi ý đúng một việc có ích.
        logger.warning(
            "tool loop hit %d steps for %s", settings.max_tool_steps, asking.teacher_code
        )
        history.append(TurnRecord(kind="assistant", text=_CEILING_REACHED))
        await _record(session, thread, position, history[-1])
        yield TurnEvent(kind="say", text=_CEILING_REACHED, conversation_id=thread)
        if began == 0:
            await _name_the_thread(session, request, settings, thread, said.text)
        yield TurnEvent(
            kind="done",
            text=_CEILING_REACHED,
            conversation_id=thread,
            ended_as="say",
            began=began,
        )
        return

    # ------------------------------------------------------------ pha 2: chạy plan
    done: list[dict] = []
    outcomes: list[StepOutcome] = []
    for index, step_of_plan in enumerate(plan, start=1):
        try:
            args = resolve_args(step_of_plan.args, done)
        except Unresolvable as missing:
            # `str(missing)` gọi tên field và trích nguyên văn cú pháp tham chiếu --
            # "bước 1 trả về assessment_id rỗng". Đó là chữ để một người sửa lỗi đọc trong
            # log, không phải chữ để giáo viên đọc trên màn hình, và nó cũng không được đi
            # vào prompt của lời kể: model sẽ nhắc lại nguyên văn.
            logger.warning("step %d of a plan could not resolve: %s", index, missing)
            outcomes.append(
                StepOutcome(title=step_of_plan.title, ok=False, detail=_COULD_NOT_CARRY_OVER)
            )
            yield TurnEvent(
                kind="step_failed",
                title=step_of_plan.title,
                detail=_COULD_NOT_CARRY_OVER,
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
        opening_a_round = watching and step_of_plan.tool_name == "start_drafting"
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
                )
            except UnknownTool:
                held["result"] = {"error": f"không có tool nào tên {step_of_plan.tool_name}"}
            except Exception:
                logger.exception("step %d of a plan failed for %s", index, asking.teacher_code)
                held["result"] = {"error": f"bước {index} chạy không xong"}
            finally:
                await session.rollback()

        detail = ""
        if paper:
            # Một khối: subscribe → chạy bước (đẩy job) → nghe chuông → thu hoạch. Các câu
            # đang được viết trong lúc bước này vẫn **đang mở**, và ADR-25 nói số câu là tiến
            # độ bên trong MỘT bước, không phải một con số thứ hai ở đâu khác.
            async for event in _wait_for_questions(
                request, session, settings, paper, thread, start=run_the_step
            ):
                yield event
            result = held.get("result", {"error": f"bước {index} chạy không xong"})
            if not _went_wrong(result):
                # `_count_questions` **thả connection** khi đếm xong. An toàn ở đây vì mọi
                # thứ trước nó đã commit (`_record` và `harvest` tự commit cả hai) -- nhưng
                # một caller tương lai có việc chưa commit thì sẽ mất nó, nên đừng gọi hàm
                # ấy giữa một chuỗi ghi.
                counted_now = await _count_questions(session, paper)
                detail = _how_many(counted_now)

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
        else:
            await run_the_step()
            result = held.get("result", {"error": f"bước {index} chạy không xong"})

        history.append(
            TurnRecord(kind="tool_result", tool_name=step_of_plan.tool_name, tool_result=result)
        )
        position = await _record(session, thread, position, history[-1])
        done.append(result)

        broke = _went_wrong(result)
        if not detail:
            detail = _said_about(result)

        outcomes.append(StepOutcome(title=step_of_plan.title, ok=not broke, detail=detail))
        yield TurnEvent(
            kind="step_failed" if broke else "step_done",
            title=step_of_plan.title,
            detail=detail,
            index=index,
            total=len(plan),
            conversation_id=thread,
        )
        if broke:
            # Dừng plan. Chạy tiếp một bước dựa trên một bước vừa hỏng là làm việc trên
            # một thế giới không còn như plan tưởng.
            break

    # ------------------------------------------------------------ model kể lại kết quả
    #
    # Việc **đợi** nằm trong vòng lặp trên, ở đúng bước đã mở nó. Chỗ này chỉ đếm, và đếm
    # trên **cả hai** cửa: một lời kể không biết đề có bao nhiêu câu thì không nói được gì
    # về việc vừa làm, mà ba câu query thì cửa nào cũng trả nổi. Thứ chỉ cửa SSE làm là
    # đứng chờ -- cửa `POST` rút cạn generator này bên trong một request, và bắt một request
    # HTTP đợi hàng phút là cách chắc chắn nhất để một proxy cắt nó giữa chừng.
    paper = _paper_in(done)
    counted = await _count_questions(session, paper) if paper else (0, 0, 0)

    telling = await _report(request, settings, said.text, outcomes, counted)
    history.append(TurnRecord(kind="assistant", text=telling))
    await _record(session, thread, position, history[-1])
    yield TurnEvent(kind="report", text=telling, conversation_id=thread)
    if began == 0:
        await _name_the_thread(session, request, settings, thread, said.text)
    yield TurnEvent(
        kind="done", text=telling, conversation_id=thread, ended_as="report", began=began
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
        HTTPException: 404 cho một đoạn chat không phải của mình, 503 khi không với tới
            được AGENT.
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
                # 404/503 không còn gửi được bằng status code: header đã đi rồi. Gửi nó
                # thành một sự kiện để màn hình nói ra được, thay vì đứng im tới timeout.
                yield _as_sse(TurnEvent(kind="done", text=str(refused.detail), ended_as="error"))
            except Exception:
                logger.exception("a streamed turn broke for %s", teacher.teacher_code)
                yield _as_sse(TurnEvent(kind="done", text=_TURN_BROKE, ended_as="error"))

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
        return _read_back(thread, list(stored))

    # Có chủ đích không dùng `_conversation`: hàm đó mở một luồng mới khi chưa có luồng
    # nào, và một GET mà ghi dữ liệu là một GET mà một lần prefetch của browser, một cú dò
    # HEAD hay một lần retry có thể nhân lên. Một giáo viên chưa nói gì bao giờ thì có một
    # hội thoại rỗng, và đó đúng là điều mà một danh sách rỗng nói ra.
    thread = await _latest_conversation(session, asking)
    if thread is None:
        return Answered(kind="say", text="", turns=[])

    stored = await _stored_turns(session, thread)
    return _read_back(thread, list(stored))


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
