"""Tài liệu của giáo viên: tải lên, và liệt kê.

**Giới hạn của vòng này phải nói ngay, vì nhìn vào màn hình thì không thấy.** Tải lên được,
liệt kê được, hiện trên rail được, đính vào ô soạn được. Thứ **chưa** có là việc tài liệu
thật sự giới hạn phạm vi ra đề: nội dung nó chưa đi vào prompt của AGENT ở bất cứ đâu. Đọc
PDF, cắt đoạn, nhồi ngữ cảnh là một phần lớn hơn hẳn, và nó nằm ngoài vòng này. Nên đây mới
là cái vỏ, và `docs/plans/backlog.md` giữ món nợ đó.

Hệ quả thẳng của giới hạn ấy: **không có số trang, không có cờ "đọc được chữ"**. Hai thứ đó
đòi mở file ra đọc. Thiết kế cũ in *"184 trang · đọc được chữ"* trên mỗi chip, và artboard 1
với 2 đã được sửa trong cùng đợt này để in **kích thước** -- con số duy nhất biết được mà
không cần parse. Một con số trang bịa ra thì tệ hơn hẳn việc không có nó: giáo viên sẽ tin.

Quyền sở hữu như mọi thứ khác (ADR-22): danh sách tìm qua `teacher_id`, nên không có id nào
một caller truyền vào để với tới tài liệu của người khác.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from be.db import get_session
from be.identity import current_teacher
from be.models import Document, Teacher, aware

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["teacher-documents"])

# Mười megabyte. Byte nằm trong database ở vòng này (xem `models.Document`), nên một file
# lớn không chỉ tốn đĩa mà còn đi qua một INSERT và một lần đọc nguyên khối. Một sách giáo
# khoa PDF thường dưới mức này; thứ trên mức này gần như luôn là một lần chọn nhầm file.
_MAX_BYTES = 10 * 1024 * 1024

# Những đuôi file mà "tài liệu để ra đề" có nghĩa. Lọc theo **đuôi tên** chứ không theo
# content-type trình duyệt gửi lên: content-type do client khai, còn đuôi thì nằm trong cái
# tên mà chính giáo viên nhìn thấy trên rail -- hai thứ lệch nhau thì thứ người ta đọc được
# là thứ đáng tin hơn.
_ALLOWED = (".pdf", ".docx", ".doc", ".txt", ".md")


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
) -> DocumentRead:
    """Nhận một file và cất nó vào thư viện của giáo viên.

    Kích thước đo **sau khi đọc**, không lấy từ header `content-length`: header là lời khai
    của client, còn độ dài của chuỗi byte vừa nhận thì là sự thật. Mà con số này về sau sẽ
    hiện trên chip, nên một lời khai sai sẽ nằm lại trên màn hình.

    Args:
        file: File tải lên.
        teacher: Được resolve từ header actor (ADR-13).
        session: Session của database.

    Returns:
        Tài liệu vừa cất, đúng hình dạng mà danh sách trả về.

    Raises:
        HTTPException: 400 khi file rỗng hoặc đuôi không nhận; 413 khi quá lớn.
    """
    filename = (file.filename or "").strip()
    if _kind(filename) == "" or not filename.lower().endswith(_ALLOWED):
        raise HTTPException(
            status_code=400,
            detail="Chỉ nhận tài liệu PDF, Word, hoặc văn bản thuần.",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File này rỗng.")
    if len(content) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File lớn hơn {_MAX_BYTES // (1024 * 1024)} MB.",
        )

    row = Document(
        teacher_id=teacher.id,
        filename=filename,
        content_type=file.content_type or "",
        byte_size=len(content),
        content=content,
        uploaded_at=datetime.now(UTC),
    )
    session.add(row)
    await session.commit()
    logger.info("document uploaded teacher=%s bytes=%s", teacher.id, len(content))
    return _as_read(row)
