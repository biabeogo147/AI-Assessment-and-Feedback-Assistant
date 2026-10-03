r"""Giáo viên sửa được chữ của một câu, và cái lưới không nới ra cho họ.

Nút *Sửa* đã nằm trên panel từ lâu **không có `onClick`** — một nút chết. Đây là đường nó
nối vào, và câu hỏi đáng giá nhất của đợt này không phải *"sửa được không"* mà là *"một câu
sửa tay có đi qua đúng cái lưới mà một câu model viết phải đi qua không"*. Hai bản kiểm của
cùng một luật là hai thứ chờ lệch nhau, và bản lỏng hơn sẽ là bản người ta đi qua.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.db import bind_sessions, prepare_schema
from be.models import (
    Answer,
    AnswerOption,
    Assessment,
    AssessmentState,
    Attempt,
    Method,
    Question,
    Student,
    Teacher,
)
from be.seed import seed_if_empty
from be.teacher_routes import router as teacher_router

TEACHER = {"X-Actor": "teacher:GV-001"}
STRANGER = {"X-Actor": "teacher:GV-002"}


@pytest_asyncio.fixture
async def stack():
    """Một đề còn mở, có đúng một câu đủ chuẩn ADR-18."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as session:
        await seed_if_empty(session)
        session.add(Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002"))
        mine = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
        paper = Assessment(
            teacher_id=mine.id,
            title="Đề đang soạn",
            subject="Toán",
            grade="12",
            state=AssessmentState.HAS_QUESTIONS,
            created_at=datetime.now(UTC),
        )
        session.add(paper)
        await session.flush()
        question = Question(
            assessment_id=paper.id,
            order_index=1,
            stem="Đạo hàm của y = x² là gì?",
            learning_objective="đạo hàm",
        )
        session.add(question)
        await session.flush()
        for label, text, right in (("A", "2x", True), ("B", "x", False), ("C", "x²", False)):
            session.add(
                AnswerOption(
                    question_id=question.id,
                    label=label,
                    text=text,
                    is_correct=right,
                    error_label=None if right else f"lỗi {label}",
                )
            )
        for index, title in enumerate(("Cách 1", "Cách 2")):
            session.add(Method(question_id=question.id, order_index=index, title=title, body="..."))
        await session.commit()
        ids = (paper.id, question.id)

    app = FastAPI()
    app.include_router(teacher_router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker, ids

    await engine.dispose()
    db_module._SESSION_MAKER = None


def _body(**over) -> dict:
    """Một câu hỏi hợp lệ, để mỗi test chỉ hỏng đúng thứ nó muốn hỏng."""
    payload = {
        "stem": "Đạo hàm của $y = x^2$ là gì?",
        "learning_objective": "đạo hàm",
        "options": [
            {"label": "A", "text": "$2x$", "is_correct": True, "error_label": None},
            {"label": "B", "text": "$x$", "is_correct": False, "error_label": "quên hệ số"},
            {"label": "C", "text": "$x^2$", "is_correct": False, "error_label": "không đạo hàm"},
        ],
        "methods": [
            {"title": "Cách 1", "body": "Dùng công thức $(x^n)' = nx^{n-1}$."},
            {"title": "Cách 2", "body": "Tính giới hạn của tỉ sai phân."},
        ],
    }
    payload.update(over)
    return payload


@pytest.mark.asyncio
async def test_a_question_in_an_open_paper_can_be_rewritten(stack) -> None:
    """Đường đi hạnh phúc, và nó trả về đúng hình dạng panel đang vẽ."""
    http, maker, (paper, question) = stack

    answer = await http.patch(
        f"/api/teacher/assessments/{paper}/questions/{question}", json=_body(), headers=TEACHER
    )

    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["stem"] == "Đạo hàm của $y = x^2$ là gì?"
    assert [one["label"] for one in body["options"]] == ["A", "B", "C"]
    assert body["options"][1]["error_label"] == "quên hệ số"

    async with maker() as session:
        stored = await session.scalar(select(Question).where(Question.id == question))
        kept = list(
            await session.scalars(select(AnswerOption).where(AnswerOption.question_id == question))
        )
    assert stored.stem == "Đạo hàm của $y = x^2$ là gì?"
    # Thay cả bộ, không để lại hàng mồ côi nào.
    assert len(kept) == 3


@pytest.mark.asyncio
async def test_a_question_in_an_approved_paper_is_locked(stack) -> None:
    """ADR-01: duyệt xong là nội dung khoá, và chính cái khoá đó làm việc duyệt có nghĩa."""
    http, maker, (paper, question) = stack
    async with maker() as session:
        row = await session.get(Assessment, paper)
        row.state = AssessmentState.APPROVED
        await session.commit()

    answer = await http.patch(
        f"/api/teacher/assessments/{paper}/questions/{question}", json=_body(), headers=TEACHER
    )

    assert answer.status_code == 409
    assert "Hoàn tác" in answer.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("over", "why"),
    [
        # Hai phương án đúng: ADR-18 đòi đúng một.
        (
            {
                "options": [
                    {"label": "A", "text": "$2x$", "is_correct": True},
                    {"label": "B", "text": "$x$", "is_correct": True},
                ]
            },
            "exactly one correct",
        ),
        # Một phương án nhiễu không có nhãn lỗi.
        (
            {
                "options": [
                    {"label": "A", "text": "$2x$", "is_correct": True},
                    {"label": "B", "text": "$x$", "is_correct": False},
                ]
            },
            "error label",
        ),
        # Một lời giải: ADR-18 đòi hơn một.
        ({"methods": [{"title": "Cách 1", "body": "..."}]}, "worked solution"),
        # Toán nằm ngoài cặp `$` — đúng cái lưới của Pha 5.
        ({"stem": r"Tính \int_0^1 x\,dx"}, "not delimited"),
    ],
)
async def test_a_hand_edit_goes_through_the_same_net(stack, over, why) -> None:
    """Cùng một `validate_question`, không phải một bản kiểm thứ hai viết riêng.

    Ca cuối là ca đáng kể nhất: luật *toán trong cặp `$`* sinh ra cho câu model viết, và một
    câu giáo viên gõ tay cũng phải theo — nếu không thì đường sửa trở thành cửa sau đưa công
    thức không dựng hình được vào đúng cái đề mà luật ấy đang bảo vệ.
    """
    http, _, (paper, question) = stack

    answer = await http.patch(
        f"/api/teacher/assessments/{paper}/questions/{question}",
        json=_body(**over),
        headers=TEACHER,
    )

    assert answer.status_code == 422, answer.text
    assert why in answer.json()["detail"]


@pytest.mark.asyncio
async def test_one_teacher_cannot_rewrite_anothers_question(stack) -> None:
    """Đề của người khác đọc ra y hệt một đề không tồn tại (ADR-22)."""
    http, _, (paper, question) = stack

    answer = await http.patch(
        f"/api/teacher/assessments/{paper}/questions/{question}",
        json=_body(),
        headers=STRANGER,
    )

    assert answer.status_code == 404


@pytest.mark.asyncio
async def test_a_question_from_another_paper_is_absent(stack) -> None:
    """Id câu đúng nhưng không thuộc đề ấy thì cũng là không tìm thấy."""
    http, _, (paper, _) = stack

    answer = await http.patch(
        f"/api/teacher/assessments/{paper}/questions/khong-co-that",
        json=_body(),
        headers=TEACHER,
    )

    assert answer.status_code == 404


@pytest.mark.asyncio
async def test_a_question_someone_already_answered_cannot_be_rewritten(stack) -> None:
    """Sửa một câu đã có người làm sẽ làm hỏng bài của họ.

    `AnswerOption.id` là `new_id()`, nên thay cả bộ phương án sinh id mới kể cả khi giáo
    viên chỉ đổi một dấu phẩy — và mọi `Answer.option_id` của câu ấy thành mồ côi. SQLite
    im lặng trả 200; Postgres nổ `ForeignKeyViolation` thành một 500 không có chữ tiếng
    Việt nào.

    Ca này hôm nay chưa tới được qua giao diện, vì ADR-02 chỉ cho thu hồi trước giờ mở.
    Nhưng luật ấy đứng ở **một file khác**, nên phép kiểm phải ở ngay chỗ có thể vỡ.
    """
    http, maker, (paper, question) = stack
    async with maker() as session:
        option = await session.scalar(
            select(AnswerOption).where(AnswerOption.question_id == question)
        )
        student = await session.scalar(select(Student))
        attempt = Attempt(
            assessment_id=paper,
            student_id=student.id,
            class_id=student.class_id,
            started_at=datetime.now(UTC),
            ends_at=datetime.now(UTC),
        )
        session.add(attempt)
        await session.flush()
        session.add(
            Answer(
                attempt_id=attempt.id,
                question_id=question,
                option_id=option.id,
                saved_at=datetime.now(UTC),
            )
        )
        await session.commit()

    answer = await http.patch(
        f"/api/teacher/assessments/{paper}/questions/{question}", json=_body(), headers=TEACHER
    )

    assert answer.status_code == 409, answer.text
    assert "lượt trả lời" in answer.json()["detail"]

    async with maker() as session:
        kept = await session.scalar(
            select(func.count())
            .select_from(AnswerOption)
            .where(AnswerOption.question_id == question)
        )
    assert kept == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("over", "why"),
    [
        # Hai phương án cùng nhãn: `options` có `UniqueConstraint(question_id, label)`, nên
        # không chặn ở đây thì nó ra **500** chứ không ra một lời từ chối đọc được.
        (
            {
                "options": [
                    {"label": "A", "text": "$2x$", "is_correct": True},
                    {"label": "A", "text": "$x$", "is_correct": False, "error_label": "lỗi"},
                ]
            },
            "duplicate option labels",
        ),
        # Một phương án duy nhất đi lọt lưới cũ, vì "mọi distractor có nhãn lỗi" đúng một
        # cách rỗng khi không có distractor nào.
        (
            {"options": [{"label": "A", "text": "$2x$", "is_correct": True}]},
            "more than one option",
        ),
        # Nhãn lỗi **được hiện trên màn hình**, nên nó phải qua cùng cái lưới toán.
        (
            {
                "options": [
                    {"label": "A", "text": "$2x$", "is_correct": True},
                    {
                        "label": "B",
                        "text": "$x$",
                        "is_correct": False,
                        "error_label": r"quên hệ số \frac{1}{2}",
                    },
                ]
            },
            "not delimited",
        ),
    ],
)
async def test_three_holes_the_old_net_let_through(stack, over, why) -> None:
    """Ba lỗ đo được, hai trong đó ra 500 chứ không ra một câu từ chối."""
    http, _, (paper, question) = stack

    answer = await http.patch(
        f"/api/teacher/assessments/{paper}/questions/{question}",
        json=_body(**over),
        headers=TEACHER,
    )

    assert answer.status_code == 422, answer.text
    assert why in answer.json()["detail"]


