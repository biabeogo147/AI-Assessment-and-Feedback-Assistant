"""Các handler soạn nội dung.

Mọi handler ở đây đều là **mock**. Không có lời gọi model nào: mỗi handler trả về nội
dung dọn trước, tất định, để luồng hai pha chạy được từ đầu tới cuối và để một test
khẳng định được cùng một điều hai lần. Thứ có thật là hình dạng của đầu ra, và sự kỷ
luật về những gì vắng mặt trong đó.

Ba luật sống sót qua việc đổi sang model thật, và các test canh chúng chứ không canh
bất kỳ câu chữ nào được sinh ra bên dưới:

  - Không handler nào trả về điểm, một dấu chấm điểm, một hạn vào, hay "học sinh giờ
    đã hiểu". AGENT viết nội dung; BE kết luận (ADR-06, ADR-20).
  - Một câu hỏi được sinh ra mang đúng một phương án đúng, một error label trên mọi
    distractor, và ít nhất hai cách giải (ADR-18). BE check lại điều này; mock không
    được tin chỉ vì nó là của ta.
  - Một câu làm lại giữ hình dạng của câu học sinh làm sai và khác với các lượt trước
    nó (ADR-17).
"""

import logging
import re

from agent import llm
from agent.graphs.authoring import draft_brief, normalise, retry_brief, write_question
from agent.graphs.explain import speak
from agent.graphs.naming import name_it
from agent.graphs.propose import propose
from agent.graphs.reporting import tell_about
from contracts import (
    ConversationNameCompleted,
    ConversationNameRequested,
    DraftQuestionCompleted,
    DraftQuestionRequested,
    ExplainTurnCompleted,
    ExplainTurnRequested,
    GeneratedOption,
    GeneratedQuestion,
    NextStepCompleted,
    NextStepRequested,
    PlanReportCompleted,
    PlanReportRequested,
    PlanStep,
    RetryQuestionCompleted,
    RetryQuestionRequested,
    SolutionMethod,
    TurnRecord,
)

logger = logging.getLogger(__name__)

_LABELS = ("A", "B", "C", "D", "E")

# Những stem mà mock thuộc lòng, để một buổi demo kể một câu chuyện liền mạch thay vì
# hiện ra chữ giữ chỗ. Bất cứ thứ gì nằm ngoài bank này sẽ lùi về hình dạng chung bên
# dưới, và hình dạng đó thẳng thắn về việc mình chỉ là người đóng thế.
_VARIANT_BANK: dict[str, tuple[GeneratedQuestion, ...]] = {}


