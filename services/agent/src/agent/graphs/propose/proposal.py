"""Hình dạng câu trả lời của model (`_Proposal`) và cách nó thành `NextStepCompleted`; kèm `nfc`,
chuẩn hoá Unicode các file khác cũng dùng."""

import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agent.latex_escapes import restore_latex_escapes
from contracts import (
    MOST_CLARIFY_QUESTIONS,
    ClarifyQuestion,
    NextStepCompleted,
    PlanStep,
)

# Bốn lớp dưới giữ dấu `_` dù file khác dùng `_Proposal`: tên lớp chính là tên tool (`_Proposal`)
# và tên các `$defs` trong schema gửi model, nên đổi tên là đổi thứ model đọc.
# `test_no_routing_decision` cũng khoá theo `"_Proposal"` (plan `propose-names-and-order`).


class _Argument(BaseModel):
    """Một argument của tool, dưới dạng một tên và một giá trị.

    Một cặp chứ không phải một mapping, vì mapping với key tuỳ ý là một JSON object
    mở và structured output ở chế độ strict từ chối những thứ đó. Giá trị là string:
    mọi argument các tool nhận hôm nay đều là string, và một union có kiểu ở đây sẽ
    là một nhánh schema mà model phải chọn giữa, chẳng được lợi gì.
    """

    model_config = ConfigDict(extra="forbid")

    param: str = Field(description="Tên tham số, viết đúng như trong danh sách tool.")
    value: str = Field(description="Giá trị của tham số.")


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


