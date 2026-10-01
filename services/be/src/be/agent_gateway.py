"""Gọi AGENT, và kiểm thứ nhận về.

Hai trách nhiệm, và cái thứ hai mới là cái quan trọng. Đẩy job vào queue là việc
đường ống. Kiểm tính hợp lệ là một luật nghiệp vụ: ADR-18 nói một câu hỏi chở đúng
một phương án đúng, một error label trên mọi Distractor, và nhiều hơn một lời giải
chi tiết -- còn một luật chỉ được một prompt ép thì không phải đang được ép. Một lần
review dữ liệu mẫu viết tay vào 2026-09-11 tìm ra một câu hỏi có hai đáp án đúng, nên
đây không phải một kiểu lỗi trên lý thuyết.
"""

import asyncio
import logging
from collections.abc import AsyncIterator

from arq.connections import ArqRedis
from arq.jobs import Job, JobStatus

from be.config import Settings
from contracts import (
    GENERATE_RETRY_QUESTION_TASK,
    GeneratedQuestion,
    RetryQuestionCompleted,
    RetryQuestionRequested,
)

logger = logging.getLogger(__name__)

_POLL_SECONDS = 0.2

# Một lần đọc channel stream chờ bao lâu trước khi vòng lặp quay lại nhìn job. Nhỏ đủ
# để việc job xong được nhận ra ngay, lớn đủ để một stream đang rỗi không thành một
# vòng lặp quay nóng.
_LISTEN_SECONDS = 0.2


class AgentError(RuntimeError):
    """Không tới được AGENT, bị timeout, hoặc nó trả về nội dung không dùng được."""


async def run_task(
    pool: ArqRedis | None,
    settings: Settings,
    task_name: str,
    payload: dict,
) -> dict:
    """Đẩy một task của AGENT vào queue rồi chờ kết quả của nó.

    BE chờ chứ không đưa cho client một job id, vì mọi người gọi hàm này đều đang ở
    bên trong một request mà người dùng đang ngồi xem, và dựng thêm một giao thức poll
    thứ hai lên trên giao thức của arq sẽ không mua được gì.

    Args:
        pool: Pool arq đã kết nối, hoặc None khi lúc startup không tới được queue. BE
            vẫn đứng được mà không có nó, để pha 1 tiếp tục chạy.
        settings: Settings của process, nơi cung cấp tên queue và timeout.
        task_name: Một trong các hằng tên task trong `contracts`.
        payload: Message yêu cầu đã serialise.

    Returns:
        Message trả lời đã serialise.

    Raises:
        AgentError: Nếu queue từ chối job, worker không bao giờ xong trong thời hạn
            timeout, hoặc job thất bại.

    Side effects:
        Ghi một job lên queue Redis dùng chung.
    """
    if pool is None:
        raise AgentError("hàng đợi chưa sẵn sàng")

    job = await pool.enqueue_job(task_name, payload, _queue_name=settings.agent_queue_name)
    if job is None:
        raise AgentError(f"arq refused task {task_name}")

    deadline = asyncio.get_running_loop().time() + settings.agent_job_timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        status = await job.status()
        if status is JobStatus.complete:
            finished = Job(job.job_id, redis=pool, _queue_name=settings.agent_queue_name)
            info = await finished.result_info()
            if info is None or not info.success:
                raise AgentError(f"task {task_name} failed inside AGENT")
            return info.result
        await asyncio.sleep(_POLL_SECONDS)

    raise AgentError(f"task {task_name} did not finish in {settings.agent_job_timeout_seconds}s")


