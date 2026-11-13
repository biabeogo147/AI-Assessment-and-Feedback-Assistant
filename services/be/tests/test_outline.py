"""`be/outline.py` (ADR-29, ADR-38): BE kiểm số câu và bài nguồn của dàn ý, không gì khác.

Dàn ý là lời Markdown của Kriky; BE không đọc nó. Hàm thuần, không database.
"""

import pytest

from be.outline import MOST_QUESTIONS_ASKED, stored, validate


def test_a_sound_outline_passes() -> None:
    assert validate(5, (), None) is None
    assert validate(3, (2, 4), {1, 2, 3, 4}) is None


@pytest.mark.parametrize("questions", [0, MOST_QUESTIONS_ASKED + 1])
def test_more_than_ten_questions_in_one_go_is_refused(questions: int) -> None:
    assert "mỗi lần chỉ soạn 1 đến 10 câu" in validate(questions, (), None)


def test_the_cap_can_be_lower_when_the_draft_is_nearly_full() -> None:
    assert validate(4, (), None, most=3) is not None
    assert validate(3, (), None, most=3) is None


def test_a_replacement_outline_is_one_question() -> None:
    assert (
        validate(2, (), None, most=1, replacing=True) == "dàn ý thay câu chỉ có 1 câu, không phải 2"
    )
    assert validate(1, (), None, most=1, replacing=True) is None


def test_more_questions_on_a_nearly_full_draft_are_not_told_they_replace_one() -> None:
    """Review pha 2: soạn thêm khi đề còn đúng một chỗ cũng có trần 1 -- lời từ chối nói số câu,
    không nói *thay câu*, để model không đổi sang việc khác."""
    assert validate(2, (), None, most=1) == "dàn ý có 2 câu; mỗi lần chỉ soạn 1 đến 1 câu"


def test_a_book_outline_must_say_which_lesson_and_only_real_ones() -> None:
    assert "outline_nodes" in validate(3, (), {1, 2})
    assert validate(3, (2, 9, 8), {1, 2}) == "dàn ý trỏ về node [8, 9] không có trong tài liệu"


def test_a_bookless_outline_points_at_no_lesson() -> None:
    assert validate(3, (2,), None) == "dàn ý trỏ về tài liệu, nhưng đề này không có tài liệu"


def test_what_is_stored_is_the_count_and_the_sources_not_the_words() -> None:
    kept = stored(4, (3, 2, 3), version=2, first=6, document_id="d1")

    assert kept == {"version": 2, "first": 6, "total": 4, "document_id": "d1", "nodes": [2, 3]}
