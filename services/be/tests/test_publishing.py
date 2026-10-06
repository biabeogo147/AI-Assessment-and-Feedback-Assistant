"""Phát hành nhiều lớp, hộp xác nhận, và cửa sổ thu hồi.

Ba luật gặp nhau ở đây và chúng **đối nhau**, nên mỗi luật cần một test riêng:

- ADR-03: giờ đóng là hạn **vào**. Ai đã vào rồi thì làm đủ thời gian của mình.
- ADR-15: hạn pha 2 thì **cắt giữa chừng**, ngược hẳn luật trên.
- ADR-02: thu hồi được **cho tới hết giờ mở**, và sau đó thì không.

Thứ đáng kiểm nhất không phải từng luật mà là chỗ chúng chạm nhau: một đề phát hành cho
nhiều lớp với hạn lệch nhau, thu hồi một lớp mà **không** làm lớp khác mất bài, và lời văn
giải thích ba luật ấy giống hệt nhau ở cả ba payload. ADR-03 đòi điều cuối đúng từng chữ,
vì ba cách diễn đạt cho một luật là ba luật.
"""

import re
from datetime import UTC, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.db import bind_sessions, prepare_schema
from be.models import (
    AnswerOption,
    Assessment,
    AssessmentState,
    Attempt,
    Method,
    Publication,
    Question,
    SchoolClass,
    Student,
    Teacher,
    TeacherTurn,
    aware,
)
from be.publication_wording import (
    FAULT_CLOSES_BEFORE_OPENS,
    FAULT_OPENS_IN_THE_PAST,
    FAULT_PHASE_TWO_TOO_EARLY,
    PHASE_ONE,
    PHASE_TWO,
    RECALL_RULE,
    phase_one_note,
    phase_two_note,
)
from be.seed import seed_if_empty
from be.student_routes import router as student_router
from be.teacher_chat import router as chat_router
from be.teacher_routes import router as assessment_router

TEACHER = {"X-Actor": "teacher:GV-001"}
STRANGER = {"X-Actor": "teacher:GV-002"}


@pytest_asyncio.fixture
async def stack():
    """Một app có hai lớp của cùng giáo viên, vì "nhiều lớp" là cả phần việc của pha này."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        session.add(Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002"))
        mine = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        assert mine is not None
        afternoon = SchoolClass(teacher_id=mine.id, name="12B")
        session.add(afternoon)
        await session.flush()
        session.add(
            Student(class_id=afternoon.id, full_name="Trần Thị C", student_code="HS2026-2001")
        )
        await session.commit()

    app = FastAPI()
    app.include_router(chat_router)
    app.include_router(assessment_router)
    app.include_router(student_router)
    app.state.queue_pool = object()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker

    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _class_id(maker, name: str) -> str:
    async with maker() as session:
        found = await session.scalar(select(SchoolClass).where(SchoolClass.name == name))
        assert found is not None
        return found.id


async def _approved(maker, teacher_code: str = "GV-001") -> str:
    """Một đề đã duyệt, kèm một câu hỏi — tiền đề của mọi test ở đây."""
    async with maker() as session:
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == teacher_code))
        assert teacher is not None
        paper = Assessment(
            teacher_id=teacher.id,
            title="Đề đạo hàm giữa kỳ",
            subject="Toán",
            grade="12",
            state=AssessmentState.APPROVED,
            created_at=datetime.now(UTC),
        )
        session.add(paper)
        await session.flush()
        question = Question(
            assessment_id=paper.id,
            stem="Đạo hàm của y = x² là gì?",
            order_index=1,
            learning_objective="đạo hàm",
        )
        session.add(question)
        await session.flush()
        session.add(AnswerOption(question_id=question.id, label="A", text="2x", is_correct=True))
        session.add(Method(question_id=question.id, order_index=1, title="Cách 1", body="..."))
        await session.commit()
        return paper.id


def _window(*, opens_in_hours: float = 2.0) -> dict:
    """Năm tham số thời gian của ADR-02, mặc định hợp lệ.

    Không còn `class_id`: một lần phát hành có **một** khung giờ cho mọi lớp, và danh
    sách lớp đi riêng trong `class_ids`.
    """
    opens = datetime.now(UTC) + timedelta(hours=opens_in_hours)
    return {
        "opens_at": opens.isoformat(),
        "closes_at": (opens + timedelta(hours=1)).isoformat(),
        "phase1_minutes": 15,
        "phase2_minutes_per_question": 5,
        "remediation_deadline": (opens + timedelta(hours=6)).isoformat(),
    }


def _body(*class_ids: str, opens_in_hours: float = 2.0, preview: bool = False) -> dict:
    """Trọn một yêu cầu phát hành: một khung giờ, một danh sách lớp."""
    return {
        "schedule": _window(opens_in_hours=opens_in_hours),
        "class_ids": list(class_ids),
        "preview": preview,
    }


async def _state(maker, assessment_id: str) -> AssessmentState:
    async with maker() as session:
        found = await session.get(Assessment, assessment_id)
        assert found is not None
        return AssessmentState(found.state)


@pytest.mark.asyncio
async def test_one_assessment_reaches_two_classes_on_one_clock(stack) -> None:
    """Một lần phát hành, **một** khung giờ, nhiều lớp.

    Khoá kép của `Publication` vẫn đúng và vẫn cần: mỗi lớp một hàng, nên thu hồi được
    từng lớp, và `recalled_at` của 12B không đụng tới 12A. Thứ **không** còn là hai cái
    đồng hồ: từ 06/10/2026 giáo viên gõ một khung giờ cho cả lần phát hành.

    Đây là siết hợp đồng cho khớp thực tế chứ không phải bớt tính năng. Biểu mẫu phát
    hành chỉ có **một** bộ ô nhập và vẫn luôn gửi cùng một bộ giá trị cho mọi lớp; hợp
    đồng cũ cho phép diễn tả một thứ không màn hình nào dựng được, và cái giá là thật —
    màn hình phải in giờ *"của từng lớp"* cho một con số chung, còn câu an toàn trên thẻ
    hứa một mốc thu hồi mà giáo viên không đọc ra nổi là mốc nào.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning, afternoon = await _class_id(maker, "12A"), await _class_id(maker, "12B")

    answer = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning, afternoon, opens_in_hours=2),
    )

    assert answer.status_code == 200
    body = answer.json()
    assert [row["published"] for row in body["classes"]] == [True, True]
    assert body["state"] == AssessmentState.PUBLISHED

    async with maker() as session:
        rows = list(
            await session.scalars(select(Publication).where(Publication.assessment_id == paper))
        )
    assert len(rows) == 2
    # **Một** cái đồng hồ, không hai. Thiếu khẳng định này thì một bản cài đặt vẫn đọc
    # `schedule` riêng cho từng lớp ở đâu đó vẫn xanh, và màn hình lại có cớ in giờ của
    # từng lớp.
    assert len({row.opens_at for row in rows}) == 1
    assert len({row.closes_at for row in rows}) == 1
    assert len({row.remediation_deadline for row in rows}) == 1


