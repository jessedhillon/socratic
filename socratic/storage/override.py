from __future__ import annotations

import sqlalchemy as sqla

from socratic.core import di
from socratic.model import AttemptID, EducatorOverride, Grade, OverrideID, UserID

from . import Session
from .table import educator_overrides


def get(
    override_id: OverrideID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> EducatorOverride | None:
    """Get an educator override by ID."""
    stmt = sqla.select(educator_overrides.__table__).where(educator_overrides.override_id == override_id)
    row = session.execute(stmt).mappings().one_or_none()
    return EducatorOverride(**row) if row else None


def find(
    *,
    attempt_id: AttemptID | None = None,
    educator_id: UserID | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[EducatorOverride, ...]:
    """Find educator overrides matching criteria."""
    stmt = sqla.select(educator_overrides.__table__).order_by(educator_overrides.create_time.desc())
    if attempt_id is not None:
        stmt = stmt.where(educator_overrides.attempt_id == attempt_id)
    if educator_id is not None:
        stmt = stmt.where(educator_overrides.educator_id == educator_id)
    rows = session.execute(stmt).mappings().all()
    return tuple(EducatorOverride(**row) for row in rows)


def create(
    *,
    attempt_id: AttemptID,
    educator_id: UserID,
    new_grade: Grade,
    reason: str,
    original_grade: Grade | None = None,
    feedback: str | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> EducatorOverride:
    """Create a new educator override."""
    override_id = OverrideID()
    stmt = sqla.insert(educator_overrides).values(
        override_id=override_id,
        attempt_id=attempt_id,
        educator_id=educator_id,
        original_grade=original_grade.value if original_grade else None,
        new_grade=new_grade.value,
        reason=reason,
        feedback=feedback,
    )
    session.execute(stmt)
    session.flush()
    result = get(override_id, session=session)
    assert result is not None
    return result
