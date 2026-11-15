"""Panel subagent của `exam_bench` (plan `bench-two-models` pha 5b): xuất tác vụ, nhập phiếu."""

import asyncio
import json
from pathlib import Path

import pytest

from exam_bench import rate, subagent


@pytest.fixture
def panel_of_subagents(monkeypatch: pytest.MonkeyPatch) -> tuple[str, ...]:
    monkeypatch.setattr(rate, "RATERS", subagent.SUBAGENT_RATERS)
    return subagent.SUBAGENT_RATERS


def _solve_verdict() -> dict:
    """Một phiếu `solve` hợp schema, dựng từ ví dụ JSON schema của chính `SolveVerdict`."""
    schema = rate.SolveVerdict.model_json_schema()
    sample = _sample(schema, schema)
    return rate.SolveVerdict.model_validate(sample).model_dump(mode="json")


def _sample(node: dict, root: dict) -> object:
    """Một giá trị hợp lệ tối thiểu cho một nút JSON schema (đủ cho các phiếu của `rate.py`)."""
    if "$ref" in node:
        return _sample(root["$defs"][node["$ref"].split("/")[-1]], root)
    if "anyOf" in node:
        return _sample(node["anyOf"][0], root)
    if "enum" in node:
        return node["enum"][0]
    kind = node.get("type")
    if kind == "object":
        return {key: _sample(value, root) for key, value in node.get("properties", {}).items()}
    if kind == "array":
        return [_sample(node["items"], root)] * max(1, node.get("minItems", 1))
    return {"string": "x", "integer": 1, "number": 1.0, "boolean": True, "null": None}[kind]


def test_the_blind_phase_holds_only_solves_and_the_keyed_phase_the_rest() -> None:
    """Lời giải mù đi riêng, trước: không subagent nào giải một câu mà đã thấy khoá của nó."""
    assert subagent.phase_of("solve") == "blind"
    assert {subagent.phase_of(kind) for kind in ("outline", "split", "review")} == {"keyed"}
    assert set(subagent.PHASES["blind"]) | set(subagent.PHASES["keyed"]) == set(rate._KINDS)


@pytest.mark.asyncio
async def test_exporting_records_each_task_once_and_votes_nothing(panel_of_subagents) -> None:
    panel = subagent.TaskPanel()
    panel.case = "c1"

    first = await panel.all_three("solve", "đề một")
    again = await panel.all_three("solve", "đề một")
    await panel.all_three("review", "đề một")

    assert first == again == [None, None, None]
    # Cùng nội dung, khác loại, là hai tác vụ; cùng cả hai thì là một.
    assert len(panel.tasks) == 2
    assert {task["case"] for task in panel.tasks.values()} == {"c1"}


def test_a_round_trip_returns_each_raters_own_checked_verdict(
    tmp_path: Path, panel_of_subagents
) -> None:
    """Xuất, ba subagent ghi phiếu, nhập: mỗi rater nhận đúng phiếu của mình; phiếu sai schema,
    dòng hỏng và mã lạ là phiếu trống, và được đếm."""
    panel = subagent.TaskPanel()
    panel.case = "c1"
    asyncio.run(panel.all_three("solve", "đề một"))
    asyncio.run(panel.all_three("solve", "đề hai"))
    written = subagent.write_tasks(tmp_path, panel.tasks)
    tasks = subagent.read_tasks(tmp_path)
    one, two = (subagent.task_id("solve", text) for text in ("đề một", "đề hai"))
    assert [path.name for path in written["blind"]] == ["c1.jsonl"] and set(tasks) == {one, two}

    def write(rater: str, lines: list[str]) -> None:
        path = tmp_path / "verdicts" / rater / "blind-c1.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    good = _solve_verdict()
    write(
        "sonnet-1",
        [
            json.dumps({"task_id": one, "verdict": good}),
            json.dumps({"task_id": two, "verdict": good}),
        ],
    )
    write(
        "sonnet-2",
        [json.dumps({"task_id": one, "verdict": {"options": "sai"}}), "không phải json"],
    )
    write(
        "sonnet-3",
        [
            json.dumps({"task_id": "lạ", "verdict": good}),
            json.dumps({"task_id": two, "verdict": good}),
        ],
    )

    verdicts, counts = subagent.read_verdicts(tmp_path, tasks)
    votes = asyncio.run(subagent.TaskPanel(verdicts).all_three("solve", "đề hai"))

    assert [vote and vote["_model"] for vote in votes] == ["sonnet-1", None, "sonnet-3"]
    assert counts == {"nhận": 3, "hỏng": 2, "mã lạ": 1, "trùng": 0, "thiếu": 3}


