"""BE đọc mục lục và đoạn nội dung của một tài liệu từ kho nội dung (`draft-from-document`). **Chỉ
đọc.**

Kho nội dung (MongoDB) do `services/document` ghi: bản thô (`mongo-content-store`) và cây mục lục
(`document-agent-hierarchy`). BE đọc cây để tool của Kriky khớp lời giáo viên với chương, bài thật,
và đọc đoạn cho tool `read_section`, để Kriky đọc phần sách trước khi nêu dàn ý. Job soạn câu
**không bao giờ** nhận đoạn chữ: nó chỉ nhận mục dàn ý của nó (ADR-29,
`check_drafting_reads_no_document_text`). Ghi thì không bao giờ:
`tools/check_contract.py` cho `pymongo` vào BE **chỉ** ở module này, và đỏ khi module này gọi một
hàm ghi.

Sự thật về tài liệu -- nó đã *sẵn sàng* chưa, nó thuộc giáo viên nào -- vẫn chỉ ở Postgres. Module
này không bao giờ được hỏi câu ấy; người gọi kiểm nó trước, ở `documents`.

Mongo không với tới được thì BE **không** chết lúc khởi động, khác object storage: soạn đề không có
tài liệu vẫn chạy, và một tool đọc mục lục trả lời *"kho nội dung không với tới được"* thay vì kéo
cả khung chat chết theo.
"""

import logging
from collections.abc import Iterable
from typing import Protocol

from pydantic import ValidationError
from pymongo import ASCENDING, AsyncMongoClient
from pymongo.errors import PyMongoError

from be.config import Settings
from contracts import IndexChunk, IndexHeader, IndexNode, PageFormulas

logger = logging.getLogger(__name__)

# Tên collection, như `services/document/src/document/content_store.py` ghi. Hai service không
# import nhau, nên tên lặp lại ở đây; đổi một bên mà quên bên kia thì `tree` trả rỗng -- và test
# đầu-cuối của `draft-from-document` là chỗ thấy điều ấy.
_INDEXES = "indexes"
_NODES = "nodes"
_CHUNKS = "chunks"
# Bản thô (`mongo-content-store`) -- BE chỉ hỏi nó một câu: trang nào có khối `formula`.
_PAGES = "pages"
# Công thức đọc từ ảnh trang (`formulas-on-demand`), `services/document` ghi khi BE xin.
_FORMULAS = "page_formulas"
_FORMULA_KIND = "formula"


class ContentUnavailable(RuntimeError):
    """Kho nội dung không với tới được, hoặc trả lỗi."""


class ContentReader(Protocol):
    """Những gì BE đọc được từ kho nội dung."""

    async def tree(self, document_id: str) -> tuple[IndexHeader, list[IndexNode]] | None:
        """Cây mục lục đã ghi xong của một tài liệu, nút theo thứ tự preorder.

        Args:
            document_id: Tài liệu.

        Returns:
            Đầu mục và các nút, hoặc `None` khi chưa có cây trọn vẹn.

        Raises:
            ContentUnavailable: Khi không đọc được kho.
        """
        ...

    async def chunks(self, document_id: str, nodes: Iterable[int]) -> list[IndexChunk]:
        """Các đoạn thuộc những nút này, theo thứ tự trong tài liệu.

        Args:
            document_id: Tài liệu.
            nodes: `ordinal` các nút.

        Returns:
            Các đoạn có `node_ordinal` thuộc `nodes`.

        Raises:
            ContentUnavailable: Khi không đọc được kho.
        """
        ...

    async def formula_pages(self, document_id: str, pages: Iterable[int]) -> set[int]:
        """Những trang trong `pages` có ít nhất một khối `formula` (nhãn PP-DocLayout lúc tải lên).

        Đây là cổng của việc đọc công thức bằng ảnh (`formulas-on-demand`): trang không có khối ấy
        thì không ai trả tiền đọc ảnh nó. Tệp có lớp chữ hay tệp văn bản thì không có khối nào
        mang nhãn này -- mọi khối của chúng là `text`.

        Args:
            document_id: Tài liệu.
            pages: Trang tệp, đếm từ 1.

        Returns:
            Tập con của `pages`.

        Raises:
            ContentUnavailable: Khi không đọc được kho.
        """
        ...

    async def formulas(self, document_id: str, pages: Iterable[int]) -> dict[int, PageFormulas]:
        """Công thức đã đọc của những trang này, theo trang.

        Args:
            document_id: Tài liệu.
            pages: Trang tệp, đếm từ 1.

        Returns:
            Trang đã có trong cache → hàng của nó. Trang chưa đọc thì không có khoá.

        Raises:
            ContentUnavailable: Khi không đọc được kho.
        """
        ...


def _model[M: IndexHeader | IndexNode | IndexChunk | PageFormulas](kind: type[M], body: dict) -> M:
    return kind.model_validate({key: value for key, value in body.items() if key != "_id"})


