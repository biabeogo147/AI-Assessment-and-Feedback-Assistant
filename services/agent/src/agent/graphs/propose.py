"""Pha lên plan của một lượt chat giáo viên: dựng prompt, rồi chọn.

Module này là **pha 1** của ADR-25. Nó tra cứu, hỏi lại, và khi đã đủ dữ kiện thì nêu một
plan — chứ không bao giờ ghi gì. Lời kể sau khi plan chạy nằm ở `reporting.py`, một task
riêng, vì đầu vào của nó khác hẳn: nó đọc kết quả của cả plan, không đọc catalog.

Hai danh mục tới riêng và điều đó là cố ý: `catalog` là tool gọi được ngay, `plannable` là
tool chỉ hẹn làm được ở pha 2. Model phải thấy cả hai — nó nêu tên tool và tên tham số
trong plan — nhưng phải phân biệt được chúng, vì gọi một tool ghi ngay lượt này sẽ bị BE
từ chối và tiêu một vòng để phát hiện lại đúng điều ấy.

Hai node, và node thứ hai là một lần gọi structured duy nhất. Nó nhỏ hơn graph soạn
đề một cách có chủ ý -- ở đây không có loop tự check, vì thứ được sinh ra không phải
nội dung ai cũng xác thực được. Một đề nghị thì hoặc được BE thực thi hoặc bị BE từ
chối, và BE là phía duy nhất biết được là cái nào.

Thứ module này cẩn thận với là prompt. Model đang chọn từ một danh sách tool nó chưa
từng thấy và đọc dữ liệu nó không tự lấy, nên cả hai phải tới dưới dạng nó làm việc
được: tên tool viết đúng chính xác như cách BE dispatch, và kết quả tool ở dạng dữ
liệu chứ không phải văn xuôi kể về dữ liệu.

System prompt mang ba luật không phải chuyện văn phong. AGENT không được nhận là mình
đã làm gì -- nó đề nghị, BE hành động (ADR-05). Nó không được nói với giáo viên nên
chọn phương án nào khi lựa chọn đó là một quyết định sư phạm, vì giáo viên giữ thẩm
quyền ấy. Và nó hỏi lại chứ không đoán khi một cái tên có thể mang nhiều nghĩa, đó là
cổng kiểm đầu vào của ADR-05.

Từ plan 4a, prompt là **lõi + skill**. `_CORE` mang những luật không lượt nào được thiếu; lời dặn
chỉ một loại việc cần -- tra lớp, soạn đề -- nằm trong `agent/skills/*.md`, và `skill_router` (Jev)
chọn skill nào được nạp trước khi graph chạy.
"""

import json
import logging
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from agent import llm, skill_router, skills
from agent.latex_escapes import restore_latex_escapes
from contracts import NextStepCompleted, NextStepRequested, PlanStep, ToolSpec, TurnRecord

logger = logging.getLogger(__name__)


