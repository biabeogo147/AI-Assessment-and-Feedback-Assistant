"""Đặt tên một bản lab: tạo tag `lab-<năm>.<z>.<x>` trên HEAD (plan `lab-version`).

Chạy bởi `.\\dev.ps1 release` (thêm `-Minor` để tăng `z`). Tên bản là thứ tester ghi vào ticket, nên
lệnh chỉ tạo tag khi tag ấy chắc chắn trỏ vào một commit ai cũng lấy được: đang ở `main`, `main` đã
push, và mục của bản ấy đã đứng đầu `CHANGELOG.md`. Lệnh **không tự push**: nó in lệnh push
cho người chạy.

Cây còn sửa dở thì chỉ cảnh báo, không từ chối: tag trỏ vào HEAD, không chở phần chưa commit, và máy
dev giữ sẵn vài dòng ghi chú riêng không bao giờ commit.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Không số 0 đứng đầu: `lab-2026.01.1` và `lab-2026.1.1` sẽ là hai tên cho cùng một bộ số.
TAG = re.compile(r"^lab-(\d{4})\.(0|[1-9]\d*)\.(0|[1-9]\d*)$", re.ASCII)
# Giờ Việt Nam, không đổi theo mùa. Offset cố định chứ không `zoneinfo`: trên Windows nó cần gói
# `tzdata` mà không file nào khai.
ZONE = timezone(timedelta(hours=7))
BRANCH = "main"
CHANGELOG = "CHANGELOG.md"


class Refused(Exception):
    """Một điều kiện không qua; lời là câu tiếng Việt in cho người chạy."""


def parse(tag: str) -> tuple[int, int, int] | None:
    """Ba con số của một tag lab, hay `None` khi tag không đúng dạng. Hàm thuần."""
    matched = TAG.match(tag.strip())
    if matched is None:
        return None
    year, z, x = (int(part) for part in matched.groups())
    return year, z, x


def latest(tags: Iterable[str]) -> str | None:
    """Tag lab lớn nhất, so theo số (`lab-2026.0.10` lớn hơn `lab-2026.0.9`); tag lạ bị bỏ qua.
    Hàm thuần."""
    known = [(numbers, tag.strip()) for tag in tags if (numbers := parse(tag))]
    return max(known)[1] if known else None


def next_version(tags: Iterable[str], today: date, minor: bool = False) -> str:
    """Tên bản kế tiếp. Hàm thuần.

    Args:
        tags: Mọi tag của repo; tag không đúng dạng `lab-YYYY.z.x` bị bỏ qua.
        today: Ngày theo giờ Việt Nam; năm của nó quyết khi nào về `.0.1`.
        minor: Tăng `z` (người phụ trách yêu cầu); `x` về `0`.

    Returns:
        Chưa có tag nào, hay tag mới nhất thuộc năm trước: `lab-<năm nay>.0.1`, kể cả khi `minor`.
        Không thì `lab-<năm>.<z+1>.0` khi `minor`, còn lại `lab-<năm>.<z>.<x+1>`.
    """
    known = [numbers for tag in tags if (numbers := parse(tag))]
    if not known:
        return f"lab-{today.year}.0.1"
    year, z, x = max(known)
    if year < today.year:
        return f"lab-{today.year}.0.1"
    return f"lab-{year}.{z + 1}.0" if minor else f"lab-{year}.{z}.{x + 1}"


def top_entry(changelog: str) -> str | None:
    """Tên bản của mục đầu tiên trong `CHANGELOG.md` (dòng `## lab-… — ngày`), hay `None`. Hàm
    thuần."""
    for line in changelog.splitlines():
        if line.startswith("## "):
            words = line[3:].split()
            return words[0] if words else None
    return None


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if done.returncode != 0:
        raise Refused(f"git {' '.join(args)} hỏng: {done.stderr.strip()}")
    return done.stdout.rstrip()


def release(root: Path, today: date, minor: bool) -> str:
    """Kiểm mọi điều kiện rồi tạo tag có chú thích trên HEAD.

    Args:
        root: Gốc repo.
        today: Ngày theo giờ Việt Nam.
        minor: Tăng `z`.

    Returns:
        Tên tag vừa tạo.

    Raises:
        Refused: Một điều kiện không qua; không tag nào được tạo.

    Side effects:
        `git fetch` nhánh `main` và các tag từ `origin`; `git tag -a` ở repo local. Không push.
    """
    dirty = _git(root, "status", "--porcelain", "--untracked-files=no")
    if dirty:
        print("Cảnh báo: còn sửa dở, phần này không vào tag:")
        print("\n".join(f"  {line}" for line in dirty.splitlines()))

    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        raise Refused(f"HEAD đang tách khỏi nhánh; chuyển về {BRANCH} trước.")
    if branch != BRANCH:
        raise Refused(f"Đang ở nhánh {branch}; chỉ đặt tên bản trên {BRANCH}.")

    try:
        _git(root, "fetch", "--quiet", "--tags", "origin", BRANCH)
    except Refused as failed:
        raise Refused(
            f"Không lấy được {BRANCH} và tag từ origin (mất mạng, hay một tag cùng tên đã khác "
            f"trên remote?), nên không kiểm được đã push chưa. {failed}"
        ) from failed
    # Tên kế tiếp và các commit từ bản trước in trước mọi phép kiểm còn lại: người viết mục
    # changelog cần chúng khi chưa commit gì.
    tags = _git(root, "tag", "--list", "lab-*").split()
    name = next_version(tags, today, minor)
    previous = latest(tags)
    span = [f"{previous}..HEAD"] if previous else ["--max-count=30"]
    print(f"Bản kế tiếp là {name}. Các commit từ {previous or 'đầu repo (30 commit mới nhất)'}:")
    print(_git(root, "log", "--oneline", *span) or "  (không có commit nào)")

    head = _git(root, "rev-parse", "HEAD")
    if head != _git(root, "rev-parse", f"origin/{BRANCH}"):
        raise Refused(
            f"HEAD khác origin/{BRANCH}: push {BRANCH} trước (hay pull nếu máy mình đang cũ), "
            "để tag trỏ vào một commit ai cũng lấy được."
        )

    already = [tag for tag in _git(root, "tag", "--points-at", "HEAD").split() if parse(tag)]
    if already:
        raise Refused(f"HEAD đã là bản {already[0]}; commit thêm rồi mới đặt tên mới.")

    # Đọc mục từ HEAD, không từ đĩa: mục viết rồi mà chưa commit thì không có trong bản được tag.
    try:
        entry = top_entry(_git(root, "show", f"HEAD:{CHANGELOG}"))
    except Refused:
        entry = None
    if entry != name:
        raise Refused(
            f"Mục đầu của {CHANGELOG} ở HEAD là {entry or 'trống'}, chưa phải {name}. Viết mục "
            f"'## {name} — {today:%d/%m/%Y}' lên đầu {CHANGELOG}, commit, push rồi chạy lại."
        )

    _git(root, "tag", "-a", name, "-m", name)
    return name


def main(argv: list[str] | None = None) -> int:
    """Điểm vào dòng lệnh. Trả mã thoát: 0 khi đã tạo tag, 1 khi từ chối."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Đặt tên một bản lab bằng tag lab-YYYY.z.x.")
    parser.add_argument("--minor", action="store_true", help="tăng z; x về 0")
    args = parser.parse_args(argv)
    try:
        name = release(REPO_ROOT, datetime.now(ZONE).date(), args.minor)
    except Refused as refused:
        print(f"Không đặt tên: {refused}")
        return 1
    print(f"Đã tạo tag {name} ở máy mình. Đẩy lên rồi deploy:")
    print(f"  git push origin {name}")
    print(f"  (trên máy lab) sudo bash /opt/aiafa/deploy/lab/deploy.sh {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
