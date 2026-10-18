"""Hai lưới lúc thu hoạch một câu soạn nháp (việc 13 của plan `wave-3-draft-panel`).

Cả hai ca đều đã xảy ra trên dữ liệu thật:

- **Hai phương án cùng chữ.** `validate_question` từ chối cả câu, nên một câu tốt mất một lượt chỉ
  vì một phương án nhiễu lặp lại. Nay trùng thì giữ một: phương án khoá luôn ở lại, nhãn đánh lại.
  Còn dưới ba phương án thì không còn là một câu trắc nghiệm đáng giữ, và ô được thử lại.
- **Lời giải chọn một phương án khác phương án khoá** (GIF lượt 4, câu 5: hai cách giải ra
  23 000 đồng mà khoá B. 27 000 đồng). Lời giải nói *"chọn X"* hay *"đáp án là X"* mà X không phải
  nhãn khoá thì ô được thử lại.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import drafting
from be.assessment_state import AssessmentState
from be.config import get_settings
from be.db import bind_sessions
from be.seed import seed_if_empty
from contracts import DraftQuestionCompleted, GeneratedOption, GeneratedQuestion, SolutionMethod
from schema.ddl import prepare_schema
from schema.models import AnswerOption, Assessment, DraftBrief, DraftItem, Question, Teacher


def _question(options: list[tuple[str, bool]], methods: tuple[str, str] = (".", ".")):
    """Một câu với các phương án `(chữ, khoá)`, nhãn A, B, C… theo thứ tự, và hai lời giải."""
    return GeneratedQuestion(
        stem="Mua 3 vở và 2 bút hết bao nhiêu tiền?",
        options=tuple(
            GeneratedOption(
                label="ABCDE"[index],
                text=text,
                is_correct=locked,
                error_label=None if locked else f"lỗi {index}",
            )
            for index, (text, locked) in enumerate(options)
        ),
        methods=tuple(
            SolutionMethod(title=f"Cách {n}", body=body) for n, body in enumerate(methods)
        ),
        learning_objective="nhân và cộng",
    )


# ------------------------------------------------------------------ gộp phương án trùng


def test_a_repeated_distractor_is_dropped_and_the_labels_close_up() -> None:
    asked = _question([("23 000", True), ("27 000", False), ("27  000", False), ("30 000", False)])

    tidy = drafting.tidy_options(asked)

    assert tidy is not None
    assert [(one.label, one.text, one.is_correct) for one in tidy.options] == [
        ("A", "23 000", True),
        ("B", "27 000", False),
        ("C", "30 000", False),
    ]


def test_a_distractor_repeating_the_locked_option_never_pushes_the_locked_one_out() -> None:
    """Phương án nhiễu đứng **trước** và trùng chữ phương án khoá: phương án khoá vẫn ở lại."""
    asked = _question([("27 000", False), ("23 000", False), ("23 000", True), ("30 000", False)])

    tidy = drafting.tidy_options(asked)

    assert tidy is not None
    assert [(one.label, one.text, one.is_correct) for one in tidy.options] == [
        ("A", "27 000", False),
        ("B", "23 000", True),
        ("C", "30 000", False),
    ]
    assert tidy.options[1].error_label is None


def test_too_few_options_left_after_merging_is_no_question() -> None:
    asked = _question([("23 000", True), ("27 000", False), ("27 000", False)])

    assert drafting.tidy_options(asked) is None


def test_a_question_without_repeats_comes_back_untouched() -> None:
    asked = _question([("23 000", True), ("27 000", False)])

    assert drafting.tidy_options(asked) is asked


# ------------------------------------------------------------------ lời giải chọn phương án khác


@pytest.mark.parametrize(
    "body",
    [
        "Tổng là 23 000 đồng. Chọn A.",
        "Vậy đáp án là C",
        "Đáp án đúng là C.",
        "Đáp án: C",
        "chọn đáp án C",
        "Vậy **Chọn C**.",
        "Đáp án: $C$",
    ],
)
def test_a_solution_naming_another_option_is_caught(body: str) -> None:
    asked = _question([("27 000", False), ("30 000", False), ("23 000", True)], (".", body))
    locked_b = _question([("27 000", False), ("23 000", True), ("30 000", False)], (".", body))

    assert drafting.names_another_option(locked_b)
    # Cùng lời giải, khoá đúng ở nhãn được nêu: không có gì để bắt (trừ ca "Chọn A").
    assert drafting.names_another_option(asked) == ("Chọn A" in body)


@pytest.mark.parametrize(
    "body",
    [
        "Chọn a = 2 thì phương trình có nghiệm.",
        "Đáp án A sai vì quên nhân 3.",
        "Không chọn A vì đã quên cộng.",
        "Ta chọn x = 3.",
        # Review pha 2: giả định, cảnh báo, tên điểm, kể nhiều nhãn -- không phải một kết luận.
        "Nếu chọn A là đã quên nhân 3.",
        "Học sinh hay chọn A vì quên cộng.",
        "Không nên chọn A.",
        "Chọn A = 2 rồi thay vào.",
        "Chọn C(1; 2) là một điểm trên đồ thị.",
        "Đáp án: A và C đều sai.",
        # Chỉ lần chọn cuối là kết luận; lần trước là bước thử.
        "Thử chọn A: ra 27 000, sai. Vậy chọn B.",
    ],
)
def test_words_that_only_look_like_a_choice_are_not_caught(body: str) -> None:
    asked = _question([("27 000", False), ("23 000", True), ("30 000", False)], (".", body))

    assert not drafting.names_another_option(asked)


def test_a_label_the_merge_moved_is_caught_against_the_new_label() -> None:
    """Phương án khoá dời từ B về A vì gộp, lời giải còn nói *"Chọn B"*: bắt."""
    asked = _question(
        [("23 000", False), ("23 000", True), ("27 000", False), ("30 000", False)],
        (".", "Tổng 23 000 đồng. Chọn B."),
    )

    tidy = drafting.tidy_options(asked)

    assert tidy is not None
    assert [one.label for one in tidy.options if one.is_correct] == ["A"]
    assert drafting.names_another_option(tidy)


# ------------------------------------------------------------------ qua `harvest`


class FakeQueue:
    """Ghi lại job được đẩy vào queue và trả kết quả ra khi được hỏi."""

    def __init__(self) -> None:
        self.jobs: list[str] = []
        self.results: dict[str, tuple[str, object]] = {}

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str):
        job_id = f"job-{len(self.jobs)}"
        self.jobs.append(job_id)
        return type("Queued", (), {"job_id": job_id})()

    def finish(self, job_id: str, question: GeneratedQuestion) -> None:
        self.results[job_id] = (
            "ready",
            DraftQuestionCompleted(request_id="r", question=question).model_dump(mode="json"),
        )


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """Một đề nháp trống có brief một câu, và một queue giả."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        teacher = await session.scalar(select(Teacher))
        draft = Assessment(
            teacher_id=teacher.id,
            title="Nháp",
            subject="Toán",
            grade="6",
            state=AssessmentState.EMPTY,
            created_at=datetime.now(UTC),
        )
        session.add(draft)
        await session.flush()
        session.add(
            DraftBrief(
                assessment_id=draft.id,
                topic_scope="nhân và cộng",
                question_count=1,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
        draft_id = draft.id

    queue = FakeQueue()

    async def collect(_pool, _settings, job_id):
        return queue.results.get(job_id, ("pending", None))

    monkeypatch.setattr(drafting, "collect_result", collect)
    yield maker, draft_id, queue
    await engine.dispose()
    db_module._SESSION_MAKER = None


@pytest.mark.asyncio
async def test_harvest_keeps_a_question_whose_only_flaw_was_a_repeated_distractor(stack) -> None:
    maker, draft_id, queue = stack
    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 1)
    queue.finish(
        "job-0",
        _question([("23 000", True), ("27 000", False), ("27 000", False), ("30 000", False)]),
    )

    async with maker() as session:
        landed = await drafting.harvest(session, queue, get_settings(), draft_id)
        labels = list(
            await session.scalars(
                select(AnswerOption.label)
                .join(Question, Question.id == AnswerOption.question_id)
                .where(Question.assessment_id == draft_id)
                .order_by(AnswerOption.label)
            )
        )

    assert landed == 1
    assert labels == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_harvest_asks_again_when_the_solution_picks_another_option(stack) -> None:
    maker, draft_id, queue = stack
    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 1)
    queue.finish(
        "job-0",
        _question(
            [("27 000", False), ("23 000", True), ("30 000", False)],
            ("3 × 5 000 + 2 × 4 000 = 23 000.", "Tổng 27 000 đồng. Chọn A."),
        ),
    )

    async with maker() as session:
        landed = await drafting.harvest(session, queue, get_settings(), draft_id)
        row = await session.scalar(select(DraftItem).where(DraftItem.assessment_id == draft_id))

    assert landed == 0
    assert row.last_fault == "lời giải chọn phương án khác phương án khoá"
    # Ô được bắn lại ngay, như mọi lần thử lại khác của `harvest`.
    assert (row.status, len(queue.jobs)) == ("pending", 2)


@pytest.mark.asyncio
async def test_harvest_asks_again_when_merging_leaves_too_few_options(stack) -> None:
    maker, draft_id, queue = stack
    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 1)
    queue.finish("job-0", _question([("23 000", True), ("27 000", False), ("27 000", False)]))

    async with maker() as session:
        landed = await drafting.harvest(session, queue, get_settings(), draft_id)
        row = await session.scalar(select(DraftItem).where(DraftItem.assessment_id == draft_id))

    assert landed == 0
    assert row.last_fault == "phương án trùng nhau, còn quá ít sau khi gộp"
