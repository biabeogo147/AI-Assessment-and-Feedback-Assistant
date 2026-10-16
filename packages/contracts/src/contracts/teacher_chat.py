"""Một lượt suy nghĩ cho khung chat của giáo viên, không hơn.

Ba task authoring mỗi cái làm trọn một việc: soạn một đề, soạn câu hỏi của một vòng, trả lời một học
sinh. Task này thì không. Nó đọc một cuộc hội thoại rồi trả lời **việc gì nên xảy ra tiếp theo** --
nói câu này, gọi tool kia, hay hỏi lại một câu trước khi làm bất cứ gì. BE chạy vòng lặp và thực
hiện bước đó.

Chỗ phân chia ấy là toàn bộ thiết kế, và nó là lý do message trả về được đặt tên theo một
*proposal*. AGENT không giữ credential database nên không thể chạy một tool; và nó **không được
phép**, vì quyền hạn thuộc về nơi có session và danh tính của giáo viên. Thứ quay về từ đây là một
đề nghị mà BE được tự do từ chối -- và đó cũng là thứ làm cho luật của ADR-05 thành cấu trúc chứ
không phải một câu trong prompt: một trợ lý chỉ có thể đề nghị thì không phát hành được gì.

Chỉ dữ liệu, như mọi thứ ở đây. Có những tool nào, ai được gọi, và tham số của chúng nghĩa là gì là
việc của BE; module này chỉ chở lời.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1

# Tên task của arq. BE enqueue bằng chuỗi và không bao giờ import package AGENT.
PROPOSE_NEXT_STEP_TASK = "propose_next_step"


class ToolSpec(BaseModel):
    """Một tool, mô tả cho model đọc chứ không phải cho một caller đọc.

    BE dựng danh sách này theo từng request từ những việc giáo viên đang hỏi được phép làm, nên một
    tool mà giáo viên không dùng được thì không bao giờ được mô tả cho model. Đó là tiện lợi, không
    phải cái cổng: BE kiểm lại lúc thực thi, vì bản mô tả này do một model đọc, và model thì đọc
    sai.

    Attributes:
        name: Identifier mà BE dispatch theo.
        description: Tool làm gì, viết bằng đúng ngôn ngữ model đang trả lời, kể cả lúc nào thì
            *không* nên dùng nó.
        arguments: Mô tả tham số theo hình dạng JSON schema, dưới dạng một mapping thuần. Không phải
            một model pydantic, vì catalog được lắp lúc chạy và hình dạng khác nhau theo từng tool.
        optional: Tham số **không** bắt buộc trong một bước plan (`draft-from-document`:
            `create_draft` nhận tài liệu khi có). Mặc định rỗng -- mọi tham số đều bắt buộc, như
            luật của `vet_plan`; một tham số chỉ tuỳ chọn khi được khai ở đây, không bao giờ do
            đoán.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    arguments: dict[str, object] = Field(default_factory=dict)
    optional: tuple[str, ...] = ()


class PlanStep(BaseModel):
    """Một bước của plan: một việc sẽ làm, chưa làm.

    `args` chỉ chứa chuỗi, vì model chỉ trả về được chuỗi phẳng. Một tham số lấy giá trị từ kết quả
    của bước trước được viết là `{k.ten_field}` với `k` đếm từ 1 -- `start_drafting` cần một
    `assessment_id` mà `create_draft` mới sinh ra, và không có cú pháp ấy thì một plan hai bước phụ
    thuộc nhau không diễn tả được (ADR-25). **BE là bên duy nhất giải nó**, từ `tool_result` của
    bước được trỏ tới.

    `frozen=True` ở đây là **đóng băng nông**: không gán lại được field, nhưng `args` vẫn là một
    dict sửa được tại chỗ. Luật đi kèm: không ai giữ lại reference tới `args` của một bước rồi sửa
    nó sau; BE giải tham chiếu thành một dict **mới** trước khi đưa cho tool.

    Attributes:
        tool_name: Tool sẽ chạy. BE kiểm lại nó có trong catalog pha 2 hay không.
        args: Tham số, dạng chuỗi. Có thể chứa `{k.ten_field}`.
        title: Câu tiếng Việt hiện trên khối bằng chứng, ví dụ *"Tạo đề trống"*. Nó là thứ giáo
            viên đọc, nên nó nói việc chứ không nói tên tool.
    """

    model_config = ConfigDict(frozen=True)

    tool_name: str = Field(min_length=1)
    args: dict[str, str] = Field(default_factory=dict)
    title: str = Field(min_length=1, max_length=120)


