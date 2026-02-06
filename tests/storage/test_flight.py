"""Tests for socratic.storage.flight module."""

from __future__ import annotations

import datetime
import typing as t

import pytest
from sqlalchemy.orm import Session

from socratic.model import Flight, FlightID, FlightStatus, FlightWithTemplate, PromptTemplate, PromptTemplateID, \
    RatingSpec, SurveyDimension, SurveyID, SurveySchema, SurveySchemaID
from socratic.storage import flight as flight_storage

# =============================================================================
# Template Fixtures
# =============================================================================


@pytest.fixture
def template_factory(db_session: Session) -> t.Callable[..., PromptTemplate]:
    """Factory fixture for creating test prompt templates."""

    def create_template(
        name: str = "test_template",
        content: str = "Hello {{ name }}!",
        description: str | None = None,
    ) -> PromptTemplate:
        with db_session.begin():
            return flight_storage.create_template(
                name=name,
                content=content,
                description=description,
                session=db_session,
            )

    return create_template


@pytest.fixture
def test_template(template_factory: t.Callable[..., PromptTemplate]) -> PromptTemplate:
    """Provide a pre-created test template."""
    return template_factory(
        name="assessment_system",
        content="You are an assessment agent for {{ objective_title }}.",
        description="Main assessment system prompt",
    )


# =============================================================================
# Survey Schema Fixtures
# =============================================================================


@pytest.fixture
def survey_schema_factory(db_session: Session) -> t.Callable[..., SurveySchema]:
    """Factory fixture for creating test survey schemas."""

    def create_schema(
        name: str = "test_schema",
        dimensions: list[SurveyDimension] | None = None,
        is_default: bool = False,
    ) -> SurveySchema:
        if dimensions is None:
            dimensions = [
                SurveyDimension(
                    name="quality",
                    label="How would you rate the quality?",
                    required=True,
                    spec=RatingSpec(min=1, max=5),
                )
            ]
        with db_session.begin():
            return flight_storage.create_survey_schema(
                name=name,
                dimensions=dimensions,
                is_default=is_default,
                session=db_session,
            )

    return create_schema


@pytest.fixture
def test_schema(survey_schema_factory: t.Callable[..., SurveySchema]) -> SurveySchema:
    """Provide a pre-created test survey schema."""
    return survey_schema_factory(
        name="assessment_feedback",
        dimensions=[
            SurveyDimension(
                name="probing_depth",
                label="Did the tutor ask meaningful follow-up questions?",
                required=True,
                spec=RatingSpec(min=0, max=5),
            ),
            SurveyDimension(
                name="clarity",
                label="Was the communication clear?",
                required=True,
                spec=RatingSpec(min=0, max=5),
            ),
        ],
        is_default=True,
    )


# =============================================================================
# Flight Fixtures
# =============================================================================


@pytest.fixture
def flight_factory(
    db_session: Session,
    test_template: PromptTemplate,
) -> t.Callable[..., Flight]:
    """Factory fixture for creating test flights."""

    def create_flight(
        template_id: PromptTemplateID | None = None,
        created_by: str = "test_user",
        model_provider: str = "openai",
        model_name: str = "gpt-4o",
        feature_flags: dict[str, t.Any] | None = None,
        context: dict[str, t.Any] | None = None,
        model_config: dict[str, t.Any] | None = None,
        labels: dict[str, t.Any] | None = None,
    ) -> Flight:
        with db_session.begin():
            return flight_storage.create_flight(
                template_id=template_id or test_template.template_id,
                created_by=created_by,
                model_provider=model_provider,
                model_name=model_name,
                started_at=datetime.datetime.now(datetime.UTC),
                feature_flags=feature_flags,
                context=context,
                model_config=model_config,
                labels=labels,
                session=db_session,
            )

    return create_flight


@pytest.fixture
def test_flight(flight_factory: t.Callable[..., Flight]) -> Flight:
    """Provide a pre-created test flight."""
    return flight_factory(
        created_by="test_assessor",
        feature_flags={"conviviality": "conversational"},
        context={"objective_title": "Python Basics"},
    )


