"""Đăng ký, đăng nhập, đăng xuất cho hai vai (việc 22, plan `sign-in-and-accounts`, ADR-36).

Mỗi vai một cookie (`aiafa_teacher`, `aiafa_student`), để giáo viên và học sinh đăng nhập song song
trong một trình duyệt khi demo (người dùng chốt 18/10/2026). Cookie `HttpOnly` -- JS của trang
không đọc được token -- và `SameSite=Lax`, nên một trang lạ không gửi được request ghi kèm cookie.

Đăng nhập thành công trả 204, không trả người: FE gọi `GET /api/teacher/me` hay `GET /api/me` ngay
sau, như mọi lần mở trang. Một hình dạng `me` duy nhất cho mỗi vai, không phải hai.
"""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from be.accounts import (
    PASSWORD_MIN,
    SESSION_DAYS,
    STUDENT_COOKIE,
    TEACHER_COOKIE,
    close_session,
    hashed,
    matches,
    next_teacher_code,
    normal_email,
    normal_phone,
    open_session,
)
from be.config import Settings, get_settings
from be.db import get_session
from schema.models import Student, Teacher

router = APIRouter(prefix="/api", tags=["accounts"])

_WRONG_TEACHER = "Số điện thoại, email hoặc mật khẩu không đúng."
_WRONG_STUDENT = "Tên đăng nhập hoặc mật khẩu không đúng."
_SIGN_UP_CLOSED = "Máy này không mở đăng ký. Hãy nhờ người quản trị tạo tài khoản."


class TeacherSignUp(BaseModel):
    """Một giáo viên tự tạo tài khoản (Figma 26b). Cả SĐT lẫn email là bắt buộc.

    Attributes:
        full_name: Họ và tên.
        phone: Số điện thoại, dạng nào cũng được; BE đưa về chỉ chữ số.
        email: Email.
        password: Ít nhất `PASSWORD_MIN` ký tự.
    """

    full_name: str
    phone: str
    email: str
    password: str


class TeacherSignIn(BaseModel):
    """Đăng nhập giáo viên (Figma 26): `login` là SĐT **hoặc** email -- có `@` thì là email.

    Attributes:
        login: SĐT hay email.
        password: Mật khẩu.
    """

    login: str
    password: str


class StudentSignIn(BaseModel):
    """Đăng nhập học sinh (Figma 12, trang học sinh) bằng tài khoản giáo viên phát.

    Attributes:
        username: Tên đăng nhập, như `tinhlk`.
        password: Mật khẩu.
    """

    username: str
    password: str


