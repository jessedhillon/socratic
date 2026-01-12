"""Tests for socratic.storage.strand module."""

from __future__ import annotations

import typing as t

import pytest
from sqlalchemy.orm import Session

from socratic.model import DependencyType, Objective, Organization, Strand, StrandID, User, UserRole
from socratic.storage import strand as strand_storage


class TestGet(object):
    """Tests for strand_storage.get()."""

    def test_get_by_strand_id(
        self,
        db_session: Session,
        strand_factory: t.Callable[..., Strand],
    ) -> None:
        """get() with strand_id returns the strand."""
        strand = strand_factory()

        with db_session.begin():
            result = strand_storage.get(strand.strand_id, session=db_session)

        assert result is not None
        assert result.strand_id == strand.strand_id

    def test_get_positional_pk(
        self,
        db_session: Session,
        strand_factory: t.Callable[..., Strand],
    ) -> None:
        """get() accepts strand_id as positional argument."""
        strand = strand_factory(name="Positional Test")

        with db_session.begin():
            result = strand_storage.get(strand.strand_id, session=db_session)

        assert result is not None
        assert result.name == "Positional Test"

    def test_get_nonexistent_returns_none(self, db_session: Session) -> None:
        """get() returns None for nonexistent strand ID."""
        with db_session.begin():
            result = strand_storage.get(StrandID(), session=db_session)

        assert result is None


class TestFind(object):
    """Tests for strand_storage.find()."""

    def test_find_all(
        self,
        db_session: Session,
        strand_factory: t.Callable[..., Strand],
    ) -> None:
        """find() returns all strands when no filters provided."""
        strand1 = strand_factory(name="Strand 1")
        strand2 = strand_factory(name="Strand 2")

        with db_session.begin():
            result = strand_storage.find(session=db_session)

        ids = {s.strand_id for s in result}
        assert strand1.strand_id in ids
        assert strand2.strand_id in ids

    def test_find_by_organization_id(
        self,
        db_session: Session,
        strand_factory: t.Callable[..., Strand],
        test_org: Organization,
        org_factory: t.Callable[..., Organization],
    ) -> None:
        """find() filters by organization_id."""
        other_org = org_factory()
        strand1 = strand_factory(name="Org 1 Strand")
        strand2 = strand_factory(name="Org 2 Strand", organization_id=other_org.organization_id)

        with db_session.begin():
            result = strand_storage.find(
                organization_id=test_org.organization_id,
                session=db_session,
            )

        ids = {s.strand_id for s in result}
        assert strand1.strand_id in ids
        assert strand2.strand_id not in ids


class TestCreate(object):
    """Tests for strand_storage.create()."""

    def test_create_strand(
        self,
        db_session: Session,
        test_org: Organization,
        test_educator: User,
    ) -> None:
        """create() creates a strand with required fields."""
        with db_session.begin():
            strand = strand_storage.create(
                organization_id=test_org.organization_id,
                created_by=test_educator.user_id,
                name="Test Strand",
                session=db_session,
            )

        assert strand.organization_id == test_org.organization_id
        assert strand.created_by == test_educator.user_id
        assert strand.name == "Test Strand"
        assert strand.strand_id is not None

    def test_create_strand_with_description(
        self,
        db_session: Session,
        test_org: Organization,
        test_educator: User,
    ) -> None:
        """create() accepts description field."""
        with db_session.begin():
            strand = strand_storage.create(
                organization_id=test_org.organization_id,
                created_by=test_educator.user_id,
                name="Test Strand",
                description="A test description",
                session=db_session,
            )

        assert strand.description == "A test description"


