"""Tests for socratic.storage.assignment module."""

from __future__ import annotations

import datetime
import typing as t

import pytest
from sqlalchemy.orm import Session

from socratic.model import Assignment, AssignmentID, Objective, Organization, RetakePolicy, User, UserRole
from socratic.storage import assignment as assignment_storage


class TestGet(object):
    """Tests for assignment_storage.get()."""

    def test_get_by_assignment_id(
        self,
        db_session: Session,
        assignment_factory: t.Callable[..., Assignment],
    ) -> None:
        """get() with assignment_id returns the assignment."""
        assignment = assignment_factory()

        with db_session.begin():
            result = assignment_storage.get(assignment.assignment_id, session=db_session)

        assert result is not None
        assert result.assignment_id == assignment.assignment_id

    def test_get_positional_pk(
        self,
        db_session: Session,
        assignment_factory: t.Callable[..., Assignment],
    ) -> None:
        """get() accepts assignment_id as positional argument."""
        assignment = assignment_factory()

        with db_session.begin():
            result = assignment_storage.get(assignment.assignment_id, session=db_session)

        assert result is not None
        assert result.assignment_id == assignment.assignment_id

    def test_get_nonexistent_returns_none(self, db_session: Session) -> None:
        """get() returns None for nonexistent assignment ID."""
        with db_session.begin():
            result = assignment_storage.get(AssignmentID(), session=db_session)

        assert result is None


class TestFind(object):
    """Tests for assignment_storage.find()."""

    def test_find_all(
        self,
        db_session: Session,
        assignment_factory: t.Callable[..., Assignment],
    ) -> None:
        """find() returns all assignments when no filters provided."""
        a1 = assignment_factory()
        a2 = assignment_factory()

        with db_session.begin():
            result = assignment_storage.find(session=db_session)

        ids = {a.assignment_id for a in result}
        assert a1.assignment_id in ids
        assert a2.assignment_id in ids

    def test_find_by_organization_id(
        self,
        db_session: Session,
        assignment_factory: t.Callable[..., Assignment],
        test_org: Organization,
        org_factory: t.Callable[..., Organization],
    ) -> None:
        """find() filters by organization_id."""
        other_org = org_factory(name="Other Org")
        a1 = assignment_factory()
        a2 = assignment_factory(organization_id=other_org.organization_id)

        with db_session.begin():
            result = assignment_storage.find(organization_id=test_org.organization_id, session=db_session)

        ids = {a.assignment_id for a in result}
        assert a1.assignment_id in ids
        assert a2.assignment_id not in ids

    def test_find_by_assigned_to(
        self,
        db_session: Session,
        assignment_factory: t.Callable[..., Assignment],
        test_learner: User,
        user_factory: t.Callable[..., User],
        test_org: Organization,
    ) -> None:
        """find() filters by assigned_to."""
        other_learner = user_factory(
            email="other@test.com",
            organization_id=test_org.organization_id,
            role=UserRole.Learner,
        )
        a1 = assignment_factory()
        a2 = assignment_factory(assigned_to=other_learner.user_id)

        with db_session.begin():
            result = assignment_storage.find(assigned_to=test_learner.user_id, session=db_session)

        ids = {a.assignment_id for a in result}
        assert a1.assignment_id in ids
        assert a2.assignment_id not in ids


class TestCreate(object):
    """Tests for assignment_storage.create()."""

    def test_create_assignment(
        self,
        db_session: Session,
        test_org: Organization,
        test_educator: User,
        test_learner: User,
        test_objective: Objective,
    ) -> None:
        """create() creates an assignment with required fields."""
        with db_session.begin():
            assignment = assignment_storage.create(
                organization_id=test_org.organization_id,
                objective_id=test_objective.objective_id,
                assigned_by=test_educator.user_id,
                assigned_to=test_learner.user_id,
                session=db_session,
            )

        assert assignment.organization_id == test_org.organization_id
        assert assignment.objective_id == test_objective.objective_id
        assert assignment.assigned_by == test_educator.user_id
        assert assignment.assigned_to == test_learner.user_id
        assert assignment.assignment_id is not None
        assert assignment.create_time is not None

    def test_create_assignment_with_optional_fields(
        self,
        db_session: Session,
        test_org: Organization,
        test_educator: User,
        test_learner: User,
        test_objective: Objective,
    ) -> None:
        """create() accepts optional fields."""
        available_from = datetime.datetime.now(datetime.UTC)
        available_until = available_from + datetime.timedelta(days=7)

        with db_session.begin():
            assignment = assignment_storage.create(
                organization_id=test_org.organization_id,
                objective_id=test_objective.objective_id,
                assigned_by=test_educator.user_id,
                assigned_to=test_learner.user_id,
                available_from=available_from,
                available_until=available_until,
                max_attempts=3,
                retake_policy=RetakePolicy.Delayed,
                retake_delay_hours=24,
                session=db_session,
            )

        # Compare with timezone stripped (database stores without tz)
        assert assignment.available_from is not None
        assert assignment.available_until is not None
        assert assignment.max_attempts == 3
        assert assignment.retake_policy == RetakePolicy.Delayed
        assert assignment.retake_delay_hours == 24

    def test_create_defaults(
        self,
        db_session: Session,
        test_org: Organization,
        test_educator: User,
        test_learner: User,
        test_objective: Objective,
    ) -> None:
        """create() uses sensible defaults for optional fields."""
        with db_session.begin():
            assignment = assignment_storage.create(
                organization_id=test_org.organization_id,
                objective_id=test_objective.objective_id,
                assigned_by=test_educator.user_id,
                assigned_to=test_learner.user_id,
                session=db_session,
            )

        assert assignment.available_from is None
        assert assignment.available_until is None
        assert assignment.max_attempts == 1
        assert assignment.retake_policy == RetakePolicy.None_
        assert assignment.retake_delay_hours is None


