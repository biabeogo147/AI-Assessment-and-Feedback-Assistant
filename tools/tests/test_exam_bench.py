"""Thước của `exam_bench` (plan `exam-quality-bench`): phép chấm thuần phải đúng trước khi con số
của nó được tin. Không gọi model."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from exam_bench import rate, score
from exam_bench.run import solve_votes, summarise
from ocr_bench.run import task_code_in

_CASES = Path(__file__).resolve().parents[1] / "exam_bench" / "cases.json"
_RATERS = rate.RATERS


# ------------------------------------------------------------------------------- đồng thuận


def test_majority_ignores_blank_votes_and_calls_a_tie_undecided() -> None:
    assert score.majority([True, True, False]) is True
    assert score.majority([False, None, False]) is False
    assert score.majority([True, None, False]) is None
    assert score.majority([None, None, None]) is None


def test_fleiss_kappa_matches_a_hand_computed_table() -> None:
    """Bốn mục, ba rater. Tính tay: P̄ = (1 + 1/3 + 1 + 1/3) / 4 = 2/3; p(có) = 6/12 = 1/2;
    Pe = (1/2)² + (1/2)² = 1/2; κ = (2/3 - 1/2) / (1 - 1/2) = 1/3."""
    rows = [[True, True, True], [True, True, False], [False, False, False], [True, False, False]]

    assert score.fleiss_kappa(rows) == pytest.approx(1 / 3)
    assert score.agreement(rows) == pytest.approx(2 / 3)


def test_ac1_stays_high_where_kappa_collapses_on_a_lopsided_criterion() -> None:
    """Nghịch lý tỉ lệ (review pha 3): 19 mục nhất trí *có*, 1 mục lệch một phiếu. κ thấp dù rater
    gần như nhất trí; AC1 thì không. Tính tay: P̄ = (19 + 1/3)/20 = 58/60; p(có) = 59/60;
    Pe(AC1) = 2·(59/60)·(1/60); AC1 = (58/60 - Pe) / (1 - Pe)."""
    rows = [[True, True, True]] * 19 + [[True, True, False]]
    p = 59 / 60
    pe = 2 * p * (1 - p)
    expected = (58 / 60 - pe) / (1 - pe)

    assert score.gwet_ac1(rows) == pytest.approx(expected)
    assert score.gwet_ac1(rows) > 0.9
    assert score.fleiss_kappa(rows) < 0.1


def test_fleiss_kappa_is_undefined_when_every_vote_agrees_on_one_side() -> None:
    assert score.fleiss_kappa([[True, True, True]] * 5) is None


def test_agreement_measures_skip_rows_with_a_blank_vote() -> None:
    rows = [[True, True, True], [False, False, False], [True, None, False]]

    assert score.fleiss_kappa(rows) == pytest.approx(1.0)
    assert score.full_rows(rows) == 2


def test_cohen_kappa_of_perfect_and_of_chance_agreement() -> None:
    assert score.cohen_kappa([True, False, True, False], [True, False, True, False]) == 1.0
    # Đồng thuận 2/4 với hai bên đều 50% có: đúng bằng ngẫu nhiên.
    assert score.cohen_kappa([True, True, False, False], [True, False, True, False]) == 0.0


def test_coverage_uses_the_smaller_of_questions_and_gold_lines() -> None:
    # Bốn dòng vàng, đề 3 câu: phủ 3 dòng là đủ.
    assert score.coverage([{0}, {1}, {2}], gold_count=4, question_count=3) == (1.0, 0)
    # Một mục ngoài mọi dòng là ngoài khung; chỉ số dòng ngoài khoảng không tính.
    assert score.coverage([{0}, set(), {7}], gold_count=3, question_count=5) == (1 / 3, 2)


# ------------------------------------------------------------------------------- lỗi bằng code


def _question(*options: tuple[str, bool], stem: str = "Tính $2^3$.") -> dict:
    return {
        "stem": stem,
        "options": [
            {"label": "ABCD"[at], "text": text, "is_correct": right, "error_label": None}
            for at, (text, right) in enumerate(options)
        ],
    }


def test_code_flaws_catch_the_machine_readable_writing_faults() -> None:
    assert score.code_flaws(_question(("$8$", True), ("$6$", False), ("$9$", False))) == []
    assert "phuong-an-trung" in score.code_flaws(
        _question(("$8$", True), ("$ 8 $", False), ("$9$", False))
    )
    assert "tat-ca-deu-dung" in score.code_flaws(
        _question(("$8$", True), ("$6$", False), ("Tất cả các phương án trên đều đúng", False))
    )
    assert "tat-ca-deu-dung" in score.code_flaws(
        _question(("$8$", True), ("$6$", False), ("Cả A và B", False))
    )
    long_key = "Bằng $8$ vì nhân ba thừa số $2$ với nhau theo định nghĩa luỹ thừa"
    assert "dap-an-dai-bat-thuong" in score.code_flaws(
        _question((long_key, True), ("$6$", False), ("$9$", False))
    )
    assert "hai-cau-hoi" in score.code_flaws(
        _question(("$8$", True), ("$6$", False), stem="Tính $2^3$? Và $3^2$?")
    )
    copied = "Câu nào là mệnh đề: Hôm nay trời đẹp quá!; Mấy giờ rồi?; Số 7 là số nguyên tố."
    assert "de-chep-phuong-an" in score.code_flaws(
        _question(
            ("Số 7 là số nguyên tố.", True),
            ("Mấy giờ rồi?", False),
            ("Hôm nay trời đẹp quá!", False),
            stem=copied,
        )
    )


def test_a_set_and_its_element_are_not_the_same_option() -> None:
    """Review pha 1 (`agent-split-bench`): $\\{6\\} \\in A$ và $6 \\in A$ là hai phương án khác
    nhau; ngoặc nhóm của LaTeX thì vẫn bỏ."""
    assert (
        score.code_flaws(
            _question(("$6 \\in A$", True), ("$\\{6\\} \\in A$", False), ("$6 \\notin A$", False))
        )
        == []
    )
    assert "phuong-an-trung" in score.code_flaws(
        _question(("$x^{2}$", True), ("$x^2$", False), ("$x^3$", False))
    )


def test_code_flaws_leave_ordinary_statements_and_quoted_questions_alone() -> None:
    """Review pha 3: *"Tất cả học sinh … đều"* là phương án nhiễu kinh điển của bài phủ định ∀, và
    dấu `?` trong chữ trích không phải câu hỏi thứ hai."""
    negation = _question(
        ("Có một học sinh lớp 10A không thích môn Toán", True),
        ("Tất cả học sinh lớp 10A đều không thích môn Toán", False),
        ("Không có học sinh nào lớp 10A thích môn Toán", False),
        stem='Phủ định của mệnh đề "Tất cả học sinh lớp 10A đều thích môn Toán" là?',
    )
    quoted = _question(
        ("Không", True),
        ("Có", False),
        stem="Câu 'Bạn có học bài không?' có phải là một mệnh đề?",
    )

    assert score.code_flaws(negation) == []
    assert score.code_flaws(quoted) == []


# ------------------------------------------------------------------------------- phiếu giải mù


def _solved(*right: str) -> dict:
    return {"work": "", "options": [{"label": one, "correct": one in right} for one in "ABC"]}


def test_solve_votes_read_the_key_from_the_marked_options() -> None:
    question = _question(("$8$", True), ("$6$", False), ("$9$", False))
    votes = {
        _RATERS[0]: _solved("A"),
        _RATERS[1]: _solved("A", "C"),
        _RATERS[2]: None,
    }

    right, single = solve_votes(votes, question)

    assert right == [True, True, None]
    assert single == [True, False, None]


def test_a_label_written_with_its_option_text_still_counts() -> None:
    """Pilot 12/11/2026: Sonnet có lúc ghi nhãn *"B. 5"* -- vẫn là phiếu của nhãn B."""
    question = _question(("$8$", True), ("$6$", False), ("$9$", False))
    wordy = {
        "work": "",
        "options": [
            {"label": "A. 8", "correct": True},
            {"label": "(b)", "correct": False},
            {"label": "C", "correct": False},
        ],
    }

    right, single = solve_votes(dict.fromkeys(_RATERS, wordy), question)

    assert right == [True, True, True] and single == [True, True, True]


def test_a_solve_that_skips_an_option_is_a_blank_vote() -> None:
    question = _question(("$8$", True), ("$6$", False), ("$9$", False))
    partial = {"work": "", "options": [{"label": "A", "correct": True}]}

    right, single = solve_votes(dict.fromkeys(_RATERS, partial), question)

    assert right == [None, None, None] and single == [None, None, None]


def test_the_blind_solve_prompt_shows_no_key_no_error_and_no_solution() -> None:
    question = _question(("$8$", True), ("$6$", False), ("$9$", False))
    question["options"][1]["error_label"] = "cộng thay vì nhân"
    question["methods"] = [{"title": "Nhân", "body": "2·2·2 = 8, chọn A"}]
    question["learning_objective"] = "Luỹ thừa"

    shown = rate.solve_prompt({"grade": "6"}, question)

    for leak in ("ĐÁP ÁN", "cộng thay vì nhân", "chọn A", "Luỹ thừa", "is_correct"):
        assert leak not in shown


# ------------------------------------------------------------------------------- gộp chỉ số

_CASE = {"id": "c", "grade": "6", "count": 2, "ask": "x", "gold": ["một", "hai"]}
_ITEM = {"index": 1, "gold": [1, 2], "specific": True, "formulas_right": True, "fits": True}
_ITEM = {**_ITEM, "distinct": True}
_GOOD_REVIEW = {
    "flaws": [],
    "follows_item": True,
    "distractors": [{"label": "B", "reproduces": True}],
}


def _paper(questions: int = 2, arm: str = "agent", run: int = 1, gate: str = "") -> dict:
    rows = []
    for ordinal in range(1, questions + 1):
        question = _question(("$8$", True), (f"${ordinal + 1}$", False), ("$9$", False))
        question["stem"] = f"Câu {ordinal}: tính $2^3$."
        question["options"][1]["error_label"] = "cộng thay vì nhân"
        rows.append({"ordinal": ordinal, "item": 0, "part": ordinal, "question": question})
    items = [{"questions": questions, "knowledge": "k", "formulas": [], "approach": "a"}]
    return {"arm": arm, "case": "c", "run": run, "gate": gate, "items": items, "questions": rows}


def _ratings(paper: dict, solve: dict | None = None, review: dict | None = None) -> list[dict]:
    head = {"arm": paper["arm"], "case": paper["case"], "run": paper["run"]}
    rows = [{**head, "kind": "outline", "votes": dict.fromkeys(_RATERS, {"items": [_ITEM]})}]
    for row in paper["questions"]:
        where = {**head, "ordinal": row["ordinal"]}
        rows.append(
            {**where, "kind": "solve", "votes": dict.fromkeys(_RATERS, solve or _solved("A"))}
        )
        rows.append(
            {**where, "kind": "review", "votes": dict.fromkeys(_RATERS, review or _GOOD_REVIEW)}
        )
    return rows


def test_a_paper_where_every_check_passes_is_usable_clean_and_covered() -> None:
    paper = _paper()

    arm = summarise({"c": _CASE}, [paper], _ratings(paper))["arms"]["agent"]

    assert (arm["usable"], arm["wanted"], arm["clean"]) == (2, 2, 1)
    assert (arm["items_ok"], arm["items"]) == (1, 1)
    assert arm["coverage"] == [1.0]
    assert (arm["faithful"], arm["distractors"]) == (2, 2)


@pytest.mark.parametrize(
    ("solve", "review", "why"),
    [
        (_solved("B"), None, "khoá sai"),
        (_solved("A", "C"), None, "hai phương án đúng"),
        (None, {**_GOOD_REVIEW, "flaws": ["hai-yeu-cau-trong-mot-cau"]}, "lỗi nặng"),
    ],
)
def test_each_failed_check_makes_a_question_unusable(solve, review, why) -> None:
    paper = _paper()

    arm = summarise({"c": _CASE}, [paper], _ratings(paper, solve, review))["arms"]["agent"]

    assert arm["usable"] == 0, why
    assert arm["clean"] == 0, why


def test_a_code_flaw_makes_a_question_unusable_without_the_panel() -> None:
    paper = _paper()
    paper["questions"][0]["question"]["options"][2]["text"] = "Tất cả các phương án trên"

    arm = summarise({"c": _CASE}, [paper], _ratings(paper))["arms"]["agent"]

    assert arm["usable"] == 1
    assert arm["code"] == {"tat-ca-deu-dung": 1}


def test_following_the_item_is_reported_apart_from_q1() -> None:
    paper = _paper()
    review = {**_GOOD_REVIEW, "follows_item": False}

    arm = summarise({"c": _CASE}, [paper], _ratings(paper, None, review))["arms"]["agent"]

    assert (arm["usable"], arm["usable_follow"]) == (2, 0)


def test_a_gated_paper_counts_its_questions_as_unusable_and_its_coverage_as_zero() -> None:
    """Review pha 3: đề trượt cổng từng không vào mẫu số -- đề hỏng càng nhiều, Q1 càng đẹp."""
    good = _paper()
    gated = _paper(questions=0, run=2, gate="không ra dàn ý: kind=say")

    arm = summarise({"c": _CASE}, [good, gated], _ratings(good))["arms"]["agent"]

    assert (arm["usable"], arm["wanted"]) == (2, 4)
    assert arm["coverage"] == [1.0, 0.0]
    assert arm["gated"] == 1


def test_a_short_paper_is_not_clean_and_its_missing_questions_count_against_q1() -> None:
    """Naive trả ít câu hơn số xin: mẫu số vẫn là số câu xin, và đề ấy không sạch."""
    short = _paper(questions=1, arm="naive")
    for row in short["questions"]:
        row["item"] = None

    arm = summarise({"c": _CASE}, [short], _ratings(short)[1:])["arms"]["naive"]

    assert (arm["usable"], arm["wanted"], arm["got"], arm["clean"]) == (1, 2, 1, 0)


def test_an_unrated_paper_is_left_out_of_every_figure() -> None:
    rated = _paper()
    unrated = _paper(run=2)

    arm = summarise({"c": _CASE}, [rated, unrated], _ratings(rated))["arms"]["agent"]

    assert (arm["papers"], arm["unrated"], arm["wanted"]) == (1, 1, 2)


def test_q2_counts_only_distractors_of_questions_whose_key_holds() -> None:
    paper = _paper()

    arm = summarise({"c": _CASE}, [paper], _ratings(paper, _solved("B")))["arms"]["agent"]

    assert arm["distractors"] == 0


# ------------------------------------------------------------------------------- chi phí, cache


def test_spend_counts_cached_reads_at_the_models_own_share_and_stops_before_the_cap() -> None:
    spend = rate.Spend(cap=1.0, reserve=0.5)
    usage = SimpleNamespace(
        input_tokens=100_000, output_tokens=10_000, cache_read_input_tokens=100_000
    )

    used = spend.add("claude-opus-5-5", usage)

    # 100k vào × 4 + 100k đọc cache × 4 × 0,05 + 10k ra × 20, mỗi triệu token.
    assert used == pytest.approx(0.4 + 0.02 + 0.2)
    with pytest.raises(rate.BudgetSpent):
        spend.check()


def test_the_cache_key_changes_with_the_schema_the_rater_reads(monkeypatch) -> None:
    before = rate.cache_key("claude-opus-5-5", "solve", "đề")

    class Wider(rate.SolveVerdict):
        note: str = ""

    monkeypatch.setitem(rate._KINDS, "solve", (rate.SOLVE_SYSTEM, Wider))

    assert rate.cache_key("claude-opus-5-5", "solve", "đề") != before


# ------------------------------------------------------------------------------- ca


def test_cases_are_well_formed_and_ids_carry_no_task_code() -> None:
    cases = json.loads(_CASES.read_text(encoding="utf-8"))

    assert len({one["id"] for one in cases}) == len(cases)
    for one in cases:
        assert not task_code_in(one["id"]), one["id"]
        assert one["gold"] and all(line.strip() for line in one["gold"])
        assert 1 <= one["count"] <= 10
        assert str(one["count"]) in one["ask"]


def test_summarise_does_not_change_what_it_reads() -> None:
    paper = _paper()
    ratings = _ratings(paper)
    before = copy.deepcopy((paper, ratings))

    summarise({"c": _CASE}, [paper], ratings)

    assert (paper, ratings) == before


# ------------------------------------------------- nhánh agent: AGENT chia việc (ADR-38)

_JOB = {"questions": 1, "knowledge": "k1", "formulas": ["$a$"], "approach": "a1"}


class RateLimitError(Exception):
    """Cùng tên lớp lỗi hạ tầng của SDK: `run._infra` đọc tên."""


def _good_question(stem: str) -> object:
    from contracts import GeneratedOption, GeneratedQuestion, SolutionMethod

    return GeneratedQuestion(
        stem=stem,
        options=(
            GeneratedOption(label="A", text="đúng", is_correct=True),
            GeneratedOption(label="B", text="sai B", error_label="lỗi B"),
            GeneratedOption(label="C", text="sai C", error_label="lỗi C"),
        ),
        methods=(SolutionMethod(title="1", body="..."), SolutionMethod(title="2", body="...")),
        learning_objective="x",
    )


def _outlined(monkeypatch, split: object) -> tuple[list[str], list]:
    """`agent_paper` không gọi model: lượt dàn ý, bước chia việc và job soạn câu đều giả."""
    import agent.graphs.authoring as authoring
    import agent.graphs.propose.split as agent_split
    from contracts import NextStepCompleted
    from exam_bench import run

    async def outline_of(case: dict) -> tuple[object, dict]:
        step = NextStepCompleted(
            request_id="r",
            kind="outline",
            text="**Câu 1–2**: k1",
            outline_questions=2,
            tool_args={"subject": "Toán", "grade": "6", "topic_scope": "x"},
        )
        return step, {"asked": "", "refusals": [], "gate": ""}

    seen: list = []

    async def split_outline(plan: object, request: object) -> object:
        seen.append(request)
        if isinstance(split, BaseException):
            raise split
        return plan.model_copy(update={"split": split})

    briefs: list[str] = []

    async def write_question(brief: str, banned: frozenset[str]) -> object:
        briefs.append(brief)
        return _good_question(f"Câu hỏi số {len(briefs)}")

    monkeypatch.setattr(run, "outline_of", outline_of)
    monkeypatch.setattr(agent_split, "split_outline", split_outline)
    monkeypatch.setattr(authoring, "write_question", write_question)
    return briefs, seen


@pytest.mark.asyncio
async def test_the_agent_branch_drafts_each_question_on_the_job_agent_split_for_it(
    monkeypatch,
) -> None:
    from contracts import Split, SplitJob
    from exam_bench import run

    split = Split(
        note="Câu 1 lo A, câu 2 lo B.",
        jobs=(
            SplitJob(part="Câu 1", knowledge="k1", approach="a1"),
            SplitJob(part="Câu 2", knowledge="k2", approach="a2"),
        ),
    )
    briefs, seen = _outlined(monkeypatch, split)

    paper = await run.agent_paper({**_CASE, "count": 2})

    # Lịch sử như lượt thật: lời xin, dàn ý có số câu, lời đồng ý -- đúng luật *ngay trước* của
    # bước chia việc (`split._shown`).
    from agent.graphs.propose.split import _shown

    told, _ = _shown(seen[0])
    assert [turn.kind for turn in seen[0].history] == ["teacher", "outline", "teacher"]
    assert told is not None and told.tool_result["total"] == 2
    # Mục dựng bằng đúng hàm của BE: có nhãn phần.
    assert [item["part"] for item in paper["items"]] == ["Câu 1", "Câu 2"]

    assert paper["split"] == {"note": "Câu 1 lo A, câu 2 lo B.", "given": 2, "wanted": 2}
    assert [item["knowledge"] for item in paper["items"]] == ["k1", "k2"]
    assert [(row["item"], row["part"]) for row in paper["questions"]] == [(0, 1), (1, 1)]
    assert "k1" in briefs[0] and "a2" in briefs[1]


@pytest.mark.asyncio
async def test_an_outline_agent_could_not_split_is_a_gated_paper(monkeypatch) -> None:
    from agent.graphs.propose.split import SplitFailed
    from exam_bench import run

    _outlined(monkeypatch, SplitFailed("thiếu"))

    paper = await run.agent_paper({**_CASE, "count": 2})

    assert paper["gate"].startswith("không chia được") and paper["questions"] == []
    # Đề chia hỏng vẫn vào mẫu số của *số job đúng*.
    assert paper["split"] == {"note": "", "given": 0, "wanted": 2}


@pytest.mark.asyncio
async def test_a_split_lost_to_the_network_is_left_out_like_an_unrated_paper(monkeypatch) -> None:
    from exam_bench import run

    _outlined(monkeypatch, RateLimitError("chậm"))

    paper = await run.agent_paper({**_CASE, "count": 2})
    arm = summarise({"c": _CASE}, [{**paper, "run": 1}], [])["arms"]["agent"]

    assert paper["infra"] == "hạ tầng: RateLimitError" and not paper["gate"]
    assert (arm["papers"], arm["unrated"]) == (0, 1)


@pytest.mark.asyncio
async def test_drafting_retries_a_failed_slot_with_the_kept_stems_banned_and_skips_infra(
    monkeypatch,
) -> None:
    """`_draft_and_harvest` qua nhiều đợt: ô 2 hỏng một lần, gặp lỗi hạ tầng một lần, rồi đạt."""
    import agent.graphs.authoring as authoring
    from exam_bench import run

    seen: list[tuple[int, frozenset[str]]] = []
    script = {
        1: [_good_question("Câu một")],
        2: [None, RateLimitError(), _good_question("Câu hai")],
    }

    async def write_question(brief: str, banned: frozenset[str]) -> object:
        ordinal = 1 if "kiến thức một" in brief else 2
        seen.append((ordinal, banned))
        answer = script[ordinal].pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    monkeypatch.setattr(authoring, "write_question", write_question)
    slots = {
        1: {"item_knowledge": "kiến thức một", "item_approach": "a"},
        2: {"item_knowledge": "kiến thức hai", "item_approach": "a"},
    }
    meta = {1: {"item": 0, "part": 1}, 2: {"item": 1, "part": 1}}
    brief = {"subject": "Toán", "grade": "6", "topic_scope": "x"}

    rows = await run._draft_and_harvest(_CASE, brief, slots, meta, 2)

    assert [row["question"]["stem"] for row in rows] == ["Câu một", "Câu hai"]
    # Một lần hỏng thật, một lần hạ tầng: chỉ lần hỏng thật tốn một lần soạn.
    assert rows[1]["attempts"] == 2 and rows[1]["faults"][-1] == "hạ tầng: RateLimitError"
    later = [banned for ordinal, banned in seen[2:] if ordinal == 2]
    assert len(later) == 2 and all(any("một" in stem for stem in banned) for banned in later)


class _Panel:
    """Thay `rate.Panel`: ghi lại thứ rater sẽ đọc, không gọi model."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, str]] = []

    async def all_three(self, kind: str, content: str) -> list:
        self.asked.append((kind, content))
        return [None, None, None]


