from __future__ import annotations

import datetime
import typing as t

import sqlalchemy as sqla

from socratic.core import di
from socratic.lib import NotSet
from socratic.model import Assignment, AssignmentID, ObjectiveID, OrganizationID, RetakePolicy, UserID

from . import Session
from .table import assignments


def get(
    assignment_id: AssignmentID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> Assignment | None:
    """Get an assignment by ID."""
    stmt = sqla.select(assignments.__table__).where(assignments.assignment_id == assignment_id)
    row = session.execute(stmt).mappings().one_or_none()
    return Assignment(**row) if row else None


def find(
    *,
    organization_id: OrganizationID | None = None,
    objective_id: ObjectiveID | None = None,
    assigned_by: UserID | None = None,
    assigned_to: UserID | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[Assignment, ...]:
    """Find assignments matching criteria."""
    stmt = sqla.select(assignments.__table__)
    if organization_id is not None:
        stmt = stmt.where(assignments.organization_id == organization_id)
    if objective_id is not None:
        stmt = stmt.where(assignments.objective_id == objective_id)
    if assigned_by is not None:
        stmt = stmt.where(assignments.assigned_by == assigned_by)
    if assigned_to is not None:
        stmt = stmt.where(assignments.assigned_to == assigned_to)
    rows = session.execute(stmt).mappings().all()
    return tuple(Assignment(**row) for row in rows)


def create(
    *,
    organization_id: OrganizationID,
    objective_id: ObjectiveID,
    assigned_by: UserID,
    assigned_to: UserID,
    available_from: datetime.datetime | None = None,
    available_until: datetime.datetime | None = None,
    max_attempts: int = 1,
    retake_policy: RetakePolicy = RetakePolicy.None_,
    retake_delay_hours: int | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> Assignment:
    """Create a new assignment."""
    assignment_id = AssignmentID()
    stmt = sqla.insert(assignments).values(
        assignment_id=assignment_id,
        organization_id=organization_id,
        objective_id=objective_id,
        assigned_by=assigned_by,
        assigned_to=assigned_to,
        available_from=available_from,
        available_until=available_until,
        max_attempts=max_attempts,
        retake_policy=retake_policy.value,
        retake_delay_hours=retake_delay_hours,
    )
    session.execute(stmt)
    session.flush()
    result = get(assignment_id, session=session)
    assert result is not None
    return result


def update(
    assignment_id: AssignmentID,
    *,
    available_from: datetime.datetime | None | NotSet = NotSet(),
    available_until: datetime.datetime | None | NotSet = NotSet(),
    max_attempts: int | NotSet = NotSet(),
    retake_policy: RetakePolicy | NotSet = NotSet(),
    retake_delay_hours: int | None | NotSet = NotSet(),
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    """Update an assignment.

    Uses NotSet sentinel for parameters where None may be a valid value.
    Call get() after if you need the updated entity.

    Raises:
        KeyError: If assignment_id does not correspond to an assignment
    """
    values: dict[str, t.Any] = {}
    if not isinstance(available_from, NotSet):
        values["available_from"] = available_from
    if not isinstance(available_until, NotSet):
        values["available_until"] = available_until
    if not isinstance(max_attempts, NotSet):
        values["max_attempts"] = max_attempts
    if not isinstance(retake_policy, NotSet):
        values["retake_policy"] = retake_policy.value
    if not isinstance(retake_delay_hours, NotSet):
        values["retake_delay_hours"] = retake_delay_hours

    if values:
        stmt = sqla.update(assignments).where(assignments.assignment_id == assignment_id).values(**values)
    else:
        # No-op update to verify assignment exists
        stmt = (
            sqla
            .update(assignments)
            .where(assignments.assignment_id == assignment_id)
            .values(assignment_id=assignment_id)
        )

    result = session.execute(stmt)
    if result.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue]
        raise KeyError(f"Assignment {assignment_id} not found")

    session.flush()


def delete(
    assignment_id: AssignmentID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> bool:
    """Delete an assignment.

    Returns:
        True if an assignment was deleted, False if not found
    """
    stmt = sqla.delete(assignments).where(assignments.assignment_id == assignment_id)
    result = session.execute(stmt)
    return bool(result.rowcount)  # pyright: ignore[reportUnknownArgumentType, reportAttributeAccessIssue]
