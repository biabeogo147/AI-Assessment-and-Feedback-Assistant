"""Ai đang gọi, và điều đó cho họ chạm vào những gì.

ADR-10 để màn hình sign-in ra ngoài vòng đầu, nhưng "một học sinh chỉ thấy phần
việc của chính mình" là một luật, không phải một tiện lợi. Nên hai nửa được tách
ra: phần phân quyền bên dưới là thứ thật và sẽ không bị viết lại, còn phần chứng
minh danh tính chỉ là một header và chỉ hoạt động khi `dev_identity_enabled` bật.

Header đọc là `X-Actor: student:HS2026-1204` hoặc `X-Actor: teacher:GV-001`.
"""

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from be.config import get_settings
from be.db import get_session
from schema.models import Student, Teacher


@dataclass(frozen=True)
class Asking:
    """Một tool đang chạy cho ai, dưới dạng các giá trị chứ không phải một dòng.

    Cố ý không phải dòng `Teacher`. Vòng lặp rollback session của nó giữa các step
    để nhả connection về pool, và một lần rollback làm hết hạn mọi object ORM đang
    gắn với session đó -- nên việc đọc `teacher.id` ở step sau sẽ là một lần IO
    xuống database từ một nơi mà cầu async của SQLAlchemy không chạm tới được. Triệu
    chứng là `MissingGreenlet`, ném ra ở rất xa nguyên nhân của nó.

    Dùng giá trị cũng làm luật khó bị mất hơn: một tool được giao sẵn một danh tính
    mà nó không thể không có, và không thể âm thầm mở rộng phạm vi của mình bằng cách
    quên đọc danh tính đó.

    Attributes:
        teacher_id: Chủ sở hữu mà mọi query đều lọc theo (ADR-22).
        teacher_code: Thứ mà log gọi tên, nhờ vậy một lần từ chối truy được dấu mà
            không cần join gì cả.
        full_name: Cách trợ lý gọi người đó.
    """

    teacher_id: str
    teacher_code: str
    full_name: str

    @classmethod
    def of(cls, teacher: Teacher) -> "Asking":
        """Đọc một dòng teacher thành một danh tính sống lâu hơn session.

        Args:
            teacher: Dòng đó, vừa được load.

        Returns:
            Ba giá trị mà các tool và vòng lặp cần.
        """
        return cls(
            teacher_id=teacher.id,
            teacher_code=teacher.teacher_code,
            full_name=teacher.full_name,
        )


def _parse(raw: str | None) -> tuple[str, str]:
    """Tách header actor thành một role và một mã.

    Args:
        raw: Giá trị header, hoặc None khi header không có.

    Returns:
        role và mã.

    Raises:
        HTTPException: 401 khi header thiếu hoặc sai dạng.
    """
    if not raw or ":" not in raw:
        raise HTTPException(status_code=401, detail="Missing actor. Send 'role:code'.")
    role, _, code = raw.partition(":")
    role, code = role.strip().lower(), code.strip()
    if role not in {"student", "teacher"} or not code:
        raise HTTPException(
            status_code=401, detail="Actor must be 'student:<code>' or 'teacher:<code>'."
        )
    return role, code


async def current_student(
    session: AsyncSession = Depends(get_session),
    x_actor: str | None = Header(default=None, alias="X-Actor"),
) -> Student:
    """Phân giải học sinh đang tạo ra request này.

    Args:
        session: Session của database.
        x_actor: Header danh tính đứng thay.

    Returns:
        Dòng Student.

    Raises:
        HTTPException: 401 khi danh tính không có, sai dạng, bị tắt, hoặc mã không
            thuộc về ai; 403 khi một giáo viên gọi một route của học sinh.
    """
    if not get_settings().dev_identity_enabled:
        raise HTTPException(status_code=401, detail="Sign-in is not available yet.")

    role, code = _parse(x_actor)
    if role != "student":
        raise HTTPException(status_code=403, detail="This is a student route.")

    found = await session.scalar(select(Student).where(Student.student_code == code))
    if found is None:
        raise HTTPException(status_code=401, detail=f"No student {code}")
    return found


async def current_teacher(
    session: AsyncSession = Depends(get_session),
    x_actor: str | None = Header(default=None, alias="X-Actor"),
) -> Teacher:
    """Phân giải giáo viên đang tạo ra request này.

    Args:
        session: Session của database.
        x_actor: Header danh tính đứng thay.

    Returns:
        Dòng Teacher.

    Raises:
        HTTPException: 401 khi danh tính không có, sai dạng, bị tắt, hoặc không biết
            là ai; 403 khi một học sinh gọi một route của giáo viên.
    """
    if not get_settings().dev_identity_enabled:
        raise HTTPException(status_code=401, detail="Sign-in is not available yet.")

    role, code = _parse(x_actor)
    if role != "teacher":
        raise HTTPException(status_code=403, detail="This is a teacher route.")

    found = await session.scalar(select(Teacher).where(Teacher.teacher_code == code))
    if found is None:
        raise HTTPException(status_code=401, detail=f"No teacher {code}")
    return found
