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

from agent import llm
from agent.graphs.explain import speak
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

_DERIVATIVE_METHODS = (
    ("Công thức luỹ thừa", "(xⁿ)′ = n·xⁿ⁻¹, áp cho từng số hạng rồi cộng lại."),
    ("Kiểm bằng hệ số góc", "Tính hệ số góc tiếp tuyến tại một điểm rồi đối chiếu."),
)

_LINEAR_METHODS = (
    ("Hệ số góc", "Dấu của hệ số góc quyết định chiều biến thiên trên toàn trục số."),
    ("Đồ thị", "Đường thẳng đi lên hay đi xuống trên cả miền xác định, không đổi chiều."),
)

_LIMIT_METHODS = (
    ("Phân tích thành nhân tử", "Tách hiệu hai bình phương rồi rút gọn trước khi thay số."),
    ("Quy tắc L'Hôpital", "Đạo hàm tử và mẫu rồi thay giá trị vào."),
)

_ASYMPTOTE_METHODS = (
    ("Tỉ số hệ số bậc cao nhất", "Bậc tử bằng bậc mẫu thì tiệm cận ngang là tỉ số hai hệ số ấy."),
    ("Lấy giới hạn", "Cho x → ±∞, chia cả tử và mẫu cho x rồi lấy giới hạn."),
)

