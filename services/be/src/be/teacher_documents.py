"""Tài liệu của giáo viên: tải lên, và liệt kê.

**Giới hạn của vòng này phải nói ngay, vì nhìn vào màn hình thì không thấy.** Tải lên được,
liệt kê được, hiện trên rail được, đính vào ô soạn được. Thứ **chưa** có là việc tài liệu
thật sự giới hạn phạm vi ra đề: nội dung nó chưa đi vào prompt của AGENT ở bất cứ đâu. Đọc
PDF, cắt đoạn, nhồi ngữ cảnh là một phần lớn hơn hẳn, và nó nằm ngoài vòng này. Nên đây mới
là cái vỏ, và `docs/plans/backlog.md` giữ món nợ đó.

Byte **không** nằm trong database nữa: chúng ở MinIO, và `documents.storage_key` là khoá.
Lần chuyển ấy xảy ra vì `services/document` -- service sẽ đọc tệp -- không có credential
database, nên nó không với tới được một cột.

Hệ quả thẳng của giới hạn ấy: **không có số trang, không có cờ "đọc được chữ"**. Hai thứ đó
đòi mở file ra đọc. Thiết kế cũ in *"184 trang · đọc được chữ"* trên mỗi chip, và artboard 1
với 2 đã được sửa trong cùng đợt này để in **kích thước** -- con số duy nhất biết được mà
không cần parse. Một con số trang bịa ra thì tệ hơn hẳn việc không có nó: giáo viên sẽ tin.

Quyền sở hữu như mọi thứ khác (ADR-22): danh sách tìm qua `teacher_id`, nên không có id nào
một caller truyền vào để với tới tài liệu của người khác.
"""

import logging
import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from be.db import get_session
from be.identity import current_teacher
from be.models import Document, Teacher, aware, new_id
from be.storage import (
    ObjectStore,
    StorageUnavailable,
    content_type_for,
    document_key,
    get_store,
)

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


class DocumentRead(BaseModel):
    """Một tài liệu, đủ để vẽ một chip trên rail.

    Attributes:
        document_id: Tài liệu nào.
        filename: Tên file giáo viên đã tải lên, nguyên văn.
        kind: Đuôi file viết hoa (`PDF`, `DOCX`), thứ nhãn vuông bên trái chip in ra.
        byte_size: Kích thước. Màn hình tự đổi sang KB/MB -- định dạng là việc của màn
            hình, còn con số thì không được làm tròn ở đây rồi không ai lấy lại được.
        uploaded_at: Lúc tải lên, UTC.
    """

    document_id: str
    filename: str
    kind: str
    byte_size: int
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


def _as_read(row: Document) -> DocumentRead:
    """Đổi một hàng thành thứ màn hình đọc.

    Args:
        row: Hàng trong `documents`.

    Returns:
        Bản đọc, không mang theo byte nào.
    """
    return DocumentRead(
        document_id=row.id,
        filename=row.filename,
        kind=_kind(row.filename),
        byte_size=row.byte_size,
        uploaded_at=aware(row.uploaded_at),
    )


@router.get("/teacher/documents", response_model=list[DocumentRead])
async def library(
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentRead]:
    """Thư viện tài liệu của giáo viên đang gọi.

    Mới nhất lên đầu, vì rail dựng để tìm thứ **vừa** tải lên: một người vừa thêm một cuốn
    sách thì việc tiếp theo họ làm là nhắc tới nó.

    Args:
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        Mọi tài liệu của giáo viên này, không kèm nội dung.
    """
    rows = await session.scalars(
        select(Document)
        .where(Document.teacher_id == teacher.id)
        .order_by(Document.uploaded_at.desc(), Document.id)
    )
    return [_as_read(row) for row in rows]


@router.post("/teacher/documents", response_model=DocumentRead, status_code=201)
async def upload(
    file: UploadFile = File(...),
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
    store: ObjectStore = Depends(get_store),
) -> DocumentRead:
    """Nhận một file và cất nó vào thư viện của giáo viên.

    Kích thước đo **sau khi đọc**, không lấy từ header `content-length`: header là lời khai
    của client, còn độ dài của chuỗi byte vừa nhận thì là sự thật. Mà con số này về sau sẽ
    hiện trên chip, nên một lời khai sai sẽ nằm lại trên màn hình.

    Args:
        file: File tải lên.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.
        store: Nơi byte thật sự nằm.

    Returns:
        Tài liệu vừa cất, đúng hình dạng mà danh sách trả về.

    Raises:
        HTTPException: 400 khi file rỗng hoặc đuôi không nhận; 413 khi quá lớn; 503 khi
            không cất được vào object storage.

    Side effects:
        Một object mới trong MinIO và một hàng mới trong `documents`, **theo đúng thứ tự ấy**.
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
    return _as_read(row)
