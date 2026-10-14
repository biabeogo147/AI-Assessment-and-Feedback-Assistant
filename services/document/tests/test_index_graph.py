"""Graph dựng cây và job `index_document` (`document-agent-hierarchy`, Task 4), không chạm mạng:
Jev, luna, tóm tắt và kho nội dung đều là bản giả. Thứ được canh là **thứ tự** và **đường lùi**: cây
ghi trước `READY`; Jev hay OpenAI hỏng thì cây vẫn dựng được, chỉ kém hơn.
"""

from datetime import UTC, datetime

import pymupdf
import pytest
from arq.worker import Retry

from contracts import (
    DOCUMENT_PROBED_TASK,
    DOCUMENT_PROGRESS_TASK,
    BlockRef,
    DecidedBy,
    DocumentIndexRequested,
    DocumentState,
    IndexMethod,
    IndexNode,
    RawBlock,
    RawDocument,
    RawPage,
    RawSource,
    TitleSource,
)
from document.config import get_settings
from document.content_store import ContentStoreUnavailable, RawChanged
from document.index.chunks import build_chunks
from document.index.features import units
from document.index.graph import Deps, build
from document.index.jev import JevRun, JevUnavailable
from document.index.llm import BannerReading, Summary
from document.index.rules import BOOK_SECTION, DEEPER, NOT_HEADING, Decision
from document.index_handlers import index_document
from document.ocr_handlers import MAX_TRIES

_AT = datetime(2026, 10, 11, tzinfo=UTC)
_BANNER = (0.0, 0.0, 1517.0, 1256.0)


def _page(number: int, *blocks: tuple[str, tuple | None, str]) -> RawPage:
    return RawPage(
        document_id="doc-1",
        page=number,
        source=RawSource.OCR,
        width=1520.0,
        height=2100.0,
        blocks=tuple(RawBlock(kind=kind, box=box, text=text) for kind, box, text in blocks),
        read_at=_AT,
    )


def _book() -> list[RawPage]:
    return [
        _page(
            1,
            ("image", _BANNER, "0 CHƯƠNG sấ HỌc"),
            ("text", (134.0, 1500.0, 1381.0, 1600.0), "Khi tính toán với những số nhỏ"),
        ),
        _page(
            2,
            ("doc_title", (366.0, 127.0, 994.0, 186.0), "CÁCH GHI SỐ TỰ NHIÊN"),
            ("paragraph_title", (140.0, 970.0, 481.0, 1007.0), "1. HỆ THẬP PHÂN"),
            ("paragraph_title", (205.0, 1092.0, 793.0, 1126.0), "Cách ghi số trong hệ thập phân"),
            ("text", (160.0, 1200.0, 1300.0, 1300.0), "Ta dùng mười chữ số"),
        ),
    ]


def _pdf(pages: int = 2) -> bytes:
    book = pymupdf.open()
    for _ in range(pages):
        book.new_page()
    raw = book.tobytes()
    book.close()
    return raw


class _Store:
    def __init__(self, log: list[str], pages: list[RawPage] | None = None) -> None:
        self.log = log
        self._pages = _book() if pages is None else pages
        self.written: tuple | None = None
        self.header = None
        self.raw_doc = RawDocument(
            document_id="doc-1", source=RawSource.OCR, started_at=_AT, finished_at=_AT
        )
        self.change_raw = False
        self.down = False

    async def raw(self, document_id: str) -> RawDocument | None:
        return self.raw_doc

    async def pages(self, document_id: str) -> list[RawPage]:
        if self.down:
            raise ContentStoreUnavailable("mongo is down")
        return self._pages

    async def indexed(self, document_id: str):
        return self.header

    async def put_index(self, header, nodes, chunks, labels) -> None:
        if self.change_raw:
            raise RawChanged("read again")
        self.log.append("put index")
        self.written = (header, nodes, chunks, labels)


async def _jev(states: list[dict]) -> JevRun:
    """Jev giả: trả đúng điều luật sẽ nói, với confidence cao."""
    out = []
    for state in states:
        text = state["block"]["text"]
        if text == "CÁCH GHI SỐ TỰ NHIÊN":
            out.append(Decision(BOOK_SECTION, 2, 0.95, DecidedBy.JEV))
        elif text.startswith("1."):
            out.append(Decision(BOOK_SECTION, 3, 0.9, DecidedBy.JEV))
        elif text.startswith("Cách"):
            out.append(Decision(BOOK_SECTION, DEEPER, 0.9, DecidedBy.JEV))
        else:
            out.append(Decision(NOT_HEADING, None, 0.9, DecidedBy.JEV))
    return JevRun(out, tokens=100 * len(states), model="jev-1.13.0")


