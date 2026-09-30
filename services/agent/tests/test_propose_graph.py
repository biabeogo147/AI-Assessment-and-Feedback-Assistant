"""What AGENT proposes for one turn of the teacher's chat.

These tests assert two kinds of thing and nothing else. First, that a proposal
travels back unchanged: the tool name and its arguments are what BE dispatches
on, so a graph that reshaped them would send the teacher's request somewhere
else. Second, that the model is actually told what it needs -- the tools it may
use and what earlier tools returned -- because a model asked to choose from a
catalog it cannot see will invent one.

What is deliberately not tested here is whether a proposal is *allowed*. AGENT
cannot know that: the teacher's identity and the database are on BE's side of
the wall. Those tests live with the executor.
"""

from types import SimpleNamespace

import pytest
from langchain_core.runnables import Runnable, RunnableLambda

from agent import llm
from agent.graphs.propose import propose
from contracts import NextStepCompleted, NextStepRequested, ToolSpec, TurnRecord

_CATALOG = (
    ToolSpec(
        name="find_class",
        description="Tìm lớp của giáo viên theo tên.",
        arguments={"name": "tên lớp, ví dụ 12A1"},
    ),
    ToolSpec(
        name="class_assessment_summary",
        description="Tóm tắt kết quả một bài kiểm tra trong một lớp.",
        arguments={"class_id": "id lớp", "assessment_id": "id đề"},
    ),
)


class Scripted:
    """A chat model answering with queued proposals, recording its prompts.

    Modelled on the fake in `test_authoring_graph.py` rather than on
    `GenericFakeChatModel`, which raises `NotImplementedError` from
    `with_structured_output` and so cannot stand in for a structured call.
    """

    def __init__(self, answers: list[NextStepCompleted]) -> None:
        self.answers = answers
        self.prompts: list[str] = []

    def with_structured_output(self, schema: object, **kwargs: object) -> Runnable:
        """Return a runnable handing back the next queued proposal."""

        def answer(messages: object) -> NextStepCompleted:
            self.prompts.append("\n".join(message.text for message in messages))
            return self.answers.pop(0)

        return RunnableLambda(answer)


def _said(text: str) -> NextStepCompleted:
    return NextStepCompleted(request_id="r1", kind="say", text=text)


def _wants(tool: str, **args: object) -> NextStepCompleted:
    return NextStepCompleted(request_id="r1", kind="call_tool", tool_name=tool, tool_args=args)


@pytest.fixture
def on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn the model path on without needing a credential."""
    monkeypatch.setattr(llm, "enabled", lambda: True)


def _asked(text: str) -> NextStepRequested:
    return NextStepRequested(
        request_id="r1",
        teacher_name="Cô Lan",
        history=(TurnRecord(kind="teacher", text=text),),
        catalog=_CATALOG,
    )


@pytest.mark.asyncio
async def test_a_tool_proposal_keeps_its_name_and_arguments(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """BE dispatches on these two fields, so nothing may rewrite them."""
    model = Scripted([_wants("find_class", name="12A1")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("lớp 12A1 làm bài hôm qua thế nào"))

    assert step.kind == "call_tool"
    assert step.tool_name == "find_class"
    assert step.tool_args == {"name": "12A1"}


@pytest.mark.asyncio
async def test_the_model_is_told_which_tools_it_may_use(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """A catalog the model cannot see is a catalog it will invent.

    The names travel because BE dispatches on them; the descriptions travel
    because choosing between two tools is the decision being asked for.
    """
    model = Scripted([_said("vâng")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    await propose(_asked("chào"))

    prompt = model.prompts[0]
    assert "find_class" in prompt
    assert "class_assessment_summary" in prompt
    assert "Tóm tắt kết quả một bài kiểm tra" in prompt


@pytest.mark.asyncio
async def test_a_tool_result_reaches_the_model_as_data(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """What a tool returned is part of what the model knows.

    This is the whole reason the loop sends the history back every round. If
    the result did not arrive, the model would propose the same tool again and
    the turn would spin until the ceiling stopped it.
    """
    model = Scripted([_said("Lớp 12A1 trung bình 6,5.")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    asked = NextStepRequested(
        request_id="r1",
        history=(
            TurnRecord(kind="teacher", text="lớp 12A1 thế nào"),
            TurnRecord(kind="tool_call", tool_name="find_class", tool_args={"name": "12A1"}),
            TurnRecord(
                kind="tool_result",
                tool_name="find_class",
                tool_result={"class_id": "c-1", "name": "12A1", "student_count": 40},
            ),
        ),
        catalog=_CATALOG,
    )

    await propose(asked)

    prompt = model.prompts[0]
    assert "12A1" in prompt
    assert "40" in prompt


@pytest.mark.asyncio
async def test_the_request_id_comes_back_on_the_proposal(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """BE correlates the answer with the question it asked.

    The model does not know the id and must not be trusted with it: a proposal
    carrying whatever id the model echoed would be attributed to another
    turn's job.
    """
    model = Scripted([NextStepCompleted(request_id="model-made-this-up", kind="say", text="ừ")])
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("chào"))

    assert step.request_id == "r1"


class WithUsage:
    """A chat model answering in the `include_raw` shape, with a usage report.

    `Scripted` above ignores `include_raw` and hands the parsed object back
    directly, which is a shape real providers also produce when they cannot
    report usage. This one is the other shape, and it exists because the
    token count is a claim about a library -- and claims about libraries in
    this plan have been wrong three times when nothing measured them.
    """

    def __init__(self, step: NextStepCompleted, total_tokens: int | None) -> None:
        self.step = step
        self.total_tokens = total_tokens

    def with_structured_output(self, schema: object, **kwargs: object) -> Runnable:
        assert kwargs.get("include_raw") is True

        usage = None if self.total_tokens is None else {"total_tokens": self.total_tokens}
        raw = SimpleNamespace(usage_metadata=usage)

        return RunnableLambda(lambda messages: {"parsed": self.step, "raw": raw})


@pytest.mark.asyncio
async def test_the_token_count_comes_from_the_provider(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """What the call cost is read off the response, not off the proposal.

    The model fills the schema, so a field it can write is a field it will
    write -- and a token count it invented would be worse than none, because
    it would look like a measurement.
    """
    model = WithUsage(
        NextStepCompleted(request_id="x", kind="say", text="ừ", model_tokens=999_999), 1234
    )
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("chào"))

    assert step.model_tokens == 1234


@pytest.mark.asyncio
async def test_a_provider_that_reports_no_usage_costs_zero_not_a_crash(
    monkeypatch: pytest.MonkeyPatch, on: None
) -> None:
    """Zero means "not told", and the turn still happens.

    Gemini is the configured fallback and does not always report usage. A
    missing count must not take the answer down with it.
    """
    model = WithUsage(NextStepCompleted(request_id="x", kind="say", text="ừ"), None)
    monkeypatch.setattr(llm, "chat_models", lambda: (model,))

    step = await propose(_asked("chào"))

    assert step.kind == "say"
    assert step.model_tokens == 0