@pytest.mark.asyncio
async def test_a_label_on_the_correct_option_is_dropped(stack) -> None:
    """`error_label` null ở đúng một dòng mỗi câu: dòng của phương án đúng (`models.py`).

    Đây là nơi **duy nhất** thi hành luật ấy, và nó không có lưới nào — một đột biến xoá
    nhánh `if one.is_correct` sống sót qua cả bộ test.
    """
    http, maker, (paper, question) = stack
    payload = _body()
    payload["options"][0]["error_label"] = "một nhãn gắn nhầm vào đáp án đúng"

    answer = await http.patch(
        f"/api/teacher/assessments/{paper}/questions/{question}", json=payload, headers=TEACHER
    )

    assert answer.status_code == 200, answer.text
    assert answer.json()["options"][0]["error_label"] is None


@pytest.mark.asyncio
async def test_the_order_the_teacher_typed_is_the_order_stored(stack) -> None:
    """Thứ tự lời giải giữ nguyên. Không giữ thì `sorted(key=order_index)` thành tuỳ tiện."""
    http, maker, (paper, question) = stack
    payload = _body()
    payload["methods"] = [
        {"title": "Zeta", "body": "cách sau"},
        {"title": "Alpha", "body": "cách trước"},
    ]

    answer = await http.patch(
        f"/api/teacher/assessments/{paper}/questions/{question}", json=payload, headers=TEACHER
    )

    assert answer.status_code == 200, answer.text
    assert [one["title"] for one in answer.json()["methods"]] == ["Zeta", "Alpha"]
