"""Tests for socratic.storage.objective module."""

from __future__ import annotations

import typing as t

import pytest
from sqlalchemy.orm import Session

from socratic.model import ExtensionPolicy, Objective, ObjectiveID, ObjectiveStatus, Organization, User, UserRole
from socratic.storage import objective as obj_storage


class TestGet(object):
    """Tests for obj_storage.get()."""

    def test_get_by_objective_id(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """get() with objective_id returns the objective."""
        obj = objective_factory(title="Test Objective")

        with db_session.begin():
            result = obj_storage.get(obj.objective_id, session=db_session)

        assert result is not None
        assert result.objective_id == obj.objective_id
        assert result.title == "Test Objective"

    def test_get_positional_pk(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """get() accepts objective_id as positional argument."""
        obj = objective_factory(title="Positional Test")

        with db_session.begin():
            result = obj_storage.get(obj.objective_id, session=db_session)

        assert result is not None
        assert result.title == "Positional Test"

    def test_get_nonexistent_returns_none(self, db_session: Session) -> None:
        """get() returns None for nonexistent objective ID."""
        with db_session.begin():
            result = obj_storage.get(ObjectiveID(), session=db_session)

        assert result is None


class TestFind(object):
    """Tests for obj_storage.find()."""

    def test_find_all(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """find() returns all objectives when no filters provided."""
        obj1 = objective_factory(title="Objective 1")
        obj2 = objective_factory(title="Objective 2")

        with db_session.begin():
            result = obj_storage.find(session=db_session)

        obj_ids = {o.objective_id for o in result}
        assert obj1.objective_id in obj_ids
        assert obj2.objective_id in obj_ids

    def test_find_by_organization_id(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
        test_org: Organization,
        org_factory: t.Callable[..., Organization],
    ) -> None:
        """find() filters by organization_id."""
        other_org = org_factory(name="Other Org")
        obj1 = objective_factory(title="Org 1 Objective")
        obj2 = objective_factory(title="Org 2 Objective", organization_id=other_org.organization_id)

        with db_session.begin():
            result = obj_storage.find(organization_id=test_org.organization_id, session=db_session)

        obj_ids = {o.objective_id for o in result}
        assert obj1.objective_id in obj_ids
        assert obj2.objective_id not in obj_ids

    def test_find_by_status(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """find() filters by status."""
        obj1 = objective_factory(title="Draft", status=ObjectiveStatus.Draft)
        obj2 = objective_factory(title="Published", status=ObjectiveStatus.Published)

        with db_session.begin():
            result = obj_storage.find(status=ObjectiveStatus.Published, session=db_session)

        obj_ids = {o.objective_id for o in result}
        assert obj2.objective_id in obj_ids
        assert obj1.objective_id not in obj_ids


class TestCreate(object):
    """Tests for obj_storage.create()."""

    def test_create_objective(
        self,
        db_session: Session,
        test_org: Organization,
        test_educator: User,
    ) -> None:
        """create() creates an objective with required fields."""
        with db_session.begin():
            obj = obj_storage.create(
                organization_id=test_org.organization_id,
                created_by=test_educator.user_id,
                title="New Objective",
                description="A test objective",
                session=db_session,
            )

        assert obj.title == "New Objective"
        assert obj.description == "A test objective"
        assert obj.organization_id == test_org.organization_id
        assert obj.created_by == test_educator.user_id
        assert obj.objective_id is not None
        assert obj.create_time is not None

    def test_create_objective_with_optional_fields(
        self,
        db_session: Session,
        test_org: Organization,
        test_educator: User,
    ) -> None:
        """create() accepts optional fields."""
        with db_session.begin():
            obj = obj_storage.create(
                organization_id=test_org.organization_id,
                created_by=test_educator.user_id,
                title="Full Objective",
                description="Complete description",
                scope_boundaries="Some boundaries",
                time_expectation_minutes=30,
                initial_prompts=["prompt1", "prompt2"],
                challenge_prompts=["challenge1"],
                extension_policy=ExtensionPolicy.Allowed,
                status=ObjectiveStatus.Published,
                session=db_session,
            )

        assert obj.scope_boundaries == "Some boundaries"
        assert obj.time_expectation_minutes == 30
        assert obj.initial_prompts == ["prompt1", "prompt2"]
        assert obj.challenge_prompts == ["challenge1"]
        assert obj.extension_policy == ExtensionPolicy.Allowed
        assert obj.status == ObjectiveStatus.Published

    def test_create_defaults(
        self,
        db_session: Session,
        test_org: Organization,
        test_educator: User,
    ) -> None:
        """create() uses sensible defaults for optional fields."""
        with db_session.begin():
            obj = obj_storage.create(
                organization_id=test_org.organization_id,
                created_by=test_educator.user_id,
                title="Minimal Objective",
                description="Minimal description",
                session=db_session,
            )

        assert obj.scope_boundaries is None
        assert obj.time_expectation_minutes is None
        assert obj.initial_prompts == []
        assert obj.challenge_prompts == []
        assert obj.extension_policy == ExtensionPolicy.Disallowed
        assert obj.status == ObjectiveStatus.Draft


class TestUpdate(object):
    """Tests for obj_storage.update()."""

    def test_update_title(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """update() can change objective title."""
        obj = objective_factory(title="Old Title")

        with db_session.begin():
            obj_storage.update(obj.objective_id, title="New Title", session=db_session)

            updated = obj_storage.get(obj.objective_id, session=db_session)

        assert updated is not None
        assert updated.title == "New Title"
        assert updated.description == obj.description  # unchanged

    def test_update_description(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """update() can change objective description."""
        obj = objective_factory(description="Old description")

        with db_session.begin():
            obj_storage.update(obj.objective_id, description="New description", session=db_session)

            updated = obj_storage.get(obj.objective_id, session=db_session)

        assert updated is not None
        assert updated.description == "New description"

    def test_update_status(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """update() can change objective status."""
        obj = objective_factory(status=ObjectiveStatus.Draft)

        with db_session.begin():
            obj_storage.update(obj.objective_id, status=ObjectiveStatus.Published, session=db_session)

            updated = obj_storage.get(obj.objective_id, session=db_session)

        assert updated is not None
        assert updated.status == ObjectiveStatus.Published

    def test_update_nullable_field_to_none(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """update() can set nullable fields to None."""
        obj = objective_factory(scope_boundaries="Some boundaries")

        with db_session.begin():
            obj_storage.update(obj.objective_id, scope_boundaries=None, session=db_session)

            updated = obj_storage.get(obj.objective_id, session=db_session)

        assert updated is not None
        assert updated.scope_boundaries is None

    def test_update_multiple_fields(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """update() can change multiple fields at once."""
        obj = objective_factory(title="Old", description="Old desc")

        with db_session.begin():
            obj_storage.update(
                obj.objective_id,
                title="New",
                description="New desc",
                status=ObjectiveStatus.Published,
                session=db_session,
            )

            updated = obj_storage.get(obj.objective_id, session=db_session)

        assert updated is not None
        assert updated.title == "New"
        assert updated.description == "New desc"
        assert updated.status == ObjectiveStatus.Published

    def test_update_nonexistent_raises_keyerror(self, db_session: Session) -> None:
        """update() raises KeyError for nonexistent objective."""
        with db_session.begin():
            with pytest.raises(KeyError):
                obj_storage.update(ObjectiveID(), title="Test", session=db_session)


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
def objective_factory(
    db_session: Session,
    test_org: Organization,
    test_educator: User,
) -> t.Callable[..., Objective]:
    """Factory fixture for creating test objectives."""

    def create_objective(
        title: str = "Test Objective",
        description: str = "A test objective description",
        organization_id: t.Any = None,
        created_by: t.Any = None,
        scope_boundaries: str | None = None,
        time_expectation_minutes: int | None = None,
        initial_prompts: list[str] | None = None,
        challenge_prompts: list[str] | None = None,
        extension_policy: ExtensionPolicy = ExtensionPolicy.Disallowed,
        status: ObjectiveStatus = ObjectiveStatus.Draft,
    ) -> Objective:
        with db_session.begin():
            obj = obj_storage.create(
                organization_id=organization_id or test_org.organization_id,
                created_by=created_by or test_educator.user_id,
                title=title,
                description=description,
                scope_boundaries=scope_boundaries,
                time_expectation_minutes=time_expectation_minutes,
                initial_prompts=initial_prompts,
                challenge_prompts=challenge_prompts,
                extension_policy=extension_policy,
                status=status,
                session=db_session,
            )
            return obj

    return create_objective
