"""Luật *docs Markdown vẽ bằng Mermaid, không link `.drawio`* (plan `agent-design-doc-mermaid`).

Chỉ phần thuần được canh ở đây: chữ Markdown vào, số dòng ra.
"""

import pytest

from check_contract import drawio_links


@pytest.mark.parametrize(
    "line",
    [
        "- [System Architecture Diagram](../diagrams/system-architecture.drawio)",
        "Xem [sơ đồ](docs/diagrams/use-case.drawio#trang-2) trước.",
        "[a](x.drawio) và [b](y.md)",
        '[x](a.drawio "tiêu đề")',
        "[x](<a b.drawio>)",
        "[x]( a.drawio )",
        "[x](A.DRAWIO?raw=1)",
        "[hình]: ../diagrams/a.drawio",
        '<a href="../diagrams/a.drawio">hình</a>',
    ],
)
def test_a_link_to_a_drawio_is_caught(line: str) -> None:
    """Link tương đối, link có mảnh `#`, link đứng giữa câu: đều là link."""
    assert drawio_links(line) == [1]


@pytest.mark.parametrize(
    "line",
    [
        # ADR ghi lại một hình bằng tên tệp trong backtick: lời ghi lại, không phải sơ đồ.
        "- `docs/diagrams/business-workflows.drawio` — `t-publish` nằm trong lane Teacher.",
        "`.drawio` files are the figures of the course report only.",
        "[bản vẽ](../diagrams/README.md)",
        # Link viết trong code là ví dụ, không phải link.
        "Đừng viết `[x](a.drawio)` trong docs.",
    ],
)
def test_a_drawio_named_but_not_linked_passes(line: str) -> None:
    """Nhắc tên `.drawio` mà không link thì không vi phạm."""
    assert drawio_links(line) == []


def test_a_link_inside_a_code_fence_is_an_example() -> None:
    """Khối code (vd. ví dụ trong tài liệu luật) không phải link."""
    assert drawio_links("```markdown\n[x](a.drawio)\n```\n[y](b.drawio)\n") == [4]


def test_the_line_numbers_are_the_lines_that_link() -> None:
    """Báo đúng dòng có link, đếm từ 1, để người sửa đi thẳng tới đó."""
    text = "# Tiêu đề\n\n[x](a.drawio)\nchữ\n[y](b.drawio)\n"

    assert drawio_links(text) == [3, 5]
