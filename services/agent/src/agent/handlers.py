"""Authoring handlers.

Every handler here is a **mock**. There is no model call: each one returns
prepared, deterministic content so the two-phase flow runs end to end and so a
test can assert the same thing twice. What is real is the shape of the output
and the discipline about what is absent from it.

Three rules survive the swap to a real model, and the tests guard them rather
than guarding any sentence produced below:

  - No handler returns a score, a mark, a deadline, or "the student now
    understands". AGENT writes content; BE concludes (ADR-06, ADR-20).
  - A generated question carries exactly one correct option, an error label on
    every distractor, and at least two solution methods (ADR-18). BE re-checks
    this; the mock is not trusted just because it is ours.
  - A retry question keeps the shape of the question the student got wrong and
    differs from the rounds before it (ADR-17).
"""

import logging
import re

from contracts import (
    DraftAssessmentCompleted,
    DraftAssessmentRequested,
    ExplainTurnCompleted,
    ExplainTurnRequested,
    GeneratedOption,
    GeneratedQuestion,
    RetryQuestionCompleted,
    RetryQuestionRequested,
    SolutionMethod,
)

logger = logging.getLogger(__name__)

_LABELS = ("A", "B", "C", "D", "E")

# Stems the mock knows by heart, so a demo tells one coherent story instead of
# showing placeholder text. Anything outside this bank falls back to the generic
# shape below, which is honest about being a stand-in.
_VARIANT_BANK: dict[str, tuple[GeneratedQuestion, ...]] = {}


def _question(
    stem: str,
    options: tuple[tuple[str, bool, str | None], ...],
    methods: tuple[tuple[str, str], ...],
    objective: str,
) -> GeneratedQuestion:
    """Assemble a question from tuples, labelling options A upward.

    Args:
        stem: The question text.
        options: (text, is_correct, error_label) in display order.
        methods: (title, body) pairs, at least two.
        objective: Learning objective string.

    Returns:
        A GeneratedQuestion with labels applied.
    """
    return GeneratedQuestion(
        stem=stem,
        options=tuple(
            GeneratedOption(label=_LABELS[i], text=text, is_correct=correct, error_label=error)
            for i, (text, correct, error) in enumerate(options)
        ),
        methods=tuple(SolutionMethod(title=title, body=body) for title, body in methods),
        learning_objective=objective,
    )


_MONOTONY_METHODS = (
    (
        "Xét dấu đạo hàm",
        "Tính y′, giải y′ = 0 để tìm các mốc, rồi lập bảng xét dấu trên từng khoảng.",
    ),
    (
        "Thử giá trị rồi kiểm lại bằng đạo hàm",
        "Thử một điểm trong mỗi khoảng để đoán chiều, sau đó xét dấu trên cả khoảng — "
        "một điểm chỉ nói về chính điểm đó.",
    ),
)

_MIN_METHODS = (
    ("Đạo hàm", "Giải y′ = 0 để tìm điểm dừng, thay lại vào y để lấy giá trị nhỏ nhất."),
    ("Bất đẳng thức Cô-si", "Với x > 0, áp dụng Cô-si cho hai số dương rồi tìm dấu bằng."),
)

