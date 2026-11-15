"""Bench chất lượng ra đề: dàn ý và đề lần đầu (plan `exam-quality-bench`).

Cùng lệ với `propose_bench`: không chạy trong `.\\dev.ps1 check` vì gọi model thật; thứ `check` canh
là test của thước (`tools/tests/test_exam_bench.py`).

Hai nhánh trên cùng bộ ca (`cases.json`, mỗi ca một bài SGK, vàng là khung *KIẾN THỨC, KĨ NĂNG*):

- `agent`: đúng đường của Kriky (ADR-38). `propose` tới lượt dàn ý -- dàn ý hỏng thì lý do về lại
  model như BE làm (`teacher_chat`, tối đa `_MOST_OUTLINE_REFUSALS` lần); Kriky hỏi lại thì giáo
  viên giả trả lời một lần bằng đủ mục. Giáo viên giả đồng ý, và AGENT chia lời dàn ý thành job
  (`agent.graphs.propose.split.split_outline`, đúng bước của lượt thật); mỗi ô câu dựng
  `DraftQuestionRequested` từ job của nó bằng `be.drafting.item_fields`; soạn **theo đợt** như BE:
  đợt đầu mọi ô song song, thu hoạch theo thứ tự ô bằng chính các phép kiểm của BE, ô hỏng soạn lại
  cả đợt với `banned` là mọi câu đã vào đề, tới `_MOST_ATTEMPTS` lần soạn. Lỗi hạ tầng (rate limit,
  timeout, mạng) không tính là một lần soạn.
- `naive`: một lời gọi tới cùng model sinh đề với cùng cấu hình (`.env`), *"soạn đề N câu…"*, cùng
  luật hình dạng câu (ADR-18) trong prompt, cùng phép kiểm, không soạn lại.

Model sinh đề chọn bằng `--model provider:model` (`tools/bench_model.py`, plan `bench-two-models`):
cùng một `.env` đo được `anthropic:claude-haiku-5-5` lẫn `openai:gpt-6-luna`; thinking, effort và
`reasoning_effort` vẫn lấy từ `.env`, và dòng đầu `report.txt` ghi chúng. Model sinh đề không được
là một rater. Token model sinh đề (cả hai nhánh, đếm qua LangChain) cộng vào chi phí và trần.

Rồi panel ba rater (`rate.py`) chấm; `score.py` gộp phiếu. Chỉ số:

- P1 độ phủ (dàn ý trượt cổng tính 0), P2 mục duyệt được nguyên -- chỉ nhánh `agent`; từ ADR-38
  "mục" là job AGENT chia từ lời dàn ý (dàn ý không còn mục có cấu trúc).
- S1 job trung thành với lời dàn ý, S1b job tả đúng một câu và khác câu anh em, S2 dàn ý phủ đủ --
  lời chấm `split`, chỉ nhánh `agent`.
- Q1 câu dùng được nguyên = giải mù ra khoá ∧ đúng một phương án đúng ∧ không lỗi nặng ∧ không lỗi
  code, **trên mọi câu được xin** (đề trượt cổng, ô hỏng, câu naive không trả đều tính không dùng
  được). Cùng phép cho hai nhánh; Q1+ (cộng *bám mục*) chỉ nhánh `agent`, báo riêng.
- Q2 phương án nhiễu trung thực, chỉ trên câu panel giải ra đúng khoá.

Báo cáo kèm đồng thuận panel từng tiêu chí: Fleiss' kappa, Gwet AC1, đồng thuận thô -- pilot đo
**thước** trước khi đo agent.

Mỗi lượt ghi vào `data/results/run-<n>/exam-<nhãn>-<model>/`: `outlines.jsonl`, `questions.jsonl`,
`ratings.jsonl`, `summary.json`, `report.txt`.

Dùng:
    python -m exam_bench.run --model openai:gpt-6-luna --label khoi --only menh-de --agent-runs 1 \\
        --naive-runs 1
    python -m exam_bench.run --model anthropic:claude-haiku-5-5 --label hai-model --cap 20
"""

import argparse
import asyncio
import itertools
import json
import logging
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import bench_model
from exam_bench import rate, score

_CASES = Path(__file__).resolve().parent / "cases.json"
_RUNS = Path("data") / "results"
# Lỗi không phải của model: không tiêu một lần soạn.
_INFRA = ("RateLimit", "Timeout", "Connection", "Overloaded", "InternalServer")

logger = logging.getLogger("exam_bench")


# ------------------------------------------------------------------------------------ sinh đề


def _request(case: dict, history: tuple = ()):
    from be.identity import Asking
    from be.teacher_tools import PHASE_PLAN, PHASE_WORK, catalog_for
    from contracts import NextStepRequested, TurnRecord

    asking = Asking(teacher_id="bench", teacher_code="GV-BENCH", full_name="Cô Hà")
    return NextStepRequested(
        request_id=case["id"],
        teacher_name=asking.full_name,
        history=history or (TurnRecord(kind="teacher", text=case["ask"]),),
        catalog=catalog_for(asking, PHASE_PLAN, documents=False, bound=False),
        plannable=catalog_for(asking, PHASE_WORK, documents=False, bound=False),
    )


def answer_back(case: dict) -> str:
    """Lời giáo viên trả một câu hỏi lại: đủ môn, khối, số câu, phạm vi, như thẻ hỏi lại gộp."""
    return (
        f"Môn Toán, lớp {case['grade']}, {case['count']} câu, đúng phạm vi mình vừa nói, "
        "không có tài liệu."
    )


# Lời BE trả model khi nó nêu plan soạn đề mà chưa có dàn ý nào giáo viên đã xem (`guard_drafting`).
_NO_OUTLINE_YET = "chưa có dàn ý nào giáo viên đã xem: nêu dàn ý (kind=outline) trước khi soạn"


async def outline_of(case: dict) -> tuple[object | None, dict]:
    """Lượt dàn ý của nhánh `agent`, như BE chạy nó: hỏi lại được trả lời một lần, dàn ý hỏng thì lý
    do về lại model, tối đa `_MOST_OUTLINE_REFUSALS` lần.

    Returns:
        `(bước dàn ý đã qua cổng, hay None; ghi chép: asked, refusals, gate, history)` --
        `history` là lịch sử tới trước lượt dàn ý, kể cả lượt hỏi lại và lời đáp của giáo viên giả.
    """
    from agent.graphs.propose import propose
    from be.outline import validate
    from be.teacher_chat import _MOST_OUTLINE_REFUSALS
    from contracts import TurnRecord

    history = [TurnRecord(kind="teacher", text=case["ask"])]
    notes: dict = {"asked": "", "refusals": [], "gate": ""}
    for _ in range(2 + _MOST_OUTLINE_REFUSALS):
        step = await _propose_like_agent(propose, _request(case, tuple(history)), notes)
        if step.kind == "ask_clarify" and not notes["asked"]:
            notes["asked"] = step.text
            history += [
                TurnRecord(kind="assistant", text=step.text),
                TurnRecord(kind="teacher", text=answer_back(case)),
            ]
            continue
        if step.kind == "outline":
            wrong = validate(step.outline_questions, step.outline_nodes, None) or (
                None if step.text.strip() else "lời dàn ý trống: viết lời trình bày dàn ý"
            )
        elif step.kind == "plan":
            wrong = _NO_OUTLINE_YET
        else:
            notes["gate"] = f"không ra dàn ý: kind={step.kind}"
            return None, notes
        if wrong is None:
            notes["history"] = tuple(history)
            return step, notes
        notes["refusals"].append(wrong)
        if len(notes["refusals"]) >= _MOST_OUTLINE_REFUSALS or (
            len(notes["refusals"]) >= 2 and notes["refusals"][-1] == notes["refusals"][-2]
        ):
            notes["gate"] = f"BE từ chối dàn ý {len(notes['refusals'])} lần: {wrong}"
            return None, notes
        history.append(
            TurnRecord(kind="tool_result", tool_name="outline", tool_result={"error": wrong})
        )
    notes["gate"] = "hết lượt mà chưa có dàn ý"
    return None, notes


