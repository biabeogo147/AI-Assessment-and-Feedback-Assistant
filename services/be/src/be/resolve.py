"""From what a teacher typed to a row, or to a question.

`classes.name` carries no unique constraint, so a class name is not an
identifier: one teacher may run two sections called 12A across years, and two
teachers may each have one. Every tool that works on a class needs a
`class_id`, which makes this translation step the place where the whole
teacher-facing surface either asks or guesses.

It asks. Three answers and no fourth:

- `Resolved` -- exactly one of this teacher's classes matches.
- `Ambiguous` -- several could be meant, and they come back as candidates for
  the assistant to ask about. ADR-05 forbids marking one of them as the one to
  pick; this module returns them in a stable order and says nothing about
  which is likelier.
- `NotFound` -- none of this teacher's classes match, and the answer carries
  the list of classes that do, because "không có lớp nào tên đó" alone leaves
  a teacher unable to tell a typo from lost data.

Two rules the answers obey:

**A class of another teacher's is answered exactly as one that does not
exist** (ADR-22). Not a different message, not a different type -- the same
`NotFound` carrying the same list. Two distinguishable refusals would be a
probe: type names until the wording changes and the school is mapped.

**Everything returned is a value, not a row.** The loop that calls this rolls
its session back between steps, which expires ORM objects; a `SchoolClass`
handed upward would raise `MissingGreenlet` on its next attribute read, far
from here.
"""

import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from be.identity import Asking
from be.models import SchoolClass, Student

# How many classes a refusal or a question will name. A teacher with thirty
# classes gets a question they can answer, not a list they have to read: the
# assistant asks them to be more specific instead.
_MOST_CANDIDATES = 6

# "lớp 12A", "Lop 12a", "12 A" all mean the same class. Stripped rather than
# matched loosely, because loose matching is what turns an exact name into an
# ambiguous one.
#
# The vowel is spelled out because "ơ" (U+01A1) and "ớ" (U+1EDB) are different
# characters, and "lớp" uses the second one. A class of `[oơ]` looks like it
# covers the word and silently does not -- which is exactly how this was
# written the first time.
#
# The tail is optional and allows punctuation, because teachers write "Lớp:
# 12A" and "lớp12A" as readily as "lớp 12A". Requiring a space made all three
# of those a not-found answer, which reads as the system having lost a class
# the teacher is standing in front of.
_PREFIX = re.compile(r"^\s*l[oơớờởỡợôốồổỗộóòỏõọ]p\s*[:.\-–—]?\s*", re.IGNORECASE)
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True)
class Candidate:
    """One class a name could mean, as values.

    Attributes:
        class_id: What every other tool needs.
        name: As stored, not as normalised -- this is shown to a teacher.
        student_count: Roster size, which is how a teacher tells two sections
            of the same name apart. It travels because without it a question
            offering "12A" and "12A" is unanswerable.
    """

    class_id: str
    name: str
    student_count: int


@dataclass(frozen=True)
class Resolved:
    """Exactly one class matched.

    Attributes:
        class_id: The id tools take.
        name: As stored.
        student_count: Roster size.
    """

    class_id: str
    name: str
    student_count: int


@dataclass(frozen=True)
class Ambiguous:
    """Several classes could be meant.

    Attributes:
        candidates: Each one that matched, in a stable order. No field says
            which to prefer, because ADR-05 leaves that choice to the teacher.
        more: How many matches were left out of `candidates`, so the assistant
            can say the list is partial rather than implying it is complete.
    """

    candidates: tuple[Candidate, ...]
    more: int = 0


@dataclass(frozen=True)
class NotFound:
    """No class of this teacher's matched.

    Attributes:
        available: This teacher's classes, so the refusal answers the obvious
            next question. Capped, with `more` counting the rest.
        more: How many were left out.
    """

    available: tuple[Candidate, ...]
    more: int = 0


