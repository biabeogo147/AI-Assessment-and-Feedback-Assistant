"""Đo text model đọc trên các ca Toán **khác chương** với mọi ví dụ trong prompt (plan 4c).

Ba phần, cùng lệ với `skill_bench`: không chạy trong `.\\dev.ps1 check` vì gọi model thật; thứ
`check` canh là **test của thước** và luật *câu đo không bao giờ nằm trong prompt*
(`tools/tests/test_propose_bench.py`).

- `propose`: gọi thẳng `agent.graphs.propose.propose` (bộ chọn skill là Jev thật), chấm **loại
  việc** và **tham số model điền** -- `subject`, `grade`, `topic_scope`, `question_count`,
  `nodes`, `document_id`; câu hỏi lại thì đếm phương án. Plan đạt ý ca còn phải qua `vet_plan`
  của BE -- một plan BE từ chối không tới được giáo viên (review T2).
- `author`: gọi `write_question` với brief như BE dựng, chấm bằng `validate_question` của BE
  (ADR-18).
- `name`: đặt tên đoạn chat; ghi những chữ của tiêu đề **không** có trong câu giáo viên -- dấu hiệu
  model chép chữ từ ví dụ (`agent/graphs/naming.py`) -- và dấu `<>` của khuôn ví dụ bị chép theo.

Mỗi lượt ghi vào `data/run-<n>/model-text-<nhãn>/`: `report.txt` và `answers.jsonl`.

Dùng:
    python -m propose_bench.run --label baseline --runs 6
"""

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

_CASES = Path(__file__).resolve().parent / "cases.json"
_RUNS = Path("data")


def _create_args(steps: list[dict]) -> dict:
    return next((step["args"] for step in steps if step["tool_name"] == "create_draft"), {})


def _count(steps: list[dict]) -> str:
    drafting = next((step for step in steps if step["tool_name"] == "start_drafting"), None)
    return str(drafting["args"].get("question_count", "")).strip() if drafting else ""


def score_propose(expect: dict, step: dict) -> tuple[bool, str]:
    """Một câu trả lời của `propose` có đúng ý ca không. Hàm thuần.

    Args:
        expect: Phần `expect` của ca. `any_of` là danh sách các kỳ vọng thay thế -- một bước trung
            gian hợp lệ (gọi `get_chapter` đúng chương trước khi nêu plan) cũng là đạt.
        step: `NextStepCompleted` đã dump.

    Returns:
        `(đạt, lý do khi không đạt)`.
    """
    if "any_of" in expect:
        results = [score_propose(one, step) for one in expect["any_of"]]
        if any(ok for ok, _ in results):
            return True, ""
        return False, results[0][1]
    kind = step.get("kind")
    if kind != expect["kind"]:
        return False, f"kind {kind} != {expect['kind']}"
    text = str(step.get("text") or "")
    if kind in {"say", "ask_clarify"} and not text.strip():
        return False, "text rỗng"
    banned = [word for word in expect.get("text_lacks", []) if word.casefold() in text.casefold()]
    if banned:
        return False, f"text có {banned[0]!r}"
    if kind == "call_tool" and step.get("tool_name") != expect.get("tool"):
        return False, f"tool {step.get('tool_name')}"
    if kind == "call_tool":
        args = step.get("tool_args") or {}
        for key, value in expect.get("args", {}).items():
            # Một giá trị, hoặc danh sách các giá trị cùng đúng (*"9A2"* hay *"lớp 9A2"*).
            allowed = value if isinstance(value, list) else [value]
            if str(args.get(key, "")).strip() not in allowed:
                return False, f"tool {key} {args.get(key)!r} / args {sorted(args)}"
    if kind == "ask_clarify" and len(step.get("choices") or []) < expect.get("min_choices", 0):
        return False, f"chỉ {len(step.get('choices') or [])} phương án"
    if kind != "plan":
        return True, ""

    steps = list(step.get("steps") or [])
    args = _create_args(steps)
    if not args:
        return False, "plan không có create_draft"
    if "toán" not in str(args.get("subject", "")).casefold():
        return False, f"subject {args.get('subject')!r}"
    if "grade" in expect and str(args.get("grade", "")).strip() != expect["grade"]:
        return False, f"grade {args.get('grade')!r}"
    if "count" in expect and _count(steps) != expect["count"]:
        return False, f"question_count {_count(steps)!r}"
    scope = str(args.get("topic_scope", "")).casefold()
    missing = [word for word in expect.get("scope_has", []) if word.casefold() not in scope]
    if missing:
        return False, f"topic_scope {args.get('topic_scope')!r}"
    for key in ("nodes", "document_id"):
        if key in expect and str(args.get(key, "")).replace(" ", "") != expect[key]:
            return False, f"{key} {args.get(key)!r}"
    return True, ""