def test_a_second_verdict_or_a_non_object_line_is_not_counted_as_received(
    tmp_path: Path, panel_of_subagents
) -> None:
    """Review pha 5b: phiếu lần hai không đếm hai lần; dòng `[]` là phiếu hỏng, không làm vỡ
    lệnh."""
    panel = subagent.TaskPanel()
    panel.case = "c1"
    asyncio.run(panel.all_three("solve", "đề một"))
    subagent.write_tasks(tmp_path, panel.tasks)
    tasks = subagent.read_tasks(tmp_path)
    (one,) = tasks
    path = tmp_path / "verdicts" / "sonnet-1" / "blind-c1.jsonl"
    path.parent.mkdir(parents=True)
    line = json.dumps({"task_id": one, "verdict": _solve_verdict()})
    path.write_text(f"{line}\n{line}\n[]\n", encoding="utf-8")

    _, counts = subagent.read_verdicts(tmp_path, tasks)

    assert (counts["nhận"], counts["trùng"], counts["hỏng"]) == (1, 1, 1)


class APITimeoutError(Exception):
    """Cùng tên lớp lỗi hạ tầng của SDK: `run._infra` đọc tên."""


@pytest.mark.asyncio
async def test_an_outline_call_lost_to_the_network_is_retried_like_the_agent_does() -> None:
    """Pha 6b: AGENT thử lại một job tới `LLM_MAX_ATTEMPTS` lần; bench gọi thẳng `propose` nên tự
    thử lại lỗi hạ tầng, và chỉ lỗi hạ tầng."""
    from exam_bench import run

    calls: list[str] = []

    async def flaky(request: str) -> str:
        calls.append(request)
        if len(calls) < 3:
            raise APITimeoutError()
        return "dàn ý"

    notes: dict = {}
    assert await run._propose_like_agent(flaky, "lời xin", notes) == "dàn ý"
    assert len(calls) == 3 and notes["infra_retries"] == 2

    async def broken(request: str) -> str:
        raise ValueError("không phải hạ tầng")

    with pytest.raises(ValueError):
        await run._propose_like_agent(broken, "lời xin", {})


@pytest.mark.asyncio
async def test_an_outline_still_lost_after_every_retry_is_an_unrated_paper(monkeypatch) -> None:
    """Hết lần thử mà vẫn lỗi hạ tầng: đề chưa đo được, không làm đổ cả lượt."""
    from exam_bench import run

    async def lost(case: dict) -> tuple:
        raise APITimeoutError()

    monkeypatch.setattr(run, "outline_of", lost)

    paper = await run.agent_paper({"id": "c", "grade": "6", "count": 2, "ask": "x"})

    assert paper["infra"] == "hạ tầng: APITimeoutError" and paper["questions"] == []


def test_a_gateway_with_the_api_panel_is_refused_before_anything_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review pha 5b: `--via` đặt base URL và key của cổng vào môi trường, và SDK của panel API đọc
    chúng -- rater sẽ đi qua cổng mà lời thử không canh."""
    import sys

    from exam_bench import run

    monkeypatch.setattr(
        sys,
        "argv",
        ["exam_bench", "--label", "x", "--model", "openai:gpt-6-luna", "--via", "stali"],
    )
    with pytest.raises(SystemExit, match="--via chỉ dùng"):
        run.main()


def test_a_generator_is_refused_by_the_real_name_of_a_rater_even_under_subagent_names(
    panel_of_subagents,
) -> None:
    """Review pha 5b: `RATERS` thành `sonnet-N` khi chấm bằng subagent; Sonnet vẫn không được tự
    chấm đề của mình."""
    from exam_bench import run

    with pytest.raises(SystemExit, match="rater"):
        run.check_generator("claude-sonnet-5-5")


def test_validate_names_every_line_a_subagent_must_fix(tmp_path: Path) -> None:
    tasks = tmp_path / "blind" / "c1.jsonl"
    tasks.parent.mkdir()
    rows = [
        {"task_id": "a", "kind": "solve", "case": "c1", "content": "x"},
        {"task_id": "b", "kind": "solve", "case": "c1", "content": "y"},
    ]
    tasks.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    verdicts = tmp_path / "v.jsonl"
    verdicts.write_text(
        json.dumps({"task_id": "a", "verdict": {"options": "sai"}}) + "\n" + "{hỏng\n",
        encoding="utf-8",
    )

    errors = subagent.validate(tasks, verdicts)

    assert any("dòng 1" in error and "sai schema" in error for error in errors)
    assert any("dòng 2" in error and "không phải JSON" in error for error in errors)
    assert any("thiếu phiếu cho task_id b" in error for error in errors)
    good = _solve_verdict()
    verdicts.write_text(
        "\n".join(json.dumps({"task_id": key, "verdict": good}) for key in "ab") + "\n",
        encoding="utf-8",
    )
    assert subagent.validate(tasks, verdicts) == []


def test_the_schemas_a_subagent_reads_are_the_api_raters_own() -> None:
    """Cùng lời dặn, cùng schema với rater API: đổi panel không đổi câu hỏi."""
    given = subagent.schemas()
    for kind, (system, model) in rate._KINDS.items():
        assert given[kind]["system"] == system
        assert given[kind]["schema"] == model.model_json_schema()
