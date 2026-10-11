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

from pydantic import Field
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
        ingest_queue_name: Queue kết quả đi về. `services/ingest` tiêu thụ nó.
        document_index_queue_name: Queue của job dựng cây (plan 3c, D4). Worker OCR đẩy vào,
            `document.index_worker` tiêu thụ -- cùng service, khác process.
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
        mongo_url: Chuỗi kết nối tới kho nội dung (MongoDB), nơi bản thô của mọi tài liệu nằm.
            Được phép ở service này vì cùng lý do với khoá object storage: Mongo giữ **nội dung**
            đọc ra từ tệp, không giữ **sự thật** về tệp -- `documents.state` vẫn chỉ ở kho của BE
            (plan 3b, D1). Chỉ `content_store.py` được dùng nó.
        mongo_database: Tên database trong Mongo.
        ocr_pages_per_job: Số trang một job OCR đọc trước khi nhường chỗ cho job kế. 4,5 s/trang
            đo ở plan 3a nhân 10 là ~45 s, dưới trần `job_timeout` 120 s với chỗ dư cho trang
            dày chữ.
        ocr_reader: Bộ nhận dạng chữ của đường OCR, `easyocr` hoặc `vietocr`. Mặc định
            `easyocr`: bằng hoặc hơn VietOCR ở mọi thước trên 50 trang (plan 3a).
        ocr_threads: Số luồng CPU cho OCR. Đặt bằng số vCPU của máy chạy worker.
        jev_api_key: Khoá của Jev (TypeSafe AI), đọc từ `JEV_API_KEY` rồi **truyền vào** client --
            SDK tự tìm `TYPESAFE_API_KEY`, nhưng `.env` của repo này không bao giờ tới
            `os.environ` (cùng bài học với `agent/llm.py`). Rỗng thì cây đi đường luật.
        jev_model: Phiên bản Jev **ghim**: một phiên bản khác trả xác suất khác, nên ngưỡng
            `jev_min_confidence` chỉ có nghĩa đi kèm con số này.
        jev_concurrency: Số lời gọi Jev bay cùng lúc trong một job.
        jev_timeout_seconds: Trần giây cho một lời gọi Jev (TypeSafe báo 70--500 ms).
        jev_min_confidence: Dưới ngưỡng này luật quyết thay Jev (D5). Chọn bằng bộ đo trên cây
            vàng (plan 3c, Task 3, `data/run-6/hierarchy-jev-1.13.0/`): Jev thuần trên Lớp 6 tập 1
            dựng 138 nút cho 91 nút vàng (F1 cấp 3: 69%), chủ yếu vì xếp tiêu đề con không đánh số
            vào cấp 3 với `confidence` thấp. Ở 0,8 Jev chỉ còn thắng luật đúng một ca, và ca ấy sai
            -- cây gần như là cây của luật, cho tới khi câu hỏi Jev được làm lại (plan 3c, Status).
        openai_api_key: Khoá OpenAI cho tóm tắt và đọc banner -- cùng khoá AGENT dùng, đọc từ cùng
            `OPENAI_API_KEY`, truyền vào client như ở `agent/llm.py`. Rỗng thì cây không có tóm
            tắt và chương chỉ có nhãn số.
        summary_model: Model tóm tắt nút cây (người dùng chốt `gpt-4o-mini`, 11/10/2026).
        banner_model: Model đọc tên chương trên ảnh banner (D9; người dùng chọn `gpt-5.6-luna`).
        llm_timeout_seconds: Trần giây cho một lời gọi OpenAI.
        llm_concurrency: Số lời gọi OpenAI bay cùng lúc trong một job.
    """

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    redis_url: str = "redis://127.0.0.1:6379/0"
    document_queue_name: str = "aiafa:document"
    ingest_queue_name: str = "aiafa:ingest"
    document_index_queue_name: str = "aiafa:document-index"
    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "aiafa"
    minio_secret_key: str = "aiafa-local-dev"
    minio_bucket: str = "aiafa-documents"
    minio_secure: bool = False
    mongo_url: str = "mongodb://127.0.0.1:27017"
    mongo_database: str = "aiafa_content"
    ocr_pages_per_job: int = Field(default=10, ge=1)
    ocr_reader: str = "easyocr"
    ocr_threads: int = 4
    jev_api_key: str = ""
    jev_model: str = "jev-1.13.0"
    jev_concurrency: int = Field(default=16, ge=1)
    jev_timeout_seconds: float = Field(default=20, gt=0)
    jev_min_confidence: float = Field(default=0.8, ge=0, le=1)
    openai_api_key: str = ""
    summary_model: str = "gpt-4o-mini"
    banner_model: str = "gpt-5.6-luna"
    llm_timeout_seconds: float = Field(default=60, gt=0)
    llm_concurrency: int = Field(default=8, ge=1)


@lru_cache
def get_settings() -> Settings:
    """Trả về instance settings dùng chung cho cả process.

    Returns:
        Một đối tượng Settings đã cache, nhờ vậy file .env chỉ được đọc một lần mỗi process.
    """
    return Settings()
