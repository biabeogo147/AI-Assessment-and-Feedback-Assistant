"""Soạn nháp một bộ câu hỏi: mỗi câu một job, cả bộ chung một brief.

Hai ràng buộc định hình chuyện này, và chúng kéo về hai hướng trái nhau.

Cả một đề nháp không thể là một job. `llm_timeout_seconds × llm_max_attempts`
là thứ `tools/check_contract.py` đem so với mức kiên nhẫn của BE cho một job, và
phép tính đó chỉ đúng với số lần `retry` của **một** lượt gọi model. Mười câu hỏi
trong một job là gấp mười, năm mươi câu là gấp năm mươi — nên hình dạng thoả được
invariant là mỗi câu một job, bắn đi rồi thu kết quả về sau.

Nhưng mười job chạy độc lập lại đúng là cách một bộ câu hỏi mất tính nhất quán:
nếu brief có thể đổi trong lúc chúng chạy thì câu 1-4 ra từ một cách hiểu về chủ
đề và câu 5-10 từ một cách hiểu khác, mà người đọc từng câu một thì không nhìn ra.
Vì vậy brief được ghi xuống một lần, trước khi bắn bất cứ thứ gì, và mọi job đều
đọc đúng dòng đó. Tính nhất quán được bảo đảm bằng cấu trúc, không phải bằng thời
điểm.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import drafting
from be.assessment_state import AssessmentState
from be.config import get_settings
from be.db import bind_sessions
from be.seed import seed_if_empty
from contracts import DraftQuestionCompleted, GeneratedOption, GeneratedQuestion, SolutionMethod
from schema.ddl import prepare_schema
from schema.models import AnswerOption, Assessment, DraftBrief, DraftItem, Method, Question, Teacher


class FakeQueue:
    """Ghi lại những gì đã vào queue và trả kết quả ra khi được hỏi."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, str, dict]] = []
        self.results: dict[str, tuple[str, object]] = {}

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str):
        job_id = f"job-{len(self.jobs)}"
        self.jobs.append((job_id, name, payload))
        return type("Queued", (), {"job_id": job_id})()

    def payloads(self) -> list[dict]:
        return [payload for _, _, payload in self.jobs]

    def finish(self, job_id: str, question: GeneratedQuestion) -> None:
        """Khai báo rằng một job đã xong với câu hỏi này."""
        self.results[job_id] = (
            "ready",
            DraftQuestionCompleted(request_id="r", question=question).model_dump(mode="json"),
        )

    def lose(self, job_id: str) -> None:
        """Khai báo rằng kết quả của job đã hết hạn và rơi khỏi Redis."""
        self.results[job_id] = ("gone", None)

    def break_(self, job_id: str) -> None:
        """Khai báo rằng job đã chạy và ném exception."""
        self.results[job_id] = ("failed", None)


def _good(stem: str) -> GeneratedQuestion:
    """Một câu hỏi thoả ADR-18: một đáp án đúng, các `Distractor` có nhãn, hai `Method`."""
    return GeneratedQuestion(
        stem=stem,
        options=(
            GeneratedOption(label="A", text="đúng", is_correct=True),
            GeneratedOption(label="B", text="sai B", is_correct=False, error_label="lỗi B"),
            GeneratedOption(label="C", text="sai C", is_correct=False, error_label="lỗi C"),
        ),
        methods=(
            SolutionMethod(title="Cách 1", body="..."),
            SolutionMethod(title="Cách 2", body="..."),
        ),
        learning_objective="đạo hàm",
    )


