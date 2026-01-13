"""View models for objective management."""

from __future__ import annotations

import datetime
import decimal

import pydantic as p

from socratic.model import ExtensionPolicy, ObjectiveID, ObjectiveStatus, OrganizationID, RubricCriterionID, UserID


class GradeThresholdRequest(p.BaseModel):
    """Grade threshold input."""

    grade: str
    description: str
    min_evidence_count: int | None = None


class FailureModeRequest(p.BaseModel):
    """Failure mode input."""

    name: str
    description: str
    indicators: list[str] = []


class RubricCriterionRequest(p.BaseModel):
    """Rubric criterion input for creating/updating objectives."""

    name: str
    description: str
    evidence_indicators: list[str] = []
    failure_modes: list[FailureModeRequest] = []
    grade_thresholds: list[GradeThresholdRequest] = []
    weight: decimal.Decimal = decimal.Decimal("1.0")


class ObjectiveCreateRequest(p.BaseModel):
    """Request to create a new objective."""

    title: str
    description: str
    scope_boundaries: str | None = None
    time_expectation_minutes: int | None = None
    initial_prompts: list[str] = []
    challenge_prompts: list[str] = []
    extension_policy: ExtensionPolicy = ExtensionPolicy.Disallowed
    rubric_criteria: list[RubricCriterionRequest] = []


class ObjectiveUpdateRequest(p.BaseModel):
    """Request to update an objective."""

    title: str | None = None
    description: str | None = None
    scope_boundaries: str | None = None
    time_expectation_minutes: int | None = None
    initial_prompts: list[str] | None = None
    challenge_prompts: list[str] | None = None
    extension_policy: ExtensionPolicy | None = None
    status: ObjectiveStatus | None = None


class GradeThresholdResponse(p.BaseModel):
    """Grade threshold output."""

    grade: str
    description: str
    min_evidence_count: int | None = None


class FailureModeResponse(p.BaseModel):
    """Failure mode output."""

    name: str
    description: str
    indicators: list[str] = []


class RubricCriterionResponse(p.BaseModel):
    """Rubric criterion output."""

    criterion_id: RubricCriterionID
    objective_id: ObjectiveID
    name: str
    description: str
    evidence_indicators: list[str] = []
    failure_modes: list[FailureModeResponse] = []
    grade_thresholds: list[GradeThresholdResponse] = []
    weight: decimal.Decimal


class ObjectiveResponse(p.BaseModel):
    """Objective details response."""

    objective_id: ObjectiveID
    organization_id: OrganizationID
    created_by: UserID
    title: str
    description: str
    scope_boundaries: str | None = None
    time_expectation_minutes: int | None = None
    initial_prompts: list[str] = []
    challenge_prompts: list[str] = []
    extension_policy: ExtensionPolicy
    status: ObjectiveStatus
    create_time: datetime.datetime
    update_time: datetime.datetime | None = None
    rubric_criteria: list[RubricCriterionResponse] = []


class ObjectiveListResponse(p.BaseModel):
    """List of objectives response."""

    objectives: list[ObjectiveResponse]
    total: int


class RubricCriterionCreateRequest(p.BaseModel):
    """Request to add a rubric criterion to an existing objective."""

    name: str
    description: str
    evidence_indicators: list[str] = []
    failure_modes: list[FailureModeRequest] = []
    grade_thresholds: list[GradeThresholdRequest] = []
    weight: decimal.Decimal = decimal.Decimal("1.0")


class RubricCriterionUpdateRequest(p.BaseModel):
    """Request to update a rubric criterion."""

    name: str | None = None
    description: str | None = None
    evidence_indicators: list[str] | None = None
    failure_modes: list[FailureModeRequest] | None = None
    grade_thresholds: list[GradeThresholdRequest] | None = None
    weight: decimal.Decimal | None = None
