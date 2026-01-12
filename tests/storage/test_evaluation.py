"""Tests for socratic.storage.evaluation module."""

from __future__ import annotations

import typing as t

import pytest
from sqlalchemy.orm import Session

from socratic.model import AssessmentAttempt, AssessmentFlag, Assignment, AttemptStatus, EvaluationResult, \
    EvaluationResultID, EvidenceMapping, Objective, Organization, RubricCriterionID, User, UserRole
from socratic.storage import evaluation as eval_storage


class TestGet(object):
    """Tests for eval_storage.get()."""

    def test_get_by_evaluation_id(
        self,
        db_session: Session,
        evaluation_factory: t.Callable[..., EvaluationResult],
    ) -> None:
        """get() with evaluation_id returns the evaluation."""
        evaluation = evaluation_factory()

        with db_session.begin():
            result = eval_storage.get(evaluation.evaluation_id, session=db_session)

        assert result is not None
        assert result.evaluation_id == evaluation.evaluation_id

    def test_get_by_attempt_id(
        self,
        db_session: Session,
        evaluation_factory: t.Callable[..., EvaluationResult],
        test_attempt: AssessmentAttempt,
    ) -> None:
        """get() with attempt_id returns the evaluation."""
        evaluation_factory()

        with db_session.begin():
            result = eval_storage.get(attempt_id=test_attempt.attempt_id, session=db_session)

        assert result is not None
        assert result.attempt_id == test_attempt.attempt_id

    def test_get_nonexistent_returns_none(self, db_session: Session) -> None:
        """get() returns None for nonexistent evaluation ID."""
        with db_session.begin():
            result = eval_storage.get(EvaluationResultID(), session=db_session)

        assert result is None


