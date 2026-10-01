"""Messages for the three authoring tasks BE hands to AGENT.

Data only, like every module here. In particular the rules ADR-18 places on a
generated question -- exactly one correct option, an error label on every
distractor, at least two solution methods -- are **not** validated here. They
are business rules, and BE owns them: a check living in this module would be a
rule neither service owns, and AGENT importing it would let the generator grade
its own homework.

Every payload is self-contained. No field here is an identifier AGENT would have
to resolve against a database, because AGENT holds no database credentials.
"""

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

# arq task names. BE enqueues by string and never imports the AGENT package.
WRITE_DRAFT_QUESTION_TASK = "write_draft_question"
GENERATE_RETRY_QUESTION_TASK = "generate_retry_question"
EXPLAIN_TURN_TASK = "explain_turn"


class GeneratedOption(BaseModel):
    """One answer option as AGENT wrote it.

    Attributes:
        label: The letter shown to the student, "A" upward.
        text: The option itself.
        is_correct: True for the single correct option. AGENT asserts this;
            BE verifies exactly one option per question carries it.
        error_label: The mistake this distractor stands for, per ADR-18. None on
            the correct option.
    """

    model_config = ConfigDict(frozen=True)

    label: str
    text: str
    is_correct: bool = False
    error_label: str | None = None


class SolutionMethod(BaseModel):
    """One way of solving a question.

    Attributes:
        title: Short name of the approach, e.g. "xét dấu đạo hàm".
        body: The worked steps.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    body: str


class GeneratedQuestion(BaseModel):
    """A question with everything ADR-18 requires attached to it.

    Attributes:
        stem: The question text.
        options: Answer options; exactly one is correct and the rest carry an
            error label. Length is not fixed -- three, four and five all occur.
        methods: Worked solutions. More than one, so a re-explanation has
            somewhere to go.
        learning_objective: What the question tests. Carried for reporting; it
            is not what makes a retry question a retry question (ADR-17).
    """

    model_config = ConfigDict(frozen=True)

    stem: str
    options: tuple[GeneratedOption, ...]
    methods: tuple[SolutionMethod, ...]
    learning_objective: str


class DraftQuestionRequested(BaseModel):
    """Ask AGENT to write **one** question of a draft.

    One question per job, not a whole set, and the reason is arithmetic rather
    than taste: `tools/check_contract.py` compares `LLM_TIMEOUT_SECONDS x
    LLM_MAX_ATTEMPTS` against BE's patience for a single job, and that holds
    only for one question's worth of retries. The task this replaced took up
    to fifty questions in one job -- fifty times the budget the check was
    verifying -- so the check was quietly wrong about the handler that spent
    the most.

    Every field here is copied from a brief BE stored **before** any job was
    queued. That is what keeps a set of questions coherent: the jobs run
    independently and cannot see each other, so if the instructions could
    still change, the first half and the second half of a paper would answer
    different questions and nobody reading them one at a time would notice.

    Attributes:
        request_id: Correlates the reply. BE's own identifier, opaque to AGENT.
        subject: School subject, e.g. "Toán".
        grade: Class level, e.g. "12".
        topic_scope: What the teacher limited the draft to, in their words.
        difficulty: How hard, in the teacher's words. Empty when unsaid.
        ordinal: Which question of the set this is, counting from one.
        of_total: How many the set has. Travels with `ordinal` so the prompt
            can say "question 3 of 10" -- the cheapest nudge towards variety
            between jobs that have no way to coordinate.
        banned_stems: Stems already in the draft, **as stored** -- AGENT
            normalises them with its own rule on arrival, so the two services
            never have to keep two normalisers in step. Best-effort either
            way: jobs fired together cannot know each other's output, so BE
            checks again for duplicates when it harvests.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    subject: str
    grade: str
    topic_scope: str
    difficulty: str = ""
    ordinal: int = Field(ge=1)
    of_total: int = Field(ge=1, le=50)
    banned_stems: tuple[str, ...] = ()


class DraftQuestionCompleted(BaseModel):
    """The one question that job wrote.

    Carries no decision: whether the draft is good enough to publish is the
    teacher's call, and whether the question satisfies ADR-18 is BE's check.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    question: GeneratedQuestion


class RetryQuestionRequested(BaseModel):
    """Ask AGENT for the question of one remediation round.

    Attributes:
        request_id: Correlates the reply.
        origin: The question the student got wrong, whole, because the retry
            must keep its shape rather than merely its objective (ADR-17).
        wrong_option_label: What the student picked.
        error_label: The mistake that option stands for, looked up from the
            authored mapping. AGENT does not infer it.
        round_index: 1, 2 or 3. AGENT writes a question; it does not decide
            whether a fourth round may happen.
        previous_stems: Stems already used in earlier rounds of this question,
            so round two is not round one with different wording.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    origin: GeneratedQuestion
    wrong_option_label: str
    error_label: str | None = None
    round_index: int = Field(ge=1)
    previous_stems: tuple[str, ...] = ()


class RetryQuestionCompleted(BaseModel):
    """The question for this round, in the same shape as any other question."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    question: GeneratedQuestion


class ChatTurn(BaseModel):
    """One turn of the phase 2 conversation.

    Attributes:
        role: "student" or "assistant".
        text: What was said.
    """

    model_config = ConfigDict(frozen=True)

    role: str
    text: str


class ExplainTurnRequested(BaseModel):
    """Ask AGENT for the assistant's next turn in the phase 2 conversation.

    Attributes:
        request_id: Correlates the reply.
        questions: Every question the student got wrong, with its solutions.
            The assistant covers the whole assessment, not one question.
        question_numbers: The number each of those questions carries on the
            paper, in the same order. Without it the assistant counts from one
            and calls question 5 "câu 1", which is worse than saying nothing:
            the student goes looking at the wrong question.
        chosen_labels: Option the student picked, keyed by question stem.
        error_labels: Authored mistake per wrong question, keyed by stem. AGENT
            follows this mapping instead of diagnosing (ADR-18).
        history: Conversation so far, oldest first.
        student_text: The message being answered. Empty for the opening turn.
        stream_channel: Where to publish the answer as it is written, so the
            student sees words rather than a pause. Empty means nobody is
            listening and the reply arrives only at the end. It is a channel
            name and not an id because the naming belongs to whoever is
            listening; AGENT publishes where it is told.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    questions: tuple[GeneratedQuestion, ...]
    question_numbers: tuple[int, ...] = ()
    chosen_labels: dict[str, str] = Field(default_factory=dict)
    error_labels: dict[str, str] = Field(default_factory=dict)
    history: tuple[ChatTurn, ...] = ()
    student_text: str = ""
    stream_channel: str = ""


class ExplainTurnCompleted(BaseModel):
    """What the assistant says next.

    One field, deliberately. An assistant turn that also returned "the student
    now understands" would be deciding when remediation ends, which is a score
    question and belongs to BE (ADR-16, ADR-17).
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCHEMA_VERSION
    request_id: str
    text: str