@pytest.mark.asyncio
async def test_an_unapproved_assessment_cannot_be_published_over_http(stack) -> None:
    """Chỗ dòng Invariants của `AGENTS.md` chuyển từ đúng-về-chữ sang đúng-về-tinh-thần.

    Dòng *"Teacher approves an assessment before release"* vốn đúng một cách mỏng: không
    đường HTTP nào phát hành được đề chưa duyệt, vì **không đường HTTP nào phát hành cả**.
    Nay có một đường, nên câu đó mới có gì để nói.
    """
    client, maker = stack
    paper = await _approved(maker)
    async with maker() as session:
        found = await session.get(Assessment, paper)
        assert found is not None
        found.state = AssessmentState.HAS_QUESTIONS
        await session.commit()

    answer = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(await _class_id(maker, "12A")),
    )

    assert answer.status_code == 409
    assert answer.json()["detail"] == "Đề đang ở trạng thái đang soạn nên không phát hành được."
    async with maker() as session:
        rows = list(
            await session.scalars(select(Publication).where(Publication.assessment_id == paper))
        )
    assert rows == []


@pytest.mark.asyncio
async def test_publishing_can_fail_for_one_class_and_succeed_for_another(stack) -> None:
    """ADR-02 cho phép thất bại một phần, và điều đó phải còn biểu diễn được.

    Đường dễ đi là raise ngay ở lớp sai đầu tiên — và nó biến một điều khoản của ADR-02
    thành không thể xảy ra. Lớp hỏng nhận lý do của riêng nó; lớp còn lại vẫn nhận đề.

    **Cái cớ để một lớp hỏng đã đổi, và luật thì không.** Trước 06/10/2026 mỗi lớp có
    khung giờ riêng, nên lớp này sai giờ còn lớp kia đúng giờ. Nay khung giờ là một, nên
    một khung giờ sai làm **mọi** lớp trượt — và đó đúng là câu trả lời đúng. Thất bại
    một phần vẫn còn, chỉ là vì những lý do thuộc về **lớp** chứ không thuộc về giờ: một
    lớp của giáo viên khác (ADR-22), một lớp đã qua giờ mở, một lớp đang có người làm bài.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")

    answer = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning, "lop-cua-nguoi-khac"),
    )

    assert answer.status_code == 200
    first, second = answer.json()["classes"]
    assert first["published"] is True
    assert second["published"] is False
    assert second["reason"] == "không tìm thấy lớp"
    # Và đề vẫn sang `đã phát hành`, vì **có** lớp nhận được.
    assert await _state(maker, paper) is AssessmentState.PUBLISHED
    async with maker() as session:
        rows = list(
            await session.scalars(select(Publication).where(Publication.assessment_id == paper))
        )
    assert [row.class_id for row in rows] == [morning]


@pytest.mark.asyncio
async def test_an_assessment_stays_approved_when_no_class_accepted_it(stack) -> None:
    """Không lớp nào nhận được thì đề **không** được sang `đã phát hành`.

    Pin lại vì đường dễ đi là `advance` vô điều kiện sau khi vòng lặp chạy xong. Một đề
    `đã phát hành` mà không có hàng `Publication` nào là một state không ai giải thích
    được, và nó khoá luôn đường bỏ duyệt — `_ALLOWED[PUBLISHED]` để rỗng, nên đề đó mắc
    kẹt vĩnh viễn.
    """
    client, maker = stack
    paper = await _approved(maker)

    answer = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(await _class_id(maker, "12A"), opens_in_hours=-1),
    )

    assert answer.status_code == 200
    assert answer.json()["classes"][0]["published"] is False
    assert await _state(maker, paper) is AssessmentState.APPROVED


@pytest.mark.asyncio
async def test_a_preview_computes_everything_and_writes_nothing(stack) -> None:
    """Hộp xác nhận của ADR-02 đọc lại **giá trị thật**, không đọc con số dựng sẵn.

    Cách duy nhất chắc chắn đúng là để cùng một đoạn code tính ra chúng — một hộp xác nhận
    tự tính lại là một bản cài đặt thứ hai của cùng một luật, và nó sẽ lệch. Nên `preview`
    đi qua đúng đường mà lần ghi thật đi, chỉ không ghi.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")
    body = _body(morning)

    preview = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json={**body, "preview": True},
    )

    assert preview.status_code == 200
    shown = preview.json()
    assert shown["preview"] is True
    assert shown["classes"][0]["published"] is True
    assert shown["classes"][0]["class_name"] == "12A"
    # Thu hồi được tới lúc nào là con số giáo viên cần biết, nên nó được nêu ra chứ không
    # để họ suy từ `opens_at`. So với giờ **đã gửi**, không so hai field với nhau: hai field
    # ấy được gán từ cùng một biểu thức nên chúng không thể lệch, và một `assert` như thế
    # không canh gì.
    assert shown["classes"][0]["withdrawable_until"] == datetime.fromisoformat(
        body["schedule"]["opens_at"]
    ).astimezone(UTC).isoformat().replace("+00:00", "Z")
    # Không ghi gì, và đề không đổi state.
    assert shown["state"] == AssessmentState.APPROVED
    assert await _state(maker, paper) is AssessmentState.APPROVED
    async with maker() as session:
        rows = list(
            await session.scalars(select(Publication).where(Publication.assessment_id == paper))
        )
    assert rows == []

    # Và lần ghi thật sau đó cho **đúng** mấy mốc mà bản xem trước đã hứa.
    real = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=body,
    )
    assert real.status_code == 200
    promised = shown["classes"][0]
    delivered = real.json()["classes"][0]
    assert [promised[key] for key in ("opens_at", "closes_at", "remediation_deadline")] == [
        delivered[key] for key in ("opens_at", "closes_at", "remediation_deadline")
    ]


