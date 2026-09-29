"""Relational shape of everything BE remembers.

ADR-21 made attempt state durable: a phase 2 deadline is hours or days away, so
nothing in this file may live in a cache with a one hour lifetime. AGENT holds
no credentials for this database and never will -- a job carries what it needs.

Two shortcuts are deliberate and marked. Identifiers are string UUIDs rather
than a native type, so the same models run on Postgres in development and on
SQLite in tests without a dialect branch. A round's generated question is stored
as JSON on the round item rather than in the question tables, because it belongs
to exactly one round and is never compared across rows -- promoting it would
mean carrying a second class of question through every query that reads the
authored ones.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    """Mint an identifier.

    Returns:
        A UUID4 in its hyphenated string form.
    """
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Declarative base for every table BE owns."""


class AssessmentState(StrEnum):
    """The four states of ADR-01, in the order an assessment passes them.

    The vocabulary lives here because it is part of the schema; the edges
    between these states live in `be/assessment_state.py`, which is the only
    module allowed to move an assessment from one to another.

    `PUBLISHED` keeps the spelling the seed already wrote, so rows created
    before this enum existed read back unchanged.

    ADR-02 splits the last state into two sub-states -- published-but-not-open
    and open -- because withdrawal is only allowed in the first. That split is
    derived from `Publication.opens_at` rather than stored as a fifth member:
    one fact in two places is two facts that disagree by next week.
    """

    EMPTY = "empty"
    HAS_QUESTIONS = "has_questions"
    APPROVED = "approved"
    PUBLISHED = "published"


class SchoolClass(Base):
    """A class a teacher created, holding the students of one roster.

    `name` is deliberately **not** unique. Two teachers may both have a "12A",
    and one teacher may reuse a name across years. The consequence is that a
    name is not an identifier: resolving what a teacher typed into one of these
    rows can come back with more than one answer, and the caller has to ask
    rather than take the first (ADR-05's input gate).
    """

    __tablename__ = "classes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("teachers.id"))
    name: Mapped[str] = mapped_column(String(64))

    teacher: Mapped[Teacher] = relationship(back_populates="classes")
    students: Mapped[list[Student]] = relationship(back_populates="school_class")


class Student(Base):
    """One student account, keyed for humans by their student code."""

    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    full_name: Mapped[str] = mapped_column(String(128))
    student_code: Mapped[str] = mapped_column(String(32), unique=True)

    school_class: Mapped[SchoolClass] = relationship(back_populates="students")


class Teacher(Base):
    """One teacher account."""

    __tablename__ = "teachers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    full_name: Mapped[str] = mapped_column(String(128))
    teacher_code: Mapped[str] = mapped_column(String(32), unique=True)

    classes: Mapped[list[SchoolClass]] = relationship(back_populates="teacher")
    assessments: Mapped[list[Assessment]] = relationship(back_populates="teacher")


