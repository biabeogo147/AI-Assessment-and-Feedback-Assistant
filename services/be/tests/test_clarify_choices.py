"""Nút của một câu hỏi lại (plan 4c T3, hậu ký ADR-23).

Hai loại câu hỏi, hai nguồn nút: hỏi về một **dòng** (lớp, tài liệu, mục) thì nút là nhãn BE dựng,
phương án model viết chỉ sống khi khớp đúng một tên; hỏi về một **tham số** (số câu, khối) thì nút
là chữ model đề xuất. Không có "Khác": từ 13/10/2026 FE tự vẽ lối ấy -- bấm nó mở ô để giáo viên
ghi rõ, không gửi chữ "Khác" (người dùng chốt).
"""

from types import SimpleNamespace

from be.teacher_chat import OTHER_CHOICE, _choices, _named, _offered, _rows_in_play

_CLASSES = {
    "found": True,
    "more": 0,
    "candidates": [
        {"class_id": "a", "name": "12A", "student_count": 3},
        {"class_id": "b", "name": "12A1", "student_count": 40},
        {"class_id": "c", "name": "12B", "student_count": 1},
    ],
}
_CHAPTERS = {
    "found": True,
    "more": 0,
    "candidates": [
        {"node": 0, "label": "Chương I. ĐA THỨC (tr. 5–30)"},
        {"node": 7, "label": "Chương II. HẰNG ĐẲNG THỨC (tr. 31–50)"},
    ],
}


def _buttons(proposed: tuple[str, ...], result: dict | None = None) -> list[str]:
    offered, _ = _offered(result or {})
    return _choices(proposed, offered, _named(result or {}))


def test_a_question_about_a_parameter_carries_the_models_options() -> None:
    assert _buttons(("10 câu", "15 câu", "20 câu")) == ["10 câu", "15 câu", "20 câu"]


def test_the_models_options_are_tidied_not_trusted_blindly() -> None:
    """Gộp trùng (kể cả khác hoa thường), bỏ ô trống, bỏ "Khác" model tự viết, có trần."""
    proposed = (
        "10 câu",
        " 10  câu ",
        "10 CÂU",
        "",
        "khác",
        *(f"{n} câu" for n in range(11, 20)),
    )

    buttons = _buttons(proposed)

    assert buttons[0] == "10 câu"
    assert [one.casefold() for one in buttons].count("10 câu") == 1
    assert "" not in buttons
    assert OTHER_CHOICE.casefold() not in [one.casefold() for one in buttons]
    assert len(buttons) == 6


def test_a_question_about_classes_puts_the_models_picks_first() -> None:
    """Tên lớp model viết khớp đúng tên trong `candidates` thì thành nhãn BE, kèm sĩ số BE đếm."""
    buttons = _buttons(("12B", "12A1", "12A"), _CLASSES)

    assert buttons == ["12B (1 học sinh)", "12A1 (40 học sinh)", "12A (3 học sinh)"]


def test_a_class_the_model_made_up_never_reaches_a_button() -> None:
    """ADR-23: *"12A-1"* lệch tên thật một dấu gạch, *"12A (45 học sinh)"* sai sĩ số, *"11C"*
    không tồn tại. Không chữ nào khớp đúng một tên thì mọi nhãn BE, như trước T3."""
    buttons = _buttons(("12A-1", "12A (45 học sinh)", "11C"), _CLASSES)

    assert buttons == ["12A (3 học sinh)", "12A1 (40 học sinh)", "12B (1 học sinh)"]


def test_the_models_picks_never_hide_a_real_row() -> None:
    """Review T3: bản đầu bày đúng tập con model chọn -- năm lớp, model chọn ba, hai lớp thật biến
    mất mà `more_choices` không báo. ADR-23: *"trả về tất cả"*. Model chỉ đổi được thứ tự."""
    five = {
        "candidates": [
            {"class_id": name, "name": name, "student_count": 30}
            for name in ("12A", "12B", "12C", "12D", "12E")
        ]
    }

    buttons = _buttons(("12D", "12B", "11Z"), five)

    assert buttons[:2] == ["12D (30 học sinh)", "12B (30 học sinh)"]
    assert sorted(buttons) == sorted(_offered(five)[0])