class OutlineItem(BaseModel):
    """Một mục của dàn ý đề (ADR-29): một nhóm câu cùng kiến thức, công thức và cách làm.

    Kriky viết mục; BE kiểm, lưu, in nguyên văn ra chat, và khi giáo viên đồng ý thì mỗi job soạn
    câu nhận đúng một mục. Mục là thứ giáo viên **duyệt**, nên nó phải nói được câu ấy hỏi gì và
    giải ra sao -- *"câu 1 về hàm hằng"* thì không duyệt được gì.

    Hình dạng thôi; luật nội dung -- chữ không chỉ toàn khoảng trắng, trần độ dài, công thức nằm
    trong cặp `$`, nút nguồn có trong cây của tài liệu, tổng câu mỗi lần xin -- là của
    `be/outline.validate` (plan `draft-outline`), nơi có cây để so.

    Không có trường độ khó theo mục: tên ấy nằm trong mẫu tên cấm của
    `services/agent/tests/test_no_routing_decision.py`, và độ khó vẫn đi theo cả đề (`difficulty`
    của brief).

    Attributes:
        questions: Mục này phủ bao nhiêu câu. Hai câu chung một mục thì chung kiến thức nhưng phải
            khác cách hỏi -- job biết mình là câu thứ mấy của mục.
        knowledge: Kiến thức câu kiểm, viết sạch bằng lời của Kriky -- không phải chữ OCR chép lại.
        formulas: Công thức sẽ dùng, mỗi phần tử một công thức trong cặp `$`. Rỗng được, cho môn
            không có công thức.
        approach: Phương án làm bài: dạng câu và các bước giải dự kiến.
        source_nodes: `ordinal` các nút trong cây của tài liệu mà mục dựa vào. Rỗng khi đề không có
            tài liệu.
    """

    model_config = ConfigDict(frozen=True)

    questions: int = Field(ge=1, le=10)
    knowledge: str = Field(min_length=1)
    formulas: tuple[str, ...] = ()
    approach: str = Field(min_length=1)
    source_nodes: tuple[int, ...] = ()