class TestFindPendingReview(object):
    """Tests for eval_storage.find_pending_review()."""

    def test_find_pending_review_returns_evaluated_attempts(
        self,
        db_session: Session,
        evaluation_factory: t.Callable[..., EvaluationResult],
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """find_pending_review() returns evaluations for evaluated attempts."""
        # Create attempt with Evaluated status
        attempt = attempt_factory(status=AttemptStatus.Evaluated)
        evaluation = evaluation_factory(attempt_id=attempt.attempt_id)

        with db_session.begin():
            result = eval_storage.find_pending_review(session=db_session)

        eval_ids = {e.evaluation_id for e in result}
        assert evaluation.evaluation_id in eval_ids


class TestCreate(object):
    """Tests for eval_storage.create()."""

    def test_create_evaluation(
        self,
        db_session: Session,
        test_attempt: AssessmentAttempt,
    ) -> None:
        """create() creates an evaluation with required fields."""
        with db_session.begin():
            evaluation = eval_storage.create(
                attempt_id=test_attempt.attempt_id,
                session=db_session,
            )

        assert evaluation.attempt_id == test_attempt.attempt_id
        assert evaluation.evaluation_id is not None

    def test_create_evaluation_with_optional_fields(
        self,
        db_session: Session,
        test_attempt: AssessmentAttempt,
    ) -> None:
        """create() accepts optional fields."""
        evidence_mappings = [
            EvidenceMapping(
                criterion_id=RubricCriterionID(),
                segment_ids=[],
                evidence_summary="Test evidence",
                strength="strong",
                failure_modes_detected=[],
            )
        ]
        flags = [AssessmentFlag.LowConfidence]
        strengths = ["Good understanding"]
        gaps = ["Needs practice"]
        reasoning_summary = "Overall good"

        with db_session.begin():
            evaluation = eval_storage.create(
                attempt_id=test_attempt.attempt_id,
                evidence_mappings=evidence_mappings,
                flags=flags,
                strengths=strengths,
                gaps=gaps,
                reasoning_summary=reasoning_summary,
                session=db_session,
            )

        assert evaluation.flags == flags
        assert evaluation.strengths == strengths
        assert evaluation.gaps == gaps
        assert evaluation.reasoning_summary == reasoning_summary

    def test_create_defaults(
        self,
        db_session: Session,
        test_attempt: AssessmentAttempt,
    ) -> None:
        """create() uses sensible defaults for optional fields."""
        with db_session.begin():
            evaluation = eval_storage.create(
                attempt_id=test_attempt.attempt_id,
                session=db_session,
            )

        assert evaluation.evidence_mappings == []
        assert evaluation.flags == []
        assert evaluation.strengths == []
        assert evaluation.gaps == []
        assert evaluation.reasoning_summary is None


@pytest.fixture
def test_educator(
    user_factory: t.Callable[..., User],
    test_org: Organization,
) -> User:
    """Provide a test educator user."""
    return user_factory(
        email="educator@test.com",
        name="Test Educator",
        password="password123",
        organization_id=test_org.organization_id,
        role=UserRole.Educator,
    )


@pytest.fixture
def test_learner(
    user_factory: t.Callable[..., User],
    test_org: Organization,
) -> User:
    """Provide a test learner user."""
    return user_factory(
        email="learner@test.com",
        name="Test Learner",
        password="password123",
        organization_id=test_org.organization_id,
        role=UserRole.Learner,
    )


@pytest.fixture
def test_objective(
    db_session: Session,
    test_org: Organization,
    test_educator: User,
) -> Objective:
    """Provide a test objective."""
    from socratic.storage import objective as obj_storage

    with db_session.begin():
        obj = obj_storage.create(
            organization_id=test_org.organization_id,
            created_by=test_educator.user_id,
            title="Test Objective",
            description="A test objective",
            session=db_session,
        )
        return obj


@pytest.fixture
def test_assignment(
    db_session: Session,
    test_org: Organization,
    test_educator: User,
    test_learner: User,
    test_objective: Objective,
) -> Assignment:
    """Provide a test assignment."""
    from socratic.storage import assignment as assignment_storage

    with db_session.begin():
        assignment = assignment_storage.create(
            organization_id=test_org.organization_id,
            objective_id=test_objective.objective_id,
            assigned_by=test_educator.user_id,
            assigned_to=test_learner.user_id,
            session=db_session,
        )
        return assignment


@pytest.fixture
def test_attempt(
    db_session: Session,
    test_assignment: Assignment,
    test_learner: User,
) -> AssessmentAttempt:
    """Provide a test attempt."""
    from socratic.storage import attempt as attempt_storage

    with db_session.begin():
        attempt = attempt_storage.create(
            assignment_id=test_assignment.assignment_id,
            learner_id=test_learner.user_id,
            status=AttemptStatus.Completed,
            session=db_session,
        )
        return attempt


@pytest.fixture
def attempt_factory(
    db_session: Session,
    test_assignment: Assignment,
    test_learner: User,
) -> t.Callable[..., AssessmentAttempt]:
    """Factory fixture for creating test attempts."""
    from socratic.storage import attempt as attempt_storage

    def create_attempt(
        status: AttemptStatus = AttemptStatus.Completed,
    ) -> AssessmentAttempt:
        with db_session.begin():
            attempt = attempt_storage.create(
                assignment_id=test_assignment.assignment_id,
                learner_id=test_learner.user_id,
                status=status,
                session=db_session,
            )
            return attempt

    return create_attempt


@pytest.fixture
def evaluation_factory(
    db_session: Session,
    test_attempt: AssessmentAttempt,
) -> t.Callable[..., EvaluationResult]:
    """Factory fixture for creating test evaluations."""

    def create_evaluation(
        attempt_id: t.Any = None,
        evidence_mappings: list[EvidenceMapping] | None = None,
        flags: list[AssessmentFlag] | None = None,
        strengths: list[str] | None = None,
        gaps: list[str] | None = None,
        reasoning_summary: str | None = None,
    ) -> EvaluationResult:
        with db_session.begin():
            evaluation = eval_storage.create(
                attempt_id=attempt_id or test_attempt.attempt_id,
                evidence_mappings=evidence_mappings,
                flags=flags,
                strengths=strengths,
                gaps=gaps,
                reasoning_summary=reasoning_summary,
                session=db_session,
            )
            return evaluation

    return create_evaluation