async def _propose_like_agent(propose, request, notes: dict):
    """Một lượt `propose`, lỗi hạ tầng thì thử lại như AGENT (`LLM_MAX_ATTEMPTS`).

    Ở hệ thống thật, AGENT hỏi model một job tới `LLM_MAX_ATTEMPTS` lần trước khi bỏ. Bench gọi
    thẳng `propose` nên tự thử lại, chỉ với lỗi hạ tầng (timeout, rate limit, mạng): pha 6b (Haiku
    qua Stali, 15/11/2026) một lời gọi dàn ý quá trần 20 s làm đổ cả lượt. Lỗi khác vẫn ném ra như
    cũ.

    Raises:
        Exception: Lỗi hạ tầng còn nguyên sau mọi lần thử, hay mọi lỗi không phải hạ tầng.
    """
    from agent.config import get_settings

    attempts = max(1, get_settings().llm_max_attempts)
    for attempt in range(1, attempts + 1):
        try:
            return await propose(request)
        except Exception as exc:
            if not _infra(exc) or attempt == attempts:
                raise
            notes["infra_retries"] = notes.get("infra_retries", 0) + 1
    raise AssertionError("không tới được")


def _harvest(question, seen: set[str], gists: list[frozenset]) -> tuple[object | None, str]:
    """Các phép kiểm lúc BE thu hoạch một câu (`be.drafting.harvest`). Trả câu đã gộp hay lý do."""
    from be.agent_gateway import AgentError, validate_question
    from be.drafting import _comparable, _gist, names_another_option, tidy_options

    tidy = tidy_options(question)
    if tidy is None:
        return None, "phương án trùng nhau, còn quá ít sau khi gộp"
    try:
        validate_question(tidy)
    except AgentError as exc:
        return None, f"sai hình dạng ADR-18: {exc}"[:160]
    if names_another_option(tidy):
        return None, "lời giải chọn phương án khác phương án khoá"
    if _comparable(tidy.stem) in seen:
        return None, "đề trùng một câu đã có"
    twin = _gist(tidy.stem)
    if twin and any(twin & other for other in gists):
        return None, "đề gần trùng một câu đã có"
    return tidy, ""


def _infra(exc: BaseException) -> bool:
    return any(word in type(exc).__name__ for word in _INFRA)


async def agent_paper(case: dict) -> dict:
    """Một đề của nhánh `agent`: dàn ý, giáo viên giả đồng ý, AGENT chia việc (ADR-38), rồi các câu
    soạn và thu hoạch theo đợt như BE."""
    from agent.graphs.propose.split import split_outline
    from be.drafting import item_fields, split_items
    from contracts import NextStepCompleted, PlanStep, TurnRecord

    paper: dict = {"arm": "agent", "case": case["id"], "gate": "", "items": [], "questions": []}
    started = time.monotonic()
    try:
        step, notes = await outline_of(case)
    except Exception as exc:  # noqa: BLE001 -- một đề không ra dàn ý được, không cả bench
        bench_model.stop_if_out_of_money(exc)
        if not _infra(exc):
            raise
        # Hết lần thử mà vẫn lỗi hạ tầng: đề chưa đo được, như đề chưa chấm.
        paper["infra"] = f"hạ tầng: {type(exc).__name__}"
        return paper
    # Từ lời xin tới dàn ý qua cổng, kể cả lượt hỏi lại và lời BE trả về: cái giáo viên chờ.
    paper["outline_seconds"] = round(time.monotonic() - started, 1)
    paper["asked_back"] = bool(notes["asked"])
    paper["asked"] = notes["asked"]
    paper["refusals"] = notes["refusals"]
    paper["infra_retries"] = notes.get("infra_retries", 0)
    if step is None:
        paper["gate"] = notes["gate"]
        return paper
    paper["said"] = step.text
    args = step.tool_args
    brief = {
        "subject": str(args.get("subject") or "").strip(),
        "grade": str(args.get("grade") or "").strip(),
        "topic_scope": str(args.get("topic_scope") or "").strip(),
    }
    paper["brief_from_model"] = all(brief.values())
    # BE lấp chỗ trống từ dàn ý trước (`_filled_brief`); đoạn chat của bench không có dàn ý trước,
    # nên lấp từ ca -- và ghi lại để báo cáo đếm.
    brief = {
        "subject": brief["subject"] or "Toán",
        "grade": brief["grade"] or case["grade"],
        "topic_scope": brief["topic_scope"] or case["ask"],
    }
    paper["brief"] = brief
    # Giáo viên giả đồng ý: đúng lịch sử lượt thật gửi AGENT, và chính bước chia việc của AGENT.
    shown = {"version": 1, "first": 1, "for": "new", "total": step.outline_questions}
    # Lịch sử như lượt thật: lời xin, lượt hỏi lại và lời đáp nếu có, dàn ý, lời đồng ý.
    agreed = _request(
        case,
        (
            *notes.get("history", (TurnRecord(kind="teacher", text=case["ask"]),)),
            TurnRecord(kind="outline", text=step.text, tool_result=shown),
            TurnRecord(kind="teacher", text="oke"),
        ),
    )
    plan = NextStepCompleted(
        request_id=case["id"],
        kind="plan",
        steps=(PlanStep(tool_name="start_drafting", title="Soạn câu hỏi theo dàn ý"),),
    )
    # Đề chia hỏng vẫn mang `split` (given 0): nó vào mẫu số của *số job đúng* và S2, không lọt
    # khỏi báo cáo (review pha 4, plan `markdown-outline-agent-split`).
    paper["split"] = {"note": "", "given": 0, "wanted": shown["total"]}
    try:
        split = (await split_outline(plan, agreed)).split
    except Exception as exc:  # noqa: BLE001 -- một đề không chia được, không cả bench
        bench_model.stop_if_out_of_money(exc)
        if _infra(exc):
            # Lỗi hạ tầng không phải lỗi chia: đề chưa đo được, như đề chưa chấm.
            paper["infra"] = f"hạ tầng: {type(exc).__name__}"
            return paper
        paper["gate"] = f"không chia được: {exc!r}"[:200]
        return paper
    if split is None:
        paper["gate"] = "AGENT không chia dàn ý"
        return paper
    paper["split"] = {"note": split.note, "given": len(split.jobs), "wanted": shown["total"]}
    # Đúng hàm `teacher_chat.guard_drafting` dùng để đưa job cho `drafting.fire`.
    paper["items"] = split_items(split)
    paper["jobs"] = paper["items"]
    held = SimpleNamespace(outline=paper["items"])
    slots = {at + 1: item_fields(held, at, 1) for at in range(len(paper["items"]))}
    meta = {at + 1: {"item": at, "part": 1} for at in range(len(paper["items"]))}
    paper["questions"] = await _draft_and_harvest(case, brief, slots, meta, len(slots))
    return paper


