"""Đo VLM đọc công thức trên ảnh trang bằng **chính lời gọi của sản phẩm** (`formulas-on-demand`).

Gọi `document.index.llm.read_formulas` với model dựng như `document.index_worker` (tắt thinking,
effort `low`), rồi chấm bằng `score.formula_verdicts` trên các khối `formula` của nhãn vàng. Thay
cho script khảo sát ngoài repo của 11/10/2026: con số đo được là con số của đúng đường giáo viên
dùng, không phải của một prompt chép tay.

Dùng (từ `tools/`, có `CLAUDE_API_KEY` trong `.env`):

    python -m ocr_bench.vision                    # mọi trang vàng có công thức, run-<n> mới
    python -m ocr_bench.vision --pages 8 17 23 26 46
    python -m ocr_bench.vision --run 5            # ghi cạnh các model đã đo trong run-5

Gọi model thật: báo chi phí trước khi chạy (≈ $0,0004/trang với Claude Haiku 5.5).
"""

import argparse
import asyncio
import json
import os
import statistics
import time
from collections import Counter
from pathlib import Path

from document.config import Settings
from document.index.llm import FORMULA_CLAUDE, model_for, read_formulas
from document.pdf import open_pdf
from ocr_bench.gold import load_book
from ocr_bench.run import _BOOK, _GOLD, _PDF, _RUNS, next_run
from ocr_bench.score import formula_verdicts

_VERDICTS = ("khop", "tach", "gan", "lech", "thieu")


def _gold_formulas(pages: list[int] | None) -> dict[int, list[str]]:
    found = {
        page.page: [block.latex for block in page.blocks if block.latex]
        for page in load_book(_GOLD, _BOOK)
    }
    found = {page: formulas for page, formulas in found.items() if formulas}
    if pages:
        found = {page: found.get(page, []) for page in pages}
    return found


async def _read_all(settings: Settings, pages: list[int]) -> dict[int, dict]:
    model = model_for(
        settings, settings.formula_provider, settings.formula_model, claude=FORMULA_CLAUDE
    )
    if model is None:
        raise SystemExit(f"no key for {settings.formula_provider}: set it in .env")
    with open_pdf(_PDF.read_bytes()) as book:
        images = {page: book.render(page - 1, settings.formula_dpi) for page in pages}
    limit = asyncio.Semaphore(settings.llm_concurrency)

    async def one(page: int) -> tuple[int, dict]:
        async with limit:
            started = time.perf_counter()
            reading = await read_formulas(model, images[page])
            return page, {
                "seconds": round(time.perf_counter() - started, 2),
                "tokens": reading.tokens,
                "refused": reading.refused,
                "read": list(reading.formulas),
            }

    return dict(await asyncio.gather(*(one(page) for page in pages)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pages", type=int, nargs="*", help="Trang tệp; trống là mọi trang vàng.")
    parser.add_argument("--run", type=int, help="Ghi vào data/results/run-<n>.")
    options = parser.parse_args()

    os.chdir(Path(__file__).resolve().parents[2])
    settings = Settings()
    gold = _gold_formulas(options.pages)
    pages = sorted(gold)
    read = asyncio.run(_read_all(settings, pages))

    number = options.run or next_run([path.name for path in _RUNS.glob("run-*")])
    folder = _RUNS / f"run-{number}" / f"vision-{settings.formula_model}-product"
    (folder / "pages").mkdir(parents=True, exist_ok=True)
    totals: Counter[str] = Counter()
    lines = []
    for page in pages:
        verdicts = formula_verdicts(gold[page], read[page]["read"])
        totals.update(verdicts)
        record = {"page": page, **read[page], "gold": gold[page], "verdicts": verdicts}
        (folder / "pages" / f"{_BOOK}_p{page:03d}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
        )
        lines.append(f"p{page:03d}  {' '.join(verdicts) or '-'}  {read[page]['seconds']}s")
    seconds = [read[page]["seconds"] for page in pages]
    summary = {
        "model": settings.formula_model,
        "pages": pages,
        "gold": sum(len(gold[page]) for page in pages),
        **{verdict: totals[verdict] for verdict in _VERDICTS},
        "tokens": sum(read[page]["tokens"] for page in pages),
        "refused": [page for page in pages if read[page]["refused"]],
        "seconds_median": statistics.median(seconds) if seconds else 0,
    }
    lines.append(json.dumps(summary, ensure_ascii=False))
    (folder / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print(folder)


if __name__ == "__main__":
    main()