def _question(
    stem: str,
    options: tuple[tuple[str, bool, str | None], ...],
    methods: tuple[tuple[str, str], ...],
    objective: str,
) -> GeneratedQuestion:
    """Lắp một câu hỏi từ các tuple, gán nhãn phương án từ A trở lên.

    Args:
        stem: Phần đề của câu hỏi.
        options: (text, is_correct, error_label) theo thứ tự hiển thị.
        methods: Các cặp (title, body), ít nhất hai cặp.
        objective: Chuỗi mục tiêu học tập.

    Returns:
        Một GeneratedQuestion đã gán nhãn.
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

# Mỗi câu hỏi được gieo sẵn cần một họ ở đây. Một câu hỏi ngoài bank sẽ lùi về một
# câu đóng thế, và BE từ chối câu đóng thế đó vì nó lặp lại đúng cái stem nó đáng ra
# phải thay (ADR-17) -- đó là lần thất bại đúng đắn, nhưng nó có nghĩa là buổi demo
# đứng lại thay vì dạy được gì.
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


def draft_question(request: DraftQuestionRequested) -> DraftQuestionCompleted:
    """Viết một câu của đề nháp mà không gọi model.

    Mock: lấy entry trong bank ở đúng vị trí của câu này, nên một đề nháp luôn thoả
    ADR-18 và luôn trông giống môn đã được yêu cầu.

    **Bank giữ sáu câu.** Một brief hỏi hơn sáu câu sẽ quay vòng lại, BE từ chối các
    câu lặp, và đề nháp trả về thiếu -- đúng sáu câu, còn mọi vị trí sau vị trí thứ sáu
    đều bỏ cuộc (xin 10 câu thì bốn vị trí, xin 50 thì bốn mươi bốn). Chuyện
    đó đáng được nói thẳng ra thay vì gọi nó là một buổi tổng duyệt cho đường xử lý
    trùng lặp: hai job thật đụng nhau là chuyện may rủi, còn cái này là chắc chắn, và
    một lần chạy demo không có API key sẽ luôn trông như việc soạn nháp bị hỏng khi
    vượt quá sáu câu.

    Args:
        request: Brief, và đây là câu thứ mấy trong bộ đề.

    Returns:
        Một câu hỏi. Không có state duyệt, không có phán xét về độ khó.
    """
    origins = [_origin_question(stem, variants) for stem, variants in _BANK_SEED]
    question = origins[(request.ordinal - 1) % len(origins)]
    logger.info("drafted question %d for %s", request.ordinal, request.request_id)
    return DraftQuestionCompleted(request_id=request.request_id, question=question)


def _origin_question(stem: str, variants: tuple[GeneratedQuestion, ...]) -> GeneratedQuestion:
    """Dựng câu hỏi pha 1 mà một entry trong bank được khoá theo.

    Args:
        stem: Stem của câu gốc.
        variants: Các biến thể làm lại của nó, dùng lại để lấy hình dạng.

    Returns:
        Một câu hỏi với stem của câu gốc và hình dạng phương án của biến thể đầu tiên.
    """
    first = variants[0]
    return GeneratedQuestion(
        stem=stem,
        options=first.options,
        methods=first.methods,
        learning_objective=first.learning_objective,
    )


def retry_question(request: RetryQuestionRequested) -> RetryQuestionCompleted:
    """Viết câu hỏi cho một lượt chữa lỗi.

    Mock: ưu tiên một biến thể dọn trước trong cùng họ câu hỏi, bỏ qua mọi stem đã
    dùng ở một lượt trước. Lùi về một câu đóng thế có nhãn rõ ràng khi câu gốc nằm
    ngoài bank.

    Args:
        request: Câu gốc, phương án học sinh đã chọn, đây là lượt thứ mấy, và các stem
            đã tiêu.

    Returns:
        Một câu hỏi, cùng hình dạng với mọi câu khác. Không bao giờ là một phán xét về
        chuyện học sinh có được thêm một lượt nữa hay không -- cái trần đó là của BE
        (ADR-17).
    """
    used = {normalise(stem) for stem in request.previous_stems}
    used.add(normalise(request.origin.stem))

    for candidate in _VARIANT_BANK.get(normalise(request.origin.stem), ()):
        if normalise(candidate.stem) not in used:
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
    """Nói lượt tiếp theo của trợ lý trong cuộc hội thoại pha 2.

    Mock: lượt mở đầu chào và gọi tên các câu làm sai; các lượt sau trả lời về đúng câu
    sai mà tin nhắn của học sinh trỏ tới, đọc error label do người soạn viết và cách
    giải đầu tiên chứ không tự chẩn đoán gì (ADR-18).

    Args:
        request: Các câu làm sai kèm lời giải của chúng, lỗi do người soạn viết cho
            từng câu, lịch sử hội thoại, và tin nhắn của học sinh.

    Returns:
        Một lượt nói của trợ lý. Không có gì về điểm, về số lượt, hay về chuyện đã sẵn
        sàng hay chưa.
    """
    numbers = _numbers(request)

    if not request.student_text.strip():
        named = ", ".join(f"câu {number}" for number in numbers)
        tail = f" Bài này bạn sai {named} — hỏi câu nào trước cũng được." if named else ""
        return ExplainTurnCompleted(request_id=request.request_id, text=_OPENING + tail)

    target = _question_in_focus(request)
    if target is None:
        example = numbers[0] if numbers else 1
        text = (
            "Bạn muốn hỏi về câu nào trong số những câu sai? Nói số câu giúp mình, "
            f"ví dụ 'câu {example} mình chưa hiểu vì sao sai'."
        )
        return ExplainTurnCompleted(request_id=request.request_id, text=text)

    chosen = request.chosen_labels.get(target.stem)
    error = request.error_labels.get(target.stem)
    method = target.methods[0] if target.methods else None
    number = numbers[request.questions.index(target)] if numbers else None

    parts = [f"Câu {number}: bạn chọn {chosen}." if chosen else f"Câu {number}:"]
    if error:
        parts.append(f"Lỗi thường gặp của lựa chọn đó là {error}.")
    if method is not None:
        parts.append(f"{method.title}: {method.body}")
    parts.append("Bạn thử lại theo cách đó xem, chỗ nào vướng thì hỏi tiếp nhé.")
    return ExplainTurnCompleted(request_id=request.request_id, text=" ".join(parts))


def _numbers(request: ExplainTurnRequested) -> tuple[int, ...]:
    """Trả về số câu theo đề cho từng câu làm sai.

    Args:
        request: Lượt đang được trả lời.

    Returns:
        Các số BE gửi tới, hoặc 1..n khi nó không gửi số nào. Đếm từ một là một
        fallback cho payload cũ, không phải một default đáng dựa vào: một học sinh được
        bảo nhìn vào "câu 1" trong khi em sai câu 5 sẽ mở sai câu.
    """
    if len(request.question_numbers) == len(request.questions):
        return request.question_numbers
    return tuple(range(1, len(request.questions) + 1))


def _question_in_focus(request: ExplainTurnRequested) -> GeneratedQuestion | None:
    """Chọn xem tin nhắn của học sinh đang nói về câu sai nào.

    Args:
        request: Lượt đang được trả lời.

    Returns:
        Câu hỏi có số mà tin nhắn gọi tên, hoặc câu sai duy nhất khi chỉ có một câu,
        hoặc None khi tin nhắn không gọi tên gì.
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


