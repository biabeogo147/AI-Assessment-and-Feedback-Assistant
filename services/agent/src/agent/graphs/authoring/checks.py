"""Tự QC hình dạng một câu vừa viết: lời phàn nàn đưa lại cho model ở lần thử kế.

BE vẫn kiểm lại mọi thứ tới tay nó; check ở đây chỉ tiết kiệm một vòng đi về."""

from contracts import GeneratedQuestion


def faults(question: GeneratedQuestion, banned: frozenset[str]) -> list[str]:
    """Liệt kê mọi thứ sai trong một lần thử, bằng lời model làm được gì với nó.

    Args:
        question: Thứ model đã viết.
        banned: Các stem nó không được lặp lại.

    Returns:
        Một lời phàn nàn cho mỗi lỗi, rỗng khi không có gì để phàn nàn.
    """
    faults = []

    correct = [option for option in question.options if option.is_correct]
    if len(correct) != 1:
        faults.append(f"Phải có đúng một phương án đúng, bạn đánh dấu {len(correct)} phương án.")

    unlabelled = [
        option.label
        for option in question.options
        if not option.is_correct and not option.error_label
    ]
    if unlabelled:
        faults.append(f"Các phương án sai {unlabelled} chưa có error_label.")

    if len(question.methods) < 2:
        faults.append(f"Cần ít nhất hai cách giải, bạn viết {len(question.methods)}.")

    if normalise(question.stem) in banned:
        faults.append("Đề này trùng với một đề đã dùng. Phải là câu khác, cùng dạng.")

    return faults


def normalise(stem: str) -> str:
    """Gộp khoảng trắng lại để hai stem được so sánh theo từ ngữ của chúng.

    Chỉ một bản cài đặt: `handlers` import hàm này chứ không giữ bản riêng. Hai hàm
    buộc phải khớp nhau, nằm trong hai file, là một lần lệch nhau đã hẹn trước ngày
    -- và ở đây hai bên sẽ lệch nhau về chuyện một câu hỏi có lặp lại câu học sinh
    đã gặp hay không.

    Args:
        stem: Một stem câu hỏi.

    Returns:
        Stem đó với mọi chuỗi khoảng trắng liền nhau rút về một dấu cách.
    """
    return " ".join(stem.split())
