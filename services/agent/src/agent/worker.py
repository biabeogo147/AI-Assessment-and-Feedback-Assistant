"""Process worker arq của AGENT.

Chạy bằng:  arq agent.worker.WorkerSettings

Một hạn chế đã biết trên Windows: arq đăng ký signal handler qua
``loop.add_signal_handler``, và hàm đó raise NotImplementedError trên
ProactorEventLoop của Windows. arq nuốt lỗi ấy và chỉ log ở mức debug, nên worker
vẫn chạy nhưng không tắt một cách êm đẹp -- Ctrl+C cắt ngang job đang chạy thay vì
để nó làm xong. Tạm chấp nhận cho giai đoạn MVP ở máy local; xem lại khi service
được đóng container trên Linux.
"""

import logging

from arq.connections import RedisSettings
from arq.worker import func

from agent.config import get_settings
from agent.handlers import (
    explain,
    generate_retry_question,
    name_conversation,
    propose_next_step,
    report_plan,
    ring_bell,
    write_draft_question,
)
from contracts import (
    EXPLAIN_TURN_TASK,
    GENERATE_RETRY_QUESTION_TASK,
    NAME_CONVERSATION_TASK,
    PROPOSE_NEXT_STEP_TASK,
    REPORT_PLAN_TASK,
    WRITE_DRAFT_QUESTION_TASK,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

_settings = get_settings()

# arq mặc định timeout kết nối một giây, chặt quá so với Docker Desktop trên
# Windows: port proxy của nó cần vài giây sau khi container báo healthy mới chịu
# nhận connection, và worker thì thoát ngay lúc khởi động thay vì chờ.
_CONNECT_TIMEOUT_SECONDS = 5


def _redis_settings() -> RedisSettings:
    """Dựng RedisSettings cho arq với timeout kết nối phù hợp môi trường này.

    Returns:
        RedisSettings worker dùng được ngay.
    """
    parsed = RedisSettings.from_dsn(_settings.redis_url)
    parsed.conn_timeout = _CONNECT_TIMEOUT_SECONDS
    return parsed


async def startup(ctx: dict) -> None:
    """Nói ra worker đang tiêu thụ queue nào.

    Không có dòng này thì việc tên queue của BE và AGENT lệch nhau trông y hệt một
    hệ thống đang rảnh: job được đẩy vào, không có lỗi nào, và không có gì chạy.

    Args:
        ctx: Context worker của arq. Không dùng.

    Side effects:
        Ghi một dòng log.
    """
    logger.info(
        "AGENT worker ready: queue=%s redis=%s",
        _settings.agent_queue_name,
        _settings.redis_url,
    )


class WorkerSettings:
    """Cấu hình worker của arq.

    Mỗi task được đăng ký dưới hằng số lấy từ `contracts` chứ không dưới tên hàm
    Python, nhờ vậy việc đổi tên hàm không thể âm thầm làm hỏng lời gọi enqueue của
    BE.
    """

    functions = [
        func(write_draft_question, name=WRITE_DRAFT_QUESTION_TASK),
        func(generate_retry_question, name=GENERATE_RETRY_QUESTION_TASK),
        func(explain, name=EXPLAIN_TURN_TASK),
        func(name_conversation, name=NAME_CONVERSATION_TASK),
        # Một lượt suy nghĩ cho khung chat của giáo viên. Khác ba task trên, nó
        # không hoàn thành việc nào của riêng mình: BE gọi nó một lần cho mỗi bước
        # của một loop mà BE sở hữu, nên một job ở đây là một lần gọi model và
        # invariant về timeout vẫn đúng trên đường này.
        func(propose_next_step, name=PROPOSE_NEXT_STEP_TASK),
        # Lời kể sau khi một plan đã chạy. Một task riêng chứ không phải một vòng nữa
        # của task trên: đầu vào của nó là kết quả cả plan, không phải một catalog
        # (ADR-25). Nhờ vậy một job vẫn là một lần gọi model.
        func(report_plan, name=REPORT_PLAN_TASK),
    ]
    queue_name = _settings.agent_queue_name
    redis_settings = _redis_settings()
    keep_result = _settings.job_result_ttl_seconds
    on_startup = startup

    # Chuông tiến độ rung ở đây chứ không trong thân job, và thứ tự là cả lý do: arq ghi
    # kết quả bằng `finish_job` rồi mới gọi hook này. Rung từ trong job là báo một câu xong
    # trước khi ai đọc được nó — BE nghe chuông rồi thu hoạch sẽ gặp `pending`, màn hình
    # trễ một nhịp, và tiếng chuông cuối cùng không gặt được gì (ADR-25).
    after_job_end = ring_bell
