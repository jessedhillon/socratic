"""Flight routes."""

from __future__ import annotations

import datetime
import typing as t

import jinja2
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from socratic.core import di
from socratic.lib import NotSet
from socratic.model import FlightID, FlightStatus, PromptTemplateID
from socratic.storage import flight as flight_storage

from ..view import FlightCreateRequest, FlightListView, FlightUpdateRequest, FlightView

router = APIRouter(prefix="/api/flights", tags=["flights"])


@router.get("", operation_id="list_flights")
@di.inject
def list_flights(
    template_id: PromptTemplateID | None = None,
    status_filter: FlightStatus | None = None,
    created_by: str | None = None,
    limit: int | None = 50,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> FlightListView:
    """List flights with optional filters."""
    with session.begin():
        flights = flight_storage.find_flights(
            template_id=template_id,
            status=status_filter,
            created_by=created_by,
            limit=limit,
            with_template=True,
            session=session,
        )
        return FlightListView.from_model(flights)


@router.get("/{flight_id}", operation_id="get_flight")
@di.inject
def get_flight(
    flight_id: FlightID,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> FlightView:
    """Get a specific flight by ID."""
    with session.begin():
        flight = flight_storage.get_flight(flight_id, with_template=True, session=session)
        if flight is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flight not found",
            )
        return FlightView.from_model(flight)


@router.post("", operation_id="create_flight", status_code=status.HTTP_201_CREATED)
@di.inject
def create_flight(
    request: FlightCreateRequest,
    env: jinja2.Environment = Depends(di.Provide["template.llm"]),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> FlightView:
    """Create a new flight.

    Resolves the template by name (with optional content for auto-versioning),
    renders it with the provided context and feature flags, and returns the flight.
    """
    with session.begin():
        # Resolve the template
        try:
            if request.template_content is not None:
                template = flight_storage.resolve_template(
                    name=request.template,
                    content=request.template_content,
                    session=session,
                )
            else:
                template = flight_storage.resolve_template(
                    name=request.template,
                    session=session,
                )
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{request.template}' not found",
            ) from None

        # Validate template rendering before creating the flight
        render_context: dict[str, t.Any] = {"feature": request.feature_flags, **request.context}
        try:
            env.from_string(template.content).render(**render_context)
        except jinja2.TemplateError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template rendering error: {e!s}",
            ) from e

        # Create the flight
        created = flight_storage.create_flight(
            template_id=template.template_id,
            created_by=request.created_by,
            model_provider=request.model_provider,
            model_name=request.model_name,
            started_at=datetime.datetime.now(datetime.UTC),
            feature_flags=request.feature_flags,
            context=request.context,
            model_config=request.model_config_data,
            labels=request.labels,
            session=session,
        )

        # Refetch with template join so FlightView.from_model can render
        flight = flight_storage.get_flight(created.flight_id, with_template=True, session=session)
        assert flight is not None
        return FlightView.from_model(flight)


@router.patch("/{flight_id}", operation_id="update_flight")
@di.inject
def update_flight(
    flight_id: FlightID,
    request: FlightUpdateRequest,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> FlightView:
    """Update a flight's status or outcome metadata."""
    with session.begin():
        status_val: FlightStatus | NotSet = NotSet()
        completed_at: datetime.datetime | None | NotSet = NotSet()
        outcome_metadata: dict[str, t.Any] | None | NotSet = NotSet()

        if request.status is not None:
            status_val = request.status
            completed_at = (
                datetime.datetime.now(datetime.UTC)
                if request.status in (FlightStatus.Completed, FlightStatus.Abandoned)
                else None
            )

        if request.outcome_metadata is not None:
            outcome_metadata = request.outcome_metadata

        try:
            flight_storage.update_flight(
                flight_id,
                status=status_val,
                completed_at=completed_at,
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
        return FlightView.from_model(flight)


@router.post("/{flight_id}/complete", operation_id="complete_flight")
@di.inject
def complete_flight(
    flight_id: FlightID,
    outcome_metadata: dict[str, t.Any] | None = None,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> FlightView:
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
        return FlightView.from_model(flight)