def _two_right() -> GeneratedQuestion:
    """Phá ADR-18 theo đúng cách một model thật vẫn phá: hai phương án đều đánh dấu đúng."""
    return _good("Câu hỏng").model_copy(
        update={
            "options": (
                GeneratedOption(label="A", text="đúng", is_correct=True),
                GeneratedOption(label="B", text="cũng đúng", is_correct=True),
            )
        }
    )


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """Một database đã seed, cộng một đề nháp rỗng thuộc giáo viên đã seed."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        teacher = await session.scalar(select(Teacher))
        assert teacher is not None
        draft = Assessment(
            teacher_id=teacher.id,
            title="Nháp mới",
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
                topic_scope="đạo hàm của đa thức",
                difficulty="cơ bản",
                question_count=3,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
        draft_id = draft.id

    queue = FakeQueue()

    async def collect(pool, settings, job_id):
        return queue.results.get(job_id, ("pending", None))

    monkeypatch.setattr(drafting, "collect_result", collect)

    yield maker, draft_id, queue

    await engine.dispose()
    from be import db as db_module

    db_module._SESSION_MAKER = None


@pytest.mark.asyncio
async def test_every_job_carries_the_same_brief(stack) -> None:
    """Brief được đọc một lần rồi sao vào từng job.

    Đây là toàn bộ lý do brief tồn tại dưới dạng một dòng được lưu. Mười job mà
    mỗi job tự suy ra chỉ dẫn riêng của mình — từ một cuộc hội thoại vẫn đang
    tiếp diễn — sẽ cho ra một bộ mà nửa đầu và nửa sau trả lời hai câu hỏi khác
    nhau, và đọc từng câu một thì không thấy ra điều đó.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 3)

    scopes = {payload["topic_scope"] for payload in queue.payloads()}
    counts = {payload["of_total"] for payload in queue.payloads()}

    assert len(queue.jobs) == 3
    assert scopes == {"đạo hàm của đa thức"}
    assert counts == {3}


@pytest.mark.asyncio
async def test_each_job_knows_which_question_of_the_set_it_is(stack) -> None:
    """Các ordinal đôi một khác nhau và phủ hết cả bộ.

    Các job chạy độc lập, nên không có gì điều phối chúng. Nói cho mỗi job biết
    vị trí của nó là cú đẩy rẻ nhất về phía sự đa dạng, và đó cũng là thứ cho
    `harvest` ghi chúng trở lại theo đúng thứ tự giáo viên đã yêu cầu.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 3)

    assert sorted(payload["ordinal"] for payload in queue.payloads()) == [1, 2, 3]


@pytest.mark.asyncio
async def test_harvest_writes_a_finished_question_in_full(stack) -> None:
    """Một câu hỏi về tới nơi dưới dạng một câu hỏi, kèm phương án và lời giải.

    ADR-18 nói một `Question` mang theo đáp án và các `Method` đã giải sẵn, nên
    một lượt `harvest` chỉ ghi `stem` sẽ cho ra một đề mà pha phụ đạo không dạy
    được từ đó.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 3)

    queue.finish("job-0", _good("Đạo hàm của y = x² là gì?"))

    async with maker() as session:
        landed = await drafting.harvest(session, queue, get_settings(), draft_id)

    assert landed == 1

    async with maker() as session:
        question = await session.scalar(select(Question).where(Question.assessment_id == draft_id))
        assert question is not None
        options = (
            await session.scalars(
                select(AnswerOption).where(AnswerOption.question_id == question.id)
            )
        ).all()
        methods = (
            await session.scalars(select(Method).where(Method.question_id == question.id))
        ).all()

    assert question.stem == "Đạo hàm của y = x² là gì?"
    assert len(options) == 3
    assert sum(1 for option in options if option.is_correct) == 1
    assert all(option.error_label for option in options if not option.is_correct)
    assert len(methods) == 2


