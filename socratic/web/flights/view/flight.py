"""View models for flights."""

from __future__ import annotations

import datetime
import typing as t

from socratic.model import AttemptID, BaseModel, FlightID, FlightStatus, PromptTemplateID


class FlightCreateRequest(BaseModel):
    """Request to create a flight."""

    template: str  # Template name (will use latest active version)
    created_by: str
    feature_flags: dict[str, t.Any] = {}
    context: dict[str, t.Any] = {}
    model_provider: str
    model_name: str
    model_config_data: dict[str, t.Any] = {}
    attempt_id: AttemptID | None = None


class FlightResponse(BaseModel):
    """Response for a flight."""

    flight_id: FlightID
    template_id: PromptTemplateID
    template_name: str | None = None
    template_version: int | None = None
    created_by: str
    feature_flags: dict[str, t.Any]
    context: dict[str, t.Any]
    rendered_content: str
    model_provider: str
    model_name: str
    model_config_data: dict[str, t.Any]
    status: FlightStatus
    started_at: datetime.datetime
    completed_at: datetime.datetime | None
    attempt_id: AttemptID | None
    outcome_metadata: dict[str, t.Any] | None
    create_time: datetime.datetime
    update_time: datetime.datetime


class FlightListResponse(BaseModel):
    """Response for listing flights."""

    flights: list[FlightResponse]


class FlightUpdateRequest(BaseModel):
    """Request to update a flight."""

    status: FlightStatus | None = None
    outcome_metadata: dict[str, t.Any] | None = None