class TurnRecord(BaseModel):
    """Một việc đã xảy ra trong cuộc hội thoại này.

    Lịch sử không chỉ gồm lời nói. Kết quả của một tool là một phần những gì model biết, nên nó đi
    thành một loại turn riêng thay vì bị dẹp thành văn xuôi -- dẹp đi nghĩa là model đọc một bản tóm
    tắt của dữ liệu thay vì đọc dữ liệu.

    Attributes:
        kind: Ai hay cái gì tạo ra turn này. `plan` là danh sách việc model vừa nêu ở cuối pha 1
            (ADR-25); nó được lưu như một turn vì `bước k/n` phải dựng lại được sau một lần F5, và
            một con số không có chỗ nào lưu là một con số chỉ đúng khi không ai tải lại trang.
            `outline` là một dàn ý đề Kriky vừa đề xuất (ADR-29): `text` là lời Kriky trình bày dàn
            ý (Markdown, ADR-30), `tool_result` chở chính các mục -- thứ duy nhất đi vào job, và
            thứ lượt sau model đọc lại cùng lời. `notice` là một thông báo của **hệ thống**, không
            phải lời Kriky -- khi model không trả lời được, hay lượt chạm trần bước (ADR-30, ngoại
            lệ 1); model đọc lại nó như một ghi chú, không như lời mình đã nói.
        text: Lời, cho turn `teacher`, `assistant` và `notice`; lời dàn ý cho turn `outline`.
        tool_name: Tool nào, cho `tool_call` và `tool_result`.
        tool_args: Tham số mà BE đã thực thi với.
        tool_result: Thứ tool trả về. BE đã tóm tắt sẵn: điểm của cả một lớp vừa không nhét nổi vào
            một prompt, vừa không cần nhét.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["teacher", "assistant", "tool_call", "tool_result", "plan", "outline", "notice"]
    text: str = ""
    tool_name: str = ""
    tool_args: dict[str, object] = Field(default_factory=dict)
    tool_result: dict[str, object] = Field(default_factory=dict)


class AttachedDocument(BaseModel):
    """Tài liệu giáo viên đính vào tin nhắn này (`draft-from-document`): chip đang nằm trong ô nhập.

    BE chỉ gửi nó khi tài liệu thuộc giáo viên; AGENT dùng `document_id` làm tham số cho tool đọc
    mục lục khi `state` là `ready`, `filename` để gọi tên tài liệu với giáo viên.

    Attributes:
        document_id: Id tài liệu.
        filename: Tên tệp như giáo viên thấy trên chip.
        state: Trạng thái tài liệu, giá trị của `DocumentState`. Khác `ready` thì chưa có mục lục
            nào để đọc: *đang xử lý* thì AGENT bảo chờ, *hỏng* hay *không đọc được chữ* thì
            AGENT nói tài liệu này không dùng được -- không soạn như thể không có chip (review
            B6, B7).
    """

    model_config = ConfigDict(frozen=True)

    document_id: str
    filename: str
    state: str = "ready"


class NextStepRequested(BaseModel):
    """Hỏi AGENT xem bước tiếp theo của cuộc hội thoại này nên là gì.

    Tự chứa, như mọi payload ở đây: catalog và lịch sử đi cùng request, vì AGENT không tra được cái
    nào trong hai thứ đó.

    Attributes:
        request_id: Id để đối chiếu, được trả lại nguyên.
        teacher_name: Cách gọi người đang hỏi. Không phải một identifier -- AGENT không bao giờ nhận
            một identifier mà nó sẽ phải tra, và danh tính dùng để phân quyền ở lại trong BE.
        history: Mọi thứ đã xảy ra, cũ nhất trước.
        catalog: Những tool model được **gọi** lượt này. Ở pha lên plan, danh sách này chỉ có tool
            đọc (ADR-25).
        plannable: Những tool model được **nêu trong một plan** nhưng chưa được gọi bây giờ. Không
            có nó thì pha 1 phải nêu tên và tham số của những tool nó chưa từng thấy mô tả, tức là
            đoán -- mà BE kiểm tên tham số theo spec và sẽ từ chối cả plan. Hai danh sách chứ không
            một, vì "được gọi ngay" và "được hẹn làm" là hai quyền khác nhau và trộn chúng lại là
            mở đúng cánh cửa ADR-25 đóng: ghi trước khi hỏi.
        attached_document: Tài liệu đính kèm tin nhắn mới nhất, `None` khi không có chip
            (`draft-from-document`). Tuỳ chọn, nên payload trước `draft-from-document` vẫn hợp lệ.

    Ở đây **không có** `stream_channel`, khác với `ExplainTurnRequested`. Một lượt của cuộc hội
    thoại này là một vòng lặp gồm vài lời gọi model và chỉ lời gọi cuối cùng sinh ra chữ, nên một
    channel mở từ lời gọi đầu sẽ chở sự im lặng trong gần cả lượt. Cái envelope sự kiện có thể nói
    "đang đọc lớp 12A1" là một việc riêng; một field không ai đọc sẽ là một lời hứa mà payload không
    giữ.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    teacher_name: str = ""
    history: tuple[TurnRecord, ...] = ()
    catalog: tuple[ToolSpec, ...] = ()
    plannable: tuple[ToolSpec, ...] = ()
    attached_document: AttachedDocument | None = None


