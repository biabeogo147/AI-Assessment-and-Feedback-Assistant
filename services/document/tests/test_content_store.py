"""Bản thô đi vào và ra khỏi Mongo mà không đổi hình dạng.

Không test nào ở đây cần Mongo chạy. Nhưng chiều đi-về phải đi qua **BSON thật**
(`bson.encode` / `bson.decode` của chính `pymongo` đã cài), không chỉ qua `as_document` rồi
`from_document`: bản đầu của file này làm vậy, và review Task 1 (11/10/2026) chứng minh nó xanh cả
khi một mốc thời gian đi vào Mongo rồi đi ra **khác** đi -- BSON chỉ giữ tới mili giây.
"""

from datetime import UTC, datetime, timedelta, timezone

import bson
import pytest
from bson.codec_options import CodecOptions
from pymongo.errors import AutoReconnect

from contracts import (
    BlockLabel,
    BlockRef,
    DecidedBy,
    IndexChunk,
    IndexHeader,
    IndexMethod,
    IndexNode,
    RawBlock,
    RawDocument,
    RawPage,
    RawSource,
    TitleSource,
    chunk_key,
    label_key,
    node_key,
    page_key,
)
from document.content_store import (
    ContentStore,
    ContentStoreUnavailable,
    RawChanged,
    as_document,
    check_index,
    finished,
    from_document,
    index_document,
)

# Có micro giây lẻ, có cả múi giờ +07:00: đúng hai thứ BSON xử khác Python.
_AT = datetime(2026, 10, 11, 16, 30, 3, 456789, tzinfo=timezone(timedelta(hours=7)))


def _through_mongo(body: dict) -> dict:
    """Đi một vòng qua BSON như một lần ghi rồi đọc thật, với `tz_aware=True` như `ContentStore`."""
    return bson.decode(bson.encode(body), codec_options=CodecOptions(tz_aware=True))


def _page(page: int = 3, at: datetime = _AT) -> RawPage:
    return RawPage(
        document_id="doc-1",
        page=page,
        source=RawSource.OCR,
        width=1140,
        height=1600,
        blocks=(
            RawBlock(kind="paragraph_title", box=(10, 20, 300, 60), text="KHÁI NIỆM"),
            RawBlock(kind="formula", box=(10, 80, 300, 120), text="a : b = c"),
        ),
        text="KHÁI NIỆM a : b = c",
        seconds={"layout": 1.8, "recognize": 1.7},
        read_at=at,
    )


def test_a_page_is_keyed_so_writing_it_again_overwrites() -> None:
    """arq chạy lại một lô thì trang ấy được ghi lần hai -- cùng `_id` nên ghi đè, không nhân đôi.

    Khoá dựng bằng `contracts.page_key`, không bằng một f-string riêng: bên đọc ở plan 3c phải dựng
    đúng khoá ấy để lấy một trang.
    """
    assert as_document(_page(3))["_id"] == page_key("doc-1", 3) == "doc-1:3"
    assert as_document(_page(3))["_id"] != as_document(_page(4))["_id"]


def test_a_page_comes_back_out_of_bson_exactly_as_it_was_stored() -> None:
    """Mongo là nơi lưu, không phải nơi định nghĩa: đọc ra phải dựng lại đúng thứ đã ghi.

    So **thứ ta gửi đi** với **thứ ta đọc về**, không so với một giá trị cắt sẵn: bản đầu của test
    này so với giá trị cắt sẵn, và bỏ hẳn bước cắt trong `as_document` vẫn xanh -- BSON tự cắt, nên
    bước của ta vô hình. Tuple (`box`, `blocks`) ra thành list rồi pydantic dựng lại thành tuple;
    múi giờ +07:00 ra thành UTC nhưng vẫn là cùng một khoảnh khắc.
    """
    sent = as_document(_page())
    assert from_document(RawPage, _through_mongo(sent)) == from_document(RawPage, sent)
    assert sent["read_at"].microsecond == 456000


