from __future__ import annotations

import typing as t

from sqlalchemy import select

from socratic.core import di
from socratic.model import AttemptID, EducatorOverride, Grade, OverrideID, UserID

from . import Session
from .table import educator_overrides


def get(key: OverrideID, session: Session = di.Provide["storage.persistent.session"]) -> EducatorOverride | None:
    stmt = select(educator_overrides.__table__).where(educator_overrides.override_id == key)
    row = session.execute(stmt).mappings().one_or_none()
    return EducatorOverride(**row) if row else None


def find(
    *,
    attempt_id: AttemptID | None = None,
    educator_id: UserID | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[EducatorOverride, ...]:
    stmt = select(educator_overrides.__table__).order_by(educator_overrides.create_time.desc())
    if attempt_id is not None:
        stmt = stmt.where(educator_overrides.attempt_id == attempt_id)
    if educator_id is not None:
        stmt = stmt.where(educator_overrides.educator_id == educator_id)
    rows = session.execute(stmt).mappings().all()
    return tuple(EducatorOverride(**row) for row in rows)


def create(
    params: OverrideCreateParams, session: Session = di.Provide["storage.persistent.session"]
) -> EducatorOverride:
    original_grade = params.get("original_grade")
    override = educator_overrides(
        override_id=OverrideID(),
        attempt_id=params["attempt_id"],
        educator_id=params["educator_id"],
        original_grade=original_grade.value if original_grade else None,
        new_grade=params["new_grade"].value,
        reason=params["reason"],
        feedback=params.get("feedback"),
    )
    session.add(override)
    session.flush()
    return get(override.override_id, session=session)  # type: ignore


class OverrideCreateParams(t.TypedDict, total=False):
    attempt_id: t.Required[AttemptID]
    educator_id: t.Required[UserID]
    original_grade: Grade | None
    new_grade: t.Required[Grade]
    reason: t.Required[str]
    feedback: str | None
