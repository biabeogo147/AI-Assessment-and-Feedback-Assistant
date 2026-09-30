"""Turning what a teacher typed into a row, or refusing to guess.

`classes.name` is not unique, so a name is not an identifier. Every tool that
takes a class has to get one from somewhere, and the only honest answers are
"this one", "one of these -- which?" and "none of yours". Picking the first row
would be the fourth answer, the wrong one, and the one nobody would notice:
the assistant would read another class's marks and say so confidently.

That refusal to guess is ADR-05's input gate, and ADR-23 is where it is
written down. What these tests pin is the part a prompt cannot hold: the
candidates offered in a clarifying question come from rows BE read, and a
class belonging to another teacher is answered exactly like a class that does
not exist (ADR-22).
"""

import unicodedata

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from be import db as db_module
from be.db import bind_sessions, prepare_schema
from be.identity import Asking
from be.models import SchoolClass, Student, Teacher
from be.resolve import Ambiguous, NotFound, Resolved, resolve_class
from be.seed import seed_if_empty
from be.teacher_tools import execute


@pytest_asyncio.fixture
async def stack():
    """A seeded database plus a second teacher who owns a class of their own."""
    engine = create_async_engine("sqlite+aiosqlite://")
    await prepare_schema(engine)
    bind_sessions(engine)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        await seed_if_empty(session)
        stranger = Teacher(full_name="Thầy Nguyễn Văn B", teacher_code="GV-002")
        session.add(stranger)
        await session.flush()
        session.add(SchoolClass(teacher_id=stranger.id, name="11B"))
        await session.commit()

    yield maker

    await engine.dispose()
    db_module._SESSION_MAKER = None


async def _mine(session) -> Asking:
    teacher = await session.scalar(select(Teacher).where(Teacher.teacher_code == "GV-001"))
    assert teacher is not None
    return Asking.of(teacher)


async def _add_class(session, asking: Asking, name: str, students: int = 0) -> SchoolClass:
    """Give the asking teacher one more class, with a roster of its own."""
    school_class = SchoolClass(teacher_id=asking.teacher_id, name=name)
    session.add(school_class)
    await session.flush()
    for index in range(students):
        session.add(
            Student(
                class_id=school_class.id,
                full_name=f"Học sinh {name} {index}",
                student_code=f"{name}-{index}",
            )
        )
    await session.flush()
    return school_class


@pytest.mark.asyncio
async def test_a_name_that_matches_one_class_resolves(stack) -> None:
    """The ordinary case, and the one every other answer is measured against."""
    async with stack() as session:
        asking = await _mine(session)

        found = await resolve_class(session, asking, "12A")

    assert isinstance(found, Resolved)
    assert found.name == "12A"
    assert found.class_id


@pytest.mark.asyncio
async def test_case_and_the_word_lop_do_not_matter(stack) -> None:
    """Teachers type "lớp 12a", not a normalised identifier.

    Refusing that would push the assistant into asking a question whose answer
    it already has, which teaches teachers to distrust the clarifying question
    when it matters.
    """
    async with stack() as session:
        asking = await _mine(session)

        for typed in ("12a", "  12A  ", "lớp 12A", "Lớp 12a"):
            found = await resolve_class(session, asking, typed)
            assert isinstance(found, Resolved), typed


@pytest.mark.asyncio
async def test_two_classes_of_the_same_name_ask_rather_than_pick(stack) -> None:
    """Both rows come back as candidates, and neither is chosen.

    `classes.name` has no unique constraint precisely because this happens --
    a teacher may run two sections called 12A across years. The candidates
    carry their roster sizes so the question can distinguish them by something
    a teacher recognises; ADR-05 forbids marking either as the one to pick.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "12A", students=7)

        answer = await resolve_class(session, asking, "12A")

    assert isinstance(answer, Ambiguous)
    assert len(answer.candidates) == 2
    assert {candidate.name for candidate in answer.candidates} == {"12A"}
    assert sorted(candidate.student_count for candidate in answer.candidates) == [3, 7]


@pytest.mark.asyncio
async def test_a_partial_name_offers_the_classes_it_could_mean(stack) -> None:
    """ "12" with a 12A and a 12B is a question, not a failure.

    Without this the assistant would answer "no such class" to a teacher who
    named a real one imprecisely, which reads as the system having lost their
    data.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "12B", students=5)

        answer = await resolve_class(session, asking, "12")

    assert isinstance(answer, Ambiguous)
    assert {candidate.name for candidate in answer.candidates} == {"12A", "12B"}


