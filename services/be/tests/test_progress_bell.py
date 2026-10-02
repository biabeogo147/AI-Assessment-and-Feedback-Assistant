"""Chuông tiến độ: nó cắt độ trễ, và nó không bao giờ là đường duy nhất.

Đây là chỗ dễ thiết kế sai nhất của ADR-25. Pub/sub của Redis **không bền**: publish vào
một channel không ai nghe thì lời nói mất luôn. Nên nếu tiếng chuông chở câu hỏi, một người
đóng tab đúng lúc sẽ làm mất hẳn một câu đã soạn xong — mất thật, không phải mất hiển thị.
Chuông chở một con số, câu hỏi đi result store của arq, và hai test dưới đây giữ đúng hai
nửa ấy đứng tách nhau.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import drafting
from be.config import get_settings
from be.db import prepare_schema
from be.drafting import fire, harvest, listen_for_progress, progress_channel
from be.models import (
    Assessment,
    AssessmentState,
    DraftBrief,
    DraftItem,
    Question,
    Teacher,
)
from contracts import DraftQuestionCompleted, GeneratedOption, GeneratedQuestion, SolutionMethod


class FakeQueue:
    """Đóng thế cho pool arq: nhớ những gì được đẩy, và trả lời cho job test cho là đã xong."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, dict]] = []
        self.results: dict[str, tuple[str, object]] = {}

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str):
        job_id = f"job-{len(self.jobs)}"
        self.jobs.append((name, payload))
        return type("Queued", (), {"job_id": job_id})()

    def finish(self, job_id: str, stem: str) -> None:
        self.results[job_id] = (
            "ready",
            DraftQuestionCompleted(request_id="r", question=_good(stem)).model_dump(mode="json"),
        )


def _good(stem: str) -> GeneratedQuestion:
    """Một câu hỏi thoả ADR-18."""
    return GeneratedQuestion(
        stem=stem,
        options=(
            GeneratedOption(label="A", text="đúng", is_correct=True),
            GeneratedOption(label="B", text="sai", is_correct=False, error_label="lỗi B"),
            GeneratedOption(label="C", text="sai", is_correct=False, error_label="lỗi C"),
        ),
        methods=(
            SolutionMethod(title="Cách 1", body="..."),
            SolutionMethod(title="Cách 2", body="..."),
        ),
        learning_objective="tích phân",
    )


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """Một database trống, một hàng đợi giả, và không một Redis thật nào."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    queue = FakeQueue()

    async def collect(pool, settings, job_id):
        return queue.results.get(job_id, ("pending", None))

    monkeypatch.setattr(drafting, "collect_result", collect)
    try:
        yield maker, queue
    finally:
        await engine.dispose()


async def _draft(maker, count: int = 2) -> str:
    """Một đề nháp rỗng kèm brief, sẵn sàng để bắn job."""
    async with maker() as session:
        teacher = Teacher(teacher_code="GV-001", full_name="Cô Lan")
        session.add(teacher)
        await session.flush()
        draft = Assessment(
            teacher_id=teacher.id,
            title="Đề tích phân",
            subject="Toán",
            grade="12",
            state=AssessmentState.EMPTY,
            created_at=datetime.now(UTC),
        )
        session.add(draft)
        await session.flush()
        session.add(
            DraftBrief(
                assessment_id=draft.id,
                topic_scope="tích phân",
                question_count=count,
                version=1,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
        return draft.id


@pytest.mark.asyncio
async def test_every_job_is_told_where_to_ring(stack) -> None:
    """Không có channel trong payload thì không có chuông nào cả.

    Channel dựng từ **id của đề**, không phải một id phát theo lượt: người nghe và người
    rung gặp nhau qua cái đề, nên một tab mở sau vẫn nghe được một vòng soạn bắt đầu từ
    trước, và hai tab cùng mở thì cùng nghe.
    """
    maker, queue = stack
    draft = await _draft(maker)

    async with maker() as session:
        queued = await fire(session, queue, get_settings(), draft)

    assert queued == 2
    channels = {payload["progress_channel"] for _, payload in queue.jobs}
    assert channels == {progress_channel(draft)}
    assert progress_channel(draft) == f"draft:{draft}"


@pytest.mark.asyncio
async def test_a_question_lands_even_when_nobody_listened(stack) -> None:
    """Ca mà cả thiết kế xoay quanh: không ai nghe chuông, câu hỏi **vẫn** vào đề.

    Giáo viên đóng tab giữa lúc soạn, hoặc không ai mở tab nào. Tiếng chuông rơi vào căn
    phòng trống và mất luôn — đúng như pub/sub vốn vậy. Thứ không được phép mất là câu hỏi:
    nó nằm trong result store của arq, và lần quan sát kế tiếp đưa nó vào đề.

    Nếu một ngày ai đó chuyển nội dung câu hỏi vào tiếng chuông để "đỡ một vòng đọc", test
    này là thứ đỏ lên.
    """
    maker, queue = stack
    draft = await _draft(maker)

    async with maker() as session:
        await fire(session, queue, get_settings(), draft)
    # Hai job xong trong lúc tuyệt đối không có ai subscribe.
    queue.finish("job-0", "Tính ∫2x dx.")
    queue.finish("job-1", "Tính ∫3x² dx.")

    async with maker() as session:
        landed = await harvest(session, queue, get_settings(), draft)

    assert landed == 2
    async with maker() as session:
        stems = list(await session.scalars(select(Question.stem)))
        found = await session.get(Assessment, draft)
    assert sorted(stems) == ["Tính ∫2x dx.", "Tính ∫3x² dx."]
    assert found is not None and AssessmentState(found.state) is AssessmentState.HAS_QUESTIONS

    # Và các row đã rời `pending`, nên lần thu sau không ghi lại lần nữa.
    async with maker() as session:
        waiting = list(
            await session.scalars(select(DraftItem).where(DraftItem.status == "pending"))
        )
    assert waiting == []


@pytest.mark.asyncio
async def test_listening_without_a_queue_ends_quietly() -> None:
    """Queue chết thì đường nghe im lặng đi ra, không ném.

    Nó chạy trong cùng request với một lượt chat. Một `AttributeError` ở đây sẽ biến một
    hàng đợi tạm thời không với tới được thành một lượt chat hỏng — trong khi thứ duy nhất
    mất đi là sự sống động của một khối bước.
    """
    heard = [one async for one in listen_for_progress(None, "bat-ky", 0.1)]

    assert heard == []