@pytest.mark.asyncio
async def test_the_timing_rules_read_identically_in_every_payload(stack) -> None:
    """ADR-03 đòi ba nơi giống hệt nhau **từng chữ**.

    Bốn nơi, không ba: lúc mở biểu mẫu, lúc xác nhận, biên bản sau khi phát hành, và — từ khi có
    giao diện — lúc **đọc lại** lịch phát hành của một đề. Nơi thứ tư thêm vào cùng đợt dựng FE, vì
    panel phải vẽ lại được câu luật sau một lần tải lại trang. Chúng cùng đọc
    một hằng số trong `publication_wording`, nên "giống hệt nhau" là một tính chất của code
    chứ không phải một việc ai đó phải nhớ — và `assert` dưới đây so với chính hằng số đó,
    không so ba response với nhau: ba bản sao của cùng một lỗi vẫn bằng nhau.
    """
    client, maker = stack
    paper = await _approved(maker)
    body = _body(await _class_id(maker, "12A"))

    form = await client.get(f"/api/teacher/assessments/{paper}/publish-form", headers=TEACHER)
    confirm = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json={**body, "preview": True},
    )
    record = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=body,
    )

    for answer in (form, confirm, record):
        assert answer.status_code == 200

    def shape(sentence: str) -> str:
        """Bỏ số và chỗ trống đi, để so **khuôn** câu chứ không so giá trị.

        `--` cũng bị bỏ, vì biểu mẫu in `--:--` ở đúng chỗ mà hai payload kia in giờ: hai
        bên khác nhau ở **giá trị**, và khuôn là thứ phải giống.
        """
        return re.sub(r"\d+|-{2}", "#", sentence)

    # Biểu mẫu nhận **cùng một câu**, chỉ với `--:--` ở chỗ số. Bản trước có một hằng số
    # nói chung chung cho biểu mẫu và một hàm điền số cho hai payload kia — hai câu khác
    # nhau hoàn toàn, tức đúng cái "ba cách diễn đạt cho một luật" mà ADR-03 ngăn.
    assert form.json()["rules"]["phase_one"] == phase_one_note()
    assert form.json()["rules"]["phase_two"] == phase_two_note()
    assert "--:--" in form.json()["rules"]["phase_one"]

    # Và ba nơi cùng một khuôn. So khuôn chứ không so chuỗi, vì hai nơi sau có số thật —
    # nếu so chuỗi thì phép kiểm chỉ còn cách so ba hằng số với nhau, và ba bản sao của
    # cùng một lỗi vẫn bằng nhau.
    filled = confirm.json()["classes"][0]
    assert shape(filled["phase_one_note"]) == shape(form.json()["rules"]["phase_one"])
    assert shape(filled["phase_two_note"]) == shape(form.json()["rules"]["phase_two"])
    assert record.json()["classes"][0]["phase_one_note"] == filled["phase_one_note"]
    assert record.json()["classes"][0]["phase_two_note"] == filled["phase_two_note"]
    for answer in (form, confirm, record):
        assert answer.json()["rules"]["recall"] == RECALL_RULE

    # Nơi thứ tư: đường đọc. Nó phải in **cùng** câu mà biên bản vừa in, không phải một câu
    # tương đương — nếu ai in lại bằng chữ khác ở đó thì dòng này đỏ.
    reread = await client.get(f"/api/teacher/assessments/{paper}/publications", headers=TEACHER)
    assert reread.status_code == 200
    assert reread.json()["rules"] == form.json()["rules"]
    assert reread.json()["classes"][0]["phase_one_note"] == filled["phase_one_note"]
    assert reread.json()["classes"][0]["phase_two_note"] == filled["phase_two_note"]


@pytest.mark.asyncio
async def test_the_form_offers_no_default_times_and_says_which_classes_hold_it(stack) -> None:
    """Biểu mẫu không gợi sẵn mốc thời gian nào, có chủ ý.

    Một giá trị gợi sẵn là một giá trị giáo viên sẽ bấm qua, và đây đúng là chỗ ADR-03 nói
    hiểu nhầm gây hại theo chiều ngược: người muốn bài nộp xong trước 18:00 sẽ đặt giờ đóng
    17:45 để bù, tức tự cắt mười lăm phút của cả lớp mà không biết.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")

    before = (
        await client.get(f"/api/teacher/assessments/{paper}/publish-form", headers=TEACHER)
    ).json()
    assert before["can_publish"] is True
    assert before["reason"] == ""
    assert {row["name"] for row in before["classes"]} == {"12A", "12B"}
    assert all(row["published"] is False for row in before["classes"])
    # Số học sinh đi kèm vì đó là cách phân biệt hai lớp cùng tên (ADR-23 dùng đúng con số
    # này), nên nó phải là một phép đếm thật — và `!= [0]` thì xanh cả khi lớp biến mất
    # khỏi payload, nên nó phải là con số đúng.
    assert [row["student_count"] for row in before["classes"] if row["name"] == "12A"] == [3]
    # Và không field nào gợi sẵn giờ. So **nguyên bộ khoá**, chứ không `not in` một tên
    # mà model vốn không khai: cái đó xanh mãi mãi và không canh gì.
    assert set(before) == {
        "assessment_id",
        "title",
        "state",
        "question_count",
        "can_publish",
        "reason",
        "classes",
        "rules",
        "undo_blocked",
    }
    # Chưa lớp nào mở thì còn lùi được, nên câu chặn rỗng.
    assert before["undo_blocked"] == ""

    await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning),
    )

    after = (
        await client.get(f"/api/teacher/assessments/{paper}/publish-form", headers=TEACHER)
    ).json()
    assert {row["name"]: row["published"] for row in after["classes"]} == {
        "12A": True,
        "12B": False,
    }


@pytest.mark.asyncio
async def test_a_bad_schedule_is_named_rule_by_rule(stack) -> None:
    """Ba điều kiện giờ, ba câu từ chối khác nhau.

    Một câu chung ("giờ không hợp lệ") buộc giáo viên đi đoán cái nào sai trong sáu con số
    họ vừa gõ.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")

    past = _window(opens_in_hours=-1)
    backwards = _window()
    backwards["closes_at"] = backwards["opens_at"]
    short_phase_two = _window()
    short_phase_two["remediation_deadline"] = short_phase_two["closes_at"]
    # Ca thứ tư, và là ca mà bản đầu **nhận**: hạn pha 2 sau giờ đóng nhưng **trước** giờ
    # nộp cuối của pha 1. Hai câu luật trong cùng một payload lúc đó tự phủ định nhau —
    # pha 2 đóng trước khi người vào muộn nhất kịp nộp.
    before_last_submission = _window()
    closes = datetime.fromisoformat(before_last_submission["closes_at"])
    before_last_submission["phase1_minutes"] = 60
    before_last_submission["remediation_deadline"] = (closes + timedelta(minutes=1)).isoformat()

    reasons = []
    for schedule in (past, backwards, short_phase_two, before_last_submission):
        answer = await client.post(
            f"/api/teacher/assessments/{paper}/publications",
            headers=TEACHER,
            json={"schedule": schedule, "class_ids": [morning], "preview": True},
        )
        assert answer.status_code == 200
        reasons.append(answer.json()["classes"][0]["reason"])

    assert reasons == [
        "giờ mở phải ở tương lai",
        "giờ đóng phải sau giờ mở",
        "hạn pha 2 phải sau giờ nộp cuối của pha 1",
        "hạn pha 2 phải sau giờ nộp cuối của pha 1",
    ]


