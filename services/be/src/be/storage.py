"""Nơi byte của tài liệu thật sự nằm.

Đây là module **duy nhất** trong BE được phép import `minio`, và
`tools/check_contract.py` canh đúng điều đó. Lý do: SDK của MinIO là **sync**, còn BE
thì async, nên mỗi lời gọi phải đi qua `run_in_threadpool`. Một chỗ quên là một event
loop bị chặn suốt thời gian đẩy một cuốn sách giáo khoa lên — và kiểu lỗi ấy không bao
giờ hiện ra dưới dạng một exception, chỉ dưới dạng "sao hôm nay chậm thế". Gom cả vào
một file thì chỗ duy nhất phải nhớ điều đó cũng là một.

Mọi method công khai của một store là `async def`, kể cả bản in-memory không cần async
chút nào, vì người gọi không được phép biết bản nào đang chạy.

Byte từng nằm trong một cột `LargeBinary` của Postgres. Chúng rời đi vì
`services/document` — service đọc tệp — **không có credential database**, nên nó không
với tới được một cột. Docstring của `models.Document` đã hẹn trước đúng lần chuyển này.
"""

import logging
from typing import BinaryIO, Protocol

from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error
from starlette.concurrency import run_in_threadpool
from urllib3.exceptions import HTTPError

from be.config import Settings

logger = logging.getLogger(__name__)

# Loại nội dung suy ra từ **đuôi file**, không lấy từ `file.content_type` mà client
# khai. Lý do không phải là sự sạch sẽ: giá trị này đi vào metadata của object, nên nó
# là `Content-Type` mà MinIO **trả về** ở lần GET đầu tiên. Nhận lời khai của client ở
# đây là chôn sẵn một stored-XSS, chờ tới ngày có một endpoint tải tài liệu về. Đuôi
# file thì đã qua `_ALLOWED` nên nó là thứ duy nhất ở đây không phải lời khai.
_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}
_FALLBACK_CONTENT_TYPE = "application/octet-stream"

_STORE: "ObjectStore | None" = None

# Chuỗi lỗi mang theo lệnh sửa, cùng hình dạng với `SchemaDrifted` của `schema/ddl.py`: một
# người đọc log lúc 11 giờ đêm không nên phải đi tra xem lệnh nào dựng lại hạ tầng.
_HOW_TO_FIX = ".\\dev.ps1 infra-up"


class StorageUnavailable(RuntimeError):
    """Object storage không với tới được.

    Tách khỏi `S3Error` thô để người gọi không phải import `minio` chỉ để bắt lỗi —
    đó chính là thứ check seam cấm.
    """


class ObjectStore(Protocol):
    """Hợp đồng giữa BE và nơi byte nằm.

    Có **hai** bản cài đặt, và điều đó là cố ý: một Protocol chỉ có một implementor là
    một class trá hình, và bản in-memory là thứ test chạy trên.
    """

    async def ensure_ready(self) -> None:
        """Dựng bucket nếu chưa có, và chứng minh rằng kho với tới được."""
        ...

    async def put(self, key: str, data: BinaryIO, length: int, content_type: str) -> None:
        """Ghi một object. `data` phải đang ở vị trí 0 và còn đúng `length` byte."""
        ...

    async def read(self, key: str) -> bytes:
        """Đọc trọn một object."""
        ...

    async def remove(self, key: str) -> None:
        """Xoá một object. Không có thì im lặng."""
        ...

    async def clear(self) -> None:
        """Xoá sạch bucket. Chỉ `be.reset_db` gọi."""
        ...