class TestUpdate(object):
    """Tests for assignment_storage.update()."""

    def test_update_max_attempts(
        self,
        db_session: Session,
        assignment_factory: t.Callable[..., Assignment],
    ) -> None:
        """update() can change max_attempts."""
        assignment = assignment_factory(max_attempts=1)

        with db_session.begin():
            updated = assignment_storage.update(assignment.assignment_id, max_attempts=5, session=db_session)

        assert updated.max_attempts == 5

    def test_update_retake_policy(
        self,
        db_session: Session,
        assignment_factory: t.Callable[..., Assignment],
    ) -> None:
        """update() can change retake_policy."""
        assignment = assignment_factory(retake_policy=RetakePolicy.None_)

        with db_session.begin():
            updated = assignment_storage.update(
                assignment.assignment_id, retake_policy=RetakePolicy.Immediate, session=db_session
            )

        assert updated.retake_policy == RetakePolicy.Immediate

    def test_update_nullable_field_to_none(
        self,
        db_session: Session,
        assignment_factory: t.Callable[..., Assignment],
    ) -> None:
        """update() can set nullable fields to None."""
        assignment = assignment_factory(retake_delay_hours=24)

        with db_session.begin():
            updated = assignment_storage.update(assignment.assignment_id, retake_delay_hours=None, session=db_session)

        assert updated.retake_delay_hours is None

    def test_update_multiple_fields(
        self,
        db_session: Session,
        assignment_factory: t.Callable[..., Assignment],
    ) -> None:
        """update() can change multiple fields at once."""
        assignment = assignment_factory()

        with db_session.begin():
            updated = assignment_storage.update(
                assignment.assignment_id,
                max_attempts=10,
                retake_policy=RetakePolicy.Delayed,
                retake_delay_hours=48,
                session=db_session,
            )

        assert updated.max_attempts == 10
        assert updated.retake_policy == RetakePolicy.Delayed
        assert updated.retake_delay_hours == 48

    def test_update_nonexistent_raises_keyerror(self, db_session: Session) -> None:
        """update() raises KeyError for nonexistent assignment."""
        with db_session.begin():
            with pytest.raises(KeyError):
                assignment_storage.update(AssignmentID(), max_attempts=5, session=db_session)


class TestDelete(object):
    """Tests for assignment_storage.delete()."""

    def test_delete_existing(
        self,
        db_session: Session,
        assignment_factory: t.Callable[..., Assignment],
    ) -> None:
        """delete() removes an existing assignment and returns True."""
        assignment = assignment_factory()

        with db_session.begin():
            result = assignment_storage.delete(assignment.assignment_id, session=db_session)

        assert result is True

        with db_session.begin():
            fetched = assignment_storage.get(assignment.assignment_id, session=db_session)
        assert fetched is None

    def test_delete_nonexistent_returns_false(self, db_session: Session) -> None:
        """delete() returns False for nonexistent assignment."""
        with db_session.begin():
            result = assignment_storage.delete(AssignmentID(), session=db_session)

        assert result is False


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
def assignment_factory(
    db_session: Session,
    test_org: Organization,
    test_educator: User,
    test_learner: User,
    test_objective: Objective,
) -> t.Callable[..., Assignment]:
    """Factory fixture for creating test assignments."""

    def create_assignment(
        organization_id: t.Any = None,
        objective_id: t.Any = None,
        assigned_by: t.Any = None,
        assigned_to: t.Any = None,
        available_from: datetime.datetime | None = None,
        available_until: datetime.datetime | None = None,
        max_attempts: int = 1,
        retake_policy: RetakePolicy = RetakePolicy.None_,
        retake_delay_hours: int | None = None,
    ) -> Assignment:
        with db_session.begin():
            assignment = assignment_storage.create(
                organization_id=organization_id or test_org.organization_id,
                objective_id=objective_id or test_objective.objective_id,
                assigned_by=assigned_by or test_educator.user_id,
                assigned_to=assigned_to or test_learner.user_id,
                available_from=available_from,
                available_until=available_until,
                max_attempts=max_attempts,
                retake_policy=retake_policy,
                retake_delay_hours=retake_delay_hours,
                session=db_session,
            )
            return assignment

    return create_assignment
