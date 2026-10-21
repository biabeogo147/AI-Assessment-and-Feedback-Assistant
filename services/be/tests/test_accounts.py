"""Đăng ký, đăng nhập, đăng xuất và luật tài khoản (việc 22, plan `sign-in-and-accounts`, ADR-36).

Phần route chạy qua cookie thật của `httpx`: một test gửi `X-Actor` chỉ để chứng minh cookie thắng,
hay header bị bỏ qua khi cờ dev tắt.
"""

import asyncio
from collections import Counter
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
from be.sign_in_limit import SignInLimit
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


@pytest.fixture
def clock():
    """Đồng hồ giả của bộ đếm đăng nhập sai: test đẩy `clock.now` thay cho chờ 15 phút."""
    return SimpleNamespace(now=0.0)


@pytest_asyncio.fixture
async def stack(clock):
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
    app.state.sign_in_limit = SignInLimit(clock=lambda: clock.now)
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


# --- máy lab: đăng ký tắt, cookie Secure (plan `lab-deploy-aws`) ---------------------------------


def _settings(http, **change):
    """Thay `get_settings` của app test bằng một bản đổi vài cờ."""
    from be.config import Settings, get_settings

    http._transport.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, **change
    )


@pytest.mark.asyncio
async def test_sign_up_closed_refuses_and_writes_nothing(stack):
    http, maker = stack
    _settings(http, teacher_sign_up_enabled=False)
    response = await http.post("/api/teacher/sign-up", json=SIGN_UP)
    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Máy này không mở đăng ký. Hãy nhờ người quản trị tạo tài khoản."
    )
    assert "aiafa_teacher" not in http.cookies
    async with maker() as session:
        assert await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-002")) is None
    # Đăng nhập vẫn chạy: chỉ cửa tự tạo tài khoản đóng.
    _, phone, _, password = SAMPLE_TEACHER
    signed = await http.post("/api/teacher/sign-in", json={"login": phone, "password": password})
    assert signed.status_code == 204


@pytest.mark.asyncio
@pytest.mark.parametrize("secure", [True, False])
async def test_session_cookie_secure_follows_the_setting(stack, secure):
    http, _ = stack
    _settings(http, session_cookie_secure=secure)
    _, phone, _, password = SAMPLE_TEACHER
    teacher = await http.post("/api/teacher/sign-in", json={"login": phone, "password": password})
    _, username, student_password = SAMPLE_STUDENTS[0]
    student = await http.post(
        "/api/sign-in", json={"username": username, "password": student_password}
    )
    for response in (teacher, student):
        assert response.status_code == 204
        assert ("; secure" in response.headers["set-cookie"].lower()) is secure


def test_lab_switches_default_like_dev(monkeypatch):
    """Thiếu biến thì như máy dev: đăng ký mở, cookie không Secure (HTTP thuần vẫn đăng nhập)."""
    from be.config import Settings

    monkeypatch.delenv("TEACHER_SIGN_UP_ENABLED", raising=False)
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    settings = Settings(_env_file=None)
    assert settings.teacher_sign_up_enabled is True
    assert settings.session_cookie_secure is False


# ------------------------------------------------------------ giới hạn số lần thử đăng nhập

_LOCKED = "Bạn nhập sai quá nhiều lần. Thử lại sau 15 phút."


@pytest.mark.asyncio
async def test_five_wrong_passwords_lock_the_teacher_even_with_the_right_one(stack, clock):
    http, _ = stack
    _, phone, _, password = SAMPLE_TEACHER
    for _ in range(5):
        wrong = await http.post("/api/teacher/sign-in", json={"login": phone, "password": "sai"})
        assert wrong.status_code == 401
    # Khoá kiểm trước mật khẩu: lần thứ sáu đúng mật khẩu vẫn bị từ chối, nên đoán trúng lúc
    # đang khoá cũng không biết là trúng.
    right = await http.post("/api/teacher/sign-in", json={"login": phone, "password": password})
    assert right.status_code == 429
    assert right.json()["detail"] == _LOCKED
    # Cùng một người, gõ SĐT kiểu khác: vẫn là một tên.
    spaced = " ".join([phone[:4], phone[4:7], phone[7:]])
    assert (
        await http.post("/api/teacher/sign-in", json={"login": spaced, "password": password})
    ).status_code == 429

    clock.now += 15 * 60
    assert (
        await http.post("/api/teacher/sign-in", json={"login": phone, "password": password})
    ).status_code == 204


