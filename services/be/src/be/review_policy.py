"""Định tuyến vào Teacher Review Queue.

Module này là cổng teacher-in-the-loop. Nó nằm ở BE có chủ đích:
business-workflows.md tách bước hệ thống tạo ra kết quả khỏi bước hệ thống quyết
định rằng một Teacher phải xem kết quả đó, và project-overview.md yêu cầu bước
thứ hai phải nằm ngoài service AI.

AGENT báo cáo bằng chứng. Không có gì ở đây chạy bên trong AGENT.
"""

from pydantic import BaseModel

from contracts import GradingCompleted, ReviewReason


class ReviewDecision(BaseModel):
    """Kết quả của việc áp review policy lên một bài làm đã chấm.

    Attributes:
        needs_teacher_review: Bài làm có vào Teacher Review Queue hay không.
        reason: Control point nào đã kích hoạt, hoặc None khi không cần ai xem lại.
    """

    needs_teacher_review: bool
    reason: ReviewReason | None = None


def decide_review(result: GradingCompleted, confidence_threshold: float) -> ReviewDecision:
    """Quyết định một bài làm đã chấm có cần một Teacher xem lại hay không.

    Hiện thực ba trong bốn control point của business-workflows.md Workflow 4.
    Cái thứ tư, ReviewReason.ANOMALY, muốn phát hiện thì phải có lịch sử của học
    sinh, nên chưa với tới được cho đến khi bài làm được lưu xuống; nó vẫn ở
    trong enum để sau này thêm vào không phải đổi contract.

    Các điều kiện được xét từ cụ thể nhất trở xuống: một câu trả lời đúng nhưng
    đi kèm lập luận sai thì nói cho Teacher nhiều hơn là một điểm confidence chỉ
    đơn thuần thấp, nên nó thắng khi cả hai cùng đúng.

    Args:
        result: Bằng chứng AGENT sinh ra cho một bài làm.
        confidence_threshold: Mức confidence mà từ đó trở xuống là phải có Teacher
            xem lại. Phép so sánh lấy cả dấu bằng, để một threshold bằng 0.0 vẫn
            đưa đi xem lại một kết quả mà model không hề tự tin chút nào.

    Returns:
        Một ReviewDecision nêu tên điều kiện đã kích hoạt, hoặc một
        ReviewDecision với needs_teacher_review bằng False khi không điều kiện
        nào đúng.

    Side effects:
        Không có. Hành động theo quyết định này là việc của caller.
    """
    if result.answer_explanation_conflict:
        return ReviewDecision(
            needs_teacher_review=True,
            reason=ReviewReason.ANSWER_EXPLANATION_CONFLICT,
        )

    if not result.has_sufficient_evidence:
        return ReviewDecision(
            needs_teacher_review=True,
            reason=ReviewReason.INSUFFICIENT_EVIDENCE,
        )

    if result.confidence <= confidence_threshold:
        return ReviewDecision(
            needs_teacher_review=True,
            reason=ReviewReason.LOW_CONFIDENCE,
        )

    return ReviewDecision(needs_teacher_review=False)
