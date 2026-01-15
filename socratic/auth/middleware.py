"""Authentication middleware and dependencies for FastAPI routes."""

from __future__ import annotations

import typing as t

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from socratic.core import di
from socratic.model import OrganizationID, User

from . import jwt as jwt_auth
from . import local as local_auth
from .jwt import TokenData

# Security scheme for JWT bearer tokens
bearer_scheme = HTTPBearer(auto_error=False)


class AuthContext(t.NamedTuple):
    """Current authentication context."""

    user: User
    organization_id: OrganizationID
    role: str
    token_data: TokenData


@di.inject
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    token: str | None = Query(None, description="JWT token (for EventSource which can't set headers)"),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> AuthContext:
    """Dependency to get the current authenticated user.

    Accepts token from either:
    - Authorization: Bearer header (preferred)
    - ?token= query parameter (for EventSource/SSE which can't set headers)

    Raises:
        HTTPException 401: If no token provided or token is invalid
        HTTPException 401: If user not found
    """
    # Get token from header or query parameter
    raw_token: str | None = None
    if credentials is not None:
        raw_token = credentials.credentials
    elif token is not None:
        raw_token = token

    if raw_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = jwt_auth.decode_token(raw_token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    with session.begin():
        user = local_auth.get_user(token_data.user_id, session=session)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return AuthContext(
        user=user,
        organization_id=token_data.organization_id,
        role=token_data.role,
        token_data=token_data,
    )


@di.inject
def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    token: str | None = Query(None, description="JWT token (for EventSource which can't set headers)"),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> AuthContext | None:
    """Dependency to optionally get the current user.

    Accepts token from either Authorization header or query parameter.
    Returns None if no valid authentication is provided.
    """
    # Get token from header or query parameter
    raw_token: str | None = None
    if credentials is not None:
        raw_token = credentials.credentials
    elif token is not None:
        raw_token = token

    if raw_token is None:
        return None

    token_data = jwt_auth.decode_token(raw_token)
    if token_data is None:
        return None

    with session.begin():
        user = local_auth.get_user(token_data.user_id, session=session)
        if user is None:
            return None

    return AuthContext(
        user=user,
        organization_id=token_data.organization_id,
        role=token_data.role,
        token_data=token_data,
    )


def require_role(
    *allowed_roles: str,
) -> t.Callable[..., AuthContext]:
    """Dependency factory to require specific roles.

    Usage:
        @router.get("/admin")
        def admin_route(auth: AuthContext = Depends(require_role("educator"))):
            ...
    """

    def check_role(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
        if auth.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{auth.role}' not authorized for this resource",
            )
        return auth

    return check_role


# Convenience dependencies
require_educator = require_role("educator")
require_learner = require_role("learner")
