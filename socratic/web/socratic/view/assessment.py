"""View models for assessment chat interface."""

from __future__ import annotations

import datetime

import pydantic as p

from socratic.model import AssignmentID, AttemptID, ObjectiveID, TranscriptSegmentID, UtteranceType


class StartAssessmentRequest(p.BaseModel):
    """Request to start a new assessment attempt."""

    # No body needed - assignment_id comes from URL path


class StartAssessmentResponse(p.BaseModel):
    """Response with attempt ID and initial orientation message."""

    attempt_id: AttemptID
    assignment_id: AssignmentID
    objective_id: ObjectiveID
    objective_title: str
    message: str  # Initial orientation message (collected after SSE stream completes)


class StartAssessmentOkResponse(p.BaseModel):
    """Immediate response when starting an assessment.

    The orientation message will be streamed via the /stream endpoint.
    """

    attempt_id: AttemptID
    assignment_id: AssignmentID
    objective_id: ObjectiveID
    objective_title: str


class MessageAcceptedResponse(p.BaseModel):
    """Response when a message is accepted for processing.

    The AI response will be streamed via the /stream endpoint.
    """

    message_id: TranscriptSegmentID


class SendMessageRequest(p.BaseModel):
    """Request to send a learner message."""

    content: str = p.Field(..., min_length=1, max_length=10000)


class AssessmentStatusResponse(p.BaseModel):
    """Current assessment status."""

    attempt_id: AttemptID
    phase: str
    message_count: int
    prompts_completed: int
    total_prompts: int
    consent_confirmed: bool


class CompleteAssessmentRequest(p.BaseModel):
    """Request to complete an assessment."""

    # Optional learner feedback
    feedback: str | None = None


class CompleteAssessmentOkResponse(p.BaseModel):
    """Response after completing an assessment."""

    attempt_id: AttemptID
    status: str
    completed_at: datetime.datetime


class TranscriptMessageResponse(p.BaseModel):
    """A single message in the transcript."""

    segment_id: TranscriptSegmentID
    utterance_type: UtteranceType
    content: str
    start_time: datetime.datetime


class TranscriptResponse(p.BaseModel):
    """Full assessment transcript."""

    attempt_id: AttemptID
    objective_title: str
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    messages: list[TranscriptMessageResponse]


class UploadVideoResponse(p.BaseModel):
    """Response after uploading assessment video."""

    attempt_id: AttemptID
    video_url: str
    size: int


class UploadVideoChunkResponse(p.BaseModel):
    """Response after uploading a video chunk."""

    attempt_id: AttemptID
    sequence: int
    size: int
    total_chunks: int


class FinalizeVideoResponse(p.BaseModel):
    """Response after finalizing chunked video upload."""

    attempt_id: AttemptID
    video_url: str
    total_size: int
    chunks_assembled: int


class ErrorResponse(p.BaseModel):
    """Error response for assessment operations."""

    error: str
    detail: str | None = None
