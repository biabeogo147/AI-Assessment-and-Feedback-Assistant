"""Graph của document agent: bản thô trong Mongo → cây ba cấp, chunk, tóm tắt → Mongo.

Một đường thẳng bảy bước, mỗi bước một node LangGraph:

    load → banners → classify → assemble → chunk → summarise → write

Thẳng chứ không rẽ, vì mọi nhánh *"nếu hỏng thì sao"* đã nằm **trong** từng bước: Jev không với tới
được thì `classify` đi đường luật (D5); luna không đọc được banner thì chương mang nhãn số (D6); một
lời tóm tắt hỏng thì nút ấy không có tóm tắt. Không bước nào làm hỏng cả cây vì một model ngoài --
tài liệu vẫn *sẵn sàng*, chỉ kém hơn, và `IndexHeader` nói kém ở đâu.

Thứ duy nhất làm job chạy lại là kho nội dung không với tới được (`ContentStoreUnavailable`), và
thứ duy nhất làm job bỏ cuộc mà không báo gì là bản thô đã bị đọc lại giữa chừng (`RawChanged`) --
lần đọc mới tự đẩy job dựng cây của nó.

**Phụ thuộc đi vào qua `Deps`**, không qua import: test thay Jev, model và kho bằng bản giả mà không
chạm mạng, đúng cách `agent/llm.py` cho bộ test của AGENT miễn phí.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from contracts import (
    BlockLabel,
    DocumentIndexRequested,
    IndexChunk,
    IndexHeader,
    IndexMethod,
    IndexNode,
    RawDocument,
    RawPage,
)
from document.config import Settings
from document.content_store import ContentStore, RawChanged
from document.index import chunks as chunking
from document.index.assemble import Banner, assemble, headings
from document.index.features import (
    Candidate,
    banner_gates,
    candidates,
    page_offset,
    printed_pages,
    to_roman,
    units,
)
from document.index.jev import JevUnavailable, open_paths, state_of
from document.index.llm import BannerReading, Summary
from document.index.rules import Decision, combine, decide
from document.pdf import open_pdf

logger = logging.getLogger(__name__)

# Phần trên của trang mở chương gửi luna, và độ phân giải. Đo trên Lớp 6 tập 1: dải tên bài đầu
# chương nằm ở 45--65% chiều cao trang; 150 DPI là cấu hình phép đo VLM của plan 3a.
BANNER_TOP = 0.75
BANNER_DPI = 150
# Trần ký tự chữ của một nút gửi đi tóm tắt: đủ cho một mục, không trả token cho cả một chương.
_SUMMARY_INPUT_CHARS = 4000
# Phần chữ mở đầu của một nút có con, gửi kèm tóm tắt của các con.
_INTRO_CHARS = 1200
# Chữ của một nút dài không quá tiêu đề cộng chừng này thì coi như nút không có chữ.
_TITLE_SLACK_CHARS = 10


class NothingToIndex(RuntimeError):
    """Kho nội dung không có bản thô nào cho tài liệu -- đã bị xoá, hoặc DB vừa dựng lại."""


@dataclass(frozen=True)
class Deps:
    """Mọi thứ graph cần từ bên ngoài.

    Attributes:
        store: Kho nội dung.
        settings: Setting của worker.
        read_file: Đọc byte của tệp từ object storage, theo khoá.
        jev: Hỏi Jev cho một danh sách `state`; trả `JevRun`. `None` khi không có khoá Jev.
        read_banner: Đọc một ảnh banner; `None` khi không có khoá OpenAI.
        summarise: Tóm tắt `(tiêu đề, nội dung)`; `None` khi không có khoá OpenAI.
        tell: Báo `services/ingest` rằng job vẫn sống -- giữ chip khỏi *xử lý hỏng* (D3).
    """

    store: ContentStore
    settings: Settings
    read_file: Callable[[str], Awaitable[bytes]]
    jev: Callable[[list[dict]], Awaitable[Any]] | None
    read_banner: Callable[[bytes], Awaitable[BannerReading]] | None
    summarise: Callable[[str, str], Awaitable[Summary]] | None
    tell: Callable[[int], Awaitable[None]]


class IndexState(TypedDict, total=False):
    """Những gì chảy qua graph."""

    asked: DocumentIndexRequested
    raw: RawDocument
    pages: list[RawPage]
    banners: list[Banner]
    candidates: list[Candidate]
    decisions: list[Decision]
    method: IndexMethod
    jev_model: str | None
    jev_tokens: int
    summary_tokens: int
    banner_tokens: int
    low_confidence: int
    nodes: list[IndexNode]
    chunks: list[IndexChunk]
    header: IndexHeader


def build(deps: Deps):
    """Dựng graph đã compile.

    Args:
        deps: Phụ thuộc.

    Returns:
        Một graph LangGraph; `await graph.ainvoke({"asked": ...})` trả state cuối.
    """
    graph = StateGraph(IndexState)
    steps = {
        "load": _load,
        "banners": _banners,
        "classify": _classify,
        "assemble": _assemble,
        "chunk": _chunk,
        "summarise": _summarise,
        "write": _write,
    }
    names = list(steps)
    for name, step in steps.items():
        graph.add_node(name, _bound(step, deps))
    graph.set_entry_point(names[0])
    for left, right in zip(names, names[1:], strict=False):
        graph.add_edge(left, right)
    graph.add_edge(names[-1], END)
    return graph.compile()


def _bound(step, deps: Deps):
    async def run(state: IndexState) -> dict:
        return await step(state, deps)

    return run


async def _load(state: IndexState, deps: Deps) -> dict:
    document_id = state["asked"].document_id
    raw = await deps.store.raw(document_id)
    pages = await deps.store.pages(document_id)
    if raw is None or not pages:
        raise NothingToIndex(f"no raw content for {document_id}")
    if raw.finished_at is None:
        # Một lần đọc mới đang chạy: dựng trên trang dở dang là gửi `READY` kèm một cây thiếu
        # trang (review Task 4). Lô OCR cuối của lần đọc ấy sẽ giao lại job dựng cây.
        raise RawChanged(f"the raw content of {document_id} is still being read")
    await deps.tell(len(pages))
    return {"raw": raw, "pages": pages, "jev_tokens": 0, "summary_tokens": 0, "banner_tokens": 0}


async def _banners(state: IndexState, deps: Deps) -> dict:
    """Banner mở chương (D9): cổng OCR, rồi luna đọc tên ở trang qua cổng."""
    gates = banner_gates(state["pages"])
    if not gates:
        return {"banners": []}
    readings: dict[int, BannerReading] = {}
    tokens = 0
    if deps.read_banner is not None:
        try:
            raw = await deps.read_file(state["asked"].storage_key)
            images = await asyncio.to_thread(_render_tops, raw, [gate.page for gate in gates])
        except Exception:
            # Không có ảnh thì không có tên -- chương vẫn mang nhãn số. Không làm hỏng cả cây vì
            # một tệp object storage chập chờn hay một trang dựng hỏng.
            logger.exception("could not render banners of %s", state["asked"].document_id)
            images = {}
        limit = asyncio.Semaphore(deps.settings.llm_concurrency)
        refused: set[int] = set()

        async def one(page: int, image: bytes) -> None:
            nonlocal tokens
            async with limit:
                try:
                    read = await deps.read_banner(image)
                except Exception:
                    logger.exception("banner model failed on page %s", page)
                    return
            tokens += read.tokens
            if read.is_opening:
                readings[page] = read
            elif read.title is None and read.number is None and read.kind is None:
                # Luna nói **rõ** đây không phải trang mở đầu -- khác với luna hỏng, khi cổng vẫn
                # thắng và chương mang nhãn số (review Task 4).
                refused.add(page)
            # Một nhịp tim mỗi banner: một lời gọi chậm có thể tới ~60 s khi OpenAI đang ốm.
            await deps.tell(len(state["pages"]))

        await asyncio.gather(*(one(page, image) for page, image in images.items()))
        gates = [gate for gate in gates if gate.page not in refused]
    # Nhãn lùi *"Chương N"* đếm **chỉ** những cổng được giữ: một cổng giả không làm lệch số của mọi
    # chương sau nó.
    banners = [
        _banner(gate, number, readings.get(gate.page)) for number, gate in enumerate(gates, 1)
    ]
    return {"banners": banners, "banner_tokens": state["banner_tokens"] + tokens}


def _render_tops(raw: bytes, pages: list[int]) -> dict[int, bytes]:
    with open_pdf(raw) as book:
        return {page: book.render(page - 1, BANNER_DPI, BANNER_TOP) for page in pages}


def _banner(gate, number: int, read: BannerReading | None) -> Banner:
    """Một banner từ lần đọc của luna, hoặc chỉ nhãn số khi không đọc được.

    Args:
        gate: Khối qua cổng.
        number: Thứ tự cổng, đếm từ 1 -- nhãn lùi khi luna không đọc ra số.
        read: Lần đọc, `None` khi không có.

    Returns:
        Banner.
    """
    fallback = f"Chương {to_roman(number)}"
    if read is None:
        return Banner(gate, fallback)
    word = "Phần" if read.kind == "phần" else "Chương"
    return Banner(
        ref=gate,
        chapter_label=f"{word} {read.number}" if read.number else fallback,
        chapter_title=read.title,
        lesson_label=f"Bài {read.lesson_number}" if read.lesson_number else None,
        lesson_title=read.lesson_title,
    )


async def _classify(state: IndexState, deps: Deps) -> dict:
    """Jev quyết từng ứng viên, luật quyết thay khi Jev không chắc hoặc không với tới được."""
    found = candidates(state["pages"])
    ruled = [decide(candidate) for candidate in found]
    method, model, tokens, low = IndexMethod.RULES, None, 0, 0
    decisions = ruled
    if deps.jev is not None and found:
        chapters = {
            banner.ref.page: banner.chapter_title or banner.chapter_label
            for banner in state["banners"]
        }
        paths = open_paths(found, ruled, chapters)
        states = [state_of(candidate, path) for candidate, path in zip(found, paths, strict=True)]
        try:
            asked = await deps.jev(states)
        except JevUnavailable:
            logger.warning("jev unavailable for %s; using rules", state["asked"].document_id)
        else:
            threshold = deps.settings.jev_min_confidence
            decisions = [
                combine(one, rule, threshold)
                for one, rule in zip(asked.decisions, ruled, strict=True)
            ]
            method, model, tokens = IndexMethod.JEV, asked.model, asked.tokens
            low = sum(one.confidence < threshold for one in asked.decisions)
    await deps.tell(len(state["pages"]))
    return {
        "candidates": found,
        "decisions": decisions,
        "method": method,
        "jev_model": model,
        "jev_tokens": tokens,
        "low_confidence": low,
    }


async def _assemble(state: IndexState, deps: Deps) -> dict:
    printed = printed_pages(state["pages"])
    decided = list(zip(state["candidates"], state["decisions"], strict=True))
    nodes = assemble(
        state["asked"].document_id,
        headings(decided, state["banners"]),
        len(state["pages"]),
        printed,
        page_offset(printed),
    )
    return {"nodes": nodes}


async def _chunk(state: IndexState, deps: Deps) -> dict:
    every = units(state["pages"])
    return {"chunks": chunking.build_chunks(state["asked"].document_id, every, state["nodes"])}


async def _summarise(state: IndexState, deps: Deps) -> dict:
    """Tóm tắt từ dưới lên (D6): cấp 3 từ chữ của nó, cha từ tóm tắt của con cộng phần mở đầu."""
    nodes = list(state["nodes"])
    if deps.summarise is None or not nodes:
        return {}
    limit = asyncio.Semaphore(deps.settings.llm_concurrency)
    tokens = 0
    finished = 0

    async def one(node: IndexNode, body: str) -> IndexNode:
        nonlocal tokens, finished
        title = f"{node.numbering} {node.title}" if node.numbering else node.title
        if len(body.strip()) <= len(title) + _TITLE_SLACK_CHARS:
            # Chunk của nút chứa chính dòng tiêu đề, nên *"không có chữ"* nghĩa là chỉ còn tiêu đề
            # (OCR bỏ sót cả mục). Hỏi tóm tắt chừng ấy là mời model bịa (review Task 4): không
            # tóm tắt còn hơn tóm tắt sai.
            return node
        async with limit:
            try:
                done = await deps.summarise(title, body)
            except Exception:
                logger.exception("summary failed for node %s", node.ordinal)
                return node
        tokens += done.tokens
        finished += 1
        # Nhịp tim theo lượt song song, không chỉ ở ranh giới cấp: ~50 mục cấp 3 với OpenAI chậm
        # có thể vượt ngưỡng 300 s của BE trước khi cả cấp xong.
        if finished % deps.settings.llm_concurrency == 0:
            await deps.tell(len(state["pages"]))
        return node.model_copy(update={"summary": done.text or None})

    for level in (3, 2, 1):
        work = []
        for node in nodes:
            if node.level != level:
                continue
            children = [child for child in nodes if child.parent_ordinal == node.ordinal]
            own = chunking.node_text(state["chunks"], node.ordinal, _SUMMARY_INPUT_CHARS)
            if children:
                listed = "\n".join(
                    f"- {child.numbering or ''} {child.title}: {child.summary or ''}".strip()
                    for child in children
                )
                body = f"{own[:_INTRO_CHARS]}\n\nCác phần con:\n{listed}"
            else:
                body = own
            work.append(one(node, body))
        for done in await asyncio.gather(*work):
            nodes[done.ordinal] = done
        await deps.tell(len(state["pages"]))
    return {"nodes": nodes, "summary_tokens": state["summary_tokens"] + tokens}


async def _write(state: IndexState, deps: Deps) -> dict:
    """Ghi cây. Chỉ sau bước này `index_handlers` mới được gửi READY.

    *"Chunk trước, `state` sau"*: cây vào Mongo rồi chip mới đổi.
    """
    raw, asked = state["raw"], state["asked"]
    labels = [
        BlockLabel(
            document_id=asked.document_id,
            ref=candidate.unit.ref,
            ocr_kind=candidate.unit.kind,
            text=candidate.unit.text.strip()[:200],
            numbering=candidate.numbering.label if candidate.numbering else None,
            role=decision.role,
            role_probabilities=decision.role_probabilities,
            level=decision.level if decision.is_node else None,
            level_probabilities=decision.level_probabilities,
            confidence=decision.confidence,
            decided_by=decision.decided_by,
        )
        for candidate, decision in zip(state["candidates"], state["decisions"], strict=True)
    ]
    printed = printed_pages(state["pages"])
    header = IndexHeader(
        document_id=asked.document_id,
        raw_started_at=raw.started_at,
        raw_pipeline=raw.pipeline,
        method=state["method"],
        jev_model=state["jev_model"],
        summary_model=deps.settings.summary_model if deps.summarise else None,
        node_count=len(state["nodes"]),
        chunk_count=len(state["chunks"]),
        low_confidence=state["low_confidence"],
        page_offset=page_offset(printed),
        jev_tokens=state["jev_tokens"],
        summary_tokens=state["summary_tokens"],
        banner_model=deps.settings.banner_model if deps.read_banner else None,
        banner_tokens=state["banner_tokens"],
        built_at=datetime.now(UTC),
    )
    await deps.store.put_index(header, state["nodes"], state["chunks"], labels)
    logger.info(
        "indexed document=%s nodes=%s chunks=%s method=%s",
        asked.document_id,
        header.node_count,
        header.chunk_count,
        header.method.value,
    )
    return {"header": header}
