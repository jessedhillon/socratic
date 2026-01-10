"""Local authentication provider using bcrypt for password hashing."""

from __future__ import annotations

import bcrypt
from sqlalchemy.orm import Session

from socratic.core import di
from socratic.model import OrganizationID, User, UserID, UserRole
from socratic.storage import organization as org_storage
from socratic.storage import user as user_storage

from .provider import AuthResult


def authenticate(
    email: str,
    password: str,
    session: Session = di.Provide["storage.persistent.session"],
) -> AuthResult:
    """Authenticate with email/password."""
    user = user_storage.get_by_email(email, session=session)
    if user is None:
        return AuthResult(success=False, error="Invalid email or password")

    if not verify_password(user.user_id, password, session=session):
        return AuthResult(success=False, error="Invalid email or password")

    return AuthResult(success=True, user=user)


def register(
    email: str,
    password: str,
    name: str,
    organization_id: OrganizationID,
    role: str,
    session: Session = di.Provide["storage.persistent.session"],
) -> AuthResult:
    """Register a new user with password."""
    # Check if email already exists
    existing = user_storage.get_by_email(email, session=session)
    if existing is not None:
        return AuthResult(success=False, error="Email already registered")

    # Verify organization exists
    org = org_storage.get(organization_id, session=session)
    if org is None:
        return AuthResult(success=False, error="Organization not found")

    # Hash password
    password_hash = _hash_password(password)

    # Create user
    user = user_storage.create(
        {
            "email": email,
            "name": name,
            "password_hash": password_hash,
        },
        session=session,
    )

    # Add to organization
    user_storage.add_to_organization(
        user.user_id,
        organization_id,
        UserRole(role),
        session=session,
    )

    return AuthResult(success=True, user=user)


def get_user(
    user_id: UserID,
    session: Session = di.Provide["storage.persistent.session"],
) -> User | None:
    """Get user by ID."""
    with session.begin():
        return user_storage.get(user_id, session=session)


def set_password(
    user_id: UserID,
    password: str,
    session: Session = di.Provide["storage.persistent.session"],
) -> bool:
    """Set/update user's password."""
    password_hash = _hash_password(password)
    result = user_storage.update(
        user_id,
        {"password_hash": password_hash},
        session=session,
    )
    return result is not None


def verify_password(
    user_id: UserID,
    password: str,
    session: Session = di.Provide["storage.persistent.session"],
) -> bool:
    """Verify user's password."""
    user = user_storage.get(user_id, session=session)
    if user is None or user.password_hash is None:
        return False

    return bcrypt.checkpw(
        password.encode("utf-8"),
        user.password_hash.encode("utf-8"),
    )


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")
