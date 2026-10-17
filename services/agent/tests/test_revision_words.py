"""Bộ câu có nhãn cho lời giáo viên ngay sau một dàn ý: *xin sửa* hay *không xin sửa*.

Plan `backlog-tier-1`, pha 5: bảy vòng review liền nhau đều ra một ca biên mới của `_NO_CHANGE` /
`_REVISES`, và mỗi lần sửa một câu lại làm hỏng một câu khác. Bộ này gom mọi câu các vòng ấy đã thử
-- sửa regex là chạy lại cả bộ, nên một lần sửa không còn âm thầm làm sai một câu cũ.

Chạy qua đúng đường code dùng (`_drafts_over_a_revision`), không gọi regex trơn. Câu mơ hồ thật,
hay đã biết còn lọt, nằm ở `OPEN` và không được canh: chúng là Tier 2 câu 5 (thay regex bằng nút
do BE dựng).
"""

import pytest

from agent.graphs.propose import _drafts_over_a_revision
from contracts import NextStepCompleted, NextStepRequested, PlanStep, TurnRecord

# Lời không xin sửa: plan soạn đi tiếp.
AGREES = (
    # *"không sao"* đứng trước không phải *"sao không …"* (vòng 8).
    "không sao không cần sửa đâu",
    "ko sao ko cần sửa",
    "không sao không cần sửa, soạn đi",
    "không cần sửa",
    "không cần sửa gì",
    "không cần sửa gì nữa",
    "không cần sửa gì nữa đâu",
    "không cần sửa nữa",
    "không cần sửa nữa đâu",
    "không cần sửa nữa nhé",
    "không cần sửa đâu",
    "không cần sửa đâu nhé",
    "không cần sửa nhé",
    "không cần sửa nha",
    "không cần sửa nha em",
    "không cần sửa ạ",
    "không cần sửa đâu ạ",
    "không cần sửa luôn",
    "không cần sửa luôn nhé",
    "không cần sửa luôn nha",
    "không cần sửa luôn ạ",
    "khỏi sửa luôn nha",
    "khỏi sửa luôn",
    "khỏi sửa nha",
    "khỏi sửa đi",
    "khỏi sửa đi nhé",
    "không sửa đi nhé",
    "ko cần sửa luôn nhé",
    "ko cần sửa nha",
    "ko sửa gì hết",
    "không đổi gì cả",
    "không thay đổi gì cả, soạn đi",
    "không chỉnh sửa gì thêm",
    "không cần chỉnh sửa gì thêm, soạn luôn",
    "không cần sửa thêm",
    "không cần sửa thêm gì",
    "không cần sửa thêm gì nữa",
    "không cần sửa thêm nhé",
    "không cần thêm bớt gì",
    "không cần thêm gì nữa",
    "không cần thêm nữa, soạn đi",
    "không cần bớt",
    "không sửa nữa, soạn luôn đi",
    "thôi không sửa nữa, soạn luôn",
    "được rồi không cần sửa",
    "oke không cần sửa, soạn đi em",
    "ok không sửa gì nhé, soạn đi",
    "ok rồi không đổi gì nữa đâu, soạn luôn",
    "không cần sửa gì đâu, soạn đi",
    "không cần đổi, soạn đi",
    "không phải sửa gì",
    "chẳng cần sửa gì",
    "chả cần sửa đâu",
    "hông cần sửa nha",
    "hok cần sửa đâu",
    "k cần sửa",
    "k cần sửa nhé",
    "không cần sửa luôn đi",
    "không cần sửa đi",
    "không cần sửa nhé, soạn đi",
    "không cần sửa nhé soạn đi",
    "không cần sửa nha soạn luôn",
    "không cần sửa đâu em soạn luôn đi",
    "không cần sửa nữa em ơi",
    "không cần sửa gì đâu em",
    "dàn ý ok, không cần sửa",
    "dàn ý ổn rồi không cần sửa gì",
    "không cần sửa nhen",
    "khỏi sửa nhen, soạn đi",
    "không cần sửa nhaa",
    "không cần sửa nhaaa soạn đi",
    "khỏi sửa nhee",
    "không cần sửa nhéee",
    "ko cần sửa ạạ",
    "không cần sửa gìi",
    "không cần sửa hếtt",
    "không đổi gì nha",
    "không cần sửa nha. soạn đi",
    "không cần sửa nhá",
    "không cần sửa nhé!",
    "không cần sửa đi luôn nhé",
    "không cần sửa luôn luôn nha",
    "không đổi đi nhé",
    "không cần bỏ luôn nhé",
    "không cần sửa luôn nhé em",
    "không cần sửa nhé luôn",
    "không cần sửa luôn cả",
    "không sửa luôn hết nha",
    "không cần sửa nhé :)",
    "không cần sửa nhé 😊",
    "không cần sửa thêm, soạn luôn",
    "không có gì cần sửa, soạn đi",
    "không cần thay đổi gì, soạn đi",
    "ok không đổi gì nữa, soạn luôn nhé",
    "không cần sửa đâu bạn",
    "được, không cần sửa đâu bạn",
    "ok không cần sửa luôn",
    "oke ko cần sửa ạ",
    "không cần sửa đâu, soạn đi",
    "ok không cần sửa nhé",
    "không cần sửa gì, soạn đi",
)

