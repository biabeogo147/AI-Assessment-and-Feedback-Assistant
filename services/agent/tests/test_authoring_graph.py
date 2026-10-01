"""Loop write-check-retry, và nó làm gì khi model không chịu tuân thủ.

Cái loop là lý do việc này là một graph thay vì một lần gọi hàm, và hành vi đáng ghim
lại là phần phản hồi: một lần hỏi lại có mang theo lời phàn nàn là một lần sửa lỗi, còn
một lần hỏi lại lặp đúng yêu cầu cũ là gieo lại xúc xắc với tỉ lệ khá hơn. Chỉ cái đầu
tiên xứng với thời gian chờ của học sinh.
"""

import pytest
from langchain_core.runnables import Runnable, RunnableLambda

from agent import handlers, llm
from agent.graphs import authoring
from contracts import (
    DraftQuestionRequested,
    GeneratedOption,
    GeneratedQuestion,
    RetryQuestionRequested,
    SolutionMethod,
)

METHODS = (
    SolutionMethod(title="Cách 1", body="Xét dấu đạo hàm."),
    SolutionMethod(title="Cách 2", body="Thử giá trị rồi kiểm lại."),
)

ORIGIN = GeneratedQuestion(
    stem="Cho hàm số y = x³ − 3x. Hàm số đồng biến trên khoảng nào?",
    options=(
        GeneratedOption(label="A", text="(−∞; −1)", is_correct=True),
        GeneratedOption(label="B", text="(−1; 1)", error_label="đọc ngược chiều biến thiên"),
    ),
    methods=METHODS,
    learning_objective="tính đơn điệu",
)


_FRESH = "Cho hàm số y = x³ − 12x. Hàm số nghịch biến trên khoảng nào?"


def _good(stem: str = _FRESH) -> GeneratedQuestion:
    """Một câu hỏi không phạm luật nào."""
    return GeneratedQuestion(
        stem=stem,
        options=(
            GeneratedOption(label="A", text="(−2; 2)", is_correct=True),
            GeneratedOption(label="B", text="(2; +∞)", error_label="đọc ngược chiều biến thiên"),
        ),
        methods=METHODS,
        learning_objective="tính đơn điệu",
    )


def _two_right() -> GeneratedQuestion:
    """Một câu hỏi có hai phương án đúng, điều ADR-18 cấm."""
    return GeneratedQuestion(
        stem="Câu hỏng: hai đáp án đúng",
        options=(
            GeneratedOption(label="A", text="(−2; 2)", is_correct=True),
            GeneratedOption(label="B", text="(2; +∞)", is_correct=True),
        ),
        methods=METHODS,
        learning_objective="tính đơn điệu",
    )


class Scripted:
    """Một chat model trả lời bằng các câu hỏi xếp sẵn, có ghi lại các prompt."""

    def __init__(self, answers: list[GeneratedQuestion]) -> None:
        self.answers = answers
        self.prompts: list[str] = []

    def with_structured_output(self, schema: object, **kwargs: object) -> Runnable:
        """Trả về một runnable đưa lại câu hỏi xếp sẵn tiếp theo."""

        def answer(messages: object) -> GeneratedQuestion:
            self.prompts.append("\n".join(message.text() for message in messages))
            return self.answers.pop(0)

        return RunnableLambda(answer)


@pytest.fixture
def on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bật đường gọi model lên mà không cần key."""
    monkeypatch.setattr(llm, "enabled", lambda: True)


@pytest.mark.asyncio
async def test_a_rejected_question_is_re_asked_with_the_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lời phàn nàn đi ngược về tới model.

    Không có nó thì lần thử thứ hai chính là lần thử thứ nhất với con xúc xắc khác. Có
    nó, model mới đang được sửa.
    """
    model = Scripted([_two_right(), _good()])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    question = await authoring.write_question("viết một câu")

    assert question.stem == _good().stem
    assert len(model.prompts) == 2
    assert "đúng một phương án đúng" in model.prompts[1], "the second ask must say what was wrong"


