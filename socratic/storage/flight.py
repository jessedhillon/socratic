"""Storage functions for flights (prompt experimentation tracking)."""

from __future__ import annotations

import datetime
import hashlib
import json
import typing as t

import jinja2
import sqlalchemy as sqla

from socratic.core import di
from socratic.lib import NotSet
from socratic.model import Flight, FlightID, FlightStatus, FlightSurvey, FlightWithTemplate, PromptTemplate, \
    PromptTemplateID, SurveyDimension, SurveyID, SurveySchema, SurveySchemaID

from . import AsyncSession, Session
from .table import flight_surveys, flights, prompt_templates, survey_schemas

_jinja_env = jinja2.Environment(autoescape=False)


def _hash_content(content: str) -> str:
    """Compute SHA-256 hash of template content using the Jinja2 AST.

    Parsing to AST normalizes syntax-only differences (e.g., ``{{ name }}`` vs
    ``{{name}}``) while preserving semantically meaningful differences.  Falls
    back to hashing the stripped raw content if the template fails to parse.
    """
    try:
        ast = _jinja_env.parse(content.strip())
        canonical = repr(ast.body)
    except jinja2.TemplateSyntaxError:
        canonical = content.strip()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _hash_dimensions(dimensions: list[SurveyDimension]) -> str:
    """Compute canonical hash of survey dimensions.

    Uses sorted JSON serialization to ensure consistent hashing
    regardless of dict key ordering.
    """
    canonical = json.dumps(
        [d.model_dump() for d in dimensions],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =============================================================================
# Prompt Templates
# =============================================================================


@t.overload
def get_template(
    template_id: PromptTemplateID,
    *,
    session: Session = ...,
) -> PromptTemplate | None: ...


@t.overload
def get_template(
    template_id: None = ...,
    *,
    name: str,
    version: int | None = ...,
    session: Session = ...,
) -> PromptTemplate | None: ...


def get_template(
    template_id: PromptTemplateID | None = None,
    *,
    name: str | None = None,
    version: int | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> PromptTemplate | None:
    """Get a prompt template by ID or name.

    If name is provided without version, returns the latest active version.
    """
    if template_id is None and name is None:
        raise ValueError("Either template_id or name must be provided")
    if template_id is not None and name is not None:
        raise ValueError("Only one of template_id or name should be provided")

    if template_id is not None:
        stmt = sqla.select(prompt_templates.__table__).where(prompt_templates.template_id == template_id)
    elif version is not None:
        stmt = sqla.select(prompt_templates.__table__).where(
            sqla.and_(
                prompt_templates.name == name,
                prompt_templates.version == version,
            )
        )
    else:
        # Get latest active version for name
        stmt = (
            sqla
            .select(prompt_templates.__table__)
            .where(
                sqla.and_(
                    prompt_templates.name == name,
                    prompt_templates.is_active == True,  # noqa: E712
                )
            )
            .order_by(prompt_templates.version.desc())
            .limit(1)
        )

    row = session.execute(stmt).mappings().one_or_none()
    return PromptTemplate(**row) if row else None


async def aget_template(
    template_id: PromptTemplateID | None = None,
    *,
    name: str | None = None,
    version: int | None = None,
    session: AsyncSession,
) -> PromptTemplate | None:
    """Get a prompt template by ID or name (async).

    If name is provided without version, returns the latest active version.
    """
    if template_id is None and name is None:
        raise ValueError("Either template_id or name must be provided")
    if template_id is not None and name is not None:
        raise ValueError("Only one of template_id or name should be provided")

    if template_id is not None:
        stmt = sqla.select(prompt_templates.__table__).where(prompt_templates.template_id == template_id)
    elif version is not None:
        stmt = sqla.select(prompt_templates.__table__).where(
            sqla.and_(
                prompt_templates.name == name,
                prompt_templates.version == version,
            )
        )
    else:
        # Get latest active version for name
        stmt = (
            sqla
            .select(prompt_templates.__table__)
            .where(
                sqla.and_(
                    prompt_templates.name == name,
                    prompt_templates.is_active == True,  # noqa: E712
                )
            )
            .order_by(prompt_templates.version.desc())
            .limit(1)
        )

    row = (await session.execute(stmt)).mappings().one_or_none()
    return PromptTemplate(**row) if row else None


def find_templates(
    *,
    name: str | None = None,
    is_active: bool | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[PromptTemplate, ...]:
    """Find templates, optionally filtered by name or active status."""
    stmt = sqla.select(prompt_templates.__table__)

    if name is not None:
        stmt = stmt.where(prompt_templates.name == name)
    if is_active is not None:
        stmt = stmt.where(prompt_templates.is_active == is_active)

    stmt = stmt.order_by(prompt_templates.name, prompt_templates.version.desc())
    rows = session.execute(stmt).mappings().all()
    return tuple(PromptTemplate(**row) for row in rows)


def create_template(
    *,
    name: str,
    content: str,
    description: str | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> PromptTemplate:
    """Create a new template.

    If a template with this name exists, creates a new version.
    """
    # Determine next version from the highest existing version (active or not)
    max_version_stmt = sqla.select(sqla.func.max(prompt_templates.version)).where(prompt_templates.name == name)
    max_version = session.execute(max_version_stmt).scalar()
    version = (max_version + 1) if max_version is not None else 1

    template_id = PromptTemplateID()
    content_hash = _hash_content(content)
    stmt = sqla.insert(prompt_templates).values(
        template_id=template_id,
        name=name,
        version=version,
        content=content,
        content_hash=content_hash,
        description=description,
    )
    session.execute(stmt)
    session.flush()

    template = get_template(template_id, session=session)
    assert template is not None
    return template


@t.overload
def resolve_template(
    *,
    name: str,
    session: Session = ...,
) -> PromptTemplate: ...


@t.overload
def resolve_template(
    *,
    name: str,
    content: str,
    description: str | None = ...,
    session: Session = ...,
) -> PromptTemplate: ...


def resolve_template(
    *,
    name: str,
    content: str | None = None,
    description: str | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> PromptTemplate:
    """Resolve a template by name, optionally with content for auto-versioning.

    Mode 1 (name only): Returns the latest active version.
    Mode 2 (name + content): Hashes content, finds matching version by (name, hash),
        or creates a new version if the content has changed.

    Raises:
        KeyError: If name-only mode and no active template exists with that name.
    """
    if content is None:
        template = get_template(name=name, session=session)
        if template is None:
            raise KeyError(f"Template '{name}' not found")
        return template

    content_hash = _hash_content(content)

    # Look for an existing version with this exact content
    stmt = (
        sqla
        .select(prompt_templates.__table__)
        .where(
            sqla.and_(
                prompt_templates.name == name,
                prompt_templates.content_hash == content_hash,
            )
        )
        .order_by(prompt_templates.version.desc())
        .limit(1)
    )
    row = session.execute(stmt).mappings().one_or_none()
    if row is not None:
        return PromptTemplate(**row)

    # Content doesn't match any version — create new version
    return create_template(name=name, content=content, description=description, session=session)


def update_template(
    template_id: PromptTemplateID,
    *,
    description: str | None | NotSet = NotSet(),
    is_active: bool | NotSet = NotSet(),
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    """Update a template's metadata.

    Note: Content changes require creating a new version.

    Raises:
        KeyError: If template_id not found
    """
    values: dict[str, t.Any] = {}
    if not isinstance(description, NotSet):
        values["description"] = description
    if not isinstance(is_active, NotSet):
        values["is_active"] = is_active

    if values:
        stmt = sqla.update(prompt_templates).where(prompt_templates.template_id == template_id).values(**values)
    else:
        stmt = (
            sqla
            .update(prompt_templates)
            .where(prompt_templates.template_id == template_id)
            .values(template_id=template_id)
        )

    result = session.execute(stmt)
    if result.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue]
        raise KeyError(f"Template {template_id} not found")

    session.flush()


# =============================================================================
# Survey Schemas
# =============================================================================


def get_survey_schema(
    schema_id: SurveySchemaID | None = None,
    *,
    name: str | None = None,
    version: int | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> SurveySchema | None:
    """Get a survey schema by ID or name.

    If name is provided without version, returns the latest version.
    """
    if schema_id is None and name is None:
        raise ValueError("Either schema_id or name must be provided")
    if schema_id is not None and name is not None:
        raise ValueError("Only one of schema_id or name should be provided")

    if schema_id is not None:
        stmt = sqla.select(survey_schemas.__table__).where(survey_schemas.schema_id == schema_id)
    elif version is not None:
        stmt = sqla.select(survey_schemas.__table__).where(
            sqla.and_(
                survey_schemas.name == name,
                survey_schemas.version == version,
            )
        )
    else:
        # Get latest version for name
        stmt = (
            sqla
            .select(survey_schemas.__table__)
            .where(survey_schemas.name == name)
            .order_by(survey_schemas.version.desc())
            .limit(1)
        )

    row = session.execute(stmt).mappings().one_or_none()
    return SurveySchema(**row) if row else None


def find_survey_schemas(
    *,
    is_default: bool | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[SurveySchema, ...]:
    """Find survey schemas, optionally filtered."""
    stmt = sqla.select(survey_schemas.__table__)

    if is_default is not None:
        stmt = stmt.where(survey_schemas.is_default == is_default)

    stmt = stmt.order_by(survey_schemas.name)
    rows = session.execute(stmt).mappings().all()
    return tuple(SurveySchema(**row) for row in rows)


def create_survey_schema(
    *,
    name: str,
    dimensions: list[SurveyDimension],
    is_default: bool = False,
    session: Session = di.Provide["storage.persistent.session"],
) -> SurveySchema:
    """Create a new survey schema, or return existing if dimensions match.

    If a schema with the same name exists:
    - If dimensions hash matches, return the existing schema (idempotent)
    - If dimensions differ, create a new version
    """
    dimensions_hash = _hash_dimensions(dimensions)

    # Check for existing schema with same name
    existing_stmt = (
        sqla
        .select(survey_schemas.__table__)
        .where(survey_schemas.name == name)
        .order_by(survey_schemas.version.desc())
        .limit(1)
    )
    existing_row = session.execute(existing_stmt).mappings().one_or_none()

    if existing_row is not None:
        # If hash matches, return existing (idempotent)
        if existing_row["dimensions_hash"] == dimensions_hash:
            return SurveySchema(**existing_row)
        # Otherwise, create new version
        next_version = existing_row["version"] + 1
    else:
        next_version = 1

    schema_id = SurveySchemaID()
    stmt = sqla.insert(survey_schemas).values(
        schema_id=schema_id,
        name=name,
        version=next_version,
        dimensions=[d.model_dump() for d in dimensions],
        dimensions_hash=dimensions_hash,
        is_default=is_default,
    )
    session.execute(stmt)
    session.flush()

    schema = get_survey_schema(schema_id, session=session)
    assert schema is not None
    return schema


# =============================================================================
# Flights
# =============================================================================


@t.overload
def get_flight(
    flight_id: FlightID,
    *,
    with_template: t.Literal[False] = ...,
    session: Session = ...,
) -> Flight | None: ...


@t.overload
def get_flight(
    flight_id: FlightID,
    *,
    with_template: t.Literal[True],
    session: Session = ...,
) -> FlightWithTemplate | None: ...


def get_flight(
    flight_id: FlightID,
    *,
    with_template: bool = False,
    session: Session = di.Provide["storage.persistent.session"],
) -> Flight | FlightWithTemplate | None:
    """Get a flight by ID, optionally with template info."""
    if with_template:
        stmt = (
            sqla
            .select(
                flights.__table__,
                prompt_templates.name.label("template_name"),
                prompt_templates.version.label("template_version"),
                prompt_templates.content.label("template_content"),
            )
            .select_from(flights)
            .join(prompt_templates, flights.template_id == prompt_templates.template_id)
            .where(flights.flight_id == flight_id)
        )
        row = session.execute(stmt).mappings().one_or_none()
        return FlightWithTemplate(**row) if row else None
    else:
        stmt = sqla.select(flights.__table__).where(flights.flight_id == flight_id)
        row = session.execute(stmt).mappings().one_or_none()
        return Flight(**row) if row else None


def find_flights(
    *,
    template_id: PromptTemplateID | None = None,
    labels: dict[str, t.Any] | None = None,
    status: FlightStatus | None = None,
    created_by: str | None = None,
    limit: int | None = None,
    with_template: bool = False,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[Flight, ...] | tuple[FlightWithTemplate, ...]:
    """Find flights matching criteria."""
    if with_template:
        stmt = (
            sqla
            .select(
                flights.__table__,
                prompt_templates.name.label("template_name"),
                prompt_templates.version.label("template_version"),
                prompt_templates.content.label("template_content"),
            )
            .select_from(flights)
            .join(prompt_templates, flights.template_id == prompt_templates.template_id)
        )
    else:
        stmt = sqla.select(flights.__table__)

    if template_id is not None:
        stmt = stmt.where(flights.template_id == template_id)
    if labels is not None:
        stmt = stmt.where(flights.labels.contains(labels))
    if status is not None:
        stmt = stmt.where(flights.status == status.value)
    if created_by is not None:
        stmt = stmt.where(flights.created_by == created_by)

    stmt = stmt.order_by(flights.started_at.desc())

    if limit is not None:
        stmt = stmt.limit(limit)

    rows = session.execute(stmt).mappings().all()

    if with_template:
        return tuple(FlightWithTemplate(**row) for row in rows)
    return tuple(Flight(**row) for row in rows)


def create_flight(
    *,
    template_id: PromptTemplateID,
    created_by: str,
    model_provider: str,
    model_name: str,
    started_at: datetime.datetime,
    feature_flags: dict[str, t.Any] | None = None,
    context: dict[str, t.Any] | None = None,
    model_config: dict[str, t.Any] | None = None,
    labels: dict[str, t.Any] | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> Flight:
    """Create a new flight."""
    flight_id = FlightID()
    stmt = sqla.insert(flights).values(
        flight_id=flight_id,
        template_id=template_id,
        created_by=created_by,
        model_provider=model_provider,
        model_name=model_name,
        started_at=started_at,
        feature_flags=feature_flags or {},
        context=context or {},
        model_config_data=model_config or {},
        labels=labels or {},
    )
    session.execute(stmt)
    session.flush()

    flight = get_flight(flight_id, session=session)
    assert flight is not None
    return flight


async def acreate_flight(
    *,
    template_id: PromptTemplateID,
    created_by: str,
    model_provider: str,
    model_name: str,
    started_at: datetime.datetime,
    feature_flags: dict[str, t.Any] | None = None,
    context: dict[str, t.Any] | None = None,
    model_config: dict[str, t.Any] | None = None,
    labels: dict[str, t.Any] | None = None,
    session: AsyncSession,
) -> Flight:
    """Create a new flight (async)."""
    flight_id = FlightID()
    stmt = sqla.insert(flights).values(
        flight_id=flight_id,
        template_id=template_id,
        created_by=created_by,
        model_provider=model_provider,
        model_name=model_name,
        started_at=started_at,
        feature_flags=feature_flags or {},
        context=context or {},
        model_config_data=model_config or {},
        labels=labels or {},
    )
    await session.execute(stmt)
    await session.flush()

    select_stmt = sqla.select(flights.__table__).where(flights.flight_id == flight_id)
    row = (await session.execute(select_stmt)).mappings().one()
    return Flight(**row)


def update_flight(
    flight_id: FlightID,
    *,
    status: FlightStatus | NotSet = NotSet(),
    completed_at: datetime.datetime | None | NotSet = NotSet(),
    outcome_metadata: dict[str, t.Any] | None | NotSet = NotSet(),
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    """Update a flight.

    Raises:
        KeyError: If flight_id not found
    """
    values: dict[str, t.Any] = {}
    if not isinstance(status, NotSet):
        values["status"] = status.value
    if not isinstance(completed_at, NotSet):
        values["completed_at"] = completed_at
    if not isinstance(outcome_metadata, NotSet):
        values["outcome_metadata"] = outcome_metadata

    if values:
        stmt = sqla.update(flights).where(flights.flight_id == flight_id).values(**values)
    else:
        stmt = sqla.update(flights).where(flights.flight_id == flight_id).values(flight_id=flight_id)

    result = session.execute(stmt)
    if result.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue]
        raise KeyError(f"Flight {flight_id} not found")

    session.flush()


def complete_flight(
    flight_id: FlightID,
    *,
    status: FlightStatus = FlightStatus.Completed,
    outcome_metadata: dict[str, t.Any] | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> None:
    """Mark a flight as completed or abandoned."""
    update_flight(
        flight_id,
        status=status,
        completed_at=datetime.datetime.now(datetime.UTC),
        outcome_metadata=outcome_metadata,
        session=session,
    )


async def acomplete_flight(
    flight_id: FlightID,
    *,
    status: FlightStatus = FlightStatus.Completed,
    outcome_metadata: dict[str, t.Any] | None = None,
    session: AsyncSession,
) -> None:
    """Mark a flight as completed or abandoned (async)."""
    values: dict[str, t.Any] = {
        "status": status.value,
        "completed_at": datetime.datetime.now(datetime.UTC),
    }
    if outcome_metadata is not None:
        values["outcome_metadata"] = outcome_metadata

    stmt = sqla.update(flights).where(flights.flight_id == flight_id).values(**values)
    result = await session.execute(stmt)
    if result.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue]
        raise KeyError(f"Flight {flight_id} not found")
    await session.flush()


# =============================================================================
# Flight Surveys
# =============================================================================


def get_survey(
    survey_id: SurveyID,
    *,
    session: Session = di.Provide["storage.persistent.session"],
) -> FlightSurvey | None:
    """Get a survey by ID."""
    stmt = sqla.select(flight_surveys.__table__).where(flight_surveys.survey_id == survey_id)
    row = session.execute(stmt).mappings().one_or_none()
    return FlightSurvey(**row) if row else None


def find_surveys(
    *,
    flight_id: FlightID | None = None,
    schema_id: SurveySchemaID | None = None,
    submitted_by: str | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[FlightSurvey, ...]:
    """Find surveys matching criteria."""
    stmt = sqla.select(flight_surveys.__table__)

    if flight_id is not None:
        stmt = stmt.where(flight_surveys.flight_id == flight_id)
    if schema_id is not None:
        stmt = stmt.where(flight_surveys.schema_id == schema_id)
    if submitted_by is not None:
        stmt = stmt.where(flight_surveys.submitted_by == submitted_by)

    stmt = stmt.order_by(flight_surveys.create_time.desc())
    rows = session.execute(stmt).mappings().all()
    return tuple(FlightSurvey(**row) for row in rows)


def create_survey(
    *,
    flight_id: FlightID,
    submitted_by: str,
    ratings: dict[str, t.Any],
    schema_id: SurveySchemaID | None = None,
    notes: str | None = None,
    tags: list[str] | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> FlightSurvey:
    """Create a survey for a flight."""
    survey_id = SurveyID()
    stmt = sqla.insert(flight_surveys).values(
        survey_id=survey_id,
        flight_id=flight_id,
        submitted_by=submitted_by,
        ratings=ratings,
        schema_id=schema_id,
        notes=notes,
        tags=tags or [],
    )
    session.execute(stmt)
    session.flush()

    survey = get_survey(survey_id, session=session)
    assert survey is not None
    return survey