class MongoContentReader:
    """Bản thật, trên `pymongo` async. Một client cho cả process, nối lười ở lời gọi đầu.

    Attributes:
        _client: Client async của Mongo.
        _db: Database của kho nội dung.
    """

    def __init__(self, url: str, database: str):
        """Tạo client. Chưa chạm mạng.

        Args:
            url: Chuỗi kết nối Mongo.
            database: Tên database.
        """
        self._client: AsyncMongoClient = AsyncMongoClient(
            url, tz_aware=True, serverSelectionTimeoutMS=3000
        )
        self._db = self._client[database]

    async def tree(self, document_id: str) -> tuple[IndexHeader, list[IndexNode]] | None:
        """Xem `ContentReader.tree`."""
        try:
            # Đầu mục ghi **cuối cùng** (`content_store.put_index`): có nó là cây đã ghi xong.
            head = await self._db[_INDEXES].find_one({"_id": document_id})
            if head is None:
                return None
            found = self._db[_NODES].find({"document_id": document_id}).sort("ordinal", ASCENDING)
            rows = await found.to_list()
            return _model(IndexHeader, head), [_model(IndexNode, row) for row in rows]
        except (PyMongoError, ValidationError) as exc:
            # `ValidationError` ở đây là một cây ghi theo hình dạng cũ hơn contract -- contract thêm
            # một trường bắt buộc, cây chưa dựng lại. Với khung chat, nó cùng nghĩa với kho vắng
            # mặt: không đọc được, nói ra, không 500 (review B2, `draft-from-document`).
            logger.warning("content store unreadable for %s: %s", document_id, exc)
            raise ContentUnavailable(str(exc)) from exc

    async def chunks(self, document_id: str, nodes: Iterable[int]) -> list[IndexChunk]:
        """Xem `ContentReader.chunks`."""
        wanted = sorted(set(nodes))
        try:
            found = (
                self._db[_CHUNKS]
                .find({"document_id": document_id, "node_ordinal": {"$in": wanted}})
                .sort("ordinal", ASCENDING)
            )
            rows = await found.to_list()
            return [_model(IndexChunk, row) for row in rows]
        except (PyMongoError, ValidationError) as exc:
            logger.warning("content store unreadable for %s: %s", document_id, exc)
            raise ContentUnavailable(str(exc)) from exc

    async def formula_pages(self, document_id: str, pages: Iterable[int]) -> set[int]:
        """Xem `ContentReader.formula_pages`."""
        wanted = sorted(set(pages))
        if not wanted:
            return set()
        try:
            found = self._db[_PAGES].find(
                {
                    "document_id": document_id,
                    "page": {"$in": wanted},
                    "blocks.kind": _FORMULA_KIND,
                },
                {"page": 1, "_id": 0},
            )
            return {int(row["page"]) for row in await found.to_list()}
        except PyMongoError as exc:
            logger.warning("content store unreadable for %s: %s", document_id, exc)
            raise ContentUnavailable(str(exc)) from exc

    async def formulas(self, document_id: str, pages: Iterable[int]) -> dict[int, PageFormulas]:
        """Xem `ContentReader.formulas`."""
        wanted = sorted(set(pages))
        if not wanted:
            return {}
        try:
            found = self._db[_FORMULAS].find({"document_id": document_id, "page": {"$in": wanted}})
            rows = [_model(PageFormulas, row) for row in await found.to_list()]
            return {row.page: row for row in rows}
        except (PyMongoError, ValidationError) as exc:
            logger.warning("content store unreadable for %s: %s", document_id, exc)
            raise ContentUnavailable(str(exc)) from exc

    async def close(self) -> None:
        """Đóng client."""
        await self._client.close()


class MemoryContentReader:
    """Bản trong bộ nhớ cho test: cây và đoạn đặt sẵn theo tài liệu.

    Attributes:
        trees: `document_id` → (đầu mục, nút).
        pieces: `document_id` → đoạn.
        formula_marks: `document_id` → trang có khối `formula`.
        page_formulas: `document_id` → trang → công thức đã đọc.
        broken: Đặt True để mọi lời đọc ném `ContentUnavailable`.
    """

    def __init__(self) -> None:
        """Kho rỗng."""
        self.trees: dict[str, tuple[IndexHeader, list[IndexNode]]] = {}
        self.pieces: dict[str, list[IndexChunk]] = {}
        self.formula_marks: dict[str, set[int]] = {}
        self.page_formulas: dict[str, dict[int, PageFormulas]] = {}
        self.broken = False

    async def tree(self, document_id: str) -> tuple[IndexHeader, list[IndexNode]] | None:
        """Xem `ContentReader.tree`."""
        if self.broken:
            raise ContentUnavailable("broken on purpose")
        return self.trees.get(document_id)

    async def chunks(self, document_id: str, nodes: Iterable[int]) -> list[IndexChunk]:
        """Xem `ContentReader.chunks`."""
        if self.broken:
            raise ContentUnavailable("broken on purpose")
        wanted = set(nodes)
        return [one for one in self.pieces.get(document_id, []) if one.node_ordinal in wanted]

    async def formula_pages(self, document_id: str, pages: Iterable[int]) -> set[int]:
        """Xem `ContentReader.formula_pages`."""
        if self.broken:
            raise ContentUnavailable("broken on purpose")
        return set(pages) & self.formula_marks.get(document_id, set())

    async def formulas(self, document_id: str, pages: Iterable[int]) -> dict[int, PageFormulas]:
        """Xem `ContentReader.formulas`."""
        if self.broken:
            raise ContentUnavailable("broken on purpose")
        read = self.page_formulas.get(document_id, {})
        return {page: read[page] for page in set(pages) if page in read}


_READER: ContentReader | None = None


def create_reader(settings: Settings) -> MongoContentReader:
    """Dựng bản thật từ settings.

    Args:
        settings: Settings của process.

    Returns:
        Reader, chưa chạm mạng.
    """
    return MongoContentReader(settings.mongo_url, settings.mongo_database)


def bind_reader(reader: ContentReader | None) -> None:
    """Trỏ mọi lời đọc vào reader này; `None` để gỡ.

    Args:
        reader: Reader dùng cho cả process.

    Side effects:
        Thay reader dùng chung của module.
    """
    global _READER
    _READER = reader


def get_reader() -> ContentReader:
    """Reader của process.

    Returns:
        Reader đã bind.

    Raises:
        ContentUnavailable: Khi chưa bind -- process không dựng kho nội dung lúc khởi động.
    """
    if _READER is None:
        raise ContentUnavailable("no content reader is bound")
    return _READER