def _split_paper(usable_jobs: int = 2, gate: str = "") -> dict:
    """Một đề nhánh `agent` từ ADR-38: mục là job AGENT chia, kèm lời chia việc."""
    paper = _paper(gate=gate)
    paper["items"] = [] if gate else [_JOB, {**_JOB, "knowledge": "k2"}]
    paper["jobs"] = paper["items"]
    paper["said"] = "md"
    paper["split"] = {"note": "chia", "given": 0 if gate else 2, "wanted": 2}
    for at, row in enumerate(paper["questions"]):
        row["item"], row["part"] = at, 1
        if at >= usable_jobs:
            row["question"]["options"][0]["is_correct"] = False
            row["question"]["options"][1]["is_correct"] = True
    if gate:
        paper["questions"] = []
    return paper


@pytest.mark.asyncio
async def test_rating_a_split_paper_shows_the_jobs_and_each_questions_own_job() -> None:
    from exam_bench import run

    paper = _split_paper()
    paper["items"][1] = {**_JOB, "knowledge": "k riêng của câu 2"}
    panel = _Panel()

    await run.rate_paper(panel, _CASE, paper)

    kinds = [kind for kind, _ in panel.asked]
    assert kinds == ["outline", "split", "solve", "review", "solve", "review"]
    split_text = panel.asked[1][1]
    assert "Câu 2 (" in split_text and "Câu 3 (" not in split_text and "md" in split_text
    assert "k riêng của câu 2" in panel.asked[5][1] and "k riêng" not in panel.asked[3][1]


