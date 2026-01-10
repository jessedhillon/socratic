"""JWT token management for session authentication."""

from __future__ import annotations

import datetime
import typing as t

import annotated_types as ant
import jwt
import pydantic as p

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


class JWTManager(object):
    """Manages JWT token creation and validation."""

    _secret_key: p.Secret[str]
    _algorithm: t.Literal["HS256"]
    _access_token_expire_minutes: t.Annotated[int, ant.Gt(1)]

    def __init__(
        self,
        secret_key: p.Secret[str],
        algorithm: t.Literal["HS256"] = "HS256",
        access_token_expire_minutes: t.Annotated[int, ant.Gt(1)] = 30,
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_token_expire_minutes = access_token_expire_minutes

    @property
    def secret_key(self) -> str:
        """Get the JWT secret key."""
        return self._secret_key.get_secret_value()

    @property
    def algorithm(self) -> str:
        """Get the JWT algorithm."""
        return self._algorithm

    @property
    def access_token_expire_minutes(self) -> int:
        """Get the access token expiration time in minutes."""
        return self._access_token_expire_minutes

    def create_access_token(
        self,
        user_id: UserID,
        organization_id: OrganizationID,
        role: str,
        expires_delta: datetime.timedelta | None = None,
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
            expires_delta = datetime.timedelta(minutes=self._access_token_expire_minutes)

        expire = now + expires_delta

        payload: dict[str, t.Any] = {
            "sub": str(user_id),
            "org": str(organization_id),
            "role": role,
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
        }

        return jwt.encode(payload, self.secret_key, algorithm=self._algorithm)

    def decode_token(self, token: str) -> TokenData | None:
        """Decode and validate a token.

        Args:
            token: The JWT token string

        Returns:
            TokenData if valid, None if invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self._algorithm],
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

    def is_token_valid(self, token: str) -> bool:
        """Check if a token is valid without decoding full payload."""
        return self.decode_token(token) is not None
