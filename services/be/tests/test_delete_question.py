"""Xoá một câu khỏi đề còn mở, và bản trong ngân hàng câu hỏi thì ở lại (ADR-28).

Ba luật được canh ở đây, mỗi luật một nhóm test:

- **Xoá trong đề không xoá ngân hàng.** Dòng ngân hàng của câu ở lại, chỉ thôi trỏ về câu.
- **Xoá không đổi trạng thái của đề** (hậu ký ADR-01): câu cuối cùng không xoá được.
- **Số câu dồn lên**, cả ở `Question` lẫn ở `DraftItem`: lần soạn thêm sau không mở ra sau một lỗ.

SQLite của các test khác không bật khoá ngoại, nên một lần xoá sai thứ tự -- câu trước phương án,
hay câu còn dòng ngân hàng trỏ vào -- vẫn xanh ở đó và chỉ đỏ trên Postgres. Ở đây khoá ngoại
**bật**, để thứ tự ấy là thứ test thấy được.
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
    Attempt,
    BankQuestion,
    DraftBrief,
    DraftItem,
    Method,
    Question,
    QuestionOutcome,
    Student,
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


async def _draft(maker, questions: int, teacher_code: str = "GV-001") -> str:
    """Một đề nháp có `questions` câu đã soạn xong, mỗi câu một ô `DraftItem` đã `ready`."""
    async with maker() as session:
        owner = await session.scalar(select(Teacher).where(Teacher.teacher_code == teacher_code))
        draft = Assessment(
            teacher_id=owner.id,
            title="Đề nháp đạo hàm",
            subject="Toán",
            grade="12",
            state=AssessmentState.HAS_QUESTIONS,
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
            session.add(Method(question_id=question.id, order_index=1, title="Cách 1", body="."))
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


async def _question_at(maker, draft: str, order: int) -> str:
    async with maker() as session:
        found = await session.scalar(
            select(Question.id).where(
                Question.assessment_id == draft, Question.order_index == order
            )
        )
        assert found is not None
        return found


async def _stems(maker, draft: str) -> list[tuple[int, str]]:
    async with maker() as session:
        rows = await session.execute(
            select(Question.order_index, Question.stem)
            .where(Question.assessment_id == draft)
            .order_by(Question.order_index)
        )
        return [(order, stem) for order, stem in rows]


async def _delete(http, draft: str, question: str, headers=TEACHER):
    return await http.delete(
        f"/api/teacher/assessments/{draft}/questions/{question}", headers=headers
    )


# ------------------------------------------------------------------ dồn số


@pytest.mark.asyncio
async def test_deleting_a_question_closes_the_gap_in_both_ledgers(stack) -> None:
    """Đề mười câu xoá câu 1: còn 1..9 -- trên câu, trên ô soạn, và trên brief.

    Mười câu chứ không bốn: chín dòng phải dồn, nên một lần gom flush (SQLAlchemy xếp các câu
    `UPDATE` theo khoá chính UUID, không theo vòng lặp) gần như chắc chắn đụng ràng buộc duy
    nhất. Với hai dòng thì bắt được hay không là do may.
    """
    http, maker, _ = stack
    draft = await _draft(maker, 10)
    gone = await _question_at(maker, draft, 1)

    answer = await _delete(http, draft, gone)

    assert answer.status_code == 204, answer.text
    assert await _stems(maker, draft) == [(n, f"Câu {n + 1}?") for n in range(1, 10)]
    async with maker() as session:
        slots = list(
            await session.execute(
                select(DraftItem.ordinal, DraftItem.job_id)
                .where(DraftItem.assessment_id == draft)
                .order_by(DraftItem.ordinal)
            )
        )
        brief = await session.get(DraftBrief, draft)
        options = await session.scalar(
            select(func.count()).select_from(AnswerOption).where(AnswerOption.question_id == gone)
        )
        methods = await session.scalar(
            select(func.count()).select_from(Method).where(Method.question_id == gone)
        )
    # Ô của câu vừa xoá đi cùng nó; các ô sau dồn lên **cùng** câu của chúng.
    assert [tuple(one) for one in slots] == [(n, f"seeded-{n + 1}") for n in range(1, 10)]
    assert brief.question_count == 9
    # Phương án và lời giải của câu đã xoá không ở lại làm dòng mồ côi.
    assert options == methods == 0


@pytest.mark.asyncio
async def test_a_finished_job_nobody_collected_is_harvested_before_the_delete(stack) -> None:
    """Một ô `pending` mà job đã xong không được đếm là *đang soạn*: xoá thu hoạch trước.

    Thiếu lần thu ấy thì giáo viên bị từ chối vì một câu đã viết xong; và câu ấy, khi về, phải
    dồn số cùng mọi câu khác.
    """
    http, maker, queue = stack
    draft = await _draft(maker, 3)
    async with maker() as session:
        brief = await session.get(DraftBrief, draft)
        brief.question_count = 4
        session.add(
            DraftItem(
                assessment_id=draft,
                ordinal=4,
                job_id="done-4",
                status="pending",
                brief_version=1,
                attempts=1,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
    queue.finish("done-4", "Câu vừa soạn xong?")

    answer = await _delete(http, draft, await _question_at(maker, draft, 1))

    assert answer.status_code == 204, answer.text
    assert await _stems(maker, draft) == [(1, "Câu 2?"), (2, "Câu 3?"), (3, "Câu vừa soạn xong?")]
    async with maker() as session:
        brief = await session.get(DraftBrief, draft)
    assert brief.question_count == 3


@pytest.mark.asyncio
async def test_failed_and_retry_slots_shift_with_the_rest(stack) -> None:
    """Ô `failed` (lỗ có từ trước) và ô `retry` dồn cùng các câu; soạn thêm bắn lại đúng chỗ.

    Câu 1, 2, 4; ô 3 `failed`; ô 5 `retry`. Xoá câu 1 thì còn câu 1, 3 -- lỗ của ô `failed`
    dịch theo chứ không bị lấp nhầm -- và lần soạn thêm bắn lại ô `retry` ở vị trí 4 cùng một
    ô mới ở 5.
    """
    http, maker, queue = stack
    draft = await _draft(maker, 4)
    async with maker() as session:
        third = await session.scalar(
            select(Question).where(Question.assessment_id == draft, Question.order_index == 3)
        )
        for row in await session.scalars(
            select(AnswerOption).where(AnswerOption.question_id == third.id)
        ):
            await session.delete(row)
        for row in await session.scalars(select(Method).where(Method.question_id == third.id)):
            await session.delete(row)
        await session.flush()
        await session.delete(third)
        slot3 = await session.scalar(
            select(DraftItem).where(DraftItem.assessment_id == draft, DraftItem.ordinal == 3)
        )
        slot3.status = "failed"
        session.add(
            DraftItem(
                assessment_id=draft,
                ordinal=5,
                job_id="lost-5",
                status="retry",
                brief_version=1,
                attempts=1,
                created_at=datetime.now(UTC),
            )
        )
        brief = await session.get(DraftBrief, draft)
        brief.question_count = 5
        await session.commit()

    assert (await _delete(http, draft, await _question_at(maker, draft, 1))).status_code == 204

    assert await _stems(maker, draft) == [(1, "Câu 2?"), (3, "Câu 4?")]
    async with maker() as session:
        slots = [
            tuple(one)
            for one in await session.execute(
                select(DraftItem.ordinal, DraftItem.status)
                .where(DraftItem.assessment_id == draft)
                .order_by(DraftItem.ordinal)
            )
        ]
        brief = await session.get(DraftBrief, draft)
    assert slots == [(1, "ready"), (2, "failed"), (3, "ready"), (4, "retry")]
    assert brief.question_count == 4

    async with maker() as session:
        assert await drafting.fire(session, queue, get_settings(), draft, 1) == 2
    queue.finish("job-0", "Câu bắn lại?")
    queue.finish("job-1", "Câu mới?")
    detail = await http.get(f"/api/teacher/assessments/{draft}", headers=TEACHER)
    assert [(one["order"], one["stem"]) for one in detail.json()["questions"]] == [
        (1, "Câu 2?"),
        (3, "Câu 4?"),
        (4, "Câu bắn lại?"),
        (5, "Câu mới?"),
    ]


@pytest.mark.asyncio
async def test_drafting_more_after_a_delete_leaves_no_gap(stack) -> None:
    """Soạn thêm một câu sau khi xoá: câu mới mang số kế tiếp, không nhảy qua một lỗ."""
    http, maker, queue = stack
    draft = await _draft(maker, 3)
    assert (await _delete(http, draft, await _question_at(maker, draft, 1))).status_code == 204

    async with maker() as session:
        queued = await drafting.fire(session, queue, get_settings(), draft, 1)
    assert queued == 1
    queue.finish("job-0", "Câu mới?")
    detail = await http.get(f"/api/teacher/assessments/{draft}", headers=TEACHER)

    assert detail.status_code == 200
    assert [one["order"] for one in detail.json()["questions"]] == [1, 2, 3]
    assert detail.json()["questions"][-1]["stem"] == "Câu mới?"


# ------------------------------------------------------------------ ngân hàng


async def _bank_of(maker, draft: str) -> list[BankQuestion]:
    async with maker() as session:
        return list(
            await session.scalars(
                select(BankQuestion)
                .where(BankQuestion.assessment_id == draft)
                .order_by(BankQuestion.stem)
            )
        )


@pytest.mark.asyncio
async def test_a_deleted_question_stays_in_the_bank(stack) -> None:
    """Duyệt, bỏ duyệt, xoá câu 1: dòng ngân hàng của nó ở lại, chỉ thôi trỏ về câu.

    Và lần duyệt lại không đụng dòng ấy: không gỡ nó (xoá trong đề không xoá ngân hàng), không
    sinh dòng mới cho các câu còn lại (chúng đã có bản).
    """
    http, maker, _ = stack
    draft = await _draft(maker, 3)
    url = f"/api/teacher/assessments/{draft}"
    assert (await http.post(f"{url}/approve", headers=TEACHER)).status_code == 200
    assert (await http.post(f"{url}/unapprove", headers=TEACHER)).status_code == 200
    gone = await _question_at(maker, draft, 1)

    assert (await _delete(http, draft, gone)).status_code == 204

    after = await _bank_of(maker, draft)
    assert [row.stem for row in after] == ["Câu 1?", "Câu 2?", "Câu 3?"]
    assert after[0].question_id is None
    assert all(row.question_id is not None for row in after[1:])
    # Câu còn lại vẫn đọc ra `in_bank` -- và câu số 1 bây giờ là câu từng là câu 2.
    detail = (await http.get(url, headers=TEACHER)).json()["questions"]
    assert [(one["order"], one["in_bank"]) for one in detail] == [(1, True), (2, True)]

    assert (await http.post(f"{url}/approve", headers=TEACHER)).status_code == 200
    again = await _bank_of(maker, draft)
    assert [(row.id, row.stem) for row in again] == [(row.id, row.stem) for row in after]
    assert again[0].question_id is None


@pytest.mark.asyncio
async def test_in_bank_says_whether_the_question_was_ever_approved(stack) -> None:
    """`in_bank` là thứ hộp xoá câu đọc để chọn lời dẫn -- nên nó phải nói đúng ở cả hai phía."""
    http, maker, _ = stack
    draft = await _draft(maker, 2)
    url = f"/api/teacher/assessments/{draft}"

    before = (await http.get(url, headers=TEACHER)).json()["questions"]
    assert [one["in_bank"] for one in before] == [False, False]

    assert (await http.post(f"{url}/approve", headers=TEACHER)).status_code == 200
    assert (await http.post(f"{url}/unapprove", headers=TEACHER)).status_code == 200
    after = (await http.get(url, headers=TEACHER)).json()["questions"]
    assert [one["in_bank"] for one in after] == [True, True]

    # Route sửa trả về cùng hình dạng, nên cũng phải nói đúng: sửa không đưa câu ra khỏi kho.
    edited = await http.patch(
        f"{url}/questions/{after[0]['question_id']}",
        json={
            "stem": "Câu 1 đã sửa?",
            "learning_objective": "đạo hàm",
            "options": [
                {"label": "A", "text": "đúng", "is_correct": True, "error_label": None},
                {"label": "B", "text": "sai", "is_correct": False, "error_label": "lỗi B"},
            ],
            "methods": [{"title": "Cách 1", "body": "."}, {"title": "Cách 2", "body": "."}],
        },
        headers=TEACHER,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["in_bank"] is True


# ------------------------------------------------------------------ lời từ chối


@pytest.mark.asyncio
async def test_an_approved_paper_refuses_a_delete(stack) -> None:
    """Duyệt khoá nội dung (ADR-01): xoá cũng là sửa nội dung."""
    http, maker, _ = stack
    draft = await _draft(maker, 2)
    assert (
        await http.post(f"/api/teacher/assessments/{draft}/approve", headers=TEACHER)
    ).status_code == 200

    answer = await _delete(http, draft, await _question_at(maker, draft, 1))

    assert answer.status_code == 409
    assert "bỏ duyệt" in answer.json()["detail"]
    assert len(await _stems(maker, draft)) == 2


@pytest.mark.asyncio
async def test_a_paper_still_being_drafted_refuses_a_delete(stack) -> None:
    """Dồn số dưới chân một job đang chạy là để nó ghi câu vào nhầm ô."""
    http, maker, _ = stack
    draft = await _draft(maker, 2)
    async with maker() as session:
        brief = await session.get(DraftBrief, draft)
        brief.question_count = 3
        session.add(
            DraftItem(
                assessment_id=draft,
                ordinal=3,
                job_id="still-running",
                status="pending",
                brief_version=1,
                attempts=1,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

    answer = await _delete(http, draft, await _question_at(maker, draft, 1))

    assert answer.status_code == 409
    assert "đang soạn" in answer.json()["detail"]
    assert len(await _stems(maker, draft)) == 2


@pytest.mark.asyncio
async def test_the_last_question_cannot_be_deleted(stack) -> None:
    """Xoá không đổi trạng thái của đề: một đề *có câu hỏi* không về *trống* bằng đường này."""
    http, maker, _ = stack
    draft = await _draft(maker, 1)

    answer = await _delete(http, draft, await _question_at(maker, draft, 1))

    assert answer.status_code == 409
    assert "câu cuối" in answer.json()["detail"]
    async with maker() as session:
        paper = await session.get(Assessment, draft)
    assert AssessmentState(paper.state) is AssessmentState.HAS_QUESTIONS


@pytest.mark.asyncio
async def test_a_paper_someone_already_sat_refuses_a_delete(stack) -> None:
    """Phòng thủ: một bài nộp **trắng** vẫn có dòng trỏ khoá ngoại về câu.

    Nộp pha 1 ghi một `QuestionOutcome` cho mọi câu, kể cả câu bỏ trắng -- không có `Answer`
    nào. Chặn theo lượt trả lời thì lọt, và Postgres trả một 500 không có chữ tiếng Việt nào.
    """
    http, maker, _ = stack
    draft = await _draft(maker, 2)
    question = await _question_at(maker, draft, 1)
    async with maker() as session:
        student = await session.scalar(select(Student))
        attempt = Attempt(
            assessment_id=draft,
            student_id=student.id,
            class_id=student.class_id,
            started_at=datetime.now(UTC),
            ends_at=datetime.now(UTC),
            submitted_at=datetime.now(UTC),
        )
        session.add(attempt)
        await session.flush()
        session.add(QuestionOutcome(attempt_id=attempt.id, question_id=question, reason="blank"))
        await session.commit()

    answer = await _delete(http, draft, question)

    assert answer.status_code == 409
    assert "lượt làm bài" in answer.json()["detail"]
    assert len(await _stems(maker, draft)) == 2


@pytest.mark.asyncio
async def test_another_teachers_question_reads_as_absent(stack) -> None:
    """ADR-22: đề của người khác đọc ra như không tồn tại, kể cả với lệnh xoá."""
    http, maker, _ = stack
    draft = await _draft(maker, 2)

    answer = await _delete(http, draft, await _question_at(maker, draft, 1), headers=STRANGER)

    assert answer.status_code == 404
    assert len(await _stems(maker, draft)) == 2


@pytest.mark.asyncio
async def test_a_question_from_another_paper_reads_as_absent(stack) -> None:
    """Id câu của một đề khác, ghép với id đề này, không xoá được gì."""
    http, maker, _ = stack
    mine = await _draft(maker, 2)
    other = await _draft(maker, 2)

    answer = await _delete(http, mine, await _question_at(maker, other, 1))

    assert answer.status_code == 404
    assert len(await _stems(maker, other)) == 2
