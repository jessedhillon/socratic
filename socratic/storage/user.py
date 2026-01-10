from __future__ import annotations

import typing as t

import bcrypt
import pydantic as p
import sqlalchemy as sqla

from socratic.core import di
from socratic.lib import NotSet
from socratic.model import OrganizationID, OrganizationMembership, User, UserID, UserRole, UserWithMemberships

from . import Session
from .table import organization_memberships, users


class MembershipCreateParams(p.BaseModel):
    """Parameters for creating a membership."""

    model_config = p.ConfigDict(frozen=True)

    organization_id: OrganizationID
    role: UserRole

    def __hash__(self) -> int:
        return hash((self.organization_id, self.role))


class MembershipRemoveParams(p.BaseModel):
    """Parameters for removing a membership.

    If role is None, removes all memberships for the organization.
    If role is specified, only removes the membership with that role.
    """

    model_config = p.ConfigDict(frozen=True)

    organization_id: OrganizationID
    role: UserRole | None = None

    def __hash__(self) -> int:
        return hash((self.organization_id, self.role))


@t.overload
def get(
    *,
    user_id: UserID,
    with_memberships: t.Literal[False] = ...,
    session: Session = ...,
) -> User | None: ...


@t.overload
def get(
    *,
    user_id: UserID,
    with_memberships: t.Literal[True],
    session: Session = ...,
) -> UserWithMemberships | None: ...


@t.overload
def get(
    *,
    email: str,
    with_memberships: t.Literal[False] = ...,
    session: Session = ...,
) -> User | None: ...


@t.overload
def get(
    *,
    email: str,
    with_memberships: t.Literal[True],
    session: Session = ...,
) -> UserWithMemberships | None: ...


def get(
    *,
    user_id: UserID | None = None,
    email: str | None = None,
    with_memberships: bool = False,
    session: Session = di.Provide["storage.persistent.session"],
) -> User | UserWithMemberships | None:
    """Get a user by ID or email.

    Exactly one of user_id or email must be provided.
    """
    if user_id is None and email is None:
        raise ValueError("Either user_id or email must be provided")
    if user_id is not None and email is not None:
        raise ValueError("Only one of user_id or email should be provided")

    if user_id is not None:
        stmt = sqla.select(users.__table__).where(users.user_id == user_id)
    else:
        stmt = sqla.select(users.__table__).where(users.email == email)

    row = session.execute(stmt).mappings().one_or_none()
    if row is None:
        return None

    user = User(**row)

    if with_memberships:
        membership_stmt = sqla.select(organization_memberships.__table__).where(
            organization_memberships.user_id == user.user_id
        )
        membership_rows = session.execute(membership_stmt).mappings().all()
        memberships = [OrganizationMembership(**m) for m in membership_rows]
        return UserWithMemberships(**user.model_dump(), memberships=memberships)

    return user