_BANK_SEED: tuple[tuple[str, tuple[GeneratedQuestion, ...]], ...] = (
    (
        "Cho hàm số y = x³ − 3x. Hàm số đồng biến trên khoảng nào?",
        (
            _question(
                "Cho hàm số y = x³ − 12x. Hàm số nghịch biến trên khoảng nào?",
                (
                    ("Khoảng (−∞; −2)", False, "lấy khoảng đồng biến thay vì nghịch biến"),
                    ("Khoảng (−2; 2)", True, None),
                    ("Khoảng (0; 4)", False, "chỉ thử một điểm rồi suy ra cả khoảng"),
                    ("Khoảng (2; +∞)", False, "lấy khoảng đồng biến thay vì nghịch biến"),
                ),
                _MONOTONY_METHODS,
                "Tính đơn điệu của hàm bậc ba",
            ),
            _question(
                "Cho hàm số y = x³ − 6x². Hàm số nghịch biến trên khoảng nào?",
                (
                    ("Khoảng (−∞; 0)", False, "lấy khoảng đồng biến thay vì nghịch biến"),
                    ("Khoảng (0; 4)", True, None),
                    ("Khoảng (0; 2)", False, "dừng ở điểm uốn thay vì ở nghiệm của y′"),
                    ("Khoảng (4; +∞)", False, "lấy khoảng đồng biến thay vì nghịch biến"),
                ),
                _MONOTONY_METHODS,
                "Tính đơn điệu của hàm bậc ba",
            ),
            _question(
                "Cho hàm số y = x³ − 27x. Hàm số nghịch biến trên khoảng nào?",
                (
                    ("Khoảng (−∞; −3)", False, "lấy khoảng đồng biến thay vì nghịch biến"),
                    ("Khoảng (−3; 3)", True, None),
                    ("Khoảng (0; 9)", False, "chỉ thử một điểm rồi suy ra cả khoảng"),
                    ("Khoảng (3; +∞)", False, "lấy khoảng đồng biến thay vì nghịch biến"),
                ),
                _MONOTONY_METHODS,
                "Tính đơn điệu của hàm bậc ba",
            ),
        ),
    ),
    (
        "Giá trị nhỏ nhất của y = x + 4/x trên (0; +∞) bằng bao nhiêu?",
        (
            _question(
                "Giá trị nhỏ nhất của y = x + 9/x trên (0; +∞) bằng bao nhiêu?",
                (
                    ("3", False, "lấy giá trị của x tại điểm cực tiểu thay cho giá trị của y"),
                    ("6", True, None),
                    ("9", False, "lấy hệ số trong tử thay cho giá trị nhỏ nhất"),
                    ("0", False, "coi hàm giảm mãi nên không có giá trị nhỏ nhất dương"),
                ),
                _MIN_METHODS,
                "Giá trị nhỏ nhất của hàm số trên một khoảng",
            ),
            _question(
                "Giá trị nhỏ nhất của y = x + 16/x trên (0; +∞) bằng bao nhiêu?",
                (
                    ("4", False, "lấy giá trị của x tại điểm cực tiểu thay cho giá trị của y"),
                    ("8", True, None),
                    ("16", False, "lấy hệ số trong tử thay cho giá trị nhỏ nhất"),
                    ("0", False, "coi hàm giảm mãi nên không có giá trị nhỏ nhất dương"),
                ),
                _MIN_METHODS,
                "Giá trị nhỏ nhất của hàm số trên một khoảng",
            ),
            _question(
                "Giá trị nhỏ nhất của y = x + 25/x trên (0; +∞) bằng bao nhiêu?",
                (
                    ("5", False, "lấy giá trị của x tại điểm cực tiểu thay cho giá trị của y"),
                    ("10", True, None),
                    ("25", False, "lấy hệ số trong tử thay cho giá trị nhỏ nhất"),
                    ("0", False, "coi hàm giảm mãi nên không có giá trị nhỏ nhất dương"),
                ),
                _MIN_METHODS,
                "Giá trị nhỏ nhất của hàm số trên một khoảng",
            ),
        ),
    ),
)

_VARIANT_BANK.update(_BANK_SEED)


def _normalise(stem: str) -> str:
    """Collapse whitespace so a stem matches the bank despite formatting.

    Args:
        stem: Raw question text.

    Returns:
        The stem with runs of whitespace reduced to single spaces.
    """
    return re.sub(r"\s+", " ", stem).strip()


def draft_questions(request: DraftAssessmentRequested) -> DraftAssessmentCompleted:
    """Draft the questions of one assessment.

    Mock: cycles through the bank's origin questions so a draft always satisfies
    ADR-18 and always looks like the subject asked for.

    Args:
        request: What to write and how much of it.

    Returns:
        The drafted questions. No approval state, no difficulty verdict.
    """
    origins = [_origin_question(stem, variants) for stem, variants in _BANK_SEED]
    questions = tuple(origins[i % len(origins)] for i in range(request.question_count))
    logger.info("drafted %d question(s) for %s", len(questions), request.request_id)
    return DraftAssessmentCompleted(request_id=request.request_id, questions=questions)


def _origin_question(stem: str, variants: tuple[GeneratedQuestion, ...]) -> GeneratedQuestion:
    """Build the phase 1 question that a bank entry is keyed by.

    Args:
        stem: The origin stem.
        variants: Its retry variants, reused for shape.

    Returns:
        A question with the origin stem and the first variant's option shape.
    """
    first = variants[0]
    return GeneratedQuestion(
        stem=stem,
        options=first.options,
        methods=first.methods,
        learning_objective=first.learning_objective,
    )


def retry_question(request: RetryQuestionRequested) -> RetryQuestionCompleted:
    """Write the question for one remediation round.

    Mock: prefers a prepared variant of the same question family, skipping any
    stem already used in an earlier round. Falls back to a clearly-labelled
    stand-in when the origin is outside the bank.

    Args:
        request: The origin question, what the student picked, which round this
            is, and the stems already spent.

    Returns:
        One question, in the same shape as any other. Never a verdict about
        whether the student may have another round -- that ceiling is BE's
        (ADR-17).
    """
    used = {_normalise(stem) for stem in request.previous_stems}
    used.add(_normalise(request.origin.stem))

    for candidate in _VARIANT_BANK.get(_normalise(request.origin.stem), ()):
        if _normalise(candidate.stem) not in used:
            logger.info("retry round=%d from bank for %s", request.round_index, request.request_id)
            return RetryQuestionCompleted(request_id=request.request_id, question=candidate)

    fallback = GeneratedQuestion(
        stem=f"{request.origin.stem} (đề thay số cho lượt {request.round_index})",
        options=request.origin.options,
        methods=request.origin.methods,
        learning_objective=request.origin.learning_objective,
    )
    logger.info("retry round=%d fell back for %s", request.round_index, request.request_id)
    return RetryQuestionCompleted(request_id=request.request_id, question=fallback)


