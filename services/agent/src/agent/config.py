"""Cấu hình của AGENT, đọc từ environment.

Để ý thứ không có mặt: không có database URL. AGENT không giữ credential của tầng
lưu trữ nào, nên một bài nộp phải tới kèm theo mọi thứ cần để chấm nó.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Neo vào gốc repo thay vì để tương đối theo thư mục làm việc. Nếu để tương đối,
# nó âm thầm trỏ vào hư không khi một process khởi động từ thư mục service của
# chính nó -- mà một file .env thiếu không phải lỗi, nó là một bộ default đầy đủ.
# Triệu chứng thuộc loại tệ nhất: một key không có ở đó, một công tắc vẫn tắt, và
# không một dòng thông báo nào nói ra điều đó.
_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    """Các setting runtime của worker AGENT.

    Attributes:
        redis_url: Chuỗi kết nối tới Redis dùng chung với BE.
        agent_queue_name: Queue cần tiêu thụ. Phải trùng giá trị của BE, không thì
            worker ngồi không trong khi job dồn lại ở một chỗ khác.
        job_result_ttl_seconds: Kết quả đã xong còn đọc được bởi BE trong bao lâu.
        llm_enabled: Handler có gọi model thật hay không. False thì giữ nội dung
            dọn trước, đó là thứ mọi test chạy trên, và là thứ một buổi demo lùi về
            khi không có key nào được cấu hình.
        llm_provider: Tên provider mà LangChain hiểu, ví dụ "openai".
        llm_model: Id model tại provider đó. Không có default nào đáng có: một id
            sai là một lần gọi thất bại, nên phải đặt nó một cách có chủ ý.
        openai_api_key: Credential cho provider OpenAI.
        google_api_key: Credential cho provider Gemini. Rỗng nghĩa là chuỗi
            fallback không có chỗ nào để lùi về, và điều đó được phép.
        llm_fallback_provider: Provider được thử khi provider đầu raise.
        llm_fallback_model: Id model tại provider fallback.
        llm_timeout_seconds: Trần thời gian cho một lần gọi model.
        llm_max_attempts: Một job được hỏi model bao nhiêu lần trước khi bỏ. Nó
            nằm ở đây chứ không nằm cạnh cái loop nó điều khiển, vì mức kiên nhẫn
            của BE với một job phải phủ hết số lần đó, và `tools/check_contract.py`
            chỉ check được điều ấy nếu nó đọc được con số.
    """

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    redis_url: str = "redis://127.0.0.1:6379/0"
    agent_queue_name: str = "aiafa:grading"
    job_result_ttl_seconds: int = 3600

    llm_enabled: bool = False
    llm_provider: str = "openai"
    llm_model: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    llm_fallback_provider: str = ""
    llm_fallback_model: str = ""
    llm_timeout_seconds: int = 20
    llm_max_attempts: int = 3


@lru_cache
def get_settings() -> Settings:
    """Trả về instance settings dùng chung cho cả process.

    Returns:
        Một đối tượng Settings đã cache, nhờ vậy file .env chỉ được đọc một lần
        mỗi process.
    """
    return Settings()
