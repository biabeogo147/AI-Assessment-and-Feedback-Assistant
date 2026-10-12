"""BE đọc mục lục và đoạn từ kho nội dung (plan 4b) -- và chỉ đọc.

Không Mongo thật nào: các collection là đồ giả nhỏ, đủ cho hai thứ cần kiểm -- reader hỏi đúng
câu (cây chỉ khi có đầu mục, đoạn theo `node_ordinal`), và lỗi của kho thành `ContentUnavailable`
chứ không thành một 500 của khung chat. Chữ *chỉ đọc* thì `check_the_content_reader_only_reads`
trong `tools/check_contract.py` canh.
"""

from datetime import UTC, datetime

import pytest
from pymongo.errors import AutoReconnect

from be.content_reader import ContentUnavailable, MongoContentReader
from contracts import BlockRef, IndexMethod, TitleSource

_AT = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


class Cursor:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def sort(self, key: str, direction: int) -> "Cursor":
        self.rows = sorted(self.rows, key=lambda row: row[key])
        return self

    async def to_list(self) -> list[dict]:
        return self.rows


class Collection:
    def __init__(self, rows: list[dict], broken: bool = False) -> None:
        self.rows = rows
        self.broken = broken
        self.asked: list[dict] = []

    async def find_one(self, query: dict) -> dict | None:
        if self.broken:
            raise AutoReconnect("mongo went away")
        return next((row for row in self.rows if row["_id"] == query["_id"]), None)

    def find(self, query: dict) -> Cursor:
        if self.broken:
            raise AutoReconnect("mongo went away")
        self.asked.append(query)
        wanted = query.get("node_ordinal", {}).get("$in")
        return Cursor(
            [
                row
                for row in self.rows
                if row["document_id"] == query["document_id"]
                and (wanted is None or row["node_ordinal"] in wanted)
            ]
        )


def _header(document_id: str = "d1") -> dict:
    return {
        "_id": document_id,
        "document_id": document_id,
        "raw_started_at": _AT,
        "method": IndexMethod.RULES.value,
        "node_count": 2,
        "chunk_count": 3,
        "built_at": _AT,
    }


def _node(ordinal: int, title: str, parent: int | None = None, level: int = 1) -> dict:
    return {
        "_id": f"d1:{ordinal}",
        "document_id": "d1",
        "ordinal": ordinal,
        "parent_ordinal": parent,
        "level": level,
        "title": title,
        "title_source": TitleSource.TEXT.value,
        "anchor": BlockRef(page=1, block=ordinal).model_dump(),
        "page_start": 1,
        "page_end": 2,
    }


def _chunk(ordinal: int, node: int | None) -> dict:
    return {
        "_id": f"d1:c{ordinal}",
        "document_id": "d1",
        "ordinal": ordinal,
        "node_ordinal": node,
        "blocks": [BlockRef(page=1, block=ordinal).model_dump()],
        "text": f"đoạn {ordinal}",
        "page_start": 1,
        "page_end": 1,
        "char_count": 6,
    }


def _reader(indexes: list[dict], nodes: list[dict], chunks: list[dict], broken=False):
    reader = MongoContentReader("mongodb://127.0.0.1:1", "test")
    reader._db = {
        "indexes": Collection(indexes, broken),
        "nodes": Collection(nodes, broken),
        "chunks": Collection(chunks, broken),
    }
    return reader


@pytest.mark.asyncio
async def test_a_tree_without_its_header_is_not_a_tree() -> None:
    """Đầu mục ghi cuối cùng: thiếu nó là cây đang ghi dở, dù đã có nút."""
    reader = _reader([], [_node(0, "Chương I")], [])

    assert await reader.tree("d1") is None


@pytest.mark.asyncio
async def test_a_tree_reads_in_preorder_and_drops_the_mongo_id() -> None:
    reader = _reader([_header()], [_node(1, "Bài 1", 0, 2), _node(0, "Chương I")], [])

    header, nodes = await reader.tree("d1")

    assert header.built_at == _AT
    assert [node.ordinal for node in nodes] == [0, 1]
    assert nodes[1].parent_ordinal == 0


@pytest.mark.asyncio
async def test_chunks_come_only_from_the_nodes_asked_for() -> None:
    reader = _reader([], [], [_chunk(2, 1), _chunk(0, 0), _chunk(1, 1), _chunk(3, None)])

    found = await reader.chunks("d1", [1])

    assert [one.ordinal for one in found] == [1, 2]


@pytest.mark.asyncio
@pytest.mark.parametrize("read", ["tree", "chunks"])
async def test_a_tree_older_than_the_contract_is_unreadable_not_a_500(read: str) -> None:
    """Contract thêm một trường bắt buộc, cây trong Mongo chưa dựng lại (review B2)."""
    stale_node = {key: value for key, value in _node(0, "Chương I").items() if key != "title"}
    stale_chunk = {key: value for key, value in _chunk(0, 0).items() if key != "text"}
    reader = _reader([_header()], [stale_node], [stale_chunk])

    with pytest.raises(ContentUnavailable):
        await (reader.tree("d1") if read == "tree" else reader.chunks("d1", [0]))


@pytest.mark.asyncio
@pytest.mark.parametrize("read", ["tree", "chunks"])
async def test_a_store_that_went_away_is_named_not_a_crash(read: str) -> None:
    reader = _reader([_header()], [], [], broken=True)

    with pytest.raises(ContentUnavailable):
        await (reader.tree("d1") if read == "tree" else reader.chunks("d1", [0]))