def _split_ratings(paper: dict, faithful: list[bool], covered: bool) -> list[dict]:
    rows = _ratings(paper)
    verdict = {
        "jobs": [
            {"index": at, "faithful": one, "single": True, "distinct": at != 2, "why": ""}
            for at, one in enumerate(faithful, 1)
        ],
        "covered": covered,
        "why": "",
    }
    head = {"arm": paper["arm"], "case": paper["case"], "run": paper["run"]}
    return [{**head, "kind": "split", "votes": dict.fromkeys(_RATERS, verdict)}, *rows]


def test_a_split_paper_reports_faithful_jobs_coverage_and_q1() -> None:
    paper = _split_paper(usable_jobs=1)

    summary = summarise({"c": _CASE}, [paper], _split_ratings(paper, [True, False], True))
    arm = summary["arms"]["agent"]

    assert (arm["jobs_faithful"], arm["jobs_apart"], arm["jobs"]) == (1, 1, 2)
    assert (arm["covered"], arm["split_papers"], arm["count_right"]) == (1, 1, 1)
    # Câu 2 khoá B mà panel giải ra A: khoá sai, không dùng được.
    assert (arm["usable"], arm["wanted"], arm["key_wrong"]) == (1, 2, 1)
    assert "Q1d bám job" in summary["criteria"] and "Q1d bám mục" not in summary["criteria"]
    assert summary["papers"][0]["note"] == "chia"