_CORE = r"""Bạn là trợ lý Kriky, làm việc cùng giáo viên phổ thông Việt Nam.

Lượt này bạn đang ở PHA LÊN PLAN. Bạn tra cứu, hỏi lại, và khi đã đủ dữ kiện thì nêu một plan —
danh sách những việc sẽ làm. Hệ thống chạy plan ấy ở pha sau, rồi hỏi bạn kể lại kết quả.

Mỗi lượt bạn chọn ĐÚNG MỘT trong bốn việc:
- say: trả lời bằng lời. Dùng khi câu vừa rồi chỉ cần một câu trả lời, không cần làm gì.
- call_tool: nhờ hệ thống chạy một tool TRA CỨU trong danh sách "tool dùng ngay", rồi bạn sẽ được
  hỏi lại với kết quả. Dùng khi bạn cần dữ liệu mà mình chưa có.
- ask_clarify: hỏi lại giáo viên. CHỈ dùng khi thiếu một tham số BẮT BUỘC của tool bạn sắp nêu,
  hoặc khi câu vừa rồi có thể hiểu theo nhiều cách. Một câu hỏi dạng CÓ/KHÔNG — "bạn có muốn…",
  "bạn có cần…", "mình đặt tên nhé?" — KHÔNG BAO GIỜ là ask_clarify: nó không lấp một chỗ trống
  nào, nó chỉ bắt giáo viên gõ thêm một lượt. Nếu bạn định hỏi một câu mà câu trả lời "tuỳ bạn"
  cũng xong việc, thì đừng hỏi, cứ làm.
- plan: nêu các việc sẽ làm, mỗi việc một tool trong danh sách "tool nêu được trong plan". text là
  câu bạn nói với giáo viên trước khi bắt tay, ví dụ "Được, mình soạn đề ngay."

Về plan:
- Các bước chạy TUẦN TỰ và một bước hỏng thì DỪNG cả plan. Vì thế plan phải đủ: khi xong, việc
  giáo viên nhờ phải XONG trọn, không dừng ở nửa đường.
- title của mỗi bước là câu tiếng Việt giáo viên đọc trên màn hình: "Tạo đề trống", "Soạn 10 câu
  hỏi". Nói VIỆC, đừng nói tên tool.
- Một tham số lấy giá trị từ kết quả của bước trước thì viết là {k.ten_field}, với k là số thứ tự
  bước, đếm từ 1. Ví dụ bước 2 cần id của đề mà bước 1 vừa mở: assessment_id = {1.assessment_id}.
  Chỉ viết đúng khuôn đó, không thêm chữ nào quanh nó, và chỉ trỏ về một bước ĐỨNG TRƯỚC nó.
- Một plan là một lời hứa, nên đừng nêu plan khi còn thiếu một mục bắt buộc — hỏi trước. Sau khi
  plan đã nêu thì KHÔNG còn chỗ nào để hỏi lại nữa.
- TUYỆT ĐỐI không nêu một tool tra cứu trong plan, và không gọi call_tool với một tool chỉ nêu
  được trong plan. Hai danh sách là hai quyền khác nhau.

Bốn điều không thương lượng:
- Bạn KHÔNG tự làm gì cả. call_tool là một lời đề nghị; hệ thống mới là người chạy. Vì thế TUYỆT ĐỐI
  không nói rằng bạn đã tạo, đã sửa, đã phát hành, đã lưu — chừng nào kết quả tool chưa nói vậy.
- ask_clarify chỉ để hỏi THÔNG TIN còn thiếu, trước một việc còn sửa lại được. TUYỆT ĐỐI không dùng
  nó để xin phép một việc không thu hồi được. Phát hành đề, xoá dữ liệu, đặt lại mật khẩu — những
  việc đó đi qua biểu mẫu riêng và hộp xác nhận, không bao giờ qua khung chat. Câu "phát hành cho
  lớp nào?" cũng vậy: đừng đưa lựa chọn, hãy nói rằng việc phát hành làm ở biểu mẫu phát hành.
- Khi việc phải chọn là quyết định sư phạm — chọn nguồn câu hỏi, chọn độ khó — bạn đưa thông tin và
  KHÔNG đánh dấu phương án nào là nên chọn. Giáo viên có thẩm quyền đó.
- Không đoán khi một cái tên có thể trỏ tới nhiều thứ. Hỏi lại, và chỉ đưa những lựa chọn có trong
  dữ liệu bạn được cấp. Không bịa tên lớp, tên đề hay con số nào.

Hai việc bạn KHÔNG làm được, và không có tool nào cho chúng: duyệt đề, và phát hành đề. Giáo viên tự
làm ở panel bên phải. Nếu họ nhờ bạn duyệt hay phát hành, hãy nói rằng chỗ làm việc đó là panel và
biểu mẫu phát hành — đừng hứa, và đừng nói là đã làm.

Cách viết:
- Tiếng Việt, gọn, như nói với đồng nghiệp. Tự gọi mình là "mình", gọi giáo viên là "bạn".
- KHÔNG dùng Markdown: không **in đậm**, không *nghiêng*, không `mã`, không bảng.
- Toán viết trong cặp `$`: `$y = x^3 - 3x$`, `$\int_0^1 (3x^2 - 2x + 1)\,dx$`, `$\frac{1}{3}$`.
  Màn hình dựng hình phần nằm giữa hai dấu `$`. Chữ thường thì viết thường, **đừng** bọc
  cả câu trong `$`. Và đừng dùng dấu ngoặc kiểu \( \) hay \[ \] — chỉ `$`."""


class _NothingToSay(ValueError):
    """Model chọn `say` hay `ask_clarify` mà để `text` rỗng."""


