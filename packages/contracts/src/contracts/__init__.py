"""Hợp đồng message dùng chung giữa BE và AGENT và `services/document`.

Ba họ message sống ở đây. Nhóm authoring chở luồng hai pha cốt lõi: BE nhờ AGENT soạn câu hỏi, soạn
câu hỏi của một vòng củng cố, và đi một lượt trong cuộc hội thoại gia sư.

`teacher_chat` chở một lượt suy nghĩ cho khung chat của giáo viên, nơi công việc không được định
trước. Câu trả lời của nó là một *proposal* -- BE sở hữu vòng lặp và thực hiện từng bước -- và đó là
thứ giữ quyền hạn cùng cổng phát hành của ADR-05 ở đúng phía tường có database và có danh tính.

`documents` chở vòng xử lý tài liệu, và nó là họ duy nhất **không** đi tới một model: BE giao
một tệp cho `services/document` mở ra đọc, rồi nhận lại một phán quyết cùng số trang. Hai chiều,
hai task, và không mũi HTTP nào giữa hai service.
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
from contracts.documents import (
    DOCUMENT_PROBED_TASK,
    PROBE_DOCUMENT_TASK,
    DocumentProbed,
    DocumentProbeRequested,
    DocumentState,
    documents_channel,
)
from contracts.teacher_chat import (
    NAME_CONVERSATION_TASK,
    PROPOSE_NEXT_STEP_TASK,
    REPORT_PLAN_TASK,
    ConversationNameCompleted,
    ConversationNameRequested,
    NextStepCompleted,
    NextStepRequested,
    PlanReportCompleted,
    PlanReportRequested,
    PlanStep,
    StepOutcome,
    ToolSpec,
    TurnRecord,
)

__all__ = [
    "DOCUMENT_PROBED_TASK",
    "EXPLAIN_TURN_TASK",
    "GENERATE_RETRY_QUESTION_TASK",
    "NAME_CONVERSATION_TASK",
    "PROBE_DOCUMENT_TASK",
    "PROPOSE_NEXT_STEP_TASK",
    "WRITE_DRAFT_QUESTION_TASK",
    "ChatTurn",
    "ConversationNameCompleted",
    "ConversationNameRequested",
    "DocumentProbeRequested",
    "DocumentProbed",
    "DocumentState",
    "DraftQuestionCompleted",
    "DraftQuestionRequested",
    "ExplainTurnCompleted",
    "ExplainTurnRequested",
    "GeneratedOption",
    "GeneratedQuestion",
    "PlanReportCompleted",
    "PlanReportRequested",
    "PlanStep",
    "REPORT_PLAN_TASK",
    "StepOutcome",
    "NextStepCompleted",
    "NextStepRequested",
    "RetryQuestionCompleted",
    "RetryQuestionRequested",
    "SolutionMethod",
    "ToolSpec",
    "TurnRecord",
    "documents_channel",
]