# Một tên lớp như giáo viên viết: khối, một chữ cái, đôi khi một số thứ tự. Đủ để nhận
# ra "12A1", "lớp 11B" và "lớp12A" trong một câu, và không hơn -- mock không phải một
# parser, nó là một cách chạy cái loop mà không mất tiền.
#
# Không có word boundary ở phía trước, vì "lớp12A" sẽ không qua được nó trong khi BE
# phân giải cách viết đó rất ổn, và việc hai nửa lệch nhau làm buổi demo trông như có
# một bug phân giải vốn không tồn tại. Một lookbehind cho chữ số thay chỗ nó, nhờ vậy
# một năm như 2026 không thể bị đọc thành một lớp; còn boundary ở cuối là thứ giữ cho
# "15 phút" và "2 câu" nằm ngoài.
_CLASS_NAME = re.compile(r"(?<!\d)(\d{1,2}\s?[A-Za-z]\d?)\b")

_NO_CLASS_NAMED = (
    "Bạn muốn xem lớp nào? Nói tên lớp giúp mình, ví dụ 'lớp 12A1 làm bài hôm qua thế nào'."
)

_NOTHING_TO_USE = "Lượt này mình chưa tra được dữ liệu nào. Bạn thử hỏi lại sau một chút nhé."

# Giáo viên đang **nhờ làm** một đề. Ba điều kiện, không một: một động từ nhờ, chữ "đề"
# đứng thành một từ, và câu đó không phải một câu hỏi. Bản đầu của chỗ này chỉ dò substring
# `(đề|soạn|tạo)`, và nó đọc "đề Toán 12A1 đã có 10 câu chưa?" thành một lệnh tạo đề mới --
# nhớ rằng mock cũng là đường lùi khi model lỗi, nên một lần timeout trên một câu HỎI sẽ
# ghi một đề thật vào database. Nó cũng đọc "lớp 12A1 có vấn đề gì không" thành việc soạn
# đề, vì "vấn đề" chứa "đề".
_ASKS_TO_MAKE = re.compile(r"(?:^|\s)(tạo|soạn|làm|lên|dựng)(?=\s)", re.IGNORECASE)
_A_PAPER = re.compile(r"(?:^|\s)(?:đề|bộ đề)(?=\s|$|[,.;:!?])", re.IGNORECASE)
# Dấu hỏi và mấy chữ chỉ câu hỏi. Chặn rộng tay là cố ý: nhận nhầm một câu nhờ thành câu
# hỏi thì mock hỏi lại một lượt, nhận nhầm chiều kia thì nó ghi một đề không ai yêu cầu.
_SOUNDS_LIKE_A_QUESTION = re.compile(
    r"\?|(?:^|\s)(chưa|mấy|bao nhiêu|thế nào|ra sao|đã có|có không|không\?)(?=\s|$|[,.;:?])",
    re.IGNORECASE,
)

# Số câu, và khối. Khối đọc từ tên lớp trước ("12A1" → 12) rồi mới tới chữ "lớp 12".
# `(?<!\d)` và ba chữ số là để "100 câu" đọc ra 100 rồi bị chặn vì quá trần, chứ không bị
# cắt thành "00" -- một con số 0 đi tới `create_draft` thành một bước đỏ, trong khi việc
# đúng là hỏi lại.
_HOW_MANY = re.compile(r"(?<!\d)(\d{1,3})\s*câu")
_WHICH_GRADE = re.compile(r"(?:lớp|khối)\s*(\d{1,2})")

# Trần của chính `create_draft`. Mock đọc được một con số ngoài khoảng thì hỏi lại, vì một
# bước đỏ không nói cho giáo viên biết phải sửa gì.
_MOST_QUESTIONS = 50