class NextStepCompleted(BaseModel):
    """Thứ AGENT đề nghị làm tiếp.

    Đúng một trong năm hình dạng, chọn bằng `kind`:

    - `say`: trả lời bằng lời; `text` chở lời đó và lượt kết thúc.
    - `call_tool`: BE nên chạy `tool_name` với `tool_args`, rồi hỏi lại.
    - `ask_clarify`: chưa đủ thông tin để hành động; `text` là câu hỏi và `choices` là các lựa chọn
      model đề xuất. BE mới dựng nút: hỏi về một dòng thì chỉ chữ khớp đúng một dòng BE đã đọc được
      giữ (ADR-23, hậu ký `unbiased-model-text` T3). Lối "Khác" -- giáo viên tự ghi -- do FE vẽ.
    - `plan`: đã đủ thông tin để làm; `steps` là các bước ghi, theo thứ tự, và `text` là câu nói
      trước khi bắt tay (ADR-25). Pha 1 kết thúc ở đây và pha 2 mới chạy các bước ấy.
    - `outline`: một dàn ý đề cho giáo viên duyệt (ADR-29); `outline` là các mục -- thứ duy nhất
      đi vào job -- và `text` là **cả lời** Kriky trình bày dàn ý cho giáo viên (Markdown, ADR-30).
      Lượt kết thúc ở đây: BE đối chiếu nhẹ lời với các mục, lưu, in lời ra chat, và chỉ soạn ở một
      lượt **sau**.

    `ask_clarify` là cổng đầu vào của ADR-05, và luật của nó -- kể cả việc một câu hỏi làm rõ được
    phép và không được phép hỏi những gì -- nằm trong chính decision record đó, do BE thi hành. Chép
    lại ở đây là đặt một bản sao của luật nghiệp vụ vào một module dữ liệu, nơi nó sẽ cũ đi mà không
    có gì gãy để báo.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    kind: Literal["say", "call_tool", "ask_clarify", "plan", "outline"]
    text: str = ""
    tool_name: str = ""
    tool_args: dict[str, object] = Field(default_factory=dict)
    choices: tuple[str, ...] = ()
    steps: tuple[PlanStep, ...] = ()
    outline: tuple[OutlineItem, ...] = ()
    # `say` này là thông báo của **hệ thống**, không phải lời Kriky (ADR-30, ngoại lệ 1,
    # `kriky-writes-every-word`): model không trả lời được, nên AGENT nói một câu cố định, và BE lưu
    # nó thành lượt `notice`. Chỉ đi với `say`.
    notice: bool = False
    # Lời gọi tốn bao nhiêu, do AGENT điền từ báo cáo usage của chính nhà cung
    # cấp, **sau khi** model đã trả lời. Model không thể biết con số này, nên
    # bất cứ thứ gì nó viết vào đây đều bị ghi đè -- đúng cách `request_id`
    # được xử lý, và vì cùng một lý do.
    model_tokens: int = 0

    @model_validator(mode="after")
    def _a_tool_call_names_a_tool(self) -> "NextStepCompleted":
        """Từ chối một `call_tool` không có tool nào trong đó.

        Chuyện hình dạng, không phải chuyện chính sách: có những tool nào là việc của BE, nhưng một
        đề nghị gọi hư không thì không phải một đề nghị. Bắt ở đây vì đường còn lại là một vòng lặp
        dispatch theo một cái tên rỗng, nhận lại "không có tool đó", rồi tiêu hết trần số lời gọi
        model để phát hiện lại đúng điều ấy.

        Returns:
            Chính nó, khi message mạch lạc.

        Raises:
            ValueError: Khi `kind` là `call_tool` mà `tool_name` rỗng, khi `plan` mà không có bước
                nào, hoặc khi một `kind` khác lại chở `steps` -- cái cuối là để BE không phải nhớ
                bỏ qua chúng ở mọi nhánh, vì một luật phải nhớ là một luật sẽ quên. `outline` theo
                đúng luật ấy: `kind='outline'` phải có mục, kind khác không được chở mục.
        """
        if self.kind == "call_tool" and not self.tool_name.strip():
            raise ValueError("kind='call_tool' needs a tool_name")
        if self.kind == "plan" and not self.steps:
            raise ValueError("kind='plan' needs at least one step")
        if self.kind != "plan" and self.steps:
            raise ValueError("only kind='plan' may carry steps")
        if self.kind == "outline" and not self.outline:
            raise ValueError("kind='outline' needs at least one item")
        if self.kind != "outline" and self.outline:
            raise ValueError("only kind='outline' may carry outline items")
        if self.notice and self.kind != "say":
            raise ValueError("only kind='say' may be a system notice")
        return self


# Tên task của arq, cũng như trên: BE enqueue bằng chuỗi.
NAME_CONVERSATION_TASK = "name_conversation"


class ConversationNameRequested(BaseModel):
    """Đặt tên cho một đoạn chat, từ câu mở đầu của nó.

    Chở nguyên câu giáo viên đã gõ, không chở `conversation_id`. AGENT không giữ credential
    database nào và không bao giờ tra một hàng nào -- payload tự chứa là luật của cả package
    này, và ở đây nó cũng là thứ làm cho task này rẻ: một lời gọi model trên một chuỗi.

    Attributes:
        schema_version: Phiên bản hình dạng.
        request_id: Id của yêu cầu, dội lại trong câu trả lời.
        said: Câu đầu tiên giáo viên gõ trong đoạn chat ấy.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    said: str = Field(min_length=1, max_length=2000)


