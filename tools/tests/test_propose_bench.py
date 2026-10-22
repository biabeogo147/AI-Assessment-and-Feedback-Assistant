"""Thước đo text model đọc (`unbiased-model-text`): test của **thước**, và luật *câu đo không nằm
trong prompt*.

Luật thứ hai là bài học của `kriky-skill-routing`: câu thử tay *"Tạo đề … chương Hàm số cho lớp 12A,
10 câu"* nằm nguyên văn trong prompt, và câu *"căn bậc 3 của x^2"* nằm nguyên văn trong skill -- một
ca *"đạt"* khi ấy chỉ chứng minh model nhớ được ví dụ. Câu dùng để đo thì không bao giờ được là ví
dụ.
"""

import json
import re
from pathlib import Path

import pytest

from propose_bench.run import be_refuses, foreign_words, score_propose

_TOOLS = Path(__file__).resolve().parents[1]


def _plan(**create: str) -> dict:
    count = create.pop("count", "10")
    return {
        "kind": "plan",
        "text": "Được.",
        "steps": [
            {"tool_name": "create_draft", "args": create, "title": "Tạo đề"},
            {
                "tool_name": "start_drafting",
                "args": {"assessment_id": "{1.assessment_id}", "question_count": count},
                "title": "Soạn câu",
            },
        ],
    }


_EXPECT = {"kind": "plan", "grade": "9", "count": "12", "scope_has": ["bậc hai"]}


def _plannable() -> tuple:
    from be.identity import Asking
    from be.teacher_tools import PHASE_WORK, catalog_for

    return catalog_for(Asking(teacher_id="t", teacher_code="GV", full_name="Cô"), PHASE_WORK)


def test_be_takes_a_well_formed_plan() -> None:
    step = _plan(subject="Toán", grade="9", topic_scope="phương trình bậc hai")

    assert be_refuses(step, _plannable()) == ""


def test_a_plan_the_be_refuses_is_named() -> None:
    """Review T2 (`unbiased-model-text`): thước chấm ý ca không biết luật BE -- tham chiếu sai khuôn
    vẫn "đạt"."""
    step = _plan(subject="Toán", grade="9", topic_scope="phương trình bậc hai")
    step["steps"][1]["args"]["assessment_id"] = "{1.assessment_id} nhé"

    assert be_refuses(step, _plannable())


def test_a_plan_with_every_argument_right_passes() -> None:
    step = _plan(subject="Toán", grade="9", topic_scope="phương trình bậc hai", count="12")

    assert score_propose(_EXPECT, step) == (True, "")


@pytest.mark.parametrize(
    ("create", "why"),
    [
        ({"subject": "Toán", "grade": "lớp 9", "topic_scope": "bậc hai", "count": "12"}, "grade"),
        ({"subject": "Lý", "grade": "9", "topic_scope": "bậc hai", "count": "12"}, "subject"),
        ({"subject": "Toán", "grade": "9", "topic_scope": "hàm số", "count": "12"}, "topic_scope"),
        (
            {"subject": "Toán", "grade": "9", "topic_scope": "bậc hai", "count": "10"},
            "question_count",
        ),
    ],
)
def test_a_wrong_argument_is_named(create: dict, why: str) -> None:
    ok, reason = score_propose(_EXPECT, _plan(**create))

    assert not ok
    assert reason.startswith(why)


def test_a_question_without_words_does_not_pass() -> None:
    assert score_propose({"kind": "ask_clarify"}, {"kind": "ask_clarify", "text": " "})[0] is False


def test_a_content_word_the_teacher_never_said_is_flagged() -> None:
    assert foreign_words("Xin chào Kriky", "Soạn đề đạo hàm") == ["đạo", "hàm"]
    assert foreign_words("Ra 12 câu về phân số", "phân số 12 câu") == []


def test_a_word_that_names_the_task_is_not_copying() -> None:
    """Review T1 (`unbiased-model-text`): *"Kết quả lớp 9A2"* là tên đúng ý cho một câu hỏi kết
    quả."""
    assert foreign_words("Lớp 9A2 làm bài kiểm tra vừa rồi thế nào?", "Kết quả lớp 9A2") == []


