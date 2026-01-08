import decimal

from .base import BaseModel
from .id import ObjectiveID, RubricCriterionID


class GradeThreshold(BaseModel):
    grade: str
    description: str
    min_evidence_count: int | None = None


class FailureMode(BaseModel):
    name: str
    description: str
    indicators: list[str] = []


class RubricCriterion(BaseModel):
    criterion_id: RubricCriterionID
    objective_id: ObjectiveID

    name: str
    description: str
    evidence_indicators: list[str] = []
    failure_modes: list[FailureMode] = []
    grade_thresholds: list[GradeThreshold] = []
    weight: decimal.Decimal = decimal.Decimal("1.0")
