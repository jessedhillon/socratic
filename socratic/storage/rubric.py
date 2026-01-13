from __future__ import annotations

import typing as t

import pydantic as p
import sqlalchemy as sqla

from socratic.core import di
from socratic.lib import NotSet
from socratic.model import ObjectiveID, RubricCriterion, RubricCriterionID

from . import Session
from .table import rubric_criteria


class ProficiencyLevelCreateParams(p.BaseModel):
    """Parameters for creating a proficiency level."""

    model_config = p.ConfigDict(frozen=True)

    grade: str
    description: str


def get(
    criterion_id: RubricCriterionID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> RubricCriterion | None:
    """Get a rubric criterion by ID."""
    stmt = sqla.select(rubric_criteria.__table__).where(rubric_criteria.criterion_id == criterion_id)
    row = session.execute(stmt).mappings().one_or_none()
    return RubricCriterion(**row) if row else None


def find(
    *,
    objective_id: ObjectiveID | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[RubricCriterion, ...]:
    """Find rubric criteria matching criteria."""
    stmt = sqla.select(rubric_criteria.__table__)
    if objective_id is not None:
        stmt = stmt.where(rubric_criteria.objective_id == objective_id)
    rows = session.execute(stmt).mappings().all()
    return tuple(RubricCriterion(**row) for row in rows)


def create(
    *,
    objective_id: ObjectiveID,
    name: str,
    description: str,
    proficiency_levels: list[ProficiencyLevelCreateParams] | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> RubricCriterion:
    """Create a new rubric criterion."""
    proficiency_levels_data: list[dict[str, t.Any]] = [pl.model_dump() for pl in (proficiency_levels or [])]

    criterion_id = RubricCriterionID()
    stmt = sqla.insert(rubric_criteria).values(
        criterion_id=criterion_id,
        objective_id=objective_id,
        name=name,
        description=description,
        proficiency_levels=proficiency_levels_data,
    )
    session.execute(stmt)
    session.flush()
    result = get(criterion_id, session=session)
    assert result is not None
    return result


def update(
    criterion_id: RubricCriterionID,
    *,
    name: str | NotSet = NotSet(),
    description: str | NotSet = NotSet(),
    proficiency_levels: list[ProficiencyLevelCreateParams] | NotSet = NotSet(),
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    """Update a rubric criterion.

    Uses NotSet sentinel for parameters where None may be a valid value.
    Call get() after if you need the updated entity.

    Raises:
        KeyError: If criterion_id does not correspond to a criterion
    """
    values: dict[str, t.Any] = {}
    if not isinstance(name, NotSet):
        values["name"] = name
    if not isinstance(description, NotSet):
        values["description"] = description
    if not isinstance(proficiency_levels, NotSet):
        values["proficiency_levels"] = [pl.model_dump() for pl in proficiency_levels]

    if values:
        stmt = sqla.update(rubric_criteria).where(rubric_criteria.criterion_id == criterion_id).values(**values)
    else:
        # No-op update to verify criterion exists
        stmt = (
            sqla
            .update(rubric_criteria)
            .where(rubric_criteria.criterion_id == criterion_id)
            .values(criterion_id=criterion_id)
        )

    result = session.execute(stmt)
    if result.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue]
        raise KeyError(f"RubricCriterion {criterion_id} not found")

    session.flush()


def delete(
    criterion_id: RubricCriterionID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> bool:
    """Delete a rubric criterion.

    Returns:
        True if a criterion was deleted, False if not found
    """
    stmt = sqla.delete(rubric_criteria).where(rubric_criteria.criterion_id == criterion_id)
    result = session.execute(stmt)
    return bool(result.rowcount)  # pyright: ignore[reportUnknownArgumentType, reportAttributeAccessIssue]
