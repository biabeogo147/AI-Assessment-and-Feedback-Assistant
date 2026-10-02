"""Hợp đồng message dùng chung giữa BE và AGENT.

Ba họ message sống ở đây. Nhóm authoring chở luồng hai pha cốt lõi: BE nhờ AGENT soạn câu hỏi, soạn
câu hỏi của một vòng củng cố, và đi một lượt trong cuộc hội thoại gia sư.

`teacher_chat` chở một lượt suy nghĩ cho khung chat của giáo viên, nơi công việc không được định
trước. Câu trả lời của nó là một *proposal* -- BE sở hữu vòng lặp và thực hiện từng bước -- và đó là
thứ giữ quyền hạn cùng cổng phát hành của ADR-05 ở đúng phía tường có database và có danh tính.

`GradingRequested` và `GradingCompleted` là cặp chấm điểm cũ. Chúng là **legacy**: ADR-20 chuyển
việc chấm trắc nghiệm vào BE, nên không gì trong luồng cốt lõi enqueue chúng nữa. Chúng ở lại tới
khi Teacher Review Queue (UC-05) được thiết kế và nói được nó thật sự cần gì. Đừng thêm field vào
chúng.
"""

from contracts.authoring import (
    EXPLAIN_TURN_TASK,
    GENERATE_RETRY_QUESTION_TASK,
    WRITE_DRAFT_QUESTION_TASK,
    ChatTurn,
    DraftQuestionCompleted,
    DraftQuestionRequested,
    ExplainTurnCompleted,
    ExplainTurnRequested,
    GeneratedOption,
    GeneratedQuestion,
    RetryQuestionCompleted,
    RetryQuestionRequested,
    SolutionMethod,
)
from contracts.enums import ReviewReason
from contracts.messages import (
    GRADE_SUBMISSION_TASK,
    SCHEMA_VERSION,
    GradingCompleted,
    GradingRequested,
)
from contracts.teacher_chat import (
    NAME_CONVERSATION_TASK,
    PROPOSE_NEXT_STEP_TASK,
    ConversationNameCompleted,
    ConversationNameRequested,
    NextStepCompleted,
    NextStepRequested,
    ToolSpec,
    TurnRecord,
)

__all__ = [
    "EXPLAIN_TURN_TASK",
    "GENERATE_RETRY_QUESTION_TASK",
    "GRADE_SUBMISSION_TASK",
    "NAME_CONVERSATION_TASK",
    "PROPOSE_NEXT_STEP_TASK",
    "SCHEMA_VERSION",
    "WRITE_DRAFT_QUESTION_TASK",
    "ChatTurn",
    "ConversationNameCompleted",
    "ConversationNameRequested",
    "DraftQuestionCompleted",
    "DraftQuestionRequested",
    "ExplainTurnCompleted",
    "ExplainTurnRequested",
    "GeneratedOption",
    "GeneratedQuestion",
    "GradingCompleted",
    "GradingRequested",
    "NextStepCompleted",
    "NextStepRequested",
    "ReviewReason",
    "RetryQuestionCompleted",
    "RetryQuestionRequested",
    "SolutionMethod",
    "ToolSpec",
    "TurnRecord",
]