def test_fewer_rows_than_three_ask_for_every_row_not_three() -> None:
    """Hai mục thì hai nút thật -- BE không bịa dòng cho đủ số."""
    buttons = _buttons(
        ("Chương II. HẰNG ĐẲNG THỨC (tr. 31–50)", "Chương I. ĐA THỨC (tr. 5–30)"), _CHAPTERS
    )

    assert buttons == [
        "Chương II. HẰNG ĐẲNG THỨC (tr. 31–50)",
        "Chương I. ĐA THỨC (tr. 5–30)",
    ]


def test_two_classes_with_one_name_cannot_be_picked_by_name() -> None:
    """Hai lớp cùng tên: chỉ sĩ số phân biệt được, nên tên trần không trỏ tới nút nào (ADR-23)."""
    twins = {
        "candidates": [
            {"class_id": "a", "name": "12A", "student_count": 3},
            {"class_id": "b", "name": "12A", "student_count": 40},
        ]
    }

    assert "12A" not in _named(twins)
    assert _named(twins)["12A (40 học sinh)"] == "12A (40 học sinh)"
    assert _buttons(("12A", "12A"), twins) == ["12A (3 học sinh)", "12A (40 học sinh)"]


def _turn(kind: str, **fields: object) -> SimpleNamespace:
    return SimpleNamespace(
        kind=kind, choices=fields.get("choices"), tool_result=fields.get("result")
    )


# Nút đã lưu của một đoạn chat **cũ**: trước 13/10/2026 BE nối "Khác" cuối mọi câu hỏi lại.
_ASKED_CLASS = [
    _turn("teacher"),
    _turn("tool_call"),
    _turn("tool_result", result=_CLASSES),
    _turn("assistant", choices=[*_offered(_CLASSES)[0], OTHER_CHOICE]),
]
# Cùng câu hỏi ấy, lưu sau ngày ấy: chỉ nhãn BE.
_ASKED_CLASS_NOW = [*_ASKED_CLASS[:3], _turn("assistant", choices=_offered(_CLASSES)[0])]


def test_a_question_about_rows_stays_open_after_other() -> None:
    """Review T3: lượt 1 hỏi lại bằng nhãn lớp, lượt 2 giáo viên bấm "Khác" và model hỏi tiếp mà
    không gọi tool. Câu hỏi vẫn là về các lớp ấy -- không thì chữ model viết thành nút."""
    assert _rows_in_play(_ASKED_CLASS, OTHER_CHOICE) == _CLASSES
    assert _rows_in_play(_ASKED_CLASS, "lớp chuyên") == _CLASSES
    # Lối "Khác" nay gửi câu giáo viên ghi, không gửi chữ "Khác" -- câu hỏi về dòng vẫn mở.
    assert _rows_in_play(_ASKED_CLASS_NOW, "lớp chuyên") == _CLASSES


def test_picking_a_row_closes_the_question() -> None:
    assert _rows_in_play(_ASKED_CLASS, "12A1 (40 học sinh)") == {}
    assert _rows_in_play(_ASKED_CLASS_NOW, "12A1 (40 học sinh)") == {}


def test_a_question_about_a_number_leaves_no_rows_in_play() -> None:
    """Câu hỏi lại trước là về số câu: nút của nó không phải nhãn của dòng nào."""
    stored = [*_ASKED_CLASS[:3], _turn("assistant", choices=["10 câu", "15 câu", OTHER_CHOICE])]

    assert _rows_in_play(stored, OTHER_CHOICE) == {}


def test_a_plain_answer_leaves_no_rows_in_play() -> None:
    """Lượt trước kết bằng một lời nói, không nút: không câu hỏi nào còn mở."""
    stored = [*_ASKED_CLASS[:3], _turn("assistant", choices=[])]

    assert _rows_in_play(stored, "soạn đề lớp 12A") == {}


def test_no_real_option_means_no_buttons_not_a_lone_other() -> None:
    """Không lựa chọn thật nào thì không nút nào -- FE không vẽ thẻ (review T3)."""
    assert _buttons(()) == []
    assert _buttons(("Khác", " ")) == []
