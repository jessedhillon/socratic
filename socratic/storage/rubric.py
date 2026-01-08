from __future__ import annotations

import decimal
import typing as t

from sqlalchemy import select

from socratic.core import di
from socratic.model import FailureMode, GradeThreshold, ObjectiveID, RubricCriterion, RubricCriterionID

from . import Session
from .table import rubric_criteria


def get(key: RubricCriterionID, session: Session = di.Provide["storage.persistent.session"]) -> RubricCriterion | None:
    stmt = select(rubric_criteria.__table__).where(rubric_criteria.criterion_id == key)
    row = session.execute(stmt).mappings().one_or_none()
    return RubricCriterion(**row) if row else None


def find(
    *,
    objective_id: ObjectiveID | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[RubricCriterion, ...]:
    stmt = select(rubric_criteria.__table__)
    if objective_id is not None:
        stmt = stmt.where(rubric_criteria.objective_id == objective_id)
    rows = session.execute(stmt).mappings().all()
    return tuple(RubricCriterion(**row) for row in rows)


def create(
    params: RubricCriterionCreateParams, session: Session = di.Provide["storage.persistent.session"]
) -> RubricCriterion:
    failure_modes_data: list[dict[str, t.Any]] = [m.model_dump() for m in params.get("failure_modes", [])]
    grade_thresholds_data: list[dict[str, t.Any]] = [th.model_dump() for th in params.get("grade_thresholds", [])]

    criterion = rubric_criteria(
        criterion_id=RubricCriterionID(),
        objective_id=params["objective_id"],
        name=params["name"],
        description=params["description"],
        evidence_indicators=params.get("evidence_indicators", []),
        failure_modes=failure_modes_data,
        grade_thresholds=grade_thresholds_data,
        weight=params.get("weight", decimal.Decimal("1.0")),
    )
    session.add(criterion)
    session.flush()
    return get(criterion.criterion_id, session=session)  # type: ignore


def delete(key: RubricCriterionID, session: Session = di.Provide["storage.persistent.session"]) -> bool:
    stmt = select(rubric_criteria).where(rubric_criteria.criterion_id == key)
    criterion = session.execute(stmt).scalar_one_or_none()
    if criterion is None:
        return False
    session.delete(criterion)
    session.flush()
    return True


class RubricCriterionCreateParams(t.TypedDict, total=False):
    objective_id: t.Required[ObjectiveID]
    name: t.Required[str]
    description: t.Required[str]
    evidence_indicators: list[str]
    failure_modes: list[FailureMode]
    grade_thresholds: list[GradeThreshold]
    weight: decimal.Decimal
