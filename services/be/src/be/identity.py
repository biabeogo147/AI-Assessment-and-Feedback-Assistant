"""Ai đang gọi, và điều đó cho họ chạm vào những gì.

Hai nửa tách nhau: phần phân quyền bên dưới là thứ thật và không bị viết lại, còn phần chứng minh
danh tính có hai đường (việc 22, ADR-36):

- **cookie phiên** (`aiafa_teacher`, `aiafa_student`), do `be.account_routes` đặt khi đăng nhập --
  đường duy nhất của trình duyệt;
- **header `X-Actor`** (`student:HS2026-1204`, `teacher:GV-001`), chỉ khi `dev_identity_enabled`
  bật **và** request không mang cookie của vai ấy. Còn lại cho test và lệnh `curl` khi dev; cookie
  luôn thắng, nên một trình duyệt đã đăng nhập không bao giờ bị một header đổi danh tính.
"""

from dataclasses import dataclass

from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from be.accounts import STUDENT_COOKIE, TEACHER_COOKIE, holder
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


# Một câu cho cả "chưa đăng nhập" lẫn "phiên đã hết": người dùng làm cùng một việc -- đăng nhập lại.
_SIGN_IN = "Bạn cần đăng nhập."


async def current_student(
    session: AsyncSession = Depends(get_session),
    token: str | None = Cookie(default=None, alias=STUDENT_COOKIE),
    x_actor: str | None = Header(default=None, alias="X-Actor"),
) -> Student:
    """Phân giải học sinh đang tạo ra request này.

    Args:
        session: Session của database.
        token: Cookie phiên của học sinh.
        x_actor: Header danh tính khi dev, chỉ đọc khi không có cookie.

    Returns:
        Dòng Student.

    Raises:
        HTTPException: 401 khi chưa đăng nhập, phiên hết hạn, header sai dạng hay mã không thuộc
            về ai; 403 khi header khai một giáo viên trên route của học sinh.
    """
    if token:
        found = await holder(session, token, "student")
        if not isinstance(found, Student):
            raise HTTPException(status_code=401, detail=_SIGN_IN)
        return found
    if not get_settings().dev_identity_enabled or x_actor is None:
        raise HTTPException(status_code=401, detail=_SIGN_IN)

    role, code = _parse(x_actor)
    if role != "student":
        raise HTTPException(status_code=403, detail="This is a student route.")

    student = await session.scalar(select(Student).where(Student.student_code == code))
    if student is None:
        raise HTTPException(status_code=401, detail=f"No student {code}")
    return student


async def current_teacher(
    session: AsyncSession = Depends(get_session),
    token: str | None = Cookie(default=None, alias=TEACHER_COOKIE),
    x_actor: str | None = Header(default=None, alias="X-Actor"),
) -> Teacher:
    """Phân giải giáo viên đang tạo ra request này.

    Args:
        session: Session của database.
        token: Cookie phiên của giáo viên.
        x_actor: Header danh tính khi dev, chỉ đọc khi không có cookie.

    Returns:
        Dòng Teacher.

    Raises:
        HTTPException: 401 khi chưa đăng nhập, phiên hết hạn, header sai dạng hay không biết là
            ai; 403 khi header khai một học sinh trên route của giáo viên.
    """
    if token:
        found = await holder(session, token, "teacher")
        if not isinstance(found, Teacher):
            raise HTTPException(status_code=401, detail=_SIGN_IN)
        return found
    if not get_settings().dev_identity_enabled or x_actor is None:
        raise HTTPException(status_code=401, detail=_SIGN_IN)

    role, code = _parse(x_actor)
    if role != "teacher":
        raise HTTPException(status_code=403, detail="This is a teacher route.")

    teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == code))
    if teacher is None:
        raise HTTPException(status_code=401, detail=f"No teacher {code}")
    return teacher
