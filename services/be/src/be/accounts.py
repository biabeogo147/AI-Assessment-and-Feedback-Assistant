"""Tài khoản: mật khẩu, phiên, tên đăng nhập, mã học sinh (việc 22, plan `sign-in-and-accounts`).

Không có gì ở đây đọc request. Route ở `be.account_routes` và `be.roster` gọi vào; `be.identity`
đọc phiên ra người.

Ba luật mà module này giữ:
- mật khẩu rõ không bao giờ được cất: chỉ `scrypt` của nó, kèm muối riêng;
- token phiên cũng không: bảng `sessions` chỉ giữ SHA-256 của token, nên một bản sao database
  không mở được phiên nào;
- tên đăng nhập là duy nhất trên **toàn hệ thống**, không chỉ trong một lớp, vì học sinh đăng nhập
  mà không chọn lớp.
"""

import asyncio
import hashlib
import hmac
import re
import secrets
import unicodedata
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from schema.models import AccountSession, Student, Teacher

# Tham số scrypt: 2**14 lần, 16 MB bộ nhớ -- mức OWASP còn chấp nhận, và một lần đăng nhập vẫn dưới
# 100 ms trên máy phòng học.
_N, _R, _P = 2**14, 8, 1
SESSION_DAYS = 30
TEACHER_COOKIE = "aiafa_teacher"
STUDENT_COOKIE = "aiafa_student"
PASSWORD_MIN = 8
# `students.username` là `String(64)`; gốc dài nhất 56 để còn chỗ cho số đuôi.
USERNAME_BASE_MOST = 56

