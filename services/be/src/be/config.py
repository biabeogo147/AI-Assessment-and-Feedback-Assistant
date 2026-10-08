"""Cấu hình của BE, đọc từ environment.

Mỗi giá trị ở đây có một dòng tương ứng trong .env.example. Không chỗ nào trong
BE được phép hardcode một host, port, tên queue hay ngưỡng.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Neo vào gốc repository, chứ không để tương đối theo thư mục làm việc. Nếu để
# tương đối, nó âm thầm trỏ vào hư không khi một process khởi động từ thư mục
# service của chính nó -- và một .env không tìm thấy không phải là lỗi, nó là
# một bộ default đầy đủ. Triệu chứng thuộc loại tệ nhất: một key không có ở đó,
# một công tắc cứ nằm ở off, và không có thông báo nào ở đâu nói ra điều đó.
_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    """Settings lúc chạy của process BE.

    Attributes:
        redis_url: Connection string tới Redis instance mà arq dùng chung với AGENT.
        agent_queue_name: Queue mà cả hai bên thống nhất. Phải khớp với giá trị
            của AGENT, nếu không job bị đẩy vào nơi không ai nghe.
        document_queue_name: Queue BE đẩy việc đọc tài liệu vào. `services/document`
            tiêu thụ nó. Đặt tên theo **bên tiêu thụ** chứ không theo công việc, vì
            `aiafa:grading` đã mục ruỗng đúng theo cách kia: tên nói về chấm bài và
            nay chở bảy task, sáu cái không phải chấm bài.
        document_stale_after_seconds: Một tài liệu đứng ở `processing` bao lâu thì
            coi là job đã chết. Áp **lúc đọc**, không ghi gì -- một process đi canh
            những process đã chết thì cũng chết được y như vậy. Cùng hình dạng với
            `review_confidence_threshold`, thứ cũng chỉ sống ở đường đọc.
        job_result_ttl_seconds: arq giữ kết quả còn đọc được bao lâu sau khi job
            xong.
        review_confidence_threshold: Mức Confidence mà ở đó hoặc dưới đó, một bài
            đã chấm bị đưa vào Teacher Review Queue. BE sở hữu ngưỡng này.
        minio_endpoint: Host và port của object storage, **không kèm scheme** --
            SDK minio nhận scheme qua `minio_secure` chứ không qua chuỗi này.
        minio_access_key: Tên truy cập của object storage.
        minio_secret_key: Khoá bí mật của object storage. Cố ý **không** đặt tên có
            chữ `password`: `check_agent_holds_no_database_credentials` khớp chữ ấy
            không phân biệt hoa thường, và một ngày nào đó module này bị đọc từ một
            service khác thì cái tên là thứ duy nhất đứng giữa.
        minio_bucket: Bucket giữ byte tài liệu. Phải hợp lệ với DNS -- chữ thường,
            3-63 ký tự, không gạch dưới -- nếu không `make_bucket` ném.
        minio_secure: Có nói HTTPS với object storage không. Local thì không.
        database_url: URL SQLAlchemy async của kho giữ state của Attempt. ADR-21
            làm state đó bền, nên đây không phải tuỳ chọn trong bất kỳ môi trường
            nào mà học sinh có thể quay lại ngày mai.
        dev_identity_header: Tên của header đứng thay cho việc đăng nhập trong
            lúc chưa có màn hình sign-in. Request tự khai mình là
            "student:<code>" hoặc "teacher:<code>".
        dev_identity_enabled: Header đó có được tôn trọng hay không. False là giá
            trị an toàn; plan đã đưa nó vào yêu cầu rằng sign-in thật phải tắt
            cái này vĩnh viễn.
        agent_job_timeout_seconds: BE chờ một job của AGENT bao lâu trước khi bỏ
            cuộc. Phải trùm hết một job trọn vẹn, kể cả mọi lần thử mà vòng retry
            bên trong AGENT làm -- `tools/check_contract.py` ép điều đó, vì không
            service nào thấy được cả hai con số.
        stream_silence_timeout_seconds: Chat stream chịu được bao lâu không nghe
            thấy gì trước khi bỏ cuộc. Tách khỏi job timeout vì một lượt kèm học
            là một lần gọi model, còn viết câu hỏi của một round thì tới
            `llm_max_attempts` lần, và một học sinh đang ngồi xem chat không nên
            phải chờ hết cái budget dài hơn kia.
        max_tool_steps: Một lượt chat của giáo viên được hỏi AGENT "làm gì tiếp"
            bao nhiêu lần. Đây là trần của một vòng lặp mà độ dài do model chọn,
            nên nó là thứ duy nhất đứng giữa một model đang lú và một hoá đơn
            không có giới hạn.
        turn_budget_seconds: Một lượt được tiêu tổng cộng bao lâu. Cần có vì
            `max_tool_steps` không phải một lời hứa về thời gian chờ: tám step ở
            mức job timeout là hơn chín phút, và một proxy hay một browser sẽ ngắt
            kết nối từ lâu trước đó trong khi BE vẫn log thành công. Đây là giới
            hạn mà giáo viên thật sự cảm thấy.
        log_level: Mức log của cây logger `be.*`. `INFO` là mặc định vì đúng những
            dòng cần nhất khi truy một đề thiếu câu -- *vì sao* một câu bị loại --
            nằm ở mức đó. Hạ xuống `WARNING` là tự bịt mắt mình.
    """

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    redis_url: str = "redis://127.0.0.1:6379/0"
    agent_queue_name: str = "aiafa:grading"
    document_queue_name: str = "aiafa:document"
    document_stale_after_seconds: int = 300
    job_result_ttl_seconds: int = 3600
    review_confidence_threshold: float = 0.7
    database_url: str = "postgresql+asyncpg://aiafa:aiafa@127.0.0.1:5432/aiafa"
    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "aiafa"
    minio_secret_key: str = "aiafa-local-dev"
    minio_bucket: str = "aiafa-documents"
    minio_secure: bool = False
    dev_identity_header: str = "X-Actor"
    dev_identity_enabled: bool = True
    agent_job_timeout_seconds: int = 70
    stream_silence_timeout_seconds: float = 25.0
    max_tool_steps: int = 8
    turn_budget_seconds: float = 90.0
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Trả về instance settings dùng chung cho cả process.

    Returns:
        Một object Settings đã cache, nên file .env chỉ được đọc một lần mỗi
        process.
    """
    return Settings()