def find(
    *,
    organization_id: OrganizationID | None = None,
    role: UserRole | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[User, ...]:
    """Find users matching criteria."""
    if organization_id is not None:
        stmt = (
            sqla.select(users.__table__)
            .join(organization_memberships, users.user_id == organization_memberships.user_id)
            .where(organization_memberships.organization_id == organization_id)
        )
        if role is not None:
            stmt = stmt.where(organization_memberships.role == role.value)
    else:
        stmt = sqla.select(users.__table__)
    rows = session.execute(stmt).mappings().all()
    return tuple(User(**row) for row in rows)


def create(
    *,
    email: str,
    name: str,
    password: p.Secret[str],
    session: Session = di.Provide["storage.persistent.session"],
) -> User:
    """Create a new user.

    Password is hashed internally using bcrypt.
    """
    password_hash = bcrypt.hashpw(
        password.get_secret_value().encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")

    user = users(
        user_id=UserID(),
        email=email,
        name=name,
        password_hash=password_hash,
    )
    session.add(user)
    session.flush()
    return get(user_id=user.user_id, session=session)  # type: ignore[return-value]


@t.overload
def update(
    user_id: UserID,
    *,
    email: str | NotSet = ...,
    name: str | NotSet = ...,
    password: p.Secret[str] | NotSet = ...,
    add_memberships: set[MembershipCreateParams] | None = ...,
    remove_memberships: set[MembershipRemoveParams] | None = ...,
    with_memberships: t.Literal[False],
    session: Session = ...,
) -> User: ...


@t.overload
def update(
    user_id: UserID,
    *,
    email: str | NotSet = ...,
    name: str | NotSet = ...,
    password: p.Secret[str] | NotSet = ...,
    add_memberships: set[MembershipCreateParams] | None = ...,
    remove_memberships: set[MembershipRemoveParams] | None = ...,
    with_memberships: t.Literal[True] = ...,
    session: Session = ...,
) -> UserWithMemberships: ...


@t.overload
def update(
    user_id: UserID,
    *,
    email: str | NotSet = ...,
    name: str | NotSet = ...,
    password: p.Secret[str] | NotSet = ...,
    add_memberships: set[MembershipCreateParams],
    remove_memberships: set[MembershipRemoveParams] | None = ...,
    with_memberships: None = ...,
    session: Session = ...,
) -> UserWithMemberships: ...


@t.overload
def update(
    user_id: UserID,
    *,
    email: str | NotSet = ...,
    name: str | NotSet = ...,
    password: p.Secret[str] | NotSet = ...,
    add_memberships: set[MembershipCreateParams] | None = ...,
    remove_memberships: set[MembershipRemoveParams],
    with_memberships: None = ...,
    session: Session = ...,
) -> UserWithMemberships: ...


def update(
    user_id: UserID,
    *,
    email: str | NotSet = NotSet(),
    name: str | NotSet = NotSet(),
    password: p.Secret[str] | NotSet = NotSet(),
    add_memberships: set[MembershipCreateParams] | None = None,
    remove_memberships: set[MembershipRemoveParams] | None = None,
    with_memberships: bool | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> User | UserWithMemberships:
    """Update a user.

    Uses NotSet sentinel for parameters where None is a valid update value.
    Password is hashed internally using bcrypt.

    Raises:
        KeyError: If user_id does not correspond to a user
    """
    # Build update values
    values: dict[str, t.Any] = {}
    if not isinstance(email, NotSet):
        values["email"] = email
    if not isinstance(name, NotSet):
        values["name"] = name
    if not isinstance(password, NotSet):
        values["password_hash"] = bcrypt.hashpw(
            password.get_secret_value().encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

    # Issue UPDATE statement (required even if no field changes)
    if values:
        stmt = sqla.update(users).where(users.user_id == user_id).values(**values)
    else:
        # No-op update to verify user exists
        stmt = sqla.update(users).where(users.user_id == user_id).values(user_id=user_id)

    result = session.execute(stmt)
    if result.rowcount == 0:  # pyright: ignore[reportAttributeAccessIssue]
        raise KeyError(f"User {user_id} not found")

    # Handle membership additions
    if add_memberships:
        for membership in add_memberships:
            m = organization_memberships(
                user_id=user_id,
                organization_id=membership.organization_id,
                role=membership.role.value,
            )
            session.add(m)

    # Handle membership removals
    if remove_memberships:
        for removal in remove_memberships:
            delete_stmt = sqla.delete(organization_memberships).where(
                organization_memberships.user_id == user_id,
                organization_memberships.organization_id == removal.organization_id,
            )
            if removal.role is not None:
                delete_stmt = delete_stmt.where(organization_memberships.role == removal.role.value)
            session.execute(delete_stmt)

    session.flush()

    # Determine return type - defaults to True if memberships were modified
    if with_memberships is None:
        with_memberships = bool(add_memberships or remove_memberships)

    return get(user_id=user_id, with_memberships=with_memberships, session=session)  # type: ignore[return-value]
