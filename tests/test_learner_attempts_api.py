"""Tests for learner attempt history API endpoint."""

from __future__ import annotations

import datetime
import decimal
import typing as t

import pytest
import sqlalchemy as sqla
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from socratic.model import AssessmentAttempt, Assignment, AttemptStatus, EvaluationResult, Grade, Objective, \
    ObjectiveStatus, Organization, OrganizationID, User, UserID, UserRole
from socratic.storage import assignment as assignment_storage
from socratic.storage import attempt as attempt_storage
from socratic.storage import evaluation as evaluation_storage
from socratic.storage import objective as objective_storage
from socratic.storage.table import assessment_attempts

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


@pytest.fixture
def attempt_factory(
    db_session: Session,
) -> t.Callable[..., AssessmentAttempt]:
    """Factory fixture for creating test attempts."""

    def create_attempt(
        assignment_id: t.Any,
        learner_id: UserID,
        status: AttemptStatus = AttemptStatus.NotStarted,
    ) -> AssessmentAttempt:
        with db_session.begin():
            return attempt_storage.create(
                assignment_id=assignment_id,
                learner_id=learner_id,
                status=status,
                session=db_session,
            )

    return create_attempt


@pytest.fixture
def evaluation_factory(
    db_session: Session,
) -> t.Callable[..., EvaluationResult]:
    """Factory fixture for creating test evaluations."""

    def create_evaluation(
        attempt_id: t.Any,
        strengths: list[str] | None = None,
        gaps: list[str] | None = None,
        reasoning_summary: str | None = None,
    ) -> EvaluationResult:
        with db_session.begin():
            return evaluation_storage.create(
                attempt_id=attempt_id,
                strengths=strengths,
                gaps=gaps,
                reasoning_summary=reasoning_summary,
                session=db_session,
            )

    return create_evaluation


