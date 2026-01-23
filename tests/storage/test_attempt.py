"""Tests for socratic.storage.attempt module."""

from __future__ import annotations

import datetime
import decimal
import typing as t

import pytest
from sqlalchemy.orm import Session

from socratic.model import AssessmentAttempt, Assignment, AttemptID, AttemptStatus, Grade, Objective, Organization, \
    User, UserRole
from socratic.storage import attempt as attempt_storage


class TestGet(object):
    """Tests for attempt_storage.get()."""

    def test_get_by_attempt_id(
        self,
        db_session: Session,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """get() with attempt_id returns the attempt."""
        attempt = attempt_factory()

        with db_session.begin():
            result = attempt_storage.get(attempt.attempt_id, session=db_session)

        assert result is not None
        assert result.attempt_id == attempt.attempt_id

    def test_get_positional_pk(
        self,
        db_session: Session,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """get() accepts attempt_id as positional argument."""
        attempt = attempt_factory()

        with db_session.begin():
            result = attempt_storage.get(attempt.attempt_id, session=db_session)

        assert result is not None
        assert result.attempt_id == attempt.attempt_id

    def test_get_nonexistent_returns_none(self, db_session: Session) -> None:
        """get() returns None for nonexistent attempt ID."""
        with db_session.begin():
            result = attempt_storage.get(AttemptID(), session=db_session)

        assert result is None


class TestFind(object):
    """Tests for attempt_storage.find()."""

    def test_find_all(
        self,
        db_session: Session,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """find() returns all attempts when no filters provided."""
        a1 = attempt_factory()
        a2 = attempt_factory()

        with db_session.begin():
            result = attempt_storage.find(session=db_session)

        ids = {a.attempt_id for a in result}
        assert a1.attempt_id in ids
        assert a2.attempt_id in ids

    def test_find_by_assignment_id(
        self,
        db_session: Session,
        attempt_factory: t.Callable[..., AssessmentAttempt],
        test_assignment: Assignment,
        assignment_factory: t.Callable[..., Assignment],
    ) -> None:
        """find() filters by assignment_id."""
        other_assignment = assignment_factory()
        a1 = attempt_factory()
        a2 = attempt_factory(assignment_id=other_assignment.assignment_id)

        with db_session.begin():
            result = attempt_storage.find(assignment_id=test_assignment.assignment_id, session=db_session)

        ids = {a.attempt_id for a in result}
        assert a1.attempt_id in ids
        assert a2.attempt_id not in ids

    def test_find_by_status(
        self,
        db_session: Session,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """find() filters by status."""
        a1 = attempt_factory(status=AttemptStatus.NotStarted)
        a2 = attempt_factory(status=AttemptStatus.InProgress)

        with db_session.begin():
            result = attempt_storage.find(status=AttemptStatus.InProgress, session=db_session)

        ids = {a.attempt_id for a in result}
        assert a2.attempt_id in ids
        assert a1.attempt_id not in ids


class TestCreate(object):
    """Tests for attempt_storage.create()."""

    def test_create_attempt(
        self,
        db_session: Session,
        test_assignment: Assignment,
        test_learner: User,
    ) -> None:
        """create() creates an attempt with required fields."""
        with db_session.begin():
            attempt = attempt_storage.create(
                assignment_id=test_assignment.assignment_id,
                learner_id=test_learner.user_id,
                session=db_session,
            )

        assert attempt.assignment_id == test_assignment.assignment_id
        assert attempt.learner_id == test_learner.user_id
        assert attempt.attempt_id is not None
        assert attempt.create_time is not None

    def test_create_attempt_with_status(
        self,
        db_session: Session,
        test_assignment: Assignment,
        test_learner: User,
    ) -> None:
        """create() accepts status parameter."""
        with db_session.begin():
            attempt = attempt_storage.create(
                assignment_id=test_assignment.assignment_id,
                learner_id=test_learner.user_id,
                status=AttemptStatus.InProgress,
                session=db_session,
            )

        assert attempt.status == AttemptStatus.InProgress

    def test_create_defaults(
        self,
        db_session: Session,
        test_assignment: Assignment,
        test_learner: User,
    ) -> None:
        """create() uses sensible defaults for optional fields."""
        with db_session.begin():
            attempt = attempt_storage.create(
                assignment_id=test_assignment.assignment_id,
                learner_id=test_learner.user_id,
                session=db_session,
            )

        assert attempt.status == AttemptStatus.NotStarted
        assert attempt.started_at is not None  # Defaults to NOW() per migration
        assert attempt.completed_at is None
        assert attempt.grade is None
        assert attempt.confidence_score is None


class TestUpdate(object):
    """Tests for attempt_storage.update()."""

    def test_update_status(
        self,
        db_session: Session,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """update() can change status."""
        attempt = attempt_factory(status=AttemptStatus.NotStarted)

        with db_session.begin():
            attempt_storage.update(attempt.attempt_id, status=AttemptStatus.InProgress, session=db_session)

            updated = attempt_storage.get(attempt.attempt_id, session=db_session)

        assert updated is not None
        assert updated.status == AttemptStatus.InProgress

    def test_update_grade(
        self,
        db_session: Session,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """update() can set grade."""
        attempt = attempt_factory(status=AttemptStatus.Completed)

        with db_session.begin():
            attempt_storage.update(attempt.attempt_id, grade=Grade.A, session=db_session)

            updated = attempt_storage.get(attempt.attempt_id, session=db_session)

        assert updated is not None
        assert updated.grade == Grade.A

    def test_update_nullable_field_to_none(
        self,
        db_session: Session,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """update() can set nullable fields to None."""
        attempt = attempt_factory()

        # First set a value
        with db_session.begin():
            attempt_storage.update(attempt.attempt_id, grade=Grade.C, session=db_session)

        # Then set it to None
        with db_session.begin():
            attempt_storage.update(attempt.attempt_id, grade=None, session=db_session)

            updated = attempt_storage.get(attempt.attempt_id, session=db_session)

        assert updated is not None
        assert updated.grade is None

    def test_update_multiple_fields(
        self,
        db_session: Session,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """update() can change multiple fields at once."""
        attempt = attempt_factory()
        now = datetime.datetime.now(datetime.UTC)

        with db_session.begin():
            attempt_storage.update(
                attempt.attempt_id,
                status=AttemptStatus.Completed,
                completed_at=now,
                grade=Grade.A,
                confidence_score=decimal.Decimal("0.95"),
                session=db_session,
            )

            updated = attempt_storage.get(attempt.attempt_id, session=db_session)

        assert updated is not None
        assert updated.status == AttemptStatus.Completed
        assert updated.completed_at is not None
        assert updated.grade == Grade.A
        assert updated.confidence_score == decimal.Decimal("0.95")

    def test_update_nonexistent_raises_keyerror(self, db_session: Session) -> None:
        """update() raises KeyError for nonexistent attempt."""
        with db_session.begin():
            with pytest.raises(KeyError):
                attempt_storage.update(AttemptID(), status=AttemptStatus.InProgress, session=db_session)


class TestTransitionToEvaluated(object):
    """Tests for attempt_storage.transition_to_evaluated()."""

    def test_transition_from_completed(
        self,
        db_session: Session,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """transition_to_evaluated() transitions from Completed to Evaluated."""
        attempt = attempt_factory(status=AttemptStatus.Completed)

        with db_session.begin():
            updated = attempt_storage.transition_to_evaluated(
                attempt.attempt_id,
                grade=Grade.C,
                confidence_score=decimal.Decimal("0.85"),
                session=db_session,
            )

        assert updated.status == AttemptStatus.Evaluated
        assert updated.grade == Grade.C
        assert updated.confidence_score == decimal.Decimal("0.85")

    def test_transition_from_wrong_status_raises_valueerror(
        self,
        db_session: Session,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """transition_to_evaluated() raises ValueError for wrong status."""
        attempt = attempt_factory(status=AttemptStatus.InProgress)

        with db_session.begin():
            with pytest.raises(ValueError, match="Cannot evaluate attempt"):
                attempt_storage.transition_to_evaluated(
                    attempt.attempt_id,
                    grade=Grade.A,
                    confidence_score=decimal.Decimal("0.9"),
                    session=db_session,
                )

    def test_transition_nonexistent_raises_keyerror(self, db_session: Session) -> None:
        """transition_to_evaluated() raises KeyError for nonexistent attempt."""
        with db_session.begin():
            with pytest.raises(KeyError):
                attempt_storage.transition_to_evaluated(
                    AttemptID(),
                    grade=Grade.A,
                    confidence_score=decimal.Decimal("0.9"),
                    session=db_session,
                )


class TestTransitionToReviewed(object):
    """Tests for attempt_storage.transition_to_reviewed()."""

    def test_transition_from_evaluated(
        self,
        db_session: Session,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """transition_to_reviewed() transitions from Evaluated to Reviewed."""
        attempt = attempt_factory(status=AttemptStatus.Evaluated)

        with db_session.begin():
            updated = attempt_storage.transition_to_reviewed(attempt.attempt_id, session=db_session)

        assert updated.status == AttemptStatus.Reviewed

    def test_transition_with_grade_override(
        self,
        db_session: Session,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """transition_to_reviewed() can override the grade."""
        attempt = attempt_factory(status=AttemptStatus.Evaluated)
        # Set initial grade
        with db_session.begin():
            attempt_storage.update(attempt.attempt_id, grade=Grade.C, session=db_session)

        with db_session.begin():
            updated = attempt_storage.transition_to_reviewed(
                attempt.attempt_id, grade_override=Grade.C, session=db_session
            )

        assert updated.status == AttemptStatus.Reviewed
        assert updated.grade == Grade.C

    def test_transition_from_wrong_status_raises_valueerror(
        self,
        db_session: Session,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """transition_to_reviewed() raises ValueError for wrong status."""
        attempt = attempt_factory(status=AttemptStatus.Completed)

        with db_session.begin():
            with pytest.raises(ValueError, match="Cannot review attempt"):
                attempt_storage.transition_to_reviewed(attempt.attempt_id, session=db_session)

    def test_transition_nonexistent_raises_keyerror(self, db_session: Session) -> None:
        """transition_to_reviewed() raises KeyError for nonexistent attempt."""
        with db_session.begin():
            with pytest.raises(KeyError):
                attempt_storage.transition_to_reviewed(AttemptID(), session=db_session)


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
def assignment_factory(
    db_session: Session,
    test_org: Organization,
    test_educator: User,
    test_learner: User,
    test_objective: Objective,
) -> t.Callable[..., Assignment]:
    """Factory fixture for creating test assignments."""
    from socratic.storage import assignment as assignment_storage

    def create_assignment() -> Assignment:
        with db_session.begin():
            assignment = assignment_storage.create(
                organization_id=test_org.organization_id,
                objective_id=test_objective.objective_id,
                assigned_by=test_educator.user_id,
                assigned_to=test_learner.user_id,
                session=db_session,
            )
            return assignment

    return create_assignment


@pytest.fixture
def attempt_factory(
    db_session: Session,
    test_assignment: Assignment,
    test_learner: User,
) -> t.Callable[..., AssessmentAttempt]:
    """Factory fixture for creating test attempts."""

    def create_attempt(
        assignment_id: t.Any = None,
        learner_id: t.Any = None,
        status: AttemptStatus = AttemptStatus.NotStarted,
    ) -> AssessmentAttempt:
        with db_session.begin():
            attempt = attempt_storage.create(
                assignment_id=assignment_id or test_assignment.assignment_id,
                learner_id=learner_id or test_learner.user_id,
                status=status,
                session=db_session,
            )
            return attempt

    return create_attempt
