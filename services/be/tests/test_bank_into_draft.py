"""Giáo viên lấy câu từ ngân hàng vào một đề còn mở (việc 17, plan `question-bank-into-draft`).

Bốn luật được canh ở đây:

- **Câu vào đề là một bản chép** mang `source="bank"` và `bank_question_id`, đủ phương án và lời
  giải, đứng sau câu cao nhất, và có ô soạn `ready` của nó -- để lần soạn thêm sau nối tiếp.
- **Câu đã có thì bỏ qua**, theo cả hai chiều chép: lấy vào từ trước, hay câu được duyệt từ chính
  đề này. Hộp chọn khoá đúng những câu ấy.
- **Duyệt không chép lại** câu lấy từ ngân hàng: không có bản thứ hai.
- **Cửa của mọi đường ghi câu**: đề của người khác 404, đề đã khoá và đề còn câu đang soạn 409.

Khoá ngoại **bật** trên SQLite, như `test_delete_question.py`: hai bảng trỏ vào nhau
(`questions.bank_question_id` ↔ `bank_questions.question_id`), và thứ tự ghi sai chỉ đỏ ở đó.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import drafting
from be.config import get_settings
from be.db import bind_sessions
from be.seed import seed_if_empty
from be.teacher_routes import router as assessment_router
from contracts import DraftQuestionCompleted, GeneratedOption, GeneratedQuestion, SolutionMethod
from schema.ddl import prepare_schema
from schema.models import (
    AnswerOption,
    Assessment,
    AssessmentState,
    BankQuestion,
    DraftBrief,
    DraftItem,
    Method,
    Question,
    Teacher,
)

TEACHER = {"X-Actor": "teacher:GV-001"}
STRANGER = {"X-Actor": "teacher:GV-002"}


class FakeQueue:
    """Ghi lại job được đẩy vào queue, và trả lời cho các job mà test cho là đã xong."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, dict]] = []
        self.results: dict[str, tuple[str, object]] = {}

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str):
        job_id = f"job-{len(self.jobs)}"
        self.jobs.append((name, payload))
        return type("Queued", (), {"job_id": job_id})()

    def finish(self, job_id: str, stem: str) -> None:
        """Nói rằng job đó đã xong, với một câu đủ chuẩn ADR-18."""
        question = GeneratedQuestion(
            stem=stem,
            options=(
                GeneratedOption(label="A", text="đúng", is_correct=True),
                GeneratedOption(label="B", text="sai", is_correct=False, error_label="lỗi B"),
            ),
            methods=(
                SolutionMethod(title="Cách 1", body="..."),
                SolutionMethod(title="Cách 2", body="..."),
            ),
            learning_objective="đạo hàm",
        )
        self.results[job_id] = (
            "ready",
            DraftQuestionCompleted(request_id="r", question=question).model_dump(mode="json"),
        )


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """Một app có hai giáo viên, và SQLite **bật khoá ngoại**."""
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _foreign_keys(connection, _record) -> None:
        # Chỉ sqlite cần bật; Postgres luôn thi hành khoá ngoại (plan `postgres-test-run`).
        if engine.dialect.name != "sqlite":
            return
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    await prepare_schema(engine)
    bind_sessions(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        session.add(Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002"))
        await session.commit()

    queue = FakeQueue()

    async def collect(_pool, _settings, job_id):
        return queue.results.get(job_id, ("pending", None))

    monkeypatch.setattr(drafting, "collect_result", collect)

    app = FastAPI()
    app.include_router(assessment_router)
    app.state.queue_pool = queue

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker, queue

    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _teacher(session, code: str) -> Teacher:
    return await session.scalar(select(Teacher).where(Teacher.teacher_code == code))


async def _draft(maker, questions: int, teacher_code: str = "GV-001") -> str:
    """Một đề nháp có `questions` câu Kriky soạn đã xong, mỗi câu một ô `ready`, có brief."""
    async with maker() as session:
        owner = await _teacher(session, teacher_code)
        draft = Assessment(
            teacher_id=owner.id,
            title="Đề nháp đạo hàm",
            subject="Toán",
            grade="12",
            state=AssessmentState.HAS_QUESTIONS if questions else AssessmentState.EMPTY,
            created_at=datetime.now(UTC),
        )
        session.add(draft)
        await session.flush()
        session.add(
            DraftBrief(
                assessment_id=draft.id,
                topic_scope="đạo hàm",
                question_count=questions,
                version=1,
                created_at=datetime.now(UTC),
            )
        )
        for index in range(1, questions + 1):
            question = Question(
                assessment_id=draft.id,
                order_index=index,
                stem=f"Câu {index}?",
                learning_objective="đạo hàm",
            )
            session.add(question)
            await session.flush()
            session.add(
                AnswerOption(question_id=question.id, label="A", text="đúng", is_correct=True)
            )
            session.add(
                AnswerOption(
                    question_id=question.id,
                    label="B",
                    text="sai",
                    is_correct=False,
                    error_label="lỗi B",
                )
            )
            session.add(Method(question_id=question.id, order_index=1, title="Cách 1", body="."))
            session.add(Method(question_id=question.id, order_index=2, title="Cách 2", body="."))
            session.add(
                DraftItem(
                    assessment_id=draft.id,
                    ordinal=index,
                    job_id=f"seeded-{index}",
                    status="ready",
                    brief_version=1,
                    attempts=1,
                    created_at=datetime.now(UTC),
                )
            )
        await session.commit()
        return draft.id


async def _banked(maker, stems: list[str], teacher_code: str = "GV-001") -> list[str]:
    """Các dòng ngân hàng của một giáo viên, mỗi dòng ba phương án và hai lời giải."""
    async with maker() as session:
        owner = await _teacher(session, teacher_code)
        source = Assessment(
            teacher_id=owner.id,
            title="Đề tuần 3 — Đạo hàm",
            subject="Toán",
            grade="12",
            state=AssessmentState.APPROVED,
            created_at=datetime.now(UTC),
        )
        session.add(source)
        await session.flush()
        ids = []
        for stem in stems:
            row = BankQuestion(
                teacher_id=owner.id,
                assessment_id=source.id,
                stem=stem,
                learning_objective="đạo hàm",
                options=[
                    {"label": "A", "text": "2x", "is_correct": True, "error_label": None},
                    {"label": "B", "text": "x", "is_correct": False, "error_label": "quên hệ số"},
                    {"label": "C", "text": "x²", "is_correct": False, "error_label": "không lấy"},
                ],
                methods=[{"title": "Cách 1", "body": "a"}, {"title": "Cách 2", "body": "b"}],
                created_at=datetime.now(UTC),
                approved_at=datetime.now(UTC),
            )
            session.add(row)
            await session.flush()
            ids.append(row.id)
        await session.commit()
        return ids


async def _take(http, draft: str, bank_ids: list[str], headers=TEACHER):
    return await http.post(
        f"/api/teacher/assessments/{draft}/bank-questions",
        json={"bank_ids": bank_ids},
        headers=headers,
    )


# ------------------------------------------------------------------ bản chép


@pytest.mark.asyncio
async def test_picked_questions_are_copied_to_the_end_in_the_order_chosen(stack) -> None:
    """Hai câu chọn theo thứ tự ngược: vào đề là câu 3, 4 theo đúng thứ tự ấy, đủ phương án."""
    http, maker, _ = stack
    draft = await _draft(maker, 2)
    first, second = await _banked(maker, ["Đạo hàm của x²?", "Đạo hàm của 3x?"])

    answer = await _take(http, draft, [second, first])

    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert [(one["order"], one["stem"], one["source"]) for one in body["questions"]] == [
        (1, "Câu 1?", "kriky"),
        (2, "Câu 2?", "kriky"),
        (3, "Đạo hàm của 3x?", "bank"),
        (4, "Đạo hàm của x²?", "bank"),
    ]
    taken = body["questions"][2]
    assert [(one["label"], one["text"], one["error_label"]) for one in taken["options"]] == [
        ("A", "2x", None),
        ("B", "x", "quên hệ số"),
        ("C", "x²", "không lấy"),
    ]
    assert [one["title"] for one in taken["methods"]] == ["Cách 1", "Cách 2"]
    # Xoá câu ấy khỏi đề không xoá ngân hàng: hộp xoá câu phải nói đúng như vậy.
    assert taken["in_bank"] is True
    async with maker() as session:
        slots = list(
            await session.execute(
                select(DraftItem.ordinal, DraftItem.status, DraftItem.job_id)
                .where(DraftItem.assessment_id == draft)
                .order_by(DraftItem.ordinal)
            )
        )
        brief = await session.get(DraftBrief, draft)
        pointers = set(
            await session.scalars(
                select(Question.bank_question_id).where(
                    Question.assessment_id == draft, Question.source == "bank"
                )
            )
        )
    assert [tuple(one) for one in slots[2:]] == [
        (3, "ready", f"bank:{second}"),
        (4, "ready", f"bank:{first}"),
    ]
    assert brief.question_count == 4
    assert pointers == {first, second}


@pytest.mark.asyncio
async def test_an_empty_draft_gets_questions_from_the_bank(stack) -> None:
    """Đề trống lấy một câu: câu 1, và đề sang *có câu* -- duyệt được ngay."""
    http, maker, _ = stack
    draft = await _draft(maker, 0)
    (only,) = await _banked(maker, ["Đạo hàm của x²?"])

    answer = await _take(http, draft, [only])

    assert answer.status_code == 200, answer.text
    assert [one["order"] for one in answer.json()["questions"]] == [1]
    assert answer.json()["state"] == "has_questions"
    assert answer.json()["erasable"] is False


@pytest.mark.asyncio
async def test_drafting_more_afterwards_continues_the_numbering(stack) -> None:
    """Kriky soạn thêm sau câu ngân hàng: câu mới mang số kế tiếp, không ghi đè số của nó."""
    http, maker, queue = stack
    draft = await _draft(maker, 1)
    (only,) = await _banked(maker, ["Đạo hàm của x²?"])
    assert (await _take(http, draft, [only])).status_code == 200

    async with maker() as session:
        queued = await drafting.fire(session, queue, get_settings(), draft, 1)
    assert queued == 1
    queue.finish("job-0", "Câu Kriky mới?")
    detail = await http.get(f"/api/teacher/assessments/{draft}", headers=TEACHER)

    assert [(one["order"], one["source"]) for one in detail.json()["questions"]] == [
        (1, "kriky"),
        (2, "bank"),
        (3, "kriky"),
    ]


# ------------------------------------------------------------------ câu đã có


@pytest.mark.asyncio
async def test_a_question_already_in_the_paper_is_skipped_and_locked(stack) -> None:
    """Lấy một câu hai lần: lần hai không thêm gì; hộp chọn ghi câu ấy *đã có trong đề này*."""
    http, maker, _ = stack
    draft = await _draft(maker, 1)
    first, second = await _banked(maker, ["Đạo hàm của x²?", "Đạo hàm của 3x?"])
    assert (await _take(http, draft, [first])).status_code == 200

    again = await _take(http, draft, [first, second])

    assert again.status_code == 200, again.text
    assert [one["stem"] for one in again.json()["questions"]] == [
        "Câu 1?",
        "Đạo hàm của x²?",
        "Đạo hàm của 3x?",
    ]
    picker = await http.get(f"/api/teacher/assessments/{draft}/bank-picker", headers=TEACHER)
    assert picker.status_code == 200
    flags = {one["bank_id"]: one["in_this_paper"] for one in picker.json()["questions"]}
    assert (flags[first], flags[second]) == (True, True)
    # Câu seed sẵn trong ngân hàng của GV-001 không dính gì tới đề này.
    assert not any(flag for bank_id, flag in flags.items() if bank_id not in (first, second))


@pytest.mark.asyncio
async def test_a_question_approved_from_this_paper_counts_as_already_in_it(stack) -> None:
    """Duyệt, bỏ duyệt: bản ngân hàng của chính câu trong đề không vào đề lần nữa."""
    http, maker, _ = stack
    draft = await _draft(maker, 2)
    url = f"/api/teacher/assessments/{draft}"
    assert (await http.post(f"{url}/approve", headers=TEACHER)).status_code == 200
    assert (await http.post(f"{url}/unapprove", headers=TEACHER)).status_code == 200
    (other,) = await _banked(maker, ["Đạo hàm của 3x?"])

    every = (await http.get(f"{url}/bank-picker", headers=TEACHER)).json()["questions"]
    picker = [
        one for one in every if one["from_title"] in ("Đề nháp đạo hàm", "Đề tuần 3 — Đạo hàm")
    ]

    assert {one["stem"]: one["in_this_paper"] for one in picker} == {
        "Câu 1?": True,
        "Câu 2?": True,
        "Đạo hàm của 3x?": False,
    }
    assert {one["from_title"] for one in picker} == {"Đề nháp đạo hàm", "Đề tuần 3 — Đạo hàm"}
    born_here = [one["bank_id"] for one in picker if one["in_this_paper"]]
    answer = await _take(http, draft, [*born_here, other])
    assert [one["stem"] for one in answer.json()["questions"]] == [
        "Câu 1?",
        "Câu 2?",
        "Đạo hàm của 3x?",
    ]


# ------------------------------------------------------------------ duyệt


@pytest.mark.asyncio
async def test_approving_does_not_file_a_bank_question_twice(stack) -> None:
    """Đề có một câu Kriky và một câu ngân hàng: duyệt chỉ thêm bản của câu Kriky."""
    http, maker, _ = stack
    draft = await _draft(maker, 1)
    (only,) = await _banked(maker, ["Đạo hàm của x²?"])
    assert (await _take(http, draft, [only])).status_code == 200

    approved = await http.post(f"/api/teacher/assessments/{draft}/approve", headers=TEACHER)

    assert approved.status_code == 200, approved.text
    async with maker() as session:
        stems = list(
            await session.scalars(
                select(BankQuestion.stem)
                .join(Assessment, Assessment.id == BankQuestion.assessment_id)
                .where(Assessment.title.in_(["Đề nháp đạo hàm", "Đề tuần 3 — Đạo hàm"]))
                .order_by(BankQuestion.stem)
            )
        )
    assert stems == ["Câu 1?", "Đạo hàm của x²?"]


# ------------------------------------------------------------------ cửa


@pytest.mark.asyncio
async def test_another_teachers_paper_and_bank_read_as_absent(stack) -> None:
    """Đề của người khác 404; câu ngân hàng của người khác cũng 404, đề không đổi."""
    http, maker, _ = stack
    draft = await _draft(maker, 1)
    (mine,) = await _banked(maker, ["Đạo hàm của x²?"])
    (theirs,) = await _banked(maker, ["Câu của thầy B?"], teacher_code="GV-002")

    assert (await _take(http, draft, [mine], headers=STRANGER)).status_code == 404
    picked = await http.get(f"/api/teacher/assessments/{draft}/bank-picker", headers=STRANGER)
    assert picked.status_code == 404
    refused = await _take(http, draft, [mine, theirs])
    assert refused.status_code == 404
    async with maker() as session:
        count = await session.scalar(
            select(func.count()).select_from(Question).where(Question.assessment_id == draft)
        )
    assert count == 1


@pytest.mark.asyncio
async def test_an_approved_paper_refuses_a_bank_pick(stack) -> None:
    http, maker, _ = stack
    draft = await _draft(maker, 1)
    (only,) = await _banked(maker, ["Đạo hàm của x²?"])
    assert (
        await http.post(f"/api/teacher/assessments/{draft}/approve", headers=TEACHER)
    ).status_code == 200

    assert (await _take(http, draft, [only])).status_code == 409


@pytest.mark.asyncio
async def test_a_paper_still_being_drafted_refuses_a_bank_pick(stack) -> None:
    """Còn ô đang soạn: từ chối, vì câu ngân hàng đứng sau ô cao nhất và ô ấy chưa xong."""
    http, maker, queue = stack
    draft = await _draft(maker, 1)
    (only,) = await _banked(maker, ["Đạo hàm của x²?"])
    async with maker() as session:
        assert await drafting.fire(session, queue, get_settings(), draft, 1) == 1

    refused = await _take(http, draft, [only])

    assert refused.status_code == 409
    assert "đang soạn" in refused.json()["detail"]


@pytest.mark.asyncio
async def test_a_paper_over_the_ceiling_refuses_a_bank_pick(stack, monkeypatch) -> None:
    """Trần một đề tính cả câu đã có: 1 câu + 2 câu ngân hàng vượt trần 2 thì 409, đề không đổi."""
    http, maker, _ = stack
    monkeypatch.setattr(drafting, "_MOST_QUESTIONS", 2)
    draft = await _draft(maker, 1)
    picked = await _banked(maker, ["Đạo hàm của x²?", "Đạo hàm của 3x?"])

    refused = await _take(http, draft, picked)

    assert refused.status_code == 409
    assert "nhiều nhất 2 câu" in refused.json()["detail"]


# ------------------------------------------------------------------ sau khi lấy vào


@pytest.mark.asyncio
async def test_an_empty_draft_with_failed_slots_starts_at_question_one(stack) -> None:
    """Đề trống còn ba ô hỏng: dọn như khi dùng lại đề trống, câu ngân hàng là *Câu 1*."""
    http, maker, _ = stack
    draft = await _draft(maker, 0)
    async with maker() as session:
        for ordinal in (1, 2, 3):
            session.add(
                DraftItem(
                    assessment_id=draft,
                    ordinal=ordinal,
                    job_id=f"dead-{ordinal}",
                    status="failed",
                    brief_version=1,
                    attempts=3,
                    last_fault="model hỏng",
                    created_at=datetime.now(UTC),
                )
            )
        await session.commit()
    (only,) = await _banked(maker, ["Đạo hàm của x²?"])

    answer = await _take(http, draft, [only])

    assert answer.status_code == 200, answer.text
    assert [one["order"] for one in answer.json()["questions"]] == [1]
    assert answer.json()["failed_slots"] == []


@pytest.mark.asyncio
async def test_deleting_a_bank_question_keeps_the_bank_row_and_reopens_it(stack) -> None:
    """Xoá câu ngân hàng khỏi đề: dòng ngân hàng ở lại, brief bớt một, hộp chọn mở lại câu ấy."""
    http, maker, _ = stack
    draft = await _draft(maker, 1)
    (only,) = await _banked(maker, ["Đạo hàm của x²?"])
    taken = (await _take(http, draft, [only])).json()["questions"][1]

    gone = await http.delete(
        f"/api/teacher/assessments/{draft}/questions/{taken['question_id']}", headers=TEACHER
    )

    assert gone.status_code == 204, gone.text
    async with maker() as session:
        row = await session.get(BankQuestion, only)
        brief = await session.get(DraftBrief, draft)
    assert row is not None and row.stem == "Đạo hàm của x²?"
    assert brief.question_count == 1
    picker = await http.get(f"/api/teacher/assessments/{draft}/bank-picker", headers=TEACHER)
    flags = {one["bank_id"]: one["in_this_paper"] for one in picker.json()["questions"]}
    assert flags[only] is False


@pytest.mark.asyncio
async def test_the_picker_shows_only_the_owners_bank(stack) -> None:
    """Ngân hàng của thầy B không lọt vào hộp chọn của cô A (ADR-22)."""
    http, maker, _ = stack
    draft = await _draft(maker, 1)
    (mine,) = await _banked(maker, ["Đạo hàm của x²?"])
    (theirs,) = await _banked(maker, ["Câu của thầy B?"], teacher_code="GV-002")

    picker = await http.get(f"/api/teacher/assessments/{draft}/bank-picker", headers=TEACHER)

    ids = {one["bank_id"] for one in picker.json()["questions"]}
    assert mine in ids and theirs not in ids


@pytest.mark.asyncio
async def test_editing_a_bank_question_keeps_its_source(stack) -> None:
    """Sửa câu ngân hàng trong đề: thẻ vẫn ghi *Từ ngân hàng*, và hộp xoá vẫn biết nó có bản."""
    http, maker, _ = stack
    draft = await _draft(maker, 1)
    (only,) = await _banked(maker, ["Đạo hàm của x²?"])
    taken = (await _take(http, draft, [only])).json()["questions"][1]

    edited = await http.patch(
        f"/api/teacher/assessments/{draft}/questions/{taken['question_id']}",
        json={
            "stem": "Đạo hàm của x² bằng gì?",
            "learning_objective": taken["learning_objective"],
            "options": taken["options"],
            "methods": taken["methods"],
        },
        headers=TEACHER,
    )

    assert edited.status_code == 200, edited.text
    assert (edited.json()["source"], edited.json()["in_bank"]) == ("bank", True)
    async with maker() as session:
        row = await session.get(BankQuestion, only)
    # Sửa trong đề không đổi bản ngân hàng.
    assert row.stem == "Đạo hàm của x²?"
