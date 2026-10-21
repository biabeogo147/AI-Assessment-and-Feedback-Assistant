"""`python -m be.lab_seed [--reset]`: dựng dữ liệu lab vào database đã cấu hình.

Mật khẩu chung của mọi tài khoản đọc từ **stdin** -- một dòng khi đổ vào bằng ống, hay hỏi kín khi
gõ tay -- để nó không nằm trên dòng lệnh, trong biến môi trường hay lịch sử shell. Không in lại.

`--reset` xoá sạch database và bucket tài liệu (`be.reset_db.wipe`), rồi seed lab **thay cho**
demo. Không có cờ ấy thì database phải là bảng rỗng BE đã dựng (`check_schema`); đã có lớp thì từ
chối: seed lab không trộn vào dữ liệu đang dùng.
"""

import argparse
import asyncio
import getpass
import sys
from datetime import UTC, datetime

from sqlalchemy import func, select

from be.accounts import PASSWORD_MIN, hash_password
from be.config import get_settings
from be.db import bind_sessions, create_engine, get_session
from be.lab_seed.story import LabSummary, seed_lab
from be.reset_db import wipe
from be.storage import create_store
from schema.ddl import check_schema
from schema.models import SchoolClass


async def main(argv: list[str] | None = None) -> int:
    """Đọc mật khẩu, (xoá rồi) seed, in tóm tắt.

    Args:
        argv: Tham số dòng lệnh; `None` là `sys.argv`.

    Returns:
        Mã thoát: 0 khi xong, 1 khi database đã có lớp mà thiếu `--reset`, 2 khi mật khẩu ngắn.

    Side effects:
        Với `--reset`: **xoá toàn bộ** database và bucket tài liệu. Sau đó ghi dữ liệu lab.
    """
    parser = argparse.ArgumentParser(prog="python -m be.lab_seed", description=__doc__)
    parser.add_argument("--reset", action="store_true", help="xoá sạch database và bucket trước")
    args = parser.parse_args(argv)

    password = _read_password()
    if len(password) < PASSWORD_MIN:
        print(f"Mật khẩu cần ít nhất {PASSWORD_MIN} ký tự.", file=sys.stderr)
        return 2

    settings = get_settings()
    engine = create_engine(settings)
    try:
        if args.reset:
            await wipe(engine, create_store(settings))
        else:
            await check_schema(engine)
        bind_sessions(engine)
        async for session in get_session():
            if not args.reset and await session.scalar(
                select(func.count()).select_from(SchoolClass)
            ):
                print("Database đã có lớp. Chạy lại với --reset để xoá rồi seed.", file=sys.stderr)
                return 1
            summary = await seed_lab(session, hash_password(password), datetime.now(UTC))
    finally:
        await engine.dispose()
    _print(summary)
    return 0


def _read_password() -> str:
    if sys.stdin.isatty():
        return getpass.getpass("Mật khẩu chung cho mọi tài khoản lab: ")
    return sys.stdin.readline().rstrip("\r\n")


def _print(summary: LabSummary) -> None:
    print(
        f"Đã seed {len(summary.teachers)} giáo viên, {summary.classes} lớp, "
        f"{summary.students} học sinh, {summary.attempts} lượt làm bài."
    )
    print("Đề: " + ", ".join(f"{kind} {count}" for kind, count in summary.papers.items()))
    print("Giáo viên đăng nhập bằng SĐT hoặc email:")
    for name, phone, email in summary.teachers:
        print(f"  {name}: {phone} · {email}")
    print("Học sinh đầu tiên mỗi lớp (tên đăng nhập):")
    print("  " + ", ".join(f"{name} {username}" for name, username in summary.sample_students))
    print("Mọi tài khoản dùng chung mật khẩu vừa nhập.")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