def test_an_unsplit_paper_counts_its_questions_as_unusable_and_its_outline_as_uncovered() -> None:
    paper = _split_paper(gate="không chia được: hỏng")

    arm = summarise({"c": _CASE}, [paper], [])["arms"]["agent"]

    assert (arm["usable"], arm["wanted"], arm["gated"]) == (0, 2, 1)
    assert (arm["covered"], arm["split_papers"], arm["count_right"]) == (0, 1, 0)


def test_a_paper_whose_ratings_came_back_blank_is_unrated_not_unusable() -> None:
    """Pilot `agent-split-bench`: hết credit giữa lượt, lời chấm trống bị tính thành câu hỏng."""
    good = _paper()
    starved = _paper(run=2)
    ratings = _ratings(good) + [
        {**row, "votes": dict.fromkeys(_RATERS)} for row in _ratings(starved)
    ]
    # Một rater trống thì hai phiếu còn lại vẫn ra đa số: đề vẫn tính.
    one_blank = _ratings(_paper(run=3))
    one_blank[1] = {**one_blank[1], "votes": {**one_blank[1]["votes"], _RATERS[0]: None}}

    arm = summarise({"c": _CASE}, [good, starved, _paper(run=3)], ratings + one_blank)["arms"]

    assert (arm["agent"]["papers"], arm["agent"]["unrated"], arm["agent"]["usable"]) == (2, 1, 4)