# Môn, đọc từ chính chữ giáo viên gõ. Một bảng tra chứ không một giá trị mặc định: mock
# **không** được đoán môn, vì cả bộ đề sinh ra từ một brief và một môn sai làm sai cả bộ.
#
# Hai bảng, vì tiếng Việt không có biên từ như tiếng Anh. Bản đầu dò substring và đọc
# "cho học sinh lớp 12" thành môn Sinh học, "soạn nhanh" thành Tiếng Anh, "xử lý số liệu"
# thành Vật lý -- cả ba đều là câu bình thường của giáo viên, và cả ba đều cho ra một bộ
# đề sai môn. Những tên môn trùng với từ thường dùng vì thế đòi chữ "môn" đứng ngay trước.
_SUBJECTS = {"toán": "Toán", "hoá": "Hoá học", "hóa": "Hoá học"}
_ONLY_AFTER_THE_WORD_MON = {
    "lý": "Vật lý",
    "sinh": "Sinh học",
    "văn": "Ngữ văn",
    "anh": "Tiếng Anh",
    "sử": "Lịch sử",
    "địa": "Địa lý",
}


def _subject_in(asked: str) -> str | None:
    """Đọc tên môn ra khỏi câu giáo viên gõ, hoặc trả `None` khi họ chưa nói.

    Args:
        asked: Câu giáo viên vừa gõ.

    Returns:
        Tên môn đầy đủ, hoặc `None` -- và `None` dẫn tới một câu hỏi lại, không tới một
        giá trị mặc định.
    """
    low = asked.lower()
    for word, full in _SUBJECTS.items():
        if re.search(rf"(?:^|\s){word}(?=\s|$|[,.;:!?])", low):
            return full
    for word, full in _ONLY_AFTER_THE_WORD_MON.items():
        if re.search(rf"(?:^|\s)môn\s+{word}(?=\s|$|[,.;:!?])", low):
            return full
    return None


_WHAT_IS_MISSING = (
    "Bạn cho mình biết thêm: môn gì, khối nào, phạm vi kiến thức, và bao nhiêu câu nhé."
)


def _brief_from(asked: str) -> dict[str, str] | None:
    """Đọc một brief soạn đề ra từ chính câu giáo viên gõ.

    Mock, và nó **chỉ đọc**: không có giá trị mặc định nào cho môn hay số câu, vì mock mà
    đoán thay giáo viên thì đang trình diễn đúng cái hành vi prompt cấm (ADR-25). Thiếu
    một mục thì trả `None` và đường gọi sẽ hỏi lại.

    `topic_scope` lấy nguyên câu giáo viên gõ. Đó không phải cách đọc lười: spec của tool
    nói đúng thế -- *phạm vi kiến thức theo lời giáo viên* -- nên lời họ là giá trị đúng
    nhất mock có.

    Args:
        asked: Câu giáo viên vừa gõ.

    Returns:
        Các tham số cho `create_draft`, hoặc `None` khi câu ấy chưa đủ -- kể cả khi số câu
        đọc được nhưng nằm ngoài trần của tool, vì một bước đỏ không nói cho giáo viên biết
        phải sửa gì.
    """
    how_many = _HOW_MANY.search(asked)
    named = _CLASS_NAME.search(asked)
    grade = named.group(1)[:2].rstrip("ABCDEFabcdef") if named else None
    if grade is None or not grade.isdigit():
        found = _WHICH_GRADE.search(asked)
        grade = found.group(1) if found else None
    subject = _subject_in(asked)
    if how_many is None or grade is None or subject is None:
        return None
    if not 1 <= int(how_many.group(1)) <= _MOST_QUESTIONS:
        return None
    return {
        "subject": subject,
        "grade": grade,
        "topic_scope": asked.strip(),
        "question_count": how_many.group(1),
    }


def _current_turn(history: tuple[TurnRecord, ...]) -> tuple[TurnRecord, ...]:
    """Mọi thứ kể từ tin nhắn gần nhất của giáo viên.

    Một lượt là một câu hỏi và phần việc đã làm cho nó. Những gì tới trước đó là ngữ
    cảnh cho một model đọc nó, không phải bằng chứng rằng câu hỏi hiện tại đã được trả
    lời.

    Args:
        history: Toàn bộ cuộc hội thoại, cũ nhất trước.

    Returns:
        Các bước của lượt hiện tại, gồm cả chính tin nhắn của giáo viên.
    """
    for index in range(len(history) - 1, -1, -1):
        if history[index].kind == "teacher":
            return history[index:]
    return history


