"""View models for educator review endpoints."""

from __future__ import annotations

import datetime
import decimal

import pydantic as p

from socratic.model import AssessmentFlag, AttemptID, AttemptStatus, EvaluationResultID, Grade, ObjectiveID, \
    OverrideID, RubricCriterionID, TranscriptSegmentID, UserID, UtteranceType


class EvidenceMappingResponse(p.BaseModel):
    """Evidence mapping for a rubric criterion."""

    criterion_id: RubricCriterionID
    criterion_name: str | None = None
    segment_ids: list[str]
    evidence_summary: str | None
    strength: str | None
    failure_modes_detected: list[str]


class TranscriptSegmentResponse(p.BaseModel):
    """A transcript segment in the review."""

    segment_id: TranscriptSegmentID
    utterance_type: UtteranceType
    content: str
    start_time: datetime.datetime
    prompt_index: int | None = None


class EvaluationResponse(p.BaseModel):
    """Evaluation result for the review."""

    evaluation_id: EvaluationResultID
    evidence_mappings: list[EvidenceMappingResponse]
    flags: list[AssessmentFlag]
    strengths: list[str]
    gaps: list[str]
    reasoning_summary: str | None
    create_time: datetime.datetime


class OverrideResponse(p.BaseModel):
    """An educator override record."""

    override_id: OverrideID
    educator_id: UserID
    educator_name: str | None = None
    original_grade: Grade | None
    new_grade: Grade
    reason: str
    feedback: str | None
    create_time: datetime.datetime


class AttemptResponse(p.BaseModel):
    """Assessment attempt in the review."""

    attempt_id: AttemptID
    learner_id: UserID
    learner_name: str | None = None
    status: AttemptStatus
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    grade: Grade | None
    confidence_score: decimal.Decimal | None


class ReviewSummary(p.BaseModel):
    """Summary of a review for listing."""

    attempt_id: AttemptID
    learner_id: UserID
    learner_name: str | None = None
    objective_id: ObjectiveID
    objective_title: str
    grade: Grade | None
    confidence_score: decimal.Decimal | None
    flags: list[AssessmentFlag]
    completed_at: datetime.datetime | None


class ReviewListResponse(p.BaseModel):
    """List of reviews pending educator attention."""

    reviews: list[ReviewSummary]
    total: int


class ReviewDetailResponse(p.BaseModel):
    """Full review detail for educator."""

    attempt: AttemptResponse
    evaluation: EvaluationResponse | None
    transcript: list[TranscriptSegmentResponse]
    override_history: list[OverrideResponse]

    # Context for the review
    objective_id: ObjectiveID
    objective_title: str
    objective_description: str


class GradeAcceptRequest(p.BaseModel):
    """Request to accept the AI-assigned grade."""

    # No fields needed - just confirms acceptance
    pass


class GradeOverrideRequest(p.BaseModel):
    """Request to override the grade."""

    new_grade: Grade
    reason: str = p.Field(..., min_length=10, max_length=1000)


class FeedbackRequest(p.BaseModel):
    """Request to add feedback."""

    feedback_text: str = p.Field(..., min_length=1, max_length=5000)
    visible_to_learner: bool = True


class FollowupAssignmentRequest(p.BaseModel):
    """Request to assign a follow-up objective."""

    objective_id: ObjectiveID
    reason: str | None = None
