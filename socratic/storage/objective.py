from __future__ import annotations

import typing as t

from sqlalchemy import select

from socratic.core import di
from socratic.model import ExtensionPolicy, Objective, ObjectiveID, ObjectiveStatus, OrganizationID, UserID

from . import Session
from .table import objectives


def get(key: ObjectiveID, session: Session = di.Provide["storage.persistent.session"]) -> Objective | None:
    stmt = select(objectives.__table__).where(objectives.objective_id == key)
    row = session.execute(stmt).mappings().one_or_none()
    return Objective(**row) if row else None


def find(
    *,
    organization_id: OrganizationID | None = None,
    created_by: UserID | None = None,
    status: ObjectiveStatus | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[Objective, ...]:
    stmt = select(objectives.__table__)
    if organization_id is not None:
        stmt = stmt.where(objectives.organization_id == organization_id)
    if created_by is not None:
        stmt = stmt.where(objectives.created_by == created_by)
    if status is not None:
        stmt = stmt.where(objectives.status == status.value)
    rows = session.execute(stmt).mappings().all()
    return tuple(Objective(**row) for row in rows)


def create(params: ObjectiveCreateParams, session: Session = di.Provide["storage.persistent.session"]) -> Objective:
    obj = objectives(
        objective_id=ObjectiveID(),
        organization_id=params["organization_id"],
        created_by=params["created_by"],
        title=params["title"],
        description=params["description"],
        scope_boundaries=params.get("scope_boundaries"),
        time_expectation_minutes=params.get("time_expectation_minutes"),
        initial_prompts=params.get("initial_prompts", []),
        challenge_prompts=params.get("challenge_prompts", []),
        extension_policy=params.get("extension_policy", ExtensionPolicy.Disallowed).value,
        status=params.get("status", ObjectiveStatus.Draft).value,
    )
    session.add(obj)
    session.flush()
    return get(obj.objective_id, session=session)  # type: ignore


def update(
    key: ObjectiveID,
    params: ObjectiveUpdateParams,
    session: Session = di.Provide["storage.persistent.session"],
) -> Objective | None:
    stmt = select(objectives).where(objectives.objective_id == key)
    obj = session.execute(stmt).scalar_one_or_none()
    if obj is None:
        return None
    for field, value in params.items():
        if value is not None:
            actual_value: t.Any = value
            if field in ("extension_policy", "status") and hasattr(value, "value"):
                actual_value = value.value  # type: ignore[union-attr]
            setattr(obj, field, actual_value)
    session.flush()
    return get(key, session=session)


class ObjectiveCreateParams(t.TypedDict, total=False):
    organization_id: t.Required[OrganizationID]
    created_by: t.Required[UserID]
    title: t.Required[str]
    description: t.Required[str]
    scope_boundaries: str | None
    time_expectation_minutes: int | None
    initial_prompts: list[str]
    challenge_prompts: list[str]
    extension_policy: ExtensionPolicy
    status: ObjectiveStatus


class ObjectiveUpdateParams(t.TypedDict, total=False):
    title: str
    description: str
    scope_boundaries: str | None
    time_expectation_minutes: int | None
    initial_prompts: list[str]
    challenge_prompts: list[str]
    extension_policy: ExtensionPolicy
    status: ObjectiveStatus
