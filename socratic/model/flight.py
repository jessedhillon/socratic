"""Flight models for prompt experimentation tracking."""

from __future__ import annotations

import datetime
import enum
import typing as t

import pydantic as p

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


class ChoiceOption(BaseModel):
    """An option for choice/multi-choice dimensions."""

    value: str
    label: str


class RatingUISpec(BaseModel):
    """UI configuration for rating dimensions."""

    control: t.Literal["slider", "radio", "stars"] = "slider"
    show_value: bool = True


class BaseSpec(BaseModel):
    """Base class for dimension specs."""

    ...


class RatingSpec(BaseSpec):
    """Spec for rating dimensions (e.g., 1-5 scale)."""

    kind: t.Literal["rating"] = "rating"
    min: int = 0
    max: int = 5
    step: int = 1
    anchors: dict[str, str] = {}
    ui: RatingUISpec = RatingUISpec()


class NumberSpec(BaseSpec):
    """Spec for numeric input dimensions."""

    kind: t.Literal["number"] = "number"
    min: float | None = None
    max: float | None = None
    integer: bool = False
    unit: str | None = None


class ChoiceSpec(BaseSpec):
    """Spec for single-choice dimensions."""

    kind: t.Literal["choice"] = "choice"
    options: list[ChoiceOption]
    randomize: bool = False


class MultiChoiceSpec(BaseSpec):
    """Spec for multi-choice dimensions."""

    kind: t.Literal["multi_choice"] = "multi_choice"
    options: list[ChoiceOption]
    min_selected: int = 0
    max_selected: int | None = None


class BooleanSpec(BaseSpec):
    """Spec for boolean dimensions."""

    kind: t.Literal["boolean"] = "boolean"
    true_label: str = "Yes"
    false_label: str = "No"


class TextSpec(BaseSpec):
    """Spec for short text input dimensions."""

    kind: t.Literal["text"] = "text"
    min_length: int = 0
    max_length: int = 280
    placeholder: str | None = None


class LongTextSpec(BaseSpec):
    """Spec for long text input dimensions."""

    kind: t.Literal["long_text"] = "long_text"
    min_length: int = 0
    max_length: int = 5000
    placeholder: str | None = None


class DateSpec(BaseSpec):
    """Spec for date input dimensions."""

    kind: t.Literal["date"] = "date"
    min_date: datetime.date | None = None
    max_date: datetime.date | None = None


class DateTimeSpec(BaseSpec):
    """Spec for datetime input dimensions."""

    kind: t.Literal["datetime"] = "datetime"
    min_datetime: datetime.datetime | None = None
    max_datetime: datetime.datetime | None = None


DimensionSpec = t.Annotated[
    RatingSpec
    | NumberSpec
    | ChoiceSpec
    | MultiChoiceSpec
    | BooleanSpec
    | TextSpec
    | LongTextSpec
    | DateSpec
    | DateTimeSpec,
    p.Field(discriminator="kind"),
]


class SurveyDimension(BaseModel):
    """A single dimension in a survey schema."""

    name: str
    label: str
    spec: DimensionSpec
    required: bool = True
    help: str | None = None
    tags: list[str] = []
    weight: float = 1.0
    reverse_scored: bool = False


class PromptTemplate(BaseModel, WithTimestamps):
    """A versioned Jinja2 template for prompt rendering."""

    template_id: PromptTemplateID
    name: str
    version: int = 1
    content: str
    content_hash: str
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
