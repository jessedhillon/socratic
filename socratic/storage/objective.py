from __future__ import annotations

import typing as t

import sqlalchemy as sqla

from socratic.core import di
from socratic.lib import NotSet
from socratic.model import ExtensionPolicy, Objective, ObjectiveID, ObjectiveStatus, OrganizationID, UserID

from . import Session
from .table import objectives


def get(
    objective_id: ObjectiveID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> Objective | None:
    """Get an objective by ID."""
    stmt = sqla.select(objectives.__table__).where(objectives.objective_id == objective_id)
    row = session.execute(stmt).mappings().one_or_none()
    return Objective(**row) if row else None


def find(
    *,
    organization_id: OrganizationID | None = None,
    created_by: UserID | None = None,
    status: ObjectiveStatus | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[Objective, ...]:
    """Find objectives matching criteria."""
    stmt = sqla.select(objectives.__table__)
    if organization_id is not None:
        stmt = stmt.where(objectives.organization_id == organization_id)
    if created_by is not None:
        stmt = stmt.where(objectives.created_by == created_by)
    if status is not None:
        stmt = stmt.where(objectives.status == status.value)
    rows = session.execute(stmt).mappings().all()
    return tuple(Objective(**row) for row in rows)


def create(
    *,
    organization_id: OrganizationID,
    created_by: UserID,
    title: str,
    description: str,
    scope_boundaries: str | None = None,
    time_expectation_minutes: int | None = None,
    initial_prompts: list[str] | None = None,
    challenge_prompts: list[str] | None = None,
    extension_policy: ExtensionPolicy = ExtensionPolicy.Disallowed,
    status: ObjectiveStatus = ObjectiveStatus.Draft,
    session: Session = di.Provide["storage.persistent.session"],
) -> Objective:
    """Create a new objective."""
    objective_id = ObjectiveID()
    stmt = sqla.insert(objectives).values(
        objective_id=objective_id,
        organization_id=organization_id,
        created_by=created_by,
        title=title,
        description=description,
        scope_boundaries=scope_boundaries,
        time_expectation_minutes=time_expectation_minutes,
        initial_prompts=initial_prompts if initial_prompts is not None else [],
        challenge_prompts=challenge_prompts if challenge_prompts is not None else [],
        extension_policy=extension_policy.value,
        status=status.value,
    )
    session.execute(stmt)
    session.flush()
    obj = get(objective_id, session=session)
    assert obj is not None
    return obj


def update(
    objective_id: ObjectiveID,
    *,
    title: str | NotSet = NotSet(),
    description: str | NotSet = NotSet(),
    scope_boundaries: str | None | NotSet = NotSet(),
    time_expectation_minutes: int | None | NotSet = NotSet(),
    initial_prompts: list[str] | NotSet = NotSet(),
    challenge_prompts: list[str] | NotSet = NotSet(),
    extension_policy: ExtensionPolicy | NotSet = NotSet(),
    status: ObjectiveStatus | NotSet = NotSet(),
    session: Session = di.Provide["storage.persistent.session"],
) -> Objective:
    """Update an objective.

    Uses NotSet sentinel for parameters where None may be a valid value.

    Raises:
        KeyError: If objective_id does not correspond to an objective
    """
    values: dict[str, t.Any] = {}
    if not isinstance(title, NotSet):
        values["title"] = title
    if not isinstance(description, NotSet):
        values["description"] = description
    if not isinstance(scope_boundaries, NotSet):
        values["scope_boundaries"] = scope_boundaries
    if not isinstance(time_expectation_minutes, NotSet):
        values["time_expectation_minutes"] = time_expectation_minutes
    if not isinstance(initial_prompts, NotSet):
        values["initial_prompts"] = initial_prompts
    if not isinstance(challenge_prompts, NotSet):
        values["challenge_prompts"] = challenge_prompts
    if not isinstance(extension_policy, NotSet):
        values["extension_policy"] = extension_policy.value
    if not isinstance(status, NotSet):
        values["status"] = status.value

    if values:
        stmt = sqla.update(objectives).where(objectives.objective_id == objective_id).values(**values)
    else:
        # No-op update to verify objective exists
        stmt = sqla.update(objectives).where(objectives.objective_id == objective_id).values(objective_id=objective_id)

    result = session.execute(stmt)
    if result.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue]
        raise KeyError(f"Objective {objective_id} not found")

    session.flush()
    obj = get(objective_id, session=session)
    assert obj is not None
    return obj
