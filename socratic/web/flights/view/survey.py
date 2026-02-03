"""View models for survey schemas and surveys."""

from __future__ import annotations

import datetime
import typing as t

from socratic.model import BaseModel, FlightID, SurveyID, SurveySchemaID


class SurveyDimensionView(BaseModel):
    """View model for a survey dimension."""

    name: str
    label: str
    kind: str
    required: bool = True
    help: str | None = None
    tags: list[str] = []
    weight: float = 1.0
    reverse_scored: bool = False
    spec: dict[str, t.Any] = {}


class SurveySchemaCreateRequest(BaseModel):
    """Request to create a survey schema."""

    name: str
    dimensions: list[SurveyDimensionView]
    is_default: bool = False


class SurveySchemaResponse(BaseModel):
    """Response for a survey schema."""

    schema_id: SurveySchemaID
    name: str
    dimensions: list[SurveyDimensionView]
    is_default: bool
    create_time: datetime.datetime


class SurveySchemaListResponse(BaseModel):
    """Response for listing survey schemas."""

    schemas: list[SurveySchemaResponse]


class SurveyCreateRequest(BaseModel):
    """Request to create a survey for a flight."""

    submitted_by: str
    ratings: dict[str, t.Any]
    schema_id: SurveySchemaID | None = None
    notes: str | None = None
    tags: list[str] | None = None


class SurveyResponse(BaseModel):
    """Response for a survey."""

    survey_id: SurveyID
    flight_id: FlightID
    schema_id: SurveySchemaID | None
    submitted_by: str
    ratings: dict[str, t.Any]
    notes: str | None
    tags: list[str]
    create_time: datetime.datetime


class SurveyListResponse(BaseModel):
    """Response for listing surveys."""

    surveys: list[SurveyResponse]
