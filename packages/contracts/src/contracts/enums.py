"""Từ vựng dùng chung cho hợp đồng giữa BE và AGENT.

Cách đặt tên theo bảng thuật ngữ Phase 1 trong docs/overview/project-overview.md, để code và tài
liệu nghiệp vụ đọc đối chiếu được với nhau.
"""

from enum import StrEnum


class ReviewReason(StrEnum):
    """Vì sao một bài đã chấm bị đưa vào Teacher Review Queue.

    Bốn thành viên ứng với bốn chốt kiểm soát mà business-workflows.md Workflow 4 liệt kê.
    Confidence chỉ là một trong bốn, nên riêng một cờ boolean sẽ làm mất chính thông tin mà giáo
    viên cần.
    """

    LOW_CONFIDENCE = "low_confidence"
    ANSWER_EXPLANATION_CONFLICT = "answer_explanation_conflict"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ANOMALY = "anomaly"