# Lời xin sửa: plan soạn bị giữ lại.
REVISES = (
    # Lời không xin sửa rồi xin thêm câu, không dấu phẩy (vòng 8).
    "không cần sửa nhé thêm 1 câu hình học",
    "không cần sửa ạ thêm 1 câu hình học",
    "không sửa gì cả thêm 2 câu nữa",
    "không cần đổi gì nhé thêm cho cô 1 câu",
    "câu 3 đổi sang tự luận",
    "sửa câu 2 thành dễ hơn",
    "thêm 2 câu hình học",
    "bớt 1 câu",
    "bỏ câu 4",
    "câu 3 khó hơn",
    "cho câu 1 dễ hơn nhé",
    "không cần thêm câu hình học",
    "không cần sửa câu 1 nhưng câu 3 khó hơn",
    "không sửa câu 1, đổi câu 3 sang tự luận",
    "không đổi câu 2, câu 3 thì khó hơn",
    "sao không đổi câu 3 sang tự luận",
    "sao không thêm câu hình học",
    "sao không sửa nhanh câu 3",
    "không cần sửa nhanh đâu, đổi câu 3 trước",
    "không cần sửa nhé nhưng câu 3 khó hơn",
    "không cần sửa ạ, thêm 1 câu hình học",
    "không cần sửa thêm câu hình học",
    "không cần sửa thêm, nhưng câu 3 khó hơn",
    "không cần thêm, đổi câu 3 sang tự luận",
    "không đổi luôn câu 3 à",
    "câu 2 đổi sang tự luận nhé",
    "oke nhưng câu 3 khó hơn",
    "sao không bỏ luôn cả câu 3?",
    "sao không thay luôn cả đề?",
    "sao không đổi luôn hết sang tự luận",
    "sao không bỏ luôn hết mấy câu hình học",
    "sao không thêm luôn đi",
    "sao không đổi luôn gì đó cho câu 3",
    "sao không sửa luôn đâu đó câu 2",
    "sao không bỏ cả câu 3?",
    "không cần sửa nhé,nhưng câu 3 khó hơn",
    "không cần sửa luôn nhé nhưng câu 3 khó hơn",
    "khỏi sửa luôn nha, câu 2 đổi sang tự luận",
    "không sửa đi nhé, thêm 1 câu",
    "sao không đổi đi nhé",
    "sao không thay luôn nhé câu 3",
    "sao không đổi luôn câu 3 sang tự luận?",
    "thêm một câu hình học",
    "không cần sửa, nhưng câu 3 khó hơn nhé",
    "sao không thêm luôn 1 câu hình học",
    "không bỏ luôn câu 5 đi à",
)

# Mơ hồ thật, hay đã biết còn lọt -- không canh (Tier 2 câu 5).
OPEN = (
    "không cần bỏ câu nào",
    "không đổi nhé câu 3 sang tự luận",
    "không thêm nha câu hình học",
    "không bỏ đâu câu 2 hay mà",
    "không cần sửa thêm 1 câu",
    "không sửa thêm câu nào",
    "không cần thay thêm câu",
    "không cần sửa luôn câu 3",
    "không cần sửa nhanh đâu",
)

_PLAN = NextStepCompleted(
    request_id="r1",
    kind="plan",
    text="Mình soạn.",
    steps=(
        PlanStep(
            tool_name="start_drafting",
            args={"assessment_id": "p1", "question_count": "2"},
            title="Soạn câu hỏi",
        ),
    ),
)


def _after_an_outline(said: str) -> NextStepRequested:
    return NextStepRequested(
        request_id="r1",
        history=(
            TurnRecord(kind="teacher", text="soạn 2 câu"),
            TurnRecord(kind="outline", text="Dàn ý", tool_result={"version": 1, "for": "new"}),
            TurnRecord(kind="teacher", text=said),
        ),
    )


@pytest.mark.parametrize("said", AGREES)
def test_a_teacher_who_asks_for_no_change_is_not_held_back(said: str) -> None:
    assert _drafts_over_a_revision(_PLAN, _after_an_outline(said)) is False


@pytest.mark.parametrize("said", REVISES)
def test_a_teacher_who_asks_for_a_change_holds_the_plan_back(said: str) -> None:
    assert _drafts_over_a_revision(_PLAN, _after_an_outline(said)) is True
