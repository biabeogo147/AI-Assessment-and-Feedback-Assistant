"""Đọc byte của một tài liệu từ object storage.

Module **duy nhất** trong service này được import `minio`, và `tools/check_contract.py` canh
đúng điều đó bằng cùng một hàm canh `be/storage.py`. SDK là sync; một lời gọi không bọc thread
chặn mọi job khác trên worker này và không ném gì cả.

**Chỉ đọc.** Không có `put`, không có `remove`, không có `clear`, và sự thiếu vắng ấy là một
phần của thiết kế chứ không phải một việc chưa làm: BE ghi byte, service này đọc chúng. Một
`put` ở đây sẽ là đường thứ hai để byte vào bucket, và hai đường thì sớm muộn khác nhau ở một
chỗ nào đó -- content type, sơ đồ khoá, hay thứ tự với hàng trong database.

Khác `be/storage.py` ở hai chỗ, cả hai có lý do:

- Bọc thread bằng `asyncio.to_thread` của thư viện chuẩn, không bằng `run_in_threadpool`. BE có
  hàm kia vì FastAPI đã mang nó vào; ở đây kéo cả một framework web về chỉ để lấy một hàm bọc
  thread là trả giá cho một thứ không dùng.
- Không có `bind`/`get` toàn cục. Seam kiểu `Depends` tồn tại trong BE vì test dựng một app rỗng
  và phải thay được store; một worker arq thì dựng client **một lần** trong `on_startup` rồi cất
  vào `ctx`, nên chỗ để thay đã có sẵn và một biến module chỉ là một trạng thái toàn cục nữa.
"""

import asyncio
import logging

from minio import Minio
from minio.error import S3Error
from urllib3.exceptions import HTTPError

from document.config import Settings

logger = logging.getLogger(__name__)

# Chuỗi lỗi mang theo lệnh sửa, cùng hình dạng với `be/storage.py`: một người đọc log lúc 11 giờ
# đêm không nên phải đi tra xem lệnh nào dựng lại hạ tầng.
_HOW_TO_FIX = ".\\dev.ps1 infra-up"


class StorageUnavailable(RuntimeError):
    """Object storage không với tới được, hoặc object không có ở đó.

    Tách khỏi `S3Error` thô để người gọi không phải import `minio` chỉ để bắt lỗi -- đó chính là
    thứ check seam cấm.
    """


class ObjectReader:
    """Đọc object từ một bucket của MinIO.

    Attributes:
        _client: Client sync của MinIO. Dựng nó **không** chạm mạng, nên một instance tạo thành
            công chưa chứng minh gì cả -- lần đọc đầu tiên mới là phép thử thật.
        _bucket: Bucket giữ byte tài liệu, cùng cái BE ghi vào.
    """

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool):
        """Dựng reader.

        Args:
            endpoint: Host và port, không kèm scheme.
            access_key: Tên truy cập.
            secret_key: Khoá bí mật.
            bucket: Tên bucket.
            secure: Có nói HTTPS hay không.
        """
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self._bucket = bucket

    async def read(self, key: str) -> bytes:
        """Đọc trọn một object.

        Args:
            key: Khoá BE đã ghi, đi tới trong payload của job.

        Returns:
            Toàn bộ byte của tệp.

        Raises:
            StorageUnavailable: Khi đọc hỏng, kể cả khi object không tồn tại. Hai ca ấy gộp làm
                một có chủ ý: từ phía service này cả hai đều là *"không có tệp để đọc"*, và phân
                biệt chúng chỉ đổi được câu log chứ không đổi được việc phải làm.
        """

        def pull() -> bytes:
            response = self._client.get_object(self._bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        try:
            return await asyncio.to_thread(pull)
        except (S3Error, HTTPError, OSError) as exc:
            raise StorageUnavailable(f"Could not read {key}: {exc} ({_HOW_TO_FIX})") from exc


def create_reader(settings: Settings) -> ObjectReader:
    """Dựng reader từ settings.

    Không chạm mạng. Gọi được trong `on_startup` của worker mà không sợ nó chết vì MinIO chưa
    lên -- lần đọc đầu tiên mới là lúc biết, và lúc ấy một job hỏng là một
    `DocumentState.FAILED` gửi về cho BE, không phải một worker chết.

    Args:
        settings: Settings của process.

    Returns:
        Một reader chưa kết nối.
    """
    return ObjectReader(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
        secure=settings.minio_secure,
    )
