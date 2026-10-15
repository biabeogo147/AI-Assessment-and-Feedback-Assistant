"""Chạy đường OCR trên bộ nhãn vàng và in bảng số.

Không chạy trong `.\\dev.ps1 check`, và không chạy được trên một máy không có `data/`. Đó là chủ
ý: 14 cuốn SGK có bản quyền và không bao giờ vào git, nên bộ đo là một việc làm tay có chủ đích
chứ không phải một cổng tự động. Thứ `check` canh là **test của thước đo**.

Kết quả engine thô được cache xuống `data/cache/`. Một lượt đọc 50 trang mất hàng chục phút;
một lượt tính điểm lại trên cache mất vài giây. Không có cache thì mỗi lần sửa một công thức
trong `score.py` là một buổi chiều.

**Mỗi lượt chạy để lại một bản ghi** ở `data/results/run-<n>/<model>/` (người dùng chốt 11/10/2026):
`report.txt` là đúng bảng in ra màn hình, `config.json` là tham số của lượt ấy, `pages/` là kết quả
engine từng trang. `<model>` là bộ nhận dạng -- `easyocr`, `vietocr-vgg_seq2seq` -- nên hai lựa
chọn chạy cùng một lượt thì nằm cạnh nhau dưới cùng một `run-<n>`. Không ghi đè: thư mục đã có
thì dừng, vì một bản ghi bị ghi đè là một phép so không còn đối chiếu lại được.

Dùng:
    python -m ocr_bench.run                 # 50 trang, dùng cache nếu có, ghi vào run-<n> mới
    python -m ocr_bench.run --pages 5       # 5 trang đầu, để thử nhanh
    python -m ocr_bench.run --fresh         # bỏ cache, đọc lại từ PDF
    python -m ocr_bench.run --reader vietocr  # đổi bộ nhận dạng chữ (mặc định easyocr)
    python -m ocr_bench.run --run 3 --reader vietocr  # ghi cạnh easyocr trong run-3
"""

import argparse
import contextlib
import io
import json
import re
import statistics
import sys
import time
from pathlib import Path

from document.ocr.model import BlockKind
from ocr_bench.gold import GoldInvalid, GoldPage, load_book
from ocr_bench.score import (
    cer,
    diacritic_error_rate,
    label_accuracy,
    match_blocks,
    missing_words,
    order_inversions,
    wer,
)

_BOOK = "L6T1"
_PDF = Path("data") / "Kết nối tri thức Lớp 6 tập 1.pdf"
_GOLD = Path("data") / "gold"
_CACHE = Path("data") / "cache"
# Kết quả đo nằm riêng ở `data/results/`, tách khỏi thứ bộ đo đọc vào (PDF, `gold/`, `cache/`) --
# người dùng chốt 13/10/2026.
_RUNS = Path("data") / "results"
_RUN_NAME = re.compile(r"^run-(\d+)$")
# Phiên bản đường đọc, nằm trong tên cache. Đổi chặng nào của `PageReader` thì tăng số này.
# `text1`: chỉ chữ, công thức không đọc lúc upload (11/10/2026).
# `text2`: khối hình giữ chữ của các dòng nằm trong nó (`document-agent-hierarchy`, D2). Nhãn vàng
# để khối hình rỗng, nên `_score_page` bỏ chữ ấy ra trước khi chấm -- bảng số của hai đường vẫn so
# được với nhau.
_PIPELINE = "text2"

_MISSING = f"""Không có dữ liệu để đo.

Cần hai thứ, và cả hai nằm **ngoài git** vì sách giáo khoa có bản quyền:
  - {_PDF}
  - {_GOLD}/{_BOOK}_p001.json ... (nhãn vàng)

Trên một máy sạch thì bộ đo này không chạy được, và đó là thiết kế chứ không phải một lỗi.
`.\\dev.ps1 check` không gọi tới đây."""


