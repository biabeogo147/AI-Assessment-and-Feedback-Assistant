"""Các nút của một câu hỏi lại: lựa chọn nào thật, cần ít nhất bao nhiêu."""

import re
import unicodedata

from contracts import NextStepCompleted, NextStepRequested

# Chữ của lối "Khác" mà thẻ hỏi lại tự vẽ (FE, người dùng chốt 13/10/2026): model viết nó vào
# `choices` thì không phải một lựa chọn (`answers`). Cùng chữ với `teacher_chat.OTHER_CHOICE` bên
# BE và `OTHER` trong `Chat.tsx` -- ba nơi không import nhau, một test giữ chúng khớp.
_OTHER = "Khác"


def answers(choices: tuple[str, ...], question: str) -> tuple[str, ...]:
    """Những lựa chọn thật sự là một câu trả lời để bấm, gộp trùng.

    Ba thứ trông như lựa chọn mà không phải, đều đo được ở ca thiếu cả bốn mục
    (`unbiased-model-text` T3):

    - kết bằng "?" -- một câu hỏi (*"Môn học là gì?"*, run-41);
    - không chữ số nào và nằm nguyên trong chính câu hỏi -- tên một mục mà câu hỏi vừa kể
      (*"Môn học"*, *"Khối lớp"* cho câu *"cho mình biết môn học, khối lớp…"*: 15/30 lượt, run-52 và
      run-53). Có chữ số thì giữ: *"12A"*, *"15 câu"* là giá trị, dù câu hỏi có nhắc tới chúng;
    - "Khác" -- hệ thống tự có lối ấy (FE vẽ "Khác…" để giáo viên tự ghi), nên model viết nó không
      làm đủ ba (review T3: 58/158 câu hỏi có nó).

    Args:
        choices: `choices` model trả về.
        question: `text` của câu hỏi.

    Returns:
        Các lựa chọn còn lại, theo thứ tự, không trùng.
    """
    asked = " ".join(question.casefold().split())
    kept: dict[str, str] = {}
    for one in choices:
        text = one.strip()
        folded = " ".join(text.casefold().split())
        if not text or text.endswith("?") or folded == _OTHER.casefold():
            continue
        if not any(char.isdigit() for char in text) and folded in asked:
            continue
        kept.setdefault(folded, text)
    return tuple(kept.values())


def row_names(request: NextStepRequested) -> set[str]:
    """Tên các dòng (`candidates`) của kết quả tool gần nhất kể từ plan gần nhất, gộp khoảng trắng,
    không phân biệt hoa thường. Hàm thuần."""
    for turn in reversed(request.history):
        if turn.kind == "plan":
            break
        if turn.kind == "tool_result":
            listed = turn.tool_result.get("candidates")
            if isinstance(listed, list):
                names = set()
                for one in listed:
                    if isinstance(one, dict):
                        for key in ("name", "label"):
                            if one.get(key):
                                names.add(" ".join(str(one[key]).split()).casefold())
                        # Chữ trên nút BE dựng cho một lớp (`teacher_chat._option`): model chép
                        # đúng nhãn ấy thì câu vẫn là câu về dòng (review code pha 5).
                        if one.get("name") and isinstance(one.get("student_count"), int):
                            button = f"{one['name']} ({one['student_count']} học sinh)"
                            names.add(" ".join(button.split()).casefold())
                return names
    return set()


# Câu hỏi xin **tên mới** của một lớp sắp tạo: *"Bạn muốn đặt tên lớp là gì?"*, *"Lớp (học) mới tên
# là gì?"*, *"đặt tên khác cho lớp mới"*, *"tạo lớp tên gì?"*. Tên ấy giáo viên tự đặt, không có giá
# trị nào để bày thành nút (`tao-lop-chua-ten`, run-119). Ba dạng, đều gắn **tên** với **lớp
# mới/sắp tạo**: *"cho mình tên lớp cần xem"* hỏi về một lớp có sẵn -- vẫn cần nút, lần hỏi lại đẩy
# model gọi `list_class`; *"đặt tên cho đề"* là câu thừa model từng hỏi, vẫn phải hỏi lại (review
# pha 1 và pha 2, plan `tier-1`).
_ASKS_A_NEW_NAME = re.compile(
    r"\bđặt\s+tên\s+(?:\S+\s+){0,2}?(?:cho\s+)?lớp\b"
    r"|\btên\s+(?:\S+\s+){0,3}?lớp(?:\s+học)?\s+mới\b"
    r"|\blớp(?:\s+học)?\s+mới\s+(?:sẽ\s+)?(?:có\s+)?tên\b"
    r"|\btạo\s+lớp\s+(?:có\s+)?tên\b",
    re.IGNORECASE,
)


def asks_a_new_name(asked: str) -> bool:
    """Câu hỏi có xin một tên mới không -- tên giáo viên tự gõ, không nút nào thật. Hàm thuần."""
    return bool(_ASKS_A_NEW_NAME.search(unicodedata.normalize("NFC", asked)))


def choices_wanted(request: NextStepRequested, asked: str = "") -> int:
    """Một câu hỏi lại lượt này cần ít nhất bao nhiêu lựa chọn.

    Ba, theo luật người dùng chốt -- trừ khi số ba không đúng:

    - Câu hỏi xin tên mới (`asks_a_new_name`): tên của một lớp sắp tạo, giáo viên tự gõ vào ô
      *Khác…*; đòi nút là mời model bịa tên, và mỗi lần đòi tốn một lần hỏi lại model (Tier 1,
      12/11/2026). Xét **trước** `candidates`: một danh sách lớp vừa tra ở lượt trước không làm câu
      hỏi tên lớp mới thành câu hỏi về một dòng (review pha 1).
    - Kết quả tool gần nhất có `candidates` ít hơn ba dòng: câu hỏi về một dòng thì chỉ có bấy nhiêu
      lựa chọn **thật**, và đòi ba là mời model bịa dòng thứ ba. Gần nhất tính từ plan gần nhất,
      **qua** các câu của giáo viên (review T3, `unbiased-model-text`): câu hỏi về hai lớp kéo sang
      lượt sau khi giáo viên gõ một tên khác, và lượt ấy không gọi lại tool -- đòi ba ở đó là ép
      model bịa lớp.

    Args:
        request: Lượt đang hỏi.
        asked: Chữ của câu hỏi -- `text`, hay `label` và `text` của một câu trong lượt nhiều câu.

    Returns:
        Số lựa chọn tối thiểu, có thể là 0.
    """
    if asks_a_new_name(asked):
        return 0
    for turn in reversed(request.history):
        if turn.kind == "plan":
            break
        if turn.kind == "tool_result":
            listed = turn.tool_result.get("candidates")
            if isinstance(listed, list):
                return min(3, len(listed))
    return 3


def choices_in(step: NextStepCompleted) -> int:
    """Tổng số lựa chọn một lượt hỏi lại bày ra, một câu hay nhiều câu (ADR-32). Hàm thuần."""
    if step.questions:
        return sum(len(one.choices) for one in step.questions)
    return len(step.choices)