@pytest.mark.asyncio
async def test_another_teachers_class_cannot_receive_my_assessment(stack) -> None:
    """ADR-22 trên đường phát hành, và nó là một lớp chứ không phải một đề.

    `_owned` canh phía đề; phía **lớp** là một câu hỏi riêng, và nó dễ quên hơn vì
    `class_id` tới từ body chứ không từ đường dẫn.
    """
    client, maker = stack
    paper = await _approved(maker)
    async with maker() as session:
        stranger = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-002"))
        assert stranger is not None
        theirs = SchoolClass(teacher_id=stranger.id, name="11B")
        session.add(theirs)
        await session.commit()
        theirs_id = theirs.id

    answer = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(theirs_id),
    )

    assert answer.status_code == 200
    assert answer.json()["classes"][0]["reason"] == "không tìm thấy lớp"
    async with maker() as session:
        rows = list(
            await session.scalars(select(Publication).where(Publication.assessment_id == paper))
        )
    assert rows == []


@pytest.mark.asyncio
async def test_withdrawing_before_the_opening_hour_is_allowed(stack) -> None:
    """Cửa sổ thu hồi của ADR-02: một sai lầm bắt được trước khi có ai vào làm thì không
    tốn gì cả.

    Và nó phải thật sự làm đề biến mất với học sinh — nếu không thì `recalled_at` chỉ là
    một cột đẹp. Đó là nửa mà đường học sinh trước đây **không** có.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")
    await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning),
    )

    answer = await client.post(
        f"/api/teacher/assessments/{paper}/publications/{morning}/withdraw", headers=TEACHER
    )

    assert answer.status_code == 200
    assert answer.json()["classes"][0]["reason"] == "đã thu hồi"
    # Lớp cuối cùng, nên đề về `đã duyệt` — không về nháp: nội dung vẫn khoá, chỉ cài đặt
    # phát hành bị gỡ.
    assert await _state(maker, paper) is AssessmentState.APPROVED
    # Hàng vẫn ở lại làm sổ sách của giáo viên.
    async with maker() as session:
        row = await session.get(Publication, (paper, morning))
    assert row is not None and row.recalled_at is not None
    # Nhưng với học sinh thì nó chưa từng xảy ra.
    listed = await client.get("/api/me/assignments", headers={"X-Actor": "student:HS2026-1204"})
    assert listed.status_code == 200
    assert [row for row in listed.json() if row["assignment_id"] == paper] == []


@pytest.mark.asyncio
async def test_withdrawing_after_the_opening_hour_is_refused(stack) -> None:
    """Sau giờ mở thì không lấy lại được, vì học sinh đã có thể nhìn thấy đề.

    Ranh giới đặt ở **giờ mở** chứ không ở lúc bấm nút: thứ làm hành động thành không đảo
    ngược được là việc đề đã hiện ra, không phải thao tác của giáo viên.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")
    await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning),
    )
    # Lùi giờ mở về quá khứ: học sinh đã vào được.
    async with maker() as session:
        row = await session.get(Publication, (paper, morning))
        assert row is not None
        row.opens_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()

    answer = await client.post(
        f"/api/teacher/assessments/{paper}/publications/{morning}/withdraw", headers=TEACHER
    )

    assert answer.status_code == 409
    assert RECALL_RULE in answer.json()["detail"]
    assert await _state(maker, paper) is AssessmentState.PUBLISHED
    async with maker() as session:
        row = await session.get(Publication, (paper, morning))
    assert row is not None and row.recalled_at is None


@pytest.mark.asyncio
async def test_withdrawing_one_of_two_classes_keeps_the_assessment_published(stack) -> None:
    """Thu hồi 12B **không** làm 12A mất bài.

    Đây là khẳng định mà cả Pha 1 dựng lên để có thể viết ra. Một đề về `đã duyệt` trong
    lúc 12A vẫn đang giữ nó là đúng cái hại mà ADR-02 ngăn — và `withdraw` không được
    phép đoán, nên nó nhận con số "còn bao nhiêu lớp đang giữ" từ caller.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning, afternoon = await _class_id(maker, "12A"), await _class_id(maker, "12B")
    await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning, afternoon),
    )

    first = await client.post(
        f"/api/teacher/assessments/{paper}/publications/{afternoon}/withdraw", headers=TEACHER
    )

    assert first.status_code == 200
    assert first.json()["state"] == AssessmentState.PUBLISHED
    assert await _state(maker, paper) is AssessmentState.PUBLISHED

    second = await client.post(
        f"/api/teacher/assessments/{paper}/publications/{morning}/withdraw", headers=TEACHER
    )

    assert second.status_code == 200
    assert second.json()["state"] == AssessmentState.APPROVED
    assert await _state(maker, paper) is AssessmentState.APPROVED


@pytest.mark.asyncio
async def test_withdrawing_a_class_that_never_held_it_reads_as_absent(stack) -> None:
    """Chưa phát hành, và đã thu hồi rồi, đọc lên giống nhau.

    Hai câu trả lời phân biệt được sẽ cho biết đề **từng** được phát hành cho lớp đó, mà
    đó là sổ sách của giáo viên chứ không phải thông tin của người đang thử id.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning, afternoon = await _class_id(maker, "12A"), await _class_id(maker, "12B")
    await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning),
    )
    await client.post(
        f"/api/teacher/assessments/{paper}/publications/{morning}/withdraw", headers=TEACHER
    )

    already = await client.post(
        f"/api/teacher/assessments/{paper}/publications/{morning}/withdraw", headers=TEACHER
    )
    never = await client.post(
        f"/api/teacher/assessments/{paper}/publications/{afternoon}/withdraw", headers=TEACHER
    )

    assert already.status_code == never.status_code == 404
    assert already.json() == never.json()