# Mật khẩu phát cho học sinh: không có 0/o, 1/l/i -- em ấy chép tay từ tờ giấy giáo viên phát.
_PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def hash_password(password: str) -> str:
    """Băm một mật khẩu thành `scrypt$n$r$p$muối$băm`.

    Args:
        password: Mật khẩu rõ.

    Returns:
        Chuỗi để cất vào `password_hash`; mang theo tham số, nên đổi tham số sau này không làm hỏng
        những mật khẩu đã cất.
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


# Băm sẵn một mật khẩu không ai có, để `check_password` tốn cùng một khoảng thời gian dù tài khoản
# có tồn tại hay không: một lần đăng nhập sai không được kể ra số điện thoại nào đã đăng ký.
_NOBODY = hash_password(secrets.token_hex(16))


def check_password(password: str, stored: str | None) -> bool:
    """So một mật khẩu với chuỗi đã cất.

    Args:
        password: Mật khẩu người dùng gõ.
        stored: `password_hash` đã cất, hay None khi không có tài khoản hoặc tài khoản chưa có mật
            khẩu -- khi ấy vẫn băm một lần rồi trả False.

    Returns:
        True khi khớp.
    """
    try:
        scheme, n, r, p, salt, digest = (stored or _NOBODY).split("$")
        if scheme != "scrypt":
            return False
        mine = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32
        )
    except ValueError:
        return False
    return stored is not None and hmac.compare_digest(mine.hex(), digest)


async def hashed(password: str) -> str:
    """`hash_password` chạy ngoài event loop.

    Một lần `scrypt` tốn ~40 ms CPU. Chạy thẳng trong một route async thì cả BE đứng theo: tạo 200
    tài khoản chặn mọi request khác, kể cả SSE của chat, gần 8 giây (review pha 1-2). `hashlib`
    nhả GIL trong lúc băm, nên nhiều lần băm chạy song song được trên threadpool.
    """
    return await asyncio.to_thread(hash_password, password)


async def matches(password: str, stored: str | None) -> bool:
    """`check_password` chạy ngoài event loop, cùng lý do với `hashed`."""
    return await asyncio.to_thread(check_password, password, stored)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def open_session(
    session: AsyncSession, *, teacher: Teacher | None = None, student: Student | None = None
) -> str:
    """Mở một phiên cho đúng một người và trả token để đặt vào cookie.

    Args:
        session: Session của database.
        teacher: Giáo viên vừa đăng nhập, hay
        student: học sinh vừa đăng nhập. Đúng một trong hai.

    Returns:
        Token rõ. Chỉ SHA-256 của nó được cất.

    Side effects:
        Thêm một dòng `sessions`, xoá các phiên đã hết hạn của mọi người -- không thì bảng chỉ lớn
        lên --, rồi commit.
    """
    assert (teacher is None) != (student is None)
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    await session.execute(delete(AccountSession).where(AccountSession.expires_at <= now))
    session.add(
        AccountSession(
            token_hash=_token_hash(token),
            role="teacher" if teacher is not None else "student",
            teacher_id=teacher.id if teacher is not None else None,
            student_id=student.id if student is not None else None,
            created_at=now,
            expires_at=now + timedelta(days=SESSION_DAYS),
        )
    )
    await session.commit()
    return token


async def holder(session: AsyncSession, token: str, role: str) -> Teacher | Student | None:
    """Người đang giữ một token, nếu phiên còn hạn và đúng vai.

    Args:
        session: Session của database.
        token: Giá trị cookie.
        role: `teacher` hay `student` -- cookie của vai nào thì chỉ mở được vai ấy.

    Returns:
        Dòng Teacher hay Student, hoặc None khi token lạ, hết hạn hay sai vai.
    """
    found = await session.scalar(
        select(AccountSession).where(AccountSession.token_hash == _token_hash(token))
    )
    if found is None or found.role != role:
        return None
    expires = found.expires_at
    # SQLite trả datetime không múi giờ dù cột khai `timezone=True`.
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires <= datetime.now(UTC):
        return None
    if role == "teacher":
        return await session.get(Teacher, found.teacher_id)
    return await session.get(Student, found.student_id)


async def close_session(session: AsyncSession, token: str) -> None:
    """Đăng xuất: xoá dòng phiên. Token lạ thì không làm gì.

    Side effects:
        Xoá dòng rồi commit.
    """
    await session.execute(
        delete(AccountSession).where(AccountSession.token_hash == _token_hash(token))
    )
    await session.commit()


def normal_phone(raw: str) -> str | None:
    """Số điện thoại về một dạng để so: chỉ chữ số, `+84` thành `0`.

    Args:
        raw: Chuỗi người dùng gõ, có thể có dấu cách, dấu chấm, gạch nối.

    Returns:
        Chuỗi chữ số, hay None khi không phải số điện thoại Việt Nam (10 hay 11 chữ số, đầu `0`).
    """
    text = re.sub(r"[\s.\-()]", "", raw)
    if text.startswith("+84"):
        text = "0" + text[3:]
    if not re.fullmatch(r"0\d{9,10}", text):
        return None
    return text


def normal_email(raw: str) -> str | None:
    """Email về chữ thường, hay None khi không giống một email."""
    text = raw.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", text) or len(text) > 254:
        return None
    return text


def plain(text: str) -> str:
    """Bỏ dấu tiếng Việt, `đ` thành `d`, chữ thường, chỉ giữ chữ và số."""
    text = text.replace("đ", "d").replace("Đ", "D")
    stripped = "".join(
        ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn"
    )
    return re.sub(r"[^a-z0-9]", "", stripped.lower())


def username_base(full_name: str) -> str:
    """Tên đăng nhập trước khi tránh trùng: tên, rồi chữ đầu của họ và tên đệm.

    *Lê Kim Tính* → `tinhlk`; *Phạm Đức Anh* → `anhpd`. Người dùng chốt 18/10/2026.

    Args:
        full_name: Họ và tên, họ trước tên sau.

    Returns:
        Chuỗi chữ thường không dấu; `hs` khi tên không còn chữ nào sau khi bỏ dấu.
    """
    words = [plain(word) for word in full_name.split()]
    words = [word for word in words if word]
    if not words:
        return "hs"
    # Cột 64 ký tự, chừa chỗ cho số đuôi: một họ tên một từ dài 128 ký tự không được thành 500.
    return (words[-1] + "".join(word[0] for word in words[:-1]))[:USERNAME_BASE_MOST]


async def usernames_for(session: AsyncSession, full_names: Iterable[str]) -> list[str]:
    """Cấp tên đăng nhập cho một loạt tên, không trùng nhau và không trùng ai đã có.

    Trùng thì thêm số từ 2: `anhpd`, `anhpd2`, `anhpd3` (Figma 28b). Hai em cùng tên trong một
    loạt cũng nhận hai tên khác nhau.

    Args:
        session: Session của database, để đọc tên đã cấp.
        full_names: Họ tên theo thứ tự.

    Returns:
        Tên đăng nhập theo cùng thứ tự. Chưa ghi gì: hai lần xem trước liên tiếp cho cùng kết quả,
        và unique index của cột là chốt cuối khi hai giáo viên tạo cùng lúc.
    """
    names = list(full_names)
    bases = [username_base(name) for name in names]
    taken: set[str] = set()
    for base in set(bases):
        taken.update(
            await session.scalars(select(Student.username).where(Student.username.like(f"{base}%")))
        )
    given: list[str] = []
    for base in bases:
        candidate, number = base, 1
        while candidate in taken:
            number += 1
            candidate = f"{base}{number}"
        taken.add(candidate)
        given.append(candidate)
    return given


async def next_student_codes(session: AsyncSession, count: int) -> list[str]:
    """Mã học sinh kế tiếp: số thứ tự tăng dần trên toàn hệ thống, 1 → N.

    Mã cũ dạng `HS2026-1204` (dữ liệu demo) không phải số nên không chen vào dãy.

    Args:
        session: Session của database.
        count: Cần bao nhiêu mã.

    Returns:
        `count` mã liên tiếp, bắt đầu từ số lớn nhất đã có cộng một.
    """
    codes = await session.scalars(select(Student.student_code))
    top = max((int(code) for code in codes if code.isdigit()), default=0)
    return [str(top + offset) for offset in range(1, count + 1)]


def new_password() -> str:
    """Mật khẩu phát cho học sinh, dạng `k7m-pq4-xd` (Figma 28c): 8 ký tự ngẫu nhiên, dễ chép."""
    pick = [secrets.choice(_PASSWORD_ALPHABET) for _ in range(8)]
    return f"{''.join(pick[:3])}-{''.join(pick[3:6])}-{''.join(pick[6:])}"


async def next_teacher_code(session: AsyncSession) -> str:
    """Mã cho một giáo viên vừa tự đăng ký: `GV-` cộng số lớn nhất đã có cộng một, ba chữ số."""
    codes = await session.scalars(select(Teacher.teacher_code))
    numbers = [int(code[3:]) for code in codes if code.startswith("GV-") and code[3:].isdigit()]
    return f"GV-{max(numbers, default=0) + 1:03d}"
