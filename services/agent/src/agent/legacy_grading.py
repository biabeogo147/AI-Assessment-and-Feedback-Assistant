"""Đường chấm bài từ trước ADR-20, được giữ sống và giữ riêng.

ADR-20 chuyển việc chấm trắc nghiệm vào BE, nơi đáp án được lưu và nơi một phép so
sánh không cần một vòng đi về qua queue. Không có gì trong luồng chính gọi module
này. Nó còn sống vì một lý do: Teacher Review Queue (UC-05) vẫn chưa được thiết kế,
và ba invariant trong `AGENTS.md` đang được canh bởi những test chạy qua đoạn code
này. Xoá nó là âm thầm cho mấy cái canh đó về hưu.

Nó nằm trong module riêng để không ai đọc `handlers.py` rồi kết luận rằng AGENT vẫn
còn chấm bài.
"""

import logging

from contracts import GradingCompleted, GradingRequested

logger = logging.getLogger(__name__)

# Đáp án tạm, có từ thời BE chưa giữ đáp án nào.
_CORRECT_OPTION_SUFFIX = "a"

# Ngắn hơn độ dài này thì phần giải thích bị coi là quá mỏng để xét cách lập luận.
_MIN_EXPLANATION_CHARS = 15


def grade(request: GradingRequested) -> GradingCompleted:
    """Chấm một bài nộp và báo lại những gì quan sát được.

    Args:
        request: Bài nộp cần chấm.

    Returns:
        Bằng chứng cho bài nộp này. Không bao giờ là một quyết định định tuyến --
        chính tính chất đó là lý do hàm này vẫn còn nằm dưới test.

    Side effects:
        Log một dòng cho mỗi bài nộp đã chấm.
    """
    is_correct = request.selected_option_id.endswith(_CORRECT_OPTION_SUFFIX)
    explanation = (request.student_explanation or "").strip()

    has_sufficient_evidence = True
    conflict = False

    if request.student_explanation is None:
        confidence = 0.55
        feedback = "Chua co phan giai thich nen he thong chi danh gia duoc dap an."
    elif not explanation:
        confidence = 0.30
        has_sufficient_evidence = False
        feedback = "Phan giai thich de trong nen chua du can cu de danh gia."
    elif is_correct and len(explanation) < _MIN_EXPLANATION_CHARS:
        confidence = 0.60
        conflict = True
        feedback = "Dap an dung nhung phan giai thich chua the hien duoc cach lam."
    elif is_correct:
        confidence = 0.92
        feedback = "Dap an dung va cach lam hop ly."
    else:
        confidence = 0.88
        feedback = "Dap an chua dung. Xem lai buoc quy dong mau so."

    result = GradingCompleted(
        submission_id=request.submission_id,
        score=1.0 if is_correct else 0.0,
        confidence=confidence,
        misconception_code=None if is_correct else f"mis-{request.selected_option_id}",
        feedback_text=feedback,
        answer_explanation_conflict=conflict,
        has_sufficient_evidence=has_sufficient_evidence,
    )

    logger.info(
        "graded submission=%s score=%.1f confidence=%.2f",
        result.submission_id,
        result.score,
        result.confidence,
    )
    return result


async def grade_submission(ctx: dict, payload: dict) -> dict:
    """Điểm vào arq cho task chấm bài cũ.

    Args:
        ctx: Context job của arq. Không dùng; arq truyền nó theo vị trí.
        payload: Một GradingRequested đã serialise.

    Returns:
        Một GradingCompleted đã serialise.

    Side effects:
        Log lại rằng một đường đã bị thay thế vừa chạy.
    """
    request = GradingRequested.model_validate(payload)
    logger.warning("legacy grading used for %s; ADR-20 moved grading to BE", request.submission_id)
    return grade(request).model_dump(mode="json")
