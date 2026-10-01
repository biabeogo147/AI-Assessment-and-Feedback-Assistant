"""Những gì các handler soạn nội dung phải giữ đúng khi một model thật thay chúng.

Không một assertion nào ở đây đọc một câu chữ mock viết ra. Mỗi assertion đều check một
tính chất mà việc thay thế phải bảo toàn: hình dạng ADR-18 đòi, sự khác biệt giữa các
lượt mà ADR-17 đòi, và sự vắng mặt của mọi phán xét.
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
    """Khẳng định ba luật ADR-18 đặt lên mọi câu hỏi được sinh ra."""
    correct = [option for option in question.options if option.is_correct]
    assert len(correct) == 1, "exactly one option may be correct"
    assert all(option.error_label for option in question.options if not option.is_correct), (
        "every distractor carries the mistake it stands for"
    )
    assert len(question.methods) >= 2, "a question needs more than one worked solution"


def test_every_question_of_a_draft_satisfies_the_authoring_rules() -> None:
    """Giờ một job viết một câu, nên cả bộ được check từng câu một."""
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
    """AGENT viết câu hỏi; chuyện chúng có được phát hành hay không không phải việc của nó."""
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
    """ADR-17: một lượt làm lại giữ hình dạng, không giữ nội dung -- không thì học thuộc là qua."""
    result = retry_question(
        RetryQuestionRequested(
            request_id="r1", origin=_ORIGIN, wrong_option_label="B", round_index=1
        )
    )
    assert result.question.stem != _ORIGIN.stem
    _assert_adr_18(result.question)


def test_later_rounds_do_not_repeat_an_earlier_stem() -> None:
    """Lượt hai không được là lượt một lần nữa, không thì trí nhớ thắng sự hiểu."""
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
    """Trợ lý bao cả bộ đề, nên những lời đầu tiên của nó nói ra điều đó."""
    reply = explain_turn(
        ExplainTurnRequested(request_id="r1", questions=(_ORIGIN,), student_text="")
    )
    assert reply.text.startswith("Mình là trợ lý Kriky")


def test_an_answer_follows_the_authored_mistake_instead_of_guessing() -> None:
    """ADR-18 biến việc chẩn đoán thành việc tra cứu; handler phải đọc, không được suy."""
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
    """Không điểm, không số lượt, không "đã sẵn sàng đi tiếp" -- những thứ đó thuộc về BE."""
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
    """AGENT không giữ credential database nào, nên không gì được tới dưới dạng một id trơ."""
    body = payload.model_dump()
    questions = [body["origin"]] if "origin" in body else body["questions"]
    for question in questions:
        assert question["stem"], "a job must carry the question text, not a question id"
        assert question["options"], "a job must carry the options, not an id to look them up"
