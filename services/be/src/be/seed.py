"""Dữ liệu demo, cố ý kể đúng câu chuyện mà file design kể.

Mười hai artboard phía học sinh đều cho thấy một đề duy nhất -- "Kiểm tra 15 phút —
Hàm số", sáu câu hỏi, lớp 12A, học sinh Nguyễn Minh Anh. Seed bất cứ thứ gì khác sẽ
có nghĩa là hệ thống đang chạy và bản design lệch nhau ngay từ cái nhìn đầu tiên, và
người review sẽ phải giữ hai bộ dữ liệu mẫu trong đầu mới phân biệt được một bug với
một chỗ khác biệt.

Chạy một lần: nếu đã có một lớp tồn tại thì hàm này không làm gì.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from schema.models import (
    AnswerOption,
    Assessment,
    AssessmentState,
    Method,
    Publication,
    Question,
    SchoolClass,
    Student,
    Teacher,
)

_MONOTONY = (
    ("Xét dấu đạo hàm", "Tính y′, giải y′ = 0, rồi lập bảng xét dấu trên từng khoảng."),
    (
        "Thử giá trị rồi kiểm lại",
        "Thử một điểm trong mỗi khoảng để đoán chiều, sau đó xét dấu trên cả khoảng — "
        "một điểm chỉ nói về chính điểm đó.",
    ),
)

# (stem, objective, [(label, text, is_correct, error_label)], [(title, body)])
_QUESTIONS = (
    (
        "Đạo hàm của y = x² + 3x là gì?",
        "Đạo hàm của đa thức",
        (
            ("A", "2x + 3", True, None),
            ("B", "x + 3", False, "quên nhân số mũ khi hạ bậc"),
            ("C", "2x", False, "bỏ sót đạo hàm của số hạng bậc nhất"),
            ("D", "x² + 3", False, "chỉ đạo hàm một số hạng"),
        ),
        (
            ("Công thức luỹ thừa", "(xⁿ)′ = n·xⁿ⁻¹, áp cho từng số hạng rồi cộng lại."),
            ("Kiểm bằng hệ số góc", "Tính hệ số góc tiếp tuyến tại một điểm và đối chiếu."),
        ),
    ),
    (
        "Hàm số y = 2x + 1 đồng biến trên khoảng nào?",
        "Tính đơn điệu của hàm bậc nhất",
        (
            ("A", "Khoảng (−∞; +∞)", True, None),
            ("B", "Khoảng (0; +∞)", False, "tưởng hàm bậc nhất chỉ tăng khi x dương"),
            ("C", "Khoảng (−∞; 0)", False, "đọc ngược chiều biến thiên"),
            ("D", "Không đồng biến ở đâu", False, "nhầm hệ số góc dương với hàm hằng"),
        ),
        (
            ("Hệ số góc", "y′ = 2 > 0 với mọi x, nên hàm đồng biến trên toàn trục số."),
            ("Đồ thị", "Đường thẳng có hệ số góc dương đi lên trên toàn miền xác định."),
        ),
    ),
    (
        "Giới hạn của (x² − 1)/(x − 1) khi x → 1 bằng bao nhiêu?",
        "Giới hạn dạng vô định",
        (
            ("A", "2", True, None),
            ("B", "0", False, "thay thẳng x = 1 vào tử rồi dừng"),
            ("C", "1", False, "rút gọn sai khi phân tích hiệu hai bình phương"),
            ("D", "Không tồn tại", False, "coi dạng 0/0 là không có giới hạn"),
        ),
        (
            ("Phân tích thành nhân tử", "(x² − 1) = (x − 1)(x + 1), rút gọn rồi thay x = 1."),
            ("Quy tắc L'Hôpital", "Đạo hàm tử và mẫu: 2x / 1, thay x = 1 được 2."),
        ),
    ),
    (
        "Cho hàm số y = x³ − 3x. Hàm số đồng biến trên khoảng nào?",
        "Tính đơn điệu của hàm bậc ba",
        (
            ("A", "Khoảng (−∞; −1)", True, None),
            ("B", "Khoảng (−1; 1)", False, "đọc ngược khoảng đồng biến và nghịch biến"),
            ("C", "Khoảng (0; 2)", False, "chỉ thử một điểm rồi suy ra cả khoảng"),
            ("D", "Khoảng (−2; 0)", False, "lấy khoảng chứa cả phần tăng lẫn phần giảm"),
        ),
        _MONOTONY,
    ),
    (
        "Đồ thị y = (2x − 1)/(x + 3) có tiệm cận ngang là đường nào?",
        "Tiệm cận của hàm phân thức",
        (
            ("A", "y = 2", True, None),
            ("B", "x = −3", False, "nhầm tiệm cận đứng với tiệm cận ngang"),
            ("C", "y = −1/3", False, "lấy tỉ số hai hằng số thay vì hai hệ số bậc cao nhất"),
            ("D", "y = 0", False, "áp quy tắc của trường hợp bậc tử nhỏ hơn bậc mẫu"),
        ),
        (
            ("Tỉ số hệ số bậc cao nhất", "Bậc tử bằng bậc mẫu nên tiệm cận ngang là 2/1 = 2."),
            ("Lấy giới hạn", "Cho x → ±∞, chia cả tử và mẫu cho x rồi lấy giới hạn."),
        ),
    ),
    (
        "Giá trị nhỏ nhất của y = x + 4/x trên (0; +∞) bằng bao nhiêu?",
        "Giá trị nhỏ nhất của hàm số trên một khoảng",
        (
            ("A", "4", True, None),
            ("B", "1", False, "lấy hệ số của x thay cho giá trị nhỏ nhất"),
            ("C", "2", False, "lấy giá trị của x tại điểm cực tiểu thay cho giá trị của y"),
            ("D", "0", False, "coi hàm giảm mãi nên không có giá trị nhỏ nhất dương"),
        ),
        (
            ("Đạo hàm", "y′ = 1 − 4/x² = 0 cho x = 2, thay lại được y(2) = 4."),
            ("Bất đẳng thức Cô-si", "x + 4/x ≥ 2√4 = 4 với x > 0, dấu bằng khi x = 2."),
        ),
    ),
)

_STUDENTS = (
    ("Nguyễn Minh Anh", "HS2026-1204"),
    ("Trần Gia Bảo", "HS2026-1205"),
    ("Lê Thu Hà", "HS2026-1206"),
)


async def seed_if_empty(session: AsyncSession) -> bool:
    """Tạo một lần lớp demo, danh sách lớp và đề đã phát hành.

    Args:
        session: Session của database để ghi qua.

    Returns:
        True khi dữ liệu đã được tạo, False khi database đã có một lớp sẵn và không có
        gì bị chạm tới.

    Side effects:
        Insert các dòng rồi commit.
    """
    existing = await session.scalar(select(func.count()).select_from(SchoolClass))
    if existing:
        return False

    now = datetime.now(UTC)

    teacher = Teacher(full_name="Cô Phạm Thu Lan", teacher_code="GV-001")
    session.add(teacher)
    # Flush trước khi tạo lớp, để lớp có một chủ sở hữu mà trỏ tới. Thứ tự ở đây quan
    # trọng theo cách mà trước đây nó không quan trọng: `teacher_id` không nullable, vì
    # một lớp không có chủ là một lớp mà không giáo viên nào bị chặn khỏi việc đọc
    # (ADR-13).
    await session.flush()

    school_class = SchoolClass(teacher_id=teacher.id, name="12A")
    session.add(school_class)
    await session.flush()

    for full_name, code in _STUDENTS:
        session.add(Student(class_id=school_class.id, full_name=full_name, student_code=code))

    assessment = Assessment(
        teacher_id=teacher.id,
        title="Kiểm tra 15 phút — Hàm số",
        subject="Toán",
        grade="12",
        state=AssessmentState.PUBLISHED,
        created_at=now,
    )
    session.add(assessment)
    await session.flush()

    for order, (stem, objective, options, methods) in enumerate(_QUESTIONS, start=1):
        question = Question(
            assessment_id=assessment.id,
            order_index=order,
            stem=stem,
            learning_objective=objective,
        )
        session.add(question)
        await session.flush()
        for label, text, is_correct, error_label in options:
            session.add(
                AnswerOption(
                    question_id=question.id,
                    label=label,
                    text=text,
                    is_correct=is_correct,
                    error_label=error_label,
                )
            )
        for index, (title, body) in enumerate(methods, start=1):
            session.add(Method(question_id=question.id, order_index=index, title=title, body=body))

    session.add(
        Publication(
            assessment_id=assessment.id,
            class_id=school_class.id,
            opens_at=now - timedelta(hours=1),
            closes_at=now + timedelta(hours=6),
            phase1_minutes=15,
            phase2_minutes_per_question=5,
            remediation_deadline=now + timedelta(hours=8),
            published_at=now - timedelta(hours=2),
        )
    )

    await session.commit()
    return True