async def _jev_down(states: list[dict]) -> JevRun:
    raise JevUnavailable("overloaded")


async def _luna(png: bytes) -> BannerReading:
    assert png.startswith(b"\x89PNG")
    return BannerReading(True, "chương", "I", "TẬP HỢP CÁC SỐ TỰ NHIÊN", "1", "TẬP HỢP", 50)


async def _summary(title: str, body: str) -> Summary:
    return Summary(f"tóm tắt: {title}", 10)


def _deps(store: _Store, told: list[int], **overrides) -> Deps:
    async def read_file(key: str) -> bytes:
        return _pdf()

    async def tell(pages: int) -> None:
        told.append(pages)

    base = {
        "store": store,
        "settings": get_settings(),
        "read_file": read_file,
        "jev": _jev,
        "read_banner": _luna,
        "summarise": _summary,
        "tell": tell,
    }
    base.update(overrides)
    return Deps(**base)


def _asked() -> DocumentIndexRequested:
    return DocumentIndexRequested(
        document_id="doc-1", storage_key="documents/gv/doc-1", filename="sach.pdf", page_count=2
    )


# --- graph ---


@pytest.mark.asyncio
async def test_the_graph_builds_a_three_level_tree_with_summaries() -> None:
    store, told = _Store([]), []
    await build(_deps(store, told)).ainvoke({"asked": _asked()})

    header, nodes, chunks, labels = store.written
    shown = [(n.level, n.numbering, n.title, n.title_source) for n in nodes]
    assert shown == [
        (1, "Chương I", "TẬP HỢP CÁC SỐ TỰ NHIÊN", TitleSource.BANNER),
        (2, "Bài 1", "TẬP HỢP", TitleSource.BANNER),
        (2, None, "CÁCH GHI SỐ TỰ NHIÊN", TitleSource.TEXT),
        (3, "1.", "HỆ THẬP PHÂN", TitleSource.TEXT),
    ]
    assert all(node.summary and node.summary.startswith("tóm tắt") for node in nodes)
    assert (header.method, header.jev_model, header.node_count) == (
        IndexMethod.JEV,
        "jev-1.13.0",
        4,
    )
    assert header.raw_started_at == _AT
    # Hai model khác giá: đọc banner (50) và tóm tắt (10 mỗi nút) đếm riêng.
    assert (header.banner_tokens, header.summary_tokens) == (50, 10 * 4)
    assert header.banner_model == get_settings().banner_model
    assert len(labels) == 3
    assert len(told) >= 3


@pytest.mark.asyncio
async def test_a_deeper_heading_stays_inside_its_parent_chunk() -> None:
    store = _Store([])
    await build(_deps(store, [])).ainvoke({"asked": _asked()})
    _, nodes, chunks, _ = store.written
    section = next(node for node in nodes if node.level == 3)
    [chunk] = [chunk for chunk in chunks if chunk.node_ordinal == section.ordinal]
    assert "Cách ghi số trong hệ thập phân" in chunk.text
    assert "Ta dùng mười chữ số" in chunk.text


@pytest.mark.asyncio
async def test_jev_down_builds_the_tree_by_the_rules() -> None:
    store = _Store([])
    await build(_deps(store, [], jev=_jev_down)).ainvoke({"asked": _asked()})
    header, nodes, _, labels = store.written
    assert (header.method, header.jev_model) == (IndexMethod.RULES, None)
    assert [n.level for n in nodes] == [1, 2, 2, 3]
    assert all(label.decided_by is DecidedBy.RULES for label in labels)


@pytest.mark.asyncio
async def test_a_banner_that_cannot_be_read_keeps_the_chapter_number_and_invents_no_name() -> None:
    async def blind(png: bytes) -> BannerReading:
        raise TimeoutError("luna timed out")

    store = _Store([])
    await build(_deps(store, [], read_banner=blind)).ainvoke({"asked": _asked()})
    first = store.written[1][0]
    assert (first.numbering, first.title, first.title_source) == (
        "Chương I",
        "Chương I",
        TitleSource.NUMBERING,
    )


