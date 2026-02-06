"""Tests for flights API endpoints."""

from __future__ import annotations

import datetime
import typing as t
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from socratic.core import SocraticContainer
from socratic.core.config import FlightsWebSettings
from socratic.model import DeploymentEnvironment, Flight, PromptTemplate, RatingSpec, SurveyDimension, SurveySchema
from socratic.storage import flight as flight_storage

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def flights_app(container: SocraticContainer) -> FastAPI:
    """Create the Flights FastAPI application for testing."""
    from socratic.web.flights.main import _create_app  # pyright: ignore[reportPrivateUsage]

    container.wire(
        modules=[
            "socratic.web.flights.main",
            "socratic.web.flights.route.flight",
            "socratic.web.flights.route.template",
            "socratic.web.flights.route.survey",
            "tests.test_flights_api",
        ]
    )

    return _create_app(
        config=FlightsWebSettings(**container.config.web.flights()),
        env=DeploymentEnvironment.Test,
        root_path=t.cast(Path, container.root()),
    )


@pytest.fixture
def flights_client(
    flights_app: FastAPI,
    container: SocraticContainer,
    db_session: Session,
) -> t.Generator[TestClient]:
    """Provide a TestClient for flights API with database session override."""
    container.storage().persistent().session.override(db_session)

    with TestClient(flights_app) as test_client:
        yield test_client

    container.storage().persistent().session.reset_override()


# =============================================================================
# Test Data Fixtures
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
        is_default=True,
    )


@pytest.fixture
def flight_factory(
    db_session: Session,
    test_template: PromptTemplate,
) -> t.Callable[..., Flight]:
    """Factory fixture for creating test flights."""

    def create_flight(
        created_by: str = "test_user",
        model_provider: str = "openai",
        model_name: str = "gpt-4o",
        feature_flags: dict[str, t.Any] | None = None,
        context: dict[str, t.Any] | None = None,
    ) -> Flight:
        with db_session.begin():
            return flight_storage.create_flight(
                template_id=test_template.template_id,
                created_by=created_by,
                model_provider=model_provider,
                model_name=model_name,
                started_at=datetime.datetime.now(datetime.UTC),
                feature_flags=feature_flags,
                context=context,
                session=db_session,
            )

    return create_flight


@pytest.fixture
def test_flight(flight_factory: t.Callable[..., Flight]) -> Flight:
    """Provide a pre-created test flight."""
    return flight_factory(
        created_by="test_assessor",
        feature_flags={"conviviality": "conversational"},
        context={"objective_title": "Test Objective"},
    )


# =============================================================================
# Template API Tests
# =============================================================================