@pytest.mark.asyncio
async def test_republishing_to_the_same_class_replaces_its_schedule(stack) -> None:
    """Phát hành lại cho cùng một lớp thay thế, không thêm một bộ thứ hai.

    Vẫn là luật ban đầu của bảng này — hai bộ hạn cùng sống cho **một lớp** là trạng thái
    không ai giải thích nổi cho học sinh — chỉ áp ở đúng cấp mà nó thực sự nói về. Và nó
    xoá `recalled_at`: phát hành lại sau khi thu hồi là một lần phát hành mới.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")
    await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning, opens_in_hours=2),
    )
    await client.post(
        f"/api/teacher/assessments/{paper}/publications/{morning}/withdraw", headers=TEACHER
    )

    again = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning, opens_in_hours=9),
    )

    assert again.status_code == 200
    async with maker() as session:
        rows = list(
            await session.scalars(select(Publication).where(Publication.assessment_id == paper))
        )
    assert len(rows) == 1
    assert rows[0].recalled_at is None
    # Và nó **thay thế** thật: tên test nói thế, nên giờ mở phải là giờ mới. Bản trước chỉ
    # đếm hàng, nên nó xanh cả khi lần phát hành thứ hai bị bỏ qua hoàn toàn.
    assert aware(rows[0].opens_at) > datetime.now(UTC) + timedelta(hours=8)
    assert await _state(maker, paper) is AssessmentState.PUBLISHED


@pytest.mark.asyncio
async def test_publishing_leaves_the_class_names_in_the_transcript(stack) -> None:
    """Biên bản phải trả lời được câu duy nhất giáo viên sẽ hỏi lại sau một tuần.

    *"Đã phát hành cho 2 lớp"* không trả lời được câu đó. Tên lớp thì có.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning, afternoon = await _class_id(maker, "12A"), await _class_id(maker, "12B")

    await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning, afternoon, opens_in_hours=8),
    )

    async with maker() as session:
        turns = list(await session.scalars(select(TeacherTurn).order_by(TeacherTurn.sequence)))
    assert [turn.tool_name for turn in turns] == ["teacher.publish"]
    assert turns[0].entity_kind == "assessment"
    assert turns[0].entity_id == paper
    assert turns[0].tool_result["classes"] == ["12A", "12B"]


@pytest.mark.asyncio
async def test_a_student_cannot_start_an_attempt_on_a_recalled_publication(stack) -> None:
    """Cửa thứ hai của việc thu hồi, và nó là cửa dễ quên hơn.

    Đường liệt kê bài tự query nên nó phải tự lọc; nhưng mọi route khác phía học sinh đi
    qua `_publication`, và nếu chỗ đó không lọc thì một học sinh biết id vẫn vào làm được
    một đề đã thu hồi. Lời từ chối phải là *"chưa được phát hành"* chứ không phải *"chưa
    tới giờ mở"*: với học sinh thì lần phát hành ấy chưa từng xảy ra, và một câu nói về giờ
    mở là một câu thừa nhận đề có thật.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")
    await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning),
    )
    await client.post(
        f"/api/teacher/assessments/{paper}/publications/{morning}/withdraw", headers=TEACHER
    )

    answer = await client.post(
        f"/api/assignments/{paper}/attempts", headers={"X-Actor": "student:HS2026-1204"}
    )

    assert answer.status_code == 404
    assert answer.json()["detail"] == "Bài này chưa được phát hành"


@pytest.mark.asyncio
async def test_the_filled_in_notes_match_the_sentence_adr_03_pinned_on_figma(stack) -> None:
    """Câu luật phải có **số thật** trong đó, và số đó là một phép tính.

    ADR-03 chốt chuỗi này ở ba nơi trên Figma và ví dụ của nó là *"đóng 18:00, làm 15 phút,
    thì bài cuối nộp 18:15"* — tức con số thứ hai **diễn đạt ra chính cái luật**. Một câu
    chung chung nói đúng mà không dạy được gì; một câu có số do FE tự tính là một bản cài
    đặt thứ hai của phép tính ấy, và nó sẽ lệch.

    Nên test này không so ba response với nhau — ba bản sao của cùng một lỗi vẫn bằng nhau
    — nó dựng lại câu từ sáu tham số đã gửi và so với thứ BE trả về.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")
    opens = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=3)
    body = {
        "schedule": {
            "opens_at": opens.isoformat(),
            "closes_at": (opens + timedelta(hours=2)).isoformat(),
            "phase1_minutes": 15,
            "phase2_minutes_per_question": 5,
            "remediation_deadline": (opens + timedelta(hours=8)).isoformat(),
        },
        "class_ids": [morning],
    }

    confirm = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json={**body, "preview": True},
    )
    record = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=body,
    )

    closes = opens + timedelta(hours=2)
    last_submission = closes + timedelta(minutes=15)
    expected_one = (
        f"Vào tham gia tới hết {closes:%H:%M} - có thể nộp lúc "
        f"{last_submission:%H:%M}, và không dừng người đang làm."
    )
    expected_two = (
        f"Chữa bài tới hết {opens + timedelta(hours=8):%H:%M} - mỗi lượt "
        "5 phút một câu, và hết hạn thì lượt đang làm bị DỪNG."
    )

    for answer in (confirm, record):
        shown = answer.json()["classes"][0]
        assert shown["phase_one_note"] == expected_one
        assert shown["phase_two_note"] == expected_two

    # Và đây là phép so chặt nhất: chuỗi **literal** đọc từ Figma node `67:29`, với đúng
    # bộ số của ví dụ trong ADR-03. Dấu gạch là gạch **ngắn** -- bản đầu tôi viết gạch dài,
    # và nó lọt qua mọi test vì mọi test đều dựng lại câu bằng chính hằng số sai đó.
    assert phase_one_note(datetime(2026, 10, 1, 18, 0, tzinfo=UTC), 15) == (
        "Vào tham gia tới hết 18:00 - có thể nộp lúc 18:15, và không dừng người đang làm."
    )

    # Giờ nộp cuối là một phép tính, nên nó phải KHÁC giờ đóng — nếu bằng nhau thì
    # `phase1_minutes` đã bị bỏ qua, và cả câu thành một lời nói sai về chính cái luật.
    assert f"{closes:%H:%M}" != f"{last_submission:%H:%M}"


