"""The write-check-retry loop, and what it does when the model will not comply.

The loop is the reason this task is a graph rather than a function call, and
the behaviour worth pinning is the feedback: a re-ask that carries the
complaint is a correction, one that repeats the same request is a re-roll with
better odds. Only the first is worth the student's wait.
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
    """A question that breaks no rule."""
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
    """A question with two correct options, which ADR-18 forbids."""
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
    """A chat model that answers with queued questions, recording the prompts."""

    def __init__(self, answers: list[GeneratedQuestion]) -> None:
        self.answers = answers
        self.prompts: list[str] = []

    def with_structured_output(self, schema: object, **kwargs: object) -> Runnable:
        """Return a runnable handing back the next queued question."""

        def answer(messages: object) -> GeneratedQuestion:
            self.prompts.append("\n".join(message.text() for message in messages))
            return self.answers.pop(0)

        return RunnableLambda(answer)


@pytest.fixture
def on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn the model path on without a key."""
    monkeypatch.setattr(llm, "enabled", lambda: True)


@pytest.mark.asyncio
async def test_a_rejected_question_is_re_asked_with_the_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The complaint travels back to the model.

    Without it the second attempt is the first attempt again with different
    dice. With it, the model is being corrected.
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
    """Three tries, then the caller decides -- it has alternatives, this does not."""
    model = Scripted([_two_right(), _two_right(), _two_right()])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    with pytest.raises(ValueError, match="usable question"):
        await authoring.write_question("viết một câu")

    assert len(model.prompts) == 3


@pytest.mark.asyncio
async def test_a_repeated_stem_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-17: a round that re-asks the old question tests memory, not learning."""
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
    """A round that will not open is worse than one that opens on prepared content.

    The student is spending a round either way, and the hand-written bank
    satisfies ADR-18 by construction -- which is what makes the whole retry
    ladder terminate.
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
    """The stems BE sends arrive raw and are normalised here.

    The first version of this path had BE normalise them with its own
    function -- one written for class names, which strips a leading "lớp" and
    removes every space. AGENT compared those against its own rule, which only
    collapses whitespace, so `"Đạo hàm của y = x² là gì?"` was sent as
    `"đạohàmcủay=x²làgì?"` and matched nothing. The check existed and never
    fired once.

    Normalising on arrival is what the remediation path already did. This
    makes the drafting path do the same, and the assertion is that a stem sent
    with untidy spacing and different case is still recognised as banned.
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
            # As stored, with the spacing a model actually produces.
            banned_stems=("Đạo hàm  của y = x²   là gì?",),
        ).model_dump(mode="json"),
    )

    # The first attempt repeated a banned stem, so the graph complained and
    # asked again -- which is the only way the second queued answer is used.
    assert len(model.prompts) == 2
    assert "trùng" in model.prompts[1]
    assert answer["question"]["stem"] != repeated