@pytest.mark.asyncio
async def test_wrong_tries_from_elsewhere_do_not_lock_the_teacher_out(stack):
    # Tier 2 câu 31 = B (21/10/2026): khoá theo cặp tên + địa chỉ. Kẻ biết SĐT giáo viên, gõ sai
    # từ máy của hắn, chỉ khoá chính cặp ấy; giáo viên ở trường vẫn vào được.
    http, _ = stack
    _, phone, _, password = SAMPLE_TEACHER
    elsewhere = ASGITransport(app=http._transport.app, client=("203.0.113.9", 4000))
    async with AsyncClient(transport=elsewhere, base_url="http://test") as stranger:
        for _ in range(5):
            wrong = await stranger.post(
                "/api/teacher/sign-in", json={"login": phone, "password": "sai"}
            )
            assert wrong.status_code == 401
        assert (
            await stranger.post("/api/teacher/sign-in", json={"login": phone, "password": "sai"})
        ).status_code == 429
    assert (
        await http.post("/api/teacher/sign-in", json={"login": phone, "password": password})
    ).status_code == 204


@pytest.mark.asyncio
async def test_lock_opens_minute_by_minute_and_says_how_long(stack, clock):
    http, _ = stack
    _, username, password = SAMPLE_STUDENTS[0]
    for _ in range(5):
        await http.post("/api/sign-in", json={"username": username, "password": "sai"})
        clock.now += 60
    # Lần sai đầu ở phút 0, nay là phút 5: còn 10 phút.
    locked = await http.post(
        "/api/sign-in", json={"username": username.upper(), "password": password}
    )
    assert locked.status_code == 429
    assert locked.json()["detail"] == "Bạn nhập sai quá nhiều lần. Thử lại sau 10 phút."
    clock.now = 15 * 60
    assert (
        await http.post("/api/sign-in", json={"username": username, "password": password})
    ).status_code == 204


@pytest.mark.asyncio
async def test_a_right_password_starts_the_count_again(stack):
    http, _ = stack
    _, username, password = SAMPLE_STUDENTS[0]
    for _ in range(4):
        await http.post("/api/sign-in", json={"username": username, "password": "sai"})
    assert (
        await http.post("/api/sign-in", json={"username": username, "password": password})
    ).status_code == 204
    for _ in range(4):
        assert (
            await http.post("/api/sign-in", json={"username": username, "password": "sai"})
        ).status_code == 401


@pytest.mark.asyncio
async def test_an_unknown_name_locks_the_same_way(stack):
    # Tên không có thật cũng khoá sau 5 lần: khác đi là câu trả lời lộ tên nào có thật.
    http, _ = stack
    for _ in range(5):
        assert (
            await http.post("/api/sign-in", json={"username": "khong-co", "password": "x"})
        ).status_code == 401
    locked = await http.post("/api/sign-in", json={"username": "khong-co", "password": "x"})
    assert locked.status_code == 429
    assert locked.json()["detail"] == _LOCKED


@pytest.mark.asyncio
async def test_one_name_locked_leaves_the_rest_of_the_class_alone(stack):
    http, _ = stack
    (_, first, _), (_, second, password) = SAMPLE_STUDENTS[0], SAMPLE_STUDENTS[1]
    for _ in range(5):
        await http.post("/api/sign-in", json={"username": first, "password": "sai"})
    # Cùng một địa chỉ (cả lớp sau một NAT), tên khác: vẫn vào được.
    assert (
        await http.post("/api/sign-in", json={"username": second, "password": password})
    ).status_code == 204


