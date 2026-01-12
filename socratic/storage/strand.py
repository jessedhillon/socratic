from __future__ import annotations

import typing as t

import sqlalchemy as sqla

from socratic.core import di
from socratic.lib import NotSet
from socratic.model import DependencyType, ObjectiveDependency, ObjectiveID, ObjectiveInStrand, OrganizationID, \
    Strand, StrandID, UserID

from . import Session
from .table import objective_dependencies, objectives_in_strands, strands


def get(
    strand_id: StrandID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> Strand | None:
    """Get a strand by ID."""
    stmt = sqla.select(strands.__table__).where(strands.strand_id == strand_id)
    row = session.execute(stmt).mappings().one_or_none()
    return Strand(**row) if row else None


def find(
    *,
    organization_id: OrganizationID | None = None,
    created_by: UserID | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[Strand, ...]:
    """Find strands matching criteria."""
    stmt = sqla.select(strands.__table__)
    if organization_id is not None:
        stmt = stmt.where(strands.organization_id == organization_id)
    if created_by is not None:
        stmt = stmt.where(strands.created_by == created_by)
    rows = session.execute(stmt).mappings().all()
    return tuple(Strand(**row) for row in rows)


def create(
    *,
    organization_id: OrganizationID,
    created_by: UserID,
    name: str,
    description: str | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> Strand:
    """Create a new strand."""
    strand_id = StrandID()
    stmt = sqla.insert(strands).values(
        strand_id=strand_id,
        organization_id=organization_id,
        created_by=created_by,
        name=name,
        description=description,
    )
    session.execute(stmt)
    session.flush()
    result = get(strand_id, session=session)
    assert result is not None
    return result


def update(
    strand_id: StrandID,
    *,
    name: str | NotSet = NotSet(),
    description: str | None | NotSet = NotSet(),
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    """Update a strand.

    Call get() after if you need the updated entity.

    Raises:
        KeyError: If strand_id not found
    """
    update_values: dict[str, t.Any] = {}
    if not isinstance(name, NotSet):
        update_values["name"] = name
    if not isinstance(description, NotSet):
        update_values["description"] = description

    stmt = sqla.update(strands).where(strands.strand_id == strand_id).values(**update_values)
    result = session.execute(stmt)
    if result.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue]
        raise KeyError(strand_id)
    session.flush()


def get_objectives_in_strand(
    strand_id: StrandID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[ObjectiveInStrand, ...]:
    """Get objectives in a strand, ordered by position."""
    stmt = (
        sqla
        .select(objectives_in_strands.__table__)
        .where(objectives_in_strands.strand_id == strand_id)
        .order_by(objectives_in_strands.position)
    )
    rows = session.execute(stmt).mappings().all()
    return tuple(ObjectiveInStrand(**row) for row in rows)


def add_objective_to_strand(
    *,
    strand_id: StrandID,
    objective_id: ObjectiveID,
    position: int,
    session: Session = di.Provide["storage.persistent.session"],
) -> ObjectiveInStrand:
    """Add an objective to a strand at a given position."""
    stmt = sqla.insert(objectives_in_strands).values(
        strand_id=strand_id,
        objective_id=objective_id,
        position=position,
    )
    session.execute(stmt)
    session.flush()
    return ObjectiveInStrand(
        strand_id=strand_id,
        objective_id=objective_id,
        position=position,
    )


def remove_objective_from_strand(
    *,
    strand_id: StrandID,
    objective_id: ObjectiveID,
    session: Session = di.Provide["storage.persistent.session"],
) -> bool:
    """Remove an objective from a strand.

    Returns:
        True if removed, False if not found
    """
    stmt = sqla.delete(objectives_in_strands).where(
        sqla.and_(
            objectives_in_strands.strand_id == strand_id,
            objectives_in_strands.objective_id == objective_id,
        )
    )
    result = session.execute(stmt)
    return bool(result.rowcount)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownArgumentType]


def reorder_objectives_in_strand(
    strand_id: StrandID,
    objective_ids: list[ObjectiveID],
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    """Reorder objectives within a strand."""
    for position, objective_id in enumerate(objective_ids):
        stmt = (
            sqla
            .update(objectives_in_strands)
            .where(objectives_in_strands.strand_id == strand_id)
            .where(objectives_in_strands.objective_id == objective_id)
            .values(position=position)
        )
        session.execute(stmt)


def get_dependencies(
    objective_id: ObjectiveID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[ObjectiveDependency, ...]:
    """Get dependencies for an objective."""
    stmt = sqla.select(objective_dependencies.__table__).where(objective_dependencies.objective_id == objective_id)
    rows = session.execute(stmt).mappings().all()
    return tuple(ObjectiveDependency(**row) for row in rows)


def add_dependency(
    *,
    objective_id: ObjectiveID,
    depends_on_objective_id: ObjectiveID,
    dependency_type: DependencyType = DependencyType.Hard,
    session: Session = di.Provide["storage.persistent.session"],
) -> ObjectiveDependency:
    """Add a dependency between objectives."""
    stmt = sqla.insert(objective_dependencies).values(
        objective_id=objective_id,
        depends_on_objective_id=depends_on_objective_id,
        dependency_type=dependency_type.value,
    )
    session.execute(stmt)
    session.flush()
    return ObjectiveDependency(
        objective_id=objective_id,
        depends_on_objective_id=depends_on_objective_id,
        dependency_type=dependency_type,
    )


def remove_dependency(
    *,
    objective_id: ObjectiveID,
    depends_on_objective_id: ObjectiveID,
    session: Session = di.Provide["storage.persistent.session"],
) -> bool:
    """Remove a dependency between objectives.

    Returns:
        True if removed, False if not found
    """
    stmt = sqla.delete(objective_dependencies).where(
        sqla.and_(
            objective_dependencies.objective_id == objective_id,
            objective_dependencies.depends_on_objective_id == depends_on_objective_id,
        )
    )
    result = session.execute(stmt)
    return bool(result.rowcount)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownArgumentType]