async def _draft_and_harvest(
    case: dict, brief: dict, slots: dict[int, dict], meta: dict[int, dict], of_total: int
) -> list[dict]:
    """Soạn và thu các ô theo đợt như BE (`be.drafting.fire` rồi `harvest`): đợt đầu mọi ô song
    song, thu theo thứ tự ô bằng các phép kiểm của BE, ô hỏng soạn lại cả đợt với `banned` là mọi
    câu đã vào đề, tới `_MOST_ATTEMPTS` lần soạn.

    Args:
        case: Ca bench.
        brief: Môn, khối, phạm vi của đề.
        slots: Ô → các trường `item_*` của `DraftQuestionRequested`.
        meta: Ô → các trường ghi vào hàng kết quả (`item`, `part`).
        of_total: Đề có bao nhiêu câu.

    Returns:
        Mỗi ô một hàng, theo thứ tự ô: `question` là câu đã qua phép kiểm hay `None`.
    """
    from agent.graphs.authoring import draft_brief, normalise, write_question
    from be.drafting import _MOST_ATTEMPTS, _comparable, _gist
    from contracts import DraftQuestionRequested

    async def write(ordinal: int, banned: tuple[str, ...]):
        asked = DraftQuestionRequested(
            request_id=f"{case['id']}:{ordinal}",
            subject=brief["subject"],
            grade=brief["grade"],
            topic_scope=brief["topic_scope"],
            ordinal=ordinal,
            of_total=of_total,
            banned_stems=banned,
            **slots[ordinal],
        )
        try:
            # Như handler của AGENT: `banned` normalise bằng luật của chính AGENT.
            return await write_question(
                draft_brief(asked), frozenset(normalise(stem) for stem in banned)
            )
        except Exception as exc:  # noqa: BLE001 -- một ô hỏng, không cả đề
            return exc

    rows = {
        ordinal: {"ordinal": ordinal, **meta[ordinal], "attempts": 0, "faults": []}
        for ordinal in slots
    }
    kept: dict[int, object] = {}
    stems: list[str] = []  # stem thô của các câu đã vào đề, như BE lưu
    seen: set[str] = set()
    gists: list[frozenset] = []
    pending = sorted(slots)
    rounds = 0
    while pending and rounds < _MOST_ATTEMPTS + 2:
        rounds += 1
        answers = await asyncio.gather(*(write(ordinal, tuple(stems)) for ordinal in pending))
        again = []
        for ordinal, answer in zip(pending, answers, strict=True):
            row = rows[ordinal]
            if isinstance(answer, BaseException):
                bench_model.stop_if_out_of_money(answer)
            if isinstance(answer, BaseException) and _infra(answer):
                row["faults"].append(f"hạ tầng: {type(answer).__name__}")
                again.append(ordinal)
                continue
            row["attempts"] += 1
            if isinstance(answer, BaseException) or answer is None:
                row["faults"].append(f"model không soạn được: {answer!r}"[:160])
            else:
                good, why = _harvest(answer, seen, gists)
                if good is not None:
                    kept[ordinal] = good
                    stems.append(good.stem)
                    seen.add(_comparable(good.stem))
                    if twin := _gist(good.stem):
                        gists.append(twin)
                    continue
                row["faults"].append(why)
                row["rejected"] = answer.model_dump(mode="json")
            if row["attempts"] < _MOST_ATTEMPTS:
                again.append(ordinal)
        pending = again
    done = []
    for ordinal in sorted(slots):
        row = rows[ordinal]
        row["question"] = kept[ordinal].model_dump(mode="json") if ordinal in kept else None
        done.append(row)
    return done


_NAIVE = (
    "Soạn một đề kiểm tra trắc nghiệm môn Toán theo yêu cầu của giáo viên dưới đây, đúng số câu "
    "được xin. Mỗi câu có 4 phương án, đúng một phương án đúng (is_correct), không hai phương án "
    "nào cùng chữ. Mỗi phương án sai ghi error_label là lỗi học sinh mắc phải để chọn nó. methods "
    "gồm ít nhất hai cách giải khác nhau. learning_objective là kiến thức câu kiểm. Viết công thức "
    "bằng LaTeX trong cặp $.\n\nYêu cầu: {ask}"
)


# Một lời gọi ra cả đề: trần ra như bản gọi thẳng SDK trước plan `bench-two-models`; trần thời gian
# và số lần SDK tự thử lại riêng của nhánh này -- trần 20 s của Kriky là cho một câu, không cả đề.
_NAIVE_CALL = {"max_tokens": 16000, "timeout": 300, "max_retries": 4}

# Mọi lượt trước plan `bench-two-models` sinh đề bằng Haiku (khi ấy khoá cứng) và không ghi model:
# `--from-run` coi đề không mang `model` là của model này (review pha 5).
LEGACY_GENERATOR = "claude-haiku-5-5"


