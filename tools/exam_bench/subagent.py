"""Panel chấm bằng subagent Claude Code thay cho panel API (plan `bench-two-models` pha 5b).

Tài khoản Anthropic hết credit, nên người dùng chốt (15/11/2026): rater là **3 subagent Sonnet,
effort `medium`**, chạy trong phiên Claude Code. Chỉ hai model sinh đề còn gọi API.

`rate_paper` không đổi: nó xin `panel.all_three(kind, content)`, và `TaskPanel` đứng vào chỗ
`rate.Panel`. Không gọi model nào:

- **xuất** (`export`): ghi mỗi lời chấm thành một tác vụ (mã băm của loại và nội dung), trả phiếu
  trống. Tác vụ chia hai đợt: `blind` chỉ có lời giải mù (`solve` -- đề không kèm khoá), `keyed` có
  dàn ý, lời chia việc và lời duyệt (lời duyệt có khoá). Đợt `blind` chấm xong mới mở đợt `keyed`,
  để không subagent nào giải mù một câu mà đã thấy khoá của nó.
- **nhập** (`import`): đọc phiếu subagent ghi, kiểm bằng đúng schema của `rate.py`, trả phiếu theo
  mã tác vụ. Phiếu hỏng hay thiếu là phiếu trống -- như rater API trả hỏng.

Lời dặn subagent: `tools/exam_bench/subagent_rater.md`. Kiểm một tệp phiếu (subagent tự chạy):
    PYTHONPATH=tools python -X utf8 -m exam_bench.subagent validate <tệp tác vụ> <tệp phiếu>
"""

import hashlib
import json
import sys
from pathlib import Path

from exam_bench import rate

# Ba subagent Sonnet: cùng một model, ba lượt độc lập (không chung ngữ cảnh). Độc lập kém panel ba
# model khác nhau -- lỗi dễ trùng, đồng thuận dễ cao hơn thật; ghi ở `grading-design.md`.
SUBAGENT_RATERS = ("sonnet-1", "sonnet-2", "sonnet-3")
PANEL_NOTE = "3 subagent Claude Code, model sonnet, effort medium, mỗi rater chấm độc lập"

# Đợt nào chứa loại lời chấm nào. `solve` là lời giải mù: không kèm khoá, nên đi riêng và đi trước.
PHASES = {"blind": ("solve",), "keyed": ("outline", "split", "review")}


def task_id(kind: str, content: str) -> str:
    """Mã một tác vụ chấm: băm loại và nội dung. Hàm thuần.

    Cùng nội dung là cùng tác vụ, nên hai đề trùng một câu chỉ chấm một lần -- như cache của panel
    API (`rate.cache_key`), trừ phần model: ở đây model là chính subagent.
    """
    return hashlib.sha256(f"{kind}\n{content}".encode()).hexdigest()[:16]


def phase_of(kind: str) -> str:
    """Đợt của một loại lời chấm. Hàm thuần."""
    return next(name for name, kinds in PHASES.items() if kind in kinds)


class TaskPanel:
    """Đứng vào chỗ `rate.Panel`: ghi tác vụ, và trả phiếu đã có thay vì gọi model.

    Attributes:
        tasks: Mã tác vụ → `{task_id, kind, case, content}`, theo thứ tự gặp.
        verdicts: `(rater, mã tác vụ)` → phiếu đã kiểm.
    """

    def __init__(self, verdicts: dict[tuple[str, str], dict] | None = None) -> None:
        self.tasks: dict[str, dict] = {}
        self.verdicts = verdicts or {}
        self.case = ""

    async def all_three(self, kind: str, content: str) -> list[dict | None]:
        """Như `rate.Panel.all_three`: ba phiếu theo thứ tự `rate.RATERS`, `None` khi chưa có."""
        key = task_id(kind, content)
        self.tasks.setdefault(
            key, {"task_id": key, "kind": kind, "case": self.case, "content": content}
        )
        return [self.verdicts.get((rater, key)) for rater in rate.RATERS]


def schemas() -> dict[str, dict]:
    """Lời dặn hệ thống và JSON schema của từng loại lời chấm -- đúng thứ rater API nhận."""
    return {
        kind: {"system": system, "schema": model.model_json_schema()}
        for kind, (system, model) in rate._KINDS.items()
    }


