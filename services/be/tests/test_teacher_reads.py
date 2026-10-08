"""Ba đường đọc mà giao diện giáo viên cần, và không đường ghi nào cấp được.

Cho tới khi có màn hình, giáo viên "xem" một đề bằng cách đọc lại câu trả lời của chat — mà một
bảng mười câu hỏi thì không nhét vào một câu trả lời được. Ba endpoint ở đây lấp đúng ba lỗ:
*tôi là ai*, *đề này có gì*, và *đề này đang phát hành cho lớp nào với giờ nào*.

Thứ đáng kiểm nhất không phải việc chúng trả về dữ liệu — mà là ba chỗ chúng **không** được phép
sai: phân quyền phải đọc y như đường ghi (ADR-22), câu luật phải là **cùng** string mà ba nơi kia
trả về (ADR-03), và nội dung chỉ-giáo-viên-được-thấy không được rò sang đường học sinh.
"""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.db import bind_sessions
from be.publication_wording import phase_one_note, phase_two_note
from be.seed import seed_if_empty
from be.student_routes import router as student_router
from be.teacher_routes import router as assessment_router
from schema.ddl import prepare_schema
from schema.models import (
    AnswerOption,
    Assessment,
    AssessmentState,
    DraftBrief,
    Method,
    Publication,
    Question,
    SchoolClass,
    Teacher,
    TeacherConversation,
    TeacherTurn,
)

TEACHER = {"X-Actor": "teacher:GV-001"}
STUDENT = {"X-Actor": "student:HS2026-1204"}


