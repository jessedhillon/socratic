"""Flight routes."""

from __future__ import annotations

import datetime
import typing as t

import jinja2
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from socratic.core import di
from socratic.model import AttemptID, FlightID, FlightStatus, FlightWithTemplate, PromptTemplateID
from socratic.storage import flight as flight_storage

from ..view import FlightCreateRequest, FlightListResponse, FlightResponse, FlightUpdateRequest

router = APIRouter(prefix="/api/flights", tags=["flights"])


def _render_template(content: str, context: dict[str, t.Any]) -> str:
    """Render a Jinja2 template with the given context."""
    env = jinja2.Environment(autoescape=False)
    template = env.from_string(content)
    return template.render(**context)


@router.get("", operation_id="list_flights")
@di.inject
def list_flights(
    template_id: PromptTemplateID | None = None,
    attempt_id: AttemptID | None = None,
    status_filter: FlightStatus | None = None,
    created_by: str | None = None,
    limit: int | None = 50,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> FlightListResponse:
    """List flights with optional filters."""
    with session.begin():
        flights = t.cast(
            tuple[FlightWithTemplate, ...],
            flight_storage.find_flights(
                template_id=template_id,
                attempt_id=attempt_id,
                status=status_filter,
                created_by=created_by,
                limit=limit,
                with_template=True,
                session=session,
            ),
        )
        return FlightListResponse(
            flights=[
                FlightResponse(
                    flight_id=f.flight_id,
                    template_id=f.template_id,
                    template_name=f.template_name,
                    template_version=f.template_version,
                    created_by=f.created_by,
                    feature_flags=f.feature_flags,
                    context=f.context,
                    rendered_content=f.rendered_content,
                    model_provider=f.model_provider,
                    model_name=f.model_name,
                    model_config_data=f.model_config_data,
                    status=f.status,
                    started_at=f.started_at,
                    completed_at=f.completed_at,
                    attempt_id=f.attempt_id,
                    outcome_metadata=f.outcome_metadata,
                    create_time=f.create_time,
                    update_time=f.update_time,
                )
                for f in flights
            ]
        )


@router.get("/{flight_id}", operation_id="get_flight")
@di.inject
def get_flight(
    flight_id: FlightID,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> FlightResponse:
    """Get a specific flight by ID."""
    with session.begin():
        flight = flight_storage.get_flight(flight_id, with_template=True, session=session)
        if flight is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flight not found",
            )
        return FlightResponse(
            flight_id=flight.flight_id,
            template_id=flight.template_id,
            template_name=flight.template_name,
            template_version=flight.template_version,
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


@router.post("", operation_id="create_flight", status_code=status.HTTP_201_CREATED)
@di.inject
def create_flight(
    request: FlightCreateRequest,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> FlightResponse:
    """Create a new flight.

    Looks up the template by name (latest active version), renders it with the
    provided context and feature flags, and returns the flight with the rendered content.
    """
    with session.begin():
        # Get the template
        template = flight_storage.get_template(name=request.template, session=session)
        if template is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{request.template}' not found",
            )

        # Combine feature flags and context for rendering
        render_context = {**request.feature_flags, **request.context}

        # Render the template
        try:
            rendered_content = _render_template(template.content, render_context)
        except jinja2.TemplateError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template rendering error: {e!s}",
            ) from e

        # Create the flight
        flight = flight_storage.create_flight(
            template_id=template.template_id,
            created_by=request.created_by,
            rendered_content=rendered_content,
            model_provider=request.model_provider,
            model_name=request.model_name,
            started_at=datetime.datetime.now(datetime.UTC),
            feature_flags=request.feature_flags,
            context=request.context,
            model_config=request.model_config_data,
            attempt_id=request.attempt_id,
            session=session,
        )

        return FlightResponse(
            flight_id=flight.flight_id,
            template_id=flight.template_id,
            template_name=template.name,
            template_version=template.version,
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


@router.patch("/{flight_id}", operation_id="update_flight")
@di.inject
def update_flight(
    flight_id: FlightID,
    request: FlightUpdateRequest,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> FlightResponse:
    """Update a flight's status or outcome metadata."""
    with session.begin():
        try:
            if request.status is not None:
                if request.status in (FlightStatus.Completed, FlightStatus.Abandoned):
                    completed_at = datetime.datetime.now(datetime.UTC)
                else:
                    completed_at = None
                flight_storage.update_flight(
                    flight_id,
                    status=request.status,
                    completed_at=completed_at,
                    outcome_metadata=request.outcome_metadata
                    if request.outcome_metadata is not None
                    else flight_storage.NotSet(),
                    session=session,
                )
            elif request.outcome_metadata is not None:
                flight_storage.update_flight(
                    flight_id,
                    outcome_metadata=request.outcome_metadata,
                    session=session,
                )
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flight not found",
            ) from None

        flight = flight_storage.get_flight(flight_id, with_template=True, session=session)
        assert flight is not None
        return FlightResponse(
            flight_id=flight.flight_id,
            template_id=flight.template_id,
            template_name=flight.template_name,
            template_version=flight.template_version,
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


@router.post("/{flight_id}/complete", operation_id="complete_flight")
@di.inject
def complete_flight(
    flight_id: FlightID,
    outcome_metadata: dict[str, t.Any] | None = None,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> FlightResponse:
    """Mark a flight as completed."""
    with session.begin():
        try:
            flight_storage.complete_flight(
                flight_id,
                outcome_metadata=outcome_metadata,
                session=session,
            )
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flight not found",
            ) from None

        flight = flight_storage.get_flight(flight_id, with_template=True, session=session)
        assert flight is not None
        return FlightResponse(
            flight_id=flight.flight_id,
            template_id=flight.template_id,
            template_name=flight.template_name,
            template_version=flight.template_version,
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