async def naive_paper(case: dict) -> dict:
    """Một đề của nhánh `naive`: một lời gọi, cùng model và cấu hình sinh đề, cùng phép kiểm.

    Đi qua `agent.llm.standalone`: cùng provider, key, thinking/effort hay `reasoning_effort` của
    `.env` như Kriky, chỉ trần ra và trần thời gian là của một lời gọi ra cả đề.
    """
    from pydantic import BaseModel

    from agent import llm
    from contracts import GeneratedQuestion

    class Paper(BaseModel):
        questions: list[GeneratedQuestion]

    paper: dict = {"arm": "naive", "case": case["id"], "gate": "", "items": [], "questions": []}
    paper["prompt"] = _NAIVE
    # Ép tool ở cả hai provider (plan `bench-two-models` pha 5b): Haiku qua Stali không giữ
    # `output_config.format` (JSON schema) -- trả chữ thường, 6/6 lần thử 15/11/2026 --, mà ép tool
    # thì chạy, như đường của Kriky. Hai model cùng một cách để so được với nhau; không còn so thẳng
    # với nhánh naive của các lượt trước (khi ấy là JSON schema).
    model = llm.standalone(**_NAIVE_CALL).with_structured_output(
        Paper, include_raw=True, method="function_calling"
    )
    started = time.monotonic()
    try:
        answer = await model.ainvoke([("human", _NAIVE.format(ask=case["ask"]))])
    except Exception as exc:  # noqa: BLE001
        bench_model.stop_if_out_of_money(exc)
        if _infra(exc):
            paper["infra"] = f"hạ tầng: {type(exc).__name__}"
        else:
            paper["gate"] = f"model không soạn được: {exc!r}"[:200]
        return paper
    paper["seconds"] = round(time.monotonic() - started, 1)
    parsed = answer.get("parsed")
    if parsed is None:
        meta = getattr(answer.get("raw"), "response_metadata", None) or {}
        stop = meta.get("stop_reason") or meta.get("finish_reason") or answer.get("parsing_error")
        paper["gate"] = f"không parse được: {stop!r}"[:200]
        return paper
    from be.drafting import _comparable, _gist

    seen: set[str] = set()
    gists: list[frozenset] = []
    for ordinal, question in enumerate(parsed.questions, start=1):
        kept, why = _harvest(question, seen, gists)
        row = {"ordinal": ordinal, "item": None, "part": 1, "attempts": 1}
        row["faults"] = [why] if why else []
        row["question"] = kept.model_dump(mode="json") if kept is not None else None
        if kept is None:
            row["rejected"] = question.model_dump(mode="json")
        paper["questions"].append(row)
        if kept is not None:
            seen.add(_comparable(kept.stem))
            if twin := _gist(kept.stem):
                gists.append(twin)
    paper["got_count"] = len(parsed.questions)
    return paper


async def generated(arm: str, case: dict, model: str, spend: rate.Spend) -> dict:
    """Một đề của một nhánh, kèm token model sinh đề đã tiêu.

    Token đếm bằng callback của LangChain, nên bắt được mọi lời gọi lồng trong graph của AGENT
    (dàn ý, chia việc, từng câu) lẫn lời gọi của nhánh `naive`. Callback gắn vào context của task
    này, nên các đề sinh song song không đếm lẫn của nhau. Mọi lời gọi tính theo giá của `model`:
    provider có thể trả tên model kèm ngày (`gpt-6-luna-2026-…`), mà process chỉ có một model.

    Args:
        arm: `agent` hay `naive`.
        case: Ca bench.
        model: Id model sinh đề đã ghim, có giá trong `rate`.
        spend: Chi phí của lượt, cộng thêm token này.

    Returns:
        Đề, có `model` và `tokens` (vào, ra).
    """
    from langchain_core.callbacks import get_usage_metadata_callback

    with get_usage_metadata_callback() as counted:
        paper = await (agent_paper(case) if arm == "agent" else naive_paper(case))
    tokens = {"input": 0, "output": 0}
    for usage in counted.usage_metadata.values():
        spend.add(model, usage, call=False)
        tokens["input"] += usage.get("input_tokens", 0) or 0
        tokens["output"] += usage.get("output_tokens", 0) or 0
    paper["model"] = model
    paper["tokens"] = tokens
    return paper


def check_generator(model: str) -> None:
    """Dừng trước mọi lời gọi khi model sinh đề không đo được. Hàm thuần.

    Raises:
        SystemExit: Model là một rater (panel phải độc lập với model nó chấm), hay bench chưa có
            giá của nó (trần chi phí không tính được).
    """
    if model in rate.RATER_MODELS:
        raise SystemExit(f"--model {model!r} là một rater: panel phải độc lập với model sinh đề")
    if not rate.priced(model):
        raise SystemExit(f"--model {model!r}: chưa có giá trong exam_bench/rate.py (_PRICES)")


# ------------------------------------------------------------------------------------- chấm


async def rate_paper(panel: rate.Panel, case: dict, paper: dict) -> list[dict]:
    """Mọi lời chấm cho một đề: dàn ý và lời chia việc (nhánh `agent`), rồi mỗi câu một lời giải
    mù và một lời duyệt -- câu được duyệt với job của nó làm mục.

    Raises:
        BudgetSpent: Khi chạm trần giữa chừng -- đề này coi như chưa chấm.
    """
    head = {"arm": paper["arm"], "case": case["id"], "run": paper["run"]}
    jobs = []
    if paper["items"] and not paper["gate"]:
        content = rate.outline_prompt(case, paper["items"])
        jobs.append(({**head, "kind": "outline"}, panel.all_three("outline", content)))
    given = [job for job in paper.get("jobs") or [] if job is not None]
    if given and paper.get("said") and not paper["gate"]:
        content = rate.split_rating_prompt(case, paper["said"], given)
        jobs.append(({**head, "kind": "split"}, panel.all_three("split", content)))
    for row in paper["questions"]:
        question = row["question"]
        if question is None:
            continue
        # Lượt `agent-md` cũ (run-131..134) để `items` rỗng và mục ở `jobs`.
        items = paper["items"] or paper.get("jobs") or []
        item = items[row["item"]] if row["item"] is not None else None
        where = {**head, "ordinal": row["ordinal"]}
        jobs.append(
            (
                {**where, "kind": "solve"},
                panel.all_three("solve", rate.solve_prompt(case, question)),
            )
        )
        content = rate.review_prompt(case, question, item, row.get("part", 1))
        jobs.append(({**where, "kind": "review"}, panel.all_three("review", content)))
    verdicts = await asyncio.gather(*(job for _, job in jobs), return_exceptions=True)
    for votes in verdicts:
        if isinstance(votes, BaseException):
            raise votes
    return [
        {**meta, "votes": dict(zip(rate.RATERS, votes, strict=True))}
        for (meta, _), votes in zip(jobs, verdicts, strict=True)
    ]


# ------------------------------------------------------------------------------------- gộp


def _key(question: dict) -> str:
    return next((one["label"] for one in question["options"] if one.get("is_correct")), "")


def label(raw: str) -> str:
    """Nhãn phương án như rater viết, về một chữ cái: *"B. 5"*, *"(c)"* thành `B`, `C`. Pilot
    12/11/2026: Sonnet có lúc chép cả chữ phương án vào nhãn, và phiếu ấy thành phiếu trống. Hàm
    thuần."""
    for char in str(raw).strip().upper():
        if char.isalpha():
            return char
    return ""


def solve_votes(votes: dict, question: dict) -> tuple[list, list]:
    """Phiếu *khoá nằm trong các phương án rater giải ra đúng* và *đúng một phương án đúng, là
    khoá*, theo thứ tự `RATERS`; cả hai đọc từ `options` của lời giải mù. Lời giải không phủ đủ nhãn
    của đề là phiếu trống. Hàm thuần."""
    key = _key(question)
    labels = {label(one["label"]) for one in question["options"]}
    right, single = [], []
    for model in rate.RATERS:
        verdict = votes.get(model)
        marked = {
            label(one["label"]): bool(one["correct"]) for one in (verdict or {}).get("options", [])
        }
        if verdict is None or not labels <= set(marked):
            right.append(None)
            single.append(None)
            continue
        true = {one for one in labels if marked[one]}
        right.append(key in true)
        single.append(true == {key})
    return right, single