@pytest.mark.asyncio
async def test_fifty_wrong_tries_from_one_address_lock_every_name(stack):
    http, _ = stack
    for one in range(50):
        await http.post("/api/sign-in", json={"username": f"doan-{one}", "password": "x"})
    _, username, password = SAMPLE_STUDENTS[0]
    locked = await http.post("/api/sign-in", json={"username": username, "password": password})
    assert locked.status_code == 429
    # Giáo viên đăng nhập từ cùng địa chỉ ấy cũng chờ: khoá là của địa chỉ, không của vai.
    _, phone, _, teacher_password = SAMPLE_TEACHER
    assert (
        await http.post("/api/teacher/sign-in", json={"login": phone, "password": teacher_password})
    ).status_code == 429


@pytest.mark.asyncio
async def test_parallel_wrong_tries_cannot_slip_past_the_lock(stack):
    # Review 21/10/2026: ghi lần sai **sau** `scrypt` thì 40 request song song đều qua bước kiểm
    # trước khi lần sai đầu vào sổ. Nay lần thử vào sổ trước mọi `await`.
    http, _ = stack
    _, username, _ = SAMPLE_STUDENTS[0]
    answers = await asyncio.gather(
        *(
            http.post("/api/sign-in", json={"username": username, "password": "sai"})
            for _ in range(20)
        )
    )
    assert Counter(one.status_code for one in answers) == {401: 5, 429: 15}


@pytest.mark.asyncio
async def test_right_sign_ins_from_one_address_never_lock_it(stack):
    # Cả lớp đăng nhập đúng sau một NAT: lần đúng rời sổ của địa chỉ, nên lần thứ 51 vẫn vào.
    http, _ = stack
    _, username, password = SAMPLE_STUDENTS[0]
    for _ in range(51):
        right = await http.post("/api/sign-in", json={"username": username, "password": password})
        assert right.status_code == 204


@pytest.mark.asyncio
async def test_a_name_past_the_column_never_reaches_the_count(stack):
    # Review vòng 1 Tier 1 (21/10/2026): tên là khoá của bộ đếm, nên tên dài tuỳ ý là bộ nhớ tuỳ ý.
    # Trần ở model trả 422 trước handler: 60 lần như vậy, quá ngưỡng 50 của địa chỉ, vẫn không khoá.
    http, _ = stack
    for _ in range(60):
        assert (
            await http.post("/api/sign-in", json={"username": "a" * 65, "password": "x"})
        ).status_code == 422
        assert (
            await http.post("/api/teacher/sign-in", json={"login": "a" * 255, "password": "x"})
        ).status_code == 422
    _, username, password = SAMPLE_STUDENTS[0]
    assert (
        await http.post("/api/sign-in", json={"username": username, "password": password})
    ).status_code == 204


def test_names_that_never_failed_leave_nothing_behind():
    # Hỏi khoá của 1000 tên ngẫu nhiên không được để lại 1000 khoá rỗng.
    limit = SignInLimit()
    for one in range(1000):
        assert limit.wait_minutes(f"student:ai-{one}", "10.0.0.1") is None
    assert limit._tries == {}


def test_expired_tries_are_swept_away():
    now = SimpleNamespace(t=0.0)
    limit = SignInLimit(clock=lambda: now.t)
    for one in range(SignInLimit._SWEEP_EVERY - 1):
        limit.attempt(f"student:ai-{one}", f"10.0.{one // 250}.{one % 250}")
    now.t = 16 * 60
    limit.attempt("student:cuoi", "10.9.9.9")
    assert set(limit._tries) == {("login", "student:cuoi", "10.9.9.9"), ("address", "10.9.9.9")}
