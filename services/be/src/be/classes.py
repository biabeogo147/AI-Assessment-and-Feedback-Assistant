"""Tạo lớp (plan `tao-lop`, hậu ký ADR-13 ngày 27/10/2026).

Một hàm, hai cửa: nút *Tạo lớp* của màn 9 (`POST /api/teacher/classes`) và tool ghi
`create_class` của Kriky (`teacher_tools`). Luật tên chỉ sống ở `create_class`, nên hai cửa không
thể lệch nhau.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from be.db import get_session
from be.identity import Asking, current_teacher
from be.resolve import normalise, tidy_name
from schema.models import SchoolClass, Teacher

router = APIRouter(prefix="/api", tags=["teacher-classes"])

#: Cột `classes.name` là `String(64)`.
MOST_NAME_CHARS = 64


class ClassRefused(Exception):
    """Tên lớp không dùng được: rỗng, quá dài, hay trùng một lớp của chính giáo viên ấy.

    Attributes:
        said: Câu cho giáo viên, in nguyên văn ở hộp tạo lớp và dòng bước của Kriky.
        duplicate: True khi lý do là trùng tên.
    """

    def __init__(self, said: str, *, duplicate: bool = False) -> None:
        super().__init__(said)
        self.said = said
        self.duplicate = duplicate


async def create_class(session: AsyncSession, asking: Asking, raw_name: str) -> SchoolClass:
    """Mở một lớp rỗng cho giáo viên đang hỏi.

    Trùng tên so bằng `resolve.normalise`, đúng phép so `list_class` dùng để tìm lớp: hai lớp đã qua
    cổng này không bao giờ làm Kriky phải hỏi lại *"lớp nào"* chỉ vì tên. Chỉ so trong lớp của chính
    giáo viên ấy; hai giáo viên vẫn có thể cùng có *12A*.

    Args:
        session: Session của database.
        asking: Ai đang tạo lớp.
        raw_name: Tên giáo viên gõ.

    Returns:
        Lớp vừa thêm, đã `flush` nên có `id`. Chưa commit: caller commit.

    Raises:
        ClassRefused: Tên rỗng, quá `MOST_NAME_CHARS` ký tự, hay trùng một lớp đã có.
    """
    name = tidy_name(raw_name)
    if not name:
        raise ClassRefused("Tên lớp đang trống.")
    if len(name) > MOST_NAME_CHARS:
        raise ClassRefused(f"Tên lớp dài quá {MOST_NAME_CHARS} ký tự.")
    # Xếp hàng các lần tạo lớp của **cùng** một giáo viên (Postgres; SQLite bỏ qua): bấm *Tạo lớp*
    # hai lần liền thì lần sau thấy lớp lần trước vừa thêm, không cùng qua phép kiểm trùng.
    await session.execute(
        select(Teacher.id).where(Teacher.id == asking.teacher_id).with_for_update()
    )
    mine = await session.scalars(
        select(SchoolClass.name).where(SchoolClass.teacher_id == asking.teacher_id)
    )
    wanted = normalise(name)
    for existing in mine:
        if normalise(existing) == wanted:
            raise ClassRefused(f'Bạn đã có lớp "{existing}".', duplicate=True)
    created = SchoolClass(teacher_id=asking.teacher_id, name=name)
    session.add(created)
    await session.flush()
    return created


class NewClass(BaseModel):
    """Thân của `POST /api/teacher/classes`. Thiếu `name` thì là tên rỗng: lời 422 vẫn là một câu,
    không phải mảng lỗi của Pydantic."""

    name: str = ""


class CreatedClass(BaseModel):
    """Lớp vừa tạo: đủ để màn hình chuyển sang màn 10 của nó."""

    class_id: str
    name: str


@router.post("/teacher/classes", response_model=CreatedClass, status_code=201)
async def post_class(
    body: NewClass,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> CreatedClass:
    """Nút *Tạo lớp* của màn 9.

    Raises:
        HTTPException: 409 khi trùng một lớp của giáo viên này; 422 khi tên rỗng hay quá dài.
            `detail` là câu cho giáo viên, hộp tạo lớp in nguyên văn.
    """
    try:
        created = await create_class(session, Asking.of(teacher), body.name)
    except ClassRefused as refused:
        raise HTTPException(
            status_code=409 if refused.duplicate else 422, detail=refused.said
        ) from refused
    await session.commit()
    return CreatedClass(class_id=created.id, name=created.name)
