"""Tests for socratic.storage.rubric module."""

from __future__ import annotations

import typing as t

import pytest
from sqlalchemy.orm import Session

from socratic.model import Objective, Organization, RubricCriterion, RubricCriterionID, User, UserRole
from socratic.storage import rubric as rubric_storage
from socratic.storage.rubric import ProficiencyLevelCreateParams


class TestGet(object):
    """Tests for rubric_storage.get()."""

    def test_get_by_criterion_id(
        self,
        db_session: Session,
        criterion_factory: t.Callable[..., RubricCriterion],
    ) -> None:
        """get() with criterion_id returns the criterion."""
        criterion = criterion_factory()

        with db_session.begin():
            result = rubric_storage.get(criterion.criterion_id, session=db_session)

        assert result is not None
        assert result.criterion_id == criterion.criterion_id

    def test_get_positional_pk(
        self,
        db_session: Session,
        criterion_factory: t.Callable[..., RubricCriterion],
    ) -> None:
        """get() accepts criterion_id as positional argument."""
        criterion = criterion_factory(name="Positional Test")

        with db_session.begin():
            result = rubric_storage.get(criterion.criterion_id, session=db_session)

        assert result is not None
        assert result.name == "Positional Test"

    def test_get_nonexistent_returns_none(self, db_session: Session) -> None:
        """get() returns None for nonexistent criterion ID."""
        with db_session.begin():
            result = rubric_storage.get(RubricCriterionID(), session=db_session)

        assert result is None