@pytest.mark.asyncio
async def test_a_failed_summary_leaves_the_node_without_one() -> None:
    async def broken(title: str, body: str) -> Summary:
        raise TimeoutError("openai timed out")

    store = _Store([])
    await build(_deps(store, [], summarise=broken)).ainvoke({"asked": _asked()})
    assert all(node.summary is None for node in store.written[1])


# --- chunks ---


def test_chunks_follow_anchors_split_at_the_cap_and_keep_the_front_matter() -> None:
    every = units(_book())
    node = IndexNode(
        document_id="doc-1",
        ordinal=0,
        level=1,
        title="CÁCH GHI",
        title_source=TitleSource.TEXT,
        anchor=BlockRef(page=2, block=0),
        page_start=2,
        page_end=2,
    )
    chunks = build_chunks("doc-1", every, [node], max_chars=40)
    assert chunks[0].node_ordinal is None
    assert chunks[0].text == "Khi tính toán với những số nhỏ"
    owned = [chunk for chunk in chunks if chunk.node_ordinal == 0]
    assert len(owned) >= 2
    assert all(chunk.char_count <= 40 for chunk in owned)
    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))


# --- index_document ---


class _Queue:
    def __init__(self, log: list[str], down: bool = False) -> None:
        self.log = log
        self.down = down
        self.jobs: list[tuple[str, dict]] = []

    async def enqueue_job(self, name: str, payload: dict, _queue_name: str = "", _job_id=None):
        if self.down:
            from redis.exceptions import ConnectionError as RedisConnectionError

            raise RedisConnectionError("redis is down")
        self.jobs.append((name, payload))
        if name == DOCUMENT_PROBED_TASK:
            self.log.append(f"hand back {payload['state']}")
        return object()


class _Reader:
    async def read(self, key: str) -> bytes:
        return _pdf()


@pytest.fixture
def no_models(monkeypatch):
    """Không khoá Jev, không model OpenAI: job đi đường luật, không chạm mạng."""
    settings = get_settings()
    monkeypatch.setattr(settings, "jev_api_key", "")


@pytest.mark.asyncio
async def test_ready_leaves_only_after_the_index_is_written(no_models) -> None:
    """*"Chunk trước, `state` sau"*: đảo lại là một khoảnh khắc chip *sẵn sàng* mà không có cây."""
    log: list[str] = []
    store, queue = _Store(log), _Queue(log)
    ctx = {"store": store, "redis": queue, "reader": _Reader()}
    await index_document(ctx, _asked().model_dump(mode="json"))
    assert log == ["put index", "hand back ready"]
    [(_, done)] = [job for job in queue.jobs if job[0] == DOCUMENT_PROBED_TASK]
    assert (done["state"], done["page_count"]) == (DocumentState.READY, 2)
    assert any(name == DOCUMENT_PROGRESS_TASK for name, _ in queue.jobs)


@pytest.mark.asyncio
async def test_a_raw_read_replaced_and_finished_builds_again_on_the_new_one(no_models) -> None:
    """Lần đọc mới đã xong: bỏ ở đây là không còn ai dựng cây, vì job của lần đọc mới bị từ chối
    bởi id cố định trong lúc job này còn chạy (review Task 4, `document-agent-hierarchy`). Nên chạy
    lại."""
    log: list[str] = []
    store, queue = _Store(log), _Queue(log)
    store.change_raw = True
    with pytest.raises(Retry):
        await index_document(
            {"store": store, "redis": queue, "reader": _Reader()}, _asked().model_dump(mode="json")
        )
    assert "hand back ready" not in log


@pytest.mark.asyncio
async def test_a_raw_read_still_running_is_left_to_its_last_batch(no_models) -> None:
    """Dựng trên trang dở dang là `READY` kèm một cây thiếu trang; lô OCR cuối sẽ giao lại job."""
    log: list[str] = []
    store, queue = _Store(log), _Queue(log)
    store.raw_doc = store.raw_doc.model_copy(update={"finished_at": None})
    out = await index_document(
        {"store": store, "redis": queue, "reader": _Reader()}, _asked().model_dump(mode="json")
    )
    assert out["dropped"] == "raw changed"
    assert log == []


