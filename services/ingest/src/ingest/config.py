"""Cấu hình của INGEST, đọc từ environment.

**Bốn trường, và đó là cả điểm của service này.** Trước plan 2c, process worker đọc settings
từ `be/config.py` — hai mươi trường, trong đó nó chạm năm, và hai trong năm chỉ vì nó import
`be/queue.py` cho một hàm nó không gọi. Mở file ấy ra thì không cách nào biết được điều đó.

Một file bốn trường **tự nói ra** ranh giới: không ngưỡng review, không khoá object storage,
không trần số bước gọi model, không header danh tính. Service này không quyết định gì nên nó
không có một con số nào để quyết định bằng.

Mỗi giá trị ở đây có một dòng tương ứng trong .env.example.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Neo vào gốc repository, cùng lý do và cùng độ sâu như `be/config.py` và
# `document/config.py`: để tương đối theo thư mục làm việc thì nó âm thầm trỏ vào
# hư không khi một process khởi động từ thư mục service của chính nó -- và một
# .env không tìm thấy không phải là lỗi, nó là một bộ default đầy đủ.
_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    """Settings lúc chạy của INGEST.

    Attributes:
        redis_url: Connection string tới Redis mà arq dùng chung với ba service kia.
        ingest_queue_name: Queue service này tiêu thụ. `services/document` đẩy kết quả
            đọc tệp vào đây. Đặt tên theo **bên tiêu thụ** chứ không theo công việc, vì
            `aiafa:grading` đã mục ruỗng đúng theo cách kia: tên nói về chấm bài và nay
            chở bảy task, sáu cái không phải chấm bài. Tên cũ của biến này là
            `BE_QUEUE_NAME`, và nó sai đúng theo luật ấy ngay khi worker rời `services/be`.
        database_url: URL SQLAlchemy async của kho giữ state. Service này **giữ
            credential database**, khác `agent` và `document` — và đó là hợp lệ: nó ghi
            vào một bảng, nên nó cần đường tới bảng ấy. Cái làm hai service kia thành
            service đọc-và-báo là chúng không giữ credential nào, chứ không phải việc
            chúng chạy process riêng.
        log_level: Mức log của cây logger `ingest.*`. Có mặt ở đây vì thiếu nó là một lỗi
            thật đã đo được: `be/worker.py` hardcode `INFO`, nên `LOG_LEVEL` trong .env chỉ
            có tác dụng ở process API và không chỗ nào nói ra điều đó.
    """

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    redis_url: str = "redis://127.0.0.1:6379/0"
    ingest_queue_name: str = "aiafa:ingest"
    database_url: str = "postgresql+asyncpg://aiafa:aiafa@127.0.0.1:5432/aiafa"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Trả về instance settings dùng chung cho cả process.

    Returns:
        Một object Settings đã cache, nên file .env chỉ được đọc một lần mỗi process.
    """
    return Settings()
