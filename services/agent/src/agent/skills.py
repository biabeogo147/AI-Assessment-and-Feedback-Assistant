"""Skill của Kriky: những lời dặn chỉ một loại việc cần, nạp khi việc ấy tới
(`kriky-skill-routing`).

Mỗi skill là một file Markdown trong `agent/skills/`, đầu file là một frontmatter hai dòng:

- `name`: tên skill, trùng tên file.
- `description`: **tiếng Anh**, và nó chính là `criteria` Jev đọc để quyết skill có áp dụng không
  (`skill_router.py`). Một nguồn sự thật cho câu *"khi nào skill này dùng"* -- không có bản sao thứ
  hai trong code để lệch nhau. Tiếng Anh vì Jev 1.13 kém hơn với ngôn ngữ khác
  (`document-agent-hierarchy`).

Thân file là tiếng Việt: đó là lời dặn Kriky đọc. Luật an toàn **không** bao giờ nằm ở đây -- Jev
chọn sai thì một skill vắng mặt, nên mọi luật mà vắng nó là nguy hiểm thuộc về lõi (`CORE` của
`graphs/propose/prompt.py`).
"""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

_HOME = Path(__file__).resolve().parent / "skills"

# Skill bao quát: nạp khi không skill chuyên biệt nào khớp. Nó đứng ngoài câu hỏi gửi Jev -- Jev chỉ
# được hỏi về các skill chuyên biệt, nên "không skill nào" luôn có một chỗ để rơi vào.
GENERAL = "tro-chuyen-chung"


@dataclass(frozen=True)
class Skill:
    """Một skill đã đọc từ đĩa.

    Attributes:
        name: Tên, trùng tên file.
        description: Câu tiếng Anh nói khi nào skill áp dụng -- `criteria` của Jev.
        body: Lời dặn tiếng Việt chèn vào prompt.
    """

    name: str
    description: str
    body: str


def _parse(path: Path) -> Skill:
    """Đọc một file skill.

    Args:
        path: File `.md`.

    Returns:
        Skill.

    Raises:
        ValueError: Thiếu frontmatter, thiếu một trong hai khoá, hoặc `name` lệch tên file.
    """
    text = path.read_text(encoding="utf-8")
    head, separator, body = text.removeprefix("---\n").partition("\n---\n")
    if not text.startswith("---\n") or not separator:
        raise ValueError(f"{path.name}: no frontmatter")
    fields = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    name, description = fields.get("name", ""), fields.get("description", "")
    if not name or not description:
        raise ValueError(f"{path.name}: frontmatter needs name and description")
    if name != path.stem:
        raise ValueError(f"{path.name}: name {name!r} does not match the file")
    return Skill(name=name, description=description, body=body.strip())


@cache
def every() -> tuple[Skill, ...]:
    """Mọi skill, theo thứ tự tên -- thứ tự cố định để prompt không đổi giữa hai lần chạy.

    Returns:
        Các skill.
    """
    return tuple(_parse(path) for path in sorted(_HOME.glob("*.md")))


def named(names: tuple[str, ...]) -> tuple[Skill, ...]:
    """Các skill mang những tên này, theo thứ tự của `every()`.

    Args:
        names: Tên skill.

    Returns:
        Các skill tìm được; tên lạ bị bỏ qua.
    """
    wanted = set(names)
    return tuple(skill for skill in every() if skill.name in wanted)
