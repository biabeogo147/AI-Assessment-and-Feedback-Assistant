"""Những message đi qua lại giữa BE và AGENT.

Module này chỉ là dữ liệu. Nó không giữ luật tính điểm, không giữ ngưỡng, không giữ quyết định định
tuyến nào, vì cả hai service đều import nó và bất cứ thứ gì đặt ở đây sẽ thành hành vi dùng chung mà
không service nào sở hữu.
"""

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

# Tên task của arq. Nó ở đây để BE enqueue việc bằng chuỗi và không bao giờ
# cần import package AGENT -- ranh giới đứng được ngay lúc thiết kế, không chỉ
# lúc chạy lint.
GRADE_SUBMISSION_TASK = "grade_submission"


class GradingRequested(BaseModel):
    """Việc BE gửi cho AGENT, ứng với một câu trả lời đã nộp.

    Chở đủ mọi thứ AGENT cần để chấm mà không phải đọc database nào, và đó chính là thứ cho phép
    AGENT không giữ credential database.

    `learning_objective` có mặt trước khi có ai dùng tới nó: Adaptive Practice (Workflow 5) sẽ cần
    nó để sinh một biến thể của cùng mục tiêu, và thêm sau thì phải version hoá hợp đồng.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    submission_id: str
    assessment_id: str
    question_id: str
    student_id: str
    selected_option_id: str
    student_explanation: str | None = None
    learning_objective: str


class GradingCompleted(BaseModel):
    """Bằng chứng AGENT sinh ra cho một bài đã chấm.

    Có chủ ý **không** chứa field `needs_teacher_review`. AGENT báo lại thứ nó quan sát được; BE áp
    ngưỡng và quyết định định tuyến. Đặt quyết định đó ở đây là chuyển cổng teacher-in-the-loop vào
    bên trong service AI, đúng điều project-overview.md loại bỏ.

    Hai cờ boolean ứng với những điều kiện review của Workflow 4 mà riêng confidence không diễn đạt
    được: một câu trả lời đúng trong khi lập luận thì không, và một trường hợp AGENT có quá ít căn
    cứ để dựa vào.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    submission_id: str
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    misconception_code: str | None = None
    feedback_text: str
    answer_explanation_conflict: bool = False
    has_sufficient_evidence: bool = True