class MinioObjectStore:
    """Bản thật. Mọi lời gọi SDK đi qua threadpool."""

    def __init__(
        self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool
    ) -> None:
        """Dựng client.

        Args:
            endpoint: `host:port`, **không kèm scheme** — SDK nhận scheme qua `secure`.
            access_key: Tên truy cập.
            secret_key: Khoá bí mật.
            bucket: Bucket giữ byte tài liệu.
            secure: Có nói HTTPS không.

        Note:
            Hàm dựng `Minio(...)` **không chạm mạng**. Phép thử kết nối duy nhất là
            `ensure_ready`, nên đừng tin rằng tạo được client nghĩa là tới được kho.
        """
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self._bucket = bucket

    def _ensure_ready(self) -> None:
        """Phần sync của `ensure_ready`."""
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    def _clear(self) -> None:
        """Phần sync của `clear`.

        `remove_objects` trả về một **generator các lỗi** và nó lazy: không ai lặp qua
        thì không một object nào bị xoá, và không một dòng log nào nói rằng đã không có
        gì xảy ra. Vòng `for` dưới đây là thứ thật sự làm việc xoá.
        """
        names = self._client.list_objects(self._bucket, recursive=True)
        targets = [DeleteObject(one.object_name) for one in names if one.object_name]
        if not targets:
            return
        for failure in self._client.remove_objects(self._bucket, targets):
            logger.warning("could not remove %s: %s", failure.name, failure.message)

    async def ensure_ready(self) -> None:
        """Dựng bucket nếu chưa có.

        Raises:
            StorageUnavailable: Khi không tới được kho, kèm lệnh dựng lại hạ tầng.
        """
        try:
            await run_in_threadpool(self._ensure_ready)
        except (S3Error, HTTPError, OSError) as exc:
            raise StorageUnavailable(
                f"Object storage unreachable: {exc}. Run {_HOW_TO_FIX}"
            ) from exc

    async def put(self, key: str, data: BinaryIO, length: int, content_type: str) -> None:
        """Ghi một object.

        Args:
            key: Khoá, do `document_key` dựng.
            data: Stream đang ở vị trí 0.
            length: Số byte, đã đo. SDK cần nó để biết chia bao nhiêu part.
            content_type: Suy từ đuôi file, không phải lời khai của client.

        Raises:
            StorageUnavailable: Khi ghi hỏng.

        Side effects:
            Một object mới trong bucket.
        """
        try:
            await run_in_threadpool(
                self._client.put_object, self._bucket, key, data, length, content_type
            )
        except (S3Error, HTTPError, OSError) as exc:
            raise StorageUnavailable(f"Could not store {key}: {exc}") from exc

    async def read(self, key: str) -> bytes:
        """Đọc trọn một object.

        Args:
            key: Khoá đã ghi.

        Returns:
            Toàn bộ byte.

        Raises:
            StorageUnavailable: Khi đọc hỏng, kể cả khi object không tồn tại.
        """

        def pull() -> bytes:
            response = self._client.get_object(self._bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        try:
            return await run_in_threadpool(pull)
        except (S3Error, HTTPError, OSError) as exc:
            raise StorageUnavailable(f"Could not read {key}: {exc}") from exc

    async def remove(self, key: str) -> None:
        """Xoá một object, không ném khi nó không có.

        Args:
            key: Khoá cần xoá.

        Side effects:
            Object biến mất. Lỗi chỉ được **log**: người gọi duy nhất là đường dọn rác
            sau một INSERT hỏng, và ở đó một exception thứ hai chỉ che mất cái thứ nhất.
        """
        try:
            await run_in_threadpool(self._client.remove_object, self._bucket, key)
        except (S3Error, HTTPError, OSError) as exc:
            logger.warning("could not remove orphaned object %s: %s", key, exc)

    async def clear(self) -> None:
        """Xoá sạch bucket.

        Raises:
            StorageUnavailable: Khi không tới được kho.

        Side effects:
            **Mọi** object biến mất.
        """
        try:
            await run_in_threadpool(self._clear)
        except (S3Error, HTTPError, OSError) as exc:
            raise StorageUnavailable(
                f"Could not clear the bucket: {exc}. Run {_HOW_TO_FIX}"
            ) from exc


class MemoryObjectStore:
    """Bản tham chiếu, và là thứ test chạy trên.

    Nó sống trong module production chứ không trong `tests/` vì hai lý do: một Protocol
    chỉ có một implementor thì không ai biết hợp đồng có thật sự tách rời hay không, và
    `services/document` sẽ cần đúng bản này. Có tiền lệ — nhánh `else` sqlite trong
    `reset_schema` cũng chỉ có test đi qua, và nó nằm trong `schema/ddl.py` chứ không
    trong `tests/`.
    """

    def __init__(self) -> None:
        """Mở một kho rỗng."""
        self.objects: dict[str, bytes] = {}

    async def ensure_ready(self) -> None:
        """Không có gì để dựng."""

    async def put(self, key: str, data: BinaryIO, length: int, content_type: str) -> None:
        """Ghi `length` byte đọc từ `data`.

        Args:
            key: Khoá.
            data: Stream đang ở vị trí 0.
            length: Số byte cần đọc. Cố ý đọc **đúng** chừng ấy chứ không `read()` hết:
                nhờ vậy một `length` sai hoặc một `seek(0)` bị quên cũng cắt cụt object
                ở đây y như nó cắt cụt trên MinIO thật, và test bắt được.
            content_type: Không dùng; giữ cho khớp hợp đồng.
        """
        self.objects[key] = data.read(length)

    async def read(self, key: str) -> bytes:
        """Đọc trọn một object.

        Args:
            key: Khoá đã ghi.

        Returns:
            Toàn bộ byte.

        Raises:
            StorageUnavailable: Khi khoá không có, để khớp hành vi của bản thật.
        """
        if key not in self.objects:
            raise StorageUnavailable(f"Could not read {key}: no such object")
        return self.objects[key]

    async def remove(self, key: str) -> None:
        """Xoá một object, không ném khi nó không có.

        Args:
            key: Khoá cần xoá.
        """
        self.objects.pop(key, None)

    async def clear(self) -> None:
        """Xoá sạch kho."""
        self.objects.clear()


def extension_of(filename: str) -> str:
    """Đuôi file, viết thường, kèm dấu chấm.

    Args:
        filename: Tên file.

    Returns:
        Ví dụ `.pdf`. Rỗng khi tên không có đuôi.
    """
    head, dot, tail = filename.rpartition(".")
    return f".{tail.lower()}" if dot and head else ""


def content_type_for(filename: str) -> str:
    """Loại nội dung suy từ đuôi file.

    Args:
        filename: Tên file giáo viên tải lên.

    Returns:
        Một content type an toàn để gắn vào object metadata.
    """
    return _CONTENT_TYPES.get(extension_of(filename), _FALLBACK_CONTENT_TYPE)


def document_key(teacher_id: str, document_id: str, filename: str) -> str:
    """Khoá của một tài liệu trong kho.

    Tiền tố theo giáo viên để console của MinIO đọc được, và để một ngày "xoá hết của
    người này" là một lần xoá prefix chứ không phải một vòng lặp.

    Tên file **không** đi vào khoá: `"SGK Giải tích 12.pdf"` là Unicode, có khoảng
    trắng, và là chuỗi client khai. Chỉ phần đuôi đi vào, và nó đã qua `_ALLOWED`.

    Args:
        teacher_id: Chủ của tài liệu.
        document_id: Id của hàng trong `documents`.
        filename: Tên file, chỉ dùng để lấy đuôi.

    Returns:
        Ví dụ `documents/<teacher>/<document>.pdf`.
    """
    return f"documents/{teacher_id}/{document_id}{extension_of(filename)}"


def create_store(settings: Settings) -> MinioObjectStore:
    """Dựng store thật từ settings.

    Args:
        settings: Settings của process.

    Returns:
        Một store chưa được chứng minh là với tới được — gọi `ensure_ready` để biết.
    """
    return MinioObjectStore(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
        secure=settings.minio_secure,
    )


def bind_store(store: ObjectStore) -> None:
    """Trỏ dependency của request vào store này.

    Args:
        store: Store mà mọi route nên dùng.

    Side effects:
        Đặt store ở mức module.
    """
    global _STORE
    _STORE = store


def get_store() -> ObjectStore:
    """Store cho một request.

    Đây là hàm thường chứ không phải async generator, khác `get_session`: một session
    sống theo request nên nó cần dọn dẹp lúc đóng, còn một store sống theo process.

    Returns:
        Store đang được bind.

    Raises:
        RuntimeError: Nếu ứng dụng chưa bao giờ gọi `bind_store`, nghĩa là một route
            đang chạy ngoài lifespan đã cấu hình.
    """
    if _STORE is None:
        raise RuntimeError("Object storage is not configured; bind_store was never called")
    return _STORE