def main(argv: list[str] | None = None) -> int:
    """Chạy bộ đo.

    Args:
        argv: Tham số dòng lệnh, hoặc `None` để lấy từ `sys.argv`.

    Returns:
        0 khi chạy xong, 2 khi thiếu dữ liệu.
    """
    options = _parse(argv)

    try:
        gold = load_book(_GOLD, _BOOK)
    except GoldInvalid as missing:
        print(_MISSING, file=sys.stderr)
        print(f"\nchi tiết: {missing}", file=sys.stderr)
        return 2
    if not _PDF.is_file():
        print(_MISSING, file=sys.stderr)
        return 2

    model = model_tag(options.reader, options.model)
    names = [one.name for one in _RUNS.iterdir() if one.is_dir()] if _RUNS.exists() else []
    number = options.run or next_run(names)
    folder = _RUNS / f"run-{number}" / model
    # Kiểm **trước** khi đọc trang nào: phát hiện ra sau nửa giờ đọc là trả giá nửa giờ.
    if folder.exists():
        print(f"{folder} đã có. Chọn --run khác, hoặc bỏ --run để lấy số mới.", file=sys.stderr)
        return 2

    gold = gold[: options.pages]
    reads, fresh_pages = _read_pages(
        gold,
        fresh=options.fresh,
        dpi=options.dpi,
        reader=options.reader,
        model=options.model,
        threads=options.threads,
    )

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        _report(gold, reads)
    report = captured.getvalue()
    print(report, end="")

    (folder / "pages").mkdir(parents=True)
    (folder / "report.txt").write_text(report, encoding="utf-8")
    config = {
        "book": _BOOK,
        "pages": len(gold),
        "reader": options.reader,
        "vietocr_model": options.model if options.reader == "vietocr" else None,
        "dpi": options.dpi,
        "threads": options.threads,
        "fresh": options.fresh,
        # Trang lấy từ cache mang số giây của **lượt cũ**. Không ghi ra thì cột giây của bản ghi
        # này trộn hai lượt chạy mà không ai biết.
        "read_this_run": fresh_pages,
        "read_from_cache": [one.page for one in gold if one.page not in fresh_pages],
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (folder / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    for read in reads:
        (folder / "pages" / f"{_BOOK}_p{read['page']:03d}.json").write_text(
            json.dumps(read, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    print(f"\nđã ghi {folder}", file=sys.stderr)
    return 0


def model_tag(reader: str, vietocr_model: str) -> str:
    """Tên thư mục con của một cấu hình trong `run-<n>/`.

    Args:
        reader: Bộ nhận dạng chữ.
        vietocr_model: Cấu hình VietOCR; chỉ có nghĩa khi `reader == "vietocr"`.

    Returns:
        `easyocr`, hoặc `vietocr-<cấu hình>`.
    """
    return f"vietocr-{vietocr_model}" if reader == "vietocr" else reader


def cache_tag(dpi: int, reader: str, vietocr_model: str, threads: int) -> str:
    """Đuôi tên tệp cache của một cấu hình đọc. Hàm thuần.

    Số luồng viết đủ chữ (`threads4`), không viết `t4`: tên cache sống lâu hơn mọi plan, và `t4`
    đọc như mã task -- đúng thứ `task_code_in` bắt (người dùng chốt 14/10/2026). Đổi khuôn này thì
    mọi cache cũ thành mồ côi, như lần đổi `_PIPELINE`.

    Args:
        dpi: Độ phân giải dựng ảnh trang.
        reader: Bộ nhận dạng chữ.
        vietocr_model: Cấu hình VietOCR; chỉ vào tên khi `reader == "vietocr"`.
        threads: Số luồng CPU.

    Returns:
        Ví dụ `200_easyocr_threads4_text2`.
    """
    return f"{dpi}_{model_tag(reader, vietocr_model)}_threads{threads}_{_PIPELINE}"


def next_run(names: list[str]) -> int:
    """Số của lượt chạy kế tiếp: lớn nhất đã có cộng một.

    Không lấp chỗ trống: `run-1` và `run-3` có mặt thì lượt mới là `run-4`, không phải `run-2`.
    Một số đã từng dùng rồi bị xoá vẫn có thể đang được nhắc tới trong plan.

    Args:
        names: Tên các thư mục con của `data/results/` (thư mục `_RUNS`).

    Returns:
        Số lượt chạy mới, bắt đầu từ 1.
    """
    taken = [int(found.group(1)) for name in names if (found := _RUN_NAME.match(name))]
    return max(taken, default=0) + 1


# Một đoạn tên là mã task của plan: một chữ cái, các chữ số, có thể thêm một chữ cái -- `t5`,
# `T2b`, `a1`, `b2`. `L6T1` (Lớp 6 tập 1) không phải: hai cụm số. Tên model `o3`, `o4-mini` là
# tên thật nên được tha; `v1`, `v2` thì không -- cũng là một mã người ngoài không giải được. Luật
# đặt ở `unbiased-model-text`.
_TASK_CODE = re.compile(r"^(?!o\d+$)[a-z]\d+[a-z]?$", re.IGNORECASE)


def task_code_in(name: str) -> str:
    """Đoạn mã task của plan nằm trong một cái tên bền, hay chuỗi rỗng. Hàm thuần.

    Luật `AGENTS.md` (người dùng chốt 13/10/2026): id ca đo, nhãn lượt đo, thư mục kết quả sống
    lâu hơn plan đặt ra chúng, và người không đọc plan không giải được *"t5"*. Tên được tách theo
    mọi ký tự không phải chữ hay số (`-`, `_`, `.`, `,`, ngoặc, khoảng trắng); một đoạn khớp
    `_TASK_CODE` là vi phạm.

    Args:
        name: Tên cần soi.

    Returns:
        Đoạn đầu tiên trông như mã task, hay `""` khi không có.
    """
    parts = re.split(r"[^0-9a-zA-Z]+", name)
    return next((part for part in parts if _TASK_CODE.match(part)), "")


def _parse(argv: list[str] | None) -> argparse.Namespace:
    """Đọc tham số dòng lệnh.

    Args:
        argv: Tham số, hoặc `None`.

    Returns:
        Các tuỳ chọn đã phân tích.
    """
    parser = argparse.ArgumentParser(description="Đo chất lượng OCR trên nhãn vàng.")
    parser.add_argument("--pages", type=int, default=50, help="Số trang đo, tính từ trang 1.")
    parser.add_argument("--fresh", action="store_true", help="Bỏ cache, đọc lại từ PDF.")
    parser.add_argument("--dpi", type=int, default=200, help="Độ phân giải dựng ảnh trang.")
    parser.add_argument(
        "--reader", default="easyocr", choices=("easyocr", "vietocr"), help="Bộ nhận dạng chữ."
    )
    parser.add_argument(
        "--model", default="vgg_seq2seq", help="Cấu hình VietOCR, khi --reader vietocr."
    )
    parser.add_argument("--threads", type=int, default=4, help="Số luồng CPU, như một VPS.")
    parser.add_argument(
        "--run",
        type=int,
        default=None,
        help="Ghi vào data/results/run-<n>; bỏ trống để lấy số mới.",
    )
    return parser.parse_args(argv)


def _read_pages(
    gold: list[GoldPage], fresh: bool, dpi: int, reader: str, model: str, threads: int
) -> tuple[list[dict], list[int]]:
    """Đọc từng trang, dùng cache khi có.

    Model chỉ được nạp khi thật sự có trang cần đọc: nạp ba model mất vài giây, và một
    lượt tính điểm lại hoàn toàn trên cache không nên trả cái giá ấy.

    Args:
        gold: Các trang nhãn vàng.
        fresh: True thì bỏ cache.
        dpi: Độ phân giải dựng ảnh.
        reader: Bộ nhận dạng chữ.
        model: Cấu hình VietOCR.
        threads: Số luồng CPU.

    Returns:
        Một dict cho mỗi trang, cùng thứ tự với `gold`; và số các trang **đọc mới** trong lượt
        này, khác với trang lấy từ cache.
    """
    _CACHE.mkdir(parents=True, exist_ok=True)
    engine = None
    raw = None
    fresh_pages: list[int] = []
    # Mọi thứ đổi được chữ đọc ra phải nằm trong tên cache. Thiếu `reader` ở đây thì một lượt
    # EasyOCR sẽ đọc lại cache của VietOCR và in ra một bảng số không đo gì cả. Số luồng thì
    # không đổi chữ, chỉ đổi giây -- nhưng giây cũng là thứ đang được đo.
    #
    # `_PIPELINE` cũng vậy: cache của đường cũ (chữ + công thức, trước 11/10/2026) mang số giây có
    # chặng `formula` của PP-FormulaNet. Thiếu nó trong tên thì một lượt chạy đường mới đọc lại
    # cache cũ, in ra giây của đường cũ, và không chạy một dòng code mới nào.
    tag = cache_tag(dpi, reader, model, threads)
    out: list[dict] = []

    for one in gold:
        cached = _CACHE / f"{_BOOK}_p{one.page:03d}_{tag}.json"
        if cached.is_file() and not fresh:
            out.append(json.loads(cached.read_text(encoding="utf-8")))
            continue

        if engine is None:
            start = time.time()
            from document.ocr.page import PageReader

            engine = PageReader(dpi=dpi, reader=reader, vietocr_model=model, threads=threads)
            raw = _PDF.read_bytes()
            print(f"nạp model: {time.time() - start:.1f}s", file=sys.stderr)

        read = engine.read_page(raw, one.page - 1)
        payload = {
            "page": read.page,
            "seconds": read.seconds,
            "blocks": [{"kind": block.kind.value, "text": block.text} for block in read.blocks],
        }
        cached.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        out.append(payload)
        fresh_pages.append(one.page)
        print(
            f"  trang {read.page:3d}: {len(read.blocks):3d} khối, "
            f"{sum(read.seconds.values()):5.1f}s",
            file=sys.stderr,
        )
    return out, fresh_pages


def _report(gold: list[GoldPage], reads: list[dict]) -> None:
    """In bảng số.

    Args:
        gold: Các trang nhãn vàng.
        reads: Kết quả engine, cùng thứ tự.
    """
    rows = [_score_page(one, read) for one, read in zip(gold, reads, strict=True)]

    print(
        f"\n{'trang':>5} {'thiếu':>7} {'CER':>7} {'WER':>7} {'dấu':>7} {'nhãn':>7} "
        f"{'đảo':>5} {'giây':>7}"
    )
    print("-" * 58)
    for row in rows:
        print(
            f"{row['page']:5d} {row['missing']:7.3f} {row['cer']:7.3f} {row['wer']:7.3f} "
            f"{row['marks']:7.3f} {row['labels']:7.3f} {row['inversions']:5d} "
            f"{row['seconds']:7.1f}"
        )

    print("\n--- gộp ---")
    for name, key in (
        ("thiếu từ", "missing"),
        ("CER", "cer"),
        ("WER", "wer"),
        ("lỗi dấu", "marks"),
        ("nhãn đúng", "labels"),
    ):
        values = [row[key] for row in rows]
        print(
            f"{name:10s} trung vị {statistics.median(values):6.3f}   "
            f"p90 {_percentile(values, 0.9):6.3f}   tệ nhất {max(values):6.3f}"
        )

    seconds = [row["seconds"] for row in rows]
    print(
        f"{'giây/trang':10s} trung vị {statistics.median(seconds):6.1f}   tổng {sum(seconds):.0f}"
    )
    _stages(reads)


def _score_page(one: GoldPage, read: dict) -> dict:
    """Chấm một trang.

    Args:
        one: Trang nhãn vàng.
        read: Kết quả engine của đúng trang ấy.

    Returns:
        Một hàng của bảng.
    """
    gold_texts = [block.text for block in one.blocks]
    read_texts = [
        "" if block["kind"] == BlockKind.IMAGE.value else block["text"] for block in read["blocks"]
    ]
    whole_gold = " ".join(text for text in gold_texts if text)
    whole_read = " ".join(text for text in read_texts if text)

    matched = match_blocks(gold_texts, read_texts)

    return {
        "page": one.page,
        "missing": missing_words(whole_gold, whole_read),
        "cer": cer(whole_gold, whole_read),
        "wer": wer(whole_gold, whole_read),
        "marks": diacritic_error_rate(whole_gold, whole_read),
        "labels": label_accuracy(
            [block.kind.value for block in one.blocks],
            [block["kind"] for block in read["blocks"]],
        ),
        "inversions": order_inversions(matched),
        "seconds": sum(read["seconds"].values()),
    }


def _stages(reads: list[dict]) -> None:
    """In thời gian theo chặng.

    Câu hỏi đang treo của `document-ocr-text-and-latex` là *chặng nào đắt*: 1 561 trang ở nhịp hiện
    tại là nhiều giờ, và một con số tổng không nói được cắt chỗ nào.

    Args:
        reads: Kết quả engine.
    """
    stages: dict[str, list[float]] = {}
    for read in reads:
        for stage, spent in read["seconds"].items():
            stages.setdefault(stage, []).append(spent)
    for stage, values in stages.items():
        share = sum(values) / sum(sum(v) for v in stages.values())
        print(f"  {stage:10s} trung vị {statistics.median(values):6.1f}s  ({share:.0%} thời gian)")


def _percentile(values: list[float], at: float) -> float:
    """Phân vị, lấy theo phần tử gần nhất.

    Không nội suy: 50 trang là một mẫu nhỏ, và một phép nội suy ở đây chỉ làm con số trông chính
    xác hơn thực tế.

    Args:
        values: Các giá trị.
        at: Phân vị cần lấy, từ 0,0 tới 1,0.

    Returns:
        Giá trị ở phân vị ấy.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(at * len(ordered)))]


if __name__ == "__main__":
    sys.exit(main())
