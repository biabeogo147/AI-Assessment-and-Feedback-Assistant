"""Đo bộ chọn skill của Kriky (plan 4a) trên bộ nhãn `cases.json`, và quét ngưỡng `SKILL_MIN_YES`.

Cùng lệ với `pageindex_bench`: không chạy trong `.\\dev.ps1 check` vì nó gọi Jev thật. Thứ `check`
canh là **test của thước đo** (`tools/tests/test_skill_bench.py`).

Jev được hỏi **một lần** mỗi ca; mọi ngưỡng tính lại trên cùng những xác suất ấy, nên quét ngưỡng
không nhân tiền lên. Cổng của plan 4a: recall của `soan-de` và `lop-va-ket-qua` bằng 100% -- thiếu
một skill chuyên biệt đắt hơn thừa nó.

Mỗi lượt ghi vào `data/results/run-<n>/skill-routing-<jev_model>/`: `report.txt` và `answers.jsonl`.

Dùng:
    python -m skill_bench.run
"""

import asyncio
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy, TypeSafeError

from agent import skill_router, skills
from agent.config import get_settings
from contracts import TurnRecord
from ocr_bench.run import next_run

_CASES = Path(__file__).resolve().parent / "cases.json"
# Kết quả đo nằm riêng ở `data/results/`, tách khỏi thứ bộ đo đọc vào (PDF, `gold/`, `cache/`) --
# người dùng chốt 13/10/2026.
_RUNS = Path("data") / "results"
# $ / triệu token vào của Jev; token ra miễn phí (plan 3c, Khảo sát Jev).
_JEV_PRICE = 0.042
_THRESHOLDS = (0.1, 0.2, 0.3, 0.4, 0.5)


@dataclass(frozen=True)
class SkillScore:
    """Điểm của một skill ở một ngưỡng.

    Attributes:
        skill: Tên skill.
        recall: Phần các ca cần skill mà được nạp nó.
        precision: Phần các ca được nạp skill mà thật sự cần nó.
        missed: Id các ca cần mà không được nạp.
    """

    skill: str
    recall: float
    precision: float
    missed: tuple[str, ...]


def score(
    expected: dict[str, set[str]], yes: dict[str, dict[str, float]], threshold: float
) -> list[SkillScore]:
    """Chấm mỗi skill chuyên biệt ở một ngưỡng. Hàm thuần.

    Args:
        expected: Id ca → các skill chuyên biệt ca ấy cần (rỗng là skill bao quát).
        yes: Id ca → skill → xác suất "yes" Jev trả.
        threshold: Ngưỡng nạp.

    Returns:
        Một điểm mỗi skill có mặt trong `yes`, theo thứ tự tên.
    """
    names = sorted({name for answers in yes.values() for name in answers})
    out = []
    for name in names:
        needed = {case for case, wanted in expected.items() if name in wanted}
        loaded = {case for case, answers in yes.items() if answers.get(name, 0) >= threshold}
        hit = needed & loaded
        out.append(
            SkillScore(
                skill=name,
                recall=len(hit) / len(needed) if needed else 1.0,
                precision=len(hit) / len(loaded) if loaded else 1.0,
                missed=tuple(sorted(needed - loaded)),
            )
        )
    return out


def _history(raw: list[list[str]]) -> list[TurnRecord]:
    return [TurnRecord(kind=speaker, text=text) for speaker, text in raw]


async def _ask(cases: list[dict]) -> tuple[dict[str, dict[str, float]], int, dict, list[float]]:
    settings = get_settings()
    if not settings.jev_api_key:
        raise SystemExit("JEV_API_KEY is empty: nothing to measure")
    # Client riêng, không phải `skill_router._client()`: trần 3 s của production là để cắt một lượt
    # chat, còn ở đây một ca chậm phải được chờ -- không thì cả lượt đo mất trắng (review plan 4a).
    client = AsyncTypeSafeClient(
        api_key=settings.jev_api_key,
        model=settings.jev_model,
        timeout=30,
        retry=RetryPolicy(max_retries=3),
    )
    specialised = [skill for skill in skills.every() if skill.name != skills.GENERAL]
    questions = skill_router._questions(specialised)
    yes: dict[str, dict[str, float]] = {}
    failed: dict[str, str] = {}
    seconds: list[float] = []
    tokens = 0
    try:
        for case in cases:
            state = skill_router.state_of(_history(case["history"]))
            started = time.monotonic()
            try:
                response = await client.system_one(state=state, questions=questions)
            except TypeSafeError as exc:
                failed[case["id"]] = repr(exc)
                continue
            seconds.append(time.monotonic() - started)
            yes[case["id"]] = {
                name: float(answer.probabilities.get("yes", 0))
                for name, answer in response.answers.items()
            }
            tokens += (response.usage.input_tokens or 0) if response.usage else 0
    finally:
        await client.aclose()
    return yes, tokens, failed, seconds


def main() -> None:
    """Hỏi Jev cho mọi ca, in và ghi bảng điểm."""
    cases = json.loads(_CASES.read_text(encoding="utf-8"))
    yes, tokens, failed, seconds = asyncio.run(_ask(cases))
    # Ca hỏng không được chấm: chấm nó là tính một lần mạng chập thành một lần Jev chọn sai.
    expected = {case["id"]: set(case["expect"]) for case in cases if case["id"] in yes}

    model = get_settings().jev_model
    slowest = max(seconds, default=0.0)
    middle = statistics.median(seconds) if seconds else 0.0
    lines = [
        f"{len(yes)}/{len(cases)} ca, {tokens} token vào, ~${tokens * _JEV_PRICE / 1e6:.4f}",
        f"thời gian một lời gọi: trung vị {middle:.2f} s, chậm nhất {slowest:.2f} s",
    ]
    lines += [f"hỏng {case}: {why}" for case, why in failed.items()]
    lines.append("")
    for threshold in _THRESHOLDS:
        lines.append(f"ngưỡng {threshold}:")
        for one in score(expected, yes, threshold):
            missed = f"  thiếu: {', '.join(one.missed)}" if one.missed else ""
            lines.append(
                f"  {one.skill:16} recall {one.recall:.0%}  precision {one.precision:.0%}{missed}"
            )
    report = "\n".join(lines)
    print(report)

    names = [path.name for path in _RUNS.iterdir()] if _RUNS.exists() else []
    out = _RUNS / f"run-{next_run(names)}" / f"skill-routing-{model}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.txt").write_text(report + "\n", encoding="utf-8", newline="\n")
    with (out / "answers.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            row = {"id": case["id"], "expect": case["expect"], "yes": yes.get(case["id"])}
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nghi vào {out}")


if __name__ == "__main__":
    main()
