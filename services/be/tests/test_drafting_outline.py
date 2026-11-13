"""Mỗi câu một job (ADR-29, ADR-38): AGENT chia dàn ý thành job, `fire` gán job thứ k cho câu mới
thứ k trước khi job nào chạy, và mỗi job soạn câu nhận đúng job của nó -- không chữ tài liệu nào.

Ba loại khẳng định. Gán theo đúng thứ tự AGENT chia (BE không chia gì). Soạn thêm nối job mới mà
không xáo job của câu đã có. Và một ô bắn lại mang lại đúng job của nó.
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
from be.drafting import item_fields
from be.seed import seed_if_empty
from contracts import (
    DraftQuestionCompleted,
    GeneratedOption,
    GeneratedQuestion,
    SolutionMethod,
)
from schema.ddl import prepare_schema
from schema.models import Assessment, DraftBrief, DraftItem, Question, Teacher


class FakeQueue:
    """Ghi lại những gì đã vào queue."""

    def __init__(self) -> None:
        self.payloads: list[dict] = []

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str):
        self.payloads.append(payload)
        return type("Queued", (), {"job_id": f"job-{len(self.payloads)}"})()


def _outline(*parts: tuple[int, str], version: int = 1) -> dict:
    """Dàn ý đã xem kèm các job, đúng hình dạng `teacher_chat.guard_drafting` trả: phần dàn ý phủ k
    câu thì k job một câu, cùng kiến thức (ADR-38)."""
    return {
        "version": version,
        "first": 1,
        "total": sum(count for count, _ in parts),
        "for": "new",
        "document_id": "",
        "nodes": [],
        "items": [
            {
                "questions": 1,
                "knowledge": knowledge,
                "formulas": [f"${knowledge[0]}$"],
                "approach": f"cách làm {knowledge}",
            }
            for count, knowledge in parts
            for _ in range(count)
        ],
    }


@pytest_asyncio.fixture
async def stack():
    """Một đề nháp rỗng có brief, chưa có dàn ý nào."""
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
                topic_scope="Chương I",
                question_count=0,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
        draft_id = draft.id
    yield maker, draft_id, FakeQueue()
    await engine.dispose()
    db_module._SESSION_MAKER = None


# ------------------------------------------------------------------ hàm thuần


def test_a_slot_from_before_the_outline_gets_no_item_fields() -> None:
    brief = DraftBrief(assessment_id="a", topic_scope="x", question_count=1, outline=[])

    assert item_fields(brief, None, 1) == {}


# ------------------------------------------------------------------ fire


@pytest.mark.asyncio
async def test_a_job_receives_exactly_its_outline_item(stack) -> None:
    """Tên giữ từ ADR-29 (`AGENTS.md` trỏ tới nó): nay "mục" là job AGENT chia (ADR-38)."""
    maker, draft_id, queue = stack

    async with maker() as session:
        await drafting.fire(
            session, queue, get_settings(), draft_id, 3, _outline((1, "A"), (2, "B"))
        )

    by_ordinal = {one["ordinal"]: one for one in queue.payloads}
    assert by_ordinal[1]["item_knowledge"] == "A"
    assert by_ordinal[1]["item_formulas"] == ["$A$"]
    assert by_ordinal[1]["item_approach"] == "cách làm A"
    assert (by_ordinal[1]["item_part"], by_ordinal[1]["item_parts"]) == (1, 1)
    assert by_ordinal[1]["other_items"] == ["B"]
    # Mỗi job một câu: không còn *"câu thứ mấy của mục"* -- câu anh em khác nhau ở lời dặn agent
    # viết, không ở số thứ tự BE đếm.
    assert [(by_ordinal[n]["item_part"], by_ordinal[n]["item_parts"]) for n in (2, 3)] == [
        (1, 1),
        (1, 1),
    ]
    # Không chữ tài liệu nào (ADR-29).
    assert not any(key.startswith("focus_") for one in queue.payloads for key in one)

    async with maker() as session:
        brief = await session.get(DraftBrief, draft_id)
        rows = {row.ordinal: row for row in await session.scalars(select(DraftItem))}
    assert [item["knowledge"] for item in brief.outline] == ["A", "B", "B"]
    assert all(item["version"] == 1 for item in brief.outline)
    assert {n: (row.outline_item, row.item_part) for n, row in rows.items()} == {
        1: (0, 1),
        2: (1, 1),
        3: (2, 1),
    }


@pytest.mark.asyncio
async def test_drafting_more_appends_items_and_leaves_the_first_questions_alone(stack) -> None:
    maker, draft_id, queue = stack
    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 2, _outline((2, "A")))
        rows = list(await session.scalars(select(DraftItem)))
        for row in rows:
            row.status = "ready"
        await session.commit()

    async with maker() as session:
        await drafting.fire(
            session, queue, get_settings(), draft_id, 1, _outline((1, "C"), version=2)
        )

    added = queue.payloads[-1]
    assert (added["ordinal"], added["item_knowledge"], added["other_items"]) == (3, "C", ["A"])
    async with maker() as session:
        brief = await session.get(DraftBrief, draft_id)
        rows = {row.ordinal: row.outline_item for row in await session.scalars(select(DraftItem))}
    assert [(item["knowledge"], item["version"]) for item in brief.outline] == [
        ("A", 1),
        ("A", 1),
        ("C", 2),
    ]
    assert rows == {1: 0, 2: 1, 3: 2}


@pytest.mark.asyncio
async def test_a_slot_fired_again_carries_its_own_item_again(stack) -> None:
    maker, draft_id, queue = stack
    async with maker() as session:
        await drafting.fire(
            session, queue, get_settings(), draft_id, 2, _outline((1, "A"), (1, "B"))
        )
        second = await session.scalar(select(DraftItem).where(DraftItem.ordinal == 2))
        second.status = "retry"
        await session.commit()

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 0)

    again = queue.payloads[-1]
    assert (again["ordinal"], again["item_knowledge"], again["other_items"]) == (2, "B", ["A"])


def test_two_items_on_the_same_knowledge_do_not_tell_each_other_to_stay_away() -> None:
    """Cùng bài, khác cách làm là được phép: job không bị dặn né chính kiến thức của nó."""
    same = [
        {"questions": 1, "knowledge": "A", "formulas": [], "approach": "cách 1"},
        {"questions": 1, "knowledge": "A", "formulas": [], "approach": "cách 2"},
        {"questions": 1, "knowledge": "B", "formulas": [], "approach": "cách 3"},
    ]
    brief = DraftBrief(assessment_id="a", topic_scope="x", question_count=3, outline=same)

    assert item_fields(brief, 1, 1)["other_items"] == ("B",)


# ------------------------------------------------------------------ thay một câu


class HarvestingQueue(FakeQueue):
    """`FakeQueue` biết trả kết quả cho `harvest`."""

    def __init__(self) -> None:
        super().__init__()
        self.results: dict[str, tuple[str, object]] = {}

    def finish(self, job_id: str, stem: str) -> None:
        question = GeneratedQuestion(
            stem=stem,
            options=(
                GeneratedOption(label="A", text="đúng", is_correct=True),
                GeneratedOption(label="B", text="sai", is_correct=False, error_label="lỗi B"),
            ),
            methods=(SolutionMethod(title="1", body="..."), SolutionMethod(title="2", body="...")),
            learning_objective="x",
        )
        self.results[job_id] = (
            "ready",
            DraftQuestionCompleted(request_id="r", question=question).model_dump(mode="json"),
        )


async def _two_questions(maker, draft_id, queue, monkeypatch) -> None:
    async def collect(pool, settings, job_id):
        return queue.results.get(job_id, ("pending", None))

    monkeypatch.setattr(drafting, "collect_result", collect)
    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 2, _outline((2, "A")))
    queue.finish("job-1", "Câu một cũ")
    queue.finish("job-2", "Câu hai cũ")
    async with maker() as session:
        assert await drafting.harvest(session, queue, get_settings(), draft_id) == 2


def _stems(rows) -> dict[int, str]:
    return {row.order_index: row.stem for row in rows}


@pytest.mark.asyncio
async def test_a_replaced_question_stays_until_its_successor_lands(stack, monkeypatch) -> None:
    maker, draft_id, _ = stack
    queue = HarvestingQueue()
    await _two_questions(maker, draft_id, queue, monkeypatch)

    async with maker() as session:
        assert await drafting.replace(
            session, queue, get_settings(), draft_id, 2, _outline((1, "C"), version=2)
        )
    asked = queue.payloads[-1]
    assert (asked["ordinal"], asked["item_knowledge"], asked["other_items"]) == (2, "C", ["A"])
    # Câu mới chưa về: câu cũ vẫn trong đề.
    async with maker() as session:
        assert _stems(
            await session.scalars(select(Question).where(Question.assessment_id == draft_id))
        ) == {
            1: "Câu một cũ",
            2: "Câu hai cũ",
        }

    queue.finish("job-3", "Câu hai mới")
    async with maker() as session:
        assert await drafting.harvest(session, queue, get_settings(), draft_id) == 1
        row = await session.scalar(
            select(DraftItem).where(DraftItem.assessment_id == draft_id, DraftItem.ordinal == 2)
        )
        stems = _stems(
            await session.scalars(select(Question).where(Question.assessment_id == draft_id))
        )
    assert stems == {1: "Câu một cũ", 2: "Câu hai mới"}
    # Hai câu đầu là hai job (A, A); job thay câu nối sau chúng, ở chỉ số 2.
    assert (row.status, row.replacing, row.outline_item) == ("ready", False, 2)


@pytest.mark.asyncio
async def test_a_replacement_whose_job_breaks_leaves_the_old_question(stack, monkeypatch) -> None:
    maker, draft_id, _ = stack
    queue = HarvestingQueue()
    await _two_questions(maker, draft_id, queue, monkeypatch)
    async with maker() as session:
        await drafting.replace(
            session, queue, get_settings(), draft_id, 1, _outline((1, "C"), version=2)
        )
    queue.results["job-3"] = ("failed", None)

    async with maker() as session:
        await drafting.harvest(session, queue, get_settings(), draft_id)
        row = await session.scalar(
            select(DraftItem).where(DraftItem.assessment_id == draft_id, DraftItem.ordinal == 1)
        )
        stems = _stems(
            await session.scalars(select(Question).where(Question.assessment_id == draft_id))
        )

    # Job thay hỏng thì được hỏi lại (plan `backlog-tier-1`), câu cũ vẫn đứng đó trong lúc chờ.
    assert stems[1] == "Câu một cũ"
    assert (row.status, row.replacing) == ("pending", True)
    assert row.last_fault == "model không soạn được câu này"


@pytest.mark.asyncio
async def test_a_replacement_out_of_attempts_leaves_the_old_question(stack, monkeypatch) -> None:
    maker, draft_id, _ = stack
    queue = HarvestingQueue()
    await _two_questions(maker, draft_id, queue, monkeypatch)
    async with maker() as session:
        await drafting.replace(
            session, queue, get_settings(), draft_id, 1, _outline((1, "C"), version=2)
        )
        row = await session.scalar(
            select(DraftItem).where(DraftItem.assessment_id == draft_id, DraftItem.ordinal == 1)
        )
        row.attempts = drafting._MOST_ATTEMPTS
        await session.commit()
    queue.results["job-3"] = ("gone", None)

    async with maker() as session:
        await drafting.harvest(session, queue, get_settings(), draft_id)
        row = await session.scalar(
            select(DraftItem).where(DraftItem.assessment_id == draft_id, DraftItem.ordinal == 1)
        )
        stems = _stems(
            await session.scalars(select(Question).where(Question.assessment_id == draft_id))
        )

    assert stems[1] == "Câu một cũ"
    assert (row.status, row.replacing) == ("ready", False)
    # Ô thôi trỏ mục mới: câu ở đó là câu cũ, và câu làm lại ở pha 2 đọc mục của ô
    # (`retry-sees-its-outline-item`, review pha 2).
    assert row.outline_item is None


@pytest.mark.asyncio
async def test_a_question_already_swapped_is_not_swapped_again(stack, monkeypatch) -> None:
    """Hai lần thu cùng giữ một ô đang thay: lần sau không gỡ câu mới lần trước vừa ghi."""
    maker, draft_id, _ = stack
    queue = HarvestingQueue()
    await _two_questions(maker, draft_id, queue, monkeypatch)
    async with maker() as session:
        await drafting.replace(
            session, queue, get_settings(), draft_id, 2, _outline((1, "C"), version=2)
        )
        old_id = (
            await session.scalar(
                select(DraftItem).where(DraftItem.assessment_id == draft_id, DraftItem.ordinal == 2)
            )
        ).replaces_question_id
    queue.finish("job-3", "Câu hai mới")
    async with maker() as session:
        await drafting.harvest(session, queue, get_settings(), draft_id)
        # Lần thu thứ hai, trễ hơn, vẫn thấy ô ở trạng thái lúc trước khi tráo.
        row = await session.scalar(
            select(DraftItem).where(DraftItem.assessment_id == draft_id, DraftItem.ordinal == 2)
        )
        row.status, row.replacing, row.replaces_question_id = "pending", True, old_id
        await session.commit()
    queue.finish("job-3", "Câu hai mới hơn nữa")

    async with maker() as session:
        await drafting.harvest(session, queue, get_settings(), draft_id)
        stems = _stems(
            await session.scalars(select(Question).where(Question.assessment_id == draft_id))
        )

    assert stems[2] == "Câu hai mới"


def _locked_tables(session) -> list[str]:
    """Bọc `session.scalar` để ghi tên bảng của mọi câu `select … FOR UPDATE` đi qua nó.

    SQLite bỏ `FOR UPDATE` lúc biên dịch, nên test đua thật không dựng được ở đây; test đơn vị đọc
    chính câu lệnh: khoá có được xin không (plan `backlog-tier-1`, việc 15).
    """
    seen: list[str] = []
    real = session.scalar

    async def scalar(statement, *args, **kwargs):
        if getattr(statement, "_for_update_arg", None) is not None:
            seen.extend(table.name for table in statement.get_final_froms())
        return await real(statement, *args, **kwargs)

    session.scalar = scalar
    return seen


@pytest.mark.asyncio
async def test_firing_and_replacing_lock_the_paper_then_its_brief(stack, monkeypatch) -> None:
    """Review code pha 5: `fire` và `replace` cùng đọc-sửa-ghi `brief.outline`; cả hai phải khoá
    đề rồi brief, cùng một thứ tự, không thì hai bên đua làm mất mục của nhau."""
    maker, draft_id, _ = stack
    queue = HarvestingQueue()
    await _two_questions(maker, draft_id, queue, monkeypatch)

    async with maker() as session:
        fired = _locked_tables(session)
        await drafting.fire(
            session, queue, get_settings(), draft_id, 1, _outline((1, "B"), version=2)
        )
    async with maker() as session:
        replaced = _locked_tables(session)
        await drafting.replace(
            session, queue, get_settings(), draft_id, 2, _outline((1, "C"), version=3)
        )

    assert fired[:2] == ["assessments", "draft_briefs"]
    assert replaced[:2] == ["assessments", "draft_briefs"]


# ------------------------------------------------------------------ review pha 2 (ADR-38)


def _jobs(*jobs: tuple[str, str], version: int = 1) -> dict:
    """Dàn ý đã xem kèm job AGENT chia, mỗi job một nhãn phần và một kiến thức riêng."""
    return {
        "version": version,
        "first": 1,
        "total": len(jobs),
        "for": "new",
        "document_id": "",
        "nodes": [],
        "items": [
            {
                "questions": 1,
                "part": part,
                "knowledge": knowledge,
                "formulas": [],
                "approach": f"cách làm {knowledge}",
            }
            for part, knowledge in jobs
        ],
    }


@pytest.mark.asyncio
async def test_each_question_gets_its_own_job_and_siblings_are_not_off_limits(stack) -> None:
    """Review pha 2: AGENT viết kiến thức riêng cho từng job, nên hai câu cùng phần thường khác vài
    chữ. Câu anh em không bị dặn né chủ đề của nhau; phần khác thì vẫn né."""
    maker, draft_id, queue = stack
    split = _jobs(
        ("Câu 1–2", "Vi-ét"), ("Câu 1–2", "Vi-ét cho tổng hai nghiệm"), ("Câu 3", "Delta")
    )

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 3, split)

    by_ordinal = {one["ordinal"]: one for one in queue.payloads}
    assert [by_ordinal[n]["item_knowledge"] for n in (1, 2, 3)] == [
        "Vi-ét",
        "Vi-ét cho tổng hai nghiệm",
        "Delta",
    ]
    assert by_ordinal[2]["item_approach"] == "cách làm Vi-ét cho tổng hai nghiệm"
    assert by_ordinal[1]["other_items"] == ["Delta"]
    assert by_ordinal[3]["other_items"] == ["Vi-ét", "Vi-ét cho tổng hai nghiệm"]


def test_one_label_for_every_job_tells_nothing_so_the_words_decide() -> None:
    """Model ghi cùng một nhãn (tên bài) cho mọi job: nhãn không phân biệt gì, luật chữ cũ đứng."""
    same = _jobs(("Bài 1", "A"), ("Bài 1", "B"))["items"]
    brief = DraftBrief(
        assessment_id="a",
        topic_scope="x",
        question_count=2,
        outline=[{**one, "version": 1} for one in same],
    )

    assert item_fields(brief, 0, 1)["other_items"] == ("B",)


@pytest.mark.asyncio
async def test_a_round_whose_jobs_do_not_match_its_count_drafts_nothing(stack) -> None:
    """Review pha 2: lớp kiểm thứ hai sau `guard_drafting` -- câu thiếu job không được lặng lẽ soạn
    theo `topic_scope`."""
    maker, draft_id, queue = stack

    async with maker() as session:
        queued = await drafting.fire(
            session, queue, get_settings(), draft_id, 3, _jobs(("Câu 1", "A"), ("Câu 2", "B"))
        )

    assert queued == 0 and queue.payloads == []


@pytest.mark.asyncio
async def test_a_slot_of_an_older_outline_item_keeps_its_part_when_fired_again(stack) -> None:
    """Đề soạn trước ADR-38 có mục nhiều câu (`questions=2`): ô `retry` của câu thứ hai vẫn nói mình
    là câu 2/2 của mục -- đường đề cũ ở lại cho ô bắn lại, *Thử lại* và câu làm lại."""
    maker, draft_id, queue = stack
    async with maker() as session:
        brief = await session.get(DraftBrief, draft_id)
        brief.outline = [
            {"questions": 2, "knowledge": "A", "formulas": [], "approach": "x", "version": 1}
        ]
        brief.question_count = 2
        for ordinal, part in ((1, 1), (2, 2)):
            session.add(
                DraftItem(
                    assessment_id=draft_id,
                    ordinal=ordinal,
                    job_id=f"old-{ordinal}",
                    status="ready" if ordinal == 1 else "retry",
                    attempts=1,
                    brief_version=brief.version,
                    created_at=datetime.now(UTC),
                    outline_item=0,
                    item_part=part,
                )
            )
        await session.commit()

    async with maker() as session:
        await drafting.fire(session, queue, get_settings(), draft_id, 0)

    again = queue.payloads[-1]
    assert (again["ordinal"], again["item_part"], again["item_parts"]) == (2, 2, 2)
