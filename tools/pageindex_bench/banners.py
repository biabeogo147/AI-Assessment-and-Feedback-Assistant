"""Đọc banner mở chương của một tài liệu bằng `gpt-5.6-luna`, qua đúng đường mà worker dùng.

Ghi ra một tệp JSON cho `pageindex_bench.run --banners`, để mọi đường phân loại được so trên cùng
một bộ tên chương. Ảnh lấy từ PDF trong `data/` chứ không từ MinIO: bộ đo chạy trên máy dev.

Dùng:
    python -m pageindex_bench.banners --document <id> --pdf <tệp.pdf> --out <banners.json>
"""

import argparse
import asyncio
import json
from pathlib import Path

from document.config import get_settings
from document.content_store import ContentStore
from document.index.features import banner_gates
from document.index.llm import model_for, read_banner
from document.pdf import open_pdf

# Phần trên của trang gửi luna: banner chương và dải tên bài đầu tiên, đo trên Lớp 6 tập 1 (dải bài
# nằm ở 45--65% chiều cao trang).
BANNER_TOP = 0.75
BANNER_DPI = 150


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    settings = get_settings()
    store = ContentStore(settings.mongo_url, settings.mongo_database)
    pages = await store.pages(args.document)
    await store.close()
    gates = banner_gates(pages)
    model = model_for(
        settings, settings.banner_provider, settings.banner_model, reasoning_effort="low"
    )
    if model is None:
        raise SystemExit(f"thiếu khoá của {settings.banner_provider} cho banner_model")
    with open_pdf(args.pdf.read_bytes()) as book:
        images = {gate.page: book.render(gate.page - 1, BANNER_DPI, BANNER_TOP) for gate in gates}

    rows, tokens = [], 0
    for gate in gates:
        read = await read_banner(model, images[gate.page])
        tokens += read.tokens
        print(gate.page, read)
        if not read.is_opening:
            continue
        word = "Phần" if read.kind == "phần" else "Chương"
        rows.append(
            {
                "page": gate.page,
                "chapter_label": f"{word} {read.number}" if read.number else None,
                "chapter_title": read.title,
                "lesson_label": f"Bài {read.lesson_number}" if read.lesson_number else None,
                "lesson_title": read.lesson_title,
            }
        )
    args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(gates)} cổng, {len(rows)} banner, {tokens} token -> {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