async def stream_task(
    pool: ArqRedis | None,
    settings: Settings,
    task_name: str,
    payload: dict,
    channel: str,
    silence_seconds: float | None = None,
) -> AsyncIterator[tuple[str, object]]:
    """Đẩy một task của AGENT vào queue rồi yield output của nó ngay khi nó được viết.

    Việc subscribe xảy ra **trước** khi đẩy job, và chính thứ tự đó là lý do hàm này
    tồn tại thay vì chỉ là ba câu lệnh ở chỗ gọi. Pub/sub của Redis không giữ lịch sử:
    publish vào một channel không ai đang nghe thì lời nói mất luôn. arq giao job cho
    worker gần như ngay lập tức, nên đẩy job trước là trao cho worker cơ hội nói vào
    một căn phòng trống.

    Args:
        pool: Pool arq đã kết nối, hoặc None khi không tới được queue.
        settings: Settings của process, nơi cung cấp tên queue và timeout.
        task_name: Một trong các hằng tên task trong `contracts`.
        payload: Message yêu cầu đã serialise.
        channel: Nơi worker được bảo là hãy publish từng mảnh vào.
        silence_seconds: Chịu được bao lâu không nghe thấy gì trước khi bỏ cuộc. Mặc
            định là job timeout. Người gọi mà job chỉ là một lần gọi model thì truyền
            vào một con số ngắn hơn, nhờ vậy phía đọc của nó không bị bắt chờ hết một
            budget đo theo một job có retry.

    Yields:
        `("chunk", text)` cho mỗi mảnh ngay khi nó tới, rồi đúng một
        `("result", reply)` chở message trả lời đã serialise.

    Raises:
        AgentError: Nếu queue từ chối job, job thất bại, hoặc không có gì xong trong
            thời hạn timeout.

    Side effects:
        Subscribe vào một channel Redis và ghi một job lên queue.
    """
    if pool is None:
        raise AgentError("hàng đợi chưa sẵn sàng")

    pubsub = pool.pubsub()
    try:
        # Nằm trong try, nhờ vậy một lần subscribe gãy giữa đường vẫn tới được phần dọn
        # dẹp bên dưới thay vì làm rò một connection ra khỏi pool.
        await pubsub.subscribe(channel)

        job = await pool.enqueue_job(task_name, payload, _queue_name=settings.agent_queue_name)
        if job is None:
            raise AgentError(f"arq refused task {task_name}")

        # Được làm mới ở mỗi mảnh, nên đây là một đồng hồ đếm sự im lặng, không phải một
        # giới hạn độ dài. Một model đang viết câu trả lời dài là một model đang làm
        # việc; một model không nói gì suốt cả cửa sổ thời gian thì không. Cắt một câu
        # trả lời đang chảy giữa dòng chỉ vì nó chảy tốt quá lâu thì thật vô lý.
        patience = silence_seconds or settings.agent_job_timeout_seconds
        deadline = asyncio.get_running_loop().time() + patience
        while asyncio.get_running_loop().time() < deadline:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=_LISTEN_SECONDS
            )
            if message is not None and message.get("type") == "message":
                deadline = asyncio.get_running_loop().time() + patience
                yield "chunk", _text(message["data"])
                continue

            if await job.status() is not JobStatus.complete:
                continue

            # Job đã xong, nhưng những mảnh được publish ở khoảnh khắc cuối có thể vẫn
            # còn đang xếp hàng trên connection này. Vét sạch chúng trước khi đóng, nếu
            # không học sinh mất phần cuối của câu mà em đang đọc.
            while True:
                trailing = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.0)
                if trailing is None or trailing.get("type") != "message":
                    break
                yield "chunk", _text(trailing["data"])

            info = await Job(
                job.job_id, redis=pool, _queue_name=settings.agent_queue_name
            ).result_info()
            if info is None or not info.success:
                raise AgentError(f"task {task_name} failed inside AGENT")
            yield "result", info.result
            return

        raise AgentError(f"task {task_name} said nothing for {patience}s")
    finally:
        # Cũng chạy khi client ngắt kết nối: browser đi mất thì generator này bị cancel,
        # và một subscription chưa đóng sẽ giữ một connection của pool suốt đời process.
        #
        # Lỗi bị nuốt, vì nếu không, một lần gãy trong lúc dọn dẹp sẽ *thay thế* đúng cái
        # thứ đã sai trước đó. Người gọi chỉ xử lý AgentError và không xử lý gì khác, nên
        # một ConnectionError ném ra ở đây sẽ thoát ra từ một generator đã gửi dòng status
        # của nó đi rồi -- client nhận một stream vỡ và không có lý do nào cho chuyện đó.
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except Exception:  # noqa: BLE001 -- dọn dẹp không được đứng trên lỗi thật
            logger.warning("could not close the stream channel %s", channel, exc_info=True)


def _text(data: object) -> str:
    """Giải mã một mảnh đã được publish.

    Args:
        data: Thứ redis trả về, bytes hoặc str tuỳ theo pool được cấu hình thế nào.

    Returns:
        Mảnh đó dưới dạng text.
    """
    return data.decode() if isinstance(data, bytes) else str(data)