# Every seeded question needs a family here. A question outside the bank falls
# back to a stand-in, and BE rejects that stand-in for repeating the stem it is
# supposed to replace (ADR-17) -- which is the right failure, but it means the
# demo stalls rather than teaching.
_BANK_SEED: tuple[tuple[str, tuple[GeneratedQuestion, ...]], ...] = (
    (
        "Đạo hàm của y = x² + 3x là gì?",
        (
            _question(
                "Đạo hàm của y = x² + 5x là gì?",
                (
                    ("2x + 5", True, None),
                    ("x + 5", False, "quên nhân số mũ khi hạ bậc"),
                    ("2x", False, "bỏ sót đạo hàm của số hạng bậc nhất"),
                    ("x² + 5", False, "chỉ đạo hàm một số hạng"),
                ),
                _DERIVATIVE_METHODS,
                "Đạo hàm của đa thức",
            ),
            _question(
                "Đạo hàm của y = 3x² − 4x là gì?",
                (
                    ("6x − 4", True, None),
                    ("3x − 4", False, "quên nhân số mũ khi hạ bậc"),
                    ("6x", False, "bỏ sót đạo hàm của số hạng bậc nhất"),
                    ("6x² − 4", False, "không hạ bậc khi lấy đạo hàm"),
                ),
                _DERIVATIVE_METHODS,
                "Đạo hàm của đa thức",
            ),
            _question(
                "Đạo hàm của y = x² − 7x là gì?",
                (
                    ("2x − 7", True, None),
                    ("x − 7", False, "quên nhân số mũ khi hạ bậc"),
                    ("2x", False, "bỏ sót đạo hàm của số hạng bậc nhất"),
                    ("2x + 7", False, "sai dấu khi hạ bậc số hạng âm"),
                ),
                _DERIVATIVE_METHODS,
                "Đạo hàm của đa thức",
            ),
        ),
    ),
    (
        "Hàm số y = 2x + 1 đồng biến trên khoảng nào?",
        (
            _question(
                "Hàm số y = 5x − 2 đồng biến trên khoảng nào?",
                (
                    ("Khoảng (−∞; +∞)", True, None),
                    ("Khoảng (0; +∞)", False, "tưởng hàm bậc nhất chỉ tăng khi x dương"),
                    ("Khoảng (−∞; 0)", False, "đọc ngược chiều biến thiên"),
                    ("Không đồng biến ở đâu", False, "nhầm hệ số góc dương với hàm hằng"),
                ),
                _LINEAR_METHODS,
                "Tính đơn điệu của hàm bậc nhất",
            ),
            _question(
                "Hàm số y = −3x + 4 nghịch biến trên khoảng nào?",
                (
                    ("Khoảng (−∞; +∞)", True, None),
                    ("Khoảng (0; +∞)", False, "tưởng hàm bậc nhất chỉ giảm khi x dương"),
                    ("Khoảng (−∞; 0)", False, "đọc ngược chiều biến thiên"),
                    ("Không nghịch biến ở đâu", False, "nhầm hệ số góc âm với hàm hằng"),
                ),
                _LINEAR_METHODS,
                "Tính đơn điệu của hàm bậc nhất",
            ),
            _question(
                "Hàm số y = 0,5x + 7 đồng biến trên khoảng nào?",
                (
                    ("Khoảng (−∞; +∞)", True, None),
                    ("Khoảng (7; +∞)", False, "lấy hệ số tự do làm mốc đổi chiều"),
                    ("Khoảng (−∞; 0)", False, "đọc ngược chiều biến thiên"),
                    ("Không đồng biến ở đâu", False, "tưởng hệ số góc dưới 1 thì hàm không tăng"),
                ),
                _LINEAR_METHODS,
                "Tính đơn điệu của hàm bậc nhất",
            ),
        ),
    ),
    (
        "Giới hạn của (x² − 1)/(x − 1) khi x → 1 bằng bao nhiêu?",
        (
            _question(
                "Giới hạn của (x² − 4)/(x − 2) khi x → 2 bằng bao nhiêu?",
                (
                    ("4", True, None),
                    ("0", False, "thay thẳng x = 2 vào tử rồi dừng"),
                    ("2", False, "rút gọn sai khi phân tích hiệu hai bình phương"),
                    ("Không tồn tại", False, "coi dạng 0/0 là không có giới hạn"),
                ),
                _LIMIT_METHODS,
                "Giới hạn dạng vô định",
            ),
            _question(
                "Giới hạn của (x² − 9)/(x − 3) khi x → 3 bằng bao nhiêu?",
                (
                    ("6", True, None),
                    ("0", False, "thay thẳng x = 3 vào tử rồi dừng"),
                    ("3", False, "rút gọn sai khi phân tích hiệu hai bình phương"),
                    ("Không tồn tại", False, "coi dạng 0/0 là không có giới hạn"),
                ),
                _LIMIT_METHODS,
                "Giới hạn dạng vô định",
            ),
            _question(
                "Giới hạn của (x² − 25)/(x − 5) khi x → 5 bằng bao nhiêu?",
                (
                    ("10", True, None),
                    ("0", False, "thay thẳng x = 5 vào tử rồi dừng"),
                    ("5", False, "rút gọn sai khi phân tích hiệu hai bình phương"),
                    ("Không tồn tại", False, "coi dạng 0/0 là không có giới hạn"),
                ),
                _LIMIT_METHODS,
                "Giới hạn dạng vô định",
            ),
        ),
    ),
    (
        "Đồ thị y = (2x − 1)/(x + 3) có tiệm cận ngang là đường nào?",
        (
            _question(
                "Đồ thị y = (3x + 2)/(x − 1) có tiệm cận ngang là đường nào?",
                (
                    ("y = 3", True, None),
                    ("x = 1", False, "nhầm tiệm cận đứng với tiệm cận ngang"),
                    ("y = −2", False, "lấy tỉ số hai hằng số thay vì hai hệ số bậc cao nhất"),
                    ("y = 0", False, "áp quy tắc của trường hợp bậc tử nhỏ hơn bậc mẫu"),
                ),
                _ASYMPTOTE_METHODS,
                "Tiệm cận của hàm phân thức",
            ),
            _question(
                "Đồ thị y = (5x − 4)/(2x + 1) có tiệm cận ngang là đường nào?",
                (
                    ("y = 2,5", True, None),
                    ("x = −0,5", False, "nhầm tiệm cận đứng với tiệm cận ngang"),
                    ("y = −4", False, "lấy hằng số ở tử làm tiệm cận"),
                    ("y = 0", False, "áp quy tắc của trường hợp bậc tử nhỏ hơn bậc mẫu"),
                ),
                _ASYMPTOTE_METHODS,
                "Tiệm cận của hàm phân thức",
            ),
            _question(
                "Đồ thị y = (x + 6)/(4x − 3) có tiệm cận ngang là đường nào?",
                (
                    ("y = 0,25", True, None),
                    ("x = 0,75", False, "nhầm tiệm cận đứng với tiệm cận ngang"),
                    ("y = 6", False, "lấy hằng số ở tử làm tiệm cận"),
                    ("y = 4", False, "lấy nghịch đảo của tỉ số hai hệ số bậc cao nhất"),
                ),
                _ASYMPTOTE_METHODS,
                "Tiệm cận của hàm phân thức",
            ),
        ),
    ),
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
    numbers = _numbers(request)

    if not request.student_text.strip():
        named = ", ".join(f"câu {number}" for number in numbers)
        tail = f" Bài này em sai {named} — hỏi câu nào trước cũng được." if named else ""
        return ExplainTurnCompleted(request_id=request.request_id, text=_OPENING + tail)

    target = _question_in_focus(request)
    if target is None:
        example = numbers[0] if numbers else 1
        text = (
            "Em muốn hỏi về câu nào trong số những câu sai? Nói số câu giúp mình, "
            f"ví dụ 'câu {example} em chưa hiểu vì sao sai'."
        )
        return ExplainTurnCompleted(request_id=request.request_id, text=text)

    chosen = request.chosen_labels.get(target.stem)
    error = request.error_labels.get(target.stem)
    method = target.methods[0] if target.methods else None
    number = numbers[request.questions.index(target)] if numbers else None

    parts = [f"Câu {number}: em chọn {chosen}." if chosen else f"Câu {number}:"]
    if error:
        parts.append(f"Lỗi thường gặp của lựa chọn đó là {error}.")
    if method is not None:
        parts.append(f"{method.title}: {method.body}")
    parts.append("Em thử lại theo cách đó xem, chỗ nào vướng thì hỏi tiếp nhé.")
    return ExplainTurnCompleted(request_id=request.request_id, text=" ".join(parts))


def _numbers(request: ExplainTurnRequested) -> tuple[int, ...]:
    """Return the paper's number for each wrong question.

    Args:
        request: The turn being answered.

    Returns:
        The numbers BE sent, or 1..n when it sent none. Counting from one is a
        fallback for an old payload, not a default worth relying on: a student
        told to look at "câu 1" when they got câu 5 wrong goes to the wrong
        question.
    """
    if len(request.question_numbers) == len(request.questions):
        return request.question_numbers
    return tuple(range(1, len(request.questions) + 1))


def _question_in_focus(request: ExplainTurnRequested) -> GeneratedQuestion | None:
    """Pick which wrong question the student's message is about.

    Args:
        request: The turn being answered.

    Returns:
        The question whose number the message names, the only wrong question
        when there is one, or None when the message names nothing.
    """
    if len(request.questions) == 1:
        return request.questions[0]

    numbers = _numbers(request)

    def by_number(text: str) -> GeneratedQuestion | None:
        match = re.search(r"câu\s*(\d+)", text, re.IGNORECASE)
        if match is None:
            return None
        wanted = int(match.group(1))
        for question, number in zip(request.questions, numbers, strict=False):
            if number == wanted:
                return question
        return None

    named = by_number(request.student_text)
    if named is not None:
        return named

    for turn in reversed(request.history):
        if turn.role == "student" and (prior := by_number(turn.text)) is not None:
            return prior
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

    Publishes the answer piece by piece while the model writes it, so the
    student watches words appear instead of a pause. The pieces are a courtesy:
    the returned text is the whole answer and is what gets stored, so a student
    who reloads loses the animation and nothing else.

    Args:
        ctx: arq job context. `ctx["redis"]` is the connection the pieces go
            out on; nothing else here is used.
        payload: A serialised ExplainTurnRequested.

    Returns:
        A serialised ExplainTurnCompleted.

    Side effects:
        Publishes to the Redis channel the request names, when it names one.
    """
    request = ExplainTurnRequested.model_validate(payload)
    if not llm.enabled():
        return explain_turn(request).model_dump(mode="json")

    channel = request.stream_channel
    redis = ctx.get("redis")
    said: list[str] = []

    async def publish(piece: str) -> None:
        said.append(piece)
        await redis.publish(channel, piece)

    try:
        text = await speak(request, publish if channel and redis is not None else None)
    except Exception:
        logger.exception("model failed on the tutoring turn")
        if said:
            # Those words are already on the student's screen. Substituting the
            # prepared answer now would store a different reply from the one
            # they watched appear, and they would find it on the next reload
            # with no explanation. A truncated answer that matches what they
            # read is the honest one; asking again is one click.
            return ExplainTurnCompleted(
                request_id=request.request_id, text="".join(said)
            ).model_dump(mode="json")
        # Nothing reached anybody, so there is nothing to contradict.
        return explain_turn(request).model_dump(mode="json")

    return ExplainTurnCompleted(request_id=request.request_id, text=text).model_dump(mode="json")