# ------------------------------------------------------------- hai model (plan `bench-two-models`)


def test_spend_reads_langchain_usage_where_cached_tokens_sit_inside_input_tokens() -> None:
    """LangChain gộp token cache **vào** `input_tokens`; SDK Anthropic để chúng ngoài."""
    spend = rate.Spend(cap=10.0)
    usage = {
        "input_tokens": 300_000,
        "output_tokens": 100_000,
        "input_token_details": {"cache_read": 200_000},
    }

    used = spend.add("gpt-6-luna", usage, call=False)

    # 100k vào mới × 0,10 + 200k đọc cache × 0,10 × 0,1 + 100k ra × 0,50, mỗi triệu token.
    assert used == pytest.approx(0.01 + 0.002 + 0.05)
    assert spend.calls == 0 and spend.by_model == {"gpt-6-luna": pytest.approx(used)}


@pytest.mark.parametrize(
    ("model", "why"),
    [("claude-opus-5-5", "là một rater"), ("gpt-4o-mini", "chưa có giá")],
)
def test_a_generator_that_cannot_be_measured_stops_before_any_call(model: str, why: str) -> None:
    from exam_bench import run

    with pytest.raises(SystemExit, match=why):
        run.check_generator(model)


def test_both_models_of_the_bench_can_generate() -> None:
    from exam_bench import run

    run.check_generator("claude-haiku-5-5")
    run.check_generator("gpt-6-luna")


