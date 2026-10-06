"""Soạn một bộ câu hỏi: bắn các job đi, thu kết quả về sau.

Hai luật kéo ngược nhau ở đây, và hình dạng của module này chính là thứ thoả mãn
được cả hai.

**Một job một câu hỏi.** `tools/check_contract.py` so
`LLM_TIMEOUT_SECONDS × LLM_MAX_ATTEMPTS` với mức kiên nhẫn của BE dành cho một
job. Phép tính đó đúng cho số lần retry của đúng một câu hỏi và không hơn, nên một
task soạn cả bộ đề trong một job -- thứ mà cái này thay thế -- làm cái check kia
lặng lẽ sai về đúng cái handler tiêu nhiều lượt gọi model nhất.

**Một brief cho mọi job.** Các job chạy độc lập và không thấy được nhau, nên nếu
phần hướng dẫn vẫn còn đổi được trong lúc chúng chạy thì câu 1-4 sẽ đến từ một cách
hiểu về chủ đề và câu 5-10 từ một cách hiểu khác. Đó là loại lỗi mà không ai tìm ra
bằng cách đọc từng câu hỏi một. Vậy nên brief là một row được lưu lại kèm một
version, mỗi job ghi lại version nó được bắn đi dưới đó, và một câu hỏi soạn cho
một brief cũ hơn thì bị **bỏ** chứ không được gộp vào. Đổi brief là mở một vòng
mới; nó không sửa phần việc đang bay.

Không có gì ở đây đứng đợi. Một giáo viên hỏi mười câu thì nhận câu trả lời ngay
và các câu hỏi hiện ra dần khi chúng về -- đúng cái đánh đổi mà phía học sinh chọn
khi nó soạn trước một câu hỏi remediation.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from be.agent_gateway import collect_result, enqueue_task, validate_question
from be.assessment_state import AssessmentState, advance, assert_editable, editable
from be.config import Settings
from be.models import AnswerOption, Assessment, DraftBrief, DraftItem, Method, Question
from contracts import (
    WRITE_DRAFT_QUESTION_TASK,
    DraftQuestionCompleted,
    DraftQuestionRequested,
    GeneratedQuestion,
)

logger = logging.getLogger(__name__)

# Mỗi lần ngó vào channel chờ bao lâu. Ngắn, vì nó chỉ quyết độ trễ giữa lúc chuông tới và
# lúc vòng lặp thấy nó; mức kiên nhẫn thật nằm ở `patience_seconds` của người gọi.
_BELL_WAIT = 0.2

# Contract chặn `of_total` ở năm mươi, và cái ngưỡng đó phải được kiểm tra trước
# job đầu tiên chứ không phải phát hiện ra ở job thứ năm mươi mốt: bắn từng job một
# nghĩa là một brief hỏi sáu mươi câu sẽ đẩy năm mươi job vào queue rồi mới nổ, để
# lại năm mươi lượt gọi model đang chạy mà không có row nào để thu chúng về.
_MOST_QUESTIONS = 50

# Một vị trí được phép tốn bao nhiêu job. Ba, vì hai trong ba cách một câu hỏi bị
# từ chối là do hên xui -- stem trùng nhau do các job chạy song song, model đánh dấu
# hai phương án cùng đúng -- và lần thử thứ ba là chỗ hên xui thôi không còn là cách
# giải thích được nữa.
_MOST_ATTEMPTS = 3

# Những status mà `fire` sẽ nhặt lại. Một vị trí đang `pending` thì đang có job
# chạy, `ready` là đã xong, và `failed` là đã bỏ.
_RETRYABLE = frozenset({"retry"})


def _comparable(stem: str) -> str:
    """Rút một stem về đúng phần làm hai câu hỏi thành cùng một câu hỏi.

    Chỉ khoảng trắng và chữ hoa chữ thường. Có chủ đích **không** dùng
    `be.resolve.normalise`, vì hàm đó viết cho tên lớp: nó cắt chữ "lớp" ở đầu và
    bỏ mọi dấu cách, nên "Lớp 12A có 30 học sinh..." và "12A có 30 học sinh..." sẽ
    so ra bằng nhau -- hai câu hỏi khác nhau bị gọi thành một.

    Hàm này không cần khớp với luật riêng của AGENT, vì các stem mà BE gửi trong
    `banned_stems` đi ở dạng **thô** và AGENT tự normalise chúng bằng hàm của nó khi
    nhận được. Hai hàm normalise mà buộc phải đồng ý với nhau qua một đường biên
    service thì, theo đúng lời docstring của chính AGENT, là một mối bất đồng đã có
    sẵn ngày hẹn.

    Args:
        stem: Một stem câu hỏi theo đúng cách đã lưu.

    Returns:
        Stem đó với các chuỗi khoảng trắng gộp lại làm một, và đã hạ hết về chữ
        thường.
    """
    return " ".join(stem.split()).casefold()


async def _stems(session: AsyncSession, assessment_id: str) -> list[str]:
    """Mọi stem đã có trong đề nháp, theo đúng cách đã lưu."""
    written = await session.scalars(
        select(Question.stem).where(Question.assessment_id == assessment_id)
    )
    return list(written)


def progress_channel(assessment_id: str) -> str:
    """Tên channel mà các job của một đề nháp rung chuông vào.

    Dựng từ chính id của đề chứ không phải một id ngẫu nhiên cho mỗi lượt: người nghe và
    người rung gặp nhau qua **cái đề**, nên một tab mở sau vẫn nghe được tiến độ của một
    vòng soạn bắt đầu từ trước, và hai tab cùng mở thì cùng nghe. Một id phát theo lượt sẽ
    chỉ phục vụ đúng cái request đã đẻ ra nó.

    Args:
        assessment_id: Đề nháp nào.

    Returns:
        Tên channel.
    """
    return f"draft:{assessment_id}"


@asynccontextmanager
async def open_bells(
    pool: object, assessment_id: str, patience_seconds: float
) -> AsyncIterator[AsyncIterator[int]]:
    """Mở tai nghe chuông của một đề nháp; bên trong khối, mỗi tiếng chuông là một số thứ tự.

    **Một context manager, không phải một generator.** Thân một async generator không chạy
    cho tới lần lặp đầu tiên, nên một bản trước đó nhận tham số `start` để giữ đúng thứ tự
    *subscribe rồi mới đẩy job* đã im lặng không chạy `start` lần nào khi chưa có chuông nào
    để lặp — và đường sản xuất mất trọn vòng soạn đầu tiên. Ở đây việc subscribe xảy ra tại
    `__aenter__`, nên câu "mở tai trước đã" là một tính chất của cú pháp, không phải một lời
    dặn: thứ nằm trong `async with` chắc chắn chạy sau nó.

    Vì sao thứ tự ấy quan trọng: pub/sub của Redis **không giữ lịch sử**. Job chạy xong trước
    khi ai subscribe thì tiếng chuông rơi vào một căn phòng trống — và trên máy dev không có
    API key, một câu "soạn xong" trong vài micro-giây.

    Chuông **không phải một bộ đếm**: một vị trí thử lại rung thêm một lần cho cùng số thứ
    tự, và một tiếng chuông có thể mất. Số câu đã soạn phải đếm từ database.

    Args:
        pool: Pool arq đã kết nối, hoặc None khi không tới được queue.
        assessment_id: Đề nháp nào.
        patience_seconds: Im lặng bao lâu thì thôi nghe. Đồng hồ đặt lại sau mỗi tiếng
            chuông, nên đây là hạn cho **sự im lặng**, không phải trần cho cả khoảng đợi.

    Yields:
        Một iterator các số thứ tự, theo đúng thứ tự chuông tới.

    Side effects:
        Subscribe một channel Redis khi vào, huỷ đăng ký khi ra.
    """
    opener = getattr(pool, "pubsub", None)
    if pool is None or opener is None:
        # Không có queue, hoặc một pool không nói pub/sub được: cả hai nghĩa là không có
        # tiếng chuông nào, và không có tiếng chuông thì vẫn không mất câu nào — chúng nằm
        # trong result store và vào đề ở lần quan sát kế tiếp.
        yield _no_bells()
        return

    channel = progress_channel(assessment_id)
    pubsub = opener()
    try:
        await pubsub.subscribe(channel)
        yield _bells_from(pubsub, channel, patience_seconds)
    finally:
        # Chạy cả khi người nghe thoát sớm hay bị cancel. Lỗi bị nuốt, vì một lần gãy lúc
        # dọn dẹp sẽ *thay thế* đúng cái thứ đã sai trước đó.
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except Exception:  # noqa: BLE001 -- dọn dẹp không được đứng trên lỗi thật
            logger.warning("could not close the progress channel %s", channel, exc_info=True)


async def _no_bells() -> AsyncIterator[int]:
    """Không có queue thì không có tiếng chuông nào, và đó không phải một lỗi."""
    return
    yield 0  # pragma: no cover -- chỉ để Python coi đây là một async generator


async def _bells_from(pubsub: object, channel: str, patience_seconds: float) -> AsyncIterator[int]:
    """Đọc từng tiếng chuông từ một subscription đã mở.

    Args:
        pubsub: Subscription đã subscribe xong.
        channel: Tên channel, chỉ để log.
        patience_seconds: Im lặng bao lâu thì thôi.

    Yields:
        Số thứ tự của câu vừa viết xong.
    """
    deadline = asyncio.get_running_loop().time() + patience_seconds
    while asyncio.get_running_loop().time() < deadline:
        try:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=_BELL_WAIT)
        except Exception:  # noqa: BLE001 -- xem bên dưới
            # Redis gãy giữa lúc nghe thì thôi nghe, không ném. Hàm này chạy trong cùng một
            # lượt chat với việc soạn đề; một exception thoát ra đây biến một hàng đợi tạm
            # thời không với tới được thành một lượt chat hỏng, trong khi thứ duy nhất mất
            # đi là sự sống động của một khối bước.
            logger.warning("stopped listening on %s", channel, exc_info=True)
            return
        if message is None or message.get("type") != "message":
            continue
        raw = message["data"]
        text = raw.decode() if isinstance(raw, bytes) else str(raw)
        if not text.isdigit():
            # Không làm mới deadline cho một tin rác: nếu không, một publisher nói linh tinh
            # giữ vòng nghe này sống mãi.
            continue
        deadline = asyncio.get_running_loop().time() + patience_seconds
        yield int(text)


async def too_many(session: AsyncSession, assessment_id: str, wanted: int) -> str:
    """Xin thêm `wanted` câu nữa thì tổng có vượt trần không, và nói ra bằng tiếng Việt.

    Tồn tại vì `fire` không nói được. Nó canh **tổng** ở `start + wanted` nhưng chỉ
    `logger.warning` rồi `return 0`, mà caller dịch `queued == 0` thành *"có thể đề chưa
    có brief, hoặc hàng đợi đang hỏng"*. Nên một đề đã có 45 câu, xin thêm 10, nhận một
    lời từ chối nêu một nguyên nhân **không có thật** -- và không chỗ nào nhắc tới con số
    50. Trần của `fire` vẫn ở đó làm chốt cuối; hàm này là chỗ nó có tiếng nói.

    Args:
        session: Session của database.
        assessment_id: Đề nháp nào.
        wanted: Số câu xin thêm lần này.

    Returns:
        Câu từ chối, hoặc chuỗi rỗng khi tổng còn trong trần.
    """
    rows = await session.scalars(
        select(func.max(DraftItem.ordinal)).where(DraftItem.assessment_id == assessment_id)
    )
    start = rows.one_or_none() or 0
    total = start + wanted
    if total <= _MOST_QUESTIONS:
        return ""
    if start:
        return (
            f"đề này đã có {start} câu, thêm {wanted} câu nữa là {total} -- "
            f"một đề nhiều nhất {_MOST_QUESTIONS} câu"
        )
    return f"số câu phải từ 1 đến {_MOST_QUESTIONS}"


async def fire(
    session: AsyncSession,
    pool: object,
    settings: Settings,
    assessment_id: str,
    wanted: int,
) -> int:
    """Đẩy vào queue một job cho mỗi câu hỏi còn thiếu, cộng `wanted` câu mới.

    Một vị trí được đẩy vào queue khi nó chưa có row hoặc row của nó đang là
    `retry`. `pending`, `ready` và `failed` đều được để yên, nên gọi hàm này hai lần
    không làm job vào queue hai lượt, và một vị trí đã bỏ thì vẫn ở trạng thái đã
    bỏ.

    Args:
        session: Session của database. Commit theo từng row.
        pool: Pool của arq, hoặc None khi không với tới được queue.
        settings: Settings của process, cung cấp tên queue.
        assessment_id: Đề nháp nào.
        wanted: Xin **thêm** bao nhiêu câu nữa. Số câu tới từ đây chứ không từ brief:
            một đề trống chưa có số câu nào để khai, và soạn 3 câu rồi soạn thêm 2 là
            chuyện thường. Mức trần được kiểm ở `start_drafting`, nơi giáo viên nói ra
            con số; chỗ này chỉ chặn một lần nữa cho **tổng** sau khi cộng.

    Returns:
        Đã đẩy bao nhiêu job vào queue.

    Raises:
        HTTPException: 409 khi nội dung của đề đã bị khoá (ADR-01).

    Side effects:
        Ghi các job lên queue và một row `DraftItem` cho mỗi job, commit sau từng
        cái một. **Và ghi `brief.question_count` thành tổng mới** — không phải một
        chi tiết: `harvest` đọc đúng con số ấy để biết ô nào đã cũ so với vòng này,
        nên một `fire` không cập nhật nó sẽ làm `harvest` xoá sai row.
    """
    brief = await session.get(DraftBrief, assessment_id)
    if brief is None:
        # Không có brief nghĩa là chưa thống nhất được gì, và một bộ đề mới nêu
        # được nửa yêu cầu thì tốt nhất là đừng soạn.
        logger.warning("nothing queued for %s: no brief", assessment_id)
        return 0

    assessment = await session.get(Assessment, assessment_id)
    if assessment is None:
        logger.warning("nothing queued for %s: no such assessment", assessment_id)
        return 0

    # ADR-01: duyệt thì khoá nội dung, và ghi thêm câu hỏi vào một đề đã duyệt
    # chính là thứ mà cái khoá đó sinh ra để chặn.
    assert_editable(assessment)

    rows = {
        row.ordinal: row
        for row in await session.scalars(
            select(DraftItem).where(DraftItem.assessment_id == assessment_id)
        )
    }

    # **Câu mới nối tiếp câu cũ, không ghi đè.** Ô cao nhất đang có cộng `wanted` là tổng
    # mới; vòng lặp dưới đi từ 1 nên nó vẫn quét qua các ô cũ -- `ready` bị bỏ qua,
    # `retry` được bắn lại, và chỉ các ô từ `start + 1` trở đi là mới.
    start = max(rows, default=0)
    total = start + wanted
    if not 1 <= total <= _MOST_QUESTIONS:
        logger.warning(
            "nothing queued for %s: %d + %d would be %d, allowed 1..%d",
            assessment_id,
            start,
            wanted,
            total,
            _MOST_QUESTIONS,
        )
        return 0

    # Brief mang **tổng**, vì `harvest` dùng nó để biết ô nào đã cũ so với vòng này.
    brief.question_count = total
    banned = tuple(await _stems(session, assessment_id))
    now = datetime.now(UTC)
    queued = 0

    for ordinal in range(1, total + 1):
        row = rows.get(ordinal)
        if row is not None and row.status not in _RETRYABLE:
            continue

        asked = DraftQuestionRequested(
            request_id=f"{assessment_id}:{ordinal}:{brief.version}",
            subject=assessment.subject,
            grade=assessment.grade,
            topic_scope=brief.topic_scope,
            difficulty=brief.difficulty,
            ordinal=ordinal,
            of_total=total,
            banned_stems=banned,
            progress_channel=progress_channel(assessment_id),
        )
        job_id = await enqueue_task(
            pool, settings, WRITE_DRAFT_QUESTION_TASK, asked.model_dump(mode="json")
        )
        if job_id is None:
            # Queue đang chết. Không ghi row nào, nên lần gọi sau sẽ thử lại.
            continue

        if row is None:
            session.add(
                DraftItem(
                    assessment_id=assessment_id,
                    ordinal=ordinal,
                    job_id=job_id,
                    status="pending",
                    attempts=1,
                    brief_version=brief.version,
                    created_at=now,
                )
            )
        else:
            row.job_id = job_id
            row.status = "pending"
            row.attempts += 1
            row.brief_version = brief.version

        try:
            # Commit theo từng row, theo đúng `_write_ahead` ở phía học sinh: hai
            # caller đều có thể lọt qua cái check phía trên, và bên thua ở unique
            # index không được phép kéo theo những job đã đang chạy chết cùng.
            await session.commit()
        except IntegrityError:
            await session.rollback()
            logger.info("position %d of %s was taken by another caller", ordinal, assessment_id)
            continue
        queued += 1

    logger.info("queued %d question(s) for draft %s", queued, assessment_id)
    return queued


async def rebrief(
    session: AsyncSession,
    assessment_id: str,
    *,
    topic_scope: str,
    question_count: int,
    difficulty: str = "",
) -> int:
    """Thay brief, mở một vòng sinh câu hỏi mới.

    Tăng version lên chính là thứ bỏ đi phần việc đang bay: một job đã bắn đi dưới
    brief cũ vẫn chạy xong và vẫn trả về một câu hỏi, và `harvest` bỏ nó đi chứ
    không để nó nằm chung một đề với những câu hỏi soạn theo hướng dẫn khác.

    Args:
        session: Session của database. Hàm này tự commit.
        assessment_id: Đề nháp nào.
        topic_scope: Phạm vi mới, theo lời giáo viên.
        question_count: Giờ bộ đề nên có bao nhiêu câu hỏi.
        difficulty: Khó đến đâu, theo lời giáo viên.

    Returns:
        Số version mới.

    Side effects:
        Ghi mới hoặc ghi đè row brief rồi commit.
    """
    brief = await session.get(DraftBrief, assessment_id)
    now = datetime.now(UTC)

    if brief is None:
        brief = DraftBrief(
            assessment_id=assessment_id,
            topic_scope=topic_scope,
            difficulty=difficulty,
            question_count=question_count,
            version=1,
            created_at=now,
        )
        session.add(brief)
    else:
        brief.topic_scope = topic_scope
        brief.difficulty = difficulty
        brief.question_count = question_count
        brief.version += 1

    version = brief.version
    await session.commit()
    logger.info("draft %s is now on brief version %d", assessment_id, version)
    return version


async def _write(
    session: AsyncSession, assessment_id: str, order_index: int, question: GeneratedQuestion
) -> None:
    """Lưu một câu hỏi cùng các phương án và các lời giải của nó.

    Args:
        session: Session của database. Không commit ở đây.
        assessment_id: Đề nháp nào.
        order_index: Số thứ tự câu hỏi mang trên đề, tức là vị trí giáo viên đã
            yêu cầu, chứ không phải thứ tự nó về tới.
        question: Câu hỏi đã qua validate.

    Side effects:
        Thêm một `Question` cùng các row `AnswerOption` và `Method` của nó.
    """
    stored = Question(
        assessment_id=assessment_id,
        order_index=order_index,
        stem=question.stem,
        learning_objective=question.learning_objective,
    )
    session.add(stored)
    await session.flush()

    for option in question.options:
        session.add(
            AnswerOption(
                question_id=stored.id,
                label=option.label,
                text=option.text,
                is_correct=option.is_correct,
                error_label=option.error_label,
            )
        )
    for index, method in enumerate(question.methods, start=1):
        session.add(
            Method(
                question_id=stored.id,
                order_index=index,
                title=method.title,
                body=method.body,
            )
        )


def _give_up_or_retry(row: DraftItem, why: str) -> None:
    """Đánh dấu một vị trí để thử lại, hoặc thôi không tiêu thêm vào nó nữa.

    Args:
        row: Item mà job của nó không cho ra thứ gì dùng được.
        why: Chuyện gì đã sai, để ghi log.

    Side effects:
        Ghi `row.status`.
    """
    row.last_fault = why[:120]
    if row.attempts >= _MOST_ATTEMPTS:
        row.status = "failed"
        logger.warning(
            "position %d of %s gave up after %d attempt(s): %s",
            row.ordinal,
            row.assessment_id,
            row.attempts,
            why,
        )
        return
    row.status = "retry"
    logger.info("position %d of %s will be asked again: %s", row.ordinal, row.assessment_id, why)


async def harvest(
    session: AsyncSession, pool: object, settings: Settings, assessment_id: str
) -> int:
    """Đưa các job đã xong vào đề nháp, và quyết định làm gì với phần còn lại.

    Được gọi từ mọi chỗ đọc đề nháp, vì BE không có worker chạy nền và một kết quả
    không ai đi thu thì là một kết quả sẽ hết hạn.

    **Mọi thứ đều được kiểm ở đây, ngay trên đường vào.** AGENT có kiểm output của
    chính nó và có fallback sang nội dung soạn trước, nhưng đây mới là cái check có
    giá trị: đề nháp là thứ giáo viên duyệt và học sinh làm, nên một câu hỏi phá
    ADR-18 thì phải bị chặn ở cửa này, hoặc không bị chặn ở đâu cả. Hai job trả về
    cùng một stem là chuyện thường tình chứ không phải một bug -- không có gì điều
    phối chúng -- và một đề có một câu hỏi hai lần thì tệ hơn một đề thiếu đi một
    câu.

    Một câu hỏi soạn cho một brief cũ hơn cũng bị bỏ ở đây. Đó là cơ chế đứng sau
    câu "đổi brief là mở một vòng mới": job cũ vẫn chạy xong, câu trả lời của nó vẫn
    về tới, và nó vẫn không vào được đề này.

    Args:
        session: Session của database. Hàm này tự commit.
        pool: Pool của arq, hoặc None.
        settings: Settings của process.
        assessment_id: Đề nháp nào.

    Returns:
        Lần gọi này có bao nhiêu câu hỏi đã vào được đề nháp.

    Side effects:
        Ghi các câu hỏi, đánh dấu hoặc xoá các row, và đưa đề ra khỏi `EMPTY` ngay
        khi câu hỏi đầu tiên về tới.
    """
    brief = await session.get(DraftBrief, assessment_id)
    waiting = list(
        await session.scalars(
            select(DraftItem).where(
                DraftItem.assessment_id == assessment_id, DraftItem.status == "pending"
            )
        )
    )
    if not waiting or brief is None:
        return 0

    # Nội dung đã khoá thì không ghi gì, kể cả một câu hỏi đã viết xong đang nằm chờ.
    # `fire` kiểm điều này lúc bắn job, nhưng giữa lúc bắn và lúc thu có một khoảng, và
    # trong khoảng đó giáo viên bấm Duyệt được -- nên phép kiểm lúc bắn không đủ. Thiếu
    # chỗ này thì `harvest` là một đường ghi `Question` đi vòng qua `assert_editable`, và
    # câu lọt vào là câu giáo viên **chưa từng thấy** trong một đề họ đã nhận trách
    # nhiệm: đúng cái hại mà ADR-01 khoá nội dung để chặn. Đo được trước khi sửa: một
    # request trả 409 trong khi số câu hỏi của đề đi từ 1 lên 2.
    assessment = await session.get(Assessment, assessment_id)
    if assessment is None or not editable(assessment):
        logger.info("skipping harvest of %s: content is locked", assessment_id)
        return 0

    seen = {_comparable(stem) for stem in await _stems(session, assessment_id)}
    taken = set(
        await session.scalars(
            select(Question.order_index).where(Question.assessment_id == assessment_id)
        )
    )
    landed = 0

    for row in sorted(waiting, key=lambda item: item.ordinal):
        if row.brief_version != brief.version or row.ordinal > brief.question_count:
            # Soạn theo hướng dẫn giờ không còn áp dụng nữa, hoặc soạn cho một vị
            # trí mà một brief ngắn hơn giờ không còn. Xoá đi chứ không đánh dấu,
            # để phần sổ sách của vòng cũ không đi theo vòng mới.
            logger.info("dropping stale position %d of %s", row.ordinal, assessment_id)
            await session.delete(row)
            continue

        state, raw = await collect_result(pool, settings, row.job_id)
        if state == "pending":
            continue
        if state == "gone":
            # Chuyện thường, không phải ngoại lệ: kết quả sống một tiếng và giáo
            # viên có thể mai mới quay lại. Thử lại được, và có chặn như mọi thứ
            # khác.
            _give_up_or_retry(row, "kết quả đã hết hạn trong Redis")
            continue
        if state == "failed":
            # Chính cái job đã nổ. Hỏi lại thì vẫn nhận đúng cái lỗi đó, nên lần
            # này không đi qua bộ đếm số lần thử.
            row.status = "failed"
            logger.warning("job for position %d of %s raised", row.ordinal, assessment_id)
            continue

        try:
            question = DraftQuestionCompleted.model_validate(raw).question
            validate_question(question)
        except Exception:
            _give_up_or_retry(row, "câu trả về sai hình dạng ADR-18")
            continue

        if _comparable(question.stem) in seen:
            _give_up_or_retry(row, "đề trùng một câu đã có")
            continue

        if row.ordinal in taken:
            # Vị trí này đã có một câu hỏi, nghĩa là có một job trùng cho cùng một
            # ordinal đã lọt qua. Giữ cái đầu tiên và dừng.
            _give_up_or_retry(row, "vị trí này đã có câu")
            continue

        # Vị trí giáo viên đã yêu cầu, không phải thứ tự nó về tới. Các job xong
        # theo đúng thứ tự model trả lời, nên đánh số bằng một biến đếm chạy dần
        # sẽ xếp các câu hỏi lên đề theo thứ tự về tới -- một giáo viên yêu cầu 1,
        # 2, 3 thì nhận 2, 3, 1, và không có constraint nào trên đường để nó vướng
        # vào.
        await _write(session, assessment_id, row.ordinal, question)
        seen.add(_comparable(question.stem))
        taken.add(row.ordinal)
        row.status = "ready"
        landed += 1

    if landed:
        assessment = await session.get(Assessment, assessment_id)
        if assessment is not None and AssessmentState(assessment.state) is AssessmentState.EMPTY:
            # Đi qua cái cửa duy nhất, vì state empty của ADR-01 chính là thứ chặn
            # việc phát hành, và cái lúc nó thôi đúng là một sự kiện trong vòng đời
            # chứ không phải một phép gán.
            advance(assessment, AssessmentState.HAS_QUESTIONS)

    # **Bắn lại ngay những ô vừa đánh `retry`.** Trước đợt này `fire` chỉ được gọi từ
    # `start_drafting`, nên một ô `retry` nằm im cho tới khi giáo viên nhờ lần nữa — và
    # cái tên `retry` nói ngược điều đó. Đo được ngày 06/10/2026: giáo viên xin 3 câu,
    # hai job song song viết ra cùng một stem, ô thứ hai thành `retry`, và đề đứng ở 2/3
    # vĩnh viễn.
    #
    # Bắn lại **ở đây** chứ không ở `fire` là có lý do: lúc này `seen` đã có câu vừa ghi,
    # nên `banned` của lần hai chứa nó và model tránh được. Bắn lại ở `fire` thì nó vẫn
    # cầm đúng danh sách rỗng đã gây ra trùng lặp.
    again = [row for row in waiting if row.status in _RETRYABLE]

    try:
        if again:
            # Commit **trước** khi bắn lại, vì `_refire` đọc `banned` từ database: câu vừa
            # ghi phải nằm ở đó rồi, không thì lần hai vẫn cầm đúng danh sách đã gây trùng.
            #
            # Và commit ấy nằm **trong** cùng một khối `try` với commit cuối, không ngoài.
            # Nó ở ngoài một lần, và đó là một lỗ: khi có ít nhất một ô `retry` thì mọi
            # thứ `harvest` vừa ghi được commit ở đây, ngoài lưới -- nên một tab thứ hai
            # nhanh tay hơn làm cả lượt chat 500, đúng cái mà `except` dưới đây được viết
            # ra để chặn. Đợt này còn làm nhánh `retry` thành đường hay đi nhất.
            await session.commit()
            await _refire(session, pool, settings, assessment_id, again)
        await session.commit()
    except IntegrityError:
        # Hai người thu cùng một lúc. Trước chuông tiến độ đây là một trùng hợp hiếm; nay
        # mỗi tiếng chuông đánh thức **mọi** tab đang mở cùng một đề, nên nó là chuyện
        # thường ngày. `Question` có unique trên (đề, vị trí), nên bên thua cuộc vướng vào
        # đó — và bên thua không có gì để làm: câu hỏi đã nằm trong đề, do bên kia ghi.
        #
        # Cùng cách `fire` xử một cuộc đua ở cùng chỗ: rollback, nói ra, và trả về 0 chứ
        # không ném. Một lượt chat không được hỏng vì một tab thứ hai nhanh tay hơn.
        await session.rollback()
        logger.info("another reader harvested %s first", assessment_id)
        return 0
    return landed


async def _refire(
    session: AsyncSession,
    pool: object,
    settings: Settings,
    assessment_id: str,
    rows: list[DraftItem],
) -> None:
    """Bắn lại job cho những ô vừa bị đánh `retry`, với `banned` đã cập nhật.

    Tách khỏi `fire` vì nó trả lời một câu hỏi khác: `fire` hỏi *đề này còn thiếu ô nào*,
    hàm này hỏi *ô này vừa hỏng, thử lại ngay được không*. Và nó đọc `banned` **lại từ
    đầu**, sau khi `harvest` vừa ghi xong — đó là toàn bộ điểm của việc bắn lại ở đây:
    lần hai biết câu nào vừa vào đề, nên nó tránh được.

    Hết `attempts` thì `_give_up_or_retry` đã đánh `failed` rồi, nên danh sách tới đây chỉ
    còn những ô thật sự đáng thử lại.

    Args:
        session: Session của database.
        pool: Pool của arq, hoặc None khi queue không với tới được.
        settings: Settings của process.
        assessment_id: Đề nháp nào.
        rows: Các ô đang ở `retry`.

    Side effects:
        Ghi job lên queue và đổi `job_id` cùng `status` của từng row.
    """
    brief = await session.get(DraftBrief, assessment_id)
    assessment = await session.get(Assessment, assessment_id)
    if brief is None or assessment is None:
        return

    banned = tuple(await _stems(session, assessment_id))
    for row in rows:
        asked = DraftQuestionRequested(
            request_id=f"{assessment_id}:{row.ordinal}:{brief.version}:{row.attempts}",
            subject=assessment.subject,
            grade=assessment.grade,
            topic_scope=brief.topic_scope,
            difficulty=brief.difficulty,
            ordinal=row.ordinal,
            of_total=brief.question_count,
            banned_stems=banned,
            progress_channel=progress_channel(assessment_id),
        )
        job_id = await enqueue_task(
            pool, settings, WRITE_DRAFT_QUESTION_TASK, asked.model_dump(mode="json")
        )
        if job_id is None:
            # Queue đang chết. Để nguyên ở `retry` **và không tiêu một lượt thử**: lần
            # `fire` sau vẫn nhặt được nó, và nó vẫn còn đủ `_MOST_ATTEMPTS` lần. Tăng
            # `attempts` trước khi biết job có đi được hay không làm một ô đáng ba lượt
            # chỉ còn hai -- Redis chết một nhịp lấy đi một lượt mà model chưa hề chạy.
            continue
        row.job_id = job_id
        row.status = "pending"
        row.attempts += 1
        logger.info(
            "position %d of %s asked again (attempt %d): %s",
            row.ordinal,
            assessment_id,
            row.attempts,
            row.last_fault,
        )


async def pending_count(session: AsyncSession, assessment_id: str) -> int:
    """Còn bao nhiêu vị trí đang có job chạy.

    Duyệt một đề nháp khi các câu hỏi còn đang được soạn là duyệt một đề mà giáo
    viên chưa xem, nên endpoint duyệt hỏi câu này trước.

    Args:
        session: Session của database.
        assessment_id: Đề nháp nào.

    Returns:
        Số vị trí đang ở `pending`.
    """
    return (
        await session.scalar(
            select(func.count())
            .select_from(DraftItem)
            .where(DraftItem.assessment_id == assessment_id, DraftItem.status == "pending")
        )
        or 0
    )