# Chữ gọi tên **việc** -- prompt đặt tên dặn *"gọi tên việc đó"*, nên chúng được phép xuất hiện dù
# giáo viên không gõ. Thứ thước bắt là chữ **nội dung** lạ (một chủ đề, một tên lớp) -- dấu hiệu
# chép ví dụ.
_ACTION_WORDS = frozenset(
    {"soạn", "đề", "tạo", "kết", "quả", "kiểm", "tra", "hỏi", "về", "lớp", "của"}
)


def foreign_words(said: str, title: str) -> list[str]:
    """Những chữ nội dung của tiêu đề không có trong câu giáo viên. Hàm thuần.

    Chữ chỉ việc (`_ACTION_WORDS`) không tính: *"Kết quả lớp 9A2"* là tên đúng ý cho một câu hỏi kết
    quả; *"Soạn đề đạo hàm"* cho một lời chào thì là chép ví dụ.

    Args:
        said: Câu giáo viên.
        title: Tiêu đề model đặt.

    Returns:
        Các chữ lạ, theo thứ tự trong tiêu đề.
    """
    seen = set(re.findall(r"\w+", said.casefold())) | _ACTION_WORDS
    return [word for word in re.findall(r"\w+", title.casefold()) if word not in seen]


def be_refuses(step: dict, plannable: tuple) -> str:
    """Lời `vet_plan` của BE cho một plan, rỗng khi BE nhận nó.

    Thước chấm ý ca (`score_propose`) không biết luật của BE: tham chiếu sai khuôn, tool ngoài
    catalog pha thực hiện, thiếu tham số bắt buộc. Plan như thế thì giáo viên chỉ nhận
    `_PLAN_REFUSED`, nên nó không được tính là đạt. `bind_book` không chạy ở đây (nó đọc Mongo):
    ca có sách phải tự điền `document_id` và `nodes`, đúng như `expect` của chúng đòi.

    Args:
        step: `NextStepCompleted` đã dump, `kind` là plan.
        plannable: Catalog pha thực hiện mà lượt ấy được cấp.

    Returns:
        Lý do từ chối, hoặc chuỗi rỗng.
    """
    from be.teacher_chat import vet_plan
    from contracts import PlanStep

    steps = tuple(PlanStep.model_validate(one) for one in step.get("steps") or [])
    return vet_plan(steps, plannable) or ""


def _history(raw: list) -> tuple:
    from contracts import TurnRecord

    out = []
    for row in raw:
        if row[0] in {"teacher", "assistant"}:
            out.append(TurnRecord(kind=row[0], text=row[1]))
        elif row[0] == "tool_call":
            out.append(TurnRecord(kind="tool_call", tool_name=row[1], tool_args=row[2]))
        else:
            out.append(TurnRecord(kind="tool_result", tool_name=row[1], tool_result=row[2]))
    return tuple(out)


async def _propose(cases: list[dict], runs: int) -> list[dict]:
    from agent import skill_router
    from agent.graphs.propose import propose
    from be.identity import Asking
    from be.teacher_tools import PHASE_PLAN, PHASE_WORK, catalog_for
    from contracts import AttachedDocument, NextStepRequested

    asking = Asking(teacher_id="bench", teacher_code="GV-BENCH", full_name="Cô Hà")
    rows = []
    for case in cases:
        attached = case.get("attached")
        document = AttachedDocument(**attached) if attached else None
        request = NextStepRequested(
            request_id=case["id"],
            teacher_name=asking.full_name,
            history=_history(case["history"]),
            catalog=catalog_for(asking, PHASE_PLAN, documents=bool(document), bound=bool(document)),
            plannable=catalog_for(
                asking, PHASE_WORK, documents=bool(document), bound=bool(document)
            ),
            attached_document=document,
        )
        # Skill Jev chọn được ghi kèm, để một lần trượt nói được là lỗi định tuyến hay lỗi prompt.
        # Jev nhớ lựa chọn theo state trong process, nên sáu lần của một ca dùng **một** lựa chọn.
        chosen = list(await skill_router.choose(request.history))
        for _ in range(runs):
            try:
                step = (await propose(request)).model_dump(mode="json")
                ok, why = score_propose(case["expect"], step)
                planned = ok and step["kind"] == "plan"
                refused = be_refuses(step, request.plannable) if planned else ""
                if refused:
                    ok, why = False, f"BE từ chối: {refused}"
            except Exception as exc:  # noqa: BLE001 -- một lần hỏng là một lần trượt, không dừng bộ đo
                step, ok, why = {}, False, f"lỗi {exc!r}"[:200]
            rows.append(
                {
                    "part": "propose",
                    "id": case["id"],
                    "ok": ok,
                    "why": why,
                    "skills": chosen,
                    "step": step,
                }
            )
    return rows


