"""Flight models for prompt experimentation tracking."""

from __future__ import annotations

import datetime
import enum
import typing as t

from .base import BaseModel, WithCtime, WithTimestamps
from .id import AttemptID, FlightID, PromptTemplateID, SurveyID, SurveySchemaID


class FlightStatus(enum.Enum):
    """Status of a flight."""

    Active = "active"
    Completed = "completed"
    Abandoned = "abandoned"


class SurveyDimensionKind(enum.Enum):
    """Kind of survey dimension."""

    Rating = "rating"
    Number = "number"
    Choice = "choice"
    MultiChoice = "multi_choice"
    Boolean = "boolean"
    Text = "text"
    LongText = "long_text"
    Date = "date"
    DateTime = "datetime"


class SurveyDimension(BaseModel):
    """A single dimension in a survey schema."""

    name: str
    label: str
    kind: SurveyDimensionKind
    required: bool = True
    help: str | None = None
    tags: list[str] = []
    weight: float = 1.0
    reverse_scored: bool = False
    spec: dict[str, t.Any] = {}


class PromptTemplate(BaseModel, WithTimestamps):
    """A versioned Jinja2 template for prompt rendering."""

    template_id: PromptTemplateID
    name: str
    version: int = 1
    content: str
    description: str | None = None
    is_active: bool = True


class SurveySchema(BaseModel, WithCtime):
    """A schema defining survey dimensions."""

    schema_id: SurveySchemaID
    name: str
    dimensions: list[SurveyDimension]
    is_default: bool = False


class ModelMetadata(BaseModel):
    """Metadata about the LLM used for a flight."""

    provider: str
    name: str
    config: dict[str, t.Any] = {}


class Flight(BaseModel, WithTimestamps):
    """A rendered template instance with tracking metadata."""

    flight_id: FlightID
    template_id: PromptTemplateID
    created_by: str

    feature_flags: dict[str, t.Any]
    context: dict[str, t.Any]
    rendered_content: str

    model_provider: str
    model_name: str
    model_config_data: dict[str, t.Any] = {}

    status: FlightStatus = FlightStatus.Active
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None

    attempt_id: AttemptID | None = None
    outcome_metadata: dict[str, t.Any] | None = None


class FlightWithTemplate(Flight):
    """Flight with embedded template info for joined queries."""

    template_name: str
    template_version: int


class FlightSurvey(BaseModel, WithCtime):
    """A submitted survey for a flight."""

    survey_id: SurveyID
    flight_id: FlightID
    schema_id: SurveySchemaID | None = None
    submitted_by: str

    ratings: dict[str, t.Any]
    notes: str | None = None
    tags: list[str] = []