class _Structured:
    """`with_structured_output(include_raw=True)` giả: trả đúng một câu trả lời đã dựng sẵn."""

    def __init__(self, answer: dict, seen: list) -> None:
        self._answer = answer
        self._seen = seen

    async def ainvoke(self, messages: list) -> dict:
        self._seen.append(messages)
        return self._answer


class _Chat:
    def __init__(self, answer: dict, seen: list) -> None:
        self._answer = answer
        self._seen = seen

    def with_structured_output(
        self, schema: type, include_raw: bool = False, method: str = "function_calling"
    ) -> _Structured:
        assert include_raw
        # Ép tool ở cả hai model (pha 5b): Haiku qua Stali không giữ JSON schema.
        assert method == "function_calling"
        return _Structured(
            self._answer(schema) if callable(self._answer) else self._answer, self._seen
        )


@pytest.mark.asyncio
async def test_the_naive_branch_asks_the_pinned_model_once_with_a_whole_paper_budget(
    monkeypatch,
) -> None:
    """Nhánh `naive` đi qua `agent.llm.standalone`: cùng model và cấu hình Kriky, trần cả đề."""
    from agent import llm
    from exam_bench import run

    built: list[dict] = []
    seen: list = []

    def standalone(**overrides: object) -> _Chat:
        built.append(overrides)
        return _Chat(
            lambda schema: {
                "parsed": schema(questions=[_good_question("Câu một"), _good_question("Câu hai")]),
                "raw": None,
                "parsing_error": None,
            },
            seen,
        )

    monkeypatch.setattr(llm, "standalone", standalone)

    paper = await run.naive_paper(_CASE)

    assert built == [run._NAIVE_CALL] and built[0]["max_tokens"] == 16000
    assert len(seen) == 1 and "x" in seen[0][0][1]
    assert [row["question"]["stem"] for row in paper["questions"]] == ["Câu một", "Câu hai"]
    assert paper["got_count"] == 2 and not paper["gate"]