# Câu nói khi model hai lần liền để trống lời. Trung tính có chủ ý: **không** lùi về mock của
# `handlers.next_step`, vì mock đoán việc bằng từ khoá và đoán sai đúng ca đo được -- *"ra đề Toán
# lớp 10 về mệnh đề"* thành câu hỏi *"bạn muốn xem lớp nào?"* (review A1). Một câu hỏi sai việc
# trông như hợp lệ và kéo cả đoạn chat lạc hướng; một câu nhờ nói lại thì không.
_UNCLEAR = "Mình chưa rõ ý bạn lắm. Bạn nói lại giúp mình nhé?"


class _Argument(BaseModel):
    """Một argument của tool, dưới dạng một tên và một giá trị.

    Một cặp chứ không phải một mapping, vì mapping với key tuỳ ý là một JSON object
    mở và structured output ở chế độ strict từ chối những thứ đó. Giá trị là string:
    mọi argument các tool nhận hôm nay đều là string, và một union có kiểu ở đây sẽ
    là một nhánh schema mà model phải chọn giữa, chẳng được lợi gì.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    value: str


class _Step(BaseModel):
    """Một bước của plan, dưới hình dạng model trả lời được.

    Cùng lý do với `_Argument`: `args` là một dãy cặp tên–giá trị chứ không phải một mapping, vì
    một JSON object với key tuỳ ý bị structured output chế độ strict từ chối. `contracts.PlanStep`
    mới là hình dạng BE đọc, và `completed` dịch sang nó.
    """

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    args: tuple[_Argument, ...] = ()
    title: str


def _unmangled(proposal: "_Proposal") -> "_Proposal":
    r"""Trả lại dấu gạch chéo mà bộ giải mã JSON đã nuốt của lời model nói.

    **Chỗ thứ hai, cùng một hỏng hóc.** `authoring` không phải ống structured-output duy
    nhất: `_Proposal.text` cũng ra từ `with_structured_output`, cũng đi qua cùng bộ giải mã
    JSON, và cũng kết thúc trong `<MathText>` -- `Chat.tsx` dựng hình nó ở năm chỗ
    (`block.said`, `live.opening`, `live.report`, `said.opening`, `said.conclusion`).

    Nghĩa là Kriky giải thích một công thức trong khung chat thì `\frac` thành form-feed y
    hệt, rồi luật pandoc `\$(?![\s$])` từ chối nhận cả cụm là toán và dấu đô la lọt ra màn
    hình. Cùng nguyên nhân, cùng hậu quả, cùng người nhìn thấy (ADR-26).

    `title` của mỗi bước plan cũng đi qua: nó hiện trong khối bước ngay dưới câu Kriky nói.
    `tool_name` và `args` thì **không** -- chúng là identifier và giá trị, không phải chữ
    cho người đọc, và một dấu gạch chéo mọc thêm trong đó là một id hỏng.

    Args:
        proposal: Thứ model vừa trả lời, ngay sau khi qua bộ giải mã JSON.

    Returns:
        Một bản mới với mọi chữ dành cho người đọc đã dựng lại.
    """
    return proposal.model_copy(
        update={
            "text": restore_latex_escapes(proposal.text),
            "steps": tuple(
                step.model_copy(update={"title": restore_latex_escapes(step.title)})
                for step in proposal.steps
            ),
        }
    )


class _Proposal(BaseModel):
    """Đúng những gì model được hỏi -- và không gì khác.

    Cố ý không phải `NextStepCompleted`. Type đó là hợp đồng giữa các service và mang
    hai field không model nào trả lời được: `request_id`, do BE phát ra, và
    `model_tokens`, do provider báo lại sau đó. Đưa cả hợp đồng cho
    `with_structured_output` đặt cả hai field ấy trước mặt model như hai câu hỏi, và
    biến `tool_args` -- một `dict[str, object]` -- thành một object mở mà OpenAI từ
    chối thẳng:

        400 Invalid schema for response_format: In context=('properties',
        'tool_args'), 'additionalProperties' is required to be supplied and to
        be false.

    Thế là mọi lần gọi thật đều thất bại rồi lùi về nội dung dọn trước, với độ trễ
    trông như thật và một câu trả lời nghe hợp lý che đi chuyện đó. Schema này là bản
    sửa và cũng là bài học: một field trong schema là một câu hỏi đặt ra cho model,
    nên chỉ hỏi những gì nó trả lời được, và đóng kín mọi object.
    """

    model_config = ConfigDict(extra="forbid")

    # **Đứng trước `kind`, có chủ ý** (plan 4a, 12/10/2026). Model sinh JSON từ trái sang phải, nên
    # field đầu tiên là quyết định đầu tiên. Khi `kind` đứng đầu, gpt-4o-mini chọn hỏi lại trước khi
    # kịp đọc ra các mục đã có -- *"Tạo đề … chương Hàm số cho lớp 12A, 10 câu"* hỏi lại 8/8 lần
    # dù prompt dặn nêu plan ngay, và đổi chữ ở lõi, skill, mô tả tool đều 0/6. Bắt nó ghi ra thứ đã
    # biết trước thì 4/6. Không rời AGENT: `completed` bỏ nó đi, chỉ log giữ lại.
    known: str = Field(
        default="",
        description=(
            "Ghi chú cho chính bạn, giáo viên KHÔNG đọc: những gì đã biết từ lời giáo viên và kết "
            "quả tool, và còn thiếu gì cho việc họ nhờ. Không viết câu hỏi hay câu trả lời ở đây."
        ),
    )
    kind: Literal["say", "call_tool", "ask_clarify", "plan"]
    text: str = Field(
        default="",
        description=(
            "Câu giáo viên đọc trên màn hình. Với ask_clarify, đây là câu hỏi. Không được rỗng với "
            "say và ask_clarify."
        ),
    )
    tool_name: str = ""
    tool_args: tuple[_Argument, ...] = ()
    steps: tuple[_Step, ...] = ()

    def completed(self, request_id: str, model_tokens: int) -> NextStepCompleted:
        """Biến câu trả lời của model thành message BE đọc.

        Args:
            request_id: Id BE đã hỏi dưới.
            model_tokens: Con số provider báo lại.

        Raises:
            ValidationError: Khi model nói `plan` mà không nêu bước nào, hoặc nêu một bước không có
                tên tool. Handler ở tầng trên bắt và lùi về mock -- chưa có gì tới tay giáo viên
                lúc này, nên lùi về là an toàn.

        Returns:
            Đề nghị, kèm hai field model không bao giờ được hỏi. `steps` chỉ đi theo một `plan`,
            vì hợp đồng từ chối chúng ở mọi `kind` khác. `choices` để rỗng:
            BE tự viết các lựa chọn cho một câu hỏi lại từ những dòng nó đã đọc
            (ADR-23), nên hỏi model lấy chúng là hỏi một thứ rồi bị ném đi.
        """
        return NextStepCompleted(
            request_id=request_id,
            kind=self.kind,
            text=self.text,
            tool_name=self.tool_name,
            tool_args={argument.name: argument.value for argument in self.tool_args},
            steps=tuple(
                PlanStep(
                    tool_name=step.tool_name,
                    args={argument.name: argument.value for argument in step.args},
                    title=step.title,
                )
                for step in self.steps
            )
            if self.kind == "plan"
            else (),
            model_tokens=model_tokens,
        )


class ProposeState(TypedDict):
    """Những gì chảy qua hai node.

    Attributes:
        request: Cuộc hội thoại và danh mục tool.
        skills: Tên các skill nạp cho lượt này, do `skill_router` chọn trước khi graph chạy.
        messages: Những gì model thấy, do `compose` điền.
        step: Đề nghị, do `choose` điền.
    """

    request: NextStepRequested
    skills: tuple[str, ...]
    messages: Annotated[list[BaseMessage], lambda old, new: new]
    step: NextStepCompleted | None


def _describe_tool(tool: ToolSpec) -> str:
    """Viết một tool ra để model chọn.

    Args:
        tool: Tool đúng như BE mô tả nó.

    Returns:
        Một khối gọi tên tool chính xác như cách BE dispatch, rồi tới việc nó làm,
        rồi tới các argument của nó.
    """
    lines = [f"- {tool.name}: {tool.description}"]
    for argument, meaning in tool.arguments.items():
        lines.append(f"    {argument}: {meaning}")
    return "\n".join(lines)


def _describe_result(turn: TurnRecord) -> str:
    """Viết kết quả tool ra dưới dạng dữ liệu, không phải một câu kể về dữ liệu.

    JSON chứ không phải văn xuôi, vì model phải đọc các giá trị ra từ đó -- một id nó
    sẽ truyền cho tool tiếp theo, một con số nó sẽ dẫn lại cho giáo viên. Văn xuôi mời
    gọi việc làm tròn và mời gọi việc bịa.

    Args:
        turn: Một lượt `tool_result`.

    Returns:
        Một dòng gọi tên tool, rồi kết quả của nó dưới dạng JSON.
    """
    body = json.dumps(turn.tool_result, ensure_ascii=False, sort_keys=True)
    return f"Kết quả của {turn.tool_name}:\n{body}"


def _compose(state: ProposeState) -> dict:
    """Biến request thành những message model thấy.

    Lịch sử hội thoại trở thành các message theo đúng thứ tự. Một lần gọi tool và kết
    quả của nó là nước đi của chính trợ lý và thứ nhận lại được từ nước đi đó, nên
    chúng được render thành một lượt assistant và một lượt human -- đó là hình dạng
    một chat model mong đợi, và là lý do model không đề nghị cùng một tool hai lần.

    Args:
        state: Mang theo request.

    Returns:
        Mảnh `messages` của state.
    """
    request = state["request"]

    # Lõi trước, rồi skill, rồi tên giáo viên: phần đứng đầu càng ít đổi giữa hai lượt thì prompt
    # cache của provider càng dùng lại được nhiều. Skill nằm **sau** lõi, nên không skill nào nói
    # trước được một luật an toàn.
    opening = [_CORE]
    for skill in skills.named(state["skills"]):
        opening.append(skill.body)
    if request.teacher_name:
        opening.append(f"Bạn đang nói với {request.teacher_name}.")
    if request.catalog:
        catalog = "\n".join(_describe_tool(tool) for tool in request.catalog)
        opening.append(f"Tool dùng ngay (call_tool) lượt này:\n{catalog}")
    else:
        # Nói ra điều đó tốt hơn bỏ hẳn phần này: một model không được cấp danh
        # sách nào thường cho rằng việc thiếu đó là sơ suất và vẫn gọi tên một tool.
        opening.append("Lượt này bạn không có tool dùng ngay nào.")
    if request.plannable:
        # Hai danh sách tới riêng, vì model phải phân biệt được "gọi được bây giờ" với "hẹn làm ở
        # pha sau". Trộn chúng lại là mời model gọi một tool ghi ngay lượt này -- BE từ chối, và
        # cái vòng lặp tiêu một lần gọi model để phát hiện lại đúng điều ấy.
        planning = "\n".join(_describe_tool(tool) for tool in request.plannable)
        opening.append(f"Tool nêu được trong plan (không gọi ngay):\n{planning}")
    else:
        # Không nhắc `call_tool` ở đây: khi `catalog` cũng rỗng thì dòng trên vừa nói là
        # không có tool nào, và một câu mời gọi tool ngay sau đó là một lời tự mâu thuẫn --
        # đúng loại chỗ model chọn câu nào nghe tích cực hơn.
        can_also = ", call_tool" if request.catalog else ""
        opening.append(f"Lượt này bạn không nêu plan được. Chỉ say{can_also} hoặc ask_clarify.")

    messages: list[BaseMessage] = [SystemMessage("\n\n".join(opening))]
    for turn in request.history:
        if turn.kind == "teacher":
            messages.append(HumanMessage(turn.text))
        elif turn.kind == "assistant":
            messages.append(AIMessage(turn.text))
        elif turn.kind == "tool_call":
            args = json.dumps(turn.tool_args, ensure_ascii=False, sort_keys=True)
            messages.append(AIMessage(f"Mình xin gọi {turn.tool_name} với {args}."))
        else:
            messages.append(HumanMessage(_describe_result(turn)))

    return {"messages": messages}


def _spent(raw: object) -> int:
    """Đọc số token mà provider báo, lấy từ một response thô.

    Args:
        raw: Bất cứ thứ gì provider trả về kèm theo đối tượng đã parse.

    Returns:
        Tổng số token, hoặc 0 khi provider không báo gì. Số 0 nghĩa là "không được
        cho biết", không phải "miễn phí": một model giả trong test không báo gì, và
        một số provider cũng vậy.
    """
    usage = getattr(raw, "usage_metadata", None)
    if isinstance(usage, dict):
        total = usage.get("total_tokens")
        if isinstance(total, int):
            return total
    return 0


async def _choose(state: ProposeState) -> dict:
    """Hỏi model một đề nghị, và ghi lại nó tốn bao nhiêu.

    `include_raw` là thứ làm cho chi phí biết được. Structured output một mình chỉ
    trả lại đối tượng đã parse rồi bỏ đi cái response nó đi trong, mà báo cáo usage
    thì nằm trên chính response đó -- nên lời khẳng định trong plan rằng ghi lại số
    token là "gần như miễn phí" đã sai: nó cần argument này và một field trong hợp
    đồng.

    Args:
        state: Mang theo các message đã dựng.

    Returns:
        Mảnh `step` của state, với `model_tokens` điền từ provider chứ không điền từ
        model.
    """
    model = llm.with_fallback(lambda chat: chat.with_structured_output(_Proposal, include_raw=True))
    answered = await model.ainvoke(state["messages"])

    # Một provider không làm được `include_raw` -- hoặc một fake bỏ qua nó -- trả
    # thẳng lại đối tượng đã parse. Cả hai hình dạng đều được hỗ trợ, vì số token chỉ là
    # thứ có thì tốt còn đề nghị thì không.
    if isinstance(answered, dict):
        parsed = answered["parsed"]
        if parsed is None:
            # `include_raw` biến một lần parse thất bại thành `parsed=None` cộng với
            # exception nằm dưới `parsing_error`, trong khi `include_raw=False` thì
            # đã raise nó kèm luôn đầu ra có vấn đề. Để nó đi qua là đổi một thông
            # báo gọi tên đầu ra xấu lấy một `AttributeError` trên None, mà cái đó
            # chẳng gọi tên gì cả.
            raise ValueError(
                f"model did not produce a usable proposal: {answered.get('parsing_error')}"
            )
        proposal: _Proposal = parsed
        spent = _spent(answered.get("raw"))
    else:
        proposal, spent = answered, 0

    logger.info("known before choosing %s: %s", proposal.kind, proposal.known)
    if proposal.kind in {"say", "ask_clarify"} and not proposal.text.strip():
        # Đo được khi thêm `known`: model viết câu hỏi vào ghi chú rồi để `text` rỗng. Một bong
        # bóng rỗng không bao giờ được tới màn hình; `propose` hỏi lại một lần.
        raise _NothingToSay(f"model chose {proposal.kind} with nothing to say")

    # `request_id` do `propose` điền, vì đó là chỗ duy nhất biết nó. Để rỗng ở đây sẽ
    # là một lời nói dối nếu nó còn ở lại, nên nó không ở lại.
    return {"step": _unmangled(proposal).completed(request_id="", model_tokens=spent)}


def _build() -> object:
    """Lắp graph.

    Returns:
        Một graph đã compile, nhận `ProposeState` và điền vào `step`.
    """
    graph = StateGraph(ProposeState)
    graph.add_node("compose", _compose)
    graph.add_node("choose", _choose)
    graph.set_entry_point("compose")
    graph.add_edge("compose", "choose")
    graph.add_edge("choose", END)
    return graph.compile()


_GRAPH = _build()


async def propose(request: NextStepRequested) -> NextStepCompleted:
    """Quyết định việc gì nên xảy ra tiếp theo trong cuộc hội thoại này.

    Args:
        request: Lịch sử tới lúc này và các tool giáo viên này được dùng.

    Returns:
        Một đề nghị. `request_id` bị ghi đè bằng id BE đã hỏi dưới: model không biết
        id đó, và một đề nghị mang theo một id nhắc lại hoặc bịa ra sẽ bị quy về job
        của một lượt khác.

    Raises:
        Exception: Bất cứ thứ gì provider raise. Handler ở tầng trên quyết định lùi
            về cái gì, vì chỉ nó biết liệu đã có thứ gì tới tay giáo viên hay chưa.
    """
    chosen = await skill_router.choose(request.history)
    state = {"request": request, "skills": chosen, "messages": [], "step": None}
    try:
        final = await _GRAPH.ainvoke(state)
    except _NothingToSay:
        # Một lần nữa, không hơn: lần trống thứ hai là model đang kẹt, không phải xui.
        logger.warning("empty answer for %s, asking once more", request.request_id)
        try:
            final = await _GRAPH.ainvoke(state)
        except _NothingToSay:
            logger.warning("empty answer twice for %s", request.request_id)
            return NextStepCompleted(request_id=request.request_id, kind="say", text=_UNCLEAR)
    step: NextStepCompleted = final["step"]
    logger.info("proposed %s for %s", step.kind, request.request_id)
    return step.model_copy(update={"request_id": request.request_id})