def next_step(request: NextStepRequested) -> NextStepCompleted:
    """Đề nghị bước tiếp theo trong một lượt của giáo viên mà không gọi model.

    Mock, và được dựng để chạy qua cái loop chứ không phải để trông có vẻ đang làm
    việc: nó xin một tool khi chưa có dữ liệu, và trả lời ngay khi có một kết quả nằm
    trong lịch sử. Hai điều đó cùng nhau là thứ làm cái loop kết thúc, nên chúng là
    phần đáng có mà không mất tiền.

    Chỉ lượt hiện tại được xét -- mọi thứ sau tin nhắn gần nhất của giáo viên. Lịch sử
    hội thoại trước đây tới từng lượt một và nay tới cả cục, và chỉ điều đó thôi đã làm
    hỏng chỗ này: check "mình đã có dữ liệu chưa?" tìm thấy một kết quả từ một lượt
    trước rồi thôi gọi tool, thế là trợ lý lặp lại câu cuối của mình mãi mãi.

    Args:
        request: Cuộc hội thoại tới lúc này và các tool giáo viên này được dùng.

    Returns:
        Một đề nghị. Không bao giờ là một tool ngoài danh mục BE gửi tới, vì một đề
        nghị mà BE buộc phải từ chối sẽ chạy qua đường lỗi và không dạy gì về đường
        bình thường. Một plan chỉ được nêu khi `plannable` thực sự có các tool của nó --
        hai danh mục là hai quyền khác nhau (ADR-25).
    """
    turn = _current_turn(request.history)
    harvested = next((step for step in reversed(turn) if step.kind == "tool_result"), None)
    asked = next((step.text for step in reversed(turn) if step.kind == "teacher"), "")
    plannable = {tool.name for tool in request.plannable}

    wants_a_paper = (
        _ASKS_TO_MAKE.search(asked) is not None
        and _A_PAPER.search(asked) is not None
        and _SOUNDS_LIKE_A_QUESTION.search(asked) is None
    )
    if wants_a_paper and {"create_draft", "start_drafting"} <= plannable:
        # Đường soạn đề đi trước đường tra lớp, vì "tạo đề 10 câu Toán cho lớp 12A1" có cả
        # hai dấu hiệu và việc được nhờ là soạn đề, không phải tra lớp.
        brief = _brief_from(asked)
        if brief is None:
            return NextStepCompleted(
                request_id=request.request_id, kind="ask_clarify", text=_WHAT_IS_MISSING
            )
        return NextStepCompleted(
            request_id=request.request_id,
            kind="plan",
            text="Được, mình soạn đề ngay.",
            steps=(
                PlanStep(
                    tool_name="create_draft",
                    args=brief,
                    title=f"Tạo đề {brief['question_count']} câu",
                ),
                # `{1.assessment_id}` là cú pháp BE giải, và một mock viết nó ra là cách
                # đường ấy được đi qua ở một bản dev không có API key.
                PlanStep(
                    tool_name="start_drafting",
                    args={"assessment_id": "{1.assessment_id}"},
                    title=f"Soạn {brief['question_count']} câu hỏi",
                ),
            ),
        )

    if harvested is not None and harvested.tool_result.get("ambiguous"):
        # ADR-23: không ai chọn giữa các candidates, và điều đó gồm cả mock. Đây là
        # đường một buổi demo đi qua, nên một mock âm thầm chọn một cái sẽ đang trình
        # diễn đúng cái hành vi mà thiết kế cấm.
        #
        # Ở đây cũng không có `choices`. BE render các lựa chọn từ những dòng nó đã
        # đọc, và một mock cũng viết chúng ra sẽ là bịa thêm một nguồn thứ hai cho đúng
        # cái thứ mà ADR-23 nói là chỉ có một nguồn.
        cut = harvested.tool_result.get("more") or 0
        tail = f" Danh sách còn {cut} lớp nữa chưa hiện." if cut else ""
        return NextStepCompleted(
            request_id=request.request_id,
            kind="ask_clarify",
            text=f"Bạn có nhiều lớp khớp tên đó. Bạn muốn xem lớp nào?{tail}",
        )

    if harvested is not None:
        body = ", ".join(f"{key}: {value}" for key, value in sorted(harvested.tool_result.items()))
        return NextStepCompleted(
            request_id=request.request_id,
            kind="say",
            text=f"Mình tra được: {body}.",
        )

    named = _CLASS_NAME.search(asked)
    usable = {tool.name for tool in request.catalog}

    if named is not None and "find_class" in usable:
        return NextStepCompleted(
            request_id=request.request_id,
            kind="call_tool",
            tool_name="find_class",
            tool_args={"name": named.group(1).replace(" ", "")},
        )

    if not usable:
        return NextStepCompleted(request_id=request.request_id, kind="say", text=_NOTHING_TO_USE)

    return NextStepCompleted(
        request_id=request.request_id, kind="ask_clarify", text=_NO_CLASS_NAMED
    )


