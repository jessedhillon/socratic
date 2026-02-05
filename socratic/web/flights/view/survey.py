"""View models for survey schemas and surveys."""

from __future__ import annotations

import datetime
import typing as t

from socratic.model import BaseModel, DimensionSpec, FlightID, FlightSurvey, SurveyDimension, SurveyID, SurveySchema, \
    SurveySchemaID


class SurveyDimensionView(BaseModel):
    """View model for a survey dimension.

    Aligned with SurveyDimension — spec is a typed discriminated union
    with ``kind`` as the discriminator, matching the domain model structure.
    """

    name: str
    label: str
    spec: DimensionSpec
    required: bool = True
    help: str | None = None
    tags: list[str] = []
    reverse_scored: bool = False

    @classmethod
    def from_model(cls, dim: SurveyDimension) -> SurveyDimensionView:
        return cls(
            name=dim.name,
            label=dim.label,
            spec=dim.spec,
            required=dim.required,
            help=dim.help,
            tags=dim.tags,
            reverse_scored=dim.reverse_scored,
        )


class SurveySchemaCreateRequest(BaseModel):
    """Request to create a survey schema."""

    name: str
    dimensions: list[SurveyDimension]
    is_default: bool = False


class SurveySchemaView(BaseModel):
    """View for a survey schema."""

    schema_id: SurveySchemaID
    name: str
    dimensions: list[SurveyDimensionView]
    is_default: bool
    create_time: datetime.datetime

    @classmethod
    def from_model(cls, schema: SurveySchema) -> SurveySchemaView:
        return cls(
            schema_id=schema.schema_id,
            name=schema.name,
            dimensions=[SurveyDimensionView.from_model(d) for d in schema.dimensions],
            is_default=schema.is_default,
            create_time=schema.create_time,
        )


class SurveySchemaListView(BaseModel):
    """View for listing survey schemas."""

    schemas: list[SurveySchemaView]

    @classmethod
    def from_model(cls, schemas: t.Sequence[SurveySchema]) -> SurveySchemaListView:
        return cls(schemas=[SurveySchemaView.from_model(s) for s in schemas])


class SurveyCreateRequest(BaseModel):
    """Request to create a survey for a flight."""

    submitted_by: str
    ratings: dict[str, t.Any]
    schema_id: SurveySchemaID | None = None
    notes: str | None = None
    tags: list[str] | None = None


class SurveyView(BaseModel):
    """View for a survey."""

    survey_id: SurveyID
    flight_id: FlightID
    schema_id: SurveySchemaID | None
    submitted_by: str
    ratings: dict[str, t.Any]
    notes: str | None
    tags: list[str]
    create_time: datetime.datetime

    @classmethod
    def from_model(cls, survey: FlightSurvey) -> SurveyView:
        return cls(
            survey_id=survey.survey_id,
            flight_id=survey.flight_id,
            schema_id=survey.schema_id,
            submitted_by=survey.submitted_by,
            ratings=survey.ratings,
            notes=survey.notes,
            tags=survey.tags,
            create_time=survey.create_time,
        )


class SurveyListView(BaseModel):
    """View for listing surveys."""

    surveys: list[SurveyView]

    @classmethod
    def from_model(cls, surveys: t.Sequence[FlightSurvey]) -> SurveyListView:
        return cls(surveys=[SurveyView.from_model(s) for s in surveys])
