"""Luật tính điểm. BE sở hữu chúng; AGENT không bao giờ thấy chúng.

Chấm một câu trắc nghiệm chỉ là một phép so sánh, nên nó nằm ở đây chứ không nằm
sau một queue (ADR-20). Thang điểm ba mức và luật sàn là ADR-16: phase 1 đặt ra
mức thấp nhất mà một câu hỏi có thể kết thúc ở đó, và remediation chỉ được phép
kéo lên.
"""

from enum import StrEnum

# ADR-17 chặn remediation ở ba vòng mỗi câu hỏi.
MAX_ROUNDS_PER_QUESTION = 3

MARK_CORRECT = 1.0
MARK_REMEDIATED = 0.5
MARK_WRONG = 0.0


class MarkReason(StrEnum):
    """Vì sao một câu hỏi đứng ở mức điểm nó đang đứng.

    Là một enum chứ không phải một câu văn: chữ hiện ra khi hover khác nhau giữa
    trạng thái "còn đang mở" và "đã đóng" của phase 2, và ADR-16 giữ phần chữ đó
    ở phía giao diện. Gửi văn xuôi từ đây ra là đóng băng nó lại.
    """

    CORRECT_FIRST_TRY = "đúng-ngay"
    REMEDIATED = "chữa-được"
    NOT_YET_REMEDIATED = "chưa-chữa"
    ROUNDS_EXHAUSTED = "hết-vòng"


def mark_for_phase_one(is_correct: bool) -> tuple[float, MarkReason, bool]:
    """Tính điểm một câu hỏi ở cuối phase 1.

    Args:
        is_correct: Phương án được chọn có phải phương án đúng không.

    Returns:
        Điểm, lý do điểm đó đứng vững, và câu hỏi đã đóng hay chưa. Trả lời đúng
        thì đóng ngay; trả lời sai thì vẫn mở, vì phase 2 còn có thể kéo điểm lên.
    """
    if is_correct:
        return MARK_CORRECT, MarkReason.CORRECT_FIRST_TRY, True
    return MARK_WRONG, MarkReason.NOT_YET_REMEDIATED, False


def mark_after_round(is_correct: bool, rounds_used: int) -> tuple[float, MarkReason, bool]:
    """Tính điểm một câu hỏi sau khi một vòng remediation đã được nộp.

    Args:
        is_correct: Câu trả lời của vòng này có đúng không.
        rounds_used: Số vòng đã dùng cho câu hỏi này, tính cả vòng vừa nộp.

    Returns:
        Điểm, lý do điểm đó đứng vững, và câu hỏi đã đóng hay chưa. Chữa được thì
        đóng câu hỏi ở nửa điểm; hết vòng thì đóng ở không điểm; còn lại thì để
        mở cho một vòng nữa.
    """
    if is_correct:
        return MARK_REMEDIATED, MarkReason.REMEDIATED, True
    if rounds_used >= MAX_ROUNDS_PER_QUESTION:
        return MARK_WRONG, MarkReason.ROUNDS_EXHAUSTED, True
    return MARK_WRONG, MarkReason.NOT_YET_REMEDIATED, False


def total(marks: list[float]) -> float:
    """Cộng một danh sách điểm từng câu.

    Args:
        marks: Mỗi câu hỏi của đề một điểm.

    Returns:
        Tổng điểm, làm tròn một chữ số thập phân để 0.5 + 0.5 không hiện ra thành
        0.9999999999999999 trên bảng điểm.
    """
    return round(sum(marks), 1)