async def _author(cases: list[dict], runs: int) -> list[dict]:
    from agent.graphs.authoring import draft_brief, write_question
    from be.agent_gateway import AgentError, validate_question
    from contracts import DraftQuestionRequested

    rows = []
    for case in cases:
        request = DraftQuestionRequested(
            request_id=case["id"],
            subject="Toán",
            grade=case["grade"],
            topic_scope=case["scope"],
            ordinal=1,
            of_total=5,
        )
        for _ in range(runs):
            try:
                question = await write_question(draft_brief(request))
                validate_question(question)
                ok, why = True, ""
                dumped = question.model_dump(mode="json")
            except AgentError as exc:
                ok, why, dumped = False, f"ADR-18: {exc}"[:200], {}
            except Exception as exc:  # noqa: BLE001
                ok, why, dumped = False, f"lỗi {exc!r}"[:200], {}
            rows.append(
                {"part": "author", "id": case["id"], "ok": ok, "why": why, "question": dumped}
            )
    return rows


async def _name(cases: list[dict], runs: int) -> list[dict]:
    from agent.graphs.naming import name_it
    from contracts import ConversationNameRequested

    rows = []
    for case in cases:
        for _ in range(runs):
            try:
                title = await name_it(
                    ConversationNameRequested(request_id=case["id"], said=case["text"])
                )
            except Exception as exc:  # noqa: BLE001
                title = f"lỗi {exc!r}"[:200]
            extra = foreign_words(case["text"], title)
            if re.search(r"[<>]", title):
                # Khuôn ví dụ của `naming` dùng `<nội dung>`; chép cả dấu ngoặc là hỏng (review T2).
                extra = ["<>", *extra]
            rows.append(
                {
                    "part": "name",
                    "id": case["id"],
                    "ok": not extra,
                    "why": " ".join(extra),
                    "title": title,
                }
            )
    return rows


def _report(rows: list[dict], seconds: float) -> str:
    lines = [f"{len(rows)} lần gọi, {seconds:.0f} s", ""]
    for part in ("propose", "author", "name"):
        mine = [row for row in rows if row["part"] == part]
        if not mine:
            continue
        passed = sum(row["ok"] for row in mine)
        lines.append(f"{part}: {passed}/{len(mine)}")
        for case in dict.fromkeys(row["id"] for row in mine):
            these = [row for row in mine if row["id"] == case]
            whys = sorted({row["why"] for row in these if not row["ok"]})
            lines.append(
                f"  {case:24} {sum(row['ok'] for row in these)}/{len(these)}"
                + (f"  · {' | '.join(whys)[:160]}" if whys else "")
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    """Chạy các phần được chọn, in và ghi báo cáo."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--runs", type=int, default=6)
    parser.add_argument("--parts", default="propose,author,name")
    parsed = parser.parse_args()

    from ocr_bench.run import next_run

    cases = json.loads(_CASES.read_text(encoding="utf-8"))
    started = time.monotonic()
    parts = parsed.parts.split(",")

    async def every_part() -> list[dict]:
        # **Một** event loop cho mọi phần: client của provider được cache trong process, và một
        # `asyncio.run` thứ hai gặp một client gắn với loop đã đóng (*"Event loop is closed"*).
        rows: list[dict] = []
        if "propose" in parts:
            rows += await _propose(cases["propose"], parsed.runs)
        if "author" in parts:
            rows += await _author(cases["author"], max(1, parsed.runs // 3))
        if "name" in parts:
            rows += await _name(cases["name"], max(1, parsed.runs // 3))
        return rows

    rows = asyncio.run(every_part())
    report = _report(rows, time.monotonic() - started)
    print(report)

    names = [path.name for path in _RUNS.iterdir()] if _RUNS.exists() else []
    out = _RUNS / f"run-{next_run(names)}" / f"model-text-{parsed.label}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.txt").write_text(report + "\n", encoding="utf-8", newline="\n")
    with (out / "answers.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"ghi vào {out}")


if __name__ == "__main__":
    main()
