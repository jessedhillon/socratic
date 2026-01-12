"""Tests for socratic.storage.override module."""

from __future__ import annotations

import typing as t

import pytest
from sqlalchemy.orm import Session

from socratic.model import AssessmentAttempt, Assignment, AttemptStatus, EducatorOverride, Grade, Objective, \
    Organization, OverrideID, User, UserRole
from socratic.storage import override as override_storage


class TestGet(object):
    """Tests for override_storage.get()."""

    def test_get_by_override_id(
        self,
        db_session: Session,
        override_factory: t.Callable[..., EducatorOverride],
    ) -> None:
        """get() with override_id returns the override."""
        override = override_factory()

        with db_session.begin():
            result = override_storage.get(override.override_id, session=db_session)

        assert result is not None
        assert result.override_id == override.override_id

    def test_get_positional_pk(
        self,
        db_session: Session,
        override_factory: t.Callable[..., EducatorOverride],
    ) -> None:
        """get() accepts override_id as positional argument."""
        override = override_factory(reason="Positional Test")

        with db_session.begin():
            result = override_storage.get(override.override_id, session=db_session)

        assert result is not None
        assert result.reason == "Positional Test"

    def test_get_nonexistent_returns_none(self, db_session: Session) -> None:
        """get() returns None for nonexistent override ID."""
        with db_session.begin():
            result = override_storage.get(OverrideID(), session=db_session)

        assert result is None


class TestFind(object):
    """Tests for override_storage.find()."""

    def test_find_all(
        self,
        db_session: Session,
        override_factory: t.Callable[..., EducatorOverride],
    ) -> None:
        """find() returns all overrides when no filters provided."""
        override1 = override_factory(reason="Override 1")
        override2 = override_factory(reason="Override 2")

        with db_session.begin():
            result = override_storage.find(session=db_session)

        ids = {o.override_id for o in result}
        assert override1.override_id in ids
        assert override2.override_id in ids

    def test_find_by_attempt_id(
        self,
        db_session: Session,
        override_factory: t.Callable[..., EducatorOverride],
        test_attempt: AssessmentAttempt,
        attempt_factory: t.Callable[..., AssessmentAttempt],
    ) -> None:
        """find() filters by attempt_id."""
        other_attempt = attempt_factory()
        override1 = override_factory(reason="Attempt 1 Override")
        override2 = override_factory(
            reason="Attempt 2 Override",
            attempt_id=other_attempt.attempt_id,
        )

        with db_session.begin():
            result = override_storage.find(
                attempt_id=test_attempt.attempt_id,
                session=db_session,
            )

        ids = {o.override_id for o in result}
        assert override1.override_id in ids
        assert override2.override_id not in ids

    def test_find_by_educator_id(
        self,
        db_session: Session,
        override_factory: t.Callable[..., EducatorOverride],
        test_educator: User,
        user_factory: t.Callable[..., User],
        test_org: Organization,
    ) -> None:
        """find() filters by educator_id."""
        other_educator = user_factory(
            email="educator2@test.com",
            name="Other Educator",
            password="password123",
            organization_id=test_org.organization_id,
            role=UserRole.Educator,
        )
        override1 = override_factory(reason="Educator 1 Override")
        override2 = override_factory(
            reason="Educator 2 Override",
            educator_id=other_educator.user_id,
        )

        with db_session.begin():
            result = override_storage.find(
                educator_id=test_educator.user_id,
                session=db_session,
            )

        ids = {o.override_id for o in result}
        assert override1.override_id in ids
        assert override2.override_id not in ids


class TestCreate(object):
    """Tests for override_storage.create()."""

    def test_create_override(
        self,
        db_session: Session,
        test_attempt: AssessmentAttempt,
        test_educator: User,
    ) -> None:
        """create() creates an override with required fields."""
        with db_session.begin():
            override = override_storage.create(
                attempt_id=test_attempt.attempt_id,
                educator_id=test_educator.user_id,
                new_grade=Grade.A,
                reason="Student showed improvement",
                session=db_session,
            )

        assert override.attempt_id == test_attempt.attempt_id
        assert override.educator_id == test_educator.user_id
        assert override.new_grade == Grade.A
        assert override.reason == "Student showed improvement"
        assert override.override_id is not None

    def test_create_override_with_optional_fields(
        self,
        db_session: Session,
        test_attempt: AssessmentAttempt,
        test_educator: User,
    ) -> None:
        """create() accepts optional fields."""
        with db_session.begin():
            override = override_storage.create(
                attempt_id=test_attempt.attempt_id,
                educator_id=test_educator.user_id,
                new_grade=Grade.S,
                reason="Exceptional work",
                original_grade=Grade.C,
                feedback="Great improvement from the original grade",
                session=db_session,
            )

        assert override.original_grade == Grade.C
        assert override.feedback == "Great improvement from the original grade"

    def test_create_defaults(
        self,
        db_session: Session,
        test_attempt: AssessmentAttempt,
        test_educator: User,
    ) -> None:
        """create() uses sensible defaults for optional fields."""
        with db_session.begin():
            override = override_storage.create(
                attempt_id=test_attempt.attempt_id,
                educator_id=test_educator.user_id,
                new_grade=Grade.A,
                reason="Standard override",
                session=db_session,
            )

        assert override.original_grade is None
        assert override.feedback is None


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
def override_factory(
    db_session: Session,
    test_attempt: AssessmentAttempt,
    test_educator: User,
) -> t.Callable[..., EducatorOverride]:
    """Factory fixture for creating test overrides."""

    def create_override(
        attempt_id: t.Any = None,
        educator_id: t.Any = None,
        new_grade: Grade = Grade.A,
        reason: str = "Test override",
        original_grade: Grade | None = None,
        feedback: str | None = None,
    ) -> EducatorOverride:
        with db_session.begin():
            override = override_storage.create(
                attempt_id=attempt_id or test_attempt.attempt_id,
                educator_id=educator_id or test_educator.user_id,
                new_grade=new_grade,
                reason=reason,
                original_grade=original_grade,
                feedback=feedback,
                session=db_session,
            )
            return override

    return create_override