def write_tasks(folder: Path, tasks: dict[str, dict]) -> dict[str, list[Path]]:
    """Ghi tác vụ thành tệp theo đợt và theo ca, cùng `schemas.json`.

    Args:
        folder: Thư mục `rating/` của lượt.
        tasks: `TaskPanel.tasks`.

    Returns:
        Đợt → các tệp tác vụ, mỗi ca một tệp (một subagent chấm một tệp).
    """
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "schemas.json").write_text(
        json.dumps(schemas(), ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
    )
    grouped: dict[tuple[str, str], list[dict]] = {}
    for task in tasks.values():
        grouped.setdefault((phase_of(task["kind"]), task["case"]), []).append(task)
    written: dict[str, list[Path]] = {}
    for (phase, case), these in sorted(grouped.items()):
        path = folder / phase / f"{case}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for task in these:
                handle.write(json.dumps(task, ensure_ascii=False) + "\n")
        written.setdefault(phase, []).append(path)
    return written


def check(kind: str, raw: object) -> dict | None:
    """Kiểm một phiếu bằng schema của loại ấy. Trả phiếu đã chuẩn hoá, hay `None` khi hỏng."""
    _, model = rate._KINDS[kind]
    try:
        return model.model_validate(raw).model_dump(mode="json")
    except Exception:  # noqa: BLE001 -- phiếu hỏng là phiếu trống, như rater API trả hỏng
        return None


def read_verdicts(folder: Path, tasks: dict[str, dict]) -> tuple[dict, dict[str, int]]:
    """Đọc phiếu của mọi subagent: `verdicts/<rater>/*.jsonl`, mỗi dòng `{task_id, verdict}`.

    Args:
        folder: Thư mục `rating/` của lượt.
        tasks: Mã tác vụ → tác vụ (để biết loại, và bỏ dòng mang mã lạ).

    Returns:
        `(rater, mã tác vụ)` → phiếu đã kiểm (kèm `_model` là tên rater), và số đếm: phiếu nhận,
        phiếu hỏng, mã lạ, tác vụ thiếu phiếu.
    """
    verdicts: dict[tuple[str, str], dict] = {}
    counts = {"nhận": 0, "hỏng": 0, "mã lạ": 0, "trùng": 0, "thiếu": 0}
    for rater in rate.RATERS:
        for path in sorted((folder / "verdicts" / rater).glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    counts["hỏng"] += 1
                    continue
                if not isinstance(row, dict):
                    counts["hỏng"] += 1
                    continue
                task = tasks.get(str(row.get("task_id")))
                if task is None:
                    counts["mã lạ"] += 1
                    continue
                if (rater, task["task_id"]) in verdicts:
                    # Một tác vụ hai phiếu: giữ phiếu đầu, không đếm hai lần.
                    counts["trùng"] += 1
                    continue
                verdict = check(task["kind"], row.get("verdict"))
                if verdict is None:
                    counts["hỏng"] += 1
                    continue
                verdict["_model"] = rater
                verdicts[(rater, task["task_id"])] = verdict
                counts["nhận"] += 1
        counts["thiếu"] += sum((rater, key) not in verdicts for key in tasks)
    return verdicts, counts


def read_tasks(folder: Path) -> dict[str, dict]:
    """Mọi tác vụ đã xuất của một lượt, theo mã."""
    tasks: dict[str, dict] = {}
    for path in sorted(folder.glob("*/*.jsonl")):
        if path.parent.name not in PHASES:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                task = json.loads(line)
                tasks[task["task_id"]] = task
    return tasks


def validate(tasks_path: Path, verdicts_path: Path) -> list[str]:
    """Lỗi của một tệp phiếu so với tệp tác vụ của nó: dòng hỏng, mã lạ, phiếu sai schema, thiếu.

    Subagent tự chạy trước khi báo xong, để sửa ngay chứ không để thành phiếu trống.
    """
    tasks = {
        (task := json.loads(line))["task_id"]: task
        for line in tasks_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    errors: list[str] = []
    seen: set[str] = set()
    if not verdicts_path.exists():
        return [f"chưa có tệp {verdicts_path}"]
    for number, line in enumerate(verdicts_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"dòng {number}: không phải JSON ({exc.msg})")
            continue
        if not isinstance(row, dict):
            errors.append(f"dòng {number}: phải là một object {{task_id, verdict}}")
            continue
        key = str(row.get("task_id"))
        if key in seen:
            errors.append(f"dòng {number}: task_id {key} có phiếu lần hai")
            continue
        if key not in tasks:
            errors.append(f"dòng {number}: task_id {key!r} không có trong tệp tác vụ")
            continue
        _, model = rate._KINDS[tasks[key]["kind"]]
        try:
            model.model_validate(row.get("verdict"))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"dòng {number} ({key}): sai schema {tasks[key]['kind']}: {exc}"[:400])
            continue
        seen.add(key)
    errors += [f"thiếu phiếu cho task_id {key}" for key in tasks if key not in seen]
    return errors


def main() -> None:
    """`validate <tệp tác vụ> <tệp phiếu>`: in lỗi, mã thoát 1 khi có lỗi."""
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 4 or sys.argv[1] != "validate":
        raise SystemExit("dùng: python -m exam_bench.subagent validate <tệp tác vụ> <tệp phiếu>")
    errors = validate(Path(sys.argv[2]), Path(sys.argv[3]))
    for error in errors:
        print(error)
    print("đạt" if not errors else f"{len(errors)} lỗi")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