def _item_votes(outline: dict, at: int, field: str) -> list:
    votes = []
    for model in rate.RATERS:
        found = next(
            (one for one in (outline.get(model) or {}).get("items", []) if one["index"] == at),
            None,
        )
        votes.append(None if found is None else found[field])
    return votes


def _new_arm() -> dict:
    return {
        "papers": 0,
        "gated": 0,
        "unrated": 0,
        # Đề hỏng vì hạ tầng (timeout, rate limit, mạng): chưa đo được, nằm trong `unrated`.
        "infra": 0,
        # Giây từ lời xin tới dàn ý qua cổng (nhánh agent): trần `LLM_TIMEOUT_SECONDS` có đủ không.
        "outline_seconds": [],
        "asked_back": 0,
        "refusals": 0,
        "brief_filled": 0,
        "coverage": [],
        "off": 0,
        "items": 0,
        "items_ok": 0,
        "wanted": 0,
        "got": 0,
        "slots_failed": 0,
        "usable": 0,
        "usable_follow": 0,
        "clean": 0,
        "distractors": 0,
        "faithful": 0,
        "key_wrong": 0,
        "many_right": 0,
        "code": {},
        # Bước chia việc của AGENT (ADR-38).
        "split_papers": 0,
        "count_right": 0,
        "covered": 0,
        "jobs": 0,
        "jobs_faithful": 0,
        "jobs_apart": 0,
        "core": 0,
    }


def summarise(cases: dict[str, dict], papers: list[dict], ratings: list[dict]) -> dict:
    """Gộp phiếu thành chỉ số theo nhánh và bảng phiếu theo tiêu chí (cho đồng thuận). Hàm thuần.

    Đề chưa chấm (dừng vì trần) bị loại khỏi mọi chỉ số và đếm riêng; đề trượt cổng **ở lại**: mọi
    câu được xin của nó là câu không dùng được, và dàn ý của nó phủ 0.
    """
    by = {(r["arm"], r["case"], r["run"], r["kind"], r.get("ordinal")): r["votes"] for r in ratings}
    # Một lời chấm mà từ hai rater trở lên trả trống (API hỏng, hết tiền) thì đa số không ra được:
    # đề ấy chưa chấm xong, không phải đề có câu hỏng (pilot `agent-split-bench`: hết credit giữa
    # lượt, bảy đề thành 0 câu dùng được).
    thin = {
        (r["arm"], r["case"], r["run"])
        for r in ratings
        if sum(vote is None for vote in r["votes"].values()) >= 2
    }
    rated = {(r["arm"], r["case"], r["run"]) for r in ratings} - thin
    arms: dict[str, dict] = {}
    criteria: dict[str, list[list]] = {}
    blanks: dict[str, int] = {}

    def table(name: str, votes: list) -> None:
        criteria.setdefault(name, []).append(votes)

    for row in ratings:
        for model, vote in row["votes"].items():
            if vote is None:
                blanks[f"{model} {row['kind']}"] = blanks.get(f"{model} {row['kind']}", 0) + 1

    papers_out = []
    for paper in papers:
        case = cases[paper["case"]]
        arm = arms.setdefault(paper["arm"], _new_arm())
        wanted = case["count"]
        summary = {"arm": paper["arm"], "case": paper["case"], "run": paper["run"]}
        has_rows = (
            any(row["question"] is not None for row in paper["questions"])
            or paper["items"]
            or any(paper.get("jobs") or [])
        )
        key = (paper["arm"], paper["case"], paper["run"])
        if paper.get("outline_seconds") is not None:
            arm["outline_seconds"].append(paper["outline_seconds"])
        arm["infra"] += bool(paper.get("infra"))
        if (
            paper.get("infra")
            or key in thin
            or (not paper["gate"] and has_rows and key not in rated)
        ):
            arm["unrated"] += 1
            summary["unrated"] = True
            papers_out.append(summary)
            continue
        arm["papers"] += 1
        arm["wanted"] += wanted
        arm["asked_back"] += bool(paper.get("asked_back"))
        arm["refusals"] += len(paper.get("refusals") or [])
        arm["brief_filled"] += paper["arm"] == "agent" and not paper.get("brief_from_model", True)
        summary["wanted"] = wanted
        if "split" in paper:
            told = paper["split"]
            arm["split_papers"] += 1
            arm["count_right"] += told["given"] == told["wanted"]
            summary["note"] = told["note"]
            verdict = by.get((paper["arm"], paper["case"], paper["run"], "split", None))
            if verdict is not None:
                covered = [
                    None if verdict.get(m) is None else bool(verdict[m]["covered"])
                    for m in rate.RATERS
                ]
                table("S2 dàn ý phủ đủ", covered)
                arm["covered"] += score.majority(covered) is True
                given = [job for job in paper.get("jobs") or [] if job is not None]
                for at in range(1, len(given) + 1):
                    found = [
                        next(
                            (
                                one
                                for one in (verdict.get(model) or {}).get("jobs", [])
                                if one["index"] == at
                            ),
                            None,
                        )
                        for model in rate.RATERS
                    ]
                    faithful = [None if one is None else bool(one["faithful"]) for one in found]
                    # S1b: job tả đúng một câu VÀ khác các job cùng phần -- thứ người soạn cần
                    # để không đoán mình là câu nào (review pha 1, plan `agent-split-bench`).
                    apart = [
                        None
                        if one is None
                        else bool(one.get("single")) and bool(one.get("distinct"))
                        for one in found
                    ]
                    table("S1 job trung thành", faithful)
                    table("S1b job một câu, khác anh em", apart)
                    arm["jobs"] += 1
                    arm["jobs_faithful"] += score.majority(faithful) is True
                    arm["jobs_apart"] += score.majority(apart) is True
        if paper["gate"]:
            arm["gated"] += 1
            if paper["arm"] == "agent":
                arm["coverage"].append(0.0)
            summary.update(gate=paper["gate"], usable=0, coverage=0.0)
            papers_out.append(summary)
            continue
        outline = by.get((paper["arm"], paper["case"], paper["run"], "outline", None))
        if outline is not None:
            mapped: list[set[int]] = []
            for at in range(1, len(paper["items"]) + 1):
                lines = set()
                gold_votes = _item_votes(outline, at, "gold")
                for line in range(1, len(case["gold"]) + 1):
                    votes = [None if one is None else line in one for one in gold_votes]
                    table("P1 dòng vàng", votes)
                    if score.majority(votes):
                        lines.add(line - 1)
                mapped.append(lines)
                passed = True
                for name, field in (
                    ("D1 cụ thể", "specific"),
                    ("D2 công thức", "formulas_right"),
                    ("D3 vừa phạm vi", "fits"),
                    ("D4 không trùng", "distinct"),
                ):
                    votes = [
                        None if one is None else bool(one)
                        for one in _item_votes(outline, at, field)
                    ]
                    table(name, votes)
                    passed = passed and score.majority(votes) is True
                arm["items"] += 1
                arm["items_ok"] += passed
            covered, off = score.coverage(mapped, len(case["gold"]), wanted)
            arm["coverage"].append(covered)
            arm["off"] += off
            summary["coverage"] = round(covered, 3)
        usable_here = 0
        core_here = 0
        failed_here = 0
        for row in paper["questions"]:
            question = row["question"]
            if question is None:
                arm["slots_failed"] += 1
                failed_here += 1
                continue
            arm["got"] += 1
            key = (paper["arm"], paper["case"], paper["run"])
            solve = by.get((*key, "solve", row["ordinal"]), {})
            review = by.get((*key, "review", row["ordinal"]), {})
            right, single = solve_votes(solve, question)
            table("Q1a giải ra khoá", right)
            table("Q1b đúng một phương án", single)
            unflawed = [
                None if review.get(m) is None else not review[m]["flaws"] for m in rate.RATERS
            ]
            table("Q1c không lỗi nặng", unflawed)
            for flaw in rate.FLAWS:
                table(
                    f"  lỗi {flaw}",
                    [
                        None if review.get(m) is None else flaw in review[m]["flaws"]
                        for m in rate.RATERS
                    ],
                )
            flaws = score.code_flaws(question)
            for flaw in flaws:
                arm["code"][flaw] = arm["code"].get(flaw, 0) + 1
            ok = (
                score.majority(right) is True
                and score.majority(single) is True
                and score.majority(unflawed) is True
                and not flaws
            )
            arm["usable"] += ok
            usable_here += ok
            # Q1 lõi: phần của Q1 không phụ thuộc thứ rater thấy kèm câu (mục hay job) -- giải mù
            # và luật code. So hai lượt mà ngữ cảnh duyệt khác nhau (trước và sau ADR-38) bằng số
            # này (review pha 1, plan `agent-split-bench`).
            core = score.majority(right) is True and score.majority(single) is True and not flaws
            arm["core"] += core
            core_here += core
            if score.majority(right) is False:
                arm["key_wrong"] += 1
            elif score.majority(right) is True and score.majority(single) is False:
                arm["many_right"] += 1
            if row["item"] is not None:
                follows = [
                    None if review.get(m) is None else review[m].get("follows_item")
                    for m in rate.RATERS
                ]
                # Từ ADR-38 mục của câu là job AGENT chia; lượt cũ còn mục dàn ý: bảng riêng.
                table("Q1d bám job" if "split" in paper else "Q1d bám mục", follows)
                arm["usable_follow"] += ok and score.majority(follows) is True
            if score.majority(right) is not True:
                continue  # Q2 chỉ đo phương án nhiễu của câu có khoá đúng
            for option in question["options"]:
                if option.get("is_correct") or not option.get("error_label"):
                    continue
                votes = []
                for model in rate.RATERS:
                    found = next(
                        (
                            one
                            for one in (review.get(model) or {}).get("distractors", [])
                            if label(one["label"]) == option["label"]
                        ),
                        None,
                    )
                    votes.append(None if found is None else bool(found["reproduces"]))
                table("Q2 nhiễu tái tạo", votes)
                arm["distractors"] += 1
                arm["faithful"] += score.majority(votes) is True
        arm["clean"] += (
            failed_here == 0 and len(paper["questions"]) == wanted and usable_here == wanted
        )
        summary.update(
            usable=usable_here, core=core_here, got=len(paper["questions"]) - failed_here
        )
        papers_out.append(summary)
    return {"arms": arms, "criteria": criteria, "blanks": blanks, "papers": papers_out}


