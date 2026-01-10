"""Tests for socratic.storage.organization module."""

from __future__ import annotations

import typing as t

import pytest
from sqlalchemy.orm import Session

from socratic.model import Organization, OrganizationID
from socratic.storage import organization as org_storage


class TestGet(object):
    """Tests for org_storage.get()."""

    def test_get_by_organization_id(
        self,
        db_session: Session,
        org_factory: t.Callable[..., Organization],
    ) -> None:
        """get() with organization_id returns the organization."""
        org = org_factory(name="Test Org", slug="test-org")

        with db_session.begin():
            result = org_storage.get(organization_id=org.organization_id, session=db_session)

        assert result is not None
        assert result.organization_id == org.organization_id
        assert result.name == "Test Org"
        assert result.slug == "test-org"

    def test_get_by_slug(
        self,
        db_session: Session,
        org_factory: t.Callable[..., Organization],
    ) -> None:
        """get() with slug returns the organization."""
        org = org_factory(name="Slug Test Org", slug="slug-test")

        with db_session.begin():
            result = org_storage.get(slug="slug-test", session=db_session)

        assert result is not None
        assert result.organization_id == org.organization_id
        assert result.slug == "slug-test"

    def test_get_nonexistent_by_id_returns_none(self, db_session: Session) -> None:
        """get() returns None for nonexistent organization ID."""
        with db_session.begin():
            result = org_storage.get(organization_id=OrganizationID(), session=db_session)

        assert result is None

    def test_get_nonexistent_by_slug_returns_none(self, db_session: Session) -> None:
        """get() returns None for nonexistent slug."""
        with db_session.begin():
            result = org_storage.get(slug="nonexistent-slug", session=db_session)

        assert result is None

    def test_get_requires_organization_id_or_slug(self, db_session: Session) -> None:
        """get() raises ValueError if neither organization_id nor slug provided."""
        with pytest.raises(ValueError, match="Either organization_id or slug must be provided"):
            org_storage.get(session=db_session)  # pyright: ignore[reportCallIssue]

    def test_get_rejects_both_organization_id_and_slug(self, db_session: Session) -> None:
        """get() raises ValueError if both organization_id and slug provided."""
        with pytest.raises(ValueError, match="Only one of organization_id or slug"):
            org_storage.get(
                organization_id=OrganizationID(),
                slug="test",
                session=db_session,
            )  # pyright: ignore[reportCallIssue]


class TestFind(object):
    """Tests for org_storage.find()."""

    def test_find_all(
        self,
        db_session: Session,
        org_factory: t.Callable[..., Organization],
    ) -> None:
        """find() returns all organizations."""
        org1 = org_factory(name="Org 1", slug="org-1")
        org2 = org_factory(name="Org 2", slug="org-2")

        with db_session.begin():
            result = org_storage.find(session=db_session)

        org_ids = {o.organization_id for o in result}
        assert org1.organization_id in org_ids
        assert org2.organization_id in org_ids


class TestCreate(object):
    """Tests for org_storage.create()."""

    def test_create_organization(self, db_session: Session) -> None:
        """create() creates an organization with the given name and slug."""
        with db_session.begin():
            org = org_storage.create(name="New Org", slug="new-org", session=db_session)

        assert org.name == "New Org"
        assert org.slug == "new-org"
        assert org.organization_id is not None
        assert org.create_time is not None


class TestUpdate(object):
    """Tests for org_storage.update()."""

    def test_update_name(
        self,
        db_session: Session,
        org_factory: t.Callable[..., Organization],
    ) -> None:
        """update() can change organization name."""
        org = org_factory(name="Old Name", slug="old-name")

        with db_session.begin():
            updated = org_storage.update(org.organization_id, name="New Name", session=db_session)

        assert updated.name == "New Name"
        assert updated.slug == "old-name"  # slug unchanged

    def test_update_slug(
        self,
        db_session: Session,
        org_factory: t.Callable[..., Organization],
    ) -> None:
        """update() can change organization slug."""
        org = org_factory(name="Test Org", slug="old-slug")

        with db_session.begin():
            updated = org_storage.update(org.organization_id, slug="new-slug", session=db_session)

        assert updated.slug == "new-slug"
        assert updated.name == "Test Org"  # name unchanged

    def test_update_multiple_fields(
        self,
        db_session: Session,
        org_factory: t.Callable[..., Organization],
    ) -> None:
        """update() can change multiple fields at once."""
        org = org_factory(name="Old Name", slug="old-slug")

        with db_session.begin():
            updated = org_storage.update(
                org.organization_id,
                name="New Name",
                slug="new-slug",
                session=db_session,
            )

        assert updated.name == "New Name"
        assert updated.slug == "new-slug"

    def test_update_nonexistent_raises_keyerror(self, db_session: Session) -> None:
        """update() raises KeyError for nonexistent organization."""
        with db_session.begin():
            with pytest.raises(KeyError):
                org_storage.update(OrganizationID(), name="Test", session=db_session)
