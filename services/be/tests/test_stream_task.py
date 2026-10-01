"""Chính cái gateway `stream`, thứ mà mọi test khác đều thay bằng một bản stub.

`stream_task` mang theo ba luật vô hình ở nơi gọi nó và đắt đỏ để tìm lại: subscribe
trước khi enqueue, vét sạch trước khi đóng, và không bao giờ để việc dọn dẹp lấn
quyền cái lỗi đã gây ra nó. Phần còn lại của bộ test đều patch hàm này ra ngoài, nên
không có mấy test ở đây thì ba luật đó chỉ chạy khi có người nhớ mà ngó tới.

Dùng một fake pool tự dựng thay vì một Redis thật, vì các luật đang được kiểm nói về
thứ tự và cách xử lý lỗi, không nói về Redis. Hàng thật được thao luyện bằng cách
chạy cả hệ thống.
"""

import asyncio

import pytest
from arq.jobs import JobStatus

from be.agent_gateway import AgentError, stream_task
from be.config import Settings

SETTINGS = Settings(agent_queue_name="q", agent_job_timeout_seconds=5)


class FakePubSub:
    """Đứng thay cho một kết nối pub/sub của redis, và ghi lại những gì nó được bảo."""

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
    """Một job báo là đã xong sau `after` lượt kiểm status."""

    def __init__(self, after: int, success: bool = True) -> None:
        self.job_id = "j1"
        self.after = after
        self.success = success
        self.asked = 0

    async def status(self) -> JobStatus:
        self.asked += 1
        return JobStatus.complete if self.asked > self.after else JobStatus.in_progress


class FakePool:
    """Vừa đủ phần của một arq pool để gateway có cái mà chạy lên."""

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
    """Làm cho lượt đọc kết quả của gateway trả về `result` mà không chạm tới Redis."""

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
    """Subscribe trước đã. Pub/sub của Redis không giữ lịch sử.

    Enqueue trước thì arq có thể giao job cho một worker trước khi có ai đang nghe, và
    thế là mất những chữ mở đầu mà chẳng còn gì cho thấy chuyện đó đã xảy ra.
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
    """Vòng vét sạch tồn tại là vì cái mẩu rơi xuống đúng lúc job kết thúc."""
    log: list[str] = []
    # Job báo xong ngay lập tức, trong khi các mẩu vẫn còn đang nằm chờ.
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
    """Bên gọi chỉ xử lý AgentError, không xử lý gì khác.

    Một ConnectionError ném ra trong lúc đóng channel sẽ thoát khỏi một generator mà
    dòng status của nó đã bay đi rồi, nên client thấy một `stream` đứt mà không có lý do
    nào. Lời phàn nàn gốc phải sống sót.
    """
    log: list[str] = []
    pubsub = FakePubSub(log, [], fail_on_close=True)
    pool = FakePool(pubsub, log, None)  # arq từ chối nhận job

    with pytest.raises(AgentError, match="refused"):
        async for _ in stream_task(pool, SETTINGS, "explain", {}, "ch"):
            pass


@pytest.mark.asyncio
async def test_silence_ends_the_stream_but_a_long_answer_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`timeout` là đồng hồ đếm sự im lặng, không phải mức giới hạn độ dài.

    Một model vẫn còn viết sau khi hết cửa sổ thời gian là đang làm việc, không phải đã
    chết. Cắt ngang nó sẽ ném đi một câu trả lời đang về đúng cách.
    """
    log: list[str] = []
    settings = Settings(agent_queue_name="q", agent_job_timeout_seconds=1)
    # Nhiều mẩu hơn số mà cửa sổ thời gian cho phép nếu cái đồng hồ không bao giờ được
    # reset, mỗi mẩu tới sau một quãng nghỉ mà tự nó vẫn nằm trong cửa sổ đó.
    pieces = [f"mẩu {index} " for index in range(12)]

    class Slow(FakePubSub):
        async def get_message(self, ignore_subscribe_messages: bool, timeout: float) -> dict | None:
            await asyncio.sleep(0.12)
            return await super().get_message(
                ignore_subscribe_messages=ignore_subscribe_messages, timeout=timeout
            )

    # `after` đếm các lượt kiểm status, và không lượt nào xảy ra khi các mẩu còn về đều:
    # job coi như xong ngay lần đầu channel im tiếng.
    pool = FakePool(Slow(log, list(pieces)), log, FakeJob(after=0))
    _patch_result(monkeypatch, {"text": "".join(pieces)})

    seen = [
        value
        async for kind, value in stream_task(pool, settings, "explain", {}, "ch")
        if kind == "chunk"
    ]

    assert seen == pieces, "a steady stream must not be cut off by the total elapsed time"