def _pct(part: float, whole: float) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "—"


def _num(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def report(
    summary: dict,
    spend: rate.Spend,
    seconds: float,
    ratings: list[dict],
    stopped: str = "",
    config: str = "",
    from_run: str = "",
) -> str:
    """Báo cáo chữ: chỉ số theo nhánh, đồng thuận từng tiêu chí, độ dao động, câu bất đồng.

    Args:
        config: Model sinh đề và cấu hình của nó (`bench_model.Pinned.config`) -- dòng đầu, để số
            nào cũng mang theo model đã sinh ra nó.
        from_run: Lượt nguồn khi chỉ chấm lại (`--from-run`): chi phí khi ấy không có token sinh đề.
    """
    lines = [
        f"exam_bench · {seconds:.0f} s · sinh đề {config or '—'} · panel {', '.join(rate.RATERS)}"
    ]
    if stopped:
        lines.append(f"DỪNG GIỮA CHỪNG: {stopped} -- đề chưa chấm bị loại khỏi mọi chỉ số")
    lines.append("")
    for name, arm in summary["arms"].items():
        cov = arm["coverage"]
        head = f"[{name}] {arm['papers']} đề, {arm['gated']} trượt cổng"
        if arm["unrated"]:
            head += f", {arm['unrated']} chưa chấm"
        if arm.get("infra"):
            head += f" (hỏng hạ tầng {arm['infra']})"
        lines.append(head)
        if arm.get("outline_seconds"):
            took = sorted(arm["outline_seconds"])
            lines.append(
                f"  ra dàn ý: trung vị {statistics.median(took):.1f} s, lâu nhất {took[-1]:.1f} s"
            )
        if name == "agent":
            lines += [
                f"  Kriky hỏi lại trước dàn ý {arm['asked_back']} lần; dàn ý bị BE trả về "
                f"{arm['refusals']} lần; brief lấp từ ca {arm['brief_filled']} đề",
                f"  P1 độ phủ           {sum(cov) / len(cov):.2f} (trên {len(cov)} đề, trượt cổng "
                f"tính 0); mục ngoài khung yêu cầu cần đạt {arm['off']}/{arm['items']}"
                if cov
                else "  P1 độ phủ           —",
                f"  P2 mục duyệt nguyên {_pct(arm['items_ok'], arm['items'])} "
                f"({arm['items_ok']}/{arm['items']})",
            ]
        if arm["split_papers"]:
            lines += [
                f"  chia việc: số job đúng {arm['count_right']}/{arm['split_papers']} đề",
                f"  S1 job trung thành  {_pct(arm['jobs_faithful'], arm['jobs'])} "
                f"({arm['jobs_faithful']}/{arm['jobs']})",
                f"  S1b một câu, khác anh em {_pct(arm['jobs_apart'], arm['jobs'])} "
                f"({arm['jobs_apart']}/{arm['jobs']})",
                f"  S2 dàn ý phủ đủ     {_pct(arm['covered'], arm['split_papers'])} "
                f"({arm['covered']}/{arm['split_papers']})",
            ]
        lines += [
            f"  Q1 câu dùng nguyên  {_pct(arm['usable'], arm['wanted'])} ({arm['usable']}/"
            f"{arm['wanted']} câu xin; trên câu thu được {_pct(arm['usable'], arm['got'])}; "
            f"ô hỏng {arm['slots_failed']})",
            f"  Q1 lõi              {_pct(arm['core'], arm['wanted'])} ({arm['core']}/"
            f"{arm['wanted']}; giải mù và luật code; không xét lỗi nặng)",
        ]
        if name == "agent":
            lines.append(
                f"  Q1+ cộng bám mục    {_pct(arm['usable_follow'], arm['wanted'])} "
                f"({arm['usable_follow']}/{arm['wanted']})"
            )
        lines += [
            f"     đề sạch          {_pct(arm['clean'], arm['papers'])} "
            f"({arm['clean']}/{arm['papers']})",
            f"  Q2 nhiễu trung thực {_pct(arm['faithful'], arm['distractors'])} "
            f"({arm['faithful']}/{arm['distractors']}, chỉ câu có khoá đúng)",
            f"  câu thu được: khoá sai {arm['key_wrong']}, nhiều đáp án đúng {arm['many_right']}",
            "  lỗi bắt bằng code   "
            + (", ".join(f"{k} {v}" for k, v in sorted(arm["code"].items())) or "không có"),
            "",
        ]
    notes = [one for one in summary["papers"] if one.get("note")]
    if notes:
        lines.append("Lời chia việc mẫu (nhánh agent):")
        for one in notes[:2]:
            lines.append(f"  -- {one['case']} #{one['run']}")
            lines += [f"     {line}" for line in one["note"].splitlines()]
        lines.append("")
    lines.append(
        "Đồng thuận panel trên hàng đủ ba phiếu: κ Fleiss · AC1 Gwet · đồng thuận thô · "
        "κ Cohen từng cặp ("
        + ", ".join(f"{a}/{b}" for a, b in itertools.combinations(rate.RATERS, 2))
        + ")"
    )
    for name, rows in summary["criteria"].items():
        fleiss = score.fleiss_kappa(rows)
        ac1 = score.gwet_ac1(rows)
        agree = score.agreement(rows)
        pairs = []
        for a, b in itertools.combinations(range(len(rate.RATERS)), 2):
            pairs.append(
                _num(score.cohen_kappa([row[a] for row in rows], [row[b] for row in rows]))
            )
        yes = sum(1 for row in rows if score.majority(row))
        full = score.full_rows(rows)
        if ac1 is None:
            flag = "  ← không xác định"
        elif ac1 < 0.6:
            flag = "  ← chưa tin được"
        else:
            flag = ""
        lines.append(
            f"  {name:<34} n={full:<4} có={_pct(yes, len(rows)):<5} κ={_num(fleiss):<5} "
            f"AC1={_num(ac1):<5} thô={_num(agree):<5} [{', '.join(pairs)}]{flag}"
        )
    if summary["blanks"]:
        lines.append(
            "Phiếu trống: " + ", ".join(f"{k} {v}" for k, v in sorted(summary["blanks"].items()))
        )
    agent_runs: dict[str, dict[int, int]] = {}
    for paper in summary["papers"]:
        if paper["arm"] == "agent" and not paper.get("unrated"):
            agent_runs.setdefault(paper["case"], {})[paper["run"]] = paper.get("usable", 0)
    if any(len(runs) > 1 for runs in agent_runs.values()):
        lines += ["", "Độ dao động nhánh agent (câu dùng nguyên theo lượt):"]
        for case, runs in agent_runs.items():
            lines.append(f"  {case:<28} " + " · ".join(str(runs[at]) for at in sorted(runs)))
    disputed = []
    for row in ratings:
        if row["kind"] != "solve":
            continue
        sets = []
        for model in rate.RATERS:
            verdict = row["votes"].get(model)
            marked = (verdict or {}).get("options", [])
            sets.append(
                "".join(sorted(label(one["label"]) for one in marked if one["correct"])) or "∅"
            )
        if len(set(sets)) > 1:
            disputed.append(
                f"  {row['arm']}/{row['case']}#{row['run']} câu {row['ordinal']}: "
                + " / ".join(sets)
            )
    lines += ["", f"Câu panel giải ra khác nhau: {len(disputed)}", *disputed]
    by_model = ", ".join(f"{m} {usd:.2f}" for m, usd in spend.by_model.items())
    lines += [
        "",
        f"Chi phí: {spend.usd:.2f} USD ({spend.calls} lời gọi, {spend.cached} từ cache) · "
        + (
            f"{by_model}. Chỉ chấm: đề lấy từ {from_run}, không sinh đề nào."
            if from_run
            else f"{by_model}. Gồm token model sinh đề của cả hai nhánh; chưa gồm Jev (chọn skill)."
        ),
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------------------------- main


def _write_papers(out: Path, papers: list[dict]) -> None:
    """`outlines.jsonl` (mỗi đề một dòng) và `questions.jsonl` (mỗi câu một dòng)."""
    _write_rows(out / "outlines.jsonl", papers)
    with (out / "questions.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for paper in papers:
            for row in paper["questions"]:
                record = {"arm": paper["arm"], "case": paper["case"], "run": paper["run"], **row}
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _write_rows(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    """Sinh đề, chấm, gộp, ghi.

    `--rate-with` chọn ai chấm (plan `bench-two-models` pha 5b):

    - `api`: panel ba model Claude qua API (`rate.Panel`), như trước.
    - `export`: sinh đề (hay lấy từ `--from-run`), ghi tác vụ chấm ra `rating/`, **không chấm**;
      ba subagent chấm theo `subagent_rater.md`.
    - `import`: `--from-run` là thư mục của lượt `export`; đọc phiếu subagent, gộp, ghi báo cáo vào
      chính thư mục ấy.
    """
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument(
        "--model", required=True, help="model sinh đề, provider:model -- vd. openai:gpt-6-luna"
    )
    parser.add_argument("--via", default="", help="cổng trung gian cho model sinh đề: stali")
    parser.add_argument("--rate-with", default="api", choices=("api", "export", "import"))
    parser.add_argument("--agent-runs", type=int, default=2)
    parser.add_argument("--naive-runs", type=int, default=1)
    parser.add_argument("--only", default="", help="tiền tố id ca, cách nhau bằng dấu phẩy")
    parser.add_argument("--cap", type=float, default=40.0, help="trần chi phí USD của cả lượt")
    parser.add_argument("--from-run", default="", help="thư mục một lượt cũ: chấm lại đề đã sinh")
    parsed = parser.parse_args()

    import bench_model
    from agent.config import get_settings
    from exam_bench import subagent
    from ocr_bench.run import next_run, task_code_in

    if code := task_code_in(parsed.label):
        raise SystemExit(f"--label {parsed.label!r} mang mã task {code!r}: đặt theo việc nó đo")
    if parsed.rate_with == "import" and not parsed.from_run:
        raise SystemExit("--rate-with import cần --from-run <thư mục của lượt export>")
    if parsed.via and parsed.rate_with == "api":
        # `--via` đặt `ANTHROPIC_BASE_URL` và key của cổng vào môi trường; SDK của panel API cũng
        # đọc chúng, nên rater sẽ đi qua cổng -- đúng thứ lời thử không canh (review pha 5b).
        raise SystemExit("--via chỉ dùng với --rate-with export|import: panel API sẽ đi qua cổng")
    if parsed.rate_with != "api":
        # Panel là ba subagent: mọi chỗ đọc `rate.RATERS` lúc gọi (gộp phiếu, đồng thuận, báo cáo).
        rate.RATERS = subagent.SUBAGENT_RATERS
    provider, model = bench_model.parse(parsed.model)
    check_generator(model)
    pinned = bench_model.pin(parsed.model, via=parsed.via, build=parsed.rate_with != "import")
    settings = get_settings()
    # Panel API là Claude, cả khi model sinh đề là OpenAI: thiếu key thì dừng trước khi tiêu tiền
    # sinh đề, không phải ở lời chấm đầu tiên (review pha 5).
    if parsed.rate_with == "api" and not settings.claude_api_key:
        raise SystemExit("panel chấm là Claude: thiếu CLAUDE_API_KEY trong .env")
    config = f"{pinned.config} (naive: một lời gọi, trần {_NAIVE_CALL['timeout']} s)"
    source = Path(parsed.from_run) if parsed.from_run else None
    generation_file = source / "generation.json" if source else None
    if parsed.rate_with == "import" and generation_file and generation_file.exists():
        config = json.loads(generation_file.read_text(encoding="utf-8"))["config"]
    print(f"sinh đề: {config}", flush=True)
    cases = {one["id"]: one for one in json.loads(_CASES.read_text(encoding="utf-8"))}
    if parsed.only:
        wanted = tuple(parsed.only.split(","))
        cases = {key: one for key, one in cases.items() if key.startswith(wanted)}
    spend = rate.Spend(cap=parsed.cap)
    started = time.monotonic()
    stopped = ""
    preflight = ""
    counts: dict[str, int] = {}

    async def everything() -> tuple[list[dict], list[dict], object]:
        nonlocal stopped, preflight, counts
        if source:
            papers = [
                json.loads(line)
                for line in (source / "outlines.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            papers = [one for one in papers if one["case"] in cases]
            other = {one.get("model") or LEGACY_GENERATOR for one in papers} - {pinned.model}
            if other:
                raise SystemExit(f"--from-run sinh bằng {sorted(other)}, không phải {pinned.model}")
        else:
            # Cổng trung gian: một lời thử trước mọi lời sinh đề -- bẩn thì dừng ở đây.
            if preflight := await bench_model.check_preflight(pinned):
                print(preflight, flush=True)
            jobs = []
            for case in cases.values():
                for run in range(1, parsed.agent_runs + 1):
                    jobs.append(("agent", run, case))
                for run in range(1, parsed.naive_runs + 1):
                    jobs.append(("naive", run, case))
            gate = asyncio.Semaphore(3)

            async def one(arm: str, run: int, case: dict) -> dict:
                async with gate:
                    try:
                        paper = await generated(arm, case, pinned.model, spend)
                    except Exception as exc:  # noqa: BLE001 -- một đề hỏng không làm mất cả lượt
                        bench_model.stop_if_out_of_money(exc)
                        # Ghi lại thay vì làm đổ `gather`: các đề đã sinh vẫn được ghi ra (pha 6b).
                        logger.warning("sinh %s %s #%d hỏng: %r", arm, case["id"], run, exc)
                        paper = {
                            "arm": arm,
                            "case": case["id"],
                            "gate": "",
                            "items": [],
                            "questions": [],
                            "infra": f"lỗi không lường: {type(exc).__name__}",
                            "model": pinned.model,
                        }
                paper["run"] = run
                print(f"  sinh {arm} {case['id']} #{run}: {paper['gate'] or 'xong'}", flush=True)
                return paper

            papers = list(await asyncio.gather(*(one(*job) for job in jobs)))
        if parsed.rate_with == "api":
            panel = rate.Panel(settings.claude_api_key, spend)
        elif parsed.rate_with == "export":
            panel = subagent.TaskPanel()
        else:
            tasks = subagent.read_tasks(source / "rating")
            verdicts, counts = subagent.read_verdicts(source / "rating", tasks)
            panel = subagent.TaskPanel(verdicts)
        ratings: list[dict] = []
        for paper in papers:
            panel.case = paper["case"]
            try:
                ratings += await rate_paper(panel, cases[paper["case"]], paper)
            except rate.BudgetSpent as exc:
                stopped = str(exc)
                print(f"DỪNG: {exc}", flush=True)
                break
            if parsed.rate_with == "api":
                print(
                    f"  chấm {paper['arm']} {paper['case']} #{paper['run']} · {spend.usd:.2f} USD",
                    flush=True,
                )
        return papers, ratings, panel

    papers, ratings, panel = asyncio.run(everything())
    names = [path.name for path in _RUNS.iterdir()] if _RUNS.exists() else []

    if parsed.rate_with == "export":
        out = _RUNS / f"run-{next_run(names)}" / f"exam-{parsed.label}-{pinned.slug}"
        out.mkdir(parents=True, exist_ok=True)
        _write_papers(out, papers)
        written = subagent.write_tasks(out / "rating", panel.tasks)
        generation = {
            "model": pinned.model,
            "config": config,
            "via": pinned.via,
            "preflight": preflight,
            "from_run": parsed.from_run,
            "seconds": round(time.monotonic() - started),
            "usd": spend.usd,
            "by_model": spend.by_model,
        }
        (out / "generation.json").write_text(
            json.dumps(generation, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
        )
        print(f"\n{len(papers)} đề, {len(panel.tasks)} tác vụ chấm, sinh đề {spend.usd:.2f} USD")
        for phase, paths in written.items():
            print(f"  {phase}: {len(paths)} tệp ({', '.join(path.stem for path in paths)})")
        print(
            f"ghi vào {out}\nTiếp: chấm đợt blind rồi keyed theo exam_bench/subagent_rater.md, "
            f"rồi --rate-with import --from-run {out}"
        )
        return

    if parsed.rate_with == "import" and generation_file and generation_file.exists():
        generated_cost = json.loads(generation_file.read_text(encoding="utf-8"))
        spend.usd, spend.by_model = generated_cost["usd"], generated_cost["by_model"]
    summary = summarise(cases, papers, ratings)
    summary["model"] = pinned.model
    summary["config"] = config
    summary["from_run"] = parsed.from_run
    summary["panel"] = list(rate.RATERS)
    text = report(
        summary,
        spend,
        time.monotonic() - started,
        ratings,
        stopped,
        config,
        "" if parsed.rate_with == "import" else parsed.from_run,
    )
    if parsed.rate_with == "import":
        counts["thiếu"] = sum(vote is None for row in ratings for vote in row["votes"].values())
        summary["verdicts"] = counts
        text += f"\nPanel: {subagent.PANEL_NOTE}. Phiếu: " + ", ".join(
            f"{name} {value}" for name, value in counts.items()
        )
    print(text)

    if parsed.rate_with == "import":
        out = source
    else:
        out = _RUNS / f"run-{next_run(names)}" / f"exam-{parsed.label}-{pinned.slug}"
        out.mkdir(parents=True, exist_ok=True)
        _write_papers(out, papers)
    _write_rows(out / "ratings.jsonl", ratings)
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
    )
    (out / "report.txt").write_text(text + "\n", encoding="utf-8", newline="\n")
    print(f"ghi vào {out}")


if __name__ == "__main__":
    main()