@pytest.mark.asyncio
async def test_a_schedule_sent_with_a_local_offset_is_stored_as_utc(stack) -> None:
    """Ca duy nhất mà SQLite và Postgres cho hai kết quả khác nhau — lệch bảy giờ.

    Dialect SQLite của SQLAlchemy **bỏ `tzinfo` mà không chuyển đổi**, nên `19:23+07:00`
    ghi xuống thành `19:23` naive rồi đọc lại thành `19:23Z` — muộn hơn bảy giờ so với
    điều giáo viên đặt. Postgres `timestamptz` thì lưu đúng. Đo được trước khi sửa.

    Và hộp xác nhận **không** bắt được lỗi này mà còn che nó: nó đọc lại đúng chuỗi vừa
    gõ, nên *"đọc lại đúng giá trị vừa nhập"* của ADR-02 nhìn ra vẫn đúng. Nên phép kiểm
    phải đọc **hàng trong database**, không đọc response.

    Mọi test khác trong file gửi `+00:00`, nên không test nào khác với tới ca này — một
    FE dùng `dayjs().format()` hay `<input type=datetime-local>` thì gửi offset địa phương.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")
    ict = timezone(timedelta(hours=7))
    opens = (datetime.now(UTC) + timedelta(hours=3)).astimezone(ict).replace(microsecond=0)

    answer = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json={
            "class_ids": [morning],
            "schedule": {
                "opens_at": opens.isoformat(),
                "closes_at": (opens + timedelta(hours=1)).isoformat(),
                "phase1_minutes": 15,
                "phase2_minutes_per_question": 5,
                "remediation_deadline": (opens + timedelta(hours=6)).isoformat(),
            },
        },
    )

    assert answer.status_code == 200
    async with maker() as session:
        row = await session.get(Publication, (paper, morning))
    assert row is not None
    # Cùng một thời điểm, viết bằng UTC. `aware()` chỉ **gắn nhãn** nên nếu offset bị bỏ
    # mà không chuyển đổi thì dòng này đỏ.
    assert aware(row.opens_at) == opens.astimezone(UTC)


@pytest.mark.asyncio
async def test_a_naive_schedule_is_refused_instead_of_guessed(stack) -> None:
    """Một giờ không có múi giờ thì BE không có cách nào biết nó là giờ nào.

    Trước khi `ClassSchedule` dùng `AwareDatetime`, `2026-10-01T08:00` được nhận và hiểu
    là 08:00 UTC — tức 15:00 ở Việt Nam. Giáo viên đặt tiết sáng, học sinh nhận tiết
    chiều, và không gì báo. Một 422 là phép kiểm rẻ nhất có thể cho chuyện đó.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")
    naive = (datetime.now() + timedelta(hours=3)).replace(microsecond=0, tzinfo=None)

    answer = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json={
            "class_ids": [morning],
            "schedule": {
                "opens_at": naive.isoformat(),
                "closes_at": (naive + timedelta(hours=1)).isoformat(),
                "phase1_minutes": 15,
                "phase2_minutes_per_question": 5,
                "remediation_deadline": (naive + timedelta(hours=6)).isoformat(),
            },
        },
    )

    assert answer.status_code == 422
    async with maker() as session:
        rows = list(
            await session.scalars(select(Publication).where(Publication.assessment_id == paper))
        )
    assert rows == []


@pytest.mark.asyncio
async def test_the_same_class_twice_in_one_request_is_refused(stack) -> None:
    """Hai dòng cùng báo thành công với hai giờ khác nhau, mà chỉ một được ghi.

    Đo được trước khi sửa: `[True, True]` trong biên bản, **một** hàng trong bảng, và cái
    sau thắng. `preview` nói y như vậy — nên hộp xác nhận của ADR-02 xác nhận một thứ
    không xảy ra: giáo viên tin 12A mở buổi sáng, thực tế mở buổi chiều.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")

    answer = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning, morning, opens_in_hours=2),
    )

    assert answer.status_code == 422
    assert "một lần" in str(answer.json())
    async with maker() as session:
        rows = list(
            await session.scalars(select(Publication).where(Publication.assessment_id == paper))
        )
    assert rows == []


@pytest.mark.asyncio
async def test_a_class_can_be_added_after_the_assessment_is_already_published(stack) -> None:
    """ADR-02 nói một đề đi tới nhiều lớp, không nói **trong một request**.

    Bản đầu từ chối mọi lần phát hành khi đề đã ở `đã phát hành`, và hậu quả là vĩnh viễn:
    đường duy nhất về `đã duyệt` là thu hồi **mọi** lớp, mà `may_withdraw` chặn khi đã qua
    giờ mở của lớp đầu. Nên một đề phát hành cho 12A hôm nay thì không bao giờ phát hành
    được cho 12C — trong khi `Publication` có khoá kép chính để việc đó khả thi.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning, afternoon = await _class_id(maker, "12A"), await _class_id(maker, "12B")
    await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning),
    )
    assert await _state(maker, paper) is AssessmentState.PUBLISHED

    later = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(afternoon, opens_in_hours=9),
    )

    assert later.status_code == 200
    assert later.json()["classes"][0]["published"] is True
    async with maker() as session:
        rows = list(
            await session.scalars(select(Publication).where(Publication.assessment_id == paper))
        )
    assert {row.class_id for row in rows} == {morning, afternoon}
    # Và biểu mẫu nói đúng chuyện đó, chứ không nói "chỉ đề đã duyệt mới phát hành được".
    form = await client.get(f"/api/teacher/assessments/{paper}/publish-form", headers=TEACHER)
    assert form.json()["can_publish"] is True


