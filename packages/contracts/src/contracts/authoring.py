"""Message cho ba task authoring mà BE giao cho AGENT.

Chỉ dữ liệu, như mọi module ở đây. Cụ thể là những luật ADR-18 đặt lên một câu hỏi được sinh ra --
đúng một phương án đúng, mọi distractor đều có nhãn lỗi, ít nhất hai cách giải -- **không** được
validate ở đây. Chúng là luật nghiệp vụ, và BE sở hữu chúng: một phép kiểm sống trong module này sẽ
là một luật không service nào sở hữu, còn AGENT mà import nó thì thành ra người sinh đề tự chấm bài
của mình.

Mọi payload đều tự chứa. Không field nào ở đây là một identifier mà AGENT sẽ phải tra lại database,
bởi AGENT không giữ credential database.
"""

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

# Tên task của arq. BE enqueue bằng chuỗi và không bao giờ import package AGENT.
WRITE_DRAFT_QUESTION_TASK = "write_draft_question"
GENERATE_RETRY_QUESTION_TASK = "generate_retry_question"
EXPLAIN_TURN_TASK = "explain_turn"


class GeneratedOption(BaseModel):
    """Một phương án trả lời, đúng như AGENT đã viết ra.

    Attributes:
        label: Chữ cái hiện cho học sinh, từ "A" trở lên.
        text: Chính nội dung phương án.
        is_correct: True cho đúng một phương án đúng. AGENT khẳng định điều này; BE kiểm lại rằng
            mỗi câu hỏi có đúng một phương án mang nó.
        error_label: Lỗi mà distractor này đại diện, theo ADR-18. None trên phương án đúng.
    """

    model_config = ConfigDict(frozen=True)

    label: str
    text: str
    is_correct: bool = False
    error_label: str | None = None


class SolutionMethod(BaseModel):
    """Một cách giải một câu hỏi.

    Attributes:
        title: Tên ngắn của cách làm, ví dụ "xét dấu đạo hàm".
        body: Các bước giải.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    body: str


class GeneratedQuestion(BaseModel):
    """Một câu hỏi, kèm đủ mọi thứ ADR-18 đòi.

    Attributes:
        stem: Phần đề của câu hỏi.
        options: Các phương án; đúng một phương án đúng và phần còn lại đều mang nhãn lỗi. Số lượng
            không cố định -- ba, bốn và năm đều có.
        methods: Các lời giải chi tiết. Nhiều hơn một, để một lượt giảng lại có chỗ mà đi.
        learning_objective: Câu hỏi kiểm cái gì. Chở theo để báo cáo; nó **không** phải là thứ làm
            cho một câu hỏi thử lại thành câu hỏi thử lại (ADR-17).
    """

    model_config = ConfigDict(frozen=True)

    stem: str
    options: tuple[GeneratedOption, ...]
    methods: tuple[SolutionMethod, ...]
    learning_objective: str


class DraftQuestionRequested(BaseModel):
    """Nhờ AGENT soạn **một** câu của một đề nháp.

    Một câu một job, không phải cả bộ, và lý do là phép tính chứ không phải sở thích:
    `tools/check_contract.py` so `LLM_TIMEOUT_SECONDS x LLM_MAX_ATTEMPTS` với độ kiên nhẫn của BE
    cho **một** job, và phép so đó chỉ đúng cho số lần thử của một câu. Task bị thay thế nhận tới
    năm mươi câu trong một job -- năm mươi lần cái ngân sách mà check đang kiểm -- nên check đã âm
    thầm nói sai về đúng handler tốn nhiều nhất.

    Mọi field ở đây được chép từ một brief mà BE lưu **trước khi** có job nào được queue. Đó là thứ
    giữ cho một bộ đề mạch lạc: các job chạy độc lập và không thấy nhau, nên nếu chỉ thị còn đổi
    được thì nửa đầu và nửa sau của một đề sẽ trả lời hai câu hỏi khác nhau, mà ai đọc từng câu một
    cũng không nhận ra.

    Attributes:
        request_id: Để đối chiếu câu trả lời. Identifier của chính BE, với AGENT thì nó vô nghĩa.
        subject: Môn học, ví dụ "Toán".
        grade: Khối lớp, ví dụ "12".
        topic_scope: Phạm vi giáo viên giới hạn đề nháp này vào, bằng lời của họ.
        difficulty: Mức độ khó, bằng lời của giáo viên. Rỗng khi họ không nói.
        ordinal: Đây là câu thứ mấy của bộ, đếm từ một.
        of_total: Bộ có bao nhiêu câu. Đi cùng `ordinal` để prompt nói được "câu 3 trong 10" -- cú
            đẩy rẻ nhất hướng tới sự đa dạng giữa những job không có cách nào phối hợp với nhau.
        banned_stems: Những stem đã có trong đề nháp, **đúng như đang lưu** -- AGENT chuẩn hoá chúng
            bằng luật của chính nó lúc nhận, nên hai service không bao giờ phải giữ hai bộ chuẩn hoá
            đồng bộ với nhau. Dù sao cũng chỉ là cố gắng hết sức: các job bắn cùng lúc không thể
            biết đầu ra của nhau, nên BE kiểm trùng lại lúc harvest.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    subject: str
    grade: str
    topic_scope: str
    difficulty: str = ""
    ordinal: int = Field(ge=1)
    of_total: int = Field(ge=1, le=50)
    banned_stems: tuple[str, ...] = ()


