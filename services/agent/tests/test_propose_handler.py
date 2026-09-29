"""The prepared proposals AGENT makes when no model is configured.

The mock exists so the loop can be driven end to end for free. That matters
more here than for the other tasks: a tool loop has a shape -- ask, run, ask
again, answer -- and a mock that only ever said one sentence would leave that
shape untested until the first paid run.

So these tests assert the shape, not the wording. What must hold is that the
mock asks for a tool when it has no data and stops asking once the data has
arrived, because those two together are what makes the loop terminate.
"""

import pytest

from agent import llm
from agent.handlers import propose_next_step
from contracts import NextStepRequested, ToolSpec, TurnRecord


@pytest.fixture(autouse=True)
def off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Take the mock path on purpose, not by accident.

    Without this these tests depended on the machine's `.env`. On a machine
    with `LLM_ENABLED=true` and a model id -- which is every machine that has
    run the thing for real -- `propose_next_step` took the model path, failed,
    and returned the mock from its exception handler. Still green, but green
    through the recovery path instead of the one under test, and one bad
    argument away from spending money to assert a prepared sentence.
    """
    monkeypatch.setattr(llm, "enabled", lambda: False)


_CATALOG = (
    ToolSpec(name="find_class", description="Tìm lớp theo tên.", arguments={"name": "tên lớp"}),
)


def _payload(*history: TurnRecord, catalog: tuple[ToolSpec, ...] = _CATALOG) -> dict:
    return NextStepRequested(request_id="r1", history=history, catalog=catalog).model_dump(
        mode="json"
    )


@pytest.mark.asyncio
async def test_the_mock_asks_for_a_class_it_was_told_about() -> None:
    """A class name in the question becomes a tool call with that name.

    Passing the name through matters: a mock that called `find_class` with a
    hard-coded argument would make the loop look right while proving nothing
    about whether arguments survive the round trip.
    """
    asked = _payload(TurnRecord(kind="teacher", text="lớp 12A1 thế nào"))
    answer = await propose_next_step({}, asked)

    assert answer["kind"] == "call_tool"
    assert answer["tool_name"] == "find_class"
    assert answer["tool_args"] == {"name": "12A1"}


@pytest.mark.asyncio
async def test_the_mock_stops_asking_once_the_result_is_in() -> None:
    """With a tool result in the history, the mock answers instead of asking.

    This is the terminating condition. Without it the loop would run to its
    ceiling on every turn, and the ceiling would look like the normal case.
    """
    answer = await propose_next_step(
        {},
        _payload(
            TurnRecord(kind="teacher", text="lớp 12A1 thế nào"),
            TurnRecord(kind="tool_call", tool_name="find_class", tool_args={"name": "12A1"}),
            TurnRecord(kind="tool_result", tool_name="find_class", tool_result={"name": "12A1"}),
        ),
    )

    assert answer["kind"] == "say"
    assert answer["text"]


@pytest.mark.asyncio
async def test_the_mock_never_proposes_a_tool_it_was_not_given() -> None:
    """An empty catalog means words only.

    BE builds the catalog from what this teacher may do, so a proposal naming
    a tool outside it is a proposal BE must refuse -- and a mock that produced
    one would be training the loop's error path instead of its happy path.
    """
    answer = await propose_next_step(
        {}, _payload(TurnRecord(kind="teacher", text="lớp 12A1 thế nào"), catalog=())
    )

    assert answer["kind"] in {"say", "ask_clarify"}
    assert not answer["tool_name"]


@pytest.mark.asyncio
async def test_the_mock_asks_back_when_no_class_was_named() -> None:
    """Nothing to look up and nothing to answer means asking.

    ADR-05's input gate in its cheapest form: the mock has no way to guess
    which class is meant, so it does not.
    """
    answer = await propose_next_step({}, _payload(TurnRecord(kind="teacher", text="tình hình sao")))

    assert answer["kind"] == "ask_clarify"
    assert answer["text"]
