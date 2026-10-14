"""Kho nội dung (MongoDB): nơi bản thô của mọi tài liệu nằm. Module duy nhất import `pymongo`.

**Vì sao service này được giữ khoá Mongo** dù
`check_agent_and_document_hold_no_database_credentials` canh nó: cùng lập luận đã cho khoá MinIO
đứng ngoài luật ấy. Mongo giữ **nội dung** đọc ra từ tệp, không giữ **sự thật** về tệp. Một tài
liệu đã xử lý xong hay chưa thì chỉ `documents.state` trong kho của BE trả lời, và chỉ
`services/ingest` ghi cột ấy. Người dùng chốt ngày 11/10/2026 (plan 3b, D1).

**Thứ tự ghi** theo Decision Record *"chunk trước, `state` sau"*: mọi trang vào đây **trước** khi
`DocumentProbed(READY)` rời service. Hỏng giữa chừng thì để lại trang mồ côi -- rác, không ai
thấy -- chứ không bao giờ một tài liệu *sẵn sàng* mà không có chữ.

**Một module, một cửa.** Cùng lệ với `storage.py` (MinIO) và `pdf.py` (PyMuPDF): gom mọi lời gọi
về một chỗ biến luật *"nhớ dùng đúng client"* thành luật *"đừng import `pymongo`"*, và luật thứ
hai thì grep được -- `check_only_one_module_per_service_talks_to_a_sync_sdk` canh nó.
`AsyncMongoClient` là async thuần, nên khác MinIO ở chỗ không phải bọc thread.

Hình dạng của thứ được ghi **không** khai ở đây mà ở `contracts.content`: Mongo là nơi lưu, không
phải nơi định nghĩa. Bên đọc ở plan 3c đọc bằng đúng các model ấy.

**Từ plan 3c, kho giữ thêm cây mục lục** -- bốn collection `indexes`, `nodes`, `chunks`,
`block_labels`, hình dạng ở `contracts.index`. Cùng một module, vì luật D2 của 3b là *một SDK, một
module*, và vì chỉ ở đây mới trả lời được câu *"đọc lại tài liệu thì cây cũ có chết theo không"*
(`begin`, D7 của 3c).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel
from pymongo import ASCENDING, AsyncMongoClient, ReplaceOne
from pymongo.errors import PyMongoError

from contracts import (
    BlockLabel,
    IndexChunk,
    IndexHeader,
    IndexNode,
    RawDocument,
    RawPage,
    chunk_key,
    label_key,
    node_key,
    page_key,
)

logger = logging.getLogger(__name__)

_DOCUMENTS = "documents"
_PAGES = "pages"
# Số trang mỗi lượt `bulk_write` của `put_pages`. Không phải để né trần của Mongo -- `pymongo` tự
# tách lô theo cỡ message, và trần thật cho mỗi trang là 16 MB một document như với `put_page`. Chia
# khúc để danh sách lệnh dựng sẵn không phình theo cả cuốn, và để một lần đứt chỉ mất một khúc.
_PAGE_BATCH = 500
# Cây mục lục (plan 3c). Đầu mục ghi **cuối cùng** và xoá **đầu tiên**, nên có nó là cây đã ghi
# xong: một lần ghi hay xoá đứt giữa chừng không để lại một cây *trông như* trọn vẹn mà thiếu nút.
_INDEXES = "indexes"
_NODES = "nodes"
_CHUNKS = "chunks"
_LABELS = "block_labels"


class ContentStoreUnavailable(RuntimeError):
    """Kho nội dung không đọc hay ghi được lúc này.

    Tách khỏi exception của `pymongo` để người gọi không phải import `pymongo` chỉ để bắt lỗi --
    đúng thứ seam check cấm. Cùng hình dạng với `StorageUnavailable` của `storage.py`. `handlers`
    bắt nó để xin arq **chạy lại** job: Mongo chập chờn một nhịp không phải lỗi của tệp.
    """


class RawChanged(RuntimeError):
    """Bản thô mà cây được dựng trên đó đã bị **đọc lại** trong lúc dựng.

    Cây trỏ vào khối bằng `(page, block)`; sau một lần đọc lại, những con trỏ ấy trỏ vào chữ khác.
    Không chạy lại: lần đọc mới tự đẩy một job dựng cây của nó (review Task 2, plan 3c).
    """


@asynccontextmanager
async def _translated(action: str, document_id: str) -> AsyncIterator[None]:
    """Dịch mọi lỗi của `pymongo` trong khối thành `ContentStoreUnavailable`.

    Args:
        action: Việc đang làm, cho câu báo lỗi.
        document_id: Tài liệu đang ghi.

    Raises:
        ContentStoreUnavailable: Khi `pymongo` ném.
    """
    try:
        yield
    except PyMongoError as exc:
        logger.warning("content store could not %s document=%s: %s", action, document_id, exc)
        raise ContentStoreUnavailable(f"Could not {action} {document_id}: {exc}") from exc


def as_document(model: RawDocument | RawPage) -> dict[str, Any]:
    """Một model của `contracts.content` thành document Mongo, có `_id`.

    Hàm thuần, tách khỏi lớp để test được mà không cần Mongo chạy.

    Args:
        model: Đầu mục tài liệu hoặc một trang.

    Returns:
        Dict ghi thẳng được vào Mongo. `_id` của trang là `page_key(...)`, của tài liệu là id của
        nó -- nên ghi lại cùng một thứ là ghi đè, không nhân đôi.

    Raises:
        ValueError: Khi một mốc thời gian không mang múi giờ. Mongo coi nó là UTC, nên một
            `datetime.now()` giờ Việt Nam sẽ lặng lẽ lệch bảy tiếng.
    """
    # `StrEnum` là `str`, nhưng ghi giá trị trần cho chắc: bên đọc ở plan 3c có thể không dùng
    # Python. `_bare` làm việc ấy và luật thời gian cho mọi tầng -- một luật cho cả bản thô lẫn cây.
    body = _bare(model.model_dump(mode="python"))
    if isinstance(model, RawPage):
        body["_id"] = page_key(model.document_id, model.page)
    else:
        body["_id"] = model.document_id
    return body


def page_writes(pages: list[RawPage]) -> list[ReplaceOne]:
    """Các lệnh ghi đè cho một khúc trang, để `bulk_write`. Hàm thuần như `as_document`.

    Args:
        pages: Các trang.

    Returns:
        Mỗi trang một `ReplaceOne` theo `_id` của nó, `upsert` -- cùng luật với `put_page`.
    """
    writes = []
    for page in pages:
        body = as_document(page)
        writes.append(ReplaceOne({"_id": body["_id"]}, body, upsert=True))
    return writes


def _to_bson_time(field: str, value: datetime) -> datetime:
    """Đưa một mốc thời gian về đúng thứ BSON giữ được.

    BSON lưu thời gian tới **mili giây**. Không cắt trước thì `datetime.now()` đi vào Mongo rồi
    đi ra không còn bằng chính nó (review Task 1, 11/10/2026, đo bằng `bson.encode`/`decode`).
    Cắt ở đây thì thứ được ghi và thứ đọc lại là một.

    Args:
        field: Tên trường, cho câu báo lỗi.
        value: Mốc thời gian.

    Returns:
        Cùng mốc, bỏ phần dưới mili giây.

    Raises:
        ValueError: Khi `value` không mang múi giờ.
    """
    if value.tzinfo is None:
        raise ValueError(f"{field} has no timezone; Mongo would store it as if it were UTC")
    return value.replace(microsecond=value.microsecond // 1000 * 1000)


type IndexModel = IndexHeader | IndexNode | IndexChunk | BlockLabel


def index_document(model: IndexModel) -> dict[str, Any]:
    """Một model của `contracts.index` thành document Mongo, có `_id`. Hàm thuần như `as_document`.

    Args:
        model: Đầu mục cây, một nút, một chunk hoặc nhãn một ứng viên.

    Returns:
        Dict ghi thẳng được vào Mongo: enum thành chuỗi trần, thời gian cắt tới mili giây, `_id`
        dựng bằng hàm khoá của `contracts.index`.

    Raises:
        ValueError: Khi một mốc thời gian không mang múi giờ.
    """
    body = _bare(model.model_dump(mode="python"))
    if isinstance(model, IndexHeader):
        body["_id"] = model.document_id
    elif isinstance(model, IndexNode):
        body["_id"] = node_key(model.document_id, model.ordinal)
    elif isinstance(model, IndexChunk):
        body["_id"] = chunk_key(model.document_id, model.ordinal)
    else:
        body["_id"] = label_key(model.document_id, model.ref)
    return body


def _bare(value: Any, field: str = "") -> Any:
    """Đi khắp một dump của pydantic: enum thành giá trị trần, thời gian theo `_to_bson_time`.

    Args:
        value: Một giá trị bất kỳ trong dump.
        field: Tên trường gần nhất, cho câu báo lỗi thời gian.

    Returns:
        Cùng giá trị, ghi được vào BSON mà đọc ra không lệch.
    """
    if isinstance(value, dict):
        return {key: _bare(inner, key) for key, inner in value.items()}
    if isinstance(value, list | tuple):
        return [_bare(inner, field) for inner in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return _to_bson_time(field, value)
    return value


def check_index(
    header: IndexHeader,
    nodes: list[IndexNode],
    chunks: list[IndexChunk],
    labels: list[BlockLabel],
) -> None:
    """Một cây có tự nhất quán không, **trước** khi chạm Mongo.

    Lý do nó tồn tại (review Task 2): hai nút cùng `ordinal` làm `insert_many` ném lỗi khoá trùng,
    mà lỗi ấy là `PyMongoError` -- `_translated` sẽ dịch nó thành *"Mongo không với tới được"*, và
    arq chạy lại job tới hết lượt, mỗi lượt lại trả tiền Jev và `gpt-4o-mini`. Bắt nó ở đây thì nó
    là đúng thứ nó là: một lỗi lập trình.

    Args:
        header: Đầu mục cây.
        nodes: Các nút.
        chunks: Các chunk.
        labels: Các nhãn.

    Raises:
        ValueError: Khi một phần tử thuộc tài liệu khác, khoá trùng, hoặc số đếm của đầu mục lệch.
    """
    document_id = header.document_id
    for part in (*nodes, *chunks, *labels):
        if part.document_id != document_id:
            raise ValueError(f"{part.document_id} is not part of the index of {document_id}")
    for name, keys in (
        ("node", [node.ordinal for node in nodes]),
        ("chunk", [chunk.ordinal for chunk in chunks]),
        ("label", [label_key(document_id, label.ref) for label in labels]),
    ):
        if len(set(keys)) != len(keys):
            raise ValueError(f"two {name}s of {document_id} share a key")
    if header.node_count != len(nodes) or header.chunk_count != len(chunks):
        raise ValueError(f"the header of {document_id} does not count what is written")


def finished(at: datetime) -> dict[str, Any]:
    """Phép cập nhật đánh dấu đầu mục đã xong. Hàm thuần như `as_document`, cùng luật thời gian.

    Args:
        at: Lúc xong, có múi giờ.

    Returns:
        Một `$set` cho `update_one`.

    Raises:
        ValueError: Khi `at` không mang múi giờ.
    """
    return {"$set": {"finished_at": _to_bson_time("finished_at", at)}}


def from_document[M: BaseModel](kind: type[M], body: dict[str, Any]) -> M:
    """Chiều ngược lại của `as_document`: bỏ `_id`, dựng lại model có kiểu.

    Args:
        kind: `RawDocument` hoặc `RawPage`.
        body: Document đọc từ Mongo.

    Returns:
        Model đã kiểm hình dạng, đúng kiểu `kind`.
    """
    return kind.model_validate({key: value for key, value in body.items() if key != "_id"})


class ContentStore:
    """Một kết nối tới kho nội dung, mở một lần ở `on_startup` của worker.

    Attributes:
        _client: Client async của Mongo. Giữ pool kết nối suốt đời worker.
        _db: Database chứa bản thô (`documents`, `pages`) và cây (`indexes`, `nodes`, `chunks`,
            `block_labels`).
    """

    def __init__(self, url: str, database: str):
        """Tạo client. Chưa mở kết nối nào: `pymongo` nối lười ở lời gọi đầu.

        Args:
            url: Chuỗi kết nối Mongo.
            database: Tên database.
        """
        self._client: AsyncMongoClient = AsyncMongoClient(url, tz_aware=True)
        self._db = self._client[database]

    async def prepare(self) -> None:
        """Tạo index, và qua đó **chạm Mongo một lần** lúc khởi động.

        Một worker mà kho nội dung không với tới được phải chết lúc khởi động, không phải ở giữa job
        đầu tiên -- lúc ấy lỗi đi kèm một tài liệu của giáo viên.

        Side effects:
            Index duy nhất `pages(document_id, page)`, `nodes(document_id, ordinal)`,
            `chunks(document_id, ordinal)`, và index `block_labels(document_id)`. Tạo lại một index
            đã có là không làm gì.
        """
        await self._db[_PAGES].create_index(
            [("document_id", ASCENDING), ("page", ASCENDING)], unique=True
        )
        for name in (_NODES, _CHUNKS):
            await self._db[name].create_index(
                [("document_id", ASCENDING), ("ordinal", ASCENDING)], unique=True
            )
        await self._db[_LABELS].create_index([("document_id", ASCENDING)])

    async def begin(self, header: RawDocument) -> None:
        """Mở bản thô của một tài liệu, xoá bản thô cũ nếu có.

        Đọc lại một tài liệu là **ghi đè** bản thô của nó (plan 3b, D6): trang cũ của một lần đọc
        trước -- có thể bằng một đường đọc khác -- không được trộn với trang mới.

        Và **cây cũ chết theo** (plan 3c, D7): nó trỏ vào khối của bản thô cũ bằng `(page, block)`,
        nên giữ nó lại là giữ những con trỏ trỏ vào chữ khác.

        Args:
            header: Đầu mục, `finished_at` còn `None`.

        Raises:
            ContentStoreUnavailable: Khi Mongo không ghi được lúc này.

        Side effects:
            Xoá cây và mọi trang của tài liệu này, rồi ghi đè đầu mục.
        """
        async with _translated("begin", header.document_id):
            await self._drop_index(header.document_id)
            await self._db[_PAGES].delete_many({"document_id": header.document_id})
            await self._db[_DOCUMENTS].replace_one(
                {"_id": header.document_id}, as_document(header), upsert=True
            )

    async def put_page(self, page: RawPage) -> None:
        """Ghi một trang. Ghi lại cùng trang là ghi đè -- arq chạy lại một lô thì không nhân đôi.

        Args:
            page: Trang đã đọc.

        Raises:
            ContentStoreUnavailable: Khi Mongo không ghi được lúc này.
        """
        body = as_document(page)
        async with _translated("put a page of", page.document_id):
            await self._db[_PAGES].replace_one({"_id": body["_id"]}, body, upsert=True)

    async def put_pages(self, pages: list[RawPage]) -> None:
        """Ghi nhiều trang, mỗi khúc `_PAGE_BATCH` trang một lượt tới Mongo.

        Đường có text layer đọc cả cuốn trong một nhịp, nên ghi từng trang là một vòng tới Mongo
        cho mỗi trang: 2 000 trang với một Mongo ở xa (~20 ms một vòng) là ~40 s chỉ để ghi. Một
        `bulk_write` mỗi khúc giữ đúng luật của `put_page` -- ghi lại là ghi đè -- với vài vòng.

        Args:
            pages: Các trang, có thể rỗng.

        Raises:
            ContentStoreUnavailable: Khi Mongo không ghi được lúc này. Một khúc đã ghi thì ở lại;
                lần chạy lại ghi đè nó, không nhân đôi.
        """
        if not pages:
            return
        async with _translated("put the pages of", pages[0].document_id):
            for start in range(0, len(pages), _PAGE_BATCH):
                await self._db[_PAGES].bulk_write(
                    page_writes(pages[start : start + _PAGE_BATCH]), ordered=False
                )

    async def stored_pages(self, document_id: str, first: int, last: int) -> set[int]:
        """Số các trang trong `[first, last]` đã nằm trong kho.

        Một lô OCR chạy lại dùng nó để không đọc lại trang lần trước đã ghi. `begin` xoá mọi
        trang của lần đọc trước, nên trang nào còn đây là trang của lần đọc này -- **khi chỉ một
        chuỗi lô đang chạy**, cùng giới hạn `_queue_batch` của `ocr_handlers` đã ghi. Một lô của
        chuỗi cũ còn nằm trong queue lúc tài liệu được đọc lại thì chạy sau `begin` và ghi trang của
        nó vào kho mới; chuỗi mới bỏ qua chúng thay vì ghi đè. Cùng tệp, cùng đường đọc thì chữ như
        nhau; chỉ lệch khi `ocr_reader` hay `pipeline` đổi giữa hai lần đọc.

        Args:
            document_id: Id tài liệu.
            first: Trang đầu, đếm từ 1.
            last: Trang cuối, tính cả nó.

        Returns:
            Các số trang đã có.

        Raises:
            ContentStoreUnavailable: Khi Mongo không đọc được lúc này.
        """
        async with _translated("list the stored pages of", document_id):
            found = self._db[_PAGES].find(
                {"document_id": document_id, "page": {"$gte": first, "$lte": last}},
                {"page": 1, "_id": 0},
            )
            rows = await found.to_list()
        return {int(row["page"]) for row in rows}

    async def finish(self, document_id: str, at: datetime) -> None:
        """Đánh dấu đường đọc đã ghi xong trang cuối.

        Args:
            document_id: Id tài liệu.
            at: Lúc xong. Phải mang múi giờ, cùng luật với `as_document`.

        Raises:
            ContentStoreUnavailable: Khi Mongo không ghi được lúc này.
        """
        update = finished(at)
        async with _translated("finish", document_id):
            await self._db[_DOCUMENTS].update_one({"_id": document_id}, update)

    async def characters(self, document_id: str) -> int:
        """Tổng số ký tự của mọi trang đã ghi.

        Lô OCR cuối dùng nó để phân biệt *đọc xong và có chữ* với *đọc xong mà cả cuốn không ra chữ
        nào* -- cái sau mới là `NO_TEXT_LAYER`.

        Args:
            document_id: Id tài liệu.

        Returns:
            Tổng số ký tự, 0 khi chưa có trang nào.

        Raises:
            ContentStoreUnavailable: Khi Mongo không đọc được lúc này.
        """
        async with _translated("count the characters of", document_id):
            found = await self._db[_PAGES].aggregate(
                [
                    {"$match": {"document_id": document_id}},
                    {"$group": {"_id": None, "total": {"$sum": {"$strLenCP": "$text"}}}},
                ]
            )
            rows = await found.to_list()
        return int(rows[0]["total"]) if rows else 0

    async def raw(self, document_id: str) -> RawDocument | None:
        """Đầu mục bản thô của một tài liệu.

        Args:
            document_id: Id tài liệu.

        Returns:
            Đầu mục, `None` khi tài liệu chưa từng được đọc (hoặc bản thô đã bị xoá).

        Raises:
            ContentStoreUnavailable: Khi Mongo không đọc được lúc này.
        """
        async with _translated("read the header of", document_id):
            body = await self._db[_DOCUMENTS].find_one({"_id": document_id})
        return None if body is None else from_document(RawDocument, body)

    async def indexed(self, document_id: str) -> IndexHeader | None:
        """Đầu mục cây của một tài liệu, nếu cây đã ghi trọn.

        Args:
            document_id: Id tài liệu.

        Returns:
            Đầu mục, `None` khi chưa có cây (hoặc cây đã chết theo một lần đọc lại).

        Raises:
            ContentStoreUnavailable: Khi Mongo không đọc được lúc này.
        """
        async with _translated("read the index header of", document_id):
            body = await self._db[_INDEXES].find_one({"_id": document_id})
        return None if body is None else from_document(IndexHeader, body)

    async def pages(self, document_id: str) -> list[RawPage]:
        """Mọi trang của một tài liệu, theo thứ tự trang.

        Một cuốn 125 trang OCR là ~3 000 khối, vài MB -- đọc trọn một lần là đúng cỡ cho một job
        dựng cây, không cần phân trang.

        Args:
            document_id: Id tài liệu.

        Returns:
            Các trang, trang 1 trước. Rỗng khi chưa có trang nào.

        Raises:
            ContentStoreUnavailable: Khi Mongo không đọc được lúc này.
        """
        async with _translated("read the pages of", document_id):
            found = self._db[_PAGES].find({"document_id": document_id}).sort("page", ASCENDING)
            rows = await found.to_list()
        return [from_document(RawPage, row) for row in rows]

    async def put_index(
        self,
        header: IndexHeader,
        nodes: list[IndexNode],
        chunks: list[IndexChunk],
        labels: list[BlockLabel],
    ) -> None:
        """Ghi một cây, **thay trọn** cây cũ của tài liệu nếu có.

        Thứ tự là hợp đồng: xoá cây cũ, ghi nút, chunk, nhãn, rồi **đầu mục cuối cùng**. Hỏng giữa
        chừng thì không có đầu mục -- bên đọc thấy *chưa có cây*, không thấy một cây thiếu nút. Và
        chỉ sau khi hàm này trả về, `DocumentProbed(READY)` mới được rời service (*"chunk trước,
        `state` sau"*).

        Args:
            header: Đầu mục cây.
            nodes: Các nút, thứ tự preorder.
            chunks: Các chunk.
            labels: Quyết định về từng ứng viên.

        Raises:
            ContentStoreUnavailable: Khi Mongo không ghi được lúc này.
            RawChanged: Khi bản thô đã bị đọc lại sau lúc cây bắt đầu dựng. Những gì vừa ghi bị xoá,
                không có đầu mục nào được ghi.
            ValueError: Khi cây tự mâu thuẫn (xem `check_index`) -- lỗi lập trình, không phải lỗi
                của kho, nên **không** được thành `ContentStoreUnavailable` để arq chạy lại.
        """
        check_index(header, nodes, chunks, labels)
        document_id = header.document_id
        async with _translated("write the index of", document_id):
            await self._drop_index(document_id)
            for name, parts in ((_NODES, nodes), (_CHUNKS, chunks), (_LABELS, labels)):
                if parts:
                    await self._db[name].insert_many([index_document(part) for part in parts])
            # Ngay trước đầu mục: bản thô còn là bản cây được dựng trên đó không. Hỏi ở đây chứ
            # không ở đầu job, vì một lần đọc lại có thể bắt đầu bất cứ lúc nào trong lúc dựng.
            raw = await self._db[_DOCUMENTS].find_one({"_id": document_id}, {"started_at": 1})
            expected = _to_bson_time("raw_started_at", header.raw_started_at)
            if raw is None or raw.get("started_at") != expected:
                await self._drop_index(document_id)
                raise RawChanged(f"the raw content of {document_id} was read again")
            await self._db[_INDEXES].replace_one(
                {"_id": document_id}, index_document(header), upsert=True
            )

    async def _drop_index(self, document_id: str) -> None:
        """Xoá cây của một tài liệu, đầu mục trước. Người gọi đã mở `_translated`.

        Args:
            document_id: Id tài liệu.
        """
        await self._db[_INDEXES].delete_one({"_id": document_id})
        for name in (_NODES, _CHUNKS, _LABELS):
            await self._db[name].delete_many({"document_id": document_id})

    async def close(self) -> None:
        """Đóng pool kết nối. Gọi ở `on_shutdown` của worker."""
        await self._client.close()