async def propose_next_step(ctx: dict, payload: dict) -> dict:
    """Điểm vào arq cho một lượt suy nghĩ trong khung chat của giáo viên.

    Args:
        ctx: Context job của arq. Không dùng.
        payload: Một NextStepRequested đã serialise.

    Returns:
        Một NextStepCompleted đã serialise. Luôn luôn là một đề nghị: handler này không
        chạy tool nào và không ghi vào store nào, vì AGENT không giữ credential database
        nào và vì việc phân quyền thuộc về nơi có session.

    Side effects:
        Không có gì ngoài việc log.
    """
    request = NextStepRequested.model_validate(payload)
    if not llm.enabled():
        return next_step(request).model_dump(mode="json")

    try:
        return (await propose(request)).model_dump(mode="json")
    except Exception:
        # Đề nghị dọn trước ở đây thay thế vào được một cách an toàn, khác với trên
        # đường kèm học sinh: chưa có gì tới tay giáo viên, vì một đề nghị không được
        # cho ai xem cho tới khi BE đã hành động trên nó.
        logger.exception("model could not propose a next step for %s", request.request_id)
        return next_step(request).model_dump(mode="json")


# Chỗ handler đặt tiếng chuông xuống cho `after_job_end` nhặt lên. Một khoá trong `ctx`,
# là dict arq dựng riêng cho từng job và truyền **cùng một object** cho cả hàm job lẫn các
# hook vòng đời của nó.
_BELL = "draft_progress_bell"


def _arm_bell(ctx: dict, request: DraftQuestionRequested) -> None:
    """Đặt sẵn tiếng chuông cho câu này; ai rung là việc của worker.

    Vì sao không publish thẳng trong thân job: lúc hàm job còn đang chạy, **kết quả chưa
    nằm trong result store**. arq ghi kết quả bằng `finish_job`, và nó chỉ chạy sau khi
    coroutine của job trả về. Một BE nghe chuông rồi thu hoạch ngay sẽ đọc được `pending`
    cho đúng câu vừa báo — màn hình luôn trễ một nhịp, và **tiếng chuông cuối cùng không
    gặt được gì**, nên một lượt chat chờ "hết câu đang soạn" sẽ treo tới hết hạn kiên nhẫn.
    Review Pha D đo được chuyện này; bản đầu của chỗ này publish ngay trong job.

    `after_job_end` của arq chạy **sau** `finish_job`. Chuông rung từ đó (`ring_bell`), còn
    chỗ này chỉ ghi lại *rung cái gì*.

    Chuông chở **số thứ tự, không chở câu hỏi** (ADR-25): pub/sub không bền, nên thứ gì nằm
    trong chuông là thứ có thể mất hẳn.

    Args:
        ctx: Context job của arq, dùng chung giữa hàm job và hook vòng đời.
        request: Yêu cầu, mang theo channel và số thứ tự.

    Side effects:
        Ghi một khoá vào `ctx`.
    """
    if request.progress_channel:
        ctx[_BELL] = (request.progress_channel, str(request.ordinal))


async def ring_bell(ctx: dict) -> None:
    """Rung tiếng chuông job vừa xong đã đặt sẵn. Đăng ký làm `after_job_end` của worker.

    Chạy sau `finish_job`, nên lúc nó publish thì kết quả **đã** đọc được: một BE nghe
    chuông rồi thu hoạch ngay sẽ thấy đúng câu vừa được báo.

    Mọi lỗi bị nuốt. Công việc đã xong và đã nằm trong store trước khi hàm này chạy, nên để
    một Redis dở chứng ném ra là đánh đổi một câu hỏi thật lấy một lần cập nhật màn hình --
    và tệ hơn: BE đọc một job ném là *"chính job đó đã nổ"*, không hỏi lại, nên vị trí ấy
    mất câu vĩnh viễn.

    Args:
        ctx: Context của job vừa xong.

    Side effects:
        Publish một con số lên Redis, hoặc không làm gì.
    """
    bell = ctx.pop(_BELL, None)
    redis = ctx.get("redis")
    if bell is None or redis is None:
        return
    channel, ordinal = bell
    try:
        await redis.publish(channel, ordinal)
    except Exception:  # noqa: BLE001 -- xem docstring
        logger.warning("could not ring the progress bell on %s", channel, exc_info=True)


