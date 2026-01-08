import enum

from .base import BaseModel, WithCtime
from .id import AttemptID, EvaluationResultID, RubricCriterionID


class AssessmentFlag(enum.Enum):
    HighFluencyLowSubstance = "high_fluency_low_substance"
    RepeatedEvasion = "repeated_evasion"
    VocabularyMirroring = "vocabulary_mirroring"
    InconsistentReasoning = "inconsistent_reasoning"
    PossibleGaming = "possible_gaming"
    LowConfidence = "low_confidence"


class EvidenceMapping(BaseModel):  # Not timestamped, embedded in EvaluationResult
    criterion_id: RubricCriterionID
    segment_ids: list[str] = []
    evidence_summary: str | None = None
    strength: str | None = None
    failure_modes_detected: list[str] = []


class EvaluationResult(BaseModel, WithCtime):
    evaluation_id: EvaluationResultID
    attempt_id: AttemptID

    evidence_mappings: list[EvidenceMapping] = []
    flags: list[AssessmentFlag] = []
    strengths: list[str] = []
    gaps: list[str] = []

    reasoning_summary: str | None = None
