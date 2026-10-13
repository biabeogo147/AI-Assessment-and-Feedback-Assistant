"""Dựng cây cho một tài liệu đã có bản thô trong Mongo, theo nhiều đường, và chấm từng đường.

Cùng lệ với `ocr_bench`: không chạy trong `.\\dev.ps1 check`, không chạy được trên máy không có
`data/`. Thứ `check` canh là **test của thước đo** (`tools/tests/test_pageindex_score.py`).

Các đường:

- `rules` -- chỉ luật (D5);
- `jev@<t>` -- Jev quyết, luật quyết thay khi `confidence` < `t` (D5); `jev@0` là Jev thuần.

Jev được hỏi **một lần** cho cả tài liệu; mọi ngưỡng tính lại trên cùng những câu trả lời ấy, nên
một lượt quét ngưỡng không nhân tiền Jev lên.

Banner (D9) không gọi luna ở đây: `--banners` trỏ tới một tệp JSON đã đọc sẵn, để mọi đường cùng
dùng một bộ tên chương và phép so chỉ đo **phần phân loại**.

Mỗi lượt ghi vào `data/results/run-<n>/pageindex-<jev_model>/`: `report.txt` (bảng in ra),
`config.json`, `labels.jsonl` (câu trả lời của Jev từng ứng viên), `tree-<đường>.json`.

Dùng:
    python -m pageindex_bench.run --document <id> --banners <banners.json>
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

from contracts import BlockRef
from document.config import get_settings
from document.content_store import ContentStore
from document.index.assemble import Banner, assemble, headings
from document.index.features import (
    banner_gates,
    candidates,
    page_offset,
    printed_pages,
)
from document.index.jev import JevClassifier, open_paths, state_of
from document.index.rules import combine, decide
from ocr_bench.run import next_run
from pageindex_bench.score import LevelScore, TreeNode, score

_GOLD = Path("data") / "gold" / "tree" / "L6T1.json"
# Kết quả đo nằm riêng ở `data/results/`, tách khỏi thứ bộ đo đọc vào (PDF, `gold/`, `cache/`) --
# người dùng chốt 13/10/2026.
_RUNS = Path("data") / "results"
# $ / triệu token vào của Jev; token ra miễn phí (plan 3c, Khảo sát Jev).
_JEV_PRICE = 0.042
_THRESHOLDS = (0.0, 0.5, 0.6, 0.7, 0.8, 0.9)


def load_gold(path: Path) -> tuple[list[TreeNode], list[tuple[int, int, int]]]:
    """Đọc cây vàng.

    Args:
        path: Tệp JSON của cây vàng.

    Returns:
        Các nút, và các khoảng không chấm `(cấp, trang đầu, trang cuối)`.
    """
    body = json.loads(path.read_text(encoding="utf-8"))
    nodes = [
        TreeNode(node["level"], node["title"], node["page"], node.get("numbering"))
        for node in body["nodes"]
    ]
    unscored = []
    for index, node in enumerate(body["nodes"]):
        if node.get("level3_scored") is False:
            later = [other["page"] for other in body["nodes"][index + 1 :] if other["level"] == 1]
            unscored.append((3, node["page"], later[0] - 1 if later else 10**6))
    return nodes, unscored


def load_banners(path: Path | None, gates: list[BlockRef]) -> list[Banner]:
    """Banner cho từng trang qua cổng, từ tệp đã đọc sẵn; thiếu thì chỉ có *"Chương N"*.

    Args:
        path: Tệp JSON, mỗi phần tử `{page, chapter_label, chapter_title, lesson_label,
            lesson_title}`. `None` thì không có tên nào.
        gates: Các khối qua cổng.

    Returns:
        Một banner mỗi cổng.
    """
    read = {}
    if path:
        read = {row["page"]: row for row in json.loads(path.read_text(encoding="utf-8"))}
    out = []
    for number, gate in enumerate(gates, start=1):
        row = read.get(gate.page, {})
        out.append(
            Banner(
                ref=gate,
                chapter_label=row.get("chapter_label") or f"Chương {number}",
                chapter_title=row.get("chapter_title"),
                lesson_label=row.get("lesson_label"),
                lesson_title=row.get("lesson_title"),
            )
        )
    return out


def _table(name: str, rows: list[LevelScore], count: int) -> str:
    cells = "  ".join(
        f"L{row.level} P{row.precision:5.1%} R{row.recall:5.1%} F{row.f1:5.1%}" for row in rows
    )
    return f"{name:10} nút {count:3}  {cells}"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", required=True)
    parser.add_argument("--gold", type=Path, default=_GOLD)
    parser.add_argument("--banners", type=Path, default=None)
    parser.add_argument("--no-jev", action="store_true")
    parser.add_argument("--run", type=int, default=None)
    # Chỉ in bảng, không ghi bản ghi -- để chỉnh luật mà không đẻ ra một `run-<n>` mỗi lần thử.
    # Không dùng được cùng Jev: một lượt trả tiền thì phải để lại bản ghi.
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()
    if args.no_save and not args.no_jev:
        raise SystemExit("--no-save chỉ dùng cùng --no-jev")

    settings = get_settings()
    store = ContentStore(settings.mongo_url, settings.mongo_database)
    pages = await store.pages(args.document)
    await store.close()
    if not pages:
        raise SystemExit(f"no raw pages for {args.document}")

    found = candidates(pages)
    ruled = [decide(candidate) for candidate in found]
    banners = load_banners(args.banners, banner_gates(pages))
    printed = printed_pages(pages)
    offset = page_offset(printed)
    gold, unscored = load_gold(args.gold)

    def built(decisions) -> list:
        return assemble(
            args.document,
            headings(list(zip(found, decisions, strict=True)), banners),
            len(pages),
            printed,
            offset,
        )

    lines = [
        f"tài liệu {args.document}: {len(pages)} trang, {len(found)} ứng viên, "
        f"{len(banners)} banner, độ lệch trang in {offset}",
        "",
    ]
    trees = {"rules": built(ruled)}
    labels: list[dict] = []
    jev_model, tokens, seconds = None, 0, 0.0
    if not args.no_jev and settings.jev_api_key:
        chapters = {
            banner.ref.page: banner.chapter_title or banner.chapter_label for banner in banners
        }
        paths = open_paths(found, ruled, chapters)
        states = [state_of(candidate, path) for candidate, path in zip(found, paths, strict=True)]
        jev = JevClassifier(
            settings.jev_api_key,
            settings.jev_model,
            settings.jev_concurrency,
            settings.jev_timeout_seconds,
        )
        started = time.monotonic()
        asked = await jev.decide_all(states)
        seconds = time.monotonic() - started
        await jev.aclose()
        jev_model, tokens = asked.model, asked.tokens
        for threshold in _THRESHOLDS:
            decisions = [
                combine(one, rule, threshold)
                for one, rule in zip(asked.decisions, ruled, strict=True)
            ]
            trees[f"jev@{threshold:g}"] = built(decisions)
        for candidate, state, one, rule in zip(found, states, asked.decisions, ruled, strict=True):
            labels.append(
                {
                    "page": candidate.unit.ref.page,
                    "block": candidate.unit.ref.block,
                    "text": candidate.unit.text,
                    "state": state,
                    "jev": [one.role, one.level, round(one.confidence, 3)],
                    "rules": [rule.role, rule.level],
                    "role_probabilities": one.role_probabilities,
                    "level_probabilities": one.level_probabilities,
                }
            )
        lines.append(
            f"Jev {jev_model}: {len(states)} lời gọi, {tokens} token vào, "
            f"${tokens * _JEV_PRICE / 1e6:.4f}, {seconds:.1f} s"
        )
        lines.append("")

    for name, tree in trees.items():
        nodes = [TreeNode(node.level, node.title, node.page_start, node.numbering) for node in tree]
        lines.append(_table(name, score(gold, nodes, unscored), len(tree)))
    report = "\n".join(lines)
    print(report)
    if args.no_save:
        return

    names = [path.name for path in _RUNS.iterdir()] if _RUNS.exists() else []
    number = args.run or next_run(names)
    folder = _RUNS / f"run-{number}" / f"pageindex-{jev_model or 'rules'}"
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "report.txt").write_text(report + "\n", encoding="utf-8")
    config = {
        "document": args.document,
        "gold": str(args.gold),
        "banners": str(args.banners) if args.banners else None,
        "jev_model": jev_model,
        "jev_tokens": tokens,
        "jev_seconds": round(seconds, 2),
        "thresholds": _THRESHOLDS,
    }
    (folder / "config.json").write_text(json.dumps(config, indent=1), encoding="utf-8")
    with (folder / "labels.jsonl").open("w", encoding="utf-8") as out:
        for row in labels:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    for name, tree in trees.items():
        rows = [node.model_dump(mode="json") for node in tree]
        target = folder / f"tree-{name}.json"
        target.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ghi vào {folder}")


if __name__ == "__main__":
    asyncio.run(main())
