"""Tài liệu của giáo viên: tải lên, và liệt kê.

**Giới hạn của vòng này phải nói ngay, vì nhìn vào màn hình thì không thấy.** Tải lên được,
liệt kê được, hiện trên rail được, đính vào ô soạn được. Thứ **chưa** có là việc tài liệu
thật sự giới hạn phạm vi ra đề: nội dung nó chưa đi vào prompt của AGENT ở bất cứ đâu. Đọc
PDF, cắt đoạn, nhồi ngữ cảnh là một phần lớn hơn hẳn, và nó nằm ngoài vòng này. Nên đây mới
là cái vỏ, và `docs/plans/backlog.md` giữ món nợ đó.

Byte **không** nằm trong database nữa: chúng ở MinIO, và `documents.storage_key` là khoá.
Lần chuyển ấy xảy ra vì `services/document` -- service sẽ đọc tệp -- không có credential
database, nên nó không với tới được một cột.

Tệp **được mở ra đọc**, nhưng không ở đây và không trong lời gọi này: đường `POST` cất byte
rồi đẩy một job cho `services/document`, và câu trả lời về sau bằng một job khác mà
`be/worker.py` ghi vào database. Nên một tài liệu vừa tải lên mang trạng thái *đang xử lý*,
và số trang của nó là `None` cho tới khi có người đếm thật.

ADR-27 đòi bốn trạng thái, nhưng chỉ ba trong số đó được **ghi** vào cột. Trạng thái thứ tư --
*xử lý hỏng* vì job đã chết -- được **suy ra lúc đọc**, vì nếu process bị giết thì không ai
còn sống để ghi nó. Xem `_as_read`.

Quyền sở hữu như mọi thứ khác (ADR-22): danh sách tìm qua `teacher_id`, nên không có id nào
một caller truyền vào để với tới tài liệu của người khác.
"""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from be.config import Settings, get_settings
from be.db import get_session
from be.document_events import open_changes
from be.identity import current_teacher
from be.models import Document, Teacher, aware, new_id
from be.queue import enqueue_probe
from be.storage import (
    ObjectStore,
    StorageUnavailable,
    content_type_for,
    document_key,
    get_store,
)
from contracts import DocumentProbeRequested, DocumentState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["teacher-documents"])

# Một trăm megabyte. Con số cũ là mười, và lý do của nó -- "byte nằm trong database, nên một
# file lớn đi qua một INSERT và một lần đọc nguyên khối" -- tan khi byte sang MinIO. Vẫn giữ
# **một** trần, vì một 413 nói ra con số thì tốt hơn một upload treo không hồi kết.
#
# Một trăm là con số **chưa đo**: chưa ai cân một bản SGK scan thật. Nó là một phỏng đoán có
# chủ đích, rộng gấp mười cái cũ.
_MAX_BYTES = 100 * 1024 * 1024

# Những đuôi file mà "tài liệu để ra đề" có nghĩa. Lọc theo **đuôi tên** chứ không theo
# content-type trình duyệt gửi lên: content-type do client khai, còn đuôi thì nằm trong cái
# tên mà chính giáo viên nhìn thấy trên rail -- hai thứ lệch nhau thì thứ người ta đọc được
# là thứ đáng tin hơn.
#
# `.doc` và `.docx` bị gỡ ngày 08/10/2026: PyMuPDF không đọc được cả hai, nên giữ chúng là
# hứa một thứ mà bước xử lý chắc chắn phải từ chối -- và từ chối lúc ấy là từ chối một tệp
# giáo viên tưởng đã cất xong, đúng cái ADR-27 gọi là tệ nhất. `.txt` và `.md` ở lại vì
# chúng không có bài toán text layer: chữ là toàn bộ file.
_ALLOWED = (".pdf", ".txt", ".md")

# Im lặng bao lâu thì phát một nhịp tim. Một kênh SSE không nói gì suốt mấy phút là thứ mà
# proxy và load balancer cắt không báo trước; một dòng comment rỗng giữ nó sống mà không
# giả vờ có tin. Mười lăm giây đủ dưới mọi mức idle timeout mặc định tôi biết.
_HEARTBEAT_SECONDS = 15.0


