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

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import drafting
from be.config import get_settings
from be.db import bind_sessions
from be.seed import seed_if_empty
from be.teacher_chat import router as chat_router
from be.teacher_routes import router as assessment_router
from contracts import DraftQuestionCompleted, GeneratedOption, GeneratedQuestion, SolutionMethod
from schema.ddl import prepare_schema
from schema.models import (
    AnswerOption,
    Assessment,
    AssessmentState,
    DraftBrief,
    DraftItem,
    Method,
    Publication,
    Question,
    SchoolClass,
    Teacher,
    TeacherConversation,
    TeacherTurn,
)

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
            GeneratedOption(label="B", text="sai B", is_correct=False, error_label="lỗi B"),
            GeneratedOption(label="C", text="sai C", is_correct=False, error_label="lỗi C"),
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
        from be.teacher_tools import PHASE_WORK, execute

        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        assert teacher is not None
        refused = await execute(
            session,
            Asking.of(teacher),
            "start_drafting",
            {"assessment_id": draft},
            pool=queue,
            phase=PHASE_WORK,
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
async def _published(maker, draft: str, *, opens_in_hours: float) -> str:
    """Đẩy một đề sang `đã phát hành` kèm **một hàng `Publication` thật**.

    Gán thẳng `state = PUBLISHED` mà không có hàng nào là dựng một trạng thái chỉ tồn tại
    trong test: thực tế `published` luôn kéo theo ít nhất một lớp đang giữ đề. Một fixture
    như thế làm test đo một nhánh mà đường thật không đi qua.
    """
    opens = datetime.now(UTC) + timedelta(hours=opens_in_hours)
    async with maker() as session:
        found = await session.get(Assessment, draft)
        assert found is not None
        found.state = AssessmentState.PUBLISHED
        school_class = await session.scalar(select(SchoolClass))
        assert school_class is not None
        session.add(
            Publication(
                assessment_id=draft,
                class_id=school_class.id,
                opens_at=opens,
                closes_at=opens + timedelta(hours=1),
                phase1_minutes=15,
                phase2_minutes_per_question=5,
                remediation_deadline=opens + timedelta(hours=6),
                published_at=datetime.now(UTC),
            )
        )
        await session.commit()
        return school_class.id


@pytest.mark.asyncio
async def test_a_published_assessment_is_unapproved_by_taking_it_back_first(stack) -> None:
    """Hoàn tác một đề **đã phát hành** làm trọn hai việc, không bắt giáo viên làm hai lần.

    Trước 06/10/2026 đường này trả 409 với lý lẽ *"thu hồi trước đã"* — mà màn hình vẫn
    vẽ nút `Hoàn tác`, và `Panel` nuốt mất câu 409, nên cú bấm không làm gì và không nói
    gì. Đo được trên trình duyệt thật: bấm, im lặng, đề vẫn phát hành.

    Nay nó thu hồi mọi lớp rồi hạ hai nấc. `_ALLOWED[PUBLISHED]` vẫn để **rỗng**: đường
    duy nhất xuống từ `đã phát hành` vẫn là `withdraw`, thao tác có tên tự chở điều kiện
    của nó. Luật không nới ra, chỉ có một caller nữa biết cách đi qua nó cho đúng.
    """
    client, maker, _ = stack
    draft = await _draft(maker, questions=1)
    class_id = await _published(maker, draft, opens_in_hours=2)

    answer = await client.post(f"/api/teacher/assessments/{draft}/unapprove", headers=TEACHER)

    assert answer.status_code == 200
    assert await _state(maker, draft) is AssessmentState.HAS_QUESTIONS
    # Và lớp không còn giữ đề: một đề `đang soạn` mà `publications` vẫn sống là đề học
    # sinh thấy được trong lúc giáo viên đang sửa câu 4.
    async with maker() as session:
        row = await session.get(Publication, (draft, class_id))
    assert row is not None and row.recalled_at is not None


@pytest.mark.asyncio
async def test_a_class_past_its_opening_hour_blocks_the_whole_undo(stack) -> None:
    """Qua giờ mở thì không hoàn tác được, và câu từ chối **gọi tên lớp**.

    Đây là nửa giữ nguyên của ADR-02: thứ làm một lần phát hành không đảo ngược được là
    **học sinh đã có thể nhìn thấy đề**. Một đề mở ra sửa trong lúc có người đang làm là
    đúng cái hại mà cả ADR-01 lẫn ADR-02 ngăn.

    *"Một lớp nào đó đã qua giờ mở"* là một lời từ chối giáo viên không hành động theo
    được, nên câu này nêu tên lớp.
    """
    client, maker, _ = stack
    draft = await _draft(maker, questions=1)
    class_id = await _published(maker, draft, opens_in_hours=-1)

    answer = await client.post(f"/api/teacher/assessments/{draft}/unapprove", headers=TEACHER)

    assert answer.status_code == 409
    assert "12A" in answer.json()["detail"]
    assert await _state(maker, draft) is AssessmentState.PUBLISHED
    # Hoặc tất cả, hoặc không gì cả: không hàng nào bị thu hồi dở dang.
    async with maker() as session:
        row = await session.get(Publication, (draft, class_id))
    assert row is not None and row.recalled_at is None


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


@pytest.mark.asyncio
async def test_the_record_lands_in_the_conversation_that_made_the_paper(stack) -> None:
    """Biên bản duyệt rơi vào đoạn chat đã sinh ra đề, không phải đoạn mới nhất.

    Từ khi giáo viên mở được nhiều đoạn chat, *"ghi vào hội thoại đang chạy"* không còn là
    một câu rõ nghĩa. Ba câu trả lời khả dĩ, và hai cái sai theo cách **im lặng**: ghi vào
    đoạn mới nhất thì giáo viên đang đọc một đoạn cũ, bấm *Duyệt*, rồi không bao giờ tìm
    thấy biên bản; tin vào một id do client gửi thì BE không còn là bên quyết định.

    Cái đúng suy ra được từ dữ liệu đã có: `teacher_turns.entity_id` đã lưu đề nào sinh ra
    từ đoạn nào, từ Pha 2. Nên không endpoint nào phải nhận thêm tham số.
    """
    client, maker = stack[0], stack[1]
    paper = await _draft(maker, questions=1)
    teacher_id = await _teacher_id(maker, "GV-001")

    async with maker() as session:
        # Đoạn chat ĐÃ sinh ra đề, mở trước.
        made_it = TeacherConversation(
            teacher_id=teacher_id, started_at=datetime(2026, 1, 1, tzinfo=UTC)
        )
        session.add(made_it)
        await session.flush()
        session.add(
            TeacherTurn(
                conversation_id=made_it.id,
                sequence=0,
                kind="tool_result",
                tool_name="create_draft",
                tool_result={"created": True, "assessment_id": paper},
                entity_kind="assessment",
                entity_id=paper,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        # Và một đoạn chat mới hơn, không liên quan gì tới đề này.
        session.add(
            TeacherConversation(teacher_id=teacher_id, started_at=datetime(2026, 6, 1, tzinfo=UTC))
        )
        await session.commit()
        made_it_id = made_it.id

    answer = await client.post(f"/api/teacher/assessments/{paper}/approve", headers=TEACHER)
    assert answer.status_code == 200, answer.text

    async with maker() as session:
        noted = await session.scalar(
            select(TeacherTurn).where(TeacherTurn.tool_name == "teacher.approve")
        )
    assert noted is not None
    assert noted.conversation_id == made_it_id


@pytest.mark.asyncio
async def test_reading_a_draft_harvests_what_the_jobs_already_wrote(stack) -> None:
    """Đọc một đề là một lần **quan sát**, và quan sát là lúc thu hoạch.

    BE không có worker chạy nền. Trước ADR-25, tool `draft_progress` thu hoạch; nó đã thành
    tool chỉ-đọc để pha lên plan không ghi gì, và món nợ ấy rơi vào đây. Không thu ở route
    này thì panel của giáo viên hiện **0 câu** cho tới khi họ bấm Duyệt — mà cổng duyệt lại
    từ chối một đề `EMPTY`, nên không có đường nào ra. Đo thấy trên trình duyệt thật: mười
    câu nằm sẵn trong Redis, `questions` trong database vẫn rỗng.
    """
    client, maker, queue = stack
    draft = await _draft(maker)
    async with maker() as session:
        session.add(
            DraftItem(
                assessment_id=draft,
                ordinal=1,
                job_id="job-read",
                status="pending",
                brief_version=1,
                attempts=1,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
    queue.finish("job-read", _good("Tích phân của y = 2x là gì?"))

    answer = await client.get(f"/api/teacher/assessments/{draft}", headers=TEACHER)

    assert answer.status_code == 200
    body = answer.json()
    assert body["question_count"] == 1
    assert body["still_drafting"] == 0
    assert [one["stem"] for one in body["questions"]] == ["Tích phân của y = 2x là gì?"]
    # Và nó **ghi** chứ không chỉ trả về: lần đọc sau, kể cả từ một đường khác, thấy câu ấy.
    assert await _state(maker, draft) is AssessmentState.HAS_QUESTIONS
