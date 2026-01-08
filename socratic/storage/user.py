from __future__ import annotations

import typing as t

from sqlalchemy import select

from socratic.core import di
from socratic.model import OrganizationID, OrganizationMembership, User, UserID, UserRole, UserWithMemberships

from . import Session
from .table import organization_memberships, users


def get(key: UserID, session: Session = di.Provide["storage.persistent.session"]) -> User | None:
    stmt = select(users.__table__).where(users.user_id == key)
    row = session.execute(stmt).mappings().one_or_none()
    return User(**row) if row else None


def get_by_email(email: str, session: Session = di.Provide["storage.persistent.session"]) -> User | None:
    stmt = select(users.__table__).where(users.email == email)
    row = session.execute(stmt).mappings().one_or_none()
    return User(**row) if row else None


def get_with_memberships(
    key: UserID, session: Session = di.Provide["storage.persistent.session"]
) -> UserWithMemberships | None:
    user = get(key, session=session)
    if user is None:
        return None
    memberships = get_memberships(key, session=session)
    return UserWithMemberships(**user.model_dump(), memberships=list(memberships))


def find(
    *,
    organization_id: OrganizationID | None = None,
    role: UserRole | None = None,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[User, ...]:
    if organization_id is not None:
        stmt = (
            select(users.__table__)
            .join(organization_memberships, users.user_id == organization_memberships.user_id)
            .where(organization_memberships.organization_id == organization_id)
        )
        if role is not None:
            stmt = stmt.where(organization_memberships.role == role.value)
    else:
        stmt = select(users.__table__)
    rows = session.execute(stmt).mappings().all()
    return tuple(User(**row) for row in rows)


def create(params: UserCreateParams, session: Session = di.Provide["storage.persistent.session"]) -> User:
    user = users(
        user_id=UserID(),
        email=params["email"],
        name=params["name"],
        password_hash=params.get("password_hash"),
    )
    session.add(user)
    session.flush()
    return get(user.user_id, session=session)  # type: ignore


def get_memberships(
    user_id: UserID,
    session: Session = di.Provide["storage.persistent.session"],
) -> tuple[OrganizationMembership, ...]:
    stmt = select(organization_memberships.__table__).where(organization_memberships.user_id == user_id)
    rows = session.execute(stmt).mappings().all()
    return tuple(OrganizationMembership(**row) for row in rows)


def add_membership(
    params: MembershipCreateParams,
    session: Session = di.Provide["storage.persistent.session"],
) -> OrganizationMembership:
    membership = organization_memberships(
        user_id=params["user_id"],
        organization_id=params["organization_id"],
        role=params["role"].value,
    )
    session.add(membership)
    session.flush()
    stmt = select(organization_memberships.__table__).where(
        organization_memberships.user_id == params["user_id"],
        organization_memberships.organization_id == params["organization_id"],
    )
    row = session.execute(stmt).mappings().one()
    return OrganizationMembership(**row)


class UserCreateParams(t.TypedDict, total=False):
    email: t.Required[str]
    name: t.Required[str]
    password_hash: str | None


class MembershipCreateParams(t.TypedDict):
    user_id: UserID
    organization_id: OrganizationID
    role: UserRole
