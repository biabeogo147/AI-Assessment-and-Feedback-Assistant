"""Chạy bộ test BE trên Postgres khi được xin: `pytest services/be/tests --postgres-url=URL`.

Việc 23 của plan `postgres-test-run`. Mọi file test ở đây tự dựng một sqlite trong bộ nhớ
(`create_async_engine("sqlite+aiosqlite://")`), và sqlite không thi hành một nửa những gì
Postgres thi hành: `String(n)`, khoá ngoại (mặc định tắt), khoá hàng `FOR UPDATE`, thứ tự kiểm
ràng buộc unique. Một lỗi chỉ Postgres thấy thì không test nào đỏ cho tới khi giáo viên gặp nó.

Không có tuỳ chọn thì file này không làm gì: bộ test vẫn chạy trên sqlite như mọi khi, và
`.\\dev.ps1 test` không đổi. Có tuỳ chọn thì mọi lần dựng engine sqlite trong bộ nhớ được đổi
sang URL ấy, và **mỗi engine một schema sạch**: lần nối đầu tiên xoá rồi dựng lại `public`, đúng
như một sqlite mới tinh của mỗi test.

**Chỉ database tên kết thúc bằng `_test`.** Lần nối đầu xoá sạch schema, nên mọi database khác --
`aiafa` của máy dev, và các bản phụ như `aiafa_fe` -- bị từ chối. Không thêm biến nào vào `.env`;
URL đi bằng dòng lệnh, nên không có cách nào lỡ tay bật nó.

**Chỉ cho `services/be/tests`.** Phép đổi engine là toàn phiên, nên có tuỳ chọn mà phiên thu cả test
ngoài thư mục này thì phiên dừng ngay: test của `packages/schema` chạy câu sqlite thuần
(`sqlite_master`, `DROP INDEX`) để giả database lệch, và `services/ingest` không thuộc việc này.
"""

import os
from pathlib import Path

import pytest
import sqlalchemy.ext.asyncio as sa_asyncio
from sqlalchemy import event
from sqlalchemy.engine import make_url

# Hậu tố bắt buộc của database đích: lần nối đầu của mỗi engine xoá sạch schema.
_SUFFIX = "_test"

# Một kết nối còn giữ khoá trên `public` thì `DROP SCHEMA` chờ mãi; chờ chừng này rồi đỏ.
_LOCK_TIMEOUT = "10s"

_HERE = Path(__file__).parent

_real_create = sa_asyncio.create_async_engine

# Test gọi BE bằng `X-Actor` (Decision 1 của plan `sign-in-and-accounts`), mà mặc định của BE nay
# tắt header ấy (Decision 4). Đặt trước mọi lần `get_settings()`: settings được cache theo process.
os.environ["DEV_IDENTITY_ENABLED"] = "true"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--postgres-url",
        default="",
        help="Chạy test BE trên Postgres này thay vì sqlite (plan `postgres-test-run`).",
    )


def pytest_configure(config: pytest.Config) -> None:
    url = config.getoption("--postgres-url")
    if not url:
        return
    name = make_url(url).database or ""
    if not name.endswith(_SUFFIX):
        raise pytest.UsageError(
            f"--postgres-url phải trỏ tới một database tên kết thúc bằng `{_SUFFIX}` "
            f"(nhận `{name}`): mỗi test xoá sạch schema. Ví dụ aiafa_test."
        )
    sa_asyncio.create_async_engine = _redirecting(url)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if not config.getoption("--postgres-url"):
        return
    outside = sorted({str(item.path) for item in items if _HERE not in item.path.parents})
    if outside:
        raise pytest.UsageError(
            "--postgres-url chỉ dành cho services/be/tests; phiên này còn thu: "
            + ", ".join(outside[:3])
            + (" …" if len(outside) > 3 else "")
        )


def _redirecting(url: str):
    """Một `create_async_engine` đổi sqlite trong bộ nhớ sang Postgres, schema sạch mỗi engine."""

    def create(target, *args, **kwargs):
        if str(target) != "sqlite+aiosqlite://":
            return _real_create(target, *args, **kwargs)
        engine = _real_create(url)

        @event.listens_for(engine.sync_engine, "first_connect")
        def _fresh_schema(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute(f"SET LOCAL lock_timeout = '{_LOCK_TIMEOUT}'")
            cursor.execute("DROP SCHEMA IF EXISTS public CASCADE")
            cursor.execute("CREATE SCHEMA public")
            cursor.close()
            # Cần: adapter tự mở transaction, và DDL của Postgres nằm trong transaction -- thiếu
            # commit thì lần trả kết nối về pool rollback mất DROP/CREATE.
            connection.commit()

        return engine

    return create