async def enqueue_task(
    pool: ArqRedis | None,
    settings: Settings,
    task_name: str,
    payload: dict,
) -> str | None:
    """Giao cho AGENT một job rồi bỏ đi.

    Ngược với `run_task`: không ai đang chờ câu trả lời, nên ở đây không có gì block và
    không có gì gãy ầm ĩ. Một queue đang chết không được phép chặn một học sinh nộp bài
    của em -- phần việc mà hàm này khởi động là một tối ưu, và con đường không có nó vẫn
    chạy được.

    Args:
        pool: Pool arq đã kết nối, hoặc None khi không tới được queue.
        settings: Settings của process, nơi cung cấp tên queue.
        task_name: Một trong các hằng tên task trong `contracts`.
        payload: Message yêu cầu đã serialise.

    Returns:
        job id để sau này lấy kết quả theo, hoặc None khi job không đẩy được vào queue.

    Side effects:
        Ghi một job lên queue Redis dùng chung.
    """
    if pool is None:
        return None
    try:
        job = await pool.enqueue_job(task_name, payload, _queue_name=settings.agent_queue_name)
    except Exception:  # noqa: BLE001 -- không ai chờ; gãy ở đây chỉ là mất một bước chạy trước
        logger.warning("could not queue %s ahead of time", task_name, exc_info=True)
        return None
    return job.job_id if job is not None else None


async def collect_result(
    pool: ArqRedis | None,
    settings: Settings,
    job_id: str,
) -> tuple[str, object]:
    """Ngó vào một job đã khởi động từ trước.

    Bốn cái kết, và trọng tâm là phân biệt được hai cái cuối. Kết quả của một job sống
    trong Redis `JOB_RESULT_TTL_SECONDS`; hạn của pha 2 có thể cách đó nhiều ngày, nên
    "câu trả lời đã hết hạn" là chuyện bình thường và phản ứng đúng là hỏi lại. Còn một
    job *đã chạy và thất bại* là một chuyện khác: hỏi lại thì vẫn nhận đúng cái thất bại
    đó, và một người gọi không phân biệt được hai thứ này sẽ đẩy lại một job hỏng vào
    queue mỗi lần học sinh mở một màn hình, mãi mãi, và im lặng.

    Args:
        pool: Pool arq đã kết nối, hoặc None khi không tới được queue.
        settings: Settings của process, nơi cung cấp tên queue.
        job_id: Thứ `enqueue_task` đã trả về.

    Returns:
        `("ready", result)` kèm message trả lời; `("pending", None)` trong lúc nó chạy;
        `("gone", None)` khi Redis không còn giữ nó nữa, trường hợp đáng hỏi lại;
        `("failed", None)` khi nó đã chạy và ném lỗi, trường hợp không đáng hỏi lại.
    """
    if pool is None:
        return "pending", None

    job = Job(job_id, redis=pool, _queue_name=settings.agent_queue_name)
    status = await job.status()
    if status is JobStatus.not_found:
        return "gone", None
    if status is not JobStatus.complete:
        return "pending", None

    info = await job.result_info()
    if info is None:
        return "gone", None
    if not info.success:
        return "failed", None
    return "ready", info.result


# BE hỏi lại bao nhiêu lần sau khi từ chối một câu hỏi. Hai, vì mục đích là sống qua
# một model đọc sai brief, không phải tranh luận với một model không làm nổi việc đó --
# và có một học sinh đang chờ ở mỗi lần thử.
#
# Con số đáng biết là cái tích. AGENT retry bên trong một job tối đa LLM_MAX_ATTEMPTS
# lần, còn BE hỏi tối đa 1 + _RETRY_ASKS job, nên một câu hỏi tốn nhiều nhất 3 x 3 = 9
# lần gọi model; một round mở lại N câu sai thì chạy những lần đó tuần tự, nên là 9N.
# Không ai nên phải thấy con số đó, nhưng đó là thứ mà budget phải sống qua được vào
# ngày một model không chịu hợp tác.
_RETRY_ASKS = 2