def _model_text(document: bool = True) -> list[str]:
    """Mọi text model đọc mà repo này viết ra; `document=False` bỏ phần của document agent."""
    from agent import skill_router, skills
    from agent.graphs import authoring, explain, naming, propose
    from be.identity import Asking
    from be.teacher_tools import PHASE_PLAN, PHASE_WORK, catalog_for
    from document.index import jev, llm

    asking = Asking(teacher_id="t", teacher_code="GV", full_name="Cô")
    specs = [
        spec
        for phase in (PHASE_PLAN, PHASE_WORK)
        for spec in catalog_for(asking, phase, documents=True)
    ]
    texts = [
        propose.prompt.CORE,
        propose.prompt.BOOK_PROCEDURE,
        propose.prompt.LIBRARY,
        authoring.prompt.SYSTEM,
        explain.prompt.SYSTEM,
        naming.prompt.SYSTEM,
        skill_router._INSTRUCTIONS,
    ]
    if document:
        texts += [
            llm._BANNER_PROMPT,
            llm._SUMMARY_SYSTEM,
            jev._ROLE_INSTRUCTIONS,
            jev._LEVEL_INSTRUCTIONS,
            *jev._ROLE_CRITERIA.values(),
            *jev._LEVEL_CRITERIA.values(),
        ]
    texts += [skill.body + skill.description for skill in skills.every()]
    # Schema của structured output **cũng** là text model đọc: pydantic gửi docstring của class và
    # mô tả của field (review T1, `unbiased-model-text` -- `SolutionMethod` từng mang *"ví dụ 'xét
    # dấu đạo hàm'"*).
    from contracts import GeneratedQuestion

    texts += [
        json.dumps(kind.model_json_schema(), ensure_ascii=False)
        for kind in (propose.proposal._Proposal, GeneratedQuestion)
    ]
    # Câu BE ghi vào lịch sử chat hay gửi kèm lý do từ chối, model đọc lại ở lượt sau.
    from be import notices, teacher_chat

    texts += [
        teacher_chat._BOOK_SCOPE_MISSING,
        teacher_chat._BOOK_NOT_READY,
        notices.CEILING_REACHED,
        notices.REPORT_MISSING,
    ]
    texts += [spec.description + json.dumps(spec.arguments, ensure_ascii=False) for spec in specs]
    return [text.casefold() for text in texts]


def _measured_sentences() -> list[str]:
    cases = json.loads((_TOOLS / "propose_bench" / "cases.json").read_text(encoding="utf-8"))
    said = [row[1] for case in cases["propose"] for row in case["history"] if row[0] == "teacher"]
    said += [case["text"] for case in cases["name"]]
    routing = json.loads((_TOOLS / "skill_bench" / "cases.json").read_text(encoding="utf-8"))
    said += [row[1] for case in routing for row in case["history"] if row[0] == "teacher"]
    return sorted({one.casefold() for one in said if len(one) > 12})


def _grams(text: str, size: int = 5) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.casefold())
    return {tuple(words[at : at + size]) for at in range(len(words) - size + 1)}


def _shared(sentence: str) -> list[str]:
    """Những cụm 5 chữ liên tiếp của câu đo xuất hiện trong text model đọc.

    So **cụm**, không so cả câu: *"căn bậc 3 của x^2 được viết vào đề như thế nào?"* và ví dụ *"căn
    bậc 3 của x^2 viết vào đề thế nào?"* khác vài chữ mà vẫn là một câu.
    """
    model = set().union(*(_grams(text) for text in _model_text()))
    return [" ".join(gram) for gram in sorted(_grams(sentence) & model)]


# Câu đo đã biết là đang trùng một ví dụ -- việc của T2 trong `unbiased-model-text`. `strict`: gỡ ví
# dụ mà quên gỡ dòng này thì test đỏ (XPASS), không lặng lẽ xanh mãi.
_KNOWN_TO_FIX: set[str] = set()


@pytest.mark.parametrize(
    "sentence",
    [
        pytest.param(
            one,
            marks=pytest.mark.xfail(strict=True, reason="plan 4c T2 bỏ ví dụ trùng câu đo"),
        )
        if one in _KNOWN_TO_FIX
        else one
        for one in _measured_sentences()
    ],
)
def test_no_measured_sentence_is_an_example_in_model_text(sentence: str) -> None:
    assert _shared(sentence) == []


def test_an_intermediate_read_of_the_right_chapter_also_passes() -> None:
    expect = {
        "any_of": [
            {"kind": "plan", "nodes": "7"},
            {"kind": "call_tool", "tool": "get_chapter", "args": {"node": "7"}},
        ]
    }
    right = {"kind": "call_tool", "tool_name": "get_chapter", "tool_args": {"node": "7"}}
    wrong = {"kind": "call_tool", "tool_name": "get_chapter", "tool_args": {"node": ""}}

    assert score_propose(expect, right)[0] is True
    assert score_propose(expect, wrong)[0] is False


def test_a_question_with_too_few_choices_is_named() -> None:
    step = {"kind": "ask_clarify", "text": "Bao nhiêu câu?", "choices": ["10 câu", "Khác"]}

    assert score_propose({"kind": "ask_clarify", "min_choices": 4}, step) == (
        False,
        "chỉ 2 phương án",
    )


# Tên của một chủ đề Toán cụ thể. Text model đọc không được mang cái nào (`unbiased-model-text`):
# một ví dụ nội dung là thứ model chép, và một prompt bám một chương làm ca chương khác tệ đi --
# baseline đo 9/54 ca soạn đề khác chương nêu được plan. Ký hiệu chung (`\frac`, `\sqrt`) thì không
# phải chủ đề.
_TOPICS = (
    "đạo hàm",
    "tích phân",
    "nguyên hàm",
    "hàm số",
    "lượng giác",
    "logarit",
    "biến thiên",
    "xét dấu",
    "hạ bậc",
    "phân số",
    "tập hợp",
    "thập phân",
    "la mã",
    "số tự nhiên",
    "vectơ",
    "xác suất",
    "căn bậc",
)