class _Question(BaseModel):
    """Một câu của một lượt hỏi lại nhiều câu (ADR-32), dưới hình dạng model trả lời được."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(
        description="Nhãn ngắn 1–3 chữ của điều được hỏi, như Khối, Số câu, Phạm vi."
    )
    text: str = Field(description="Câu hỏi.")
    choices: tuple[str, ...] = Field(
        default=(),
        description="Ít nhất 3 câu trả lời ngắn giáo viên có thể bấm cho riêng câu này.",
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

    # **Đứng trước `kind`, có chủ ý** (`kriky-skill-routing`, 12/10/2026). Model sinh JSON từ trái
    # sang phải, nên field đầu tiên là quyết định đầu tiên. Khi `kind` đứng đầu, gpt-4o-mini chọn
    # hỏi lại trước khi kịp đọc ra các mục đã có -- *"Tạo đề … chương Hàm số cho lớp 12A, 10 câu"*
    # hỏi lại 8/8 lần dù prompt dặn nêu plan ngay, và đổi chữ ở lõi, skill, mô tả tool đều 0/6. Bắt
    # nó ghi ra thứ đã biết trước thì 4/6. Không rời AGENT: `completed` bỏ nó đi, chỉ log giữ lại.
    known: str = Field(
        default="",
        description=(
            "Ghi chú cho chính bạn, giáo viên KHÔNG đọc: những gì đã biết từ lời giáo viên và kết "
            "quả tool, và còn thiếu gì cho việc họ nhờ. Không viết câu hỏi hay câu trả lời ở đây."
        ),
    )
    kind: Literal["say", "call_tool", "ask_clarify", "plan", "outline"]
    text: str = Field(
        default="",
        description=(
            "Lời giáo viên đọc trên màn hình, Markdown. Với ask_clarify, đây là câu hỏi. Với "
            "outline, đây là cả dàn ý. Không được rỗng với say, ask_clarify và outline."
        ),
    )
    # ADR-38: dàn ý là lời `text`; đi kèm chỉ một con số và các bài nguồn. Đứng **ngay sau `text`**,
    # không ở cuối: thử tay và bench run-98/run-100 thấy model chọn `outline` rồi bỏ trống phần đi
    # kèm khi nó nằm cuối -- model sinh JSON từ trái sang phải, cùng lý do `known` đứng đầu.
    outline_questions: int = Field(
        default=0,
        description=(
            "Chỉ với outline: dàn ý có bao nhiêu câu -- ĐÚNG số câu giáo viên xin; thay câu thì 1. "
            "Các kind khác để 0."
        ),
    )
    outline_nodes: tuple[int, ...] = Field(
        default=(),
        description=(
            "Chỉ với outline có tài liệu: số node các bài nguồn của dàn ý, lấy từ nodes của "
            "read_section. Không có tài liệu, hay kind khác, thì để trống."
        ),
    )
    # `unbiased-model-text` T3 (người dùng chốt 12/10/2026): hỏi lại thì có ít nhất 3 lựa chọn do
    # model đề xuất, FE vẽ thêm lối "Khác" để giáo viên tự ghi. Câu hỏi về một dòng -- lớp, tài
    # liệu, mục -- thì BE chỉ giữ chữ khớp đúng một tên nó đã đọc (`teacher_chat._choices`, hậu ký
    # ADR-23), nên lời dặn ở đây là *chép đúng tên*.
    choices: tuple[str, ...] = Field(
        default=(),
        description=(
            "Chỉ với ask_clarify: ít nhất 3 câu trả lời ngắn giáo viên có thể bấm, mỗi câu một khả "
            "năng khác nhau, viết đúng như lời giáo viên sẽ trả lời -- một giá trị, không phải tên "
            "một mục hay một câu hỏi. Hỏi về một lớp, một tài liệu hay một mục thì chép đúng tên "
            "trong kết quả tool. Không đánh dấu lựa chọn nào là nên chọn. Các kind khác để trống."
        ),
    )
    # ADR-32: hỏi 2–3 điều cùng lúc, mỗi điều một bộ nút. Đứng sau `choices`: một câu hỏi vẫn là
    # đường thường gặp, và hai đường đặt cạnh nhau để model thấy chúng loại trừ nhau.
    questions: tuple[_Question, ...] = Field(
        default=(),
        description=(
            "Chỉ với ask_clarify, khi cần hỏi 2 hoặc 3 điều cùng lúc: mỗi điều một câu. Khi dùng "
            "questions thì text là một câu mở ngắn và choices để trống. Hỏi một điều thì để trống."
        ),
    )
    tool_name: str = ""
    tool_args: tuple[_Argument, ...] = ()
    steps: tuple[_Step, ...] = ()

    def asked(self) -> tuple[tuple[ClarifyQuestion, ...], str, tuple[str, ...]]:
        """Các câu, lời mở và nút của một lượt hỏi lại, đã quy về hợp đồng (ADR-32). Hàm thuần.

        Hai câu trở lên đi thành `questions` (tối đa `MOST_CLARIFY_QUESTIONS`, phần dư bỏ --
        `choose` đã hỏi lại model khi có dư). Một câu thì là câu hỏi lại thường: lời mở và câu hỏi
        gộp làm `text`, nút của câu thành `choices`.

        Returns:
            `(questions, text, choices)`.
        """
        made = tuple(
            ClarifyQuestion(
                label=nfc(one.label).strip() or "Câu hỏi",
                text=nfc(one.text).strip() or nfc(one.label).strip() or "?",
                choices=tuple(nfc(choice) for choice in one.choices),
            )
            for one in self.questions
            if one.text.strip() or one.label.strip()
        )
        if len(made) >= 2:
            return made[:MOST_CLARIFY_QUESTIONS], nfc(self.text), ()
        if len(made) == 1:
            lead = nfc(self.text).strip()
            joined = f"{lead}\n\n{made[0].text}" if lead and lead != made[0].text else made[0].text
            return (), joined, made[0].choices or tuple(nfc(one) for one in self.choices)
        return (), nfc(self.text), tuple(nfc(one) for one in self.choices)

    def completed(self, request_id: str, model_tokens: int) -> NextStepCompleted:
        """Biến câu trả lời của model thành message BE đọc.

        Args:
            request_id: Id BE đã hỏi dưới.
            model_tokens: Con số provider báo lại.

        Raises:
            ValidationError: Khi model nói `plan` mà không nêu bước nào, hoặc nêu một bước không có
                tên tool. Handler ở tầng trên bắt và trả một thông báo hệ thống (ADR-30) -- không
                lùi về mock, vì mock nói dưới giọng Kriky một việc nó đoán.

        Returns:
            Đề nghị, kèm hai field model không bao giờ được hỏi. `steps` chỉ đi theo một `plan`,
            vì hợp đồng từ chối chúng ở mọi `kind` khác. `choices` chỉ đi theo `ask_clarify`: BE
            dựng nút từ chúng (`unbiased-model-text` T3) -- trước T3 field này để rỗng, vì ADR-23
            bản đầu bỏ hết chữ model viết.
        """
        # NFC cho mọi chữ model viết (`unbiased-model-text` T3): gpt-4o-mini có lúc trả "ứ" ở dạng
        # phân rã -- "ư" + dấu sắc rời (run-57) -- và chữ ấy không khớp nhãn BE, lời giáo viên hay
        # `bind_book`, dù in ra trông y hệt.
        questions, text, choices = (
            self.asked() if self.kind == "ask_clarify" else ((), nfc(self.text), ())
        )
        return NextStepCompleted(
            request_id=request_id,
            kind=self.kind,
            text=text,
            tool_name=self.tool_name,
            tool_args={argument.param: nfc(argument.value) for argument in self.tool_args},
            steps=tuple(
                PlanStep(
                    tool_name=step.tool_name,
                    args={argument.param: nfc(argument.value) for argument in step.args},
                    title=nfc(step.title),
                )
                for step in self.steps
            )
            if self.kind == "plan"
            else (),
            choices=choices,
            questions=questions,
            outline_questions=self.outline_questions if self.kind == "outline" else 0,
            outline_nodes=self.outline_nodes if self.kind == "outline" else (),
            model_tokens=model_tokens,
        )


def unmangled(proposal: "_Proposal") -> "_Proposal":
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


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)
