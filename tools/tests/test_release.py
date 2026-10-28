"""Luật đặt tên bản lab (plan `lab-version`): tên kế tiếp, và lệnh chỉ tạo tag khi đủ điều kiện.

Phần git chạy trên một repo thật trong `tmp_path`, có `origin` là một repo bare bên cạnh: luật
*đã push* chỉ kiểm được bằng một remote thật. Cấu hình git của máy (ký commit, tên người) không lọt
vào, vì `GIT_CONFIG_GLOBAL` trỏ vào một file rỗng.
"""

import subprocess
from datetime import date
from pathlib import Path

import pytest

from release import Refused, latest, next_version, release, top_entry

TODAY = date(2026, 10, 28)


@pytest.mark.parametrize(
    ("tags", "today", "minor", "expected"),
    [
        ([], TODAY, False, "lab-2026.0.1"),
        ([], TODAY, True, "lab-2026.0.1"),
        (["lab-2026.0.1"], TODAY, False, "lab-2026.0.2"),
        (["lab-2026.0.7"], TODAY, True, "lab-2026.1.0"),
        (["lab-2026.1.0"], TODAY, False, "lab-2026.1.1"),
        (["lab-2026.3.4"], date(2027, 1, 2), False, "lab-2027.0.1"),
        (["lab-2026.3.4"], date(2027, 1, 2), True, "lab-2027.0.1"),
        (["lab-2026.0.9", "lab-2026.0.10"], TODAY, False, "lab-2026.0.11"),
        (
            ["v1.0", "lab-2026.0.2-rc", "lab-26.0.5", "lab-2026.01.9", "lab-2026.0.3"],
            TODAY,
            False,
            "lab-2026.0.4",
        ),
    ],
)
def test_next_version(tags, today, minor, expected):
    assert next_version(tags, today, minor) == expected


def test_latest_compares_numbers_not_letters():
    assert latest(["lab-2026.0.9", "lab-2026.0.10", "lab-2026.0.2"]) == "lab-2026.0.10"
    assert latest(["main", "v2"]) is None


def test_top_entry_reads_the_first_version_heading():
    text = "# Changelog\n\nLời mở.\n\n## lab-2026.0.2 — 29/10/2026\n\n## lab-2026.0.1 — x\n"
    assert top_entry(text) == "lab-2026.0.2"
    assert top_entry("# Changelog\n\nChưa có bản nào.\n") is None


def _run(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Một repo `main` đã push lên `origin`, có một commit với CHANGELOG.md trống mục."""
    empty = tmp_path / "gitconfig"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for leaked in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):  # chạy trong một git hook
        monkeypatch.delenv(leaked, raising=False)
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Thử")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "thu@example.com")
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    _run(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    _run(tmp_path, "init", "-q", "-b", "main", str(work))
    _run(work, "remote", "add", "origin", str(origin))
    (work / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    _run(work, "add", ".")
    _run(work, "commit", "-q", "-m", "đầu")
    _run(work, "push", "-q", "origin", "main")
    return work


def _write_entry(work: Path, name: str, push: bool = True) -> None:
    (work / "CHANGELOG.md").write_text(f"# Changelog\n\n## {name} — 28/10/2026\n", encoding="utf-8")
    _run(work, "commit", "-q", "-am", f"changelog {name}")
    if push:
        _run(work, "push", "-q", "origin", "main")


def test_tags_head_when_the_entry_heads_the_changelog(repo):
    _write_entry(repo, "lab-2026.0.1")

    assert release(repo, TODAY, minor=False) == "lab-2026.0.1"
    assert _run(repo, "tag", "--points-at", "HEAD") == "lab-2026.0.1"
    assert _run(repo, "cat-file", "-t", "lab-2026.0.1") == "tag"  # có chú thích
    assert _run(repo, "ls-remote", "--tags", "origin") == ""  # không tự push


def test_a_missing_changelog_entry_creates_no_tag(repo, capsys):
    with pytest.raises(Refused, match="chưa phải lab-2026.0.1"):
        release(repo, TODAY, minor=False)

    assert "Bản kế tiếp là lab-2026.0.1" in capsys.readouterr().out
    assert _run(repo, "tag") == ""


def test_an_unpushed_head_creates_no_tag(repo):
    _write_entry(repo, "lab-2026.0.1", push=False)

    with pytest.raises(Refused, match="push main"):
        release(repo, TODAY, minor=False)
    assert _run(repo, "tag") == ""


def test_another_branch_creates_no_tag(repo):
    _run(repo, "switch", "-q", "-c", "nhanh")
    _write_entry(repo, "lab-2026.0.1", push=False)

    with pytest.raises(Refused, match="nhánh nhanh"):
        release(repo, TODAY, minor=False)
    assert _run(repo, "tag") == ""


def test_a_tagged_head_is_not_tagged_again(repo):
    _write_entry(repo, "lab-2026.0.1")
    release(repo, TODAY, minor=False)
    _run(repo, "push", "-q", "origin", "lab-2026.0.1")

    with pytest.raises(Refused, match="đã là bản lab-2026.0.1"):
        release(repo, TODAY, minor=False)


def test_uncommitted_changes_warn_but_still_tag(repo, capsys):
    _write_entry(repo, "lab-2026.0.1")
    (repo / "khac.txt").write_text("x", encoding="utf-8")
    _run(repo, "add", "khac.txt")

    assert release(repo, TODAY, minor=False) == "lab-2026.0.1"
    assert "còn sửa dở" in capsys.readouterr().out


def test_minor_bumps_z(repo):
    _write_entry(repo, "lab-2026.0.1")
    release(repo, TODAY, minor=False)
    _run(repo, "push", "-q", "origin", "lab-2026.0.1")
    _write_entry(repo, "lab-2026.1.0")

    assert release(repo, TODAY, minor=True) == "lab-2026.1.0"


def test_an_entry_written_but_not_committed_creates_no_tag(repo):
    """Mục changelog phải nằm trong chính bản được tag, không chỉ trên đĩa."""
    (repo / "CHANGELOG.md").write_text("# Changelog\n\n## lab-2026.0.1 — x\n", encoding="utf-8")

    with pytest.raises(Refused, match="ở HEAD là trống"):
        release(repo, TODAY, minor=False)
    assert _run(repo, "tag") == ""


def test_a_tag_pushed_from_another_machine_counts(repo, tmp_path, capsys):
    """Tên kế tiếp tính cả tag người khác đã push: lệnh lấy tag từ `origin` trước."""
    other = tmp_path / "other"
    _run(tmp_path, "clone", "-q", str(tmp_path / "origin.git"), str(other))
    _write_entry(other, "lab-2026.0.1")
    _run(other, "tag", "-a", "lab-2026.0.1", "-m", "lab-2026.0.1")
    _run(other, "push", "-q", "origin", "lab-2026.0.1")
    _run(repo, "pull", "-q", "origin", "main")
    _write_entry(repo, "lab-2026.0.2")

    assert release(repo, TODAY, minor=False) == "lab-2026.0.2"
    assert "Bản kế tiếp là lab-2026.0.2" in capsys.readouterr().out