class TestUpdate(object):
    """Tests for strand_storage.update()."""

    def test_update_name(
        self,
        db_session: Session,
        strand_factory: t.Callable[..., Strand],
    ) -> None:
        """update() updates the strand name."""
        strand = strand_factory(name="Original Name")

        with db_session.begin():
            strand_storage.update(
                strand.strand_id,
                name="New Name",
                session=db_session,
            )

            result = strand_storage.get(strand.strand_id, session=db_session)

        assert result is not None
        assert result.name == "New Name"

    def test_update_description(
        self,
        db_session: Session,
        strand_factory: t.Callable[..., Strand],
    ) -> None:
        """update() updates the strand description."""
        strand = strand_factory(description=None)

        with db_session.begin():
            strand_storage.update(
                strand.strand_id,
                description="New description",
                session=db_session,
            )

            result = strand_storage.get(strand.strand_id, session=db_session)

        assert result is not None
        assert result.description == "New description"

    def test_update_description_to_none(
        self,
        db_session: Session,
        strand_factory: t.Callable[..., Strand],
    ) -> None:
        """update() can set description to None."""
        strand = strand_factory(description="Original")

        with db_session.begin():
            strand_storage.update(
                strand.strand_id,
                description=None,
                session=db_session,
            )

            result = strand_storage.get(strand.strand_id, session=db_session)

        assert result is not None
        assert result.description is None

    def test_update_nonexistent_raises_keyerror(self, db_session: Session) -> None:
        """update() raises KeyError for nonexistent strand ID."""
        with db_session.begin():
            with pytest.raises(KeyError):
                strand_storage.update(
                    StrandID(),
                    name="New Name",
                    session=db_session,
                )


