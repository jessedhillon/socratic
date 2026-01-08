"""View models for assignment management."""

from __future__ import annotations

import datetime
import decimal

import pydantic as p

from socratic.model import AssignmentID, AttemptID, AttemptStatus, Grade, ObjectiveID, OrganizationID, RetakePolicy, \
    UserID


class AssignmentCreateRequest(p.BaseModel):
    """Request to create a new assignment."""

    objective_id: ObjectiveID
    assigned_to: UserID
    available_from: datetime.datetime | None = None
    available_until: datetime.datetime | None = None
    max_attempts: int = 1
    retake_policy: RetakePolicy = RetakePolicy.None_
    retake_delay_hours: int | None = None


class BulkAssignmentCreateRequest(p.BaseModel):
    """Request to create assignments for multiple learners."""

    objective_id: ObjectiveID
    assigned_to: list[UserID]
    available_from: datetime.datetime | None = None
    available_until: datetime.datetime | None = None
    max_attempts: int = 1
    retake_policy: RetakePolicy = RetakePolicy.None_
    retake_delay_hours: int | None = None


class AssignmentUpdateRequest(p.BaseModel):
    """Request to update an assignment."""

    available_from: datetime.datetime | None = None
    available_until: datetime.datetime | None = None
    max_attempts: int | None = None
    retake_policy: RetakePolicy | None = None
    retake_delay_hours: int | None = None


class AssignmentResponse(p.BaseModel):
    """Assignment details response."""

    assignment_id: AssignmentID
    organization_id: OrganizationID
    objective_id: ObjectiveID
    assigned_by: UserID
    assigned_to: UserID
    available_from: datetime.datetime | None = None
    available_until: datetime.datetime | None = None
    max_attempts: int
    retake_policy: RetakePolicy
    retake_delay_hours: int | None = None
    create_time: datetime.datetime
    update_time: datetime.datetime | None = None


class AssignmentListResponse(p.BaseModel):
    """List of assignments response."""

    assignments: list[AssignmentResponse]
    total: int


class AttemptResponse(p.BaseModel):
    """Assessment attempt response."""

    attempt_id: AttemptID
    assignment_id: AssignmentID
    learner_id: UserID
    status: AttemptStatus
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None
    grade: Grade | None = None
    confidence_score: decimal.Decimal | None = None
    create_time: datetime.datetime


class AssignmentWithAttemptsResponse(p.BaseModel):
    """Assignment with attempt history."""

    assignment_id: AssignmentID
    organization_id: OrganizationID
    objective_id: ObjectiveID
    assigned_by: UserID
    assigned_to: UserID
    available_from: datetime.datetime | None = None
    available_until: datetime.datetime | None = None
    max_attempts: int
    retake_policy: RetakePolicy
    retake_delay_hours: int | None = None
    create_time: datetime.datetime
    update_time: datetime.datetime | None = None
    attempts: list[AttemptResponse] = []
    attempts_remaining: int = 0


class LearnerResponse(p.BaseModel):
    """Learner information for educators."""

    user_id: UserID
    email: str
    name: str


class LearnerListResponse(p.BaseModel):
    """List of learners response."""

    learners: list[LearnerResponse]
    total: int


class LearnerAssignmentSummary(p.BaseModel):
    """Summary of a learner's assignment status."""

    assignment_id: AssignmentID
    objective_id: ObjectiveID
    objective_title: str
    status: AttemptStatus
    grade: Grade | None = None
    attempts_used: int
    attempts_remaining: int
    available_from: datetime.datetime | None = None
    available_until: datetime.datetime | None = None
    is_available: bool = True
    is_locked: bool = False  # True if prerequisites not met


class LearnerDashboardResponse(p.BaseModel):
    """Learner dashboard with all assignments."""

    assignments: list[LearnerAssignmentSummary]
    total_completed: int
    total_in_progress: int
    total_pending: int