async def write_draft_question(ctx: dict, payload: dict) -> dict:
    """Điểm vào arq cho một câu của đề nháp của giáo viên.

    Một câu một job, và đó là thứ làm invariant về timeout đúng trên đường này:
    `tools/check_contract.py` so số lần retry đáng cho một câu với mức kiên nhẫn của BE
    với một job, còn task mà nó thay thế thì nhận tới năm mươi câu trong một job.

    Xong một câu thì **đặt sẵn một tiếng chuông** (ADR-25), và worker rung nó sau khi kết
    quả đã vào store — xem `_arm_bell`. BE đang nghe thu hoạch ngay và đẩy con số mới xuống
    màn hình, thay vì để giáo viên nhìn một khối bước đứng yên.

    Chuông đặt **trước** khi làm việc, nên nó có mặt trên cả ba đường ra -- model viết được,
    model hỏng và lùi về nội dung dọn trước, và máy dev không có API key. Cả ba đều đặt một
    kết quả vào result store, và một màn hình chỉ sống khi có API key thì không phải một màn
    hình sống.

    Args:
        ctx: Context job của arq, nơi tiếng chuông được đặt xuống.
        payload: Một DraftQuestionRequested đã serialise.

    Returns:
        Một DraftQuestionCompleted đã serialise.

    Side effects:
        Ghi tiếng chuông vào `ctx`. AGENT không ghi vào store nào của riêng nó; BE harvest
        kết quả và quyết định nó có được vào đề nháp hay không.
    """
    request = DraftQuestionRequested.model_validate(payload)
    _arm_bell(ctx, request)
    if not llm.enabled():
        return draft_question(request).model_dump(mode="json")

    try:
        # Normalise ở đây, bằng luật của chính AGENT, vì đó là luật mà `_faults` so
        # sánh theo. BE gửi các stem đúng như nó đã lưu: hai bộ normalise buộc phải
        # khớp nhau qua một ranh giới service là một lần lệch nhau đã hẹn trước ngày --
        # và bản đầu tiên của dòng này đã chứng minh điều đó, đem bộ normalise tên lớp
        # của BE so với bộ normalise khoảng trắng của AGENT, nên không stem bị cấm nào
        # khớp được lần nào.
        banned = frozenset(normalise(stem) for stem in request.banned_stems)
        question = await write_question(draft_brief(request), banned)
    except Exception:
        # Nội dung dọn trước, chứ không phải không có gì. Một đề nháp thiếu một câu là
        # chuyện giáo viên hỏi lại một lần; một đề nháp từ chối bắt đầu là một tính năng
        # không hoạt động.
        logger.exception("model could not write question %d of the draft", request.ordinal)
        return draft_question(request).model_dump(mode="json")

    return DraftQuestionCompleted(request_id=request.request_id, question=question).model_dump(
        mode="json"
    )


async def generate_retry_question(ctx: dict, payload: dict) -> dict:
    """Điểm vào arq cho câu hỏi của một lượt chữa lỗi.

    Lùi về bank dọn trước khi model không sinh được một câu giữ đúng hình dạng. Chính
    cái fallback đó là thứ làm cái loop kết thúc: một biến thể viết tay thoả ADR-18 ngay
    từ cách nó được dựng, nên BE luôn có thứ để nhận dù model có cư xử tệ đến đâu. Học
    sinh thì đang mở một lượt trong cả hai trường hợp, và một lượt mở ra trên một câu
    dọn trước vẫn tốt hơn một lượt từ chối mở.

    Args:
        ctx: Context job của arq. Không dùng.
        payload: Một RetryQuestionRequested đã serialise.

    Returns:
        Một RetryQuestionCompleted đã serialise.

    Side effects:
        Không có gì ngoài việc log. AGENT không ghi vào store nào của riêng nó.
    """
    request = RetryQuestionRequested.model_validate(payload)
    if not llm.enabled():
        return retry_question(request).model_dump(mode="json")

    banned = frozenset(normalise(stem) for stem in (*request.previous_stems, request.origin.stem))
    try:
        question = await write_question(retry_brief(request), banned)
    except Exception:
        logger.exception("model could not write round %d; using the bank", request.round_index)
        return retry_question(request).model_dump(mode="json")

    return RetryQuestionCompleted(request_id=request.request_id, question=question).model_dump(
        mode="json"
    )


