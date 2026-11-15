"""Hình in trong sách phải khớp `.drawio` của nó (plan `user-guide`: hai cuốn, hai cặp thư mục)."""

import hashlib
import json
from pathlib import Path

from check_contract import figure_drift


def _book(root: Path) -> tuple[Path, Path]:
    """Dựng một cuốn sách nhỏ: một `.drawio`, hình xuất ra của nó, và `sources.json` khớp."""
    diagrams = root / "docs" / "diagrams"
    figures = root / "book" / "figures"
    diagrams.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True)
    drawio = diagrams / "a.drawio"
    drawio.write_text("<mxfile/>", encoding="utf-8")
    (figures / "a.pdf").write_bytes(b"%PDF")
    manifest = {
        "a.pdf": {
            "source": drawio.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(drawio.read_bytes()).hexdigest(),
        }
    }
    (figures / "sources.json").write_text(json.dumps(manifest), encoding="utf-8")
    return diagrams, figures


def test_a_figure_exported_from_the_current_diagram_passes(tmp_path: Path) -> None:
    """Hash khớp và mọi sơ đồ đều có hình: không lệch gì."""
    diagrams, figures = _book(tmp_path)
    assert figure_drift(tmp_path, diagrams, figures, "user guide") == []


def test_a_diagram_edited_after_export_is_caught(tmp_path: Path) -> None:
    """Sửa `.drawio` mà không xuất lại: sách đang in bản hình cũ."""
    diagrams, figures = _book(tmp_path)
    (diagrams / "a.drawio").write_text("<mxfile>đổi</mxfile>", encoding="utf-8")
    problems = figure_drift(tmp_path, diagrams, figures, "user guide")
    assert any("re-export" in one for one in problems)


def test_a_new_diagram_without_a_figure_is_caught(tmp_path: Path) -> None:
    """Chiều dễ quên: sơ đồ mới chưa xuất thì không có hash nào để lệch."""
    diagrams, figures = _book(tmp_path)
    (diagrams / "b.drawio").write_text("<mxfile/>", encoding="utf-8")
    problems = figure_drift(tmp_path, diagrams, figures, "user guide")
    assert problems == ["docs/diagrams/b.drawio: no figure in the user guide was exported from it"]


def test_diagrams_in_a_subfolder_are_not_the_parent_book_s(tmp_path: Path) -> None:
    """Sơ đồ của hướng dẫn nằm trong thư mục con; cuốn ở thư mục cha không bị đòi in nó."""
    diagrams, figures = _book(tmp_path)
    child = diagrams / "user-guide"
    child.mkdir()
    (child / "c.drawio").write_text("<mxfile/>", encoding="utf-8")
    assert figure_drift(tmp_path, diagrams, figures, "report") == []


def test_a_book_with_no_diagrams_and_no_manifest_passes(tmp_path: Path) -> None:
    """Hướng dẫn chưa vẽ sơ đồ nào thì chưa cần `sources.json`."""
    assert figure_drift(tmp_path, tmp_path / "none", tmp_path / "figures", "user guide") == []


def test_diagrams_without_a_manifest_are_caught(tmp_path: Path) -> None:
    """Có sơ đồ mà không có `sources.json`: không hình nào tin được."""
    diagrams = tmp_path / "d"
    diagrams.mkdir()
    (diagrams / "a.drawio").write_text("<mxfile/>", encoding="utf-8")
    problems = figure_drift(tmp_path, diagrams, tmp_path / "figures", "user guide")
    assert len(problems) == 1 and "is missing" in problems[0]


def test_a_manifest_that_does_not_parse_is_caught(tmp_path: Path) -> None:
    """`sources.json` hỏng thì không hình nào tin được."""
    diagrams, figures = _book(tmp_path)
    (figures / "sources.json").write_text("{không phải json", encoding="utf-8")
    problems = figure_drift(tmp_path, diagrams, figures, "user guide")
    assert len(problems) == 1 and "does not parse" in problems[0]


def test_an_empty_manifest_is_caught(tmp_path: Path) -> None:
    """Manifest rỗng mà có sơ đồ: sơ đồ ấy chưa hình nào được xuất."""
    diagrams, figures = _book(tmp_path)
    (figures / "sources.json").write_text("{}", encoding="utf-8")
    problems = figure_drift(tmp_path, diagrams, figures, "user guide")
    assert len(problems) == 1 and "non-empty" in problems[0]


def test_the_check_watches_the_user_guide_too(tmp_path: Path, monkeypatch) -> None:
    """Nối dây: một sơ đồ của hướng dẫn chưa xuất hình làm check của repo đỏ."""
    import check_contract

    _book(tmp_path)
    guide = tmp_path / "docs" / "diagrams" / "user-guide"
    guide.mkdir()
    (guide / "c.drawio").write_text("<mxfile/>", encoding="utf-8")
    # Cuốn báo cáo của repo giả: hình ở docs/report/figures, như repo thật.
    (tmp_path / "book").rename(tmp_path / "docs" / "report")
    monkeypatch.setattr(check_contract, "REPO_ROOT", tmp_path)
    failure = check_contract.check_every_figure_matches_the_diagram_it_came_from()
    assert failure is not None and "user guide" in failure
