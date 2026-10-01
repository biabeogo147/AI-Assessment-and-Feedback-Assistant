"""Luật thời gian và điều kiện tham gia của phase 2.

Hai cái đồng hồ gặp nhau ở đây và chúng không khớp nhau, và đó chính là lý do
module này tồn tại. Phase 1 cho mỗi học sinh một khoảng thời gian riêng mà không
gì cắt ngang được (ADR-03). Phase 2 cho mỗi vòng một ngân sách thời gian tính từ
số câu hỏi còn đang mở, nằm trong một hạn tuyệt đối do giáo viên đặt -- và khi
hạn đến giữa vòng, vòng đó bị **dừng** (ADR-15).
"""

from datetime import datetime, timedelta


def round_budget_minutes(minutes_per_question: int, open_questions: int) -> int:
    """Tính một vòng được chạy bao lâu.

    Args:
        minutes_per_question: Con số giáo viên đặt lúc phát hành.
        open_questions: Số câu hỏi còn phải chữa, và con số này co lại qua từng vòng.

    Returns:
        Tổng số phút cho vòng đó.
    """
    return minutes_per_question * open_questions


def round_ends_at(now: datetime, budget_minutes: int, deadline: datetime) -> datetime:
    """Quyết định một vòng dừng lúc nào.

    Args:
        now: Giờ server lúc vòng bắt đầu.
        budget_minutes: Ngân sách thời gian lấy từ round_budget_minutes.
        deadline: Hạn của phase 2, đặt lúc phát hành.

    Returns:
        Mốc nào đến trước giữa lúc hết ngân sách và lúc đến hạn. Đây là chỗ "hết
        hạn thì lượt đang làm bị DỪNG" trở thành một con số thay vì một câu nói.
    """
    return min(now + timedelta(minutes=budget_minutes), deadline)


def will_be_cut(now: datetime, budget_minutes: int, deadline: datetime) -> bool:
    """Cho biết một vòng bắt đầu ngay lúc này có bị hạn cắt giữa đường không.

    BE trả lời câu này, không phải phía giao diện: so sánh hai mốc thời gian
    chính là luật của ADR-15, và nếu client làm phép so sánh đó thì client sở hữu
    luôn cái luật.

    Args:
        now: Giờ server.
        budget_minutes: Ngân sách thời gian vòng này sẽ được cấp.
        deadline: Hạn của phase 2.

    Returns:
        True khi ngân sách không vừa trước hạn, và đó là thứ chọn ra dạng có cảnh
        báo của cửa vào vòng.
    """
    return now + timedelta(minutes=budget_minutes) > deadline