async def explain(ctx: dict, payload: dict) -> dict:
    """Điểm vào arq cho một lượt nói của trợ lý.

    Publish câu trả lời từng mẩu một trong lúc model viết nó, để học sinh nhìn chữ hiện
    ra thay vì nhìn một khoảng lặng. Các mẩu chỉ là một phép lịch sự: chữ được trả về là
    cả câu trả lời và là thứ được lưu, nên một học sinh tải lại trang chỉ mất phần hoạt
    hình và không mất gì khác.

    Args:
        ctx: Context job của arq. `ctx["redis"]` là connection các mẩu đi ra trên; không
            thứ gì khác trong đó được dùng.
        payload: Một ExplainTurnRequested đã serialise.

    Returns:
        Một ExplainTurnCompleted đã serialise.

    Side effects:
        Publish vào channel Redis mà request gọi tên, khi nó có gọi tên một channel.
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
            # Những chữ đó đã nằm trên màn hình của học sinh rồi. Thay vào bằng câu trả
            # lời dọn trước lúc này sẽ lưu một câu khác với câu các em đã nhìn hiện ra,
            # và các em sẽ gặp nó ở lần tải lại sau mà không có lời giải thích nào. Một
            # câu trả lời bị cắt ngang nhưng khớp với thứ các em đã đọc mới là câu trung
            # thực; hỏi lại thì chỉ một cú bấm.
            return ExplainTurnCompleted(
                request_id=request.request_id, text="".join(said)
            ).model_dump(mode="json")
        # Chưa có gì tới tay ai, nên không có gì để mâu thuẫn với.
        return explain_turn(request).model_dump(mode="json")

    return ExplainTurnCompleted(request_id=request.request_id, text=text).model_dump(mode="json")


def conversation_name(request: ConversationNameRequested) -> ConversationNameCompleted:
    """Đặt tên cho một đoạn chat, không cần model.

    Mock: lấy mấy từ đầu của câu mở đầu. Nó xấu hơn hẳn một cái tên model viết, và nó
    **đúng** — đó là điều kiện duy nhất một mock phải đạt. Cùng đường này chạy khi
    `LLM_ENABLED=false`, nên một bản dev không có API key vẫn có rail đọc được.

    Args:
        request: Câu mở đầu của đoạn chat.

    Returns:
        Một cái tên ngắn.
    """
    words = request.said.split()
    return ConversationNameCompleted(request_id=request.request_id, title=" ".join(words[:6]))


def plan_report(request: PlanReportRequested) -> PlanReportCompleted:
    """Kể lại một plan đã chạy, không cần model.

    Mock: ghép từ chính `outcomes`. Nó khô hơn hẳn một câu model viết, và nó **đúng** --
    nó không thể nói quá, vì nó không có gì ngoài những dòng BE đã viết.

    Args:
        request: Câu giáo viên đã nhờ và kết quả từng bước.

    Returns:
        Một câu kết.
    """
    done = [one for one in request.outcomes if one.ok]
    broke = next((one for one in request.outcomes if not one.ok), None)
    did = "; ".join(one.title.lower() for one in done)
    if broke is None:
        text = f"Mình đã {did}." if did else "Mình chưa làm được bước nào."
    elif did:
        tail = f" ({broke.detail})" if broke.detail else ""
        text = f"Mình đã {did}, nhưng dừng ở bước {broke.title.lower()}{tail}."
    else:
        tail = f" ({broke.detail})" if broke.detail else ""
        text = f"Mình chưa làm được bước {broke.title.lower()}{tail}."
    return PlanReportCompleted(request_id=request.request_id, text=text)


async def report_plan(ctx: dict, payload: dict) -> dict:
    """Điểm vào arq cho lời kể sau khi một plan đã chạy.

    Một job riêng, không phải một vòng nữa của `propose_next_step`: đầu vào của nó là kết
    quả của cả plan, không phải một catalog (ADR-25). Một job là một lần gọi model, nên
    invariant về timeout vẫn đúng trên đường này.

    Args:
        ctx: Ngữ cảnh của arq. Không dùng: task này không stream và không chạm Redis.
        payload: `PlanReportRequested` dưới dạng JSON.

    Returns:
        `PlanReportCompleted` dưới dạng JSON. Mọi cách model hỏng đều lùi về mock: lượt chat
        đã chạy xong và đã ghi đủ trước khi task này được gọi, nên một exception từ phần kể
        lại sẽ biến một lượt đã thành công thành một lỗi.

    Raises:
        ValidationError: Khi `payload` không phải một `PlanReportRequested`. Nằm ngoài
            `try` có chủ ý, như ba handler kia: payload do BE tự dựng, nên một payload sai
            hình dạng là lỗi lập trình và phải nổ ở chỗ gần nguyên nhân.
    """
    request = PlanReportRequested.model_validate(payload)
    if not llm.enabled():
        return plan_report(request).model_dump(mode="json")

    try:
        text = await tell_about(request)
    except Exception:
        logger.exception("model failed to report a plan for %s", request.request_id)
        return plan_report(request).model_dump(mode="json")

    return PlanReportCompleted(request_id=request.request_id, text=text).model_dump(mode="json")


async def name_conversation(ctx: dict, payload: dict) -> dict:
    """Điểm vào arq cho việc đặt tên một đoạn chat.

    Args:
        ctx: Ngữ cảnh của arq. Không dùng gì trong đó: task này không stream và không
            chạm Redis.
        payload: `ConversationNameRequested` dưới dạng JSON.

    Returns:
        `ConversationNameCompleted` dưới dạng JSON.
    """
    request = ConversationNameRequested.model_validate(payload)
    if not llm.enabled():
        return conversation_name(request).model_dump(mode="json")

    try:
        title = await name_it(request)
    except Exception:
        logger.exception("model failed to name a conversation")
        return conversation_name(request).model_dump(mode="json")

    return ConversationNameCompleted(request_id=request.request_id, title=title).model_dump(
        mode="json"
    )
