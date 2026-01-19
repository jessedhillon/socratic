from .base import BaseModel
from .id import ObjectiveID, RubricCriterionID


class ProficiencyLevel(BaseModel):
    """Describes what a response at a specific grade level looks like."""

    grade: str
    description: str


class RubricCriterion(BaseModel):
    criterion_id: RubricCriterionID
    objective_id: ObjectiveID

    name: str
    description: str
    proficiency_levels: list[ProficiencyLevel] = []
    evidence_indicators: list[str] = []
    failure_modes: list[str] = []
