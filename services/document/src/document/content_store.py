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
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pymongo import ASCENDING, AsyncMongoClient
from pymongo.errors import PyMongoError

from contracts import RawDocument, RawPage, page_key

logger = logging.getLogger(__name__)

_DOCUMENTS = "documents"
_PAGES = "pages"


class ContentStoreUnavailable(RuntimeError):
    """Kho nội dung không đọc hay ghi được lúc này.

    Tách khỏi exception của `pymongo` để người gọi không phải import `pymongo` chỉ để bắt lỗi --
    đúng thứ seam check cấm. Cùng hình dạng với `StorageUnavailable` của `storage.py`. `handlers`
    bắt nó để xin arq **chạy lại** job: Mongo chập chờn một nhịp không phải lỗi của tệp.
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
    body = model.model_dump(mode="python")
    if isinstance(model, RawPage):
        body["_id"] = page_key(model.document_id, model.page)
    else:
        body["_id"] = model.document_id
    # `StrEnum` là `str`, nhưng ghi giá trị trần cho chắc: bên đọc ở plan 3c có thể không dùng
    # Python.
    body["source"] = model.source.value
    for key, value in body.items():
        if isinstance(value, datetime):
            body[key] = _to_bson_time(key, value)
    return body


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
        _db: Database chứa hai collection `documents` và `pages`.
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
            Index duy nhất `pages(document_id, page)`. Tạo lại một index đã có là không làm gì.
        """
        await self._db[_PAGES].create_index(
            [("document_id", ASCENDING), ("page", ASCENDING)], unique=True
        )

    async def begin(self, header: RawDocument) -> None:
        """Mở bản thô của một tài liệu, xoá bản thô cũ nếu có.

        Đọc lại một tài liệu là **ghi đè** bản thô của nó (plan 3b, D6): trang cũ của một lần đọc
        trước -- có thể bằng một đường đọc khác -- không được trộn với trang mới.

        Args:
            header: Đầu mục, `finished_at` còn `None`.

        Raises:
            ContentStoreUnavailable: Khi Mongo không ghi được lúc này.

        Side effects:
            Xoá mọi trang của tài liệu này, rồi ghi đè đầu mục.
        """
        async with _translated("begin", header.document_id):
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

    async def close(self) -> None:
        """Đóng pool kết nối. Gọi ở `on_shutdown` của worker."""
        await self._client.close()
