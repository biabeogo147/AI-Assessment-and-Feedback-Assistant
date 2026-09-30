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
async def test_the_mock_asks_which_class_when_the_name_matched_several() -> None:
    """An ambiguous result becomes a question, not a recital of the result.

    ADR-23's whole point is that nobody picks between candidates. The mock has
    to honour that too, or the free way of driving the loop would demonstrate
    the one behaviour the design forbids -- and it is the demo people see.

    It writes no options of its own: BE renders those from the rows it read,
    and a mock that also wrote them would be a second source for the one thing
    ADR-23 says has exactly one.
    """
    answer = await propose_next_step(
        {},
        _payload(
            TurnRecord(kind="teacher", text="lớp 12A thế nào"),
            TurnRecord(kind="tool_call", tool_name="find_class", tool_args={"name": "12A"}),
            TurnRecord(
                kind="tool_result",
                tool_name="find_class",
                tool_result={
                    "found": False,
                    "ambiguous": True,
                    "candidates": [
                        {"class_id": "c-1", "name": "12A", "student_count": 3},
                        {"class_id": "c-2", "name": "12A", "student_count": 2},
                    ],
                },
            ),
        ),
    )

    assert answer["kind"] == "ask_clarify"
    assert answer["text"]
    assert answer["choices"] == []


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
async def test_the_mock_finds_a_name_written_against_the_word_lop() -> None:
    """ "lớp12A" names a class, and BE can resolve it.

    The mock's extractor needed a word boundary before the digits, so it saw
    nothing here and asked which class -- while BE, given the chance, resolves
    that spelling fine. The two halves disagreeing makes a demo look like a
    resolution bug that is not there.
    """
    asked = _payload(TurnRecord(kind="teacher", text="lớp12A thế nào"))
    answer = await propose_next_step({}, asked)

    assert answer["kind"] == "call_tool"
    assert answer["tool_args"] == {"name": "12A"}


@pytest.mark.asyncio
async def test_the_mock_still_ignores_numbers_that_are_not_class_names() -> None:
    """Loosening the boundary must not turn durations and years into classes.

    "15 phút" and "2026" sit in the same sentences as class names, and a mock
    that looked one up would send the loop after a class nobody mentioned.
    """
    for text in ("bài 15 phút hôm qua thế nào", "năm 2026 có mấy bài", "còn 2 câu chưa chữa"):
        answer = await propose_next_step({}, _payload(TurnRecord(kind="teacher", text=text)))
        assert answer["kind"] == "ask_clarify", text


@pytest.mark.asyncio
async def test_the_mock_asks_back_when_no_class_was_named() -> None:
    """Nothing to look up and nothing to answer means asking.

    ADR-05's input gate in its cheapest form: the mock has no way to guess
    which class is meant, so it does not.
    """
    answer = await propose_next_step({}, _payload(TurnRecord(kind="teacher", text="tình hình sao")))

    assert answer["kind"] == "ask_clarify"
    assert answer["text"]
