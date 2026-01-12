"""Tests for socratic.storage.user module."""

from __future__ import annotations

import typing as t

import pydantic as p
import pytest
from sqlalchemy.orm import Session

from socratic.model import Organization, OrganizationID, User, UserID, UserRole
from socratic.storage import user as user_storage
from socratic.storage.user import MembershipCreateParams, MembershipRemoveParams


class TestGet(object):
    """Tests for user_storage.get()."""

    def test_get_by_user_id(
        self,
        db_session: Session,
        user_factory: t.Callable[..., User],
        test_org: Organization,
    ) -> None:
        """get() with user_id returns the user."""
        user = user_factory(email="test@example.com", organization_id=test_org.organization_id)

        with db_session.begin():
            result = user_storage.get(user_id=user.user_id, session=db_session)

        assert result is not None
        assert result.user_id == user.user_id
        assert result.email == "test@example.com"

    def test_get_by_email(
        self,
        db_session: Session,
        user_factory: t.Callable[..., User],
        test_org: Organization,
    ) -> None:
        """get() with email returns the user."""
        user = user_factory(email="findme@example.com", organization_id=test_org.organization_id)

        with db_session.begin():
            result = user_storage.get(email="findme@example.com", session=db_session)

        assert result is not None
        assert result.user_id == user.user_id

    def test_get_with_memberships(
        self,
        db_session: Session,
        user_factory: t.Callable[..., User],
        test_org: Organization,
    ) -> None:
        """get() with with_memberships=True includes memberships."""
        user = user_factory(
            email="member@example.com",
            organization_id=test_org.organization_id,
            role=UserRole.Educator,
        )

        with db_session.begin():
            result = user_storage.get(user_id=user.user_id, with_memberships=True, session=db_session)

        assert result is not None
        assert hasattr(result, "memberships")
        assert len(result.memberships) == 1
        assert result.memberships[0].organization_id == test_org.organization_id
        assert result.memberships[0].role == UserRole.Educator

    def test_get_nonexistent_returns_none(self, db_session: Session) -> None:
        """get() returns None for nonexistent user."""
        with db_session.begin():
            result = user_storage.get(user_id=UserID(), session=db_session)

        assert result is None

    def test_get_requires_user_id_or_email(self, db_session: Session) -> None:
        """get() raises ValueError if neither user_id nor email provided."""
        with pytest.raises(ValueError, match="Either user_id or email must be provided"):
            user_storage.get(session=db_session)  # pyright: ignore[reportCallIssue]

    def test_get_rejects_both_user_id_and_email(self, db_session: Session) -> None:
        """get() raises ValueError if both user_id and email provided."""
        with pytest.raises(ValueError, match="Only one of user_id or email"):
            user_storage.get(user_id=UserID(), email="test@example.com", session=db_session)  # pyright: ignore[reportCallIssue, reportArgumentType]


class TestCreate(object):
    """Tests for user_storage.create()."""

    def test_create_user(self, db_session: Session) -> None:
        """create() creates a user with hashed password."""
        with db_session.begin():
            user = user_storage.create(
                email="new@example.com",
                name="New User",
                password=p.Secret("mypassword"),
                session=db_session,
            )

        assert user.email == "new@example.com"
        assert user.name == "New User"
        assert user.user_id is not None

    def test_create_user_password_is_hashed(self, db_session: Session) -> None:
        """create() hashes the password with bcrypt."""
        import bcrypt

        with db_session.begin():
            user = user_storage.create(
                email="hashed@example.com",
                name="Hashed User",
                password=p.Secret("testpassword"),
                session=db_session,
            )

            # Fetch the raw password_hash from database
            result = user_storage.get(user_id=user.user_id, session=db_session)

        assert result is not None
        assert result.password_hash is not None
        assert result.password_hash != "testpassword"
        assert bcrypt.checkpw(b"testpassword", result.password_hash.encode("utf-8"))


class TestUpdate(object):
    """Tests for user_storage.update()."""

    def test_update_email(
        self,
        db_session: Session,
        user_factory: t.Callable[..., User],
        test_org: Organization,
    ) -> None:
        """update() can change email."""
        user = user_factory(email="old@example.com", organization_id=test_org.organization_id)

        with db_session.begin():
            user_storage.update(
                user.user_id,
                email="new@example.com",
                session=db_session,
            )

            updated = user_storage.get(user_id=user.user_id, session=db_session)

        assert updated is not None
        assert updated.email == "new@example.com"

    def test_update_password(
        self,
        db_session: Session,
        user_factory: t.Callable[..., User],
        test_org: Organization,
    ) -> None:
        """update() can change password."""
        import bcrypt

        user = user_factory(
            email="pwchange@example.com",
            password="oldpassword",
            organization_id=test_org.organization_id,
        )

        with db_session.begin():
            user_storage.update(
                user.user_id,
                password=p.Secret("newpassword"),
                session=db_session,
            )

            result = user_storage.get(user_id=user.user_id, session=db_session)

        assert result is not None
        assert result.password_hash is not None
        assert bcrypt.checkpw(b"newpassword", result.password_hash.encode("utf-8"))

    def test_update_nonexistent_raises_keyerror(self, db_session: Session) -> None:
        """update() raises KeyError for nonexistent user."""
        with db_session.begin():
            with pytest.raises(KeyError):
                user_storage.update(
                    UserID(),
                    name="Nobody",
                    session=db_session,
                )