def test_a_time_without_a_timezone_is_refused() -> None:
    """Mongo coi giờ không múi là UTC: `datetime.now()` giờ Việt Nam sẽ lệch bảy tiếng, im lặng."""
    with pytest.raises(ValueError, match="read_at"):
        as_document(_page(at=datetime(2026, 10, 11, 16, 30)))


def test_the_source_is_stored_as_a_bare_string() -> None:
    """Bên đọc của plan 3c có thể không dùng Python, nên giá trị phải là chuỗi trần."""
    body = as_document(_page())
    assert body["source"] == "ocr"
    assert type(body["source"]) is str


def test_a_document_header_is_keyed_by_the_document_id() -> None:
    """Cùng id với hàng `documents` trong kho của BE: hai kho nói về một tài liệu bằng một khoá."""
    header = RawDocument(
        document_id="doc-1", source=RawSource.TEXT_LAYER, page_count=29, started_at=_AT
    )
    body = as_document(header)
    assert body["_id"] == "doc-1"
    assert body["finished_at"] is None
    back = from_document(RawDocument, _through_mongo(body))
    assert back == header.model_copy(update={"started_at": _AT.replace(microsecond=456000)})
    assert back.started_at.tzinfo is not None
    assert back.started_at.astimezone(UTC) == _AT.replace(microsecond=456000).astimezone(UTC)


def test_finishing_follows_the_same_time_rule_as_writing() -> None:
    """`finish` ghi một mốc thời gian không qua `as_document`, nên nó phải tự theo cùng luật: cắt
    tới mili giây, từ chối giờ không múi. Thử tay ngày 11/10/2026 bắt được nó lọt luật này.
    """
    update = finished(_AT)
    assert update["$set"]["finished_at"].microsecond == 456000
    with pytest.raises(ValueError, match="finished_at"):
        finished(datetime(2026, 10, 11, 16, 30))


@pytest.mark.asyncio
async def test_a_mongo_error_becomes_the_typed_error() -> None:
    """Lỗi của `pymongo` thành `ContentStoreUnavailable`, để `handlers` xin arq chạy lại mà không
    phải import `pymongo` -- và không phải `except Exception`, thứ nuốt cả lỗi lập trình.
    """

    class _Down:
        async def replace_one(self, *_: object, **__: object) -> None:
            raise AutoReconnect("connection reset")

    store = ContentStore("mongodb://127.0.0.1:1", "unused")
    store._db = {"pages": _Down()}
    with pytest.raises(ContentStoreUnavailable, match="doc-1"):
        await store.put_page(_page())
    await store.close()


# --- Cây mục lục (plan 3c) ---


def _header(at: datetime = _AT) -> IndexHeader:
    return IndexHeader(
        document_id="doc-1",
        raw_started_at=at,
        raw_pipeline="text2",
        method=IndexMethod.JEV,
        node_count=1,
        chunk_count=1,
        built_at=at,
    )


def _tree_node() -> IndexNode:
    return IndexNode(
        document_id="doc-1",
        ordinal=0,
        level=1,
        numbering="Chương I",
        title="TẬP HỢP CÁC SỐ TỰ NHIÊN",
        title_source=TitleSource.BANNER,
        anchor=BlockRef(page=6, block=0),
        page_start=6,
        page_end=29,
    )


def _tree_chunk() -> IndexChunk:
    return IndexChunk(
        document_id="doc-1",
        ordinal=0,
        node_ordinal=0,
        blocks=(BlockRef(page=7, block=1), BlockRef(page=7, block=2)),
        text="Tập hợp\nTrên Hình 1.1 ...",
        page_start=7,
        page_end=7,
        char_count=24,
    )


def test_every_index_shape_is_keyed_by_its_contract_function() -> None:
    """Bên đọc dựng `_id` bằng `node_key` / `chunk_key` / `label_key`; bên ghi phải dùng đúng
    chúng."""
    label = BlockLabel(
        document_id="doc-1",
        ref=BlockRef(page=7, block=1),
        ocr_kind="paragraph_title",
        text="Tập hợp",
        role="book_section",
        level=2,
        decided_by=DecidedBy.JEV,
    )
    assert index_document(_header())["_id"] == "doc-1"
    assert index_document(_tree_node())["_id"] == node_key("doc-1", 0)
    assert index_document(_tree_chunk())["_id"] == chunk_key("doc-1", 0)
    assert index_document(label)["_id"] == label_key("doc-1", BlockRef(page=7, block=1))