class DocumentRead(BaseModel):
    """Một tài liệu, đủ để vẽ một chip trên rail.

    Attributes:
        document_id: Tài liệu nào.
        filename: Tên file giáo viên đã tải lên, nguyên văn.
        kind: Đuôi file viết hoa (`PDF`, `DOCX`), thứ nhãn vuông bên trái chip in ra.
        byte_size: Kích thước. Màn hình tự đổi sang KB/MB -- định dạng là việc của màn
            hình, còn con số thì không được làm tròn ở đây rồi không ai lấy lại được.
        state: Một trong bốn giá trị của `DocumentState`. Đây là giá trị **đã suy ra**, không
            nhất thiết là giá trị trong cột -- xem `_as_read`.
        page_count: Số trang, hoặc `None` khi con số **không tồn tại** (tệp văn bản thuần)
            hoặc **chưa đo được** (đang xử lý, hoặc xử lý hỏng). Không bao giờ là `0` cho
            một tệp không có khái niệm trang: màn hình sẽ in "0 trang", và giáo viên sẽ tin.
        fault: Vì sao không dùng được, bằng một câu tiếng Việt. Rỗng khi không có gì sai.
            Trạng thái nói *chuyện gì*, câu này nói *vì sao* -- và hai lý do khác nhau cùng
            dẫn tới *không đọc được chữ*: một bản scan, và một PDF không có trang nào.
        uploaded_at: Lúc tải lên, UTC.
    """

    document_id: str
    filename: str
    kind: str
    byte_size: int
    state: str
    page_count: int | None
    fault: str
    uploaded_at: datetime


def _kind(filename: str) -> str:
    """Đuôi file, viết hoa, không có dấu chấm.

    Args:
        filename: Tên file.

    Returns:
        Ví dụ `PDF`. Rỗng khi tên không có đuôi.
    """
    _, _, tail = filename.rpartition(".")
    return tail.upper() if tail and tail != filename else ""


def _as_read(row: Document, stale_after_seconds: int) -> DocumentRead:
    """Đổi một hàng thành thứ màn hình đọc, và suy ra trạng thái đáng tin.

    **Đây là nơi trạng thái thứ tư sinh ra.** Ba trạng thái kia được ghi vào cột bởi
    `be/ingest.py`; *xử lý hỏng* vì job đã chết thì không ai ghi được -- nếu process bị giết
    thì không có ai còn sống để ghi. Nên nó là một **phép so lúc đọc**: một hàng còn đứng ở
    `processing` lâu hơn mức cho phép thì đọc ra `failed`.

    Một phép so thì không chết được, khác một process đi canh những process đã chết. Và cột
    vẫn giữ `processing` -- đó không phải nói dối, vì cột ghi *đã nghe được gì* còn đường đọc
    trả lời *nên tin gì*. Repo này đã có đúng hình dạng ấy cho một luật khác:
    *"Ngưỡng được áp lúc đọc kết quả chứ không lưu kèm"* (`architecture.md`). Hệ quả hợp ý:
    một job về muộn vẫn **thắng**, vì lần đọc sau thấy một giá trị thật trong cột.

    Args:
        row: Hàng trong `documents`.
        stale_after_seconds: Một hàng được đứng ở `processing` bao lâu trước khi bị coi là
            một job đã chết.

    Returns:
        Bản đọc, không mang theo byte nào.
    """
    state = row.state
    fault = row.fault
    if state == DocumentState.PROCESSING:
        waited = (datetime.now(UTC) - aware(row.uploaded_at)).total_seconds()
        if waited > stale_after_seconds:
            state = DocumentState.FAILED.value
            fault = "Xử lý tài liệu này đã dừng giữa đường. Thử tải lại."

    return DocumentRead(
        document_id=row.id,
        filename=row.filename,
        kind=_kind(row.filename),
        byte_size=row.byte_size,
        state=state,
        page_count=row.page_count,
        fault=fault,
        uploaded_at=aware(row.uploaded_at),
    )


