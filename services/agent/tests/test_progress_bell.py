"""Chuông tiến độ: rung **sau** khi kết quả đã vào store, và không bao giờ làm hỏng job.

Hai luật, và luật thứ nhất là thứ dễ làm sai nhất. arq ghi kết quả bằng `finish_job`, **sau
khi** coroutine của job trả về; `after_job_end` chạy sau đó nữa. Rung chuông từ trong thân
job là báo "xong câu 3" trong lúc BE vẫn đọc câu 3 là `pending` — màn hình trễ một nhịp, và
tiếng chuông cuối cùng không gặt được gì, nên một lượt chat chờ "hết câu đang soạn" treo tới
hết hạn kiên nhẫn. Bản đầu của Pha D làm đúng như vậy; review bắt được.

Luật thứ hai: công việc đã nằm trong store trước khi chuông rung, nên một Redis dở chứng
không được phép làm job thất bại — BE đọc một job ném là *"chính job đó đã nổ"*, không hỏi
lại, nên vị trí ấy mất câu vĩnh viễn.
"""

import pytest

from agent import handlers, llm
from contracts import (
    DraftQuestionRequested,
    GeneratedOption,
    GeneratedQuestion,
    SolutionMethod,
)


class Bells:
    """Đóng thế cho connection Redis mà arq đưa cho hook."""

    def __init__(self, broken: bool = False) -> None:
        self.rung: list[tuple[str, str]] = []
        self.broken = broken

    async def publish(self, channel: str, message: str) -> None:
        if self.broken:
            raise ConnectionError("redis đi vắng")
        self.rung.append((channel, message))


def _asked(channel: str = "draft:de-1") -> dict:
    return DraftQuestionRequested(
        request_id="de-1:3:1",
        subject="Toán",
        grade="12",
        topic_scope="tích phân",
        ordinal=3,
        of_total=10,
        progress_channel=channel,
    ).model_dump(mode="json")


def _good() -> GeneratedQuestion:
    """Một câu hỏi thoả ADR-18, để đường model-viết-được chạy tới cuối."""
    return GeneratedQuestion(
        stem="Tính ∫2x dx.",
        options=(
            GeneratedOption(label="A", text="x² + C", is_correct=True),
            GeneratedOption(label="B", text="2x² + C", is_correct=False, error_label="lỗi B"),
            GeneratedOption(label="C", text="2 + C", is_correct=False, error_label="lỗi C"),
        ),
        methods=(
            SolutionMethod(title="Cách 1", body="..."),
            SolutionMethod(title="Cách 2", body="..."),
        ),
        learning_objective="tích phân",
    )


async def _one_job(ctx: dict, payload: dict) -> dict:
    """Chạy một job đúng cách arq chạy nó: thân job, rồi hook sau khi kết quả đã vào store."""
    answer = await handlers.write_draft_question(ctx, payload)
    await handlers.ring_bell(ctx)
    return answer


@pytest.mark.asyncio
async def test_the_job_itself_rings_nothing(monkeypatch) -> None:
    """Thân job **không** publish gì cả.

    Đây là phép kiểm giữ đúng cái thứ tự mà review Pha D bắt được. Lúc thân job còn chạy,
    kết quả chưa nằm trong result store của arq; một tiếng chuông phát ra từ đây mời BE đi
    thu hoạch một thứ chưa đọc được.
    """
    monkeypatch.setattr(llm, "enabled", lambda: False)
    bells = Bells()
    ctx: dict = {"redis": bells}

    await handlers.write_draft_question(ctx, _asked())

    assert bells.rung == []
    # Nhưng chuông đã được **đặt sẵn**, chờ hook rung.
    assert any(isinstance(value, tuple) for value in ctx.values())