def test_an_index_comes_back_out_of_bson_exactly_as_it_was_stored() -> None:
    """Enum lồng nhau thành chuỗi trần, thời gian cắt tới mili giây, khối lồng nhau thành mảng: đi
    một vòng BSON rồi dựng lại vẫn bằng chính nó -- cùng luật `as_document` đã đo cho bản thô."""
    header = _header()
    stored = _through_mongo(index_document(header))
    assert stored["method"] == "jev"
    assert from_document(IndexHeader, stored) == header.model_copy(
        update={"raw_started_at": stored["raw_started_at"], "built_at": stored["built_at"]}
    )
    assert stored["built_at"].microsecond == 456000
    chunk = _tree_chunk()
    assert from_document(IndexChunk, _through_mongo(index_document(chunk))) == chunk
    node = _tree_node()
    assert _through_mongo(index_document(node))["title_source"] == "banner"
    assert from_document(IndexNode, _through_mongo(index_document(node))) == node


def test_an_index_time_without_a_timezone_is_refused() -> None:
    with pytest.raises(ValueError, match="built_at"):
        index_document(_header().model_copy(update={"built_at": datetime(2026, 10, 11, 16, 30)}))


class _Logged:
    """Một collection giả, ghi mọi lệnh vào một nhật ký chung để test đọc được **thứ tự**.

    `rows` là những document mà `find_one` / `find` trả về.
    """

    def __init__(self, name: str, log: list[str], rows: list[dict] | None = None):
        self._name = name
        self._log = log
        self._rows = rows or []

    async def delete_one(self, *_: object, **__: object) -> None:
        self._log.append(f"delete {self._name}")

    async def delete_many(self, *_: object, **__: object) -> None:
        self._log.append(f"delete {self._name}")

    async def insert_many(self, rows: list, *_: object, **__: object) -> None:
        self._log.append(f"insert {self._name} {len(rows)}")

    async def replace_one(self, *_: object, **__: object) -> None:
        self._log.append(f"replace {self._name}")

    async def find_one(self, *_: object, **__: object) -> dict | None:
        self._log.append(f"find {self._name}")
        return self._rows[0] if self._rows else None

    def find(self, *_: object, **__: object) -> "_Logged":
        self._log.append(f"find {self._name}")
        return self

    def sort(self, *_: object, **__: object) -> "_Logged":
        return self

    async def to_list(self, *_: object, **__: object) -> list[dict]:
        return self._rows


def _logged_store(log: list[str], raw_started_at: datetime | None = _AT) -> ContentStore:
    """Một kho giả có đầu mục bản thô mang `raw_started_at` (cắt mili giây như Mongo giữ)."""
    store = ContentStore("mongodb://127.0.0.1:1", "unused")
    names = ("pages", "indexes", "nodes", "chunks", "block_labels")
    store._db = {name: _Logged(name, log) for name in names}
    raw = []
    if raw_started_at is not None:
        raw = [
            _through_mongo(
                as_document(
                    RawDocument(
                        document_id="doc-1", source=RawSource.OCR, started_at=raw_started_at
                    )
                )
            )
        ]
    store._db["documents"] = _Logged("documents", log, raw)
    return store


@pytest.mark.asyncio
async def test_the_index_header_is_dropped_first_and_written_last() -> None:
    """Có đầu mục là cây đã ghi trọn. Ghi nó trước nút -- hay xoá nó sau nút -- là để một lần đứt
    giữa chừng lại một cây *trông như* trọn vẹn mà thiếu nút."""
    log: list[str] = []
    store = _logged_store(log)
    await store.put_index(_header(), [_tree_node()], [_tree_chunk()], [])
    assert log == [
        "delete indexes",
        "delete nodes",
        "delete chunks",
        "delete block_labels",
        "insert nodes 1",
        "insert chunks 1",
        "find documents",
        "replace indexes",
    ]
    await store.close()


