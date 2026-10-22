"""Lời dặn (brief) cho một câu soạn mới trong đề, hay một câu làm lại ở pha 2 (ADR-17)."""

from contracts import DraftQuestionRequested, RetryQuestionRequested


def draft_brief(request: DraftQuestionRequested) -> str:
    """Mô tả đúng một câu hỏi mà job này viết.

    Mọi thứ ở đây đến từ một brief BE đã lưu trước khi có job nào được đẩy vào
    queue, nên mọi câu trong bộ đề đều được viết theo cùng một bộ chỉ dẫn. Vị trí
    câu được đưa vào vì các job chạy độc lập và không thấy nhau: nói với một job
    rằng nó là câu thứ ba trong mười câu là sự phối hợp duy nhất có thể, và đó là
    một lời nhắc chứ không phải một bảo đảm -- BE kiểm tra trùng lặp lúc harvest.

    Args:
        request: Môn, lớp, phạm vi giáo viên giới hạn lại, mức độ khó họ yêu cầu, và
            đây là câu thứ mấy trong bộ đề.

    Returns:
        Brief.
    """
    lines = [
        f"Viết câu hỏi số {request.ordinal} trong bộ {request.of_total} câu.",
        f"Môn: {request.subject}. Lớp: {request.grade}.",
        f"Phạm vi giáo viên giới hạn: {request.topic_scope}",
    ]
    if request.difficulty:
        lines.append(f"Mức độ giáo viên yêu cầu: {request.difficulty}")
    if request.item_knowledge.strip():
        # ADR-29 (`draft-outline`): câu này đứng trên **một mục của dàn ý** giáo viên đã duyệt --
        # kiến thức, công thức và cách làm, đúng như giáo viên đã đọc. Hai câu chung một mục thì
        # được nói mình là câu thứ mấy, vì các job chạy song song và không thấy nhau.
        lines += ["", f"Kiến thức câu này kiểm: {request.item_knowledge}"]
        if request.item_formulas:
            lines.append("Công thức sẽ dùng: " + "; ".join(request.item_formulas))
        lines.append(f"Cách làm bài: {request.item_approach}")
        if request.item_parts > 1:
            lines.append(
                f"Mục này có {request.item_parts} câu; đây là câu thứ {request.item_part}. "
                "Cùng kiến thức nhưng khác cách hỏi hoặc số liệu với các câu kia của mục."
            )
        # *"Bám đúng … trên"* đứng ngay sau mục của câu này, trước mọi danh sách phải tránh: đứng
        # sau chúng thì *"trên"* trỏ vào kiến thức hay câu cũ phải tránh, như thể giáo viên đã
        # duyệt chúng (review code vòng 12, 13).
        lines.append(
            "Bám đúng kiến thức, công thức và cách làm trên: giáo viên đã duyệt chúng trước khi "
            "câu được soạn."
        )
        if request.other_items:
            lines.append("Các câu khác của đề lo những kiến thức sau, đừng hỏi sang:")
            lines += [f"  · {knowledge}" for knowledge in request.other_items]
        lines += _already_written(request)
        return "\n".join(lines)
    lines += [
        "",
        "Mỗi câu trong bộ phải hỏi một khía cạnh khác nhau của phạm vi trên.",
    ]
    # Cùng lý do với nhánh có dàn ý: *"phạm vi trên"* phải trỏ vào phạm vi, không vào các câu cũ.
    lines += _already_written(request)
    return "\n".join(lines)


def retry_brief(request: RetryQuestionRequested) -> str:
    """Mô tả câu hỏi mà một lượt chữa lỗi cần.

    ADR-17 nói rất cụ thể về chuyện một lượt làm lại dùng để làm gì: nó hỏi xem học
    sinh đã sửa được lỗi chưa, không hỏi xem em có nhớ đáp án hay không. Vì thế brief
    đòi cùng một hình dạng với nội dung khác, và gọi tên cái lỗi mà câu hỏi mới phải
    cho học sinh một cơ hội nữa để mắc lại.

    Args:
        request: Câu gốc, phương án đã chọn, đây là lượt thứ mấy.

    Returns:
        Brief.
    """
    origin = request.origin
    lines = [
        "Viết MỘT câu hỏi mới để kiểm tra lại đúng kiến thức của câu dưới đây.",
        "",
        f"Câu gốc: {origin.stem}",
    ]
    for option in origin.options:
        mark = " (đáp án đúng)" if option.is_correct else ""
        lines.append(f"  {option.label}. {option.text}{mark}")
    lines.append(f"Mục tiêu học tập: {origin.learning_objective}")

    if request.wrong_option_label:
        lines.append(f"Học sinh đã chọn {request.wrong_option_label}.")
    if request.error_label:
        lines.append(f"Lỗi của em là: {request.error_label}.")

    lines += [
        "",
        "Yêu cầu:",
        "- Cùng DẠNG và cùng cách làm với câu gốc, nhưng số liệu và ngữ cảnh phải KHÁC.",
        "- Độ khó tương đương, không dễ hơn.",
        "- Phải có một phương án nhiễu ứng với đúng lỗi trên, để biết em đã sửa được chưa.",
    ]
    if request.previous_stems:
        lines.append("- KHÔNG được trùng bất kỳ đề nào sau đây:")
        lines += [f"  · {stem}" for stem in request.previous_stems]

    return "\n".join(lines)


def _already_written(request: DraftQuestionRequested) -> list[str]:
    """Các câu đã có trong đề, để model không viết lại đúng bài ấy. Hàm thuần.

    Thử tay 17/10/2026 (plan `backlog-tier-1`, case 02): ô 4 bị BE trả về ba lần vì gần trùng câu 3,
    và cả ba lần model viết lại đúng $\\frac{x}{12}=\\frac{5}{8}$, chỉ đổi lời dẫn. `banned_stems`
    tới AGENT mà chỉ dùng để so trùng nguyên văn **sau** khi viết; model không được thấy chúng, nên
    lần thử lại không biết phải tránh bài nào.

    Args:
        request: Job soạn câu; `banned_stems` là các câu đã có lúc job được đẩy đi.

    Returns:
        Các dòng thêm vào brief; rỗng khi đề chưa có câu nào.
    """
    # Mọi câu, không cắt: câu đã gây trùng có thể nằm ở bất kỳ đâu trong đề (một ô soạn thêm trùng
    # câu 1), nên cắt mười câu đầu hay mười câu cuối đều bỏ sót được đúng nó (review code vòng 12,
    # 13). Đề có trần 50 câu, nên danh sách dài nhất là 50 dòng: thay một câu trong đề đầy, câu
    # đang bị thay vẫn còn trong đề (review code vòng 14; xem Tier 2 câu 23 của backlog).
    written = [stem for stem in request.banned_stems if stem.strip()]
    if not written:
        return []
    return [
        "",
        "Đề đã có những câu dưới đây. Không viết lại bài nào trong số này -- cùng biểu thức, cùng "
        "số liệu mà đổi lời dẫn vẫn là trùng; dùng biểu thức và số liệu khác:",
        *(f"  · {stem}" for stem in written),
    ]