@pytest.mark.asyncio
async def test_the_first_question_moves_the_draft_out_of_empty(stack) -> None:
    """`EMPTY → HAS_QUESTIONS` xảy ra qua `advance`, không phải bằng phép gán.

    State rỗng của ADR-01 chính là thứ chặn việc phát hành, nên cái khoảnh khắc nó
    thôi còn đúng phải đi qua đúng một cửa — cửa biết lifecycle.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 3)
        before = await session.get(Assessment, draft_id)
        assert before is not None and before.state == AssessmentState.EMPTY

    queue.finish("job-0", _good("Câu một"))

    async with maker() as session:
        await drafting.harvest(session, queue, get_settings(), draft_id)
        after = await session.get(Assessment, draft_id)

    assert after is not None
    assert after.state == AssessmentState.HAS_QUESTIONS


@pytest.mark.asyncio
async def test_a_question_that_breaks_adr_18_never_reaches_the_draft(stack) -> None:
    """Kiểm ở cửa vào, và hàng của chính ta cũng không được tin chỉ vì nó là của ta.

    AGENT tự kiểm và `fallback` sang nội dung soạn trước, nhưng lượt kiểm có giá
    trị là lượt này: đề nháp là thứ một giáo viên sẽ duyệt và một học sinh sẽ
    làm, nên một câu hỏi sai cấu trúc phải bị từ chối ở đây, hoặc không bao giờ.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 3)

    queue.finish("job-0", _two_right())

    async with maker() as session:
        landed = await drafting.harvest(session, queue, get_settings(), draft_id)
        questions = (
            await session.scalars(select(Question).where(Question.assessment_id == draft_id))
        ).all()
        item = await session.scalar(
            select(DraftItem).where(DraftItem.assessment_id == draft_id, DraftItem.ordinal == 1)
        )

    assert landed == 0
    assert questions == []
    # Vị trí ấy được hỏi lại NGAY, không phải chờ giáo viên nhờ lần nữa: hai phương án
    # cùng đánh dấu đúng là chuyện may rủi chứ không phải một lỗi cố định. Trước đợt này
    # nó dừng ở `retry` và chỉ `start_drafting` mới nhặt lên — nên một đề 3 câu đứng ở
    # 2/3 vĩnh viễn. Thứ ngăn nó lặp vô hạn là bộ đếm attempts, không phải status.
    assert item is not None and item.status == "pending"
    assert item.attempts == 2
    # Và lý do còn đọc được, chứ không chỉ nằm trong một dòng log không ai bật.
    assert item.last_fault == "câu trả về sai hình dạng ADR-18"