# =============================================================================
# Template Tests
# =============================================================================


class TestGetTemplate(object):
    """Tests for flight_storage.get_template()."""

    def test_get_by_template_id(
        self,
        db_session: Session,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        """get_template() with template_id returns the template."""
        template = template_factory(name="test_get", content="Test content")

        with db_session.begin():
            result = flight_storage.get_template(template.template_id, session=db_session)

        assert result is not None
        assert result.template_id == template.template_id
        assert result.name == "test_get"
        assert result.content == "Test content"

    def test_get_by_name_returns_latest_active(
        self,
        db_session: Session,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        """get_template() with name returns the latest active version."""
        template_factory(name="versioned", content="Version 1")
        template2 = template_factory(name="versioned", content="Version 2")

        with db_session.begin():
            result = flight_storage.get_template(name="versioned", session=db_session)

        assert result is not None
        assert result.version == 2
        assert result.content == "Version 2"
        assert result.template_id == template2.template_id

    def test_get_by_name_and_version(
        self,
        db_session: Session,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        """get_template() with name and version returns specific version."""
        template1 = template_factory(name="specific", content="Version 1")
        template_factory(name="specific", content="Version 2")

        with db_session.begin():
            result = flight_storage.get_template(name="specific", version=1, session=db_session)

        assert result is not None
        assert result.version == 1
        assert result.content == "Version 1"
        assert result.template_id == template1.template_id

    def test_get_nonexistent_by_id_returns_none(self, db_session: Session) -> None:
        """get_template() returns None for nonexistent template ID."""
        with db_session.begin():
            result = flight_storage.get_template(PromptTemplateID(), session=db_session)

        assert result is None

    def test_get_nonexistent_by_name_returns_none(self, db_session: Session) -> None:
        """get_template() returns None for nonexistent name."""
        with db_session.begin():
            result = flight_storage.get_template(name="nonexistent", session=db_session)

        assert result is None

    def test_get_requires_id_or_name(self, db_session: Session) -> None:
        """get_template() raises ValueError if neither id nor name provided."""
        with pytest.raises(ValueError, match="Either template_id or name must be provided"):
            flight_storage.get_template(session=db_session)  # type: ignore[call-overload]

    def test_get_rejects_both_id_and_name(
        self,
        db_session: Session,
        test_template: PromptTemplate,
    ) -> None:
        """get_template() raises ValueError if both id and name provided."""
        with pytest.raises(ValueError, match="Only one of template_id or name"):
            flight_storage.get_template(
                test_template.template_id,  # pyright: ignore[reportArgumentType]
                name="test",
                session=db_session,
            )


class TestFindTemplates(object):
    """Tests for flight_storage.find_templates()."""

    def test_find_all(
        self,
        db_session: Session,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        """find_templates() returns all templates."""
        t1 = template_factory(name="template_a", content="A")
        t2 = template_factory(name="template_b", content="B")

        with db_session.begin():
            result = flight_storage.find_templates(session=db_session)

        template_ids = {t.template_id for t in result}
        assert t1.template_id in template_ids
        assert t2.template_id in template_ids

    def test_find_by_name(
        self,
        db_session: Session,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        """find_templates() filters by name."""
        template_factory(name="find_target", content="Target")
        template_factory(name="find_other", content="Other")

        with db_session.begin():
            result = flight_storage.find_templates(name="find_target", session=db_session)

        assert len(result) == 1
        assert result[0].name == "find_target"

    def test_find_by_active_status(
        self,
        db_session: Session,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        """find_templates() filters by active status."""
        t1 = template_factory(name="active_test", content="Active")
        # Deactivate the template
        with db_session.begin():
            flight_storage.update_template(t1.template_id, is_active=False, session=db_session)

        with db_session.begin():
            active = flight_storage.find_templates(is_active=True, session=db_session)
            inactive = flight_storage.find_templates(is_active=False, session=db_session)

        active_ids = {t.template_id for t in active}
        inactive_ids = {t.template_id for t in inactive}
        assert t1.template_id not in active_ids
        assert t1.template_id in inactive_ids


class TestCreateTemplate(object):
    """Tests for flight_storage.create_template()."""

    def test_create_first_version(self, db_session: Session) -> None:
        """create_template() creates version 1 for new template name."""
        with db_session.begin():
            template = flight_storage.create_template(
                name="new_template",
                content="New content",
                description="A new template",
                session=db_session,
            )

        assert template.name == "new_template"
        assert template.version == 1
        assert template.content == "New content"
        assert template.description == "A new template"
        assert template.is_active is True
        assert template.template_id is not None

    def test_create_increments_version(
        self,
        db_session: Session,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        """create_template() increments version for existing name."""
        template_factory(name="versioned_create", content="V1")

        with db_session.begin():
            v2 = flight_storage.create_template(
                name="versioned_create",
                content="V2",
                session=db_session,
            )

        assert v2.version == 2
        assert v2.content == "V2"


class TestUpdateTemplate(object):
    """Tests for flight_storage.update_template()."""

    def test_update_description(
        self,
        db_session: Session,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        """update_template() can change description."""
        template = template_factory(name="update_desc", content="Content")

        with db_session.begin():
            flight_storage.update_template(
                template.template_id,
                description="Updated description",
                session=db_session,
            )
            updated = flight_storage.get_template(template.template_id, session=db_session)

        assert updated is not None
        assert updated.description == "Updated description"

    def test_update_is_active(
        self,
        db_session: Session,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        """update_template() can change is_active."""
        template = template_factory(name="deactivate_test", content="Content")

        with db_session.begin():
            flight_storage.update_template(
                template.template_id,
                is_active=False,
                session=db_session,
            )
            updated = flight_storage.get_template(template.template_id, session=db_session)

        assert updated is not None
        assert updated.is_active is False

    def test_update_nonexistent_raises_keyerror(self, db_session: Session) -> None:
        """update_template() raises KeyError for nonexistent template."""
        with db_session.begin():
            with pytest.raises(KeyError):
                flight_storage.update_template(
                    PromptTemplateID(),
                    description="Test",
                    session=db_session,
                )


# =============================================================================
# Survey Schema Tests
# =============================================================================


class TestGetSurveySchema(object):
    """Tests for flight_storage.get_survey_schema()."""

    def test_get_by_schema_id(
        self,
        db_session: Session,
        survey_schema_factory: t.Callable[..., SurveySchema],
    ) -> None:
        """get_survey_schema() with schema_id returns the schema."""
        schema = survey_schema_factory(name="get_by_id")

        with db_session.begin():
            result = flight_storage.get_survey_schema(schema.schema_id, session=db_session)

        assert result is not None
        assert result.schema_id == schema.schema_id
        assert result.name == "get_by_id"

    def test_get_by_name(
        self,
        db_session: Session,
        survey_schema_factory: t.Callable[..., SurveySchema],
    ) -> None:
        """get_survey_schema() with name returns the schema."""
        schema = survey_schema_factory(name="get_by_name")

        with db_session.begin():
            result = flight_storage.get_survey_schema(name="get_by_name", session=db_session)

        assert result is not None
        assert result.schema_id == schema.schema_id

    def test_get_nonexistent_returns_none(self, db_session: Session) -> None:
        """get_survey_schema() returns None for nonexistent schema."""
        with db_session.begin():
            result = flight_storage.get_survey_schema(SurveySchemaID(), session=db_session)

        assert result is None

    def test_get_requires_id_or_name(self, db_session: Session) -> None:
        """get_survey_schema() raises ValueError if neither provided."""
        with pytest.raises(ValueError, match="Either schema_id or name must be provided"):
            flight_storage.get_survey_schema(session=db_session)


class TestFindSurveySchemas(object):
    """Tests for flight_storage.find_survey_schemas()."""

    def test_find_all(
        self,
        db_session: Session,
        survey_schema_factory: t.Callable[..., SurveySchema],
    ) -> None:
        """find_survey_schemas() returns all schemas."""
        s1 = survey_schema_factory(name="find_all_1")
        s2 = survey_schema_factory(name="find_all_2")

        with db_session.begin():
            result = flight_storage.find_survey_schemas(session=db_session)

        schema_ids = {s.schema_id for s in result}
        assert s1.schema_id in schema_ids
        assert s2.schema_id in schema_ids

    def test_find_by_default(
        self,
        db_session: Session,
        survey_schema_factory: t.Callable[..., SurveySchema],
    ) -> None:
        """find_survey_schemas() filters by is_default."""
        survey_schema_factory(name="default_schema", is_default=True)
        survey_schema_factory(name="non_default_schema", is_default=False)

        with db_session.begin():
            defaults = flight_storage.find_survey_schemas(is_default=True, session=db_session)
            non_defaults = flight_storage.find_survey_schemas(is_default=False, session=db_session)

        default_names = {s.name for s in defaults}
        non_default_names = {s.name for s in non_defaults}
        assert "default_schema" in default_names
        assert "non_default_schema" in non_default_names


class TestCreateSurveySchema(object):
    """Tests for flight_storage.create_survey_schema()."""

    def test_create_schema(self, db_session: Session) -> None:
        """create_survey_schema() creates a schema with dimensions."""
        dimensions = [
            SurveyDimension(
                name="test_dim",
                label="Test",
                spec=RatingSpec(min=1, max=5),
            )
        ]
        with db_session.begin():
            schema = flight_storage.create_survey_schema(
                name="created_schema",
                dimensions=dimensions,
                is_default=True,
                session=db_session,
            )

        assert schema.name == "created_schema"
        assert schema.is_default is True
        assert len(schema.dimensions) == 1
        assert schema.dimensions[0].name == "test_dim"


# =============================================================================
# Flight Tests
# =============================================================================


class TestGetFlight(object):
    """Tests for flight_storage.get_flight()."""

    def test_get_by_flight_id(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """get_flight() returns the flight."""
        flight = flight_factory(created_by="get_test")

        with db_session.begin():
            result = flight_storage.get_flight(flight.flight_id, session=db_session)

        assert result is not None
        assert result.flight_id == flight.flight_id
        assert result.created_by == "get_test"

    def test_get_with_template(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
        test_template: PromptTemplate,
    ) -> None:
        """get_flight() with with_template=True returns FlightWithTemplate."""
        flight = flight_factory()

        with db_session.begin():
            result = flight_storage.get_flight(
                flight.flight_id,
                with_template=True,
                session=db_session,
            )

        assert result is not None
        assert isinstance(result, FlightWithTemplate)
        assert result.template_name == test_template.name
        assert result.template_version == test_template.version

    def test_get_nonexistent_returns_none(self, db_session: Session) -> None:
        """get_flight() returns None for nonexistent flight."""
        with db_session.begin():
            result = flight_storage.get_flight(FlightID(), session=db_session)

        assert result is None


class TestFindFlights(object):
    """Tests for flight_storage.find_flights()."""

    def test_find_all(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """find_flights() returns all flights."""
        f1 = flight_factory(created_by="find_1")
        f2 = flight_factory(created_by="find_2")

        with db_session.begin():
            result = flight_storage.find_flights(session=db_session)

        flight_ids = {f.flight_id for f in result}
        assert f1.flight_id in flight_ids
        assert f2.flight_id in flight_ids

    def test_find_by_template_id(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
        test_template: PromptTemplate,
    ) -> None:
        """find_flights() filters by template_id."""
        flight_factory(created_by="template_filter")

        with db_session.begin():
            result = flight_storage.find_flights(
                template_id=test_template.template_id,
                session=db_session,
            )

        assert len(result) >= 1
        assert all(f.template_id == test_template.template_id for f in result)

    def test_find_by_status(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """find_flights() filters by status."""
        flight = flight_factory(created_by="status_filter")
        with db_session.begin():
            flight_storage.complete_flight(flight.flight_id, session=db_session)

        with db_session.begin():
            completed = flight_storage.find_flights(
                status=FlightStatus.Completed,
                session=db_session,
            )
            active = flight_storage.find_flights(
                status=FlightStatus.Active,
                session=db_session,
            )

        completed_ids = {f.flight_id for f in completed}
        active_ids = {f.flight_id for f in active}
        assert flight.flight_id in completed_ids
        assert flight.flight_id not in active_ids

    def test_find_by_created_by(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """find_flights() filters by created_by."""
        flight_factory(created_by="unique_creator")
        flight_factory(created_by="other_creator")

        with db_session.begin():
            result = flight_storage.find_flights(created_by="unique_creator", session=db_session)

        assert len(result) == 1
        assert result[0].created_by == "unique_creator"

    def test_find_with_limit(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """find_flights() respects limit."""
        for i in range(5):
            flight_factory(created_by=f"limit_test_{i}")

        with db_session.begin():
            result = flight_storage.find_flights(limit=2, session=db_session)

        assert len(result) == 2


class TestCreateFlight(object):
    """Tests for flight_storage.create_flight()."""

    def test_create_flight(
        self,
        db_session: Session,
        test_template: PromptTemplate,
    ) -> None:
        """create_flight() creates a flight with all fields."""
        with db_session.begin():
            flight = flight_storage.create_flight(
                template_id=test_template.template_id,
                created_by="create_test",
                model_provider="anthropic",
                model_name="claude-sonnet-4",
                started_at=datetime.datetime.now(datetime.UTC),
                feature_flags={"flag": "value"},
                context={"key": "data"},
                model_config={"temperature": 0.7},
                session=db_session,
            )

        assert flight.template_id == test_template.template_id
        assert flight.created_by == "create_test"
        assert flight.model_provider == "anthropic"
        assert flight.model_name == "claude-sonnet-4"
        assert flight.feature_flags == {"flag": "value"}
        assert flight.context == {"key": "data"}
        assert flight.model_config_data == {"temperature": 0.7}
        assert flight.status == FlightStatus.Active
        assert flight.completed_at is None


class TestUpdateFlight(object):
    """Tests for flight_storage.update_flight()."""

    def test_update_status(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """update_flight() can change status."""
        flight = flight_factory()

        with db_session.begin():
            flight_storage.update_flight(
                flight.flight_id,
                status=FlightStatus.Completed,
                completed_at=datetime.datetime.now(datetime.UTC),
                session=db_session,
            )
            updated = flight_storage.get_flight(flight.flight_id, session=db_session)

        assert updated is not None
        assert updated.status == FlightStatus.Completed
        assert updated.completed_at is not None

    def test_update_outcome_metadata(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """update_flight() can set outcome_metadata."""
        flight = flight_factory()

        with db_session.begin():
            flight_storage.update_flight(
                flight.flight_id,
                outcome_metadata={"score": 85, "notes": "Good job"},
                session=db_session,
            )
            updated = flight_storage.get_flight(flight.flight_id, session=db_session)

        assert updated is not None
        assert updated.outcome_metadata == {"score": 85, "notes": "Good job"}

    def test_update_nonexistent_raises_keyerror(self, db_session: Session) -> None:
        """update_flight() raises KeyError for nonexistent flight."""
        with db_session.begin():
            with pytest.raises(KeyError):
                flight_storage.update_flight(
                    FlightID(),
                    status=FlightStatus.Completed,
                    session=db_session,
                )


class TestCompleteFlight(object):
    """Tests for flight_storage.complete_flight()."""

    def test_complete_flight(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """complete_flight() marks flight as completed."""
        flight = flight_factory()

        with db_session.begin():
            flight_storage.complete_flight(
                flight.flight_id,
                outcome_metadata={"result": "success"},
                session=db_session,
            )
            updated = flight_storage.get_flight(flight.flight_id, session=db_session)

        assert updated is not None
        assert updated.status == FlightStatus.Completed
        assert updated.completed_at is not None
        assert updated.outcome_metadata == {"result": "success"}


class TestCompleteFlightAbandoned(object):
    """Tests for abandoning flights via complete_flight()."""

    def test_complete_flight_as_abandoned(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """complete_flight() with Abandoned status marks flight as abandoned."""
        flight = flight_factory()

        with db_session.begin():
            flight_storage.complete_flight(
                flight.flight_id,
                status=FlightStatus.Abandoned,
                outcome_metadata={"reason": "user cancelled"},
                session=db_session,
            )
            updated = flight_storage.get_flight(flight.flight_id, session=db_session)

        assert updated is not None
        assert updated.status == FlightStatus.Abandoned
        assert updated.completed_at is not None
        assert updated.outcome_metadata == {"reason": "user cancelled"}


# =============================================================================
# Survey Tests
# =============================================================================


class TestGetSurvey(object):
    """Tests for flight_storage.get_survey()."""

    def test_get_by_survey_id(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """get_survey() returns the survey."""
        flight = flight_factory()
        with db_session.begin():
            survey = flight_storage.create_survey(
                flight_id=flight.flight_id,
                submitted_by="test_submitter",
                ratings={"quality": 4},
                session=db_session,
            )

        with db_session.begin():
            result = flight_storage.get_survey(survey.survey_id, session=db_session)

        assert result is not None
        assert result.survey_id == survey.survey_id
        assert result.submitted_by == "test_submitter"

    def test_get_nonexistent_returns_none(self, db_session: Session) -> None:
        """get_survey() returns None for nonexistent survey."""
        with db_session.begin():
            result = flight_storage.get_survey(SurveyID(), session=db_session)

        assert result is None


class TestFindSurveys(object):
    """Tests for flight_storage.find_surveys()."""

    def test_find_by_flight_id(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """find_surveys() filters by flight_id."""
        flight = flight_factory()
        with db_session.begin():
            survey = flight_storage.create_survey(
                flight_id=flight.flight_id,
                submitted_by="find_test",
                ratings={"score": 5},
                session=db_session,
            )

        with db_session.begin():
            result = flight_storage.find_surveys(flight_id=flight.flight_id, session=db_session)

        assert len(result) == 1
        assert result[0].survey_id == survey.survey_id

    def test_find_by_submitted_by(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """find_surveys() filters by submitted_by."""
        flight = flight_factory()
        with db_session.begin():
            flight_storage.create_survey(
                flight_id=flight.flight_id,
                submitted_by="unique_submitter",
                ratings={"score": 3},
                session=db_session,
            )

        with db_session.begin():
            result = flight_storage.find_surveys(submitted_by="unique_submitter", session=db_session)

        assert len(result) == 1
        assert result[0].submitted_by == "unique_submitter"


class TestCreateSurvey(object):
    """Tests for flight_storage.create_survey()."""

    def test_create_survey(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
        test_schema: SurveySchema,
    ) -> None:
        """create_survey() creates a survey with all fields."""
        flight = flight_factory()
        with db_session.begin():
            survey = flight_storage.create_survey(
                flight_id=flight.flight_id,
                submitted_by="survey_creator",
                ratings={"probing_depth": 4, "clarity": 5},
                schema_id=test_schema.schema_id,
                notes="Great session!",
                tags=["excellent", "recommended"],
                session=db_session,
            )

        assert survey.flight_id == flight.flight_id
        assert survey.submitted_by == "survey_creator"
        assert survey.ratings == {"probing_depth": 4, "clarity": 5}
        assert survey.schema_id == test_schema.schema_id
        assert survey.notes == "Great session!"
        assert survey.tags == ["excellent", "recommended"]

    def test_create_survey_without_schema(
        self,
        db_session: Session,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """create_survey() works without schema_id."""
        flight = flight_factory()
        with db_session.begin():
            survey = flight_storage.create_survey(
                flight_id=flight.flight_id,
                submitted_by="no_schema",
                ratings={"custom_field": 10},
                session=db_session,
            )

        assert survey.schema_id is None
        assert survey.ratings == {"custom_field": 10}
