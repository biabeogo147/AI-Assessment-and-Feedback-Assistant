"""One turn of thinking for the teacher's chat, and nothing more.

The three authoring tasks each do a whole job: write an assessment, write a
round's question, answer a student. This one does not. It reads a conversation
and answers **what should happen next** -- say this, call that tool, or ask a
question before doing anything. BE runs the loop and performs the step.

That split is the whole design, and it is why the completed message is named
for a *proposal*. AGENT holds no database credentials, so it cannot execute a
tool; and it must not, because authorisation belongs where the session and the
teacher's identity are. What comes back from here is a suggestion BE is free to
refuse -- which is also what makes ADR-05's rule structural rather than a line
in a prompt: an assistant that can only propose cannot publish anything.

Data only, as everywhere here. Which tools exist, who may call them and what
their arguments mean are BE's business; this module only carries the words.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1

# arq task name. BE enqueues by string and never imports the AGENT package.
PROPOSE_NEXT_STEP_TASK = "propose_next_step"


class ToolSpec(BaseModel):
    """One tool, described for the model rather than for a caller.

    BE builds this list per request from what the asking teacher may do, so a
    tool a teacher cannot use is never described to the model at all. That is a
    convenience and not the gate: BE checks again when it executes, because
    this description is read by a model and a model reads things wrongly.

    Attributes:
        name: The identifier BE dispatches on.
        description: What the tool does, in the language the model is answering
            in, including when *not* to use it.
        arguments: JSON-schema-shaped description of the arguments, as a plain
            mapping. Not a pydantic model, because the catalog is assembled at
            runtime and the shapes differ per tool.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    arguments: dict[str, object] = Field(default_factory=dict)


class TurnRecord(BaseModel):
    """One thing that already happened in this conversation.

    The history is not only the words. A tool result is part of what the model
    knows, so it travels as its own kind of turn rather than being flattened
    into prose -- flattening it would mean the model reads a summary of the
    data instead of the data.

    Attributes:
        kind: Who or what produced this turn.
        text: The words, for `teacher` and `assistant` turns.
        tool_name: Which tool, for `tool_call` and `tool_result`.
        tool_args: The arguments BE executed with.
        tool_result: What the tool returned. Already summarised by BE: a whole
            class's marks would not fit in a prompt and does not need to.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["teacher", "assistant", "tool_call", "tool_result"]
    text: str = ""
    tool_name: str = ""
    tool_args: dict[str, object] = Field(default_factory=dict)
    tool_result: dict[str, object] = Field(default_factory=dict)


class NextStepRequested(BaseModel):
    """Ask AGENT what the next step of this conversation should be.

    Self-contained, like every payload here: the catalog and the history travel
    with the request because AGENT cannot look either of them up.

    Attributes:
        request_id: Correlation id, echoed back.
        teacher_name: How to address the person. Not an identifier -- AGENT
            never receives one it would have to resolve, and identity for
            authorisation stays in BE.
        history: Everything that has happened, oldest first.
        catalog: The tools this teacher may use, on this turn.

    There is no `stream_channel` here, unlike `ExplainTurnRequested`. A turn of
    this conversation is a loop of several model calls and only the last one
    produces words, so a channel opened at the first call would carry silence
    for most of the turn. The event envelope that can say "reading class 12A1"
    is its own piece of work; a field nothing reads would be a promise the
    payload does not keep.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    teacher_name: str = ""
    history: tuple[TurnRecord, ...] = ()
    catalog: tuple[ToolSpec, ...] = ()


class NextStepCompleted(BaseModel):
    """What AGENT proposes doing next.

    Exactly one of three shapes, chosen by `kind`:

    - `say`: answer in words; `text` carries them and the turn ends.
    - `call_tool`: BE should run `tool_name` with `tool_args`, then ask again.
    - `ask_clarify`: there is not enough information to act; `text` is the
      question and `choices` are the options, which must come from data BE
      supplied rather than from the model's imagination.

    `ask_clarify` is the input gate of ADR-05, whose rules -- including what
    a clarifying question may and may not ask for -- live in that decision
    record and are enforced by BE. Repeating them here would put a copy of a
    business rule in a data module, where it would go stale without anything
    failing.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    kind: Literal["say", "call_tool", "ask_clarify"]
    text: str = ""
    tool_name: str = ""
    tool_args: dict[str, object] = Field(default_factory=dict)
    choices: tuple[str, ...] = ()
    # What the call cost, filled in by AGENT from the provider's own usage
    # report **after** the model has answered. The model cannot know this, so
    # whatever it writes here is overwritten -- the same treatment
    # `request_id` gets, and for the same reason.
    model_tokens: int = 0

    @model_validator(mode="after")
    def _a_tool_call_names_a_tool(self) -> "NextStepCompleted":
        """Reject a `call_tool` with no tool in it.

        Shape, not policy: which tools exist is BE's business, but a proposal
        to call nothing is not a proposal. Caught here because the alternative
        is a loop that dispatches on an empty name, gets "no such tool" back,
        and spends its whole ceiling of model calls rediscovering that.

        Returns:
            Self, when the message is coherent.

        Raises:
            ValueError: When `kind` is `call_tool` and `tool_name` is blank.
        """
        if self.kind == "call_tool" and not self.tool_name.strip():
            raise ValueError("kind='call_tool' needs a tool_name")
        return self
