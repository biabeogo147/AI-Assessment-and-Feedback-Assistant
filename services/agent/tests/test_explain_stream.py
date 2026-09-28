"""What the tutoring handler does while the model writes, and when it stops.

The interesting behaviour is all in the failure: a model that dies halfway has
already put words on a student's screen, and what gets stored has to be those
words. Storing something else means the student reloads and finds a different
answer from the one they just read, with nothing to explain the swap.
"""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from agent import handlers, llm
from contracts import (
    ExplainTurnRequested,
    GeneratedOption,
    GeneratedQuestion,
    SolutionMethod,
)

QUESTION = GeneratedQuestion(
    stem="Đồ thị y = (2x − 1)/(x + 3) có tiệm cận ngang là đường nào?",
    options=(
        GeneratedOption(label="A", text="y = 2", is_correct=True),
        GeneratedOption(label="B", text="x = −3", error_label="nhầm tiệm cận đứng"),
    ),
    methods=(
        SolutionMethod(title="Cách 1", body="Chia tử và mẫu cho x."),
        SolutionMethod(title="Cách 2", body="Xét giới hạn khi x → ±∞."),
    ),
    learning_objective="tiệm cận",
)

REQUEST = ExplainTurnRequested(
    request_id="a1",
    questions=(QUESTION,),
    question_numbers=(5,),
    chosen_labels={QUESTION.stem: "B"},
    error_labels={QUESTION.stem: "nhầm tiệm cận đứng"},
    stream_channel="aiafa:stream:test",
)


class Recorder:
    """Stands in for the Redis connection arq hands the handler."""

    def __init__(self) -> None:
        self.published: list[str] = []

    async def publish(self, channel: str, piece: str) -> None:
        self.published.append(piece)


@pytest.fixture
def on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn the model path on without needing a key or a `.env`."""
    monkeypatch.setattr(llm, "enabled", lambda: True)


@pytest.mark.asyncio
async def test_the_answer_goes_out_piece_by_piece(
    on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pieces are published as they are produced, not posted at the end."""
    monkeypatch.setattr(
        llm, "chat_models", lambda: (GenericFakeChatModel(messages=iter(["một hai ba"])),)
    )
    redis = Recorder()

    reply = await handlers.explain({"redis": redis}, REQUEST.model_dump(mode="json"))

    assert redis.published, "nothing was published, so the student watched a blank screen"
    assert "".join(redis.published) == reply["text"]


@pytest.mark.asyncio
async def test_a_model_that_dies_midway_keeps_the_words_already_read(
    on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What was stored must be what was shown.

    The prepared answer is the right fallback only while nobody has read
    anything yet. Once words are on the screen it becomes the wrong one: the
    history would disagree with the conversation the student remembers.
    """

    async def dies(request, publish):
        await publish("Ở câu 5, ")
        await publish("lỗi của em là ")
        raise RuntimeError("provider hung up")

    monkeypatch.setattr(handlers, "speak", dies)
    redis = Recorder()

    reply = await handlers.explain({"redis": redis}, REQUEST.model_dump(mode="json"))

    assert reply["text"] == "Ở câu 5, lỗi của em là "
    assert reply["text"] == "".join(redis.published)


@pytest.mark.asyncio
async def test_a_model_that_dies_before_saying_anything_falls_back(
    on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With nothing read yet there is nothing to contradict.

    So the prepared answer is served, and the student gets a turn instead of an
    error.
    """

    async def dies(request, publish):
        raise RuntimeError("provider refused the connection")

    monkeypatch.setattr(handlers, "speak", dies)
    redis = Recorder()

    reply = await handlers.explain({"redis": redis}, REQUEST.model_dump(mode="json"))

    assert redis.published == []
    assert "Kriky" in reply["text"], "the prepared greeting should have stood in"


@pytest.mark.asyncio
async def test_nobody_listening_means_nothing_is_published(
    on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A job whose client has gone away still answers; it just answers quietly."""
    monkeypatch.setattr(
        llm, "chat_models", lambda: (GenericFakeChatModel(messages=iter(["xong"])),)
    )
    redis = Recorder()
    silent = REQUEST.model_copy(update={"stream_channel": ""})

    reply = await handlers.explain({"redis": redis}, silent.model_dump(mode="json"))

    assert redis.published == []
    assert reply["text"]