@pytest.mark.asyncio
async def test_the_bell_carries_a_number_not_a_question(monkeypatch) -> None:
    """Chuông chở số thứ tự, không chở nội dung.

    Pub/sub không bền: không ai nghe thì lời nói mất. Chở câu hỏi trong đó nghĩa là một
    người đóng tab đúng lúc làm **mất hẳn** một câu đã soạn xong.
    """
    monkeypatch.setattr(llm, "enabled", lambda: False)
    bells = Bells()

    answer = await _one_job({"redis": bells}, _asked())

    assert bells.rung == [("draft:de-1", "3")]
    # Và câu hỏi vẫn đi đường cũ: nó nằm trong thứ job trả về, tức result store của arq.
    assert answer["question"]["stem"]


@pytest.mark.asyncio
async def test_the_path_that_actually_runs_in_production_rings(monkeypatch) -> None:
    """Đường model viết được cũng rung — đường duy nhất có thật khi có API key.

    Review Pha D đo được rằng xoá tiếng chuông khỏi đúng nhánh này thì cả bộ test vẫn xanh:
    năm test cũ chỉ đi qua nhánh mock và nhánh `except`.
    """
    monkeypatch.setattr(llm, "enabled", lambda: True)

    async def writes(brief, banned):
        return _good()

    monkeypatch.setattr(handlers, "write_question", writes)
    bells = Bells()

    answer = await _one_job({"redis": bells}, _asked())

    assert bells.rung == [("draft:de-1", "3")]
    assert answer["question"]["stem"] == "Tính ∫2x dx."


@pytest.mark.asyncio
async def test_a_model_that_dies_still_rings(monkeypatch) -> None:
    """Model hỏng thì job lùi về nội dung dọn trước — và vẫn báo.

    Không rung ở nhánh này thì màn hình đứng im đúng lúc có một câu vừa vào đề, và người
    đọc kết luận rằng hệ thống treo.
    """
    monkeypatch.setattr(llm, "enabled", lambda: True)

    async def dies(brief, banned):
        raise RuntimeError("model đi vắng")

    monkeypatch.setattr(handlers, "write_question", dies)
    bells = Bells()

    answer = await _one_job({"redis": bells}, _asked())

    assert bells.rung == [("draft:de-1", "3")]
    assert answer["question"]["stem"]


@pytest.mark.asyncio
async def test_a_broken_bell_does_not_break_the_job(monkeypatch) -> None:
    """Redis ném thì job **vẫn** xong.

    Phép kiểm đáng giá nhất trong file: lúc chuông rung, câu hỏi đã viết xong và đã nằm
    trong store. Một exception thoát ra từ hook biến một job đã thành công thành một job
    thất bại, và BE đọc nó là *"chính job đó đã nổ"* — tức không hỏi lại, và vị trí ấy mất
    câu vĩnh viễn.
    """
    monkeypatch.setattr(llm, "enabled", lambda: False)

    answer = await _one_job({"redis": Bells(broken=True)}, _asked())

    assert answer["question"]["stem"]


@pytest.mark.asyncio
async def test_no_channel_means_no_bell(monkeypatch) -> None:
    """Payload không mang channel thì không publish gì.

    Chuỗi rỗng là mặc định của một payload cũ, không phải một lời nói rằng "không ai nghe" --
    BE luôn điền channel. Publish vào một chuỗi rỗng là một lệnh Redis đi ra mỗi câu, cho
    không ai cả.
    """
    monkeypatch.setattr(llm, "enabled", lambda: False)
    bells = Bells()

    await _one_job({"redis": bells}, _asked(channel=""))

    assert bells.rung == []


@pytest.mark.asyncio
async def test_a_hook_without_a_bell_does_nothing(monkeypatch) -> None:
    """Hook chạy sau **mọi** job của worker, kể cả những job không bao giờ đặt chuông.

    Soạn đề, chấm bài, đặt tên đoạn chat — tất cả đi qua `after_job_end`. Một hook cho rằng
    lúc nào cũng có chuông sẽ ném `KeyError` sau mỗi job khác, và arq log nó như một lỗi của
    worker.
    """
    bells = Bells()

    await handlers.ring_bell({"redis": bells})

    assert bells.rung == []