@pytest.mark.asyncio
async def test_a_naive_paper_the_model_cut_short_is_gated_with_its_stop_reason(monkeypatch) -> None:
    from langchain_core.messages import AIMessage

    from agent import llm
    from exam_bench import run

    raw = AIMessage(content="", response_metadata={"finish_reason": "length"})
    answer = {"parsed": None, "raw": raw, "parsing_error": ValueError("cụt")}
    monkeypatch.setattr(llm, "standalone", lambda **_: _Chat(answer, []))

    paper = await run.naive_paper(_CASE)

    assert paper["gate"] == "không parse được: 'length'" and paper["questions"] == []


@pytest.mark.asyncio
async def test_generator_tokens_are_counted_even_inside_nested_calls_and_parallel_papers(
    monkeypatch,
) -> None:
    """Callback bắt mọi lời gọi lồng (graph AGENT) và không đếm lẫn giữa các đề song song; mọi lời
    gọi tính theo giá model đã ghim, dù provider trả tên kèm ngày."""
    import asyncio

    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.runnables import RunnableLambda

    from exam_bench import run

    def model(tokens: int) -> GenericFakeChatModel:
        reply = AIMessage(
            content="ok",
            usage_metadata={
                "input_tokens": tokens,
                "output_tokens": 10,
                "total_tokens": tokens + 10,
            },
            response_metadata={"model_name": "gpt-6-luna-2026-11-01"},
        )
        return GenericFakeChatModel(messages=iter([reply, reply]))

    async def agent_paper(case: dict) -> dict:
        chat = model(case["tokens"])
        # Một lời gọi trực tiếp, một lời gọi lồng trong runnable khác -- như node của graph.
        await chat.ainvoke("a")

        async def node(text: str) -> object:
            return await chat.ainvoke(text)

        await RunnableLambda(node).ainvoke("b")
        return {"arm": "agent", "case": case["id"], "gate": "", "items": [], "questions": []}

    monkeypatch.setattr(run, "agent_paper", agent_paper)
    spend = rate.Spend(cap=10.0)

    one, two = await asyncio.gather(
        run.generated("agent", {"id": "a", "tokens": 1000}, "gpt-6-luna", spend),
        run.generated("agent", {"id": "b", "tokens": 5000}, "gpt-6-luna", spend),
    )

    assert one["tokens"] == {"input": 2000, "output": 20}
    assert two["tokens"] == {"input": 10000, "output": 20}
    assert one["model"] == "gpt-6-luna" and set(spend.by_model) == {"gpt-6-luna"}
    assert spend.usd == pytest.approx((12_000 * 0.10 + 40 * 0.50) / 1e6)


def test_the_report_names_the_generator_and_how_long_outlines_took() -> None:
    from exam_bench import run

    papers = [
        {
            "arm": "agent",
            "case": "c",
            "run": 1,
            "gate": "x",
            "items": [],
            "questions": [],
            "outline_seconds": 4.0,
        },
        {
            "arm": "agent",
            "case": "c",
            "run": 2,
            "gate": "x",
            "items": [],
            "questions": [],
            "outline_seconds": 12.0,
        },
        {
            "arm": "agent",
            "case": "c",
            "run": 3,
            "gate": "",
            "items": [],
            "questions": [],
            "infra": "hạ tầng: APITimeoutError",
            "outline_seconds": 20.5,
        },
    ]
    summary = summarise({"c": _CASE}, papers, [])
    arm = summary["arms"]["agent"]
    text = run.report(summary, rate.Spend(cap=1.0), 1.0, [], config="openai/gpt-6-luna · x")

    assert arm["infra"] == 1 and arm["outline_seconds"] == [4.0, 12.0, 20.5]
    assert "sinh đề openai/gpt-6-luna · x" in text.splitlines()[0]
    assert "(hỏng hạ tầng 1)" in text and "trung vị 12.0 s, lâu nhất 20.5 s" in text