_OPENING = (
    "Mình là trợ lý Kriky, bạn có thể hỏi mình để giải đáp các thắc mắc trong bài làm vừa rồi."
)


def explain_turn(request: ExplainTurnRequested) -> ExplainTurnCompleted:
    """Take the assistant's next turn in the phase 2 conversation.

    Mock: the opening turn greets and names the wrong questions; later turns
    answer about whichever wrong question the student's message points at,
    reading the authored error label and the first solution method rather than
    diagnosing anything (ADR-18).

    Args:
        request: Wrong questions with their solutions, the authored error per
            question, the history, and the student's message.

    Returns:
        One assistant turn. Nothing about scores, rounds or readiness.
    """
    if not request.student_text.strip():
        stems = ", ".join(f"câu {i + 1}" for i in range(len(request.questions)))
        tail = f" Bài này em sai {stems} — hỏi câu nào trước cũng được." if stems else ""
        return ExplainTurnCompleted(request_id=request.request_id, text=_OPENING + tail)

    target = _question_in_focus(request)
    if target is None:
        text = (
            "Em muốn hỏi về câu nào trong số những câu sai? Nói số câu giúp mình, "
            "ví dụ 'câu 4 em chưa hiểu vì sao sai'."
        )
        return ExplainTurnCompleted(request_id=request.request_id, text=text)

    chosen = request.chosen_labels.get(target.stem)
    error = request.error_labels.get(target.stem)
    method = target.methods[0] if target.methods else None

    parts = [f"Ở câu này em chọn {chosen}." if chosen else "Ở câu này:"]
    if error:
        parts.append(f"Lỗi thường gặp của lựa chọn đó là {error}.")
    if method is not None:
        parts.append(f"{method.title}: {method.body}")
    parts.append("Em thử lại theo cách đó xem, chỗ nào vướng thì hỏi tiếp nhé.")
    return ExplainTurnCompleted(request_id=request.request_id, text=" ".join(parts))


def _question_in_focus(request: ExplainTurnRequested) -> GeneratedQuestion | None:
    """Pick which wrong question the student's message is about.

    Args:
        request: The turn being answered.

    Returns:
        The question whose ordinal the message names, the only wrong question
        when there is one, or None when the message names nothing.
    """
    if len(request.questions) == 1:
        return request.questions[0]

    match = re.search(r"câu\s*(\d+)", request.student_text, re.IGNORECASE)
    if match is not None:
        index = int(match.group(1)) - 1
        if 0 <= index < len(request.questions):
            return request.questions[index]

    for turn in reversed(request.history):
        if turn.role != "student":
            continue
        prior = re.search(r"câu\s*(\d+)", turn.text, re.IGNORECASE)
        if prior is not None:
            index = int(prior.group(1)) - 1
            if 0 <= index < len(request.questions):
                return request.questions[index]
    return None


async def draft_assessment(ctx: dict, payload: dict) -> dict:
    """arq entry point for drafting an assessment.

    Args:
        ctx: arq job context. Unused; arq passes it positionally.
        payload: A serialised DraftAssessmentRequested.

    Returns:
        A serialised DraftAssessmentCompleted.

    Side effects:
        None beyond logging. AGENT writes to no store of its own.
    """
    return draft_questions(DraftAssessmentRequested.model_validate(payload)).model_dump(mode="json")


async def generate_retry_question(ctx: dict, payload: dict) -> dict:
    """arq entry point for one remediation round's question.

    Args:
        ctx: arq job context. Unused.
        payload: A serialised RetryQuestionRequested.

    Returns:
        A serialised RetryQuestionCompleted.

    Side effects:
        None beyond logging.
    """
    return retry_question(RetryQuestionRequested.model_validate(payload)).model_dump(mode="json")


async def explain(ctx: dict, payload: dict) -> dict:
    """arq entry point for one assistant turn.

    Args:
        ctx: arq job context. Unused.
        payload: A serialised ExplainTurnRequested.

    Returns:
        A serialised ExplainTurnCompleted.

    Side effects:
        None beyond logging.
    """
    return explain_turn(ExplainTurnRequested.model_validate(payload)).model_dump(mode="json")
