from __future__ import annotations

import decimal
import typing as t

import pydantic as p
import sqlalchemy as sqla

from socratic.core import di
from socratic.model import ObjectiveID, RubricCriterion, RubricCriterionID

from . import Session
from .table import rubric_criteria


class GradeThresholdCreateParams(p.BaseModel):
    """Parameters for creating a grade threshold."""

    model_config = p.ConfigDict(frozen=True)

    grade: str
    description: str
    min_evidence_count: int | None = None


class FailureModeCreateParams(p.BaseModel):
    """Parameters for creating a failure mode."""

    model_config = p.ConfigDict(frozen=True)

    name: str
    description: str
    indicators: list[str] = []


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
    evidence_indicators: list[str] | None = None,
    failure_modes: list[FailureModeCreateParams] | None = None,
    grade_thresholds: list[GradeThresholdCreateParams] | None = None,
    weight: decimal.Decimal = decimal.Decimal("1.0"),
    session: Session = di.Provide["storage.persistent.session"],
) -> RubricCriterion:
    """Create a new rubric criterion."""
    failure_modes_data: list[dict[str, t.Any]] = [m.model_dump() for m in (failure_modes or [])]
    grade_thresholds_data: list[dict[str, t.Any]] = [th.model_dump() for th in (grade_thresholds or [])]

    criterion_id = RubricCriterionID()
    stmt = sqla.insert(rubric_criteria).values(
        criterion_id=criterion_id,
        objective_id=objective_id,
        name=name,
        description=description,
        evidence_indicators=evidence_indicators if evidence_indicators is not None else [],
        failure_modes=failure_modes_data,
        grade_thresholds=grade_thresholds_data,
        weight=weight,
    )
    session.execute(stmt)
    session.flush()
    result = get(criterion_id, session=session)
    assert result is not None
    return result


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
