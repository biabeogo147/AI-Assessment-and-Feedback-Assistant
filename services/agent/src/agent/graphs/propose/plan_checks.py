"""Kiểm hình dạng một plan: tham số hỏng, thiếu tham số, soạn ngay sau lời xin sửa dàn ý."""

import re

from agent.graphs.propose.outline import _AGREES
from contracts import NextStepCompleted, NextStepRequested, PlanStep, TurnRecord

# Ký tự điều khiển, trừ tab và xuống dòng. Tham số plan không đi qua `_unmangled` -- chúng là giá
# trị, không phải chữ để dựng toán -- nên một ký tự như vậy là chữ hỏng, không phải LaTeX bị nuốt.
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _garbled(steps: tuple[PlanStep, ...]) -> str:
    """Bước đầu tiên có tham số mang ký tự điều khiển, gọi tên ra; rỗng khi không bước nào.

    Đo được ở `unbiased-model-text` T3: hai lượt trong ~1100 trả *"tỉ lệ th\\x13"*, *"tỉ lệ
    th\\x1c"* làm `topic_scope` (run-53, run-54; nguồn chưa rõ) -- chữ ấy thành tên đề giáo viên
    đọc. Hỏi lại model một lần như một plan thiếu tham số.

    Args:
        steps: Các bước model nêu.

    Returns:
        Một dòng cho log, hoặc chuỗi rỗng.
    """
    for index, step in enumerate(steps, start=1):
        for key, value in step.args.items():
            if _CONTROL.search(str(value)):
                return f"step {index} ({step.tool_name}) has a control character in {key}"
    return ""


# Lời xin sửa dàn ý: *"câu 2 đổi sang tự luận"*, *"thêm một câu hình học"*, *"oke nhưng câu 3 khó
# hơn"*. Lời đồng ý trọn câu (`_AGREES`) thì không phải.
_REVISES = re.compile(
    r"\b(?:đổi|sửa|thay|bỏ|thêm|bớt|chuyển|khó hơn|dễ hơn|nhưng|thay vì)\b", re.IGNORECASE
)


def _drafts_over_a_revision(step: NextStepCompleted, request: NextStepRequested) -> bool:
    """Plan có soạn câu, mà lời giáo viên sau dàn ý gần nhất là lời xin sửa. Hàm thuần."""
    if not any(one.tool_name in {"start_drafting", "replace_question"} for one in step.steps):
        return False
    after: list[TurnRecord] = []
    for turn in reversed(request.history):
        if turn.kind == "outline":
            break
        after.append(turn)
    else:
        return False
    said = [turn.text for turn in after if turn.kind == "teacher"]
    if not said or _AGREES.match(said[0]):
        return False
    return bool(_REVISES.search(_NO_CHANGE.sub(" ", said[0])))


