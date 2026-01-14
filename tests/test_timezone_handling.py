"""Tests for timezone-aware datetime handling.

Verifies that timestamps are correctly stored, retrieved, and compared
after migration to timestamp with time zone columns.
"""

from __future__ import annotations

import datetime
import typing as t
from zoneinfo import ZoneInfo

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from socratic.model import Assignment, AssignmentID, Objective, ObjectiveID, ObjectiveStatus, Organization, \
    OrganizationID, User, UserID, UserRole
from socratic.storage import assignment as assignment_storage
from socratic.storage.table import assignments, objectives


class JWTConfig(t.NamedTuple):
    """JWT configuration for tests."""

    secret_key: str
    algorithm: str


@pytest.fixture
def objective_factory(
    db_session: Session,
) -> t.Callable[..., Objective]:
    """Factory fixture for creating test objectives."""

    def create_objective(
        organization_id: OrganizationID,
        created_by: UserID,
        title: str = "Test Objective",
        description: str = "A test objective",
        status: ObjectiveStatus = ObjectiveStatus.Published,
    ) -> Objective:
        objective_id = ObjectiveID()

        with db_session.begin():
            obj = objectives(
                objective_id=objective_id,
                organization_id=organization_id,
                title=title,
                description=description,
                status=status.value,
                created_by=created_by,
            )
            db_session.add(obj)
            db_session.flush()

            stmt = select(objectives.__table__).where(objectives.objective_id == objective_id)
            row = db_session.execute(stmt).mappings().one()
            return Objective(**row)

    return create_objective


@pytest.fixture
def assignment_factory(
    db_session: Session,
) -> t.Callable[..., Assignment]:
    """Factory fixture for creating test assignments."""

    def create_assignment(
        organization_id: OrganizationID,
        objective_id: ObjectiveID,
        assigned_by: UserID,
        assigned_to: UserID,
        max_attempts: int = 3,
        available_from: datetime.datetime | None = None,
        available_until: datetime.datetime | None = None,
    ) -> Assignment:
        assignment_id = AssignmentID()

        with db_session.begin():
            asgn = assignments(
                assignment_id=assignment_id,
                organization_id=organization_id,
                objective_id=objective_id,
                assigned_by=assigned_by,
                assigned_to=assigned_to,
                max_attempts=max_attempts,
                available_from=available_from,
                available_until=available_until,
                retake_policy="none",
            )
            db_session.add(asgn)
            db_session.flush()

            stmt = select(assignments.__table__).where(assignments.assignment_id == assignment_id)
            row = db_session.execute(stmt).mappings().one()
            return Assignment(**row)

    return create_assignment


def create_auth_token(
    user: User,
    organization_id: OrganizationID,
    role: UserRole,
    jwt_config: JWTConfig,
) -> str:
    """Create a JWT token for testing."""
    now = datetime.datetime.now(datetime.UTC)
    payload = {
        "sub": str(user.user_id),
        "org": str(organization_id),
        "role": role.value,
        "exp": now + datetime.timedelta(hours=1),
        "iat": now,
    }
    return jwt.encode(payload, jwt_config.secret_key, algorithm=jwt_config.algorithm)


class TestTimezoneStorage(object):
    """Tests for timezone-aware datetime storage."""

    def test_timestamps_stored_with_timezone_info(
        self,
        db_session: Session,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
    ) -> None:
        """Timestamps are stored and retrieved with timezone info."""
        educator = user_factory(
            email="educator@test.com",
            name="Test Educator",
            organization_id=test_org.organization_id,
            role=UserRole.Educator,
        )
        learner = user_factory(
            email="learner@test.com",
            name="Test Learner",
            organization_id=test_org.organization_id,
            role=UserRole.Learner,
        )
        objective = objective_factory(
            organization_id=test_org.organization_id,
            created_by=educator.user_id,
        )

        # Create assignment with timezone-aware datetime
        available_from = datetime.datetime(2026, 6, 15, 14, 30, tzinfo=datetime.UTC)
        assignment = assignment_factory(
            organization_id=test_org.organization_id,
            objective_id=objective.objective_id,
            assigned_by=educator.user_id,
            assigned_to=learner.user_id,
            available_from=available_from,
        )

        # Retrieve and verify timezone is preserved
        with db_session.begin():
            retrieved = assignment_storage.get(assignment.assignment_id, session=db_session)
            assert retrieved is not None
            assert retrieved.available_from is not None
            assert retrieved.available_from.tzinfo is not None
            # The timestamp should represent the same instant
            assert retrieved.available_from == available_from

    def test_create_time_has_timezone_info(
        self,
        db_session: Session,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
    ) -> None:
        """Server-generated create_time includes timezone info."""
        educator = user_factory(
            email="educator@test.com",
            name="Test Educator",
            organization_id=test_org.organization_id,
            role=UserRole.Educator,
        )
        learner = user_factory(
            email="learner@test.com",
            name="Test Learner",
            organization_id=test_org.organization_id,
            role=UserRole.Learner,
        )
        objective = objective_factory(
            organization_id=test_org.organization_id,
            created_by=educator.user_id,
        )

        assignment = assignment_factory(
            organization_id=test_org.organization_id,
            objective_id=objective.objective_id,
            assigned_by=educator.user_id,
            assigned_to=learner.user_id,
        )

        # Retrieve and verify create_time has timezone
        with db_session.begin():
            retrieved = assignment_storage.get(assignment.assignment_id, session=db_session)
            assert retrieved is not None
            assert retrieved.create_time.tzinfo is not None

    def test_different_timezone_representations_compare_equal(
        self,
        db_session: Session,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
    ) -> None:
        """Same instant in different timezone representations compares equal."""
        educator = user_factory(
            email="educator@test.com",
            name="Test Educator",
            organization_id=test_org.organization_id,
            role=UserRole.Educator,
        )
        learner = user_factory(
            email="learner@test.com",
            name="Test Learner",
            organization_id=test_org.organization_id,
            role=UserRole.Learner,
        )
        objective = objective_factory(
            organization_id=test_org.organization_id,
            created_by=educator.user_id,
        )

        # 14:00 UTC
        utc_time = datetime.datetime(2026, 6, 15, 14, 0, tzinfo=datetime.UTC)
        # Same instant as US/Pacific (UTC-7 in summer due to PDT)
        pacific_tz = ZoneInfo("America/Los_Angeles")
        pacific_time = datetime.datetime(2026, 6, 15, 7, 0, tzinfo=pacific_tz)

        assignment = assignment_factory(
            organization_id=test_org.organization_id,
            objective_id=objective.objective_id,
            assigned_by=educator.user_id,
            assigned_to=learner.user_id,
            available_from=utc_time,
        )

        # Retrieve and compare with Pacific time representation
        with db_session.begin():
            retrieved = assignment_storage.get(assignment.assignment_id, session=db_session)
            assert retrieved is not None
            assert retrieved.available_from is not None
            # These should be the same instant
            assert retrieved.available_from == pacific_time


