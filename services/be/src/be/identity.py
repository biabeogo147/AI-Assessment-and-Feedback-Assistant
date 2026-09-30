"""Who is calling, and what that lets them touch.

ADR-10 left the sign-in screen out of the first round, but "a student sees only
their own work" is a rule and not a convenience. So the two halves are split:
authorisation below is the real thing and will not be rewritten, while the proof
of identity is a header that only works while `dev_identity_enabled` is on.

The header reads `X-Actor: student:HS2026-1204` or `X-Actor: teacher:GV-001`.
"""

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from be.config import get_settings
from be.db import get_session
from be.models import Student, Teacher


@dataclass(frozen=True)
class Asking:
    """Who a tool is running for, as values rather than as a row.

    Deliberately not the `Teacher` row. The loop rolls its session back
    between steps to release the pooled connection, and a rollback expires
    every ORM object attached to that session -- so reading `teacher.id` on
    the next step would be database IO from a place SQLAlchemy's async bridge
    cannot reach. The symptom is `MissingGreenlet`, raised far from its cause.

    Values also make the rule harder to lose: a tool is handed an identity it
    cannot avoid having, and cannot quietly widen its scope by forgetting to
    read one.

    Attributes:
        teacher_id: Owner every query filters on (ADR-22).
        teacher_code: What the logs name, so a refusal can be traced without
            joining anything.
        full_name: How the assistant addresses the person.
    """

    teacher_id: str
    teacher_code: str
    full_name: str

    @classmethod
    def of(cls, teacher: Teacher) -> "Asking":
        """Read a teacher row into an identity that outlives the session.

        Args:
            teacher: The row, freshly loaded.

        Returns:
            The three values the tools and the loop need.
        """
        return cls(
            teacher_id=teacher.id,
            teacher_code=teacher.teacher_code,
            full_name=teacher.full_name,
        )


def _parse(raw: str | None) -> tuple[str, str]:
    """Split an actor header into a role and a code.

    Args:
        raw: Header value, or None when the header is absent.

    Returns:
        The role and the code.

    Raises:
        HTTPException: 401 when the header is missing or malformed.
    """
    if not raw or ":" not in raw:
        raise HTTPException(status_code=401, detail="Missing actor. Send 'role:code'.")
    role, _, code = raw.partition(":")
    role, code = role.strip().lower(), code.strip()
    if role not in {"student", "teacher"} or not code:
        raise HTTPException(
            status_code=401, detail="Actor must be 'student:<code>' or 'teacher:<code>'."
        )
    return role, code


async def current_student(
    session: AsyncSession = Depends(get_session),
    x_actor: str | None = Header(default=None, alias="X-Actor"),
) -> Student:
    """Resolve the student making this request.

    Args:
        session: Database session.
        x_actor: The stand-in identity header.

    Returns:
        The Student row.

    Raises:
        HTTPException: 401 when identity is absent, malformed, disabled, or the
            code belongs to nobody; 403 when a teacher calls a student route.
    """
    if not get_settings().dev_identity_enabled:
        raise HTTPException(status_code=401, detail="Sign-in is not available yet.")

    role, code = _parse(x_actor)
    if role != "student":
        raise HTTPException(status_code=403, detail="This is a student route.")

    found = await session.scalar(select(Student).where(Student.student_code == code))
    if found is None:
        raise HTTPException(status_code=401, detail=f"No student {code}")
    return found


async def current_teacher(
    session: AsyncSession = Depends(get_session),
    x_actor: str | None = Header(default=None, alias="X-Actor"),
) -> Teacher:
    """Resolve the teacher making this request.

    Args:
        session: Database session.
        x_actor: The stand-in identity header.

    Returns:
        The Teacher row.

    Raises:
        HTTPException: 401 when identity is absent, malformed, disabled, or
            unknown; 403 when a student calls a teacher route.
    """
    if not get_settings().dev_identity_enabled:
        raise HTTPException(status_code=401, detail="Sign-in is not available yet.")

    role, code = _parse(x_actor)
    if role != "teacher":
        raise HTTPException(status_code=403, detail="This is a teacher route.")

    found = await session.scalar(select(Teacher).where(Teacher.teacher_code == code))
    if found is None:
        raise HTTPException(status_code=401, detail=f"No teacher {code}")
    return found