# Lời **không** xin sửa: *"không cần sửa gì"*, *"ko đổi gì nữa"* -- bỏ đi trước khi tìm `_REVISES`,
# như `_NO_BOOK` với chữ *sách* (review code pha 5, plan `backlog-tier-1`).
#
# Chỉ khi động từ **đứng cuối ý**: *"không cần thêm câu hình học"* là lời xin bỏ một mục. Cuối ý là
# một trong ba hình dạng sau động từ (hay hai động từ liền nhau, *"sửa thêm"*):
#   - *gì/nữa/cả/hết/đâu* ngay sau động từ (*"không cần sửa gì nữa"*);
#   - một tiểu từ cuối câu thật, có thể kéo dài (*nhé, nha, nhen, nhaa, ạ*), *luôn/đi* đứng trước
#     cũng được (*"khỏi sửa luôn nha"*);
#   - chuỗi tiểu từ bất kỳ rồi hết câu hay một dấu câu (*"không cần sửa luôn cả"*, *"khỏi sửa đi"*).
# Sau hai hình dạng đầu, đuôi nhận thêm tiểu từ và một *thêm* cuối ý (`_TRAILING_MORE`).
# *luôn/đi* **giữa câu**, trước *cả/hết* rồi một chữ khác, là lời xin sửa (*"sao không bỏ luôn cả
# câu 3?"*). *"sao không …"* là lời gợi ý sửa, không phải lời phủ định. `\b` sau tiểu từ: *nha*
# không ăn đầu chữ *nhanh*.
#
# Chín vòng review (pha 5) liền ra ca biên mới, nên regex này đi cùng một bộ câu có nhãn
# (`tests/test_revision_words.py`): sửa regex là chạy lại cả bộ. Ca biên còn lại là Tier 2 câu 5.
_CHANGE_VERB = r"(?:thay\s+đổi|chỉnh\s+sửa|sửa|đổi|thay|thêm|bớt|bỏ)"
_END_PARTICLE = r"(?:nh[éeaá]+n?|ạ+)"
# *"gì thêm"* là *"gì nữa"*: *gì* mang theo *thêm* dù có chữ khác theo sau (*"không cần sửa gì thêm
# soạn đi"*), trừ khi sau *thêm* là tân ngữ -- *"gì thêm 1 câu"* là lời xin thêm câu (vòng 9).
# `?+` (possessive): *"gì thêm"* khớp được cả một tiểu từ lẫn *gì* + `_TRAILING_MORE`, và để
# regex thử cả hai thì một chuỗi *"luôn gì thêm gì thêm …"* backtrack theo hàm mũ -- 24 cặp đã mất
# 13 s, trong khi `said` cho tới 2 000 ký tự (review code vòng 10).
_INNER_PARTICLE = (
    r"(?:gì[iì]*(?:\s+thêm\b(?!\s+(?:\d|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|vài|mấy|câu|cho"
    r"|phần|bài)))?+"
    r"|nữa|cả|hết+|đâu)"
)
_LONG_PARTICLE = r"(?:luôn|đi)"
# *thêm* ở đuôi chỉ khi nó cũng là cuối ý (*"không chỉnh sửa gì thêm"*): theo sau là hết câu, dấu
# câu, hay một tiểu từ khác -- *"không cần sửa nhé thêm 1 câu"* là lời xin thêm câu (vòng 8).
_TRAILING_MORE = (
    rf"thêm(?=\s*(?:[,.!?;:)]|$)|\s+(?:{_END_PARTICLE}|{_INNER_PARTICLE}|{_LONG_PARTICLE})\b)"
)
_ANY_PARTICLE = rf"(?:{_END_PARTICLE}|{_INNER_PARTICLE}|{_LONG_PARTICLE}|{_TRAILING_MORE})"
_NO_CHANGE = re.compile(
    # *"sao không …"* là lời gợi ý sửa, trừ *"không sao không cần sửa"* (vòng 8).
    r"(?<!(?<!\bkhông\s)(?<!\bko\s)\bsao\s)"
    rf"\b(?:không|ko|k|hok|hông|khỏi|chẳng|chả)\s+(?:cần\s+|phải\s+)?{_CHANGE_VERB}"
    rf"(?:\s+{_CHANGE_VERB})?"
    rf"(?:(?:\s+{_INNER_PARTICLE}\b)+(?:\s+{_ANY_PARTICLE}\b)*"
    rf"|(?:\s+{_LONG_PARTICLE}\b)*(?:\s+{_END_PARTICLE}\b)+(?:\s+{_ANY_PARTICLE}\b)*"
    rf"|(?:\s+{_ANY_PARTICLE}\b)*(?=\s*(?:[,.!?;:)]|$)))"
    rf"|\bkhông\s+có\s+gì\s+(?:cần\s+|phải\s+)?{_CHANGE_VERB}\b",
    re.IGNORECASE,
)


def _lacking(steps: tuple[PlanStep, ...], request: NextStepRequested) -> str:
    """Bước đầu tiên thiếu một tham số bắt buộc, gọi tên ra; rỗng khi không bước nào thiếu.

    Luật của `vet_plan` bên BE -- tham số khai trong catalog, trừ `optional`, phải **có mặt** -- trừ
    đúng một chỗ BE tự lo: đoạn chat gắn một cuốn sách sẵn sàng thì `bind_book` điền `document_id`
    **trước** `vet_plan`, nên thiếu nó không phải lý do hỏi lại (review T2b, `unbiased-model-text`).
    `nodes` thì vẫn tính: `bind_book` chỉ điền nó khi `topic_scope` trùng đúng tên mục. Tool không
    có trong catalog thì để BE nói: đó là lời từ chối của nó.

    Args:
        steps: Các bước model nêu.
        request: Lượt đang hỏi -- catalog pha thực hiện, và chip của đoạn chat.

    Returns:
        Một dòng cho log, hoặc chuỗi rỗng.
    """
    attached = request.attached_document
    filled_by_be = {"document_id"} if attached is not None and attached.state == "ready" else set()
    specs = {spec.name: spec for spec in request.plannable}
    for index, step in enumerate(steps, start=1):
        spec = specs.get(step.tool_name)
        if spec is None:
            continue
        missing = set(spec.arguments) - set(step.args) - set(spec.optional) - filled_by_be
        if missing:
            return f"step {index} ({step.tool_name}) lacks {sorted(missing)}"
    return ""