class Assessment(Base):
    """An assessment through its lifecycle.

    `state` is the ADR-01 lifecycle and has **four** values, not three: an
    assessment with no questions yet is its own state, because that state is
    what blocks publishing. Approval locks the content, which is why questions
    carry no edit timestamp -- the lock is a state on this row, not a
    per-question flag.

    `teacher_id` is the author. ADR-13 says a class belongs to a teacher and
    the same follows for what a teacher writes; until this column existed the
    rule had nowhere to live, so no query could apply it.
    """

    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    teacher_id: Mapped[str] = mapped_column(ForeignKey("teachers.id"))
    title: Mapped[str] = mapped_column(String(160))
    subject: Mapped[str] = mapped_column(String(64))
    grade: Mapped[str] = mapped_column(String(16))
    # Three arguments that are not defaults, each for its own reason.
    #
    # `create_constraint` and `validate_strings` are both off by default, and
    # those defaults are the worst of the three options: an unknown string is
    # written without complaint and then raises `LookupError` on the next read
    # of the table, in whatever route happens to touch it next. `validate_
    # strings` moves the error to the write that caused it; `create_constraint`
    # puts the same rule in the schema, so a state outside ADR-01 cannot arrive
    # through psql either.
    #
    # `values_callable` stores the member *values*. Without it SQLAlchemy
    # stores member **names**, so the column would hold "PUBLISHED" while
    # ADR-01 and `data-model.md` both name "published" -- and while rows
    # written before this enum existed held "published" as well.
    state: Mapped[AssessmentState] = mapped_column(
        Enum(
            AssessmentState,
            native_enum=False,
            length=16,
            name="assessment_state",
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=AssessmentState.EMPTY,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    teacher: Mapped[Teacher] = relationship(back_populates="assessments")
    questions: Mapped[list[Question]] = relationship(
        back_populates="assessment", order_by="Question.order_index"
    )
    publication: Mapped[Publication | None] = relationship(
        back_populates="assessment", uselist=False
    )


class Question(Base):
    """One authored question of an assessment."""

    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    order_index: Mapped[int] = mapped_column(Integer)
    stem: Mapped[str] = mapped_column(Text)
    learning_objective: Mapped[str] = mapped_column(String(160))

    assessment: Mapped[Assessment] = relationship(back_populates="questions")
    options: Mapped[list[AnswerOption]] = relationship(
        back_populates="question", order_by="AnswerOption.label"
    )
    methods: Mapped[list[Method]] = relationship(
        back_populates="question", order_by="Method.order_index"
    )


class AnswerOption(Base):
    """One option of a question, with the mistake it stands for.

    `error_label` is the authored distractor mapping of ADR-18, and it is null
    on exactly one row per question: the correct one.
    """

    __tablename__ = "options"
    __table_args__ = (UniqueConstraint("question_id", "label"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    label: Mapped[str] = mapped_column(String(4))
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    error_label: Mapped[str | None] = mapped_column(Text, nullable=True)

    question: Mapped[Question] = relationship(back_populates="options")


class Method(Base):
    """One worked solution of a question. ADR-18 requires more than one."""

    __tablename__ = "methods"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    order_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)

    question: Mapped[Question] = relationship(back_populates="methods")


class Publication(Base):
    """The six parameters a teacher sets when releasing an assessment.

    One row per assessment: re-publishing replaces the terms rather than adding
    a second set, because two live sets of deadlines for one assessment is a
    state nobody could explain to a student.
    """

    __tablename__ = "publications"

    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"), primary_key=True)
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id"))
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    phase1_minutes: Mapped[int] = mapped_column(Integer)
    phase2_minutes_per_question: Mapped[int] = mapped_column(Integer)
    remediation_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recalled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assessment: Mapped[Assessment] = relationship(back_populates="publication")


class Attempt(Base):
    """One student's run at one assessment, across both phases.

    `submitted_at` ends phase 1, not the attempt (ADR-14). The attempt finishes
    when every wrong question is closed or the remediation deadline passes.
    """

    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("assessment_id", "student_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("assessments.id"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Answer(Base):
    """What a student picked for one phase 1 question.

    Saved on every click rather than at submit, so losing the network loses one
    click instead of a paper.
    """

    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    option_id: Mapped[str] = mapped_column(ForeignKey("options.id"))
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuestionOutcome(Base):
    """The running verdict on one question of one attempt.

    This is the score ledger. `mark` only ever rises: phase 1 sets the floor and
    remediation can lift a 0 to a 0.5, never the other way round (ADR-16).
    `rounds_used` is the per-question counter ADR-17 caps at three.
    """

    __tablename__ = "question_outcomes"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    mark: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(String(24))
    rounds_used: Mapped[int] = mapped_column(Integer, default=0)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)


class RemediationRound(Base):
    """One timed round covering every question still open.

    A round gathers all remaining questions rather than one, because phase 2
    receives an assessment, not a question (ADR-17).

    **At most one round per attempt may be unsubmitted, and the database is
    what enforces it.** The route checks first, but a check followed by an
    insert is two statements: two tabs pressing the button together both pass
    the check and both write. A student would then hold two clocks, which
    ADR-15 gives no meaning to. The partial unique index below turns that race
    into an integrity error the route converts to a refusal.
    """

    __tablename__ = "rounds"
    __table_args__ = (
        Index(
            "uq_one_open_round_per_attempt",
            "attempt_id",
            unique=True,
            postgresql_where=text("submitted_at IS NULL"),
            sqlite_where=text("submitted_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"))
    index: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list[RoundItem]] = relationship(back_populates="round")


class RoundItem(Base):
    """The generated question one round poses for one original question.

    `options` and `methods` are JSON because this question belongs to this round
    and nothing else. Keeping the correct option here, server side, is what lets
    BE grade the round without asking AGENT anything (ADR-20).
    """

    __tablename__ = "round_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    round_id: Mapped[str] = mapped_column(ForeignKey("rounds.id"))
    origin_question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    order_index: Mapped[int] = mapped_column(Integer)
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[list[dict]] = mapped_column(JSON)
    methods: Mapped[list[dict]] = mapped_column(JSON)
    chosen_label: Mapped[str | None] = mapped_column(String(4), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(8), nullable=True)

    round: Mapped[RemediationRound] = relationship(back_populates="items")


class PregeneratedItem(Base):
    """A round's question, written before the student asks for it.

    Writing a question takes a model the better part of twenty seconds, and
    doing it when the student presses the button means the student watches a
    blank screen for as long as it takes. But ADR-14 sends them through the
    tutoring screen first, and that is minutes of reading and asking. So the
    work is started the moment phase 1 is submitted and collected later: the
    wait is spent on something the student chose to do.

    **AGENT does not write this table.** It holds no database credentials and
    `tools/check_contract.py` keeps it that way, so BE reads the finished job
    off the queue and stores it here itself.

    `status` moves `pending -> ready`, or `pending -> failed` when the job ran
    and raised. A job whose result simply aged out of Redis -- which is
    ordinary, since results live an hour and a phase 2 deadline can be days
    away -- has its row **deleted** instead, so the one rule "a question with
    no row for the round it needs gets one queued" covers both never-started
    and started-but-lost. `failed` is kept precisely so it is *not* re-queued:
    the same job would fail the same way, every time the student opens a
    screen.

    The unique index is not decoration. Two tabs on the tutoring screen both
    poll, both find the same finished job, and both insert; checking first and
    writing second is two statements with a gap in the middle. The same lesson
    as `uq_one_open_round_per_attempt` above, learned the same way.
    """

    __tablename__ = "pregenerated_items"
    __table_args__ = (
        Index(
            "uq_one_pregenerated_per_round",
            "attempt_id",
            "origin_question_id",
            "round_index",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"))
    origin_question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"))
    round_index: Mapped[int] = mapped_column(Integer)
    job_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(8), default="pending")
    stem: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    methods: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChatMessage(Base):
    """One turn of the phase 2 conversation, stored before it is streamed.

    Order is by `created_at` plus `sequence`, because two turns can land inside
    the same clock tick and a conversation that reorders itself on reload is a
    different conversation.
    """

    __tablename__ = "chat_messages"
    # One turn per position. Two requests can reach the opening turn holding
    # the same empty history -- React's StrictMode opens the stream twice by
    # design -- and a check followed by an insert is two statements with a gap
    # in the middle. Without this the student is greeted twice, by two rows
    # that both claim to be the first.
    __table_args__ = (UniqueConstraint("attempt_id", "sequence"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Report(Base):
    """A student saying the assistant's explanation was hard to follow.

    Scoped to the attempt, not to one message: the assistant works across the
    whole assessment, so a report pointing at a single turn would promise the
    teacher a narrower thing than exists (ADR-19).
    """

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("attempts.id"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
