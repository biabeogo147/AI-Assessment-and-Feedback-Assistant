"""Duyệt và bỏ duyệt, qua đúng đường HTTP mà giáo viên sẽ bấm.

Hai luật của ADR-01 được thi hành ở đây, và cả hai đều là loại luật mà không có gì đỏ khi
nó bị bỏ: **duyệt thì khoá nội dung**, và **duyệt thì bỏ được**. Trước đợt này cả hai chỉ
sống trong một bảng cạnh mà chưa đường HTTP nào đi qua.

Thêm một bất biến mà plan gọi là *`state` ↔ số câu hỏi*: không duyệt được một đề trống, và
không duyệt được một đề còn câu đang soạn. Cái thứ hai là cái đáng giá — duyệt trong lúc
job còn chạy là duyệt những câu hỏi giáo viên chưa từng thấy, và mấy câu đó sẽ lặng lẽ rơi
vào một đề mà nội dung đã khoá.

Các test ở đây gọi qua HTTP chứ không gọi hàm, vì chỗ cần kiểm chính là chỗ hai thứ gặp
nhau: phân quyền của ADR-22, và bảng cạnh của ADR-01.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import drafting
from be.config import get_settings
from be.db import bind_sessions, prepare_schema
from be.models import (
    AnswerOption,
    Assessment,
    AssessmentState,
    DraftBrief,
    DraftItem,
    Method,
    Question,
    Teacher,
    TeacherTurn,
)
from be.seed import seed_if_empty
from be.teacher_chat import router as chat_router
from be.teacher_routes import router as assessment_router
from contracts import DraftQuestionCompleted, GeneratedOption, GeneratedQuestion, SolutionMethod

TEACHER = {"X-Actor": "teacher:GV-001"}
STRANGER = {"X-Actor": "teacher:GV-002"}


class FakeQueue:
    """Ghi lại những gì được đẩy vào queue, và trả lời cho các job mà test cho là đã xong."""

    def __init__(self) -> None:
        self.jobs: list[tuple[str, dict]] = []
        self.results: dict[str, tuple[str, object]] = {}

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str):
        job_id = f"job-{len(self.jobs)}"
        self.jobs.append((name, payload))
        return type("Queued", (), {"job_id": job_id})()

    def finish(self, job_id: str, question: GeneratedQuestion) -> None:
        """Nói rằng job đó đã xong, với câu hỏi này."""
        self.results[job_id] = (
            "ready",
            DraftQuestionCompleted(request_id="r", question=question).model_dump(mode="json"),
        )


def _good(stem: str) -> GeneratedQuestion:
    """Một câu hỏi thoả ADR-18: đúng một đáp án, distractor có nhãn, hai cách giải."""
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
        learning_objective="đạo hàm",
    )


@pytest_asyncio.fixture
async def stack(monkeypatch):
    """Một app có hai giáo viên, để "không phải của tôi" là một ca thật sự tồn tại."""
    engine = create_async_engine("sqlite+aiosqlite://")
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
    app.include_router(chat_router)
    app.include_router(assessment_router)
    app.state.queue_pool = queue

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker, queue

    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _teacher_id(maker, code: str) -> str:
    async with maker() as session:
        found = await session.scalar(select(Teacher).where(Teacher.teacher_code == code))
        assert found is not None
        return found.id


async def _draft(
    maker, teacher_code: str = "GV-001", *, questions: int = 0, asked: int | None = None
) -> str:
    """Dựng một đề nháp kèm brief, và tuỳ chọn một số câu hỏi đã viết xong.

    `asked` là số câu brief yêu cầu, mặc định bằng số câu đã viết. Hai con số này tách
    nhau ra vì `harvest` **xoá** mọi vị trí vượt quá `question_count` của brief hiện tại,
    nên một test muốn có một vị trí đang chạy thật thì brief phải còn chỗ cho nó.
    """
    teacher_id = await _teacher_id(maker, teacher_code)
    async with maker() as session:
        draft = Assessment(
            teacher_id=teacher_id,
            title="Đề nháp đạo hàm",
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
                question_count=max(asked if asked is not None else questions, 1),
                version=1,
                created_at=datetime.now(UTC),
            )
        )
        for index in range(questions):
            question = Question(
                assessment_id=draft.id,
                stem=f"Câu {index + 1}?",
                order_index=index + 1,
                learning_objective="đạo hàm",
            )
            session.add(question)
            await session.flush()
            session.add(
                AnswerOption(question_id=question.id, label="A", text="đúng", is_correct=True)
            )
            session.add(Method(question_id=question.id, order_index=1, title="Cách 1", body="..."))
        if questions:
            draft.state = AssessmentState.HAS_QUESTIONS
        await session.commit()
        return draft.id


async def _state(maker, assessment_id: str) -> AssessmentState:
    async with maker() as session:
        found = await session.get(Assessment, assessment_id)
        assert found is not None
        return AssessmentState(found.state)


@pytest.mark.asyncio
async def test_an_empty_assessment_cannot_be_approved(stack) -> None:
    """Nửa thứ nhất của bất biến `state` ↔ số câu hỏi.

    Một đề không câu nào mà duyệt được thì phát hành được, và học sinh mở ra thấy một bài
    kiểm tra trống. Không constraint nào của database chạm tới chuyện này: `state` và số
    dòng `questions` là hai thứ, và không gì buộc chúng phải khớp nhau.
    """
    client, maker, _ = stack
    draft = await _draft(maker)

    answer = await client.post(f"/api/teacher/assessments/{draft}/approve", headers=TEACHER)

    assert answer.status_code == 409
    assert "chưa có câu hỏi" in answer.json()["detail"]
    assert await _state(maker, draft) is AssessmentState.EMPTY


@pytest.mark.asyncio
async def test_an_assessment_still_being_drafted_cannot_be_approved(stack) -> None:
    """Nửa thứ hai, và là nửa đáng giá hơn.

    Duyệt trong lúc job còn chạy là duyệt những câu hỏi giáo viên **chưa từng thấy** —
    chúng sẽ về sau đó và rơi vào một đề mà nội dung đã bị ADR-01 khoá. Không có gì đỏ
    nếu không chặn ở đây: `harvest` vẫn ghi chúng vào, lặng lẽ.
    """
    client, maker, _ = stack
    draft = await _draft(maker, questions=1, asked=2)
    async with maker() as session:
        session.add(
            DraftItem(
                assessment_id=draft,
                ordinal=2,
                job_id="job-99",
                status="pending",
                brief_version=1,
                attempts=1,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

    answer = await client.post(f"/api/teacher/assessments/{draft}/approve", headers=TEACHER)

    assert answer.status_code == 409
    assert "đang soạn" in answer.json()["detail"]
    assert await _state(maker, draft) is AssessmentState.HAS_QUESTIONS


@pytest.mark.asyncio
async def test_approving_harvests_the_jobs_that_already_finished(stack) -> None:
    """Thu hoạch trước, rồi mới đếm — nếu không thì không ai duyệt được bao giờ.

    BE không có worker chạy nền, nên một `DraftItem` chỉ rời `pending` lúc `harvest` chạy.
    Một endpoint đếm trước khi thu sẽ từ chối một giáo viên có đủ câu đã viết xong, và từ
    chối **mãi mãi**: con số nó đọc chỉ đổi khi có người gọi một endpoint khác. Đây là
    cùng cái lỗi mà review Pha 3 đã bắt ở `start_drafting`.
    """
    client, maker, queue = stack
    draft = await _draft(maker)
    async with maker() as session:
        session.add(
            DraftItem(
                assessment_id=draft,
                ordinal=1,
                job_id="job-0",
                status="pending",
                brief_version=1,
                attempts=1,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
    queue.finish("job-0", _good("Đạo hàm của y = x² là gì?"))

    answer = await client.post(f"/api/teacher/assessments/{draft}/approve", headers=TEACHER)

    assert answer.status_code == 200
    body = answer.json()
    assert body["state"] == AssessmentState.APPROVED
    assert body["question_count"] == 1
    # Một phép đo, không phải một lời khai: cả ba field đọc lại từ database sau commit.
    # Bản đầu ghi cứng `still_drafting=0`, nên dòng này so hai hằng số với nhau.
    assert body["still_drafting"] == 0
    assert await _state(maker, draft) is AssessmentState.APPROVED
    async with maker() as session:
        stems = list(
            await session.scalars(select(Question.stem).where(Question.assessment_id == draft))
        )
    assert stems == ["Đạo hàm của y = x² là gì?"]


@pytest.mark.asyncio
async def test_unapproving_opens_the_content_again_and_leaves_evidence(stack) -> None:
    """ADR-01 đòi cạnh lùi, và đòi luôn bằng chứng cho nó.

    Bỏ duyệt là **thao tác duy nhất hạ một state xuống**, nên nó là thao tác đáng ghi lại
    nhất: không có dòng nào trong `teacher_turns` thì "ai mở lại đề này, lúc nào" là câu
    không trả lời được, kể cả khi state hiện tại nói đúng.
    """
    client, maker, _ = stack
    draft = await _draft(maker, questions=2)
    assert (
        await client.post(f"/api/teacher/assessments/{draft}/approve", headers=TEACHER)
    ).status_code == 200

    answer = await client.post(f"/api/teacher/assessments/{draft}/unapprove", headers=TEACHER)

    assert answer.status_code == 200
    assert answer.json()["state"] == AssessmentState.HAS_QUESTIONS
    assert await _state(maker, draft) is AssessmentState.HAS_QUESTIONS

    async with maker() as session:
        turns = list(await session.scalars(select(TeacherTurn).order_by(TeacherTurn.sequence)))
    names = [turn.tool_name for turn in turns]
    # Có dấu chấm, có chủ ý: hai bước này đi vào **cùng** cuộc hội thoại mà model đọc, và
    # một `tool_result` mang tên giống một tool sẽ dạy nó rằng cái tên đó gọi được —
    # trong khi `catalog_for` không bao giờ cấp nó. Một cái tên không phải identifier hợp
    # lệ thì không mời gọi chuyện đó.
    assert names == ["teacher.approve", "teacher.unapprove"]
    # Chủ thể, không chỉ câu chữ: đây là thứ cho giao diện liên kết bước này tới đề sau
    # một lần tải lại, và là thứ làm transcript trả lời được "đề nào".
    assert [turn.entity_kind for turn in turns] == ["assessment", "assessment"]
    assert {turn.entity_id for turn in turns} == {draft}


@pytest.mark.asyncio
async def test_an_approved_assessment_refuses_new_questions(stack) -> None:
    """Duyệt thì khoá nội dung, và đó là toàn bộ lý do việc duyệt có nghĩa.

    Kiểm qua đường mà agent thật sự dùng để ghi câu hỏi, chứ không gọi `assert_editable`
    trực tiếp: một luật chỉ đúng khi gọi thẳng vào nó thì chưa được thi hành ở đâu.
    """
    client, maker, queue = stack
    draft = await _draft(maker, questions=1)
    assert (
        await client.post(f"/api/teacher/assessments/{draft}/approve", headers=TEACHER)
    ).status_code == 200

    async with maker() as session:
        from be.identity import Asking
        from be.teacher_tools import execute

        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        assert teacher is not None
        refused = await execute(
            session, Asking.of(teacher), "start_drafting", {"assessment_id": draft}, pool=queue
        )

    assert refused["started"] is False
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_another_teachers_assessment_reads_as_absent(stack) -> None:
    """ADR-22 trên đường duyệt.

    Hai câu trả lời phân biệt được sẽ cho bất kỳ ai dò xem giáo viên khác đang có những
    gì, chỉ bằng cách thử id — nên lời từ chối phải **giống hệt** nhau, không chỉ cùng mã
    trạng thái.
    """
    client, maker, _ = stack
    theirs = await _draft(maker, "GV-002", questions=1)

    mine_but_theirs = await client.post(
        f"/api/teacher/assessments/{theirs}/approve", headers=TEACHER
    )
    absent = await client.post("/api/teacher/assessments/khong-ton-tai/approve", headers=TEACHER)

    assert mine_but_theirs.status_code == absent.status_code == 404
    assert mine_but_theirs.json() == absent.json()
    # Và đề của họ không bị chạm: một lần từ chối đọc như không tìm thấy vẫn phải *là*
    # không tìm thấy.
    assert await _state(maker, theirs) is AssessmentState.HAS_QUESTIONS


@pytest.mark.asyncio
async def test_unapproving_an_unapproved_assessment_is_refused(stack) -> None:
    """Bảng cạnh của ADR-01 là bên phân xử, và nó nói tên cả hai state.

    Pin lại vì đường dễ đi là coi bỏ duyệt như một phép gán `state = has_questions`, và
    một phép gán như thế sẽ âm thầm đưa một đề **đã phát hành** về trạng thái soạn được —
    thu hồi là cạnh của ADR-02, không phải một lần bỏ duyệt.
    """
    client, maker, _ = stack
    draft = await _draft(maker, questions=1)

    answer = await client.post(f"/api/teacher/assessments/{draft}/unapprove", headers=TEACHER)

    assert answer.status_code == 409
    # Nguyên câu, không phải một mẩu: `"đang soạn"` cũng nằm trong câu từ chối *khác hẳn*
    # của `approve` (*"Còn N câu đang soạn"*), nên một assert bắt mẩu đó sẽ xanh cả khi
    # endpoint trả về lời từ chối của một luật khác.
    assert answer.json()["detail"] == "Đề đang ở trạng thái đang soạn nên không bỏ duyệt được."
    assert await _state(maker, draft) is AssessmentState.HAS_QUESTIONS


@pytest.mark.asyncio
async def test_a_published_assessment_cannot_be_unapproved(stack) -> None:
    """Cùng bảng cạnh, ở ca mà hậu quả là thật.

    Một đề đã phát hành mà bỏ duyệt được thì nội dung mở ra sửa trong khi học sinh đang
    làm. `_ALLOWED[PUBLISHED]` để rỗng có chủ ý, và test này là chỗ chỗ-trống đó được
    kiểm.
    """
    client, maker, _ = stack
    draft = await _draft(maker, questions=1)
    async with maker() as session:
        found = await session.get(Assessment, draft)
        assert found is not None
        found.state = AssessmentState.PUBLISHED
        await session.commit()

    answer = await client.post(f"/api/teacher/assessments/{draft}/unapprove", headers=TEACHER)

    assert answer.status_code == 409
    assert await _state(maker, draft) is AssessmentState.PUBLISHED


@pytest.mark.asyncio
async def test_a_position_a_shortened_brief_no_longer_has_does_not_block_approval(stack) -> None:
    """Một vị trí của brief cũ thì không giữ đề lại được.

    Tìm ra bằng một test khác hỏng: tôi dựng một vị trí đang chạy ở ordinal 2 trong khi
    brief chỉ xin 1 câu, và lần duyệt vẫn **thành công**. Đó không phải bug — `harvest` xoá
    mọi vị trí vượt quá `question_count` của brief hiện tại, vì đó chính là cơ chế đứng sau
    câu "đổi brief là mở một vòng mới".

    Nhưng nó đáng được viết ra, vì nếu không thì cách duy nhất biết điều này là làm hỏng
    một test khác. Và hệ quả thì có thật: giáo viên hạ từ 10 câu xuống 5 thì duyệt được
    ngay, chứ không bị năm job cũ giữ lại.
    """
    client, maker, _ = stack
    draft = await _draft(maker, questions=1)
    async with maker() as session:
        session.add(
            DraftItem(
                assessment_id=draft,
                ordinal=2,
                job_id="job-98",
                status="pending",
                brief_version=1,
                attempts=1,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()

    answer = await client.post(f"/api/teacher/assessments/{draft}/approve", headers=TEACHER)

    assert answer.status_code == 200
    assert await _state(maker, draft) is AssessmentState.APPROVED
    async with maker() as session:
        left = list(
            await session.scalars(select(DraftItem).where(DraftItem.assessment_id == draft))
        )
    assert left == []


@pytest.mark.asyncio
async def test_unapproving_an_empty_assessment_is_refused(stack) -> None:
    """Bảng cạnh biết *cạnh nào tồn tại*, không biết *ai đang xin đi*.

    Cạnh `EMPTY → HAS_QUESTIONS` có thật, nhưng nó tồn tại cho `harvest`: câu hỏi đầu tiên
    thu được đưa đề ra khỏi `EMPTY`. Một lần bỏ duyệt giao hết cho bảng sẽ đi lậu qua đúng
    cạnh đó — và đó là điều đã xảy ra. Đo được trước khi sửa: 200, rồi một đề **0 câu**
    mang state `đang soạn`, vĩnh viễn, vì cạnh ngược chưa dựng. Chính bất biến mà endpoint
    duyệt bỏ công thi hành, bị endpoint kia của cùng pha phá.
    """
    client, maker, _ = stack
    draft = await _draft(maker)

    answer = await client.post(f"/api/teacher/assessments/{draft}/unapprove", headers=TEACHER)

    assert answer.status_code == 409
    assert (
        answer.json()["detail"] == "Đề đang ở trạng thái chưa có câu hỏi nên không bỏ duyệt được."
    )
    assert await _state(maker, draft) is AssessmentState.EMPTY
    # Và không có bằng chứng nào được ghi cho một việc chưa xảy ra: một bản ghi nói sai
    # thì tệ hơn một bản ghi thiếu.
    async with maker() as session:
        turns = list(await session.scalars(select(TeacherTurn)))
    assert turns == []


@pytest.mark.asyncio
async def test_a_refused_approval_writes_nothing_at_all(stack) -> None:
    """Một request trả 409 nói *không có gì xảy ra*, nên nó phải đúng nghĩa đen.

    `harvest` tự `commit`, và nó chạy trước khi `advance` có cơ hội từ chối — nên một lần
    duyệt bị từ chối từng kịp **ghi một câu hỏi vào một đề đã khoá nội dung** rồi mới trả
    409. Đo được: status 409 trong khi số câu hỏi của đề đi từ 1 lên 2. Câu lọt vào là câu
    giáo viên chưa từng thấy, trong một đề họ đã nhận trách nhiệm.
    """
    client, maker, queue = stack
    draft = await _draft(maker, questions=1, asked=2)
    async with maker() as session:
        found = await session.get(Assessment, draft)
        assert found is not None
        found.state = AssessmentState.APPROVED
        session.add(
            DraftItem(
                assessment_id=draft,
                ordinal=2,
                job_id="job-0",
                status="pending",
                brief_version=1,
                attempts=1,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
    queue.finish("job-0", _good("Câu lẻn lút vào đề đã duyệt?"))

    answer = await client.post(f"/api/teacher/assessments/{draft}/approve", headers=TEACHER)

    assert answer.status_code == 409
    # Nguyên câu, vì câu chữ là đóng góp **quan sát được** của phép kiểm trong `approve`.
    # `harvest` nay có phép kiểm riêng nên nó mới là thứ giữ cho dữ liệu không bị ghi;
    # phép kiểm ở endpoint từ chối sớm hơn một nhịp và nói "không duyệt được" thay vì để
    # `advance` nói "không chuyển sang đã duyệt được" — một câu nói về việc giáo viên vừa
    # yêu cầu, một câu nói về một bảng cạnh họ chưa bao giờ nghe tên.
    assert answer.json()["detail"] == "Đề đang ở trạng thái đã duyệt nên không duyệt được."
    async with maker() as session:
        stems = list(
            await session.scalars(select(Question.stem).where(Question.assessment_id == draft))
        )
        left = list(
            await session.scalars(select(DraftItem).where(DraftItem.assessment_id == draft))
        )
    assert stems == ["Câu 1?"]
    # Vị trí đang chạy cũng còn nguyên: `harvest` xoá các row của brief cũ rồi commit, nên
    # một lần từ chối từng xoá dữ liệu kể cả khi không job nào xong.
    assert len(left) == 1


@pytest.mark.asyncio
async def test_harvest_never_writes_into_a_locked_assessment(stack) -> None:
    """Cùng lỗ, ở tầng mà nó thật sự sống.

    `approve` nay chặn trước khi thu hoạch, nhưng `harvest` có nhiều caller hơn thế — hai
    tool của đường chat cũng gọi nó. Nên phép kiểm phải nằm **trong** `harvest`, nếu không
    thì mỗi caller mới là một lần phải nhớ lại. Và nó cần có: `fire` kiểm lúc bắn job,
    nhưng giữa lúc bắn và lúc thu có một khoảng, và trong khoảng đó giáo viên bấm Duyệt
    được.
    """
    _, maker, queue = stack
    draft = await _draft(maker, questions=1, asked=2)
    async with maker() as session:
        found = await session.get(Assessment, draft)
        assert found is not None
        found.state = AssessmentState.APPROVED
        session.add(
            DraftItem(
                assessment_id=draft,
                ordinal=2,
                job_id="job-0",
                status="pending",
                brief_version=1,
                attempts=1,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
    queue.finish("job-0", _good("Câu thứ hai?"))

    async with maker() as session:
        landed = await drafting.harvest(session, queue, get_settings(), draft)

    assert landed == 0
    async with maker() as session:
        stems = list(
            await session.scalars(select(Question.stem).where(Question.assessment_id == draft))
        )
    assert stems == ["Câu 1?"]


@pytest.mark.asyncio
async def test_another_teachers_assessment_cannot_be_unapproved(stack) -> None:
    """ADR-22 trên đường bỏ duyệt.

    `_owned` dùng chung cho cả hai endpoint, nên cái này gần như chắc đúng — nhưng "gần
    như chắc" là lý do để viết một dòng, không phải lý do để bỏ. Phân quyền mà chỉ được
    kiểm ở một trong hai đường thì đường thứ hai là đường không ai canh.
    """
    client, maker, _ = stack
    theirs = await _draft(maker, "GV-002", questions=1)
    async with maker() as session:
        found = await session.get(Assessment, theirs)
        assert found is not None
        found.state = AssessmentState.APPROVED
        await session.commit()

    refused = await client.post(f"/api/teacher/assessments/{theirs}/unapprove", headers=TEACHER)
    absent = await client.post("/api/teacher/assessments/khong-ton-tai/unapprove", headers=TEACHER)

    assert refused.status_code == absent.status_code == 404
    assert refused.json() == absent.json()
    assert await _state(maker, theirs) is AssessmentState.APPROVED
