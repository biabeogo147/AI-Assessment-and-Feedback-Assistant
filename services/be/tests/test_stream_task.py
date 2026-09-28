"""The streaming gateway itself, which every other test replaces with a stub.

`stream_task` carries three rules that are invisible at its call site and
expensive to rediscover: subscribe before enqueue, drain before closing, and
never let tidying up outrank the error that caused it. The rest of the suite
patches this function out, so without these tests those rules run only when a
person remembers to look.

A hand-built fake pool rather than a real Redis, because the rules under test
are about ordering and error handling, not about Redis. The real thing is
exercised by running the system.
"""

import asyncio

import pytest
from arq.jobs import JobStatus

from be.agent_gateway import AgentError, stream_task
from be.config import Settings

SETTINGS = Settings(agent_queue_name="q", agent_job_timeout_seconds=5)


class FakePubSub:
    """Stands in for a redis pub/sub connection, recording what it was told."""

    def __init__(self, log: list[str], pieces: list[str], fail_on_close: bool = False) -> None:
        self.log = log
        self.pieces = pieces
        self.fail_on_close = fail_on_close
        self.closed = False

    async def subscribe(self, channel: str) -> None:
        self.log.append("subscribe")

    async def get_message(self, ignore_subscribe_messages: bool, timeout: float) -> dict | None:
        if self.pieces:
            return {"type": "message", "data": self.pieces.pop(0).encode()}
        return None

    async def unsubscribe(self, channel: str) -> None:
        if self.fail_on_close:
            raise ConnectionError("redis went away while tidying up")

    async def aclose(self) -> None:
        self.closed = True


class FakeJob:
    """A job that reports complete after `after` status checks."""

    def __init__(self, after: int, success: bool = True) -> None:
        self.job_id = "j1"
        self.after = after
        self.success = success
        self.asked = 0

    async def status(self) -> JobStatus:
        self.asked += 1
        return JobStatus.complete if self.asked > self.after else JobStatus.in_progress


class FakePool:
    """Enough of an arq pool for the gateway to run against."""

    def __init__(self, pubsub: FakePubSub, log: list[str], job: FakeJob | None) -> None:
        self._pubsub = pubsub
        self.log = log
        self.job = job

    def pubsub(self) -> FakePubSub:
        return self._pubsub

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str) -> FakeJob | None:
        self.log.append("enqueue")
        return self.job


def _patch_result(monkeypatch: pytest.MonkeyPatch, result: object, success: bool = True) -> None:
    """Make the gateway's result read return `result` without touching Redis."""

    class Info:
        def __init__(self) -> None:
            self.success = success
            self.result = result

    class Reader:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def result_info(self) -> Info:
            return Info()

    monkeypatch.setattr("be.agent_gateway.Job", Reader)


@pytest.mark.asyncio
async def test_the_channel_is_open_before_the_job_is_handed_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Subscribe first. Redis pub/sub keeps no history.

    Enqueue first and arq may hand the job to a worker before anyone is
    listening, which loses the opening words with nothing to show it happened.
    """
    log: list[str] = []
    pool = FakePool(FakePubSub(log, []), log, FakeJob(after=0))
    _patch_result(monkeypatch, {"text": "xong"})

    async for _ in stream_task(pool, SETTINGS, "explain", {}, "ch"):
        pass

    assert log == ["subscribe", "enqueue"]


@pytest.mark.asyncio
async def test_pieces_published_at_the_last_instant_are_not_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The drain loop exists for the piece that lands as the job finishes."""
    log: list[str] = []
    # The job reports complete immediately, while pieces are still queued.
    pool = FakePool(FakePubSub(log, ["một ", "hai ", "ba"]), log, FakeJob(after=0))
    _patch_result(monkeypatch, {"text": "một hai ba"})

    seen = [
        value
        async for kind, value in stream_task(pool, SETTINGS, "explain", {}, "ch")
        if kind == "chunk"
    ]

    assert seen == ["một ", "hai ", "ba"]