class TestListTemplates(object):
    """Tests for GET /api/templates."""

    def test_returns_empty_list_when_no_templates(
        self,
        flights_client: TestClient,
    ) -> None:
        """Returns empty list when no templates exist."""
        response = flights_client.get("/api/templates")

        assert response.status_code == 200
        data = response.json()
        assert data["templates"] == []

    def test_returns_all_templates(
        self,
        flights_client: TestClient,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        """Returns all templates."""
        t1 = template_factory(name="template_a", content="A")
        t2 = template_factory(name="template_b", content="B")

        response = flights_client.get("/api/templates")

        assert response.status_code == 200
        data = response.json()
        template_ids = {t["template_id"] for t in data["templates"]}
        assert str(t1.template_id) in template_ids
        assert str(t2.template_id) in template_ids

    def test_filters_by_name(
        self,
        flights_client: TestClient,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        """Filters templates by name."""
        template_factory(name="target", content="Target")
        template_factory(name="other", content="Other")

        response = flights_client.get("/api/templates?name=target")

        assert response.status_code == 200
        data = response.json()
        assert len(data["templates"]) == 1
        assert data["templates"][0]["name"] == "target"

    def test_filters_by_active_status(
        self,
        flights_client: TestClient,
        template_factory: t.Callable[..., PromptTemplate],
        db_session: Session,
    ) -> None:
        """Filters templates by active status."""
        t1 = template_factory(name="active_filter", content="Active")
        with db_session.begin():
            flight_storage.update_template(t1.template_id, is_active=False, session=db_session)

        response = flights_client.get("/api/templates?is_active=false")

        assert response.status_code == 200
        data = response.json()
        template_ids = {t["template_id"] for t in data["templates"]}
        assert str(t1.template_id) in template_ids


class TestGetTemplate(object):
    """Tests for GET /api/templates/{template_id}."""

    def test_returns_template(
        self,
        flights_client: TestClient,
        test_template: PromptTemplate,
    ) -> None:
        """Returns template for valid ID."""
        response = flights_client.get(f"/api/templates/{test_template.template_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["template_id"] == str(test_template.template_id)
        assert data["name"] == test_template.name
        assert data["content"] == test_template.content

    def test_returns_404_for_nonexistent(
        self,
        flights_client: TestClient,
    ) -> None:
        """Returns 404 for nonexistent template."""
        from socratic.model import PromptTemplateID

        response = flights_client.get(f"/api/templates/{PromptTemplateID()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Template not found"


class TestCreateTemplate(object):
    """Tests for POST /api/templates."""

    def test_creates_template(
        self,
        flights_client: TestClient,
    ) -> None:
        """Creates a new template."""
        response = flights_client.post(
            "/api/templates",
            json={
                "name": "new_api_template",
                "content": "New {{ var }}",
                "description": "Created via API",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "new_api_template"
        assert data["content"] == "New {{ var }}"
        assert data["description"] == "Created via API"
        assert data["version"] == 1
        assert data["is_active"] is True

    def test_creates_new_version(
        self,
        flights_client: TestClient,
        template_factory: t.Callable[..., PromptTemplate],
    ) -> None:
        """Creates new version when name exists."""
        template_factory(name="versioned_api", content="V1")

        response = flights_client.post(
            "/api/templates",
            json={
                "name": "versioned_api",
                "content": "V2",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["version"] == 2
        assert data["content"] == "V2"


class TestUpdateTemplate(object):
    """Tests for PATCH /api/templates/{template_id}."""

    def test_updates_description(
        self,
        flights_client: TestClient,
        test_template: PromptTemplate,
    ) -> None:
        """Updates template description."""
        response = flights_client.patch(
            f"/api/templates/{test_template.template_id}",
            params={"description": "Updated description"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"

    def test_updates_is_active(
        self,
        flights_client: TestClient,
        test_template: PromptTemplate,
    ) -> None:
        """Updates template active status."""
        response = flights_client.patch(
            f"/api/templates/{test_template.template_id}",
            params={"is_active": "false"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    def test_returns_404_for_nonexistent(
        self,
        flights_client: TestClient,
    ) -> None:
        """Returns 404 for nonexistent template."""
        from socratic.model import PromptTemplateID

        response = flights_client.patch(
            f"/api/templates/{PromptTemplateID()}",
            params={"description": "Test"},
        )

        assert response.status_code == 404


# =============================================================================
# Flight API Tests
# =============================================================================


class TestListFlights(object):
    """Tests for GET /api/flights."""

    def test_returns_empty_list_when_no_flights(
        self,
        flights_client: TestClient,
        test_template: PromptTemplate,  # Ensure template exists
    ) -> None:
        """Returns empty list when no flights exist."""
        response = flights_client.get("/api/flights")

        assert response.status_code == 200
        data = response.json()
        assert data["flights"] == []

    def test_returns_all_flights(
        self,
        flights_client: TestClient,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """Returns all flights."""
        f1 = flight_factory(created_by="list_1")
        f2 = flight_factory(created_by="list_2")

        response = flights_client.get("/api/flights")

        assert response.status_code == 200
        data = response.json()
        flight_ids = {f["flight_id"] for f in data["flights"]}
        assert str(f1.flight_id) in flight_ids
        assert str(f2.flight_id) in flight_ids

    def test_filters_by_status(
        self,
        flights_client: TestClient,
        flight_factory: t.Callable[..., Flight],
        db_session: Session,
    ) -> None:
        """Filters flights by status."""
        flight = flight_factory(created_by="status_test")
        with db_session.begin():
            flight_storage.complete_flight(flight.flight_id, session=db_session)

        response = flights_client.get("/api/flights?status_filter=completed")

        assert response.status_code == 200
        data = response.json()
        flight_ids = {f["flight_id"] for f in data["flights"]}
        assert str(flight.flight_id) in flight_ids

    def test_filters_by_created_by(
        self,
        flights_client: TestClient,
        flight_factory: t.Callable[..., Flight],
    ) -> None:
        """Filters flights by created_by."""
        flight_factory(created_by="unique_api_user")
        flight_factory(created_by="other_user")

        response = flights_client.get("/api/flights?created_by=unique_api_user")

        assert response.status_code == 200
        data = response.json()
        assert len(data["flights"]) == 1
        assert data["flights"][0]["created_by"] == "unique_api_user"


class TestGetFlight(object):
    """Tests for GET /api/flights/{flight_id}."""

    def test_returns_flight(
        self,
        flights_client: TestClient,
        test_flight: Flight,
    ) -> None:
        """Returns flight for valid ID."""
        response = flights_client.get(f"/api/flights/{test_flight.flight_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["flight_id"] == str(test_flight.flight_id)
        assert data["created_by"] == test_flight.created_by
        assert data["template_name"] is not None

    def test_returns_404_for_nonexistent(
        self,
        flights_client: TestClient,
    ) -> None:
        """Returns 404 for nonexistent flight."""
        from socratic.model import FlightID

        response = flights_client.get(f"/api/flights/{FlightID()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Flight not found"


class TestCreateFlight(object):
    """Tests for POST /api/flights."""

    def test_creates_flight(
        self,
        flights_client: TestClient,
        test_template: PromptTemplate,
    ) -> None:
        """Creates a new flight."""
        response = flights_client.post(
            "/api/flights",
            json={
                "template": test_template.name,
                "created_by": "api_creator",
                "model_provider": "anthropic",
                "model_name": "claude-sonnet-4",
                "feature_flags": {"mode": "test"},
                "context": {"objective_title": "API Test"},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["created_by"] == "api_creator"
        assert data["model_provider"] == "anthropic"
        assert data["model_name"] == "claude-sonnet-4"
        assert data["status"] == "active"
        assert "API Test" in data["rendered_content"]

    def test_returns_404_for_nonexistent_template(
        self,
        flights_client: TestClient,
    ) -> None:
        """Returns 404 when template doesn't exist."""
        response = flights_client.post(
            "/api/flights",
            json={
                "template": "nonexistent_template",
                "created_by": "test",
                "model_provider": "openai",
                "model_name": "gpt-4o",
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestUpdateFlight(object):
    """Tests for PATCH /api/flights/{flight_id}."""

    def test_updates_status(
        self,
        flights_client: TestClient,
        test_flight: Flight,
    ) -> None:
        """Updates flight status."""
        response = flights_client.patch(
            f"/api/flights/{test_flight.flight_id}",
            json={"status": "completed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["completed_at"] is not None

    def test_updates_outcome_metadata(
        self,
        flights_client: TestClient,
        test_flight: Flight,
    ) -> None:
        """Updates flight outcome_metadata."""
        response = flights_client.patch(
            f"/api/flights/{test_flight.flight_id}",
            json={"outcome_metadata": {"score": 95}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["outcome_metadata"] == {"score": 95}

    def test_returns_404_for_nonexistent(
        self,
        flights_client: TestClient,
    ) -> None:
        """Returns 404 for nonexistent flight."""
        from socratic.model import FlightID

        response = flights_client.patch(
            f"/api/flights/{FlightID()}",
            json={"status": "completed"},
        )

        assert response.status_code == 404


class TestCompleteFlight(object):
    """Tests for POST /api/flights/{flight_id}/complete."""

    def test_completes_flight(
        self,
        flights_client: TestClient,
        test_flight: Flight,
    ) -> None:
        """Completes a flight."""
        # The endpoint accepts outcome_metadata as the direct body (not wrapped)
        response = flights_client.post(
            f"/api/flights/{test_flight.flight_id}/complete",
            json={"result": "pass"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["outcome_metadata"] == {"result": "pass"}

    def test_returns_404_for_nonexistent(
        self,
        flights_client: TestClient,
    ) -> None:
        """Returns 404 for nonexistent flight."""
        from socratic.model import FlightID

        response = flights_client.post(f"/api/flights/{FlightID()}/complete")

        assert response.status_code == 404


# =============================================================================
# Survey Schema API Tests
# =============================================================================


class TestListSurveySchemas(object):
    """Tests for GET /api/survey-schemas."""

    def test_returns_empty_list_when_no_schemas(
        self,
        flights_client: TestClient,
    ) -> None:
        """Returns empty list when no schemas exist."""
        response = flights_client.get("/api/survey-schemas")

        assert response.status_code == 200
        data = response.json()
        assert data["schemas"] == []

    def test_returns_all_schemas(
        self,
        flights_client: TestClient,
        survey_schema_factory: t.Callable[..., SurveySchema],
    ) -> None:
        """Returns all survey schemas."""
        s1 = survey_schema_factory(name="schema_a")
        s2 = survey_schema_factory(name="schema_b")

        response = flights_client.get("/api/survey-schemas")

        assert response.status_code == 200
        data = response.json()
        schema_ids = {s["schema_id"] for s in data["schemas"]}
        assert str(s1.schema_id) in schema_ids
        assert str(s2.schema_id) in schema_ids


class TestGetSurveySchema(object):
    """Tests for GET /api/survey-schemas/{schema_id}."""

    def test_returns_schema(
        self,
        flights_client: TestClient,
        test_schema: SurveySchema,
    ) -> None:
        """Returns schema for valid ID."""
        response = flights_client.get(f"/api/survey-schemas/{test_schema.schema_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["schema_id"] == str(test_schema.schema_id)
        assert data["name"] == test_schema.name

    def test_returns_404_for_nonexistent(
        self,
        flights_client: TestClient,
    ) -> None:
        """Returns 404 for nonexistent schema."""
        from socratic.model import SurveySchemaID

        response = flights_client.get(f"/api/survey-schemas/{SurveySchemaID()}")

        assert response.status_code == 404


class TestCreateSurveySchema(object):
    """Tests for POST /api/survey-schemas."""

    def test_creates_schema(
        self,
        flights_client: TestClient,
    ) -> None:
        """Creates a new survey schema."""
        response = flights_client.post(
            "/api/survey-schemas",
            json={
                "name": "api_created_schema",
                "dimensions": [
                    {
                        "name": "rating",
                        "label": "Rate this",
                        "required": True,
                        "spec": {"kind": "rating", "min": 1, "max": 5},
                    }
                ],
                "is_default": False,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "api_created_schema"
        assert len(data["dimensions"]) == 1

    def test_returns_409_for_duplicate_name(
        self,
        flights_client: TestClient,
        survey_schema_factory: t.Callable[..., SurveySchema],
    ) -> None:
        """Returns 409 when schema name already exists."""
        survey_schema_factory(name="duplicate_schema")

        response = flights_client.post(
            "/api/survey-schemas",
            json={
                "name": "duplicate_schema",
                "dimensions": [],
            },
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]


# =============================================================================
# Survey API Tests
# =============================================================================


class TestListFlightSurveys(object):
    """Tests for GET /api/flights/{flight_id}/surveys."""

    def test_returns_empty_list_when_no_surveys(
        self,
        flights_client: TestClient,
        test_flight: Flight,
    ) -> None:
        """Returns empty list when flight has no surveys."""
        response = flights_client.get(f"/api/flights/{test_flight.flight_id}/surveys")

        assert response.status_code == 200
        data = response.json()
        assert data["surveys"] == []

    def test_returns_flight_surveys(
        self,
        flights_client: TestClient,
        test_flight: Flight,
        db_session: Session,
    ) -> None:
        """Returns surveys for a flight."""
        with db_session.begin():
            survey = flight_storage.create_survey(
                flight_id=test_flight.flight_id,
                submitted_by="test_submitter",
                ratings={"score": 5},
                session=db_session,
            )

        response = flights_client.get(f"/api/flights/{test_flight.flight_id}/surveys")

        assert response.status_code == 200
        data = response.json()
        assert len(data["surveys"]) == 1
        assert data["surveys"][0]["survey_id"] == str(survey.survey_id)

    def test_returns_404_for_nonexistent_flight(
        self,
        flights_client: TestClient,
    ) -> None:
        """Returns 404 for nonexistent flight."""
        from socratic.model import FlightID

        response = flights_client.get(f"/api/flights/{FlightID()}/surveys")

        assert response.status_code == 404


class TestCreateSurvey(object):
    """Tests for POST /api/flights/{flight_id}/surveys."""

    def test_creates_survey(
        self,
        flights_client: TestClient,
        test_flight: Flight,
    ) -> None:
        """Creates a survey for a flight."""
        response = flights_client.post(
            f"/api/flights/{test_flight.flight_id}/surveys",
            json={
                "submitted_by": "api_submitter",
                "ratings": {"quality": 4, "clarity": 5},
                "notes": "Great session",
                "tags": ["excellent"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["submitted_by"] == "api_submitter"
        assert data["ratings"] == {"quality": 4, "clarity": 5}
        assert data["notes"] == "Great session"
        assert data["tags"] == ["excellent"]

    def test_creates_survey_with_schema(
        self,
        flights_client: TestClient,
        test_flight: Flight,
        test_schema: SurveySchema,
    ) -> None:
        """Creates a survey with a schema reference."""
        response = flights_client.post(
            f"/api/flights/{test_flight.flight_id}/surveys",
            json={
                "submitted_by": "schema_user",
                "ratings": {"quality": 3},
                "schema_id": str(test_schema.schema_id),
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["schema_id"] == str(test_schema.schema_id)

    def test_returns_404_for_nonexistent_flight(
        self,
        flights_client: TestClient,
    ) -> None:
        """Returns 404 for nonexistent flight."""
        from socratic.model import FlightID

        response = flights_client.post(
            f"/api/flights/{FlightID()}/surveys",
            json={
                "submitted_by": "test",
                "ratings": {},
            },
        )

        assert response.status_code == 404


class TestGetSurvey(object):
    """Tests for GET /api/surveys/{survey_id}."""

    def test_returns_survey(
        self,
        flights_client: TestClient,
        test_flight: Flight,
        db_session: Session,
    ) -> None:
        """Returns survey for valid ID."""
        with db_session.begin():
            survey = flight_storage.create_survey(
                flight_id=test_flight.flight_id,
                submitted_by="get_test",
                ratings={"score": 5},
                session=db_session,
            )

        response = flights_client.get(f"/api/surveys/{survey.survey_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["survey_id"] == str(survey.survey_id)
        assert data["submitted_by"] == "get_test"

    def test_returns_404_for_nonexistent(
        self,
        flights_client: TestClient,
    ) -> None:
        """Returns 404 for nonexistent survey."""
        from socratic.model import SurveyID

        response = flights_client.get(f"/api/surveys/{SurveyID()}")

        assert response.status_code == 404