class TestAssignmentAvailability(object):
    """Tests for assignment availability with timezone-aware datetimes."""

    def test_future_available_from_shows_not_available(
        self,
        client: TestClient,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
        jwt_manager: JWTConfig,
    ) -> None:
        """Assignment with future available_from in UTC is not available."""
        educator = user_factory(
            email="educator@test.com",
            name="Test Educator",
            organization_id=test_org.organization_id,
            role=UserRole.Educator,
        )
        learner = user_factory(
            email="learner@test.com",
            name="Test Learner",
            organization_id=test_org.organization_id,
            role=UserRole.Learner,
        )
        objective = objective_factory(
            organization_id=test_org.organization_id,
            created_by=educator.user_id,
        )

        # Create assignment available 1 hour from now in UTC
        future_utc = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
        assignment_factory(
            organization_id=test_org.organization_id,
            objective_id=objective.objective_id,
            assigned_by=educator.user_id,
            assigned_to=learner.user_id,
            available_from=future_utc,
        )

        # Learner requests their assignments
        token = create_auth_token(learner, test_org.organization_id, UserRole.Learner, jwt_manager)
        response = client.get(
            "/api/learners/me/assignments",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["assignments"]) == 1
        assert data["assignments"][0]["is_available"] is False

    def test_past_available_until_shows_not_available(
        self,
        client: TestClient,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
        jwt_manager: JWTConfig,
    ) -> None:
        """Assignment with past available_until is not available."""
        educator = user_factory(
            email="educator@test.com",
            name="Test Educator",
            organization_id=test_org.organization_id,
            role=UserRole.Educator,
        )
        learner = user_factory(
            email="learner@test.com",
            name="Test Learner",
            organization_id=test_org.organization_id,
            role=UserRole.Learner,
        )
        objective = objective_factory(
            organization_id=test_org.organization_id,
            created_by=educator.user_id,
        )

        # Create assignment that expired 1 hour ago
        past_utc = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
        assignment_factory(
            organization_id=test_org.organization_id,
            objective_id=objective.objective_id,
            assigned_by=educator.user_id,
            assigned_to=learner.user_id,
            available_until=past_utc,
        )

        # Learner requests their assignments
        token = create_auth_token(learner, test_org.organization_id, UserRole.Learner, jwt_manager)
        response = client.get(
            "/api/learners/me/assignments",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["assignments"]) == 1
        assert data["assignments"][0]["is_available"] is False

    def test_currently_available_assignment_shows_available(
        self,
        client: TestClient,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
        jwt_manager: JWTConfig,
    ) -> None:
        """Assignment within availability window is available."""
        educator = user_factory(
            email="educator@test.com",
            name="Test Educator",
            organization_id=test_org.organization_id,
            role=UserRole.Educator,
        )
        learner = user_factory(
            email="learner@test.com",
            name="Test Learner",
            organization_id=test_org.organization_id,
            role=UserRole.Learner,
        )
        objective = objective_factory(
            organization_id=test_org.organization_id,
            created_by=educator.user_id,
        )

        # Create assignment that started 1 hour ago and ends in 1 hour
        now = datetime.datetime.now(datetime.UTC)
        assignment_factory(
            organization_id=test_org.organization_id,
            objective_id=objective.objective_id,
            assigned_by=educator.user_id,
            assigned_to=learner.user_id,
            available_from=now - datetime.timedelta(hours=1),
            available_until=now + datetime.timedelta(hours=1),
        )

        # Learner requests their assignments
        token = create_auth_token(learner, test_org.organization_id, UserRole.Learner, jwt_manager)
        response = client.get(
            "/api/learners/me/assignments",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["assignments"]) == 1
        assert data["assignments"][0]["is_available"] is True