@pytest.mark.asyncio
async def test_a_failure_while_tidying_up_does_not_replace_the_real_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The caller handles AgentError and nothing else.

    A ConnectionError raised while closing the channel would escape a generator
    whose status line has already gone out, so the client sees a broken stream
    and no reason for it. The original complaint has to survive.
    """
    log: list[str] = []
    pubsub = FakePubSub(log, [], fail_on_close=True)
    pool = FakePool(pubsub, log, None)  # arq refuses the job

    with pytest.raises(AgentError, match="refused"):
        async for _ in stream_task(pool, SETTINGS, "explain", {}, "ch"):
            pass


@pytest.mark.asyncio
async def test_silence_ends_the_stream_but_a_long_answer_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The timeout is a silence timer, not a length limit.

    A model still writing after the window is working, not dead. Cutting it off
    would throw away an answer that was arriving correctly.
    """
    log: list[str] = []
    settings = Settings(agent_queue_name="q", agent_job_timeout_seconds=1)
    # More pieces than the window would allow if the clock never reset, each
    # one arriving after a pause that on its own stays inside the window.
    pieces = [f"mẩu {index} " for index in range(12)]

    class Slow(FakePubSub):
        async def get_message(self, ignore_subscribe_messages: bool, timeout: float) -> dict | None:
            await asyncio.sleep(0.12)
            return await super().get_message(
                ignore_subscribe_messages=ignore_subscribe_messages, timeout=timeout
            )

    # `after` counts status checks, and none happen while pieces keep arriving:
    # the job is done the first time the channel goes quiet.
    pool = FakePool(Slow(log, list(pieces)), log, FakeJob(after=0))
    _patch_result(monkeypatch, {"text": "".join(pieces)})

    seen = [
        value
        async for kind, value in stream_task(pool, settings, "explain", {}, "ch")
        if kind == "chunk"
    ]

    assert seen == pieces, "a steady stream must not be cut off by the total elapsed time"


class Rejecting:
    """Counts asks and hands back what it was scripted to, for the retry loop."""

    def __init__(self, questions: list[dict]) -> None:
        self.questions = questions
        self.seen_previous: list[list[str]] = []

    async def __call__(self, pool, settings, task_name, payload) -> dict:
        self.seen_previous.append(list(payload["previous_stems"]))
        return {
            "schema_version": 1,
            "request_id": payload["request_id"],
            "question": self.questions.pop(0),
        }


def _question(stem: str, correct: int = 1, methods: int = 2) -> dict:
    """Build a serialised question, optionally breaking one ADR-18 rule."""
    options = [
        {"label": "A", "text": "một", "is_correct": correct >= 1, "error_label": None},
        {
            "label": "B",
            "text": "hai",
            "is_correct": correct >= 2,
            "error_label": None if correct >= 2 else "nhầm dấu",
        },
    ]
    return {
        "stem": stem,
        "options": options,
        "methods": [{"title": f"Cách {i}", "body": "..."} for i in range(1, methods + 1)],
        "learning_objective": "mục tiêu",
    }


@pytest.mark.asyncio
async def test_a_rejected_round_question_is_re_asked_with_it_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BE tells AGENT which stem it just refused.

    Re-sending the identical payload would leave the second answer to chance.
    The rejected stem goes into `previous_stems`, which is the field that
    already meant "do not write this one".
    """
    from be import agent_gateway
    from contracts import GeneratedOption, GeneratedQuestion, RetryQuestionRequested, SolutionMethod

    origin = GeneratedQuestion(
        stem="đề gốc",
        options=(
            GeneratedOption(label="A", text="một", is_correct=True),
            GeneratedOption(label="B", text="hai", error_label="nhầm dấu"),
        ),
        methods=(
            SolutionMethod(title="Cách 1", body="..."),
            SolutionMethod(title="Cách 2", body="..."),
        ),
        learning_objective="mục tiêu",
    )
    # First answer has two correct options; second is fine.
    agent = Rejecting([_question("đề hỏng", correct=2), _question("đề mới")])
    monkeypatch.setattr(agent_gateway, "run_task", agent)

    ask = RetryQuestionRequested(
        request_id="r1", origin=origin, wrong_option_label="B", round_index=1
    )
    question = await agent_gateway.ask_for_retry_question(object(), SETTINGS, ask, "đề gốc", [])

    assert question.stem == "đề mới"
    assert agent.seen_previous[0] == []
    assert agent.seen_previous[1] == ["đề hỏng"], "the second ask must name what was refused"


@pytest.mark.asyncio
async def test_the_refusal_says_which_rule_was_broken(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 503 that says only "three tries failed" tells the reader nothing."""
    from be import agent_gateway
    from contracts import GeneratedOption, GeneratedQuestion, RetryQuestionRequested, SolutionMethod

    origin = GeneratedQuestion(
        stem="đề gốc",
        options=(
            GeneratedOption(label="A", text="một", is_correct=True),
            GeneratedOption(label="B", text="hai", error_label="nhầm dấu"),
        ),
        methods=(
            SolutionMethod(title="Cách 1", body="..."),
            SolutionMethod(title="Cách 2", body="..."),
        ),
        learning_objective="mục tiêu",
    )
    monkeypatch.setattr(agent_gateway, "run_task", Rejecting([_question("x", methods=1)] * 3))

    ask = RetryQuestionRequested(
        request_id="r1", origin=origin, wrong_option_label="B", round_index=1
    )
    with pytest.raises(AgentError, match="worked solution"):
        await agent_gateway.ask_for_retry_question(object(), SETTINGS, ask, "đề gốc", [])