def _set_cookie(response: Response, name: str, token: str, *, secure: bool) -> None:
    response.set_cookie(
        name,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        path="/api",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


@router.post("/teacher/sign-up", status_code=204)
async def teacher_sign_up(
    body: TeacherSignUp,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> None:
    """Tạo tài khoản giáo viên rồi đăng nhập luôn.

    Raises:
        HTTPException: 403 khi máy này tắt đăng ký (`teacher_sign_up_enabled`); 422 khi một ô
            sai dạng; 409 khi SĐT hay email đã có tài khoản.

    Side effects:
        Thêm một dòng `teachers`, một dòng `sessions`; đặt cookie `aiafa_teacher`.
    """
    if not settings.teacher_sign_up_enabled:
        raise HTTPException(status_code=403, detail=_SIGN_UP_CLOSED)
    full_name = " ".join(body.full_name.split())
    phone = normal_phone(body.phone)
    email = normal_email(body.email)
    if not full_name:
        raise HTTPException(status_code=422, detail="Hãy nhập họ và tên.")
    if len(full_name) > 128:
        raise HTTPException(status_code=422, detail="Họ và tên dài quá 128 ký tự.")
    if phone is None:
        raise HTTPException(status_code=422, detail="Số điện thoại không đúng dạng.")
    if email is None:
        raise HTTPException(status_code=422, detail="Email không đúng dạng.")
    if len(body.password) < PASSWORD_MIN:
        raise HTTPException(status_code=422, detail=f"Mật khẩu cần ít nhất {PASSWORD_MIN} ký tự.")
    if await session.scalar(select(Teacher.id).where(Teacher.phone == phone)):
        raise HTTPException(status_code=409, detail="Số điện thoại này đã có tài khoản.")
    if await session.scalar(select(Teacher.id).where(Teacher.email == email)):
        raise HTTPException(status_code=409, detail="Email này đã có tài khoản.")

    teacher = Teacher(
        full_name=full_name,
        teacher_code=await next_teacher_code(session),
        phone=phone,
        email=email,
        password_hash=await hashed(body.password),
    )
    session.add(teacher)
    try:
        await session.flush()
    except IntegrityError as exc:
        # Hai lần đăng ký cùng lúc vượt qua hai câu hỏi ở trên -- trùng SĐT, email, hay cùng lấy một
        # mã giáo viên; unique index là chốt cuối. Không biết là cái nào, nên câu không đoán.
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Chưa tạo được tài khoản vì có người vừa đăng ký cùng lúc. Hãy thử lại.",
        ) from exc
    _set_cookie(
        response,
        TEACHER_COOKIE,
        await open_session(session, teacher=teacher),
        secure=settings.session_cookie_secure,
    )


@router.post("/teacher/sign-in", status_code=204)
async def teacher_sign_in(
    body: TeacherSignIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> None:
    """Đăng nhập giáo viên bằng SĐT hoặc email.

    Raises:
        HTTPException: 401 với **một** câu cho mọi lần sai -- không nói SĐT nào đã đăng ký.

    Side effects:
        Thêm một dòng `sessions`; đặt cookie `aiafa_teacher`.
    """
    login = body.login.strip()
    if "@" in login:
        email = normal_email(login)
        where = Teacher.email == email if email else None
    else:
        phone = normal_phone(login)
        where = Teacher.phone == phone if phone else None
    teacher = await session.scalar(select(Teacher).where(where)) if where is not None else None
    if not await matches(body.password, teacher.password_hash if teacher else None):
        raise HTTPException(status_code=401, detail=_WRONG_TEACHER)
    assert teacher is not None
    _set_cookie(
        response,
        TEACHER_COOKIE,
        await open_session(session, teacher=teacher),
        secure=settings.session_cookie_secure,
    )


@router.post("/teacher/sign-out", status_code=204)
async def teacher_sign_out(
    response: Response,
    session: AsyncSession = Depends(get_session),
    token: str | None = Cookie(default=None, alias=TEACHER_COOKIE),
) -> None:
    """Đăng xuất giáo viên. Không có phiên thì vẫn 204: kết quả đã đúng như người gọi muốn.

    Side effects:
        Xoá dòng phiên; xoá cookie.
    """
    if token:
        await close_session(session, token)
    response.delete_cookie(TEACHER_COOKIE, path="/api")


@router.post("/sign-in", status_code=204)
async def student_sign_in(
    body: StudentSignIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> None:
    """Đăng nhập học sinh bằng tên đăng nhập và mật khẩu giáo viên phát.

    Raises:
        HTTPException: 401 với một câu cho mọi lần sai.

    Side effects:
        Thêm một dòng `sessions`; đặt cookie `aiafa_student`.
    """
    username = body.username.strip().lower()
    student = await session.scalar(select(Student).where(Student.username == username))
    if not await matches(body.password, student.password_hash if student else None):
        raise HTTPException(status_code=401, detail=_WRONG_STUDENT)
    assert student is not None
    _set_cookie(
        response,
        STUDENT_COOKIE,
        await open_session(session, student=student),
        secure=settings.session_cookie_secure,
    )


@router.post("/sign-out", status_code=204)
async def student_sign_out(
    response: Response,
    session: AsyncSession = Depends(get_session),
    token: str | None = Cookie(default=None, alias=STUDENT_COOKIE),
) -> None:
    """Đăng xuất học sinh.

    Side effects:
        Xoá dòng phiên; xoá cookie.
    """
    if token:
        await close_session(session, token)
    response.delete_cookie(STUDENT_COOKIE, path="/api")
