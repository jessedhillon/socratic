"""JWT token management for session authentication."""

from __future__ import annotations

import datetime
import typing as t

import jwt
import pydantic as p

from socratic.core import di
from socratic.model import OrganizationID, UserID


class TokenPayload(t.TypedDict):
    """JWT token payload structure."""

    sub: str  # user_id
    org: str  # organization_id
    role: str  # user's role in organization
    exp: int  # expiration timestamp
    iat: int  # issued at timestamp


class TokenData(t.NamedTuple):
    """Decoded token data."""

    user_id: UserID
    organization_id: OrganizationID
    role: str
    expires_at: datetime.datetime
    issued_at: datetime.datetime


def create_access_token(
    user_id: UserID,
    organization_id: OrganizationID,
    role: str,
    expires_delta: datetime.timedelta | None = None,
    secret: p.Secret[str] = di.Provide["secrets.auth.jwt"],
    algorithm: str = di.Provide["config.web.socratic.auth.jwt_algorithm"],
    expire_minutes: int = di.Provide["config.web.socratic.auth.access_token_expire_minutes"],
) -> str:
    """Create a new access token.

    Args:
        user_id: The user's ID
        organization_id: The organization context
        role: User's role in the organization
        expires_delta: Custom expiration time (default: access_token_expire_minutes)

    Returns:
        Encoded JWT token string
    """
    now = datetime.datetime.now(datetime.UTC)
    if expires_delta is None:
        expires_delta = datetime.timedelta(minutes=expire_minutes)

    expire = now + expires_delta

    payload: dict[str, t.Any] = {
        "sub": str(user_id),
        "org": str(organization_id),
        "role": role,
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
    }

    return jwt.encode(payload, secret.get_secret_value(), algorithm=algorithm)


def decode_token(
    token: str,
    secret: p.Secret[str] = di.Provide["secrets.auth.jwt"],
    algorithm: str = di.Provide["config.web.socratic.auth.jwt_algorithm"],
) -> TokenData | None:
    """Decode and validate a token.

    Args:
        token: The JWT token string

    Returns:
        TokenData if valid, None if invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            secret.get_secret_value(),
            algorithms=[algorithm],
        )

        return TokenData(
            user_id=UserID(payload["sub"]),
            organization_id=OrganizationID(payload["org"]),
            role=payload["role"],
            expires_at=datetime.datetime.fromtimestamp(payload["exp"], tz=datetime.UTC),
            issued_at=datetime.datetime.fromtimestamp(payload["iat"], tz=datetime.UTC),
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def is_token_valid(
    token: str,
    secret: p.Secret[str] = di.Provide["secrets.auth.jwt"],
    algorithm: str = di.Provide["config.web.socratic.auth.jwt_algorithm"],
) -> bool:
    """Check if a token is valid without decoding full payload."""
    return decode_token(token, secret=secret, algorithm=algorithm) is not None