class TestMembershipAdd(object):
    """Tests for adding memberships via update()."""

    def test_add_membership(
        self,
        db_session: Session,
        user_factory: t.Callable[..., User],
        org_factory: t.Callable[..., Organization],
    ) -> None:
        """update() can add a membership."""
        org1 = org_factory(name="Org 1", slug="org-1")
        org2 = org_factory(name="Org 2", slug="org-2")
        user = user_factory(email="multi@example.com", organization_id=org1.organization_id)

        with db_session.begin():
            user_storage.update(
                user.user_id,
                add_memberships={MembershipCreateParams(organization_id=org2.organization_id, role=UserRole.Learner)},
                session=db_session,
            )

            result = user_storage.get(user_id=user.user_id, with_memberships=True, session=db_session)

        assert result is not None
        assert len(result.memberships) == 2
        org_ids = {m.organization_id for m in result.memberships}
        assert org1.organization_id in org_ids
        assert org2.organization_id in org_ids


class TestMembershipRemove(object):
    """Tests for removing memberships via update()."""

    def test_remove_membership_all_roles(
        self,
        db_session: Session,
        user_factory: t.Callable[..., User],
        org_factory: t.Callable[..., Organization],
    ) -> None:
        """remove_memberships with role=None removes all memberships for that org."""
        org1 = org_factory(name="Org 1", slug="org-1")
        org2 = org_factory(name="Org 2", slug="org-2")
        user = user_factory(email="multi@example.com", organization_id=org1.organization_id)

        # Add second membership
        with db_session.begin():
            user_storage.update(
                user.user_id,
                add_memberships={MembershipCreateParams(organization_id=org2.organization_id, role=UserRole.Learner)},
                session=db_session,
            )

        # Remove from org1 (role=None means remove all roles)
        with db_session.begin():
            user_storage.update(
                user.user_id,
                remove_memberships={MembershipRemoveParams(organization_id=org1.organization_id)},
                session=db_session,
            )

            result = user_storage.get(user_id=user.user_id, with_memberships=True, session=db_session)

        assert result is not None
        assert len(result.memberships) == 1
        assert result.memberships[0].organization_id == org2.organization_id

    def test_remove_membership_specific_role(
        self,
        db_session: Session,
        user_factory: t.Callable[..., User],
        org_factory: t.Callable[..., Organization],
    ) -> None:
        """remove_memberships with role specified only removes if role matches."""
        org1 = org_factory(name="Org 1", slug="org-1")
        org2 = org_factory(name="Org 2", slug="org-2")
        user = user_factory(email="multirole@example.com", organization_id=org1.organization_id, role=UserRole.Educator)

        # Add membership to second org
        with db_session.begin():
            user_storage.update(
                user.user_id,
                add_memberships={MembershipCreateParams(organization_id=org2.organization_id, role=UserRole.Learner)},
                session=db_session,
            )

        # Verify user has both memberships
        with db_session.begin():
            before = user_storage.get(user_id=user.user_id, with_memberships=True, session=db_session)
        assert before is not None
        assert len(before.memberships) == 2

        # Remove educator role from org1 (matches)
        with db_session.begin():
            user_storage.update(
                user.user_id,
                remove_memberships={
                    MembershipRemoveParams(organization_id=org1.organization_id, role=UserRole.Educator)
                },
                session=db_session,
            )

            result = user_storage.get(user_id=user.user_id, with_memberships=True, session=db_session)

        # Should only have org2 membership
        assert result is not None
        assert len(result.memberships) == 1
        assert result.memberships[0].organization_id == org2.organization_id

    def test_remove_membership_wrong_role_no_effect(
        self,
        db_session: Session,
        user_factory: t.Callable[..., User],
        test_org: Organization,
    ) -> None:
        """remove_memberships with non-matching role has no effect."""
        user = user_factory(
            email="educator@example.com",
            organization_id=test_org.organization_id,
            role=UserRole.Educator,
        )

        # Try to remove learner role (user only has educator)
        with db_session.begin():
            user_storage.update(
                user.user_id,
                remove_memberships={
                    MembershipRemoveParams(organization_id=test_org.organization_id, role=UserRole.Learner)
                },
                session=db_session,
            )

            result = user_storage.get(user_id=user.user_id, with_memberships=True, session=db_session)

        # Should still have educator role
        assert result is not None
        assert len(result.memberships) == 1
        assert result.memberships[0].role == UserRole.Educator

    def test_remove_membership_nonexistent_org_no_effect(
        self,
        db_session: Session,
        user_factory: t.Callable[..., User],
        test_org: Organization,
    ) -> None:
        """remove_memberships for non-member org has no effect."""
        user = user_factory(email="single@example.com", organization_id=test_org.organization_id)

        # Try to remove from org user isn't a member of
        with db_session.begin():
            user_storage.update(
                user.user_id,
                remove_memberships={MembershipRemoveParams(organization_id=OrganizationID())},
                session=db_session,
            )

            result = user_storage.get(user_id=user.user_id, with_memberships=True, session=db_session)

        # Should still have original membership
        assert result is not None
        assert len(result.memberships) == 1
        assert result.memberships[0].organization_id == test_org.organization_id