@pytest.mark.asyncio
async def test_a_class_past_its_opening_hour_cannot_have_its_schedule_rewritten(stack) -> None:
    """Phép kiểm **bắt buộc** đi kèm việc nới cổng state ở test trên.

    Trước khi nới, nhánh ghi đè *vô tình* an toàn: đề ở `đã phát hành` thì cả request bị từ
    chối, nên không ai tới được chỗ ghi đè một lớp đang làm bài. An toàn nhờ một tác dụng
    phụ không phải an toàn — và nới cổng mở ngay hai đường: sửa hạn dưới chân học sinh
    đang làm, và đặt `recalled_at = None` cộng một `opens_at` mới ở tương lai để
    `may_withdraw` lại cho thu hồi một lần phát hành mà học sinh **đã** vào.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning, afternoon = await _class_id(maker, "12A"), await _class_id(maker, "12B")
    await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning),
    )
    async with maker() as session:
        row = await session.get(Publication, (paper, morning))
        assert row is not None
        row.opens_at = datetime.now(UTC) - timedelta(minutes=5)
        was = row.opens_at
        await session.commit()

    answer = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning, afternoon, opens_in_hours=20),
    )

    assert answer.status_code == 200
    rewritten, added = answer.json()["classes"]
    assert rewritten["published"] is False
    assert rewritten["reason"] == "lớp này đã qua giờ mở nên không đổi được cài đặt phát hành"
    # Lớp còn lại vẫn nhận được — vẫn là luật thất bại một phần của ADR-02.
    assert added["published"] is True
    async with maker() as session:
        row = await session.get(Publication, (paper, morning))
    assert row is not None
    assert aware(row.opens_at) == aware(was)
    assert row.recalled_at is None


@pytest.mark.asyncio
async def test_a_class_with_a_started_attempt_cannot_have_its_schedule_rewritten(stack) -> None:
    """Một `Attempt` tồn tại là bằng chứng mạnh hơn một mốc thời gian.

    Đồng hồ có thể nói chưa tới giờ mở — lệch giờ máy, hay một lần ghi đè trước đó — nhưng
    nếu đã có người bắt đầu làm thì hạn của lớp ấy không còn là thứ sửa được.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")
    await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning),
    )
    async with maker() as session:
        student = await session.scalar(select(Student).where(Student.class_id == morning))
        assert student is not None
        now = datetime.now(UTC)
        session.add(
            Attempt(
                assessment_id=paper,
                student_id=student.id,
                class_id=morning,
                started_at=now,
                ends_at=now + timedelta(minutes=15),
            )
        )
        await session.commit()

    answer = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning, opens_in_hours=20),
    )

    assert answer.status_code == 200
    assert answer.json()["classes"][0]["reason"] == (
        "lớp này đã có học sinh làm bài nên không đổi được cài đặt phát hành"
    )


@pytest.mark.asyncio
async def test_the_note_is_written_in_the_timezone_the_teacher_typed(stack) -> None:
    """Lưu bằng UTC, **hiện** bằng giờ giáo viên đang đọc.

    Tìm ra bằng một lượt chạy thật trên Postgres, không bằng test: gửi `08:45+07:00` thì
    câu luật in *"Vào tham gia tới hết 01:45"*. Con số ấy đúng về vật lý và vô nghĩa với
    người đọc — đúng loại hiểu nhầm mà ADR-03 dành cả tài liệu để ngăn, chỉ theo một chiều
    khác. Không test nào trước đó thấy được vì tất cả đều gửi UTC, nên giờ hiện luôn trùng
    giờ gửi.

    Offset đi kèm request **là** múi giờ người gửi đang đọc, nên nó là thứ duy nhất BE cần
    và nó đã có sẵn.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")
    ict = timezone(timedelta(hours=7))
    opens = (datetime.now(ict) + timedelta(days=1)).replace(
        hour=8, minute=0, second=0, microsecond=0
    )

    answer = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json={
            "class_ids": [morning],
            "schedule": {
                "opens_at": opens.isoformat(),
                "closes_at": (opens + timedelta(minutes=45)).isoformat(),
                "phase1_minutes": 15,
                "phase2_minutes_per_question": 5,
                "remediation_deadline": opens.replace(hour=22).isoformat(),
            },
            "preview": True,
        },
    )

    assert answer.status_code == 200
    shown = answer.json()["classes"][0]
    # Giáo viên gõ 08:45 và 09:00 giờ Việt Nam, nên câu luật phải nói đúng hai con số đó.
    assert shown["phase_one_note"] == (
        "Vào tham gia tới hết 08:45 - có thể nộp lúc 09:00, và không dừng người đang làm."
    )
    assert shown["phase_two_note"].startswith("Chữa bài tới hết 22:00 - ")
    # Mà thứ **lưu** xuống vẫn là UTC.
    assert shown["opens_at"].endswith("Z") or "+00:00" in shown["opens_at"]


@pytest.mark.asyncio
async def test_the_preview_refuses_exactly_where_the_real_publish_refuses(stack) -> None:
    """Hộp xác nhận đọc lại **giá trị thật**, kể cả khi giá trị thật là một lời từ chối.

    Một lượt chạy thật qua giao diện tìm ra chỗ này: `preview` trả `published: true` cho một
    lớp đã qua giờ mở, hộp xác nhận hiện ra đầy đủ hai câu luật, rồi lần gửi thật mới từ
    chối. Nguyên nhân là `_publish_one` thoát sớm ở nhánh preview **trước** khi kiểm
    `_already_running` — nên hộp xác nhận hứa một việc mà hệ thống đã biết là không làm được.

    Không test nào cũ thấy được, vì mọi test preview đều dùng một lớp chưa phát hành bao giờ.
    Điều khoản của ADR-02 không phải "preview tính ra cùng mấy con số" mà là **preview đi qua
    cùng những cổng**.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")
    await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning),
    )
    async with maker() as session:
        row = await session.get(Publication, (paper, morning))
        assert row is not None
        row.opens_at = datetime.now(UTC) - timedelta(minutes=5)
        await session.commit()

    asked = _body(morning, opens_in_hours=20, preview=True)
    shown = await client.post(
        f"/api/teacher/assessments/{paper}/publications", headers=TEACHER, json=asked
    )
    done = await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json={**asked, "preview": False},
    )

    assert shown.status_code == 200
    assert done.status_code == 200
    # Cùng một kết luận và **cùng một câu**: hộp xác nhận không được nói một đằng rồi biên
    # bản nói một nẻo.
    assert shown.json()["classes"][0]["published"] is False
    assert shown.json()["classes"][0]["reason"] == done.json()["classes"][0]["reason"]


