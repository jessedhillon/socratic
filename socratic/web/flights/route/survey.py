"""Survey schema and survey routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from socratic.core import di
from socratic.model import FlightID, SurveyID, SurveySchemaID
from socratic.storage import flight as flight_storage

from ..view import SurveyCreateRequest, SurveyListResponse, SurveyResponse, SurveySchemaCreateRequest, \
    SurveySchemaListResponse, SurveySchemaResponse
from ..view.survey import SurveyDimensionView

router = APIRouter(tags=["surveys"])


# =============================================================================
# Survey Schemas
# =============================================================================


@router.get("/api/survey-schemas", operation_id="list_survey_schemas")
@di.inject
def list_survey_schemas(
    is_default: bool | None = None,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> SurveySchemaListResponse:
    """List available survey schemas."""
    with session.begin():
        schemas = flight_storage.find_survey_schemas(
            is_default=is_default,
            session=session,
        )
        return SurveySchemaListResponse(
            schemas=[
                SurveySchemaResponse(
                    schema_id=s.schema_id,
                    name=s.name,
                    dimensions=[SurveyDimensionView(**d.model_dump()) for d in s.dimensions],
                    is_default=s.is_default,
                    create_time=s.create_time,
                )
                for s in schemas
            ]
        )


@router.get("/api/survey-schemas/{schema_id}", operation_id="get_survey_schema")
@di.inject
def get_survey_schema(
    schema_id: SurveySchemaID,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> SurveySchemaResponse:
    """Get a specific survey schema by ID."""
    with session.begin():
        schema = flight_storage.get_survey_schema(schema_id, session=session)
        if schema is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Survey schema not found",
            )
        return SurveySchemaResponse(
            schema_id=schema.schema_id,
            name=schema.name,
            dimensions=[SurveyDimensionView(**d.model_dump()) for d in schema.dimensions],
            is_default=schema.is_default,
            create_time=schema.create_time,
        )


@router.post("/api/survey-schemas", operation_id="create_survey_schema", status_code=status.HTTP_201_CREATED)
@di.inject
def create_survey_schema(
    request: SurveySchemaCreateRequest,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> SurveySchemaResponse:
    """Create a new survey schema."""
    with session.begin():
        # Check if name already exists
        existing = flight_storage.get_survey_schema(name=request.name, session=session)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Survey schema '{request.name}' already exists",
            )

        schema = flight_storage.create_survey_schema(
            name=request.name,
            dimensions=[d.model_dump() for d in request.dimensions],
            is_default=request.is_default,
            session=session,
        )
        return SurveySchemaResponse(
            schema_id=schema.schema_id,
            name=schema.name,
            dimensions=[SurveyDimensionView(**d.model_dump()) for d in schema.dimensions],
            is_default=schema.is_default,
            create_time=schema.create_time,
        )


# =============================================================================
# Surveys (Flight Feedback)
# =============================================================================


@router.get("/api/flights/{flight_id}/surveys", operation_id="list_flight_surveys")
@di.inject
def list_flight_surveys(
    flight_id: FlightID,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> SurveyListResponse:
    """List surveys for a specific flight."""
    with session.begin():
        # Verify flight exists
        flight = flight_storage.get_flight(flight_id, session=session)
        if flight is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flight not found",
            )

        surveys = flight_storage.find_surveys(flight_id=flight_id, session=session)
        return SurveyListResponse(
            surveys=[
                SurveyResponse(
                    survey_id=s.survey_id,
                    flight_id=s.flight_id,
                    schema_id=s.schema_id,
                    submitted_by=s.submitted_by,
                    ratings=s.ratings,
                    notes=s.notes,
                    tags=s.tags,
                    create_time=s.create_time,
                )
                for s in surveys
            ]
        )


@router.post("/api/flights/{flight_id}/surveys", operation_id="create_survey", status_code=status.HTTP_201_CREATED)
@di.inject
def create_survey(
    flight_id: FlightID,
    request: SurveyCreateRequest,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> SurveyResponse:
    """Submit a survey for a flight."""
    with session.begin():
        # Verify flight exists
        flight = flight_storage.get_flight(flight_id, session=session)
        if flight is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Flight not found",
            )

        # Verify schema exists if provided
        if request.schema_id is not None:
            schema = flight_storage.get_survey_schema(request.schema_id, session=session)
            if schema is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Survey schema not found",
                )

        survey = flight_storage.create_survey(
            flight_id=flight_id,
            submitted_by=request.submitted_by,
            ratings=request.ratings,
            schema_id=request.schema_id,
            notes=request.notes,
            tags=request.tags,
            session=session,
        )
        return SurveyResponse(
            survey_id=survey.survey_id,
            flight_id=survey.flight_id,
            schema_id=survey.schema_id,
            submitted_by=survey.submitted_by,
            ratings=survey.ratings,
            notes=survey.notes,
            tags=survey.tags,
            create_time=survey.create_time,
        )


@router.get("/api/surveys/{survey_id}", operation_id="get_survey")
@di.inject
def get_survey(
    survey_id: SurveyID,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> SurveyResponse:
    """Get a specific survey by ID."""
    with session.begin():
        survey = flight_storage.get_survey(survey_id, session=session)
        if survey is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Survey not found",
            )
        return SurveyResponse(
            survey_id=survey.survey_id,
            flight_id=survey.flight_id,
            schema_id=survey.schema_id,
            submitted_by=survey.submitted_by,
            ratings=survey.ratings,
            notes=survey.notes,
            tags=survey.tags,
            create_time=survey.create_time,
        )