class TestFind(object):
    """Tests for rubric_storage.find()."""

    def test_find_all(
        self,
        db_session: Session,
        criterion_factory: t.Callable[..., RubricCriterion],
    ) -> None:
        """find() returns all criteria when no filters provided."""
        c1 = criterion_factory(name="Criterion 1")
        c2 = criterion_factory(name="Criterion 2")

        with db_session.begin():
            result = rubric_storage.find(session=db_session)

        ids = {c.criterion_id for c in result}
        assert c1.criterion_id in ids
        assert c2.criterion_id in ids

    def test_find_by_objective_id(
        self,
        db_session: Session,
        criterion_factory: t.Callable[..., RubricCriterion],
        test_objective: Objective,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """find() filters by objective_id."""
        other_objective = objective_factory(title="Other Objective")
        c1 = criterion_factory(name="Objective 1 Criterion")
        c2 = criterion_factory(name="Objective 2 Criterion", objective_id=other_objective.objective_id)

        with db_session.begin():
            result = rubric_storage.find(objective_id=test_objective.objective_id, session=db_session)

        ids = {c.criterion_id for c in result}
        assert c1.criterion_id in ids
        assert c2.criterion_id not in ids


class TestCreate(object):
    """Tests for rubric_storage.create()."""

    def test_create_criterion(
        self,
        db_session: Session,
        test_objective: Objective,
    ) -> None:
        """create() creates a criterion with required fields."""
        with db_session.begin():
            criterion = rubric_storage.create(
                objective_id=test_objective.objective_id,
                name="Test Criterion",
                description="A test criterion",
                session=db_session,
            )

        assert criterion.objective_id == test_objective.objective_id
        assert criterion.name == "Test Criterion"
        assert criterion.description == "A test criterion"
        assert criterion.criterion_id is not None

    def test_create_criterion_with_optional_fields(
        self,
        db_session: Session,
        test_objective: Objective,
    ) -> None:
        """create() accepts optional fields."""
        proficiency_levels = [
            ProficiencyLevelCreateParams(
                grade="S",
                description="Demonstrates mastery of the concept",
            ),
            ProficiencyLevelCreateParams(
                grade="A",
                description="Shows good understanding with minor gaps",
            ),
            ProficiencyLevelCreateParams(
                grade="C",
                description="Partial understanding with some misconceptions",
            ),
            ProficiencyLevelCreateParams(
                grade="F",
                description="Does not demonstrate understanding",
            ),
        ]

        with db_session.begin():
            criterion = rubric_storage.create(
                objective_id=test_objective.objective_id,
                name="Full Criterion",
                description="Complete criterion",
                proficiency_levels=proficiency_levels,
                session=db_session,
            )

        assert len(criterion.proficiency_levels) == 4
        assert criterion.proficiency_levels[0].grade == "S"
        assert criterion.proficiency_levels[1].grade == "A"

    def test_create_defaults(
        self,
        db_session: Session,
        test_objective: Objective,
    ) -> None:
        """create() uses sensible defaults for optional fields."""
        with db_session.begin():
            criterion = rubric_storage.create(
                objective_id=test_objective.objective_id,
                name="Minimal Criterion",
                description="Minimal description",
                session=db_session,
            )

        assert criterion.proficiency_levels == []


class TestDelete(object):
    """Tests for rubric_storage.delete()."""

    def test_delete_existing(
        self,
        db_session: Session,
        criterion_factory: t.Callable[..., RubricCriterion],
    ) -> None:
        """delete() removes an existing criterion and returns True."""
        criterion = criterion_factory()

        with db_session.begin():
            result = rubric_storage.delete(criterion.criterion_id, session=db_session)

        assert result is True

        with db_session.begin():
            fetched = rubric_storage.get(criterion.criterion_id, session=db_session)
        assert fetched is None

    def test_delete_nonexistent_returns_false(self, db_session: Session) -> None:
        """delete() returns False for nonexistent criterion."""
        with db_session.begin():
            result = rubric_storage.delete(RubricCriterionID(), session=db_session)

        assert result is False


class TestUpdate(object):
    """Tests for rubric_storage.update()."""

    def test_update_single_field(
        self,
        db_session: Session,
        criterion_factory: t.Callable[..., RubricCriterion],
    ) -> None:
        """update() updates a single field."""
        criterion = criterion_factory(name="Original Name")

        with db_session.begin():
            rubric_storage.update(
                criterion.criterion_id,
                name="Updated Name",
                session=db_session,
            )
            result = rubric_storage.get(criterion.criterion_id, session=db_session)

        assert result is not None
        assert result.name == "Updated Name"
        assert result.description == "A test criterion description"  # unchanged

    def test_update_multiple_fields(
        self,
        db_session: Session,
        criterion_factory: t.Callable[..., RubricCriterion],
    ) -> None:
        """update() updates multiple fields at once."""
        criterion = criterion_factory()

        with db_session.begin():
            rubric_storage.update(
                criterion.criterion_id,
                name="New Name",
                description="New Description",
                session=db_session,
            )
            result = rubric_storage.get(criterion.criterion_id, session=db_session)

        assert result is not None
        assert result.name == "New Name"
        assert result.description == "New Description"

    def test_update_proficiency_levels(
        self,
        db_session: Session,
        criterion_factory: t.Callable[..., RubricCriterion],
    ) -> None:
        """update() updates proficiency_levels list."""
        criterion = criterion_factory()

        new_levels = [
            ProficiencyLevelCreateParams(
                grade="S",
                description="Demonstrates mastery",
            ),
            ProficiencyLevelCreateParams(
                grade="A",
                description="Shows good understanding",
            ),
        ]

        with db_session.begin():
            rubric_storage.update(
                criterion.criterion_id,
                proficiency_levels=new_levels,
                session=db_session,
            )
            result = rubric_storage.get(criterion.criterion_id, session=db_session)

        assert result is not None
        assert len(result.proficiency_levels) == 2
        assert result.proficiency_levels[0].grade == "S"
        assert result.proficiency_levels[1].grade == "A"

    def test_update_nonexistent_raises_keyerror(self, db_session: Session) -> None:
        """update() raises KeyError for nonexistent criterion."""
        with pytest.raises(KeyError):
            with db_session.begin():
                rubric_storage.update(
                    RubricCriterionID(),
                    name="New Name",
                    session=db_session,
                )

    def test_update_no_changes_verifies_existence(
        self,
        db_session: Session,
        criterion_factory: t.Callable[..., RubricCriterion],
    ) -> None:
        """update() with no fields still verifies criterion exists."""
        criterion = criterion_factory()

        # Should not raise - criterion exists
        with db_session.begin():
            rubric_storage.update(criterion.criterion_id, session=db_session)

    def test_update_no_changes_raises_for_nonexistent(self, db_session: Session) -> None:
        """update() with no fields raises KeyError for nonexistent criterion."""
        with pytest.raises(KeyError):
            with db_session.begin():
                rubric_storage.update(RubricCriterionID(), session=db_session)


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
def objective_factory(
    db_session: Session,
    test_org: Organization,
    test_educator: User,
) -> t.Callable[..., Objective]:
    """Factory fixture for creating test objectives."""
    from socratic.storage import objective as obj_storage

    def create_objective(
        title: str = "Test Objective",
        description: str = "A test objective description",
    ) -> Objective:
        with db_session.begin():
            obj = obj_storage.create(
                organization_id=test_org.organization_id,
                created_by=test_educator.user_id,
                title=title,
                description=description,
                session=db_session,
            )
            return obj

    return create_objective


@pytest.fixture
def criterion_factory(
    db_session: Session,
    test_objective: Objective,
) -> t.Callable[..., RubricCriterion]:
    """Factory fixture for creating test rubric criteria."""

    def create_criterion(
        name: str = "Test Criterion",
        description: str = "A test criterion description",
        objective_id: t.Any = None,
        proficiency_levels: list[ProficiencyLevelCreateParams] | None = None,
    ) -> RubricCriterion:
        with db_session.begin():
            criterion = rubric_storage.create(
                objective_id=objective_id or test_objective.objective_id,
                name=name,
                description=description,
                proficiency_levels=proficiency_levels,
                session=db_session,
            )
            return criterion

    return create_criterion