def normalise(name: str) -> str:
    """Reduce a typed class name to what it means.

    Unicode form first. "lớp" typed on a Mac arrives decomposed -- "l", "o",
    U+031B, "p" -- and compares unequal to the composed spelling stored in the
    database, so without this a teacher on macOS gets not-found for every
    class they name.

    Args:
        name: As the teacher wrote it, possibly with "lớp" in front and
            possibly with punctuation after it.

    Returns:
        Composed, lower-cased, with the word "lớp" and all whitespace removed.
        Empty when the input carried no name, which callers must treat as
        "nothing named" and never as "matches everything".
    """
    composed = unicodedata.normalize("NFC", name)
    return _SPACES.sub("", _PREFIX.sub("", composed)).casefold()


async def _candidates(session: AsyncSession, asking: Asking) -> list[Candidate]:
    """Every class this teacher owns, with roster sizes, in one query.

    Args:
        session: Database session.
        asking: Whose classes. This filter is the whole of ADR-22 here.

    Returns:
        Candidates ordered by name then id, so two sections of one name come
        back in the same order every time -- a question whose options move
        between askings is a question a teacher cannot answer twice.
    """
    counted = (
        select(SchoolClass.id, SchoolClass.name, func.count(Student.id))
        .outerjoin(Student, Student.class_id == SchoolClass.id)
        .where(SchoolClass.teacher_id == asking.teacher_id)
        .group_by(SchoolClass.id, SchoolClass.name)
        .order_by(SchoolClass.name, SchoolClass.id)
    )
    rows = await session.execute(counted)
    return [
        Candidate(class_id=class_id, name=name, student_count=count)
        for class_id, name, count in rows.all()
    ]


def _capped(matches: list[Candidate]) -> tuple[tuple[Candidate, ...], int]:
    """Trim a list of candidates and report how many were dropped."""
    kept = tuple(matches[:_MOST_CANDIDATES])
    return kept, max(0, len(matches) - len(kept))


async def resolve_class(
    session: AsyncSession, asking: Asking, typed: str
) -> Resolved | Ambiguous | NotFound:
    """Work out which of this teacher's classes a name means.

    Exact match first, then substring. That order is what makes both halves
    safe: substring matching is what lets "12" mean "one of 12A and 12B", and
    it is also what would make "12A" ambiguous the moment a 12A1 exists.

    Args:
        session: Database session.
        asking: Who is asking. Only their classes are ever considered, and a
            class of someone else's is indistinguishable from one that is not
            there (ADR-22).
        typed: The name as the teacher wrote it.

    Returns:
        `Resolved` for one match, `Ambiguous` for several, `NotFound` for
        none. Never a guess: there is no code path that picks one of several.
    """
    owned = await _candidates(session, asking)
    wanted = normalise(typed)
    if not wanted:
        # An argument the model left out arrives as "". Matching that by
        # substring would match every class, and the assistant would resolve
        # to whichever came first.
        available, more = _capped(owned)
        return NotFound(available=available, more=more)

    # The stored spelling first, before anything is normalised away. "12A" and
    # "12 A" are two different rows that normalise to one string, so on the
    # normalised comparison alone they would be ambiguous forever and no string
    # a teacher could type would ever pick one. This gives each of them a way
    # in without weakening the refusal to guess: it only ever matches when the
    # teacher wrote the name exactly as it is stored.
    literal = unicodedata.normalize("NFC", typed).strip()
    verbatim = [
        candidate for candidate in owned if unicodedata.normalize("NFC", candidate.name) == literal
    ]
    if len(verbatim) == 1:
        only = verbatim[0]
        return Resolved(class_id=only.class_id, name=only.name, student_count=only.student_count)

    exact = [candidate for candidate in owned if normalise(candidate.name) == wanted]
    if len(exact) == 1:
        only = exact[0]
        return Resolved(class_id=only.class_id, name=only.name, student_count=only.student_count)
    if len(exact) > 1:
        candidates, more = _capped(exact)
        return Ambiguous(candidates=candidates, more=more)

    partial = [candidate for candidate in owned if wanted in normalise(candidate.name)]
    if len(partial) == 1:
        only = partial[0]
        return Resolved(class_id=only.class_id, name=only.name, student_count=only.student_count)
    if len(partial) > 1:
        candidates, more = _capped(partial)
        return Ambiguous(candidates=candidates, more=more)

    available, more = _capped(owned)
    return NotFound(available=available, more=more)