class TestObjectiveInStrand(object):
    """Tests for objective-in-strand functions."""

    def test_add_objective_to_strand(
        self,
        db_session: Session,
        strand_factory: t.Callable[..., Strand],
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """add_objective_to_strand() adds an objective to a strand."""
        strand = strand_factory()
        objective = objective_factory()

        with db_session.begin():
            result = strand_storage.add_objective_to_strand(
                strand_id=strand.strand_id,
                objective_id=objective.objective_id,
                position=0,
                session=db_session,
            )

        assert result.strand_id == strand.strand_id
        assert result.objective_id == objective.objective_id
        assert result.position == 0

    def test_get_objectives_in_strand(
        self,
        db_session: Session,
        strand_factory: t.Callable[..., Strand],
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """get_objectives_in_strand() returns objectives ordered by position."""
        strand = strand_factory()
        obj1 = objective_factory(title="Objective 1")
        obj2 = objective_factory(title="Objective 2")

        with db_session.begin():
            strand_storage.add_objective_to_strand(
                strand_id=strand.strand_id,
                objective_id=obj1.objective_id,
                position=1,
                session=db_session,
            )
            strand_storage.add_objective_to_strand(
                strand_id=strand.strand_id,
                objective_id=obj2.objective_id,
                position=0,
                session=db_session,
            )

        with db_session.begin():
            result = strand_storage.get_objectives_in_strand(strand.strand_id, session=db_session)

        assert len(result) == 2
        assert result[0].objective_id == obj2.objective_id
        assert result[1].objective_id == obj1.objective_id

    def test_remove_objective_from_strand(
        self,
        db_session: Session,
        strand_factory: t.Callable[..., Strand],
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """remove_objective_from_strand() removes an objective from a strand."""
        strand = strand_factory()
        objective = objective_factory()

        with db_session.begin():
            strand_storage.add_objective_to_strand(
                strand_id=strand.strand_id,
                objective_id=objective.objective_id,
                position=0,
                session=db_session,
            )

        with db_session.begin():
            result = strand_storage.remove_objective_from_strand(
                strand_id=strand.strand_id,
                objective_id=objective.objective_id,
                session=db_session,
            )

        assert result is True

        with db_session.begin():
            objectives = strand_storage.get_objectives_in_strand(strand.strand_id, session=db_session)

        assert len(objectives) == 0

    def test_remove_objective_from_strand_not_found(
        self,
        db_session: Session,
        strand_factory: t.Callable[..., Strand],
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """remove_objective_from_strand() returns False when not found."""
        strand = strand_factory()
        objective = objective_factory()

        with db_session.begin():
            result = strand_storage.remove_objective_from_strand(
                strand_id=strand.strand_id,
                objective_id=objective.objective_id,
                session=db_session,
            )

        assert result is False

    def test_reorder_objectives_in_strand(
        self,
        db_session: Session,
        strand_factory: t.Callable[..., Strand],
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """reorder_objectives_in_strand() reorders objectives."""
        strand = strand_factory()
        obj1 = objective_factory(title="Objective 1")
        obj2 = objective_factory(title="Objective 2")
        obj3 = objective_factory(title="Objective 3")

        with db_session.begin():
            strand_storage.add_objective_to_strand(
                strand_id=strand.strand_id,
                objective_id=obj1.objective_id,
                position=0,
                session=db_session,
            )
            strand_storage.add_objective_to_strand(
                strand_id=strand.strand_id,
                objective_id=obj2.objective_id,
                position=1,
                session=db_session,
            )
            strand_storage.add_objective_to_strand(
                strand_id=strand.strand_id,
                objective_id=obj3.objective_id,
                position=2,
                session=db_session,
            )

        # Reorder to: obj3, obj1, obj2
        with db_session.begin():
            strand_storage.reorder_objectives_in_strand(
                strand.strand_id,
                [obj3.objective_id, obj1.objective_id, obj2.objective_id],
                session=db_session,
            )

        with db_session.begin():
            result = strand_storage.get_objectives_in_strand(strand.strand_id, session=db_session)

        assert result[0].objective_id == obj3.objective_id
        assert result[1].objective_id == obj1.objective_id
        assert result[2].objective_id == obj2.objective_id


class TestDependency(object):
    """Tests for dependency functions."""

    def test_add_dependency(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """add_dependency() creates a dependency between objectives."""
        obj1 = objective_factory(title="Objective 1")
        obj2 = objective_factory(title="Objective 2")

        with db_session.begin():
            result = strand_storage.add_dependency(
                objective_id=obj1.objective_id,
                depends_on_objective_id=obj2.objective_id,
                session=db_session,
            )

        assert result.objective_id == obj1.objective_id
        assert result.depends_on_objective_id == obj2.objective_id
        assert result.dependency_type == DependencyType.Hard

    def test_add_dependency_soft(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """add_dependency() accepts dependency_type parameter."""
        obj1 = objective_factory(title="Objective 1")
        obj2 = objective_factory(title="Objective 2")

        with db_session.begin():
            result = strand_storage.add_dependency(
                objective_id=obj1.objective_id,
                depends_on_objective_id=obj2.objective_id,
                dependency_type=DependencyType.Soft,
                session=db_session,
            )

        assert result.dependency_type == DependencyType.Soft

    def test_get_dependencies(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """get_dependencies() returns dependencies for an objective."""
        obj1 = objective_factory(title="Objective 1")
        obj2 = objective_factory(title="Objective 2")
        obj3 = objective_factory(title="Objective 3")

        with db_session.begin():
            strand_storage.add_dependency(
                objective_id=obj1.objective_id,
                depends_on_objective_id=obj2.objective_id,
                session=db_session,
            )
            strand_storage.add_dependency(
                objective_id=obj1.objective_id,
                depends_on_objective_id=obj3.objective_id,
                session=db_session,
            )

        with db_session.begin():
            result = strand_storage.get_dependencies(obj1.objective_id, session=db_session)

        assert len(result) == 2
        dep_ids = {d.depends_on_objective_id for d in result}
        assert obj2.objective_id in dep_ids
        assert obj3.objective_id in dep_ids

    def test_remove_dependency(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """remove_dependency() removes a dependency."""
        obj1 = objective_factory(title="Objective 1")
        obj2 = objective_factory(title="Objective 2")

        with db_session.begin():
            strand_storage.add_dependency(
                objective_id=obj1.objective_id,
                depends_on_objective_id=obj2.objective_id,
                session=db_session,
            )

        with db_session.begin():
            result = strand_storage.remove_dependency(
                objective_id=obj1.objective_id,
                depends_on_objective_id=obj2.objective_id,
                session=db_session,
            )

        assert result is True

        with db_session.begin():
            deps = strand_storage.get_dependencies(obj1.objective_id, session=db_session)

        assert len(deps) == 0

    def test_remove_dependency_not_found(
        self,
        db_session: Session,
        objective_factory: t.Callable[..., Objective],
    ) -> None:
        """remove_dependency() returns False when not found."""
        obj1 = objective_factory(title="Objective 1")
        obj2 = objective_factory(title="Objective 2")

        with db_session.begin():
            result = strand_storage.remove_dependency(
                objective_id=obj1.objective_id,
                depends_on_objective_id=obj2.objective_id,
                session=db_session,
            )

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
def strand_factory(
    db_session: Session,
    test_org: Organization,
    test_educator: User,
) -> t.Callable[..., Strand]:
    """Factory fixture for creating test strands."""

    def create_strand(
        name: str = "Test Strand",
        description: str | None = None,
        organization_id: t.Any = None,
    ) -> Strand:
        with db_session.begin():
            strand = strand_storage.create(
                organization_id=organization_id or test_org.organization_id,
                created_by=test_educator.user_id,
                name=name,
                description=description,
                session=db_session,
            )
            return strand

    return create_strand


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
        description: str = "A test objective",
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
