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
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    arguments: dict[str, object] = Field(default_factory=dict)


class TurnRecord(BaseModel):
    """Một việc đã xảy ra trong cuộc hội thoại này.

    Lịch sử không chỉ gồm lời nói. Kết quả của một tool là một phần những gì model biết, nên nó đi
    thành một loại turn riêng thay vì bị dẹp thành văn xuôi -- dẹp đi nghĩa là model đọc một bản tóm
    tắt của dữ liệu thay vì đọc dữ liệu.

    Attributes:
        kind: Ai hay cái gì tạo ra turn này.
        text: Lời, cho turn `teacher` và `assistant`.
        tool_name: Tool nào, cho `tool_call` và `tool_result`.
        tool_args: Tham số mà BE đã thực thi với.
        tool_result: Thứ tool trả về. BE đã tóm tắt sẵn: điểm của cả một lớp vừa không nhét nổi vào
            một prompt, vừa không cần nhét.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["teacher", "assistant", "tool_call", "tool_result"]
    text: str = ""
    tool_name: str = ""
    tool_args: dict[str, object] = Field(default_factory=dict)
    tool_result: dict[str, object] = Field(default_factory=dict)


class NextStepRequested(BaseModel):
    """Hỏi AGENT xem bước tiếp theo của cuộc hội thoại này nên là gì.

    Tự chứa, như mọi payload ở đây: catalog và lịch sử đi cùng request, vì AGENT không tra được cái
    nào trong hai thứ đó.

    Attributes:
        request_id: Id để đối chiếu, được trả lại nguyên.
        teacher_name: Cách gọi người đang hỏi. Không phải một identifier -- AGENT không bao giờ nhận
            một identifier mà nó sẽ phải tra, và danh tính dùng để phân quyền ở lại trong BE.
        history: Mọi thứ đã xảy ra, cũ nhất trước.
        catalog: Những tool giáo viên này được dùng, trong lượt này.

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


class NextStepCompleted(BaseModel):
    """Thứ AGENT đề nghị làm tiếp.

    Đúng một trong ba hình dạng, chọn bằng `kind`:

    - `say`: trả lời bằng lời; `text` chở lời đó và lượt kết thúc.
    - `call_tool`: BE nên chạy `tool_name` với `tool_args`, rồi hỏi lại.
    - `ask_clarify`: chưa đủ thông tin để hành động; `text` là câu hỏi và `choices` là các lựa chọn,
      mà chúng phải đến từ dữ liệu BE cấp chứ không phải từ tưởng tượng của model.

    `ask_clarify` là cổng đầu vào của ADR-05, và luật của nó -- kể cả việc một câu hỏi làm rõ được
    phép và không được phép hỏi những gì -- nằm trong chính decision record đó, do BE thi hành. Chép
    lại ở đây là đặt một bản sao của luật nghiệp vụ vào một module dữ liệu, nơi nó sẽ cũ đi mà không
    có gì gãy để báo.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    kind: Literal["say", "call_tool", "ask_clarify"]
    text: str = ""
    tool_name: str = ""
    tool_args: dict[str, object] = Field(default_factory=dict)
    choices: tuple[str, ...] = ()
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
            ValueError: Khi `kind` là `call_tool` mà `tool_name` rỗng.
        """
        if self.kind == "call_tool" and not self.tool_name.strip():
            raise ValueError("kind='call_tool' needs a tool_name")
        return self