@router.get("/teacher/documents", response_model=list[DocumentRead])
async def library(
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> list[DocumentRead]:
    """Thư viện tài liệu của giáo viên đang gọi.

    Mới nhất lên đầu, vì rail dựng để tìm thứ **vừa** tải lên: một người vừa thêm một cuốn
    sách thì việc tiếp theo họ làm là nhắc tới nó.

    Args:
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.
        settings: Nơi cung cấp mức *đứng quá lâu*.

    Returns:
        Mọi tài liệu của giáo viên này, không kèm nội dung.
    """
    rows = await session.scalars(
        select(Document)
        .where(Document.teacher_id == teacher.id)
        .order_by(Document.uploaded_at.desc(), Document.id)
    )
    return [_as_read(row, settings.document_stale_after_seconds) for row in rows]


@router.get("/teacher/documents/stream")
async def watch(
    request: Request,
    teacher: Teacher = Depends(current_teacher),
) -> StreamingResponse:
    """Phát một dòng mỗi lần thư viện của giáo viên này đổi.

    **Kênh chỉ hích, không chở dữ liệu.** Mỗi khung chỉ nói *có gì đó đổi*; trình duyệt nghe
    xong thì gọi lại `GET /api/teacher/documents`. Lý do nằm ở `be/document_events.py`: pub/sub
    của Redis không giữ lịch sử, nên một event chở dữ liệu mà mất đi là một chip sai vĩnh viễn,
    còn một tiếng hích mất đi thì tiếng sau sửa luôn.

    Hệ quả: trình duyệt **vẫn phải** đọc danh sách một lần lúc mở màn hình. Kênh này không bao
    giờ là nguồn đầu tiên.

    Args:
        request: Nơi lấy pool Redis. Đọc qua `getattr` vì test dựng một app rỗng không có
            lifespan, và không có queue thì kênh im lặng chứ không hỏng.
        teacher: Được resolve từ header actor (ADR-13). Nó cũng là **phạm vi** của kênh: một
            giáo viên chỉ nghe được channel của chính mình, nên không có id nào một caller
            truyền vào để nghe trộm thư viện người khác.

    Returns:
        Một `text/event-stream` gồm các khung `data: 1` và những dòng nhịp tim.
    """
    pool = getattr(request.app.state, "queue_pool", None)

    async def frames() -> AsyncIterator[str]:
        async with open_changes(pool, teacher.id) as changes:
            quiet_since = asyncio.get_running_loop().time()
            async for changed in changes:
                if await request.is_disconnected():
                    return
                if changed:
                    quiet_since = asyncio.get_running_loop().time()
                    yield "data: 1\n\n"
                elif asyncio.get_running_loop().time() - quiet_since > _HEARTBEAT_SECONDS:
                    quiet_since = asyncio.get_running_loop().time()
                    # Dòng bắt đầu bằng `:` là comment của SSE: client bỏ qua, proxy thấy có
                    # chữ chạy qua. Nó **không** phải một tiếng hích, nên nó không làm trình
                    # duyệt gọi lại danh sách.
                    yield ": vẫn đang nghe\n\n"

    return StreamingResponse(frames(), media_type="text/event-stream")


@router.post("/teacher/documents", response_model=DocumentRead, status_code=201)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
    store: ObjectStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> DocumentRead:
    """Nhận một file và cất nó vào thư viện của giáo viên.

    Kích thước đo **sau khi đọc**, không lấy từ header `content-length`: header là lời khai
    của client, còn độ dài của chuỗi byte vừa nhận thì là sự thật. Mà con số này về sau sẽ
    hiện trên chip, nên một lời khai sai sẽ nằm lại trên màn hình.

    Args:
        request: Nơi lấy pool arq ra. Đọc qua `getattr` vì test dựng một app rỗng không có
            lifespan, và một queue chết không được phép làm việc cất tệp hỏng theo.
        file: File tải lên.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.
        store: Nơi byte thật sự nằm.
        settings: Nơi cung cấp tên queue và mức *đứng quá lâu*.

    Returns:
        Tài liệu vừa cất, mang trạng thái *đang xử lý* -- hoặc *xử lý hỏng* nếu ngay cả việc
        giao job cũng không xong.

    Raises:
        HTTPException: 400 khi file rỗng hoặc đuôi không nhận; 413 khi quá lớn; 503 khi
            không cất được vào object storage.

    Side effects:
        Một object mới trong MinIO và một hàng mới trong `documents`, **theo đúng thứ tự ấy**,
        rồi một job trên queue của `services/document`.
    """
    filename = (file.filename or "").strip()
    if _kind(filename) == "" or not filename.lower().endswith(_ALLOWED):
        raise HTTPException(
            status_code=400,
            detail="Chỉ nhận tài liệu PDF hoặc văn bản thuần.",
        )

    # Đo bằng `seek`/`tell` chứ không bằng `await file.read()`. Starlette đã đổ phần thân vào
    # một `SpooledTemporaryFile` tràn ra đĩa sau 1 MB, nên đọc hết vào bộ nhớ là tự nạp 100 MB
    # vào RAM cho một việc chỉ cần biết độ dài.
    #
    # Ba dòng này gọi **thẳng**, không qua threadpool: chúng là `lseek`, tốn micro giây, và đẩy
    # chúng vào thread thì mất đúng cái thứ tự đang cần -- mọi lớp kiểm phải xong **trước khi**
    # chạm tới object storage, nếu không một lần từ chối vẫn để lại rác.
    stream = file.file
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)

    if size == 0:
        raise HTTPException(status_code=400, detail="File này rỗng.")
    if size > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File lớn hơn {_MAX_BYTES // (1024 * 1024)} MB.",
        )

    # Object trước, hàng sau. Hai kho không commit cùng nhau nên phải chọn hình dạng hỏng nào
    # rẻ hơn: ngược lại thì còn một hàng trỏ vào hư không -- chip hiện trên rail, giáo viên tin
    # là có. Thế này thì còn một object mồ côi: rác, không ai thấy, dọn được.
    document_id = new_id()
    key = document_key(teacher.id, document_id, filename)
    try:
        await store.put(key, stream, size, content_type_for(filename))
    except StorageUnavailable as broken:
        logger.error("could not store document for teacher=%s: %s", teacher.id, broken)
        raise HTTPException(
            status_code=503,
            detail="Chưa cất được tài liệu. Thử lại sau một lát.",
        ) from broken

    row = Document(
        id=document_id,
        teacher_id=teacher.id,
        filename=filename,
        content_type=file.content_type or "",
        byte_size=size,
        storage_key=key,
        uploaded_at=datetime.now(UTC),
    )
    try:
        session.add(row)
        await session.commit()
    except Exception:
        # Ca phổ biến của "hỏng giữa hai kho" là INSERT đỏ, và nó không đáng phải trả giá bằng
        # rác. Dọn chủ động ở đây để rác chỉ còn là ca process bị giết -- đúng đánh đổi đã
        # chọn, và khoá được log nên nó grep được.
        await store.remove(key)
        logger.exception("insert failed after storing %s; removed the orphan", key)
        raise
    logger.info("document uploaded teacher=%s bytes=%s key=%s", teacher.id, size, key)

    # Giao việc đọc tệp **sau** khi hàng đã commit. Ngược lại thì worker thắng được cuộc đua
    # và đi ghi một hàng chưa tồn tại -- `be/ingest.py` sẽ ghi được không hàng nào rồi bỏ,
    # và tài liệu đứng ở *đang xử lý* mãi mãi dù mọi thứ đều chạy đúng.
    pool = getattr(request.app.state, "queue_pool", None)
    try:
        if pool is None:
            raise OSError("queue pool is not open")
        await enqueue_probe(
            pool,
            settings,
            DocumentProbeRequested(document_id=row.id, storage_key=key, filename=filename),
        )
    except (OSError, RuntimeError) as unreachable:
        # Tệp **vẫn ở lại**: nó đã cất xong, và một lần thử lại về sau cần nó. Thứ đổi là
        # hàng nói thật ngay -- `processing` ở đây là một chip nói dối không bao giờ được sửa,
        # vì không có job nào để mà về muộn.
        logger.error("could not hand %s to the document service: %s", row.id, unreachable)
        row.state = DocumentState.FAILED.value
        row.fault = "Chưa giao được việc xử lý tài liệu. Thử tải lại."
        await session.commit()

    return _as_read(row, settings.document_stale_after_seconds)