@pytest.mark.asyncio
async def test_two_jobs_returning_the_same_stem_yield_one_question(stack) -> None:
    """Các job độc lập có thể trùng nhau, và đề nháp không được hiện câu đó hai lần.

    Không có gì điều phối các job, nên hai job viết ra cùng một câu hỏi là kết
    cục bình thường chứ không phải bug — và một đề có cùng một câu hai lần thì tệ
    hơn một đề thiếu đi một câu.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 3)

    same = "Đạo hàm của y = x² là gì?"
    queue.finish("job-0", _good(same))
    queue.finish("job-1", _good(same))

    async with maker() as session:
        landed = await drafting.harvest(session, queue, get_settings(), draft_id)
        questions = (
            await session.scalars(select(Question).where(Question.assessment_id == draft_id))
        ).all()
        rows = {
            row.ordinal: (row.status, row.attempts, row.last_fault)
            for row in await session.scalars(
                select(DraftItem).where(DraftItem.assessment_id == draft_id)
            )
        }

    assert landed == 1
    assert len(questions) == 1

    # Đây là A3, đo được. Giáo viên xin 3 câu và nhận 2, âm thầm: ô 2 trùng câu của ô 1
    # nên bị đánh `retry`, mà `fire` chỉ được gọi từ `start_drafting` -- nên `retry` thực
    # tế nghĩa là **bỏ dở**. Năm mắt xích: `fire` tính `banned` một lần (rỗng, đề mới) →
    # ba job song song cùng cầm danh sách rỗng ấy → hai câu mở đầu giống nhau → ô 2 bị
    # loại → không ai bắn lại.
    #
    # Lượt bắn lại nằm **trong** `harvest`, không ngoài nó, vì đó là nơi `banned` đã có
    # câu vừa ghi: hỏi lại với một danh sách cũ là hỏi lại để trùng thêm một lần.
    assert rows[2][:2] == ("pending", 2)
    # Và lý do đọc được bằng một câu SQL. Một status `retry` không nói vì sao là một dấu
    # vết không dùng được -- đúng thứ đã biến A3 thành "không ai truy được".
    assert rows[2][2] == "đề trùng một câu đã có"


@pytest.mark.asyncio
async def test_a_result_that_aged_out_is_asked_again(stack) -> None:
    """Một câu trả lời bị mất thì `retry` được; một job đã ném exception thì không.

    Kết quả job sống được một giờ, nên một giáo viên bắt đầu soạn nháp rồi mai
    quay lại sẽ thấy chúng không còn — chuyện thường, và đáng thêm một job nữa.
    Một job đã chạy rồi *ném exception* thì khác: hỏi lại cũng nhận đúng cái hỏng
    đó, nên nó không đi qua bộ đếm attempts chút nào.

    Và khẳng định đáng giá nằm ở lượt `fire` thứ hai: một status mà không ai hành
    động theo thì chẳng chứng minh được gì, nên chỗ này kiểm rằng vị trí đó thật
    sự nhận một job mới, còn vị trí `failed` thì không.
    """
    maker, draft_id, queue = stack
    settings = get_settings()

    async with maker() as session:
        await drafting.fire(session, queue, settings, draft_id, 3)

    queue.lose("job-0")
    queue.break_("job-1")

    async with maker() as session:
        await drafting.harvest(session, queue, settings, draft_id)
        rows = {
            row.ordinal: row.status
            for row in await session.scalars(
                select(DraftItem).where(DraftItem.assessment_id == draft_id)
            )
        }

    # Ô 1 hết hạn trong Redis thì được hỏi lại **ngay trong lượt harvest ấy**; ô 2 có
    # job tự nổ nên bỏ cuộc, không thử lại. Trước đợt này ô 1 dừng ở `retry` và chờ một
    # cú `start_drafting` nữa — mà không có cú ấy thì nó chờ mãi.
    assert rows == {1: "pending", 2: "failed", 3: "pending"}

    async with maker() as session:
        after = {
            row.ordinal: (row.status, row.attempts, row.last_fault)
            for row in await session.scalars(
                select(DraftItem).where(DraftItem.assessment_id == draft_id)
            )
        }

    assert after[1] == ("pending", 2, "kết quả đã hết hạn trong Redis")
    # Job tự nổ thì KHÔNG đi qua bộ đếm: hỏi lại sẽ nhận đúng cái lỗi đó.
    assert after[2][:2] == ("failed", 1)


@pytest.mark.asyncio
async def test_a_question_keeps_the_position_it_was_asked_for(stack) -> None:
    """`order_index` lấy từ vị trí đã đặt hàng, không lấy từ thứ tự về đích.

    Các job chạy song song và xong theo đúng thứ tự model trả lời, điều mà lần
    chạy thật đầu tiên phơi ra rõ mồn một: ba job, ba thời điểm hoàn tất khác
    nhau. Vậy nên đánh số câu hỏi bằng một bộ đếm tăng dần đã xếp chúng lên đề
    theo thứ tự về đích — giáo viên đặt 1, 2, 3 thì nhận được 2, 3, 1, âm thầm,
    không có ràng buộc nào để mà vướng.
    """
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 3)

    # Job giữa và job cuối trả lời trước; job đầu vẫn đang chạy.
    queue.finish("job-1", _good("Câu hai"))
    queue.finish("job-2", _good("Câu ba"))

    async with maker() as session:
        await drafting.harvest(session, queue, get_settings(), draft_id)

    queue.finish("job-0", _good("Câu một"))

    async with maker() as session:
        await drafting.harvest(session, queue, get_settings(), draft_id)
        numbered = {
            question.order_index: question.stem
            for question in await session.scalars(
                select(Question).where(Question.assessment_id == draft_id)
            )
        }

    assert numbered == {1: "Câu một", 2: "Câu hai", 3: "Câu ba"}


@pytest.mark.asyncio
async def test_a_refused_question_is_asked_again_but_not_forever(stack) -> None:
    """Một câu trả lời sai cấu trúc tốn một lần `retry`, không tốn cả vị trí.

    Hai trong ba lý do từ chối là chuyện may rủi chứ không phải lỗi cố định: model
    đánh dấu hai phương án đều đúng, và hai job song song viết ra cùng một `stem`.
    Đóng dấu `failed` vĩnh viễn cho những ca đó đã làm đề nháp thiếu câu mãi mãi,
    và không gì — kể cả bắn lại — lấp được chỗ trống. Nhưng xoá dòng đó vô điều
    kiện lại là cái hỏng còn lại: một câu hỏi model không bao giờ làm đúng sẽ được
    đẩy lại vào queue ở mỗi lượt đọc, tiêu ngân sách đến vô tận.
    """
    maker, draft_id, queue = stack
    settings = get_settings()

    async with maker() as session:
        await drafting.fire(session, queue, settings, draft_id, 3)

    queue.finish("job-0", _two_right())

    async with maker() as session:
        await drafting.harvest(session, queue, settings, draft_id)
        # `harvest` tự bắn lại, nên không cần một cú `fire` nào ở giữa.
        asked = await session.scalar(
            select(DraftItem).where(DraftItem.assessment_id == draft_id, DraftItem.ordinal == 1)
        )

    assert asked is not None and (asked.status, asked.attempts) == ("pending", 2)

    # Vẫn câu trả lời đó hai lần nữa, và vị trí ấy bỏ cuộc thay vì lặp vô hạn.
    for job in ("job-3", "job-4"):
        queue.finish(job, _two_right())
        async with maker() as session:
            await drafting.harvest(session, queue, settings, draft_id)
            await drafting.fire(session, queue, settings, draft_id, 3)

    async with maker() as session:
        item = await session.scalar(
            select(DraftItem).where(DraftItem.assessment_id == draft_id, DraftItem.ordinal == 1)
        )
        # `wanted=0`: hỏi "còn ô nào cần bắn lại không" mà **không** xin thêm câu nào.
        # Một `fire(…, 3)` ở đây sẽ hợp lệ thêm ba ô mới, và che mất điều đang kiểm.
        again = await drafting.fire(session, queue, settings, draft_id, 0)

    assert item is not None and item.status == "failed"
    assert again == 0


@pytest.mark.asyncio
async def test_firing_twice_does_not_queue_the_same_position_twice(stack) -> None:
    """Hai lượt gọi tool tới cùng lúc tốn một bộ job, không phải hai.

    Đọc các vị trí đã bị chiếm và chèn dòng mới là hai câu lệnh, giữa chúng có một
    khoảng hở. Unique index là thứ phân định, và bên thua không được kéo theo ba
    job của chính nó xuống cùng — chúng đã ở trên queue và đã đang tiêu lượt gọi
    model.
    """
    maker, draft_id, queue = stack
    settings = get_settings()

    async with maker() as session:
        first = await drafting.fire(session, queue, settings, draft_id, 3)

    # `wanted=0`: không xin thêm câu nào, chỉ hỏi xem ba ô cũ có bị bắn lại không.
    # `fire(…, 3)` ở đây là **soạn thêm ba câu** — hợp lệ, nhưng là một câu hỏi khác.
    async with maker() as session:
        second = await drafting.fire(session, queue, settings, draft_id, 0)
        rows = (
            await session.scalars(select(DraftItem).where(DraftItem.assessment_id == draft_id))
        ).all()

    assert first == 3
    assert second == 0
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_a_brief_asking_for_more_than_the_contract_allows_fires_nothing(stack) -> None:
    """Mức trần được kiểm trước job đầu tiên, không phải phát hiện ở job thứ 51.

    `of_total` bị chặn ở 50 trong contract. Bắn từng job một có nghĩa là một brief
    đặt 60 câu sẽ đẩy năm mươi job vào queue rồi mới ném exception, để lại năm
    mươi lượt gọi model đang chạy, không có dòng nào để thu chúng về, và đúng
    chuyện đó lặp lại ở mỗi lần `retry`.
    """
    maker, draft_id, queue = stack

    # Con số tới từ **lời gọi**, không từ brief: một đề trống chưa có số câu nào để khai,
    # nên `start_drafting` mới là chỗ giáo viên nói ra nó. `fire` chặn một lần nữa cho
    # TỔNG sau khi cộng, vì xin thêm 10 câu vào một đề đã có 45 cũng vượt trần.
    async with maker() as session:
        queued = await drafting.fire(session, queue, get_settings(), draft_id, 60)

    assert queued == 0
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_a_new_brief_discards_questions_written_for_the_old_one(stack) -> None:
    """Viết lại brief là mở một vòng mới; nó không sửa việc đang bay giữa đường.

    Đây là tuyên bố mà cả thiết kế đặt lên — rằng một bộ câu hỏi được viết dựa trên
    một cách hiểu duy nhất về chủ đề. Không có nó, câu "làm khó hơn đi" sẽ để những
    job bắn theo scope cũ rơi vào cùng đề nháp với những job bắn theo scope mới, và
    đề sẽ nửa này nửa kia mà xét riêng từng câu thì chẳng câu nào trông sai.
    """
    maker, draft_id, queue = stack
    settings = get_settings()

    async with maker() as session:
        await drafting.fire(session, queue, settings, draft_id, 3)

    async with maker() as session:
        await drafting.rebrief(session, draft_id, topic_scope="tích phân", question_count=2)

    # Job bắn theo brief cũ trả lời sau khi brief mới đã được ghi.
    queue.finish("job-0", _good("Câu của brief cũ"))

    async with maker() as session:
        landed = await drafting.harvest(session, queue, settings, draft_id)
        questions = (
            await session.scalars(select(Question).where(Question.assessment_id == draft_id))
        ).all()

    assert landed == 0
    assert questions == []


@pytest.mark.asyncio
async def test_a_second_round_adds_on_top_instead_of_starting_over(stack) -> None:
    """Gọi `fire` lần nữa là **soạn thêm**, không phải soạn lại.

    Luật này được tuyên bố ở hai chỗ — comment của `fire` nói *"câu mới nối tiếp câu cũ,
    không ghi đè"*, docstring `start_drafting` nói *"gọi lại với số khác là soạn thêm"* — và
    trước test này **không chỗ nào đo nó**: mọi test gọi `fire` trên một đề mới, nơi
    `start = 0`, nên `total = start + wanted` và `total = wanted` cho cùng một kết quả. Đột
    biến bỏ `start +` sống sót qua cả bộ test.

    Thứ nó hỏng nếu mất: giáo viên có hai câu rồi xin thêm hai câu, và nhận lại **hai** câu —
    hai câu cũ bị hỏi lại thay vì giữ, hoặc bị ghi đè. Cộng thêm `brief.question_count` sai,
    mà `harvest` dùng chính con số ấy để biết ô nào đã cũ.
    """
    maker, draft_id, queue = stack
    settings = get_settings()

    async with maker() as session:
        await drafting.fire(session, queue, settings, draft_id, 2)

    queue.finish("job-0", _good("Câu một"))
    queue.finish("job-1", _good("Câu hai"))

    async with maker() as session:
        await drafting.harvest(session, queue, settings, draft_id)

    async with maker() as session:
        queued = await drafting.fire(session, queue, settings, draft_id, 2)
        rows = sorted(
            row.ordinal
            for row in await session.scalars(
                select(DraftItem).where(DraftItem.assessment_id == draft_id)
            )
        )
        brief = await session.get(DraftBrief, draft_id)

    # Hai ô MỚI, ở vị trí 3 và 4. Hai ô cũ không bị hỏi lại.
    assert queued == 2
    assert rows == [1, 2, 3, 4]
    # Và brief mang **tổng**, vì đó là con số `harvest` đọc để biết ô nào đã cũ.
    assert brief is not None and brief.question_count == 4


@pytest.mark.asyncio
async def test_the_cap_counts_the_questions_already_there(stack) -> None:
    """Mức trần tính trên **tổng**, và nó nói ra con số ấy bằng tiếng Việt.

    `fire` canh tổng nhưng chỉ `logger.warning` rồi `return 0`, mà caller dịch `queued == 0`
    thành *"có thể đề chưa có brief, hoặc hàng đợi đang hỏng"* — một lời từ chối nêu một
    nguyên nhân **không có thật**, và không chỗ nào nhắc tới con số 50. `too_many` là chỗ
    trần ấy có tiếng nói; `fire` giữ phép kiểm làm chốt cuối.

    Trước test này, đột biến `1 <= total` thành `1 <= wanted` sống sót: test trần duy nhất
    gọi `fire` trên một đề rỗng, tức đo trần của `wanted`.
    """
    maker, draft_id, queue = stack
    settings = get_settings()

    async with maker() as session:
        # Một đề đã gần đầy: 48 ô đã đặt.
        await drafting.fire(session, queue, settings, draft_id, 48)

    async with maker() as session:
        # Xin thêm 5 câu nữa: 48 + 5 = 53, quá trần.
        complaint = await drafting.too_many(session, draft_id, 5)
        queued = await drafting.fire(session, queue, settings, draft_id, 5)

    assert queued == 0
    # Câu nói chở cả ba con số, vì một lời từ chối không nói "còn mấy chỗ" thì giáo viên
    # phải đoán. Và nó không nhắc tới hàng đợi, vì hàng đợi không hỏng.
    assert "48" in complaint and "5" in complaint and "53" in complaint
    assert "hàng đợi" not in complaint

    async with maker() as session:
        # Và còn đúng 2 chỗ thì xin 2 câu vẫn được: trần là 50, không phải 48.
        assert await drafting.too_many(session, draft_id, 2) == ""