@pytest_asyncio.fixture
async def stack():
    """Một app có hai giáo viên, để "không phải của tôi" là một ca thật sự tồn tại."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        session.add(Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002"))
        await session.commit()

    app = FastAPI()
    app.include_router(assessment_router)
    app.include_router(student_router)
    app.state.queue_pool = object()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker

    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _paper(maker, teacher_code: str = "GV-001", *, with_brief: bool = True) -> str:
    """Một đề đã duyệt, hai câu, mỗi câu hai phương án và hai cách giải."""
    async with maker() as session:
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == teacher_code))
        assert teacher is not None
        paper = Assessment(
            teacher_id=teacher.id,
            title="Kiểm tra 15 phút — Hàm số",
            subject="Toán",
            grade="12",
            state=AssessmentState.APPROVED,
            created_at=datetime.now(UTC),
        )
        session.add(paper)
        await session.flush()
        if with_brief:
            session.add(
                DraftBrief(
                    assessment_id=paper.id,
                    topic_scope="Chương Hàm số",
                    difficulty="cơ bản",
                    question_count=2,
                    version=1,
                    created_at=datetime.now(UTC),
                )
            )
        for index in (1, 2):
            question = Question(
                assessment_id=paper.id,
                stem=f"Câu {index} về đạo hàm?",
                order_index=index,
                learning_objective="đạo hàm",
            )
            session.add(question)
            await session.flush()
            session.add(
                AnswerOption(
                    question_id=question.id, label="A", text="2x", is_correct=True, error_label=None
                )
            )
            session.add(
                AnswerOption(
                    question_id=question.id,
                    label="B",
                    text="x²",
                    is_correct=False,
                    error_label="quên hạ bậc",
                )
            )
            session.add(
                Method(
                    question_id=question.id, order_index=1, title="Cách 1", body="dùng công thức"
                )
            )
            session.add(
                Method(question_id=question.id, order_index=2, title="Cách 2", body="xét giới hạn")
            )
        await session.commit()
        return paper.id


async def _class_id(maker, name: str) -> str:
    async with maker() as session:
        found = await session.scalar(select(SchoolClass).where(SchoolClass.name == name))
        assert found is not None
        return found.id


@pytest.mark.asyncio
async def test_a_teacher_can_read_who_they_are(stack) -> None:
    """Dải trên cùng phải trả lời được "máy này đang là ai".

    ADR-13 nói phòng máy là dùng chung, nên mọi màn hình phải mang dải tên. Phía học sinh có
    `GET /api/me` từ lâu; phía giáo viên thì tên chỉ đi **vào** prompt của AGENT và không bao giờ
    đi ra.
    """
    client, _ = stack

    answer = await client.get("/api/teacher/me", headers=TEACHER)

    assert answer.status_code == 200
    body = answer.json()
    assert body["teacher_code"] == "GV-001"
    assert body["full_name"]
    assert body["teacher_id"]


@pytest.mark.asyncio
async def test_a_student_cannot_read_the_teacher_identity(stack) -> None:
    """Cùng một header, hai vai, hai câu trả lời.

    Pin lại vì `/api/teacher/me` là endpoint giáo viên **duy nhất** không nhận `assessment_id`, nên
    nó là endpoint duy nhất mà một lỗi phân quyền không bị `_owned` che mất.
    """
    client, _ = stack

    answer = await client.get("/api/teacher/me", headers=STUDENT)

    assert answer.status_code == 403


@pytest.mark.asyncio
async def test_reading_an_assessment_gives_the_panel_everything_it_draws(stack) -> None:
    """Panel vẽ gì thì endpoint phải trả đúng ngần ấy, không hơn không kém.

    `topic_scope` là phần *"Chương Hàm số"* trên dòng meta, và nó tới từ `DraftBrief` chứ không từ
    `Assessment` — đó là chỗ **duy nhất** có nó. Thiếu nó thì giao diện phải bịa một cái tên chương.

    `methods` đi kèm chứ không nằm sau một lần gọi nữa, vì thẻ in *"Lời giải · 2 cách"* ngay khi
    còn thu gọn: con số đó là `len(methods)`, nên tách ra thì mười thẻ là mười request chỉ để đếm.
    """
    client, maker = stack
    paper = await _paper(maker)

    answer = await client.get(f"/api/teacher/assessments/{paper}", headers=TEACHER)

    assert answer.status_code == 200
    body = answer.json()
    assert body["title"] == "Kiểm tra 15 phút — Hàm số"
    assert body["subject"] == "Toán"
    assert body["grade"] == "12"
    assert body["topic_scope"] == "Chương Hàm số"
    assert body["state"] == AssessmentState.APPROVED
    assert body["question_count"] == 2
    assert body["still_drafting"] == 0

    first = body["questions"][0]
    assert first["order"] == 1
    assert [one["label"] for one in first["options"]] == ["A", "B"]
    # Hai field mà đường học sinh không bao giờ được thấy trước khi nộp.
    assert first["options"][0]["is_correct"] is True
    assert first["options"][1]["error_label"] == "quên hạ bậc"
    # Và số cách giải, thứ thẻ in ra khi còn thu gọn.
    assert len(first["methods"]) == 2


@pytest.mark.asyncio
async def test_an_assessment_without_a_brief_reads_with_an_empty_scope(stack) -> None:
    """Không phải đề nào cũng do chat soạn ra.

    `topic_scope` rỗng là một câu trả lời, không phải một lỗi — và giao diện phải chịu được, vì
    một đề seed hay một đề nhập tay thì không có `DraftBrief` nào.
    """
    client, maker = stack
    paper = await _paper(maker, with_brief=False)

    answer = await client.get(f"/api/teacher/assessments/{paper}", headers=TEACHER)

    assert answer.status_code == 200
    assert answer.json()["topic_scope"] == ""
    assert answer.json()["difficulty"] == ""
    assert answer.json()["question_count"] == 2


@pytest.mark.asyncio
async def test_another_teachers_assessment_reads_as_absent_on_the_read_path_too(stack) -> None:
    """ADR-22 phải đúng ở **mọi** cửa, không chỉ ở đường ghi.

    Một đường đọc là chỗ dễ quên nhất: nó không đổi gì nên "cho xem thì có sao". Có sao — hai câu
    trả lời phân biệt được sẽ cho bất kỳ ai dò xem giáo viên khác đang có đề nào, chỉ bằng cách
    thử id. Nên lời từ chối phải **giống hệt** lời cho một đề không tồn tại.
    """
    client, maker = stack
    theirs = await _paper(maker, "GV-002")

    mine_but_theirs = await client.get(f"/api/teacher/assessments/{theirs}", headers=TEACHER)
    absent = await client.get("/api/teacher/assessments/khong-ton-tai", headers=TEACHER)

    assert mine_but_theirs.status_code == absent.status_code == 404
    assert mine_but_theirs.json() == absent.json()


@pytest.mark.asyncio
async def test_reading_the_publications_gives_back_the_six_parameters(stack) -> None:
    """Lỗ mà đợt trước để lại: sáu tham số đã đặt thì không đọc lại được.

    `publish-form` chỉ nói lớp nào **đang giữ** đề, không nói giữ với giờ nào — nên sau một lần tải
    lại trang, giáo viên muốn biết "12A mở lúc mấy giờ" chỉ còn cách đi hỏi học sinh.
    """
    client, maker = stack
    paper = await _paper(maker)
    morning = await _class_id(maker, "12A")
    opens = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=3)
    async with maker() as session:
        session.add(
            Publication(
                assessment_id=paper,
                class_id=morning,
                opens_at=opens,
                closes_at=opens + timedelta(minutes=45),
                phase1_minutes=15,
                phase2_minutes_per_question=5,
                remediation_deadline=opens + timedelta(hours=8),
                published_at=datetime.now(UTC),
            )
        )
        await session.commit()

    answer = await client.get(f"/api/teacher/assessments/{paper}/publications", headers=TEACHER)

    assert answer.status_code == 200
    only = answer.json()["classes"][0]
    assert only["class_name"] == "12A"
    assert only["student_count"] == 3
    assert only["phase1_minutes"] == 15
    assert only["phase2_minutes_per_question"] == 5
    # Thu hồi được tới lúc nào là con số giáo viên cần, nên nó được nêu ra chứ không để họ suy.
    assert only["withdrawable_until"] == only["opens_at"]


@pytest.mark.asyncio
async def test_a_recalled_publication_reads_as_if_it_never_happened(stack) -> None:
    """Thu hồi mềm: hàng ở lại làm sổ sách, nhưng mọi câu hỏi "lớp nào đang giữ" phải lọc nó.

    Nếu không, thu hồi lớp cuối cùng vẫn để lại một dòng trên panel nói rằng đề đang phát hành.
    """
    client, maker = stack
    paper = await _paper(maker)
    morning = await _class_id(maker, "12A")
    opens = datetime.now(UTC) + timedelta(hours=3)
    async with maker() as session:
        session.add(
            Publication(
                assessment_id=paper,
                class_id=morning,
                opens_at=opens,
                closes_at=opens + timedelta(minutes=45),
                phase1_minutes=15,
                phase2_minutes_per_question=5,
                remediation_deadline=opens + timedelta(hours=8),
                published_at=datetime.now(UTC),
                recalled_at=datetime.now(UTC),
            )
        )
        await session.commit()

    answer = await client.get(f"/api/teacher/assessments/{paper}/publications", headers=TEACHER)

    assert answer.status_code == 200
    assert answer.json()["classes"] == []


@pytest.mark.asyncio
async def test_the_read_path_prints_the_same_two_sentences_as_everywhere_else(stack) -> None:
    """ADR-03 đòi ba nơi giống hệt nhau từng chữ. Đường đọc này là nơi **thứ tư**.

    Nó không so hai response với nhau — hai bản sao của cùng một lỗi vẫn bằng nhau. Nó dựng lại câu
    bằng chính hàm trong `publication_wording` và so với thứ endpoint trả về, nên nếu ai đó in lại
    câu luật bằng chữ khác ở đây thì dòng này đỏ.
    """
    client, maker = stack
    paper = await _paper(maker)
    morning = await _class_id(maker, "12A")
    opens = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=3)
    closes = opens + timedelta(minutes=45)
    deadline = opens + timedelta(hours=8)
    async with maker() as session:
        session.add(
            Publication(
                assessment_id=paper,
                class_id=morning,
                opens_at=opens,
                closes_at=closes,
                phase1_minutes=15,
                phase2_minutes_per_question=5,
                remediation_deadline=deadline,
                published_at=datetime.now(UTC),
            )
        )
        await session.commit()

    answer = await client.get(f"/api/teacher/assessments/{paper}/publications", headers=TEACHER)

    only = answer.json()["classes"][0]
    assert only["phase_one_note"] == phase_one_note(closes, 15)
    assert only["phase_two_note"] == phase_two_note(deadline, 5)
    # Và cùng ba câu luật chưa điền số mà biểu mẫu trả về.
    assert "--:--" in answer.json()["rules"]["phase_one"]


@pytest.mark.asyncio
async def test_another_teachers_publications_read_as_absent_too(stack) -> None:
    """Cửa thứ hai của ADR-22 trên đường đọc, và là cửa dễ quên hơn.

    `publications_of` gọi `_owned` rồi **bỏ** giá trị trả về — nó gọi chỉ để lấy cái 404. Một
    dòng như thế đọc lên như thừa, và người dọn dẹp tiếp theo sẽ xoá nó. Lúc đó lịch phát hành
    của mọi giáo viên đọc được bằng cách thử id: mấy giờ lớp nào làm bài, trong bao lâu.

    Tìm ra bằng cách phá: bỏ dòng `_owned` trong hàm đó thì **không test nào đỏ**.
    """
    client, maker = stack
    theirs = await _paper(maker, "GV-002")

    mine_but_theirs = await client.get(
        f"/api/teacher/assessments/{theirs}/publications", headers=TEACHER
    )
    absent = await client.get(
        "/api/teacher/assessments/khong-ton-tai/publications", headers=TEACHER
    )

    assert mine_but_theirs.status_code == absent.status_code == 404
    assert mine_but_theirs.json() == absent.json()


@pytest.mark.asyncio
async def test_a_paper_says_which_conversation_made_it(stack) -> None:
    """Panel sống bên trong đoạn chat của nó, nên đề phải nói được đoạn ấy là đoạn nào.

    Không có con số này thì một link trỏ thẳng vào đề — một bookmark, một tab mở từ hôm
    qua — không có cách nào về đúng chỗ, và panel sẽ mở trong một đoạn chat không liên
    quan gì tới đề đang xem.
    """
    client, maker = stack
    paper = await _paper(maker)

    async with maker() as session:
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        assert teacher is not None
        thread = TeacherConversation(teacher_id=teacher.id, started_at=datetime.now(UTC))
        session.add(thread)
        await session.flush()
        session.add(
            TeacherTurn(
                conversation_id=thread.id,
                sequence=0,
                kind="tool_result",
                tool_name="create_draft",
                tool_result={"created": True, "assessment_id": paper},
                entity_kind="assessment",
                entity_id=paper,
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
        made_it = thread.id

    read = await client.get(f"/api/teacher/assessments/{paper}", headers=TEACHER)

    assert read.status_code == 200
    assert read.json()["conversation_id"] == made_it


@pytest.mark.asyncio
async def test_a_paper_from_no_conversation_says_so(stack) -> None:
    """Đề seed hoặc đề tạo bằng tay không thuộc đoạn chat nào, và nói thẳng ra.

    Trả rỗng chứ không đoán một đoạn nào đó: panel vẫn phải mở được, nhưng nó không được
    bịa ra một nguồn gốc. Màn hình đọc chuỗi rỗng rồi tự quyết mở ở đâu.
    """
    client, maker = stack
    paper = await _paper(maker)

    read = await client.get(f"/api/teacher/assessments/{paper}", headers=TEACHER)

    assert read.status_code == 200
    assert read.json()["conversation_id"] == ""