async def ask_for_retry_question(
    pool: ArqRedis | None,
    settings: Settings,
    ask: RetryQuestionRequested,
    origin_stem: str,
    spent: list[str],
) -> GeneratedQuestion:
    """Lấy câu hỏi của một round, và hỏi lại khi thứ nhận về phạm một luật.

    Lần hỏi lại chở theo stem đã bị từ chối trong `previous_stems`. Gửi lại đúng payload
    cũ là để một câu trả lời khác cho sự may rủi; nói rõ cái gì sai ở lần trước mới là
    khác biệt giữa một lần retry và một lần đổ lại xúc xắc.

    ADR-18 và ADR-17 được kiểm ở đây chứ không kiểm bên trong AGENT, vì một bộ sinh tự
    chấp nhận việc của chính nó là tự chấm bài của mình. AGENT vẫn tự kiểm hình dạng của
    nó trước khi trả lời -- việc đó tiết kiệm một lượt đi về, và đây vẫn là lần kiểm có
    giá trị.

    Args:
        pool: Pool arq đã kết nối, hoặc None khi không tới được queue.
        settings: Settings của process.
        ask: Yêu cầu, mà hàm này sao lại và sửa thêm giữa các lần thử.
        origin_stem: Câu hỏi pha 1 đang được remediation.
        spent: Những stem đã dùng ở các round trước của câu hỏi này.

    Returns:
        Một câu hỏi thoả cả hai luật.

    Raises:
        AgentError: Nếu mọi lần thử đều phạm một luật, hoặc queue thất bại.

    Side effects:
        Ghi tối đa ba job lên queue.
    """
    rejected: list[str] = []
    last: AgentError | None = None

    for attempt in range(1 + _RETRY_ASKS):
        payload = ask.model_copy(
            update={"previous_stems": (*ask.previous_stems, *rejected)}
        ).model_dump(mode="json")

        raw = await run_task(pool, settings, GENERATE_RETRY_QUESTION_TASK, payload)
        question = RetryQuestionCompleted.model_validate(raw).question

        try:
            validate_question(question)
            # `rejected` cố ý nằm ngoài chuyện này. Những stem đó bị từ chối vì hình
            # dạng của chúng và chưa học sinh nào từng thấy chúng, nên một model sửa
            # đúng hình dạng mà giữ nguyên câu chữ thì đã viết ra một câu hỏi hoàn toàn
            # tốt. Coi bản nháp bị loại của chính nó là "đã dùng rồi" sẽ là từ chối
            # đúng cái sửa mà ta vừa yêu cầu.
            validate_retry(question, origin_stem, spent)
        except AgentError as exc:
            logger.warning("rejected round question on attempt %d: %s", attempt + 1, exc)
            last = exc
            rejected.append(question.stem)
            continue

        return question

    # Lời phàn nàn cuối cùng đi kèm theo lời từ chối. Không có nó, 503 chỉ nói rằng ba
    # lần thử đều thất bại, và điều đó chẳng cho người đọc log biết gì về luật nào đã bị
    # phạm -- mà cái luật mới là toàn bộ lý do ta từ chối.
    raise AgentError(f"{1 + _RETRY_ASKS} lần thử đều không đạt — {last}")


def validate_question(question: GeneratedQuestion) -> None:
    """Kiểm một câu hỏi được sinh ra theo ADR-18 trước khi nó được lưu.

    Args:
        question: Thứ AGENT đã tạo ra.

    Raises:
        AgentError: Nếu câu hỏi có số phương án đúng khác đúng một, có một Distractor
            không có error label, hoặc có ít hơn hai lời giải chi tiết.
    """
    correct = [option for option in question.options if option.is_correct]
    if len(correct) != 1:
        raise AgentError(
            f"a question must have exactly one correct option, got {len(correct)}: {question.stem}"
        )

    unmapped = [
        option.label
        for option in question.options
        if not option.is_correct and not option.error_label
    ]
    if unmapped:
        raise AgentError(f"distractors {unmapped} carry no error label: {question.stem}")

    if len(question.methods) < 2:
        raise AgentError(f"a question needs more than one worked solution: {question.stem}")


def validate_retry(question: GeneratedQuestion, origin_stem: str, spent: list[str]) -> None:
    """Kiểm rằng câu hỏi retry là một câu hỏi mới, không phải câu cũ lặp lại.

    ADR-17 nói rõ một lần retry để làm gì: nó kiểm xem học sinh đã sửa được lỗi chưa,
    không kiểm xem em có nhớ đáp án hay không. Một round đưa lại đúng stem cũ là đang
    kiểm trí nhớ, và đó chính là cái sai mà cả cái trần ba round tồn tại để tránh.

    Args:
        question: Thứ AGENT đã tạo ra cho round này.
        origin_stem: Câu hỏi pha 1 đang được remediation.
        spent: Những stem đã dùng ở các round trước của câu hỏi này.

    Raises:
        AgentError: Nếu stem lặp lại câu gốc hoặc lặp lại bất kỳ round trước đó.
    """
    normalise = " ".join(question.stem.split())
    if normalise == " ".join(origin_stem.split()):
        raise AgentError(f"a retry question repeats the question it replaces: {question.stem}")
    if normalise in {" ".join(stem.split()) for stem in spent}:
        raise AgentError(f"a retry question repeats an earlier round: {question.stem}")
