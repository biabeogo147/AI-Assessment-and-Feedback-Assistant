"""Tạo lớp và xoá lớp rỗng (plan `tao-lop`, plan `erase-empty-class`, hậu ký ADR-13 27/10/2026).

Tạo lớp: một hàm, hai cửa: nút *Tạo lớp* của màn 9 (`POST /api/teacher/classes`) và tool ghi
`create_class` của Kriky (`teacher_tools`). Luật tên chỉ sống ở `create_class`, nên hai cửa không
thể lệch nhau.

Xoá lớp: chỉ lớp rỗng, chỉ ở màn 10 (`DELETE /api/teacher/classes/{id}`), như xoá đề trống
(ADR-33). Kriky không có tool xoá lớp.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from be.db import get_session
from be.identity import Asking, current_teacher
from be.resolve import normalise, tidy_name
from schema.models import Attempt, Publication, SchoolClass, Student, Teacher

logger = logging.getLogger(__name__)

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


async def why_not_erasable(session: AsyncSession, school_class: SchoolClass) -> str:
    """Vì sao lớp này chưa xoá được; rỗng khi xoá được. Một phép cho mọi chỗ: màn 10 đọc nó qua
    `ClassDetail.erasable`, route xoá đọc nó trước khi xoá.

    Lớp rỗng là lớp không học sinh, **chưa từng** nhận đề (kể cả lần phát hành đã thu hồi: hàng
    `Publication` ở lại), và không lượt làm bài nào ghi lớp này (`Attempt.class_id`, kể cả của
    em đã chuyển lớp). Xoá một lớp như thế không đụng tới tài khoản hay bài làm của ai (ADR-13).

    Args:
        session: Session của database.
        school_class: Lớp đã kiểm là của giáo viên đang hỏi.

    Returns:
        Câu cho giáo viên, in nguyên văn ở hộp xoá lớp; rỗng khi lớp rỗng.
    """
    students = await session.scalar(
        select(func.count()).select_from(Student).where(Student.class_id == school_class.id)
    )
    if students:
        return f"Lớp còn {students} học sinh nên không xoá được."
    papers = await session.scalar(
        select(func.count()).select_from(Publication).where(Publication.class_id == school_class.id)
    )
    attempts = await session.scalar(
        select(func.count()).select_from(Attempt).where(Attempt.class_id == school_class.id)
    )
    if papers or attempts:
        return "Lớp đã nhận đề nên không xoá được."
    return ""


@router.delete("/teacher/classes/{class_id}", status_code=204)
async def erase_empty_class(
    class_id: str,
    teacher: Teacher = Depends(current_teacher),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Xoá **cứng** một lớp rỗng -- nút *Xoá lớp* của màn 10 (hậu ký ADR-13, 27/10/2026).

    Raises:
        HTTPException: 404 khi lớp không có hay thuộc người khác (ADR-22); 409 khi lớp không rỗng,
            `detail` là câu của `why_not_erasable`.
    """
    asking = Asking.of(teacher)
    school_class = await session.scalar(
        select(SchoolClass)
        .where(SchoolClass.id == class_id, SchoolClass.teacher_id == asking.teacher_id)
        .with_for_update()
    )
    if school_class is None:
        # Cùng câu với màn 10 (`teacher_reads._NO_CLASS`): lớp người khác và lớp không có là một.
        raise HTTPException(
            status_code=404, detail="Không tìm thấy lớp này trong danh sách của bạn."
        )
    refused = await why_not_erasable(session, school_class)
    if refused:
        raise HTTPException(status_code=409, detail=refused)
    await session.delete(school_class)
    await session.commit()
    logger.info("teacher %s erased empty class %s", asking.teacher_code, class_id)
    return Response(status_code=204)
