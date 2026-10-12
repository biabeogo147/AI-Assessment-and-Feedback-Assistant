"""Thước đo bộ chọn skill: test của **thước** và của **bộ nhãn**, chạy được không cần Jev."""

import json
from pathlib import Path

from agent import skills
from skill_bench.run import score

_CASES = Path(__file__).resolve().parents[1] / "skill_bench" / "cases.json"


def test_a_missed_case_is_named_and_counts_against_recall() -> None:
    expected = {"a": {"soan-de"}, "b": {"soan-de"}, "c": set()}
    yes = {"a": {"soan-de": 0.9}, "b": {"soan-de": 0.1}, "c": {"soan-de": 0.6}}

    (only,) = score(expected, yes, 0.5)

    assert (only.recall, only.precision, only.missed) == (0.5, 0.5, ("b",))


def test_a_lower_threshold_loads_more() -> None:
    expected = {"a": {"soan-de"}}
    yes = {"a": {"soan-de": 0.25}}

    assert score(expected, yes, 0.3)[0].recall == 0.0
    assert score(expected, yes, 0.2)[0].recall == 1.0


def test_every_case_names_real_skills_and_ends_on_the_teacher() -> None:
    """Một nhãn trỏ tới skill không tồn tại thì recall của nó không bao giờ đo được."""
    cases = json.loads(_CASES.read_text(encoding="utf-8"))
    specialised = {skill.name for skill in skills.every()} - {skills.GENERAL}

    assert len({case["id"] for case in cases}) == len(cases)
    for case in cases:
        assert set(case["expect"]) <= specialised, case["id"]
        assert case["history"][-1][0] == "teacher", case["id"]
        assert {speaker for speaker, _ in case["history"]} <= {"teacher", "assistant"}
    # Mọi skill chuyên biệt, và skill bao quát, đều có ca của mình.
    for name in specialised:
        assert any(name in case["expect"] for case in cases), name
    assert any(not case["expect"] for case in cases)