class TestListMyAttempts(object):
    """Tests for GET /api/learners/me/attempts."""

    def test_returns_empty_list_when_no_attempts(
        self,
        client: TestClient,
        test_org: Organization,
        user_factory: t.Callable[..., User],
    ) -> None:
        """Returns empty list when learner has no attempts."""
        learner = user_factory(
            email="learner@test.com",
            name="Test Learner",
            organization_id=test_org.organization_id,
            role=UserRole.Learner,
        )

        token = create_auth_token(learner, test_org.organization_id, UserRole.Learner)
        response = client.get(
            "/api/learners/me/attempts",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["attempts"] == []
        assert data["total"] == 0

    def test_returns_attempts_with_objective_info(
        self,
        client: TestClient,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """Returns attempts with assignment and objective details."""
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
            title="Understanding Variables",
            description="Learn about variables in programming",
        )
        assignment = assignment_factory(
            organization_id=test_org.organization_id,
            objective_id=objective.objective_id,
            assigned_by=educator.user_id,
            assigned_to=learner.user_id,
        )
        attempt_factory(
            assignment_id=assignment.assignment_id,
            learner_id=learner.user_id,
            status=AttemptStatus.Completed,
        )

        token = create_auth_token(learner, test_org.organization_id, UserRole.Learner)
        response = client.get(
            "/api/learners/me/attempts",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["attempts"]) == 1

        attempt = data["attempts"][0]
        assert attempt["objective_id"] == str(objective.objective_id)
        assert attempt["objective_title"] == "Understanding Variables"
        assert attempt["objective_description"] == "Learn about variables in programming"
        assert attempt["status"] == "completed"

    def test_returns_attempts_sorted_by_create_time_descending(
        self,
        client: TestClient,
        db_session: Session,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """Returns attempts sorted by create_time descending (latest first)."""
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

        # Create multiple attempts
        attempt1 = attempt_factory(
            assignment_id=assignment.assignment_id,
            learner_id=learner.user_id,
        )
        attempt2 = attempt_factory(
            assignment_id=assignment.assignment_id,
            learner_id=learner.user_id,
        )
        attempt3 = attempt_factory(
            assignment_id=assignment.assignment_id,
            learner_id=learner.user_id,
        )

        # Set explicit create_times to ensure deterministic ordering
        base_time = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.UTC)
        with db_session.begin():
            db_session.execute(
                sqla
                .update(assessment_attempts)
                .where(assessment_attempts.attempt_id == attempt1.attempt_id)
                .values(create_time=base_time)
            )
            db_session.execute(
                sqla
                .update(assessment_attempts)
                .where(assessment_attempts.attempt_id == attempt2.attempt_id)
                .values(create_time=base_time + datetime.timedelta(hours=1))
            )
            db_session.execute(
                sqla
                .update(assessment_attempts)
                .where(assessment_attempts.attempt_id == attempt3.attempt_id)
                .values(create_time=base_time + datetime.timedelta(hours=2))
            )

        token = create_auth_token(learner, test_org.organization_id, UserRole.Learner)
        response = client.get(
            "/api/learners/me/attempts",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3

        # Should be sorted by create_time desc (latest first = attempt3)
        attempt_ids = [a["attempt_id"] for a in data["attempts"]]
        assert attempt_ids == [
            str(attempt3.attempt_id),
            str(attempt2.attempt_id),
            str(attempt1.attempt_id),
        ]

    def test_filters_by_assignment_id(
        self,
        client: TestClient,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """Filters attempts by assignment_id query parameter."""
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
        objective1 = objective_factory(
            organization_id=test_org.organization_id,
            created_by=educator.user_id,
            title="Objective 1",
        )
        objective2 = objective_factory(
            organization_id=test_org.organization_id,
            created_by=educator.user_id,
            title="Objective 2",
        )
        assignment1 = assignment_factory(
            organization_id=test_org.organization_id,
            objective_id=objective1.objective_id,
            assigned_by=educator.user_id,
            assigned_to=learner.user_id,
        )
        assignment2 = assignment_factory(
            organization_id=test_org.organization_id,
            objective_id=objective2.objective_id,
            assigned_by=educator.user_id,
            assigned_to=learner.user_id,
        )

        # Create attempts for both assignments
        attempt_factory(
            assignment_id=assignment1.assignment_id,
            learner_id=learner.user_id,
        )
        attempt_factory(
            assignment_id=assignment2.assignment_id,
            learner_id=learner.user_id,
        )

        # Filter by assignment1
        token = create_auth_token(learner, test_org.organization_id, UserRole.Learner)
        response = client.get(
            f"/api/learners/me/attempts?assignment_id={assignment1.assignment_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["attempts"][0]["assignment_id"] == str(assignment1.assignment_id)
        assert data["attempts"][0]["objective_title"] == "Objective 1"

    def test_only_returns_own_attempts(
        self,
        client: TestClient,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """Learner only sees their own attempts, not other learners'."""
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
        assignment1 = assignment_factory(
            organization_id=test_org.organization_id,
            objective_id=objective.objective_id,
            assigned_by=educator.user_id,
            assigned_to=learner1.user_id,
        )
        assignment2 = assignment_factory(
            organization_id=test_org.organization_id,
            objective_id=objective.objective_id,
            assigned_by=educator.user_id,
            assigned_to=learner2.user_id,
        )

        # Create attempts for both learners
        attempt_factory(
            assignment_id=assignment1.assignment_id,
            learner_id=learner1.user_id,
        )
        attempt_factory(
            assignment_id=assignment2.assignment_id,
            learner_id=learner2.user_id,
        )

        # Learner1 should only see their own attempt
        token = create_auth_token(learner1, test_org.organization_id, UserRole.Learner)
        response = client.get(
            "/api/learners/me/attempts",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["attempts"][0]["assignment_id"] == str(assignment1.assignment_id)

    def test_includes_evaluation_info_for_evaluated_attempts(
        self,
        client: TestClient,
        db_session: Session,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
        attempt_factory: t.Callable[..., AssessmentAttempt],
        evaluation_factory: t.Callable[..., EvaluationResult],
    ) -> None:
        """Includes evaluation info for evaluated attempts."""
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
        attempt = attempt_factory(
            assignment_id=assignment.assignment_id,
            learner_id=learner.user_id,
            status=AttemptStatus.Completed,
        )

        # Transition to evaluated status and create evaluation
        with db_session.begin():
            attempt_storage.transition_to_evaluated(
                attempt.attempt_id,
                grade=Grade.A,
                confidence_score=decimal.Decimal("0.85"),
                session=db_session,
            )
        evaluation = evaluation_factory(
            attempt_id=attempt.attempt_id,
            strengths=["Good understanding"],
            gaps=["Needs more practice"],
            reasoning_summary="Overall good performance",
        )

        token = create_auth_token(learner, test_org.organization_id, UserRole.Learner)
        response = client.get(
            "/api/learners/me/attempts",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

        attempt_data = data["attempts"][0]
        assert attempt_data["status"] == "evaluated"
        assert attempt_data["has_evaluation"] is True
        assert attempt_data["evaluation_id"] == str(evaluation.evaluation_id)
        # Feedback should not be included for evaluated (only reviewed)
        assert attempt_data["feedback"] is None

    def test_includes_feedback_for_reviewed_attempts(
        self,
        client: TestClient,
        db_session: Session,
        test_org: Organization,
        user_factory: t.Callable[..., User],
        objective_factory: t.Callable[..., Objective],
        assignment_factory: t.Callable[..., Assignment],
        attempt_factory: t.Callable[..., AssessmentAttempt],
        evaluation_factory: t.Callable[..., EvaluationResult],
    ) -> None:
        """Includes feedback for reviewed attempts."""
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
        attempt = attempt_factory(
            assignment_id=assignment.assignment_id,
            learner_id=learner.user_id,
            status=AttemptStatus.Completed,
        )

        # Transition to evaluated and then reviewed
        with db_session.begin():
            attempt_storage.transition_to_evaluated(
                attempt.attempt_id,
                grade=Grade.S,
                confidence_score=decimal.Decimal("0.95"),
                session=db_session,
            )
        evaluation_factory(
            attempt_id=attempt.attempt_id,
            strengths=["Excellent understanding", "Clear explanations"],
            gaps=["Minor improvement area"],
            reasoning_summary="Outstanding performance with minor areas for growth",
        )
        with db_session.begin():
            attempt_storage.transition_to_reviewed(
                attempt.attempt_id,
                session=db_session,
            )

        token = create_auth_token(learner, test_org.organization_id, UserRole.Learner)
        response = client.get(
            "/api/learners/me/attempts",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

        attempt_data = data["attempts"][0]
        assert attempt_data["status"] == "reviewed"
        assert attempt_data["has_evaluation"] is True
        assert attempt_data["feedback"] is not None
        assert attempt_data["feedback"]["strengths"] == ["Excellent understanding", "Clear explanations"]
        assert attempt_data["feedback"]["gaps"] == ["Minor improvement area"]
        assert attempt_data["feedback"]["reasoning_summary"] == "Outstanding performance with minor areas for growth"

    def test_requires_authentication(
        self,
        client: TestClient,
    ) -> None:
        """Returns 401 when not authenticated."""
        response = client.get("/api/learners/me/attempts")
        assert response.status_code == 401

    def test_requires_learner_role(
        self,
        client: TestClient,
        test_org: Organization,
        user_factory: t.Callable[..., User],
    ) -> None:
        """Returns 403 when user is not a learner."""
        educator = user_factory(
            email="educator@test.com",
            name="Test Educator",
            organization_id=test_org.organization_id,
            role=UserRole.Educator,
        )

        token = create_auth_token(educator, test_org.organization_id, UserRole.Educator)
        response = client.get(
            "/api/learners/me/attempts",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
