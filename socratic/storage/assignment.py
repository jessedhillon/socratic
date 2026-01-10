from __future__ import annotations

import datetime
import typing as t

from sqlalchemy import delete as sql_delete
from sqlalchemy import select

from socratic.core import di
from socratic.model import Assignment, AssignmentID, ObjectiveID, OrganizationID, RetakePolicy, UserID

from . import Session
from .table import assignments


def get(key: AssignmentID, session: Session = di.Provide["storage.persistent.session"]) -> Assignment | None:
    stmt = select(assignments.__table__).where(assignments.assignment_id == key)
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
    stmt = select(assignments.__table__)
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


def create(params: AssignmentCreateParams, session: Session = di.Provide["storage.persistent.session"]) -> Assignment:
    assignment = assignments(
        assignment_id=AssignmentID(),
        organization_id=params["organization_id"],
        objective_id=params["objective_id"],
        assigned_by=params["assigned_by"],
        assigned_to=params["assigned_to"],
        available_from=params.get("available_from"),
        available_until=params.get("available_until"),
        max_attempts=params.get("max_attempts", 1),
        retake_policy=params.get("retake_policy", RetakePolicy.None_).value,
        retake_delay_hours=params.get("retake_delay_hours"),
    )
    session.add(assignment)
    session.flush()
    return get(assignment.assignment_id, session=session)  # type: ignore


def update(
    key: AssignmentID,
    params: AssignmentUpdateParams,
    session: Session = di.Provide["storage.persistent.session"],
) -> Assignment | None:
    stmt = select(assignments).where(assignments.assignment_id == key)
    assignment = session.execute(stmt).scalar_one_or_none()
    if assignment is None:
        return None
    for field, value in params.items():
        if value is not None:
            if field == "retake_policy" and isinstance(value, RetakePolicy):
                setattr(assignment, field, value.value)
            else:
                setattr(assignment, field, value)
    session.flush()
    return get(key, session=session)


def delete(
    key: AssignmentID,
    session: Session = di.Provide["storage.persistent.session"],
) -> bool:
    stmt = sql_delete(assignments).where(assignments.assignment_id == key)
    result = session.execute(stmt)
    return bool(result.rowcount)  # pyright: ignore [reportAttributeAccessIssue, reportUnknownArgumentType]


class AssignmentCreateParams(t.TypedDict, total=False):
    organization_id: t.Required[OrganizationID]
    objective_id: t.Required[ObjectiveID]
    assigned_by: t.Required[UserID]
    assigned_to: t.Required[UserID]
    available_from: datetime.datetime | None
    available_until: datetime.datetime | None
    max_attempts: int
    retake_policy: RetakePolicy
    retake_delay_hours: int | None


class AssignmentUpdateParams(t.TypedDict, total=False):
    available_from: datetime.datetime | None
    available_until: datetime.datetime | None
    max_attempts: int
    retake_policy: RetakePolicy
    retake_delay_hours: int | None
