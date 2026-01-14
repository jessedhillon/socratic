"""Tests for assignment API endpoints."""

from __future__ import annotations

import typing as t

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from socratic.core import TimestampProvider
from socratic.model import Assignment, Objective, ObjectiveStatus, Organization, OrganizationID, User, UserID, UserRole
from socratic.storage import assignment as assignment_storage
from socratic.storage import objective as objective_storage

from .conftest import create_auth_token


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
        with db_session.begin():
            return objective_storage.create(
                organization_id=organization_id,
                created_by=created_by,
                title=title,
                description=description,
                status=status,
                session=db_session,
            )

    return create_objective


@pytest.fixture
def assignment_factory(
    db_session: Session,
) -> t.Callable[..., Assignment]:
    """Factory fixture for creating test assignments."""

    def create_assignment(
        organization_id: OrganizationID,
        objective_id: t.Any,
        assigned_by: UserID,
        assigned_to: UserID,
        max_attempts: int = 3,
    ) -> Assignment:
        with db_session.begin():
            return assignment_storage.create(
                organization_id=organization_id,
                objective_id=objective_id,
                assigned_by=assigned_by,
                assigned_to=assigned_to,
                max_attempts=max_attempts,
                session=db_session,
            )

    return create_assignment


class TestCreateAssignment(object):
    """Tests for POST /api/assignments."""

    def test_rejects_duplicate_assignment(
        self,
        client: TestClient,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
        utcnow: TimestampProvider,
    ) -> None:
        """Returns 409 when assigning same objective to same learner twice."""
        # Create educator and learner
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

        # Create objective
        objective = objective_factory(
            organization_id=test_org.organization_id,
            created_by=educator.user_id,
            title="Test Objective",
        )

        # Create first assignment
        assignment_factory(
            organization_id=test_org.organization_id,
            objective_id=objective.objective_id,
            assigned_by=educator.user_id,
            assigned_to=learner.user_id,
        )

        # Try to create duplicate
        token = create_auth_token(educator, test_org.organization_id, UserRole.Educator, utcnow)
        response = client.post(
            "/api/assignments",
            json={
                "objective_id": str(objective.objective_id),
                "assigned_to": str(learner.user_id),
                "max_attempts": 3,
                "retake_policy": "none",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 409
        assert "already assigned" in response.json()["detail"]

    def test_allows_different_learners_same_objective(
        self,
        client: TestClient,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
        utcnow: TimestampProvider,
    ) -> None:
        """Allows assigning same objective to different learners."""
        educator = user_factory(
            email="educator@test.com",
            name="Test Educator",
            organization_id=test_org.organization_id,
            role=UserRole.Educator,
        )
        learner1 = user_factory(
            email="learner1@test.com",
            name="Test Learner 1",
            organization_id=test_org.organization_id,
            role=UserRole.Learner,
        )
        learner2 = user_factory(
            email="learner2@test.com",
            name="Test Learner 2",
            organization_id=test_org.organization_id,
            role=UserRole.Learner,
        )

        objective = objective_factory(
            organization_id=test_org.organization_id,
            created_by=educator.user_id,
        )

        # Assign to first learner
        assignment_factory(
            organization_id=test_org.organization_id,
            objective_id=objective.objective_id,
            assigned_by=educator.user_id,
            assigned_to=learner1.user_id,
        )

        # Assign to second learner (should succeed)
        token = create_auth_token(educator, test_org.organization_id, UserRole.Educator, utcnow)
        response = client.post(
            "/api/assignments",
            json={
                "objective_id": str(objective.objective_id),
                "assigned_to": str(learner2.user_id),
                "max_attempts": 3,
                "retake_policy": "none",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201


class TestBulkCreateAssignments(object):
    """Tests for POST /api/assignments/bulk."""

    def test_skips_duplicate_assignments(
        self,
        client: TestClient,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
        utcnow: TimestampProvider,
    ) -> None:
        """Bulk creation skips learners who already have the assignment."""
        educator = user_factory(
            email="educator@test.com",
            name="Test Educator",
            organization_id=test_org.organization_id,
            role=UserRole.Educator,
        )
        learner1 = user_factory(
            email="learner1@test.com",
            name="Test Learner 1",
            organization_id=test_org.organization_id,
            role=UserRole.Learner,
        )
        learner2 = user_factory(
            email="learner2@test.com",
            name="Test Learner 2",
            organization_id=test_org.organization_id,
            role=UserRole.Learner,
        )

        objective = objective_factory(
            organization_id=test_org.organization_id,
            created_by=educator.user_id,
        )

        # Pre-assign to learner1
        assignment_factory(
            organization_id=test_org.organization_id,
            objective_id=objective.objective_id,
            assigned_by=educator.user_id,
            assigned_to=learner1.user_id,
        )

        # Bulk assign to both learners
        token = create_auth_token(educator, test_org.organization_id, UserRole.Educator, utcnow)
        response = client.post(
            "/api/assignments/bulk",
            json={
                "objective_id": str(objective.objective_id),
                "assigned_to": [str(learner1.user_id), str(learner2.user_id)],
                "max_attempts": 3,
                "retake_policy": "none",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        # Only learner2 should get a new assignment
        assert data["total"] == 1
        assert data["assignments"][0]["assigned_to"] == str(learner2.user_id)
