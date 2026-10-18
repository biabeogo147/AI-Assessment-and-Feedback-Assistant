"""Đăng ký, đăng nhập, đăng xuất và luật tài khoản (việc 22, plan `sign-in-and-accounts`, ADR-36).

Phần route chạy qua cookie thật của `httpx`: một test gửi `X-Actor` chỉ để chứng minh cookie thắng,
hay header bị bỏ qua khi cờ dev tắt.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be import identity
from be.account_routes import router as account_router
from be.accounts import (
    check_password,
    hash_password,
    new_password,
    next_student_codes,
    normal_phone,
    username_base,
    usernames_for,
)
from be.db import bind_sessions
from be.seed import SAMPLE_STUDENTS, SAMPLE_TEACHER, give_sample_sign_in, seed_if_empty
from be.student_routes import router as student_router
from be.teacher_routes import router as teacher_router
from schema.ddl import prepare_schema
from schema.models import AccountSession, SchoolClass, Student, Teacher

SIGN_UP = {
    "full_name": "Thầy  Nguyễn Văn Bình ",
    "phone": "091 234 5678",
    "email": "Binh.Nguyen@Example.com",
    "password": "mat-khau-dai",
}


@pytest_asyncio.fixture
async def stack():
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        await give_sample_sign_in(session)
    app = FastAPI()
    app.include_router(account_router)
    app.include_router(student_router)
    app.include_router(teacher_router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http, maker
    await engine.dispose()
    db_module._SESSION_MAKER = None


# --- luật thuần ---------------------------------------------------------------------------------


def test_password_round_trip_and_salt():
    one, two = hash_password("abc12345"), hash_password("abc12345")
    assert one != two and one.startswith("scrypt$16384$8$1$")
    assert check_password("abc12345", one)
    assert not check_password("abc12346", one)
    assert not check_password("abc12345", None)
    assert not check_password("abc12345", "md5$xyz")


@pytest.mark.parametrize(
    ("full_name", "expected"),
    [
        ("Lê Kim Tính", "tinhlk"),
        ("Phạm Đức Anh", "anhpd"),
        ("Nguyễn  Minh   Anh", "anhnm"),
        ("Hà", "ha"),
        ("Đặng Thị Ngọc Ánh", "anhdtn"),
        ("123 !!", "123"),
        ("—", "hs"),
    ],
)
def test_username_base(full_name, expected):
    assert username_base(full_name) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0912 345 678", "0912345678"),
        ("+84 912.345.678", "0912345678"),
        ("091-234-5678", "0912345678"),
        ("12345", None),
        ("abc0912345678", None),
    ],
)
def test_normal_phone(raw, expected):
    assert normal_phone(raw) == expected


def test_new_password_shape():
    for _ in range(50):
        password = new_password()
        parts = password.split("-")
        assert [len(part) for part in parts] == [3, 3, 2]
        assert not set("".join(parts)) & set("01oli")


@pytest.mark.asyncio
async def test_usernames_avoid_existing_and_each_other(stack):
    _, maker = stack
    async with maker() as session:
        given = await usernames_for(session, ["Phạm Đức Anh", "Phạm Đình Anh", "Nguyễn Mai Anh"])
        # Ba học sinh demo đã có `anhnm` (Nguyễn Minh Anh): em thứ ba nhận `anhnm2`.
        assert given == ["anhpd", "anhpd2", "anhnm2"]


@pytest.mark.asyncio
async def test_student_codes_count_up_past_numeric_only(stack):
    _, maker = stack
    async with maker() as session:
        assert await next_student_codes(session, 2) == ["1", "2"]
        class_id = await session.scalar(select(SchoolClass.id))
        session.add(Student(class_id=class_id, full_name="A", student_code="41"))
        await session.commit()
        assert await next_student_codes(session, 1) == ["42"]


# --- giáo viên ----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sign_up_signs_in_and_normalises(stack):
    http, maker = stack
    response = await http.post("/api/teacher/sign-up", json=SIGN_UP)
    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert "aiafa_teacher=" in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()

    me = (await http.get("/api/teacher/me")).json()
    assert me["full_name"] == "Thầy Nguyễn Văn Bình"
    assert me["teacher_code"] == "GV-002"
    async with maker() as session:
        teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-002"))
        assert (teacher.phone, teacher.email) == ("0912345678", "binh.nguyen@example.com")
        assert "mat-khau-dai" not in teacher.password_hash
        # Bảng phiên không giữ token rõ.
        token = http.cookies["aiafa_teacher"]
        stored = await session.scalar(select(AccountSession.token_hash))
        assert stored != token and len(stored) == 64


@pytest.mark.parametrize(
    ("change", "status", "detail"),
    [
        ({"phone": "0912345001"}, 409, "Số điện thoại này đã có tài khoản."),
        ({"email": "LAN.PHAM@example.com"}, 409, "Email này đã có tài khoản."),
        ({"phone": "12"}, 422, "Số điện thoại không đúng dạng."),
        ({"email": "khong-phai-email"}, 422, "Email không đúng dạng."),
        ({"password": "ngan"}, 422, "Mật khẩu cần ít nhất 8 ký tự."),
        ({"full_name": "   "}, 422, "Hãy nhập họ và tên."),
    ],
)
@pytest.mark.asyncio
async def test_sign_up_refusals(stack, change, status, detail):
    http, _ = stack
    response = await http.post("/api/teacher/sign-up", json=SIGN_UP | change)
    assert response.status_code == status
    assert response.json()["detail"] == detail
    assert "aiafa_teacher" not in http.cookies


@pytest.mark.asyncio
async def test_teacher_sign_in_by_phone_or_email(stack):
    http, _ = stack
    _, phone, email, password = SAMPLE_TEACHER
    for login in (phone, f" {email.upper()} ", "+84" + phone[1:]):
        http.cookies.clear()
        response = await http.post(
            "/api/teacher/sign-in", json={"login": login, "password": password}
        )
        assert response.status_code == 204, login
        assert (await http.get("/api/teacher/me")).json()["teacher_code"] == "GV-001"


@pytest.mark.parametrize(
    "body",
    [
        {"login": "0912345001", "password": "sai-mat-khau"},
        {"login": "0999999999", "password": "demo-gv-001"},
        {"login": "ai@example.com", "password": "demo-gv-001"},
        {"login": "linh tinh", "password": "demo-gv-001"},
    ],
)
@pytest.mark.asyncio
async def test_teacher_sign_in_wrong_says_one_thing(stack, body):
    http, _ = stack
    response = await http.post("/api/teacher/sign-in", json=body)
    assert response.status_code == 401
    assert response.json()["detail"] == "Số điện thoại, email hoặc mật khẩu không đúng."


@pytest.mark.asyncio
async def test_sign_out_ends_the_session(stack):
    http, maker = stack
    _, phone, _, password = SAMPLE_TEACHER
    await http.post("/api/teacher/sign-in", json={"login": phone, "password": password})
    token = http.cookies["aiafa_teacher"]
    assert (await http.post("/api/teacher/sign-out")).status_code == 204
    assert "aiafa_teacher" not in http.cookies
    # Token cũ, giữ lại ở đâu đó, cũng không mở được nữa.
    http.cookies.set("aiafa_teacher", token, domain="test", path="/api")
    again = await http.get("/api/teacher/me")
    assert again.status_code == 401
    assert again.json()["detail"] == "Bạn cần đăng nhập."
    async with maker() as session:
        assert await session.scalar(select(AccountSession.id)) is None


@pytest.mark.asyncio
async def test_expired_session_is_refused(stack):
    http, maker = stack
    _, phone, _, password = SAMPLE_TEACHER
    await http.post("/api/teacher/sign-in", json={"login": phone, "password": password})
    async with maker() as session:
        await session.execute(
            update(AccountSession).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()
    assert (await http.get("/api/teacher/me")).status_code == 401


@pytest.mark.asyncio
async def test_cookie_beats_actor_header(stack):
    http, _ = stack
    await http.post("/api/teacher/sign-up", json=SIGN_UP)
    me = await http.get("/api/teacher/me", headers={"X-Actor": "teacher:GV-001"})
    assert me.json()["teacher_code"] == "GV-002"


@pytest.mark.asyncio
async def test_actor_header_ignored_when_dev_identity_off(stack, monkeypatch):
    http, _ = stack
    monkeypatch.setattr(
        identity, "get_settings", lambda: SimpleNamespace(dev_identity_enabled=False)
    )
    off = await http.get("/api/teacher/me", headers={"X-Actor": "teacher:GV-001"})
    assert off.status_code == 401
    # Cookie vẫn chạy khi cờ tắt: đó là đường thật.
    _, phone, _, password = SAMPLE_TEACHER
    await http.post("/api/teacher/sign-in", json={"login": phone, "password": password})
    assert (await http.get("/api/teacher/me")).status_code == 200


# --- học sinh -----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_student_sign_in_and_out(stack):
    http, _ = stack
    code, username, password = SAMPLE_STUDENTS[0]
    response = await http.post(
        "/api/sign-in", json={"username": f" {username.upper()} ", "password": password}
    )
    assert response.status_code == 204
    me = (await http.get("/api/me")).json()
    assert (me["student_code"], me["full_name"]) == (code, "Nguyễn Minh Anh")

    assert (await http.post("/api/sign-out")).status_code == 204
    assert (await http.get("/api/me")).status_code == 401


@pytest.mark.asyncio
async def test_student_wrong_password_and_unknown_say_one_thing(stack):
    http, _ = stack
    for body in (
        {"username": "anhnm", "password": "sai-roi-nhe"},
        {"username": "ai", "password": "x"},
    ):
        response = await http.post("/api/sign-in", json=body)
        assert response.status_code == 401
        assert response.json()["detail"] == "Tên đăng nhập hoặc mật khẩu không đúng."


@pytest.mark.asyncio
async def test_each_role_has_its_own_cookie(stack):
    http, _ = stack
    _, username, password = SAMPLE_STUDENTS[0]
    await http.post("/api/sign-in", json={"username": username, "password": password})
    # Cookie học sinh không mở route giáo viên ...
    assert (await http.get("/api/teacher/me")).status_code == 401
    # ... và hai vai đăng nhập song song trong một trình duyệt (người dùng chốt 18/10/2026).
    _, phone, _, teacher_password = SAMPLE_TEACHER
    await http.post("/api/teacher/sign-in", json={"login": phone, "password": teacher_password})
    assert (await http.get("/api/teacher/me")).status_code == 200
    assert (await http.get("/api/me")).status_code == 200
    # Token của vai này đặt vào cookie vai kia cũng không mở được.
    teacher_token = http.cookies["aiafa_teacher"]
    http.cookies.clear()
    http.cookies.set("aiafa_student", teacher_token, domain="test", path="/api")
    swapped = await http.get("/api/me")
    assert swapped.status_code == 401


@pytest.mark.asyncio
async def test_sample_sign_in_is_idempotent(stack):
    _, maker = stack
    async with maker() as session:
        before = await session.scalar(
            select(Teacher.password_hash).where(Teacher.teacher_code == "GV-001")
        )
        assert await give_sample_sign_in(session) == 0
        after = await session.scalar(
            select(Teacher.password_hash).where(Teacher.teacher_code == "GV-001")
        )
        assert before == after


@pytest.mark.asyncio
async def test_sign_up_refuses_a_name_past_the_column(stack):
    http, _ = stack
    response = await http.post("/api/teacher/sign-up", json=SIGN_UP | {"full_name": "A" * 129})
    assert response.status_code == 422
    assert response.json()["detail"] == "Họ và tên dài quá 128 ký tự."


@pytest.mark.asyncio
async def test_signing_in_sweeps_expired_sessions(stack):
    http, maker = stack
    _, phone, _, password = SAMPLE_TEACHER
    await http.post("/api/teacher/sign-in", json={"login": phone, "password": password})
    async with maker() as session:
        await session.execute(
            update(AccountSession).values(expires_at=datetime.now(UTC) - timedelta(days=1))
        )
        await session.commit()
    http.cookies.clear()
    await http.post("/api/teacher/sign-in", json={"login": phone, "password": password})
    async with maker() as session:
        assert len((await session.scalars(select(AccountSession))).all()) == 1


def test_dev_identity_is_off_unless_asked(monkeypatch):
    """Một cài đặt thiếu biến không nhận danh tính tự khai (Decision 4, `sign-in-and-accounts`)."""
    from be.config import Settings

    monkeypatch.delenv("DEV_IDENTITY_ENABLED", raising=False)
    assert Settings(_env_file=None).dev_identity_enabled is False