@pytest.mark.parametrize("topic", _TOPICS)
def test_kriky_text_names_no_math_topic(topic: str) -> None:
    assert not [text[:80] for text in _model_text(document=False) if topic in text]


def test_document_agent_text_names_no_math_topic() -> None:
    """`unbiased-model-text` T4: tiêu chí Jev và hai prompt dựng cây cũng không gọi tên chủ đề Toán
    nào."""
    assert not [topic for topic in _TOPICS if any(topic in text for text in _model_text())]


def test_agent_and_be_agree_on_which_tools_read_documents() -> None:
    """`DOCUMENT_READS` của AGENT và `_DOCUMENT_READS` của BE phải là một bộ (review T2,
    `unbiased-model-text`).

    BE dùng bộ này để mở tool mục lục cho đoạn chat từng đọc tài liệu; AGENT dùng nó để biết lượt
    nào còn đang chọn sách và chèn `BOOK_PROCEDURE`. Hai service không import nhau, nên bộ được
    chép ở hai nơi: BE thêm một tool đọc tài liệu mà quên AGENT thì kết quả của tool ấy không mở
    thủ tục sách, và model soạn đề không sách ngay sau khi vừa đọc mục lục.
    """
    from agent.graphs.propose.books import DOCUMENT_READS as agent_reads
    from be.teacher_chat import _DOCUMENT_READS as be_reads

    assert agent_reads == be_reads


def test_agent_be_and_fe_agree_on_the_other_choice() -> None:
    """Chữ của lối "Khác" là một (`unbiased-model-text` T3; từ 13/10/2026 là lối gõ FE tự vẽ).

    FE vẽ "Khác…" và lọc chữ "Khác" khỏi nút đã lưu của đoạn chat cũ; BE loại "Khác" model tự
    viết khỏi nút, và đọc nút cũ (`_rows_in_play`); AGENT không đếm nó là một lựa chọn. Lệch một
    chữ thì đoạn chat cũ hiện hai nút "Khác", một trong hai gửi đi đúng chữ "Khác".
    """
    from agent.graphs.propose.clarify import _OTHER
    from be.teacher_chat import OTHER_CHOICE

    chat = (
        _TOOLS.parent / "services" / "fe" / "src" / "screens" / "teacher" / "Chat.tsx"
    ).read_text(encoding="utf-8")
    fe = re.search(r'^const OTHER = "([^"]*)";$', chat, re.MULTILINE)

    assert fe is not None
    assert _OTHER == OTHER_CHOICE == fe.group(1)


@pytest.mark.parametrize("label", ["t5-sau-thu-vien", "sau-T2b", "(t3)"])
def test_a_label_with_a_task_code_is_refused_before_any_model_call(
    monkeypatch: pytest.MonkeyPatch, label: str
) -> None:
    """Luật đặt tên của `AGENTS.md`: nhãn thành tên thư mục kết quả, sống lâu hơn plan."""
    import sys

    from propose_bench import run

    def no_model(*_: object, **__: object) -> None:
        raise AssertionError("bộ đo gọi model trước khi kiểm nhãn")

    monkeypatch.setattr(run.asyncio, "run", no_model)
    monkeypatch.setattr(sys, "argv", ["propose_bench", "--label", label, "--parts", "propose"])

    with pytest.raises(SystemExit, match="mã task"):
        run.main()


def _outline(count: int, purpose: str = "new", nodes: tuple[int, ...] = ()) -> dict:
    return {
        "kind": "outline",
        "text": "Dàn ý.",
        "tool_args": {"for": purpose},
        "outline": [
            {"questions": count, "knowledge": "K", "approach": "A", "source_nodes": list(nodes)}
        ],
    }


def test_an_outline_scores_on_its_total_its_purpose_and_its_sources() -> None:
    """`draft-outline`: dàn ý đúng số câu, đúng việc, bài nguồn trong các node ca cho phép."""
    expect = {"kind": "outline", "count": "6", "nodes_in": [7, 8]}

    assert score_propose(expect, _outline(6, nodes=(8,))) == (True, "")
    assert score_propose(expect, _outline(5, nodes=(8,)))[1] == "tổng câu 5"
    assert score_propose(expect, _outline(6, nodes=(99,)))[0] is False
    assert score_propose(expect, _outline(6))[0] is False
    assert score_propose({"kind": "outline"}, _outline(6, purpose="more"))[1] == "for 'more'"


def test_a_replacing_outline_scores_on_the_question_it_replaces() -> None:
    step = {**_outline(1, purpose="replace"), "tool_args": {"for": "replace", "question": "2"}}

    assert score_propose({"kind": "outline", "for": "replace", "question": "2"}, step)[0] is True
    assert score_propose({"kind": "outline", "for": "replace", "question": "3"}, step)[1] == (
        "question '2'"
    )
