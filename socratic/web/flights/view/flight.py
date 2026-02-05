"""View models for flights."""

from __future__ import annotations

import datetime
import typing as t

from socratic.model import AttemptID, BaseModel, Flight, FlightID, FlightStatus, FlightWithTemplate, PromptTemplateID


class FlightCreateRequest(BaseModel):
    """Request to create a flight.

    Template resolution modes:
    - template only: uses the latest active version of the named template
    - template + template_content: content-addressed lookup — reuses an existing
      version if the content matches, otherwise creates a new version
    """

    template: str
    template_content: str | None = None
    created_by: str
    feature_flags: dict[str, t.Any] = {}
    context: dict[str, t.Any] = {}
    model_provider: str
    model_name: str
    model_config_data: dict[str, t.Any] = {}
    attempt_id: AttemptID | None = None


class FlightView(BaseModel):
    """View for a flight."""

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

    @classmethod
    def from_model(cls, flight: Flight | FlightWithTemplate) -> FlightView:
        return cls(
            flight_id=flight.flight_id,
            template_id=flight.template_id,
            template_name=flight.template_name if isinstance(flight, FlightWithTemplate) else None,
            template_version=flight.template_version if isinstance(flight, FlightWithTemplate) else None,
            created_by=flight.created_by,
            feature_flags=flight.feature_flags,
            context=flight.context,
            rendered_content=flight.rendered_content,
            model_provider=flight.model_provider,
            model_name=flight.model_name,
            model_config_data=flight.model_config_data,
            status=flight.status,
            started_at=flight.started_at,
            completed_at=flight.completed_at,
            attempt_id=flight.attempt_id,
            outcome_metadata=flight.outcome_metadata,
            create_time=flight.create_time,
            update_time=flight.update_time,
        )


class FlightListView(BaseModel):
    """Response for listing flights."""

    flights: list[FlightView]

    @classmethod
    def from_model(cls, flights: t.Sequence[Flight | FlightWithTemplate]) -> FlightListView:
        return cls(flights=[FlightView.from_model(f) for f in flights])


class FlightUpdateRequest(BaseModel):
    """Request to update a flight."""

    status: FlightStatus | None = None
    outcome_metadata: dict[str, t.Any] | None = None
