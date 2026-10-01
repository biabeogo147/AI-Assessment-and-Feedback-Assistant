"""What the authoring handlers must keep true when a real model replaces them.

Not one assertion here reads a sentence the mock writes. Every one checks a
property the swap must preserve: the shape ADR-18 requires, the difference
ADR-17 requires between rounds, and the absence of any verdict.
"""

import pytest

from agent.handlers import draft_question, explain_turn, retry_question
from contracts import (
    ChatTurn,
    DraftQuestionRequested,
    ExplainTurnRequested,
    GeneratedOption,
    GeneratedQuestion,
    RetryQuestionRequested,
    SolutionMethod,
)

_ORIGIN = GeneratedQuestion(
    stem="Cho hàm số y = x³ − 3x. Hàm số đồng biến trên khoảng nào?",
    options=(
        GeneratedOption(label="A", text="Khoảng (−∞; −1)", is_correct=True),
        GeneratedOption(label="B", text="Khoảng (−1; 1)", error_label="đọc ngược khoảng"),
        GeneratedOption(label="C", text="Khoảng (0; 2)", error_label="chỉ thử một điểm"),
        GeneratedOption(label="D", text="Khoảng (−2; 0)", error_label="khoảng lẫn hai chiều"),
    ),
    methods=(
        SolutionMethod(title="Xét dấu đạo hàm", body="..."),
        SolutionMethod(title="Thử giá trị", body="..."),
    ),
    learning_objective="Tính đơn điệu của hàm bậc ba",
)


def _assert_adr_18(question: GeneratedQuestion) -> None:
    """Assert the three rules ADR-18 puts on any generated question."""
    correct = [option for option in question.options if option.is_correct]
    assert len(correct) == 1, "exactly one option may be correct"
    assert all(option.error_label for option in question.options if not option.is_correct), (
        "every distractor carries the mistake it stands for"
    )
    assert len(question.methods) >= 2, "a question needs more than one worked solution"


def test_every_question_of_a_draft_satisfies_the_authoring_rules() -> None:
    """One job writes one question now, so the set is checked one at a time."""
    for ordinal in range(1, 5):
        result = draft_question(
            DraftQuestionRequested(
                request_id="r1",
                subject="Toán",
                grade="12",
                topic_scope="chương 1",
                ordinal=ordinal,
                of_total=4,
            )
        )
        _assert_adr_18(result.question)


def test_a_draft_reports_no_verdict() -> None:
    """AGENT writes questions; whether they may be published is not its call."""
    payload = draft_question(
        DraftQuestionRequested(
            request_id="r1",
            subject="Toán",
            grade="12",
            topic_scope="chương 1",
            ordinal=1,
            of_total=1,
        )
    ).model_dump()
    for forbidden in ("score", "confidence", "needs_teacher_review", "approved", "difficulty"):
        assert forbidden not in payload


def test_a_retry_question_differs_from_the_question_it_replaces() -> None:
    """ADR-17: a retry keeps the shape, not the content -- otherwise recall passes."""
    result = retry_question(
        RetryQuestionRequested(
            request_id="r1", origin=_ORIGIN, wrong_option_label="B", round_index=1
        )
    )
    assert result.question.stem != _ORIGIN.stem
    _assert_adr_18(result.question)


def test_later_rounds_do_not_repeat_an_earlier_stem() -> None:
    """Round two must not be round one again, or memory beats understanding."""
    first = retry_question(
        RetryQuestionRequested(
            request_id="r1", origin=_ORIGIN, wrong_option_label="B", round_index=1
        )
    ).question

    second = retry_question(
        RetryQuestionRequested(
            request_id="r2",
            origin=_ORIGIN,
            wrong_option_label="B",
            round_index=2,
            previous_stems=(first.stem,),
        )
    ).question

    assert second.stem != first.stem
    assert second.stem != _ORIGIN.stem
    _assert_adr_18(second)


def test_the_opening_turn_names_the_whole_paper() -> None:
    """The assistant covers the assessment, so its first words say so."""
    reply = explain_turn(
        ExplainTurnRequested(request_id="r1", questions=(_ORIGIN,), student_text="")
    )
    assert reply.text.startswith("Mình là trợ lý Kriky")


def test_an_answer_follows_the_authored_mistake_instead_of_guessing() -> None:
    """ADR-18 turned diagnosis into a lookup; the handler must read, not infer."""
    reply = explain_turn(
        ExplainTurnRequested(
            request_id="r1",
            questions=(_ORIGIN,),
            chosen_labels={_ORIGIN.stem: "B"},
            error_labels={_ORIGIN.stem: "đọc ngược khoảng"},
            history=(ChatTurn(role="assistant", text="chào em"),),
            student_text="câu 1 em chưa hiểu vì sao sai",
        )
    )
    assert "đọc ngược khoảng" in reply.text


def test_an_assistant_turn_carries_only_words() -> None:
    """No score, no round count, no "ready to move on" -- those belong to BE."""
    payload = explain_turn(
        ExplainTurnRequested(request_id="r1", questions=(_ORIGIN,), student_text="")
    ).model_dump()
    assert set(payload) == {"schema_version", "request_id", "text"}


@pytest.mark.parametrize(
    "payload",
    [
        RetryQuestionRequested(
            request_id="r1", origin=_ORIGIN, wrong_option_label="B", round_index=1
        ),
        ExplainTurnRequested(request_id="r1", questions=(_ORIGIN,), student_text=""),
    ],
)
def test_a_job_carries_its_own_content(payload) -> None:
    """AGENT holds no database credentials, so nothing may arrive as a bare id."""
    body = payload.model_dump()
    questions = [body["origin"]] if "origin" in body else body["questions"]
    for question in questions:
        assert question["stem"], "a job must carry the question text, not a question id"
        assert question["options"], "a job must carry the options, not an id to look them up"
