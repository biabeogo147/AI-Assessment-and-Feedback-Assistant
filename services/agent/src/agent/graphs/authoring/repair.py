"""Sửa đầu ra structured output trước khi kiểm: dấu gạch chéo bộ giải mã JSON nuốt, mục kiến
thức dài quá cột."""

import re

from agent.latex_escapes import restore_latex_escapes
from contracts import GeneratedQuestion

# Cột `questions.learning_objective` và `bank_questions.learning_objective` là `String(160)`
# (`schema/models.py`). Thử tay 17/10/2026 (`kriky-writes-every-word`): Haiku 5.5 chép cả mục dàn ý
# vào đây, 168 ký tự, và `harvest` của BE gãy cả lượt -- các câu còn lại treo `pending`. Không ai
# đọc chữ này trên màn (form sửa không có ô cho nó), nên cắt gọn ở đây rẻ hơn mọi lần hỏi lại model.
_MOST_OBJECTIVE = 160

# Hai gạch chéo trở lên liền nhau rồi một chữ cái: `\\Rightarrow` trong chữ đã giải mã.
_DOUBLED = re.compile(r"\\{2,}(?=[A-Za-z])")


def unmangled(question: GeneratedQuestion) -> GeneratedQuestion:
    r"""Trả lại dấu gạch chéo mà bộ giải mã JSON đã nuốt của mọi chữ trong một câu hỏi.

    **Đây là chỗ duy nhất việc này được làm, và nó nằm ở đây chứ không ở `contracts` vì
    một lý do đo được.** `be/teacher_routes.py` dựng lại chính `GeneratedQuestion` để
    kiểm tra đường PATCH của giáo viên; một validator đặt ở tầng contract sẽ sửa luôn
    chữ **giáo viên tự gõ** -- thứ không ai nhờ, và là một bề mặt đoán mò đặt đúng vào
    cổng người của ADR-05. Hỏng hóc sinh ra ở ranh giới structured-output, nên nó được
    chữa ở đúng ranh giới ấy.

    Chạy **trước** `_check`, nên mọi lời phàn nàn gửi lại cho model nói về chữ thật nó
    viết, không nói về chữ đã bị JSON cắt xén.

    Args:
        question: Thứ model vừa viết, ngay sau khi qua bộ giải mã JSON.

    Returns:
        Một bản mới với mọi field chữ đã dựng lại. `GeneratedQuestion` là `frozen=True`.
    """
    return question.model_copy(
        update={
            "stem": restore_latex_escapes(question.stem),
            # `learning_objective` dễ bị quên vì giáo viên không nhìn thấy nó, và chính vì
            # thế nó là field **cần** nhất ở đây: form sửa không có ô nào cho nó, nên nếu
            # hỏng thì không ai sửa được bằng tay. Nó đi vào báo cáo (ADR-17).
            # Và nó phải vừa cột của nó (`_MOST_OBJECTIVE`).
            "learning_objective": _clipped(
                _single_backslashed(restore_latex_escapes(question.learning_objective))
            ),
            "options": tuple(
                option.model_copy(
                    update={
                        "text": restore_latex_escapes(option.text),
                        "error_label": (
                            None
                            if option.error_label is None
                            else restore_latex_escapes(option.error_label)
                        ),
                    }
                )
                for option in question.options
            ),
            "methods": tuple(
                method.model_copy(
                    update={
                        "title": restore_latex_escapes(method.title),
                        "body": restore_latex_escapes(method.body),
                    }
                )
                for method in question.methods
            ),
        }
    )


def _single_backslashed(text: str) -> str:
    r"""Gộp `\\` model **tự viết đôi** trước một tên lệnh thành một `\`. Hàm thuần.

    Khác `restore_latex_escapes`: hàm ấy trả lại gạch chéo JSON đã nuốt, còn đây là gạch chéo
    thừa. Model chép mục dàn ý vào `learning_objective` và đôi khi thoát gạch chéo hai lần, nên chữ
    lưu là `$P \\Rightarrow Q$`. KaTeX đọc `\\` là xuống dòng, và hộp ngân hàng dựng thành
    *"P RightarrowQ"* (backlog, 22/10/2026).

    Không so với `LATEX_COMMANDS`: bảng ấy chỉ giữ những lệnh mở đầu bằng một chữ JSON nuốt được
    (`b`, `f`, `n`, `r`, `t`), còn lỗi này rơi vào `\cup`, `\Rightarrow`. Trong một nhãn một dòng,
    `\\` liền trước một chữ cái không bao giờ là xuống dòng có chủ ý, nên mọi tên lệnh đều gộp.

    Chỉ dùng cho `learning_objective`. Đề bài và lời giải có thể có ma trận hay hệ phương trình
    dùng `\\` thật, nên không đi qua đây.

    Args:
        text: Mục kiến thức đã dựng lại gạch chéo bị nuốt.

    Returns:
        Chữ với mọi `\\<chữ cái>` thành `\<chữ cái>`.
    """
    return _DOUBLED.sub(lambda _: "\\", text)


def _clipped(text: str) -> str:
    """Chữ vừa cột `learning_objective`: cắt ở ranh giới từ, kèm `…`. Hàm thuần."""
    text = text.strip()
    if len(text) <= _MOST_OBJECTIVE:
        return text
    head = text[: _MOST_OBJECTIVE - 1]
    cut = head.rsplit(" ", 1)[0] if " " in head else head
    return cut.rstrip(" ,;:.") + "…"


def parsed(answer: object) -> tuple[GeneratedQuestion | None, str]:
    """Câu hỏi đọc được từ một lần gọi model, và lỗi giải mã nếu không đọc được. Hàm thuần.

    `include_raw=True` trả một dict `{raw, parsed, parsing_error}`; một model giả trong test có
    thể trả thẳng câu hỏi.
    """
    if isinstance(answer, dict):
        error = answer.get("parsing_error")
        return answer.get("parsed"), "" if error is None else str(error)
    return answer if isinstance(answer, GeneratedQuestion) else None, ""
