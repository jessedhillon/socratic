from __future__ import annotations

import typing as t

from sqlalchemy import select
from sqlalchemy import update as sql_update

from socratic.core import di
from socratic.model import DependencyType, ObjectiveDependency, ObjectiveID, ObjectiveInStrand, OrganizationID, \
    Strand, StrandID, UserID

from . import Session
from .table import objective_dependencies, objectives_in_strands, strands


def get(key: StrandID, session: Session = di.Provide["storage.persistent.session"]) -> Strand | None:
    stmt = select(strands.__table__).where(strands.strand_id == key)
    row = session.execute(stmt).mappings().one_or_none()
    return Strand(**row) if row else None


def find(
    *,
    organization_id: OrganizationID | None = None,
    created_by: UserID | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[Strand, ...]:
    stmt = select(strands.__table__)
    if organization_id is not None:
        stmt = stmt.where(strands.organization_id == organization_id)
    if created_by is not None:
        stmt = stmt.where(strands.created_by == created_by)
    rows = session.execute(stmt).mappings().all()
    return tuple(Strand(**row) for row in rows)


def create(params: StrandCreateParams, session: Session = di.Provide["storage.persistent.session"]) -> Strand:
    strand = strands(
        strand_id=StrandID(),
        organization_id=params["organization_id"],
        created_by=params["created_by"],
        name=params["name"],
        description=params.get("description"),
    )
    session.add(strand)
    session.flush()
    return get(strand.strand_id, session=session)  # type: ignore


def get_objectives_in_strand(
    strand_id: StrandID,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[ObjectiveInStrand, ...]:
    stmt = (
        select(objectives_in_strands.__table__)
        .where(objectives_in_strands.strand_id == strand_id)
        .order_by(objectives_in_strands.position)
    )
    rows = session.execute(stmt).mappings().all()
    return tuple(ObjectiveInStrand(**row) for row in rows)


def add_objective_to_strand(
    params: ObjectiveInStrandParams,
    session: Session = di.Provide["storage.persistent.session"],
) -> ObjectiveInStrand:
    obj_in_strand = objectives_in_strands(
        strand_id=params["strand_id"],
        objective_id=params["objective_id"],
        position=params["position"],
    )
    session.add(obj_in_strand)
    session.flush()
    return ObjectiveInStrand(**params)


def get_dependencies(
    objective_id: ObjectiveID,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[ObjectiveDependency, ...]:
    stmt = select(objective_dependencies.__table__).where(objective_dependencies.objective_id == objective_id)
    rows = session.execute(stmt).mappings().all()
    return tuple(ObjectiveDependency(**row) for row in rows)


def add_dependency(
    params: DependencyCreateParams,
    session: Session = di.Provide["storage.persistent.session"],
) -> ObjectiveDependency:
    dep = objective_dependencies(
        objective_id=params["objective_id"],
        depends_on_objective_id=params["depends_on_objective_id"],
        dependency_type=params.get("dependency_type", DependencyType.Hard).value,
    )
    session.add(dep)
    session.flush()
    return ObjectiveDependency(**params)


def update(
    key: StrandID,
    params: StrandUpdateParams,
    session: Session = di.Provide["storage.persistent.session"],
) -> Strand | None:
    stmt = select(strands).where(strands.strand_id == key)
    strand = session.execute(stmt).scalar_one_or_none()
    if strand is None:
        return None
    for field, value in params.items():
        if value is not None:
            setattr(strand, field, value)
    session.flush()
    return get(key, session=session)


def reorder_objectives_in_strand(
    strand_id: StrandID,
    objective_ids: list[ObjectiveID],
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    for position, objective_id in enumerate(objective_ids):
        stmt = (
            sql_update(objectives_in_strands)
            .where(objectives_in_strands.strand_id == strand_id)
            .where(objectives_in_strands.objective_id == objective_id)
            .values(position=position)
        )
        session.execute(stmt)


class StrandCreateParams(t.TypedDict, total=False):
    organization_id: t.Required[OrganizationID]
    created_by: t.Required[UserID]
    name: t.Required[str]
    description: str | None


class StrandUpdateParams(t.TypedDict, total=False):
    name: str
    description: str | None


class ObjectiveInStrandParams(t.TypedDict):
    strand_id: StrandID
    objective_id: ObjectiveID
    position: int


class DependencyCreateParams(t.TypedDict, total=False):
    objective_id: t.Required[ObjectiveID]
    depends_on_objective_id: t.Required[ObjectiveID]
    dependency_type: DependencyType