@pytest.mark.asyncio
async def test_an_exact_name_wins_over_a_longer_one_containing_it(stack) -> None:
    """ "12A" resolves when both 12A and 12A1 exist.

    Substring matching is what makes a partial name useful, and it is also
    what would make an exact name ambiguous. The exact match is tried first,
    so naming a class precisely always works.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "12A1", students=9)

        answer = await resolve_class(session, asking, "12A")

    assert isinstance(answer, Resolved)
    assert answer.name == "12A"


@pytest.mark.asyncio
async def test_nothing_of_this_teachers_matches_and_the_list_says_what_does(stack) -> None:
    """A refusal that names the teacher's own classes.

    "Không có lớp nào tên đó" on its own leaves a teacher guessing whether
    they mistyped or whether the class is gone. The list turns the refusal
    into the answer to the next question.
    """
    async with stack() as session:
        asking = await _mine(session)

        answer = await resolve_class(session, asking, "9Z")

    assert isinstance(answer, NotFound)
    assert {candidate.name for candidate in answer.available} == {"12A"}


@pytest.mark.asyncio
async def test_another_teachers_class_is_answered_as_if_it_did_not_exist(stack) -> None:
    """ADR-22, enforced here rather than promised.

    Two different refusals would be a probe: type names until the wording
    changes and you have mapped the school. The list of the asking teacher's
    own classes is the same in both answers, so there is nothing to compare.
    """
    async with stack() as session:
        asking = await _mine(session)

        theirs = await resolve_class(session, asking, "11B")
        absent = await resolve_class(session, asking, "9Z")

    assert isinstance(theirs, NotFound)
    assert isinstance(absent, NotFound)
    assert theirs == absent


@pytest.mark.asyncio
async def test_an_empty_name_is_not_found_rather_than_everything(stack) -> None:
    """A blank argument must not match every class by substring.

    The model fills these arguments, and an omitted one arrives as "". Without
    this the assistant would silently resolve to whichever class happened to
    be first.
    """
    async with stack() as session:
        asking = await _mine(session)

        answer = await resolve_class(session, asking, "   ")

    assert isinstance(answer, NotFound)


@pytest.mark.asyncio
async def test_find_class_hands_the_ambiguity_to_the_loop(stack) -> None:
    """The tool reports candidates instead of raising or guessing.

    The loop feeds this back to the model as data, so the clarifying question
    is phrased by the assistant from rows BE read. That is the half of ADR-05
    that cannot live in a prompt.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "12A", students=7)

        result = await execute(session, asking, "find_class", {"name": "12A"})

    assert result["found"] is False
    assert result["ambiguous"] is True
    assert [candidate["name"] for candidate in result["candidates"]] == ["12A", "12A"]
    assert sorted(candidate["student_count"] for candidate in result["candidates"]) == [3, 7]


@pytest.mark.asyncio
async def test_a_class_with_no_students_still_resolves(stack) -> None:
    """A roster size of zero is a number, not a missing class.

    `outerjoin` plus `count` is what makes this work, and it is the kind of
    query that silently returns nothing when written with an inner join -- so
    a brand-new class would vanish from every answer.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "10C", students=0)

        found = await resolve_class(session, asking, "10C")

    assert isinstance(found, Resolved)
    assert found.student_count == 0


@pytest.mark.asyncio
async def test_a_name_written_exactly_as_stored_wins_over_normalising(stack) -> None:
    """Two classes differing only in spacing stay reachable.

    "12A" and "12 A" normalise to the same string, so on the normalised
    comparison alone they are ambiguous forever -- and no string a teacher
    could type would ever pick one. Trying the stored spelling first gives
    both of them a way in, without weakening the refusal to guess.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "12 A", students=4)

        spaced = await resolve_class(session, asking, "12 A")
        tight = await resolve_class(session, asking, "12A")

    assert isinstance(spaced, Resolved)
    assert spaced.name == "12 A"
    assert isinstance(tight, Resolved)
    assert tight.name == "12A"


@pytest.mark.asyncio
async def test_the_word_lop_may_carry_punctuation_or_no_space(stack) -> None:
    """Teachers type "Lớp: 12A" and "lớp12A" too.

    Every one of these was a not-found answer before, which reads to a teacher
    as the system having lost a class they are standing in front of.
    """
    async with stack() as session:
        asking = await _mine(session)

        for typed in ("Lớp: 12A", "lớp12A", "lớp - 12A", "LỚP 12A"):
            found = await resolve_class(session, asking, typed)
            assert isinstance(found, Resolved), typed


@pytest.mark.asyncio
async def test_a_decomposed_name_matches_a_composed_one(stack) -> None:
    """The same Vietnamese word in two Unicode spellings is one word.

    macOS and iOS send decomposed text, so "lớp" can arrive as "l" + "o" +
    U+031B + "p". Without normalising the form, a teacher on a Mac gets
    not-found for every class they name.
    """
    async with stack() as session:
        asking = await _mine(session)
        await _add_class(session, asking, "12 Văn", students=6)

        decomposed = unicodedata.normalize("NFD", "lớp 12 Văn")

        found = await resolve_class(session, asking, decomposed)

    assert isinstance(found, Resolved)
    assert found.name == "12 Văn"


@pytest.mark.asyncio
async def test_a_missing_name_says_so_instead_of_searching_for_none(stack) -> None:
    """`{"name": null}` is an omitted argument, not a class called "none".

    `str(None)` is "none", which would be searched for, matched against any
    class whose name contained it, and otherwise reported as "no class of
    yours by that name" -- the wrong sentence for a question that never named
    a class.
    """
    async with stack() as session:
        asking = await _mine(session)

        result = await execute(session, asking, "find_class", {"name": None})

    assert result["found"] is False
    assert result["reason"] == "chưa có tên lớp nào trong câu hỏi"
