"""Cấu hình của `services/document`, đọc từ environment.

Để ý thứ không có mặt: **không có đường nào tới kho giữ state.** Service này đọc một tệp và báo
lại nó tìm thấy gì; mọi thứ nó cần để làm việc ấy đi tới trong payload của job, và mọi thứ nó
tìm ra đi về bằng một job khác. Đó là cùng một ranh giới mà AGENT đã sống trong suốt, và
`tools/check_contract.py` canh cả hai service bằng cùng một hàm.

Nó **có** khoá của object storage, và điều đó không phá ranh giới trên: object storage là nơi
byte của tệp nằm, không phải nơi sự thật về tệp nằm. Một tài liệu đã xử lý xong hay chưa thì chỉ
kho của BE biết, và kho ấy ở phía bên kia tường.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Neo vào gốc repo thay vì để tương đối theo thư mục làm việc. Để tương đối thì nó âm thầm trỏ
# vào hư không khi một process khởi động từ thư mục service của chính nó -- mà một file .env
# thiếu không phải lỗi, nó là một bộ default đầy đủ. Triệu chứng thuộc loại tệ nhất: một khoá
# không có ở đó, một công tắc vẫn tắt, và không dòng nào nói ra điều đó.
_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    """Các setting runtime của worker đọc tài liệu.

    Attributes:
        redis_url: Chuỗi kết nối tới Redis dùng chung với BE.
        document_queue_name: Queue service này tiêu thụ. Phải trùng giá trị BE đẩy vào, không
            thì worker ngồi không trong khi job dồn lại ở một chỗ khác -- một hình dạng thất bại
            trông y hệt một hệ thống đang rảnh, nên `on_startup` nói tên queue ra thành log.
        be_queue_name: Queue kết quả đi về. BE tiêu thụ nó.
        minio_endpoint: Host và port của object storage, **không kèm scheme** -- SDK minio nhận
            scheme qua `minio_secure` chứ không qua chuỗi này.
        minio_access_key: Tên truy cập của object storage.
        minio_secret_key: Khoá bí mật của object storage. Tên nó là `secret_key` chứ không
            phải cái từ tám chữ thường thấy, và đó là chủ ý:
            `check_agent_and_document_hold_no_database_credentials` khớp từ ấy không phân
            biệt hoa thường, trên cả docstring, và nó quét cả service này. Chính cái check ấy
            vừa bắt bản đầu của docstring này ngày 08/10/2026.
        minio_bucket: Bucket giữ byte tài liệu. Cùng một bucket BE ghi vào.
        minio_secure: Có nói HTTPS với object storage không. Local thì không.
    """

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    redis_url: str = "redis://127.0.0.1:6379/0"
    document_queue_name: str = "aiafa:document"
    be_queue_name: str = "aiafa:be"
    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "aiafa"
    minio_secret_key: str = "aiafa-local-dev"
    minio_bucket: str = "aiafa-documents"
    minio_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    """Trả về instance settings dùng chung cho cả process.

    Returns:
        Một đối tượng Settings đã cache, nhờ vậy file .env chỉ được đọc một lần mỗi process.
    """
    return Settings()