class Rejecting:
    """Đếm số lượt bị hỏi và trả về đúng thứ đã viết sẵn trong kịch bản, cho vòng `retry`."""

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
    """Dựng một câu hỏi đã serialise, và nếu muốn thì phá đúng một luật của ADR-18."""
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
    """BE nói cho AGENT biết nó vừa từ chối `stem` nào.

    Gửi lại đúng y `payload` cũ sẽ phó câu trả lời thứ hai cho may rủi. `stem` bị từ chối
    đi vào `previous_stems`, vốn là field đã mang nghĩa "đừng viết câu này".
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
    # Câu trả lời đầu có hai phương án đúng; câu thứ hai thì ổn.
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
    """Một cái 503 chỉ nói "thử ba lần đều hỏng" thì chẳng nói gì cho người đọc."""
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


@pytest.mark.asyncio
async def test_a_fixed_draft_that_keeps_its_wording_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Một bản nháp bị từ chối không phải một câu hỏi học sinh đã thấy.

    Vậy nên khi cách sửa tối thiểu của model là bỏ dấu đúng ở phương án thứ hai và giữ
    nguyên câu chữ, thì đó là một câu hỏi tốt và phải nhận. Coi chính bản nháp đã bị
    model loại là "đã dùng rồi" sẽ từ chối đúng cái sửa mà ta vừa yêu cầu, và đốt một
    lượt thử để làm việc đó.
    """
    from be import agent_gateway
    from contracts import (
        GeneratedOption,
        GeneratedQuestion,
        RetryQuestionRequested,
        SolutionMethod,
    )

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
    # Cùng một `stem` hai lần: lần đầu có hai phương án đúng, rồi được sửa lại.
    agent = Rejecting([_question("đề mới", correct=2), _question("đề mới")])
    monkeypatch.setattr(agent_gateway, "run_task", agent)

    ask = RetryQuestionRequested(
        request_id="r1", origin=origin, wrong_option_label="B", round_index=1
    )
    question = await agent_gateway.ask_for_retry_question(object(), SETTINGS, ask, "đề gốc", [])

    assert question.stem == "đề mới"


@pytest.mark.asyncio
async def test_a_dead_queue_is_not_reported_as_three_bad_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Một queue chết và một model không tuân luật là hai lời phàn nàn khác nhau.

    Gộp cái đầu vào cái sau sẽ đẩy người đọc log đi ngó mấy cái prompt trong khi vấn đề
    nằm ở Redis.
    """
    from be import agent_gateway
    from contracts import (
        GeneratedOption,
        GeneratedQuestion,
        RetryQuestionRequested,
        SolutionMethod,
    )

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

    async def queue_is_down(pool, settings, task_name, payload) -> dict:
        raise AgentError("hàng đợi chưa sẵn sàng")

    monkeypatch.setattr(agent_gateway, "run_task", queue_is_down)

    ask = RetryQuestionRequested(
        request_id="r1", origin=origin, wrong_option_label="B", round_index=1
    )
    with pytest.raises(AgentError, match="hàng đợi"):
        await agent_gateway.ask_for_retry_question(object(), SETTINGS, ask, "đề gốc", [])