class DraftQuestionCompleted(BaseModel):
    """Đúng một câu hỏi mà job đó đã viết.

    Không chở quyết định nào: đề nháp có đủ tốt để phát hành hay không là việc của giáo viên, còn
    câu hỏi có thoả ADR-18 hay không là phép kiểm của BE.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    question: GeneratedQuestion


class RetryQuestionRequested(BaseModel):
    """Nhờ AGENT soạn câu hỏi cho một vòng củng cố.

    Attributes:
        request_id: Để đối chiếu câu trả lời.
        origin: Câu hỏi học sinh làm sai, nguyên cả câu, vì câu thử lại phải giữ được **hình dạng**
            của nó chứ không chỉ giữ mục tiêu (ADR-17).
        wrong_option_label: Học sinh đã chọn phương án nào.
        error_label: Lỗi mà phương án đó đại diện, tra từ bảng ánh xạ đã soạn sẵn. AGENT không tự
            suy ra.
        round_index: 1, 2 hay 3. AGENT soạn một câu hỏi; nó không quyết định có được phép có vòng
            thứ tư hay không.
        previous_stems: Những stem đã dùng ở các vòng trước của chính câu này, để vòng hai không
            phải là vòng một viết lại bằng từ khác.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    origin: GeneratedQuestion
    wrong_option_label: str
    error_label: str | None = None
    round_index: int = Field(ge=1)
    previous_stems: tuple[str, ...] = ()


class RetryQuestionCompleted(BaseModel):
    """Câu hỏi cho vòng này, cùng hình dạng với mọi câu hỏi khác."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    question: GeneratedQuestion


class ChatTurn(BaseModel):
    """Một lượt của cuộc hội thoại pha 2.

    Attributes:
        role: "student" hoặc "assistant".
        text: Nội dung đã nói.
    """

    model_config = ConfigDict(frozen=True)

    role: str
    text: str


class ExplainTurnRequested(BaseModel):
    """Nhờ AGENT soạn lượt tiếp theo của trợ lý trong cuộc hội thoại pha 2.

    Attributes:
        request_id: Để đối chiếu câu trả lời.
        questions: Mọi câu học sinh làm sai, kèm lời giải. Trợ lý phụ trách cả bài, không
            phải một câu.
        question_numbers: Số thứ tự của từng câu đó **trên đề**, cùng thứ tự. Không có nó
            thì trợ lý đếm từ một và gọi câu 5 là "câu 1", tệ hơn cả việc không nói gì:
            học sinh sẽ đi tìm sai câu.
        chosen_labels: Phương án học sinh đã chọn, khoá theo stem của câu hỏi.
        error_labels: Lỗi đã soạn sẵn cho từng câu sai, khoá theo stem. AGENT đi theo bảng ánh xạ
            này thay vì tự chẩn đoán (ADR-18).
        history: Hội thoại đến giờ, cũ nhất trước.
        student_text: Tin nhắn đang được trả lời. Rỗng ở lượt mở đầu.
        stream_channel: Nơi phát câu trả lời ra trong lúc nó đang được viết, để học sinh thấy chữ
            thay vì thấy một khoảng lặng. Rỗng nghĩa là không ai đang nghe và câu trả lời chỉ về lúc
            cuối. Nó là tên một channel chứ không phải một id, vì việc đặt tên thuộc về người đang
            nghe; AGENT phát vào chỗ nó được bảo.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    questions: tuple[GeneratedQuestion, ...]
    question_numbers: tuple[int, ...] = ()
    chosen_labels: dict[str, str] = Field(default_factory=dict)
    error_labels: dict[str, str] = Field(default_factory=dict)
    history: tuple[ChatTurn, ...] = ()
    student_text: str = ""
    stream_channel: str = ""


class ExplainTurnCompleted(BaseModel):
    """Thứ trợ lý nói tiếp.

    Một field, có chủ ý. Một lượt trả lời mà kèm luôn "giờ thì học sinh đã hiểu" là đang quyết định
    khi nào việc củng cố kết thúc, mà đó là một câu hỏi về điểm và nó thuộc về BE (ADR-16, ADR-17).
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    text: str