def test_the_form_template_builds_exactly_the_sentence_the_function_builds() -> None:
    """Khuôn gửi cho biểu mẫu và câu BE dựng ra phải là **một** thứ.

    Biểu mẫu nay điền chỗ trống của khuôn bằng con số giáo viên đang gõ, thay vì hiện một
    câu `--:--` tải một lần lúc mở màn — câu ấy đứng ngay dưới mấy ô nhập, trông như sắp
    đổi theo, mà về cấu trúc thì không bao giờ đổi được.

    Cái giá của hướng ấy là phép cộng *giờ đóng + phút làm bài* tồn tại hai bản, một ở đây
    và một ở FE. Phép kiểm này ghim nửa còn lại: **chữ nghĩa** chỉ có một bản, và điền
    khuôn bằng tay phải ra đúng chuỗi mà hàm dựng ra. Lệch nhau là lúc một cách diễn đạt
    thứ hai vừa sinh ra, đúng thứ ADR-03 dành cả tài liệu để ngăn.
    """
    closes = datetime(2026, 9, 15, 18, 0, tzinfo=UTC)
    deadline = datetime(2026, 9, 15, 22, 0, tzinfo=UTC)

    assert PHASE_ONE.format(closes="18:00", last="18:15") == phase_one_note(closes, 15)
    assert PHASE_TWO.format(deadline="22:00", rate="5") == phase_two_note(deadline, 5)

    # Và chỗ trống cũng đi qua đúng khuôn ấy, nên biểu mẫu lúc chưa gõ gì vẫn là cùng câu.
    assert PHASE_ONE.format(closes="--:--", last="--:--") == phase_one_note()
    assert PHASE_TWO.format(deadline="--:--", rate="--") == phase_two_note()


@pytest.mark.asyncio
async def test_bieu_mau_cho_ba_loi_tu_choi_dung_day(stack) -> None:
    """Ba field lời từ chối phải nối đúng ba hằng, không nối chéo.

    Biểu mẫu phát hành nay nói TRƯỚC cú bấm rằng một cửa sổ thời gian không dùng được, và
    nó mượn chữ của BE để không sinh ra cách diễn đạt thứ hai (ADR-03). Nhưng việc mượn ấy
    đi qua ba dòng gán trong `TimingRules`, và **nối chéo chúng là một thay đổi xanh hết
    mọi lưới**: `check_the_form_fills_the_slots_the_wording_declares` kiểm tên hằng ở
    `publication_wording.py` và tên field mà FE đọc, nhưng không kiểm khúc nối giữa hai
    cái. Hệ quả: giáo viên gõ giờ mở vào quá khứ và màn hình nói *"giờ đóng phải sau giờ
    mở"* — một câu đúng ngữ pháp, sai hoàn toàn, và chỉ sai với người đang đọc nó.

    So với **hằng số**, không so ba câu với nhau: ba bản sao của cùng một lỗi vẫn bằng nhau.
    """
    client, maker = stack
    paper = await _approved(maker)

    answer = await client.get(f"/api/teacher/assessments/{paper}/publish-form", headers=TEACHER)
    assert answer.status_code == 200
    rules = answer.json()["rules"]

    assert rules["opens_in_the_past"] == FAULT_OPENS_IN_THE_PAST
    assert rules["closes_before_opens"] == FAULT_CLOSES_BEFORE_OPENS
    assert rules["phase_two_too_early"] == FAULT_PHASE_TWO_TOO_EARLY

    # Và ba câu phải khác nhau: nối cả ba vào cùng một hằng cũng là nối sai dây, mà ba
    # phép so ở trên không bắt được nếu hằng ấy trùng.
    assert (
        len(
            {rules["opens_in_the_past"], rules["closes_before_opens"], rules["phase_two_too_early"]}
        )
        == 3
    )


@pytest.mark.asyncio
async def test_the_form_says_the_undo_is_shut_before_the_teacher_presses_it(stack) -> None:
    """Biểu mẫu nói trước cú bấm, cùng khuôn với cách nó chặn một cửa sổ thời gian vô lý.

    Một nút bấm được rồi mới nhận 409 là một nút hứa một việc hệ thống **đã biết** là không
    làm được. Và đường ấy từng tệ hơn thế: `Panel` nuốt mất câu 409, nên cú bấm không làm gì
    và không nói gì — đo được trên trình duyệt thật ngày 06/10/2026.

    Khẳng định đáng giá nhất ở đây là cái cuối: câu của biểu mẫu và câu của lời từ chối phải
    **giống hệt nhau**, vì chúng là cùng một hàm. Hai bản cài đặt của một luật là hai luật, và
    cái lệch đầu tiên sẽ là một nút bấm được cho một việc không làm được.
    """
    client, maker = stack
    paper = await _approved(maker)
    morning = await _class_id(maker, "12A")

    await client.post(
        f"/api/teacher/assessments/{paper}/publications",
        headers=TEACHER,
        json=_body(morning),
    )

    # Trước giờ mở: còn lùi được, biểu mẫu im lặng.
    form = await client.get(f"/api/teacher/assessments/{paper}/publish-form", headers=TEACHER)
    assert form.json()["undo_blocked"] == ""

    # Đẩy giờ mở về quá khứ: học sinh đã có thể vào làm.
    async with maker() as session:
        row = await session.get(Publication, (paper, morning))
        assert row is not None
        row.opens_at = datetime.now(UTC) - timedelta(minutes=5)
        await session.commit()

    shut = await client.get(f"/api/teacher/assessments/{paper}/publish-form", headers=TEACHER)
    said = shut.json()["undo_blocked"]
    # Gọi tên lớp: "một lớp nào đó đã qua giờ mở" là lời từ chối không hành động theo được.
    assert "12A" in said
    assert RECALL_RULE in said

    refused = await client.post(f"/api/teacher/assessments/{paper}/unapprove", headers=TEACHER)
    assert refused.status_code == 409
    assert refused.json()["detail"] == said