class ConversationNameCompleted(BaseModel):
    """Một cái tên ngắn cho đoạn chat.

    BE **không** tin con số dài: nó cắt và dọn trước khi lưu, vì một model trả về ba trăm ký
    tự hay một câu bọc trong dấu ngoặc kép là chuyện thường, và chỗ chuỗi này đi tới là một
    hàng rộng 228px trên rail.

    Attributes:
        schema_version: Phiên bản hình dạng.
        request_id: Dội lại từ yêu cầu.
        title: Cái tên. Rỗng nghĩa là model không đặt được, và BE lùi về câu đầu cắt ngắn.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    title: str = ""


# Tên task của arq, cũng như trên: BE enqueue bằng chuỗi.
REPORT_PLAN_TASK = "report_plan"


class StepOutcome(BaseModel):
    """Một bước của plan đã chạy, và nó ra sao.

    Attributes:
        title: Câu đã hiện trên khối bằng chứng, chép lại từ `PlanStep.title`.
        ok: Bước đó xong hay hỏng.
        detail: Con số hoặc lý do, bằng lời của BE. Rỗng khi không có gì đáng nói.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    ok: bool
    detail: str = ""


class PlanReportRequested(BaseModel):
    """Kể lại cho giáo viên những gì plan vừa làm.

    Payload tự chứa: nó chở câu giáo viên đã gõ và kết quả từng bước, không chở id nào để AGENT đi
    tra -- AGENT không có credential database.

    Đây là một task riêng chứ không phải một vòng nữa của `propose_next_step`, vì đầu vào của nó
    khác hẳn: nó đọc kết quả của cả plan, không đọc catalog.

    Attributes:
        schema_version: Phiên bản hình dạng.
        request_id: Id của yêu cầu, dội lại trong câu trả lời.
        said: Câu giáo viên đã gõ, để lời kể trả lời đúng thứ họ hỏi.
        outcomes: Các bước đã chạy, theo thứ tự. Không bao giờ rỗng: một plan bị từ chối thì
            không bước nào chạy và BE không gọi tới task này.
        written: Đề đã có bao nhiêu câu, **đếm từ database** chứ không đếm từ số tiếng chuông --
            chuông có thể mất, và một vị trí thử lại rung hai lần.
        asked_for: Giáo viên xin bao nhiêu câu. `written == asked_for` là lúc nói "xong".
        still_drafting: Còn bao nhiêu câu đang soạn. Lớn hơn 0 thì lời kể nói "đang soạn".

    Ba con số cuối tồn tại để luật *"nói đang soạn chứ đừng nói đã xong"* là **dữ liệu**, không
    phải một câu cứng trong prompt. Câu cứng ấy đúng chừng nào báo cáo còn chạy trước lúc soạn
    xong; từ khi đường SSE đợi hết câu rồi mới kể, chính nó thành máy sinh lời nói sai chiều
    ngược lại (ADR-25).
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    said: str = Field(min_length=1, max_length=2000)
    outcomes: tuple[StepOutcome, ...] = ()
    written: int = 0
    asked_for: int = 0
    still_drafting: int = 0


class PlanReportCompleted(BaseModel):
    """Lời kể của Kriky sau khi plan chạy xong.

    Attributes:
        schema_version: Phiên bản hình dạng.
        request_id: Dội lại từ yêu cầu.
        text: Câu kết. Rỗng nghĩa là model không nói được, và BE lùi về một câu dựng từ `outcomes`.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    text: str = ""