@pytest.mark.asyncio
async def test_an_unexpected_failure_still_tells_the_teacher(no_models, monkeypatch) -> None:
    """arq không chạy lại một lỗi lập trình; một job chết im là chip đứng *đang xử lý* 300 s."""
    import document.index_handlers as handlers

    def broken(_deps):
        raise ValueError("a bug")

    monkeypatch.setattr(handlers, "build", broken)
    log: list[str] = []
    store, queue = _Store(log), _Queue(log)
    out = await index_document(
        {"store": store, "redis": queue, "reader": _Reader()}, _asked().model_dump(mode="json")
    )
    assert out["state"] == DocumentState.FAILED.value
    [(_, done)] = [job for job in queue.jobs if job[0] == DOCUMENT_PROBED_TASK]
    assert done["state"] == DocumentState.FAILED and done["fault"]


@pytest.mark.asyncio
async def test_a_job_out_of_time_tells_the_teacher_before_arq_kills_it(
    no_models, monkeypatch
) -> None:
    import asyncio

    import document.index_handlers as handlers

    class _Slow:
        async def ainvoke(self, _state):
            await asyncio.sleep(5)

    monkeypatch.setattr(handlers, "build", lambda _deps: _Slow())
    monkeypatch.setattr(handlers, "INDEX_BUDGET_SECONDS", 0.05)
    log: list[str] = []
    out = await index_document(
        {"store": _Store(log), "redis": _Queue(log), "reader": _Reader()},
        _asked().model_dump(mode="json"),
    )
    assert out["state"] == DocumentState.FAILED.value
    assert log == ["hand back failed"]


@pytest.mark.asyncio
async def test_a_retry_after_the_index_was_written_does_not_build_it_again(no_models) -> None:
    """Gửi `READY` hỏng rồi chạy lại: dựng lại là trả tiền Jev và OpenAI lần nữa cho cùng cây."""
    log: list[str] = []
    store, queue = _Store(log), _Queue(log)
    store.header = type("Header", (), {"raw_started_at": _AT})()
    await index_document(
        {"store": store, "redis": queue, "reader": _Reader()}, _asked().model_dump(mode="json")
    )
    assert log == ["hand back ready"]


@pytest.mark.asyncio
@pytest.mark.parametrize("where", ["mongo", "redis"])
async def test_a_store_or_queue_blip_asks_arq_to_run_again(no_models, where: str) -> None:
    log: list[str] = []
    store, queue = _Store(log), _Queue(log, down=where == "redis")
    store.down = where == "mongo"
    with pytest.raises(Retry):
        await index_document(
            {"store": store, "redis": queue, "reader": _Reader()}, _asked().model_dump(mode="json")
        )


@pytest.mark.asyncio
async def test_a_gate_that_luna_clearly_refuses_is_dropped() -> None:
    """Luna nói rõ *không phải trang mở đầu* thì cổng bỏ -- khác với luna hỏng, khi cổng thắng."""

    async def no(png: bytes) -> BannerReading:
        return BannerReading(False, None, None, None, None, None, 30)

    store = _Store([])
    await build(_deps(store, [], read_banner=no)).ainvoke({"asked": _asked()})
    assert [node.level for node in store.written[1]] == [1, 2]
    assert store.written[1][0].title == "CÁCH GHI SỐ TỰ NHIÊN"


@pytest.mark.asyncio
async def test_a_node_without_text_is_not_summarised() -> None:
    """Nội dung rỗng mời model bịa; không tóm tắt còn hơn tóm tắt sai."""
    asked: list[str] = []

    async def record(title: str, body: str) -> Summary:
        asked.append(title)
        return Summary("x", 1)

    pages = [_page(1, ("doc_title", (366.0, 127.0, 994.0, 186.0), "CÁCH GHI SỐ TỰ NHIÊN"))]
    store = _Store([], pages)
    await build(_deps(store, [], summarise=record, jev=None)).ainvoke({"asked": _asked()})
    assert asked == []


@pytest.mark.asyncio
async def test_mongo_still_down_on_the_last_try_tells_the_teacher(no_models) -> None:
    """Lần thử cuối của job dựng cây mà Mongo vẫn chết: gửi `FAILED`, không chết im."""
    log: list[str] = []
    store, queue = _Store(log), _Queue(log)
    store.down = True

    await index_document(
        {"store": store, "redis": queue, "reader": _Reader(), "job_try": MAX_TRIES},
        _asked().model_dump(mode="json"),
    )

    assert log == ["hand back failed"]
    # Câu của lần thử cuối, không phải câu của `_give_up` (lỗi lập trình) -- hai đường cùng một log.
    [(_, sent)] = queue.jobs
    assert sent["fault"].startswith("Kho lưu trữ")