@pytest.mark.asyncio
async def test_an_index_built_on_a_raw_read_that_was_replaced_is_refused() -> None:
    """Đọc lại tài liệu trong lúc cây đang dựng: cây cũ trỏ `(page, block)` vào chữ mới. Nó bị
    xoá, không có đầu mục nào được ghi (review Task 2)."""
    log: list[str] = []
    store = _logged_store(log, raw_started_at=_AT + timedelta(minutes=3))
    with pytest.raises(RawChanged):
        await store.put_index(_header(), [_tree_node()], [_tree_chunk()], [])
    assert "replace indexes" not in log
    assert log[-4:] == ["delete indexes", "delete nodes", "delete chunks", "delete block_labels"]
    await store.close()


@pytest.mark.asyncio
async def test_an_index_whose_raw_content_is_gone_is_refused() -> None:
    store = _logged_store([], raw_started_at=None)
    with pytest.raises(RawChanged):
        await store.put_index(_header(), [_tree_node()], [_tree_chunk()], [])
    await store.close()


@pytest.mark.asyncio
async def test_reading_a_document_again_kills_its_index() -> None:
    """Cây trỏ vào khối của bản thô bằng `(page, block)`; đọc lại là đổi chữ dưới những con trỏ ấy
    (plan 3c, D7)."""
    log: list[str] = []
    store = _logged_store(log)
    await store.begin(RawDocument(document_id="doc-1", source=RawSource.OCR, started_at=_AT))
    assert log[:4] == ["delete indexes", "delete nodes", "delete chunks", "delete block_labels"]
    assert log[4:] == ["delete pages", "replace documents"]
    await store.close()


@pytest.mark.asyncio
async def test_an_index_cannot_mix_two_documents() -> None:
    store = _logged_store([])
    stranger = _tree_node().model_copy(update={"document_id": "doc-2"})
    with pytest.raises(ValueError, match="doc-2"):
        await store.put_index(_header(), [stranger], [], [])
    await store.close()


def test_a_tree_that_contradicts_itself_is_a_programming_error() -> None:
    """Khoá trùng mà để tới `insert_many` thì thành `PyMongoError`, rồi thành *"Mongo không với
    tới được"*, rồi arq chạy lại -- trả tiền Jev mỗi lượt cho một lỗi không bao giờ tự hết."""
    node = _tree_node()
    with pytest.raises(ValueError, match="share a key"):
        check_index(_header().model_copy(update={"node_count": 2}), [node, node], [], [])
    with pytest.raises(ValueError, match="count"):
        check_index(_header(), [], [_tree_chunk()], [])
    line = BlockLabel(
        document_id="doc-1",
        ref=BlockRef(page=1, block=0, line=3),
        ocr_kind="text",
        text="# Mở đầu",
        role="book_section",
        decided_by=DecidedBy.JEV,
    )
    other_line = line.model_copy(update={"ref": BlockRef(page=1, block=0, line=4)})
    check_index(_header(), [node], [_tree_chunk()], [line, other_line])


def test_a_label_keeps_its_probabilities_through_bson() -> None:
    label = BlockLabel(
        document_id="doc-1",
        ref=BlockRef(page=7, block=1),
        ocr_kind="paragraph_title",
        text="Tập hợp",
        role="book_section",
        role_probabilities={"not_heading": 0.1, "book_section": 0.9},
        level=2,
        level_probabilities={"level_2": 0.8, "deeper": 0.2},
        confidence=0.7,
        decided_by=DecidedBy.JEV,
    )
    assert from_document(BlockLabel, _through_mongo(index_document(label))) == label


@pytest.mark.asyncio
async def test_pages_come_back_as_models() -> None:
    """`pages` đọc bằng chính model mà đường đọc đã ghi -- hai bên không nói chuyện bằng dict."""
    store = _logged_store([])
    store._db["pages"] = _Logged("pages", [], [_through_mongo(as_document(_page(3)))])
    [page] = await store.pages("doc-1")
    assert page.blocks[0].text == "KHÁI NIỆM"
    header = await store.raw("doc-1")
    assert header is not None and header.source is RawSource.OCR
    await store.close()