@pytest.mark.asyncio
async def test_a_model_that_never_complies_is_given_up_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ba lần thử, rồi bên gọi quyết định -- nó có các lựa chọn khác, chỗ này thì không."""
    model = Scripted([_two_right(), _two_right(), _two_right()])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    with pytest.raises(ValueError, match="usable question"):
        await authoring.write_question("viết một câu")

    assert len(model.prompts) == 3


@pytest.mark.asyncio
async def test_a_repeated_stem_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-17: một lượt hỏi lại câu cũ là kiểm tra trí nhớ, không phải kiểm tra sự học."""
    repeat = _good(stem=ORIGIN.stem)
    model = Scripted([repeat, _good()])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    question = await authoring.write_question(
        "viết một câu", frozenset({authoring.normalise(ORIGIN.stem)})
    )

    assert question.stem != ORIGIN.stem
    assert "trùng với một đề đã dùng" in model.prompts[1]


@pytest.mark.asyncio
async def test_the_bank_catches_a_model_that_cannot_write_the_round(
    on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Một lượt không chịu mở ra còn tệ hơn một lượt mở ra trên nội dung dọn trước.

    Học sinh thì đang tiêu một lượt trong cả hai trường hợp, và cái bank viết tay thoả
    ADR-18 ngay từ cách nó được dựng -- đó chính là thứ làm cả cái thang làm lại kết
    thúc được.
    """
    monkeypatch.setattr(llm, "chat_models", lambda: (Scripted([_two_right()] * 3),))

    ask = RetryQuestionRequested(
        request_id="r1", origin=ORIGIN, wrong_option_label="B", round_index=1
    )
    reply = await handlers.generate_retry_question({}, ask.model_dump(mode="json"))

    question = reply["question"]
    assert question["stem"] != ORIGIN.stem
    assert sum(1 for option in question["options"] if option["is_correct"]) == 1
    assert len(question["methods"]) >= 2


@pytest.mark.asyncio
async def test_a_banned_stem_is_recognised_however_be_stored_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Các stem BE gửi tới ở dạng thô và được normalise ở đây.

    Bản đầu tiên của đường này để BE tự normalise chúng bằng hàm của chính nó -- một hàm
    viết cho tên lớp, nó cắt chữ "lớp" ở đầu và xoá mọi dấu cách. AGENT đem những stem
    đó so với luật của chính mình, luật chỉ gộp khoảng trắng, nên
    `"Đạo hàm của y = x² là gì?"` được gửi đi dưới dạng `"đạohàmcủay=x²làgì?"` và không
    khớp với gì cả. Check thì có đó mà chưa nổ lần nào.

    Normalise ngay lúc nhận là việc đường chữa lỗi vốn đã làm. Test này làm cho đường
    soạn nháp làm điều tương tự, và điều được khẳng định là: một stem gửi tới với khoảng
    trắng không gọn và chữ hoa chữ thường khác đi vẫn được nhận ra là bị cấm.
    """
    repeated = "Đạo hàm của y = x² là gì?"
    model = Scripted([_good().model_copy(update={"stem": repeated}), _good()])
    monkeypatch.setattr(llm, "enabled", lambda: True)
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    answer = await handlers.write_draft_question(
        {},
        DraftQuestionRequested(
            request_id="r1",
            subject="Toán",
            grade="12",
            topic_scope="đạo hàm",
            ordinal=2,
            of_total=3,
            # Đúng như đã lưu, với cách để khoảng trắng mà một model thật sinh ra.
            banned_stems=("Đạo hàm  của y = x²   là gì?",),
        ).model_dump(mode="json"),
    )

    # Lần thử đầu lặp lại một stem bị cấm, nên graph phàn nàn rồi hỏi lại -- đó là cách
    # duy nhất để câu trả lời xếp sẵn thứ hai được dùng tới.
    assert len(model.prompts) == 2
    assert "trùng" in model.prompts[1]
    assert answer["question"]["stem"] != repeated
