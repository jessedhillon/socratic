"""Authentication routes."""

from __future__ import annotations

import datetime

import jwt as pyjwt
import pydantic as p
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from socratic.auth import AuthContext, get_current_user, jwt
from socratic.auth import local as local_auth
from socratic.core import di
from socratic.model import OrganizationID
from socratic.storage import organization as org_storage
from socratic.storage import user as user_storage

from ..view.auth import LoginRequest, LoginResponse, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", operation_id="login")
@di.inject
def login(
    request: LoginRequest,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
    expire_minutes: int = Depends(di.Provide["config.web.socratic.auth.access_token_expire_minutes"]),
) -> LoginResponse:
    """Authenticate a user and return access token."""
    with session.begin():
        result = local_auth.authenticate(request.email, request.password, session=session)

        if not result.success or result.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=result.error or "Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get user's organization membership
        memberships = user_storage.get_memberships(result.user.user_id, session=session)
        if not memberships:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no organization membership",
            )

        # Use first membership (users could have multiple in future)
        membership = memberships[0]

    # Create access token
    expires_delta = datetime.timedelta(minutes=expire_minutes)
    expires_at = datetime.datetime.now(datetime.UTC) + expires_delta

    access_token = jwt.create_access_token(
        user_id=result.user.user_id,
        organization_id=membership.organization_id,
        role=membership.role.value,
        expires_delta=expires_delta,
    )

    return LoginResponse(
        user=UserResponse(
            user_id=result.user.user_id,
            email=result.user.email,
            name=result.user.name,
            organization_id=membership.organization_id,
            role=membership.role.value,
        ),
        token=TokenResponse(
            access_token=access_token,
            expires_at=expires_at,
        ),
    )


@router.post("/register", operation_id="register", status_code=status.HTTP_201_CREATED)
@di.inject
def register(
    request: RegisterRequest,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
    secret: p.Secret[str] = Depends(di.Provide["secrets.auth.jwt"]),
    algorithm: str = Depends(di.Provide["config.web.socratic.auth.jwt_algorithm"]),
    expire_minutes: int = Depends(di.Provide["config.web.socratic.auth.access_token_expire_minutes"]),
) -> LoginResponse:
    """Register a new user with an invite token."""
    # Decode and validate invite token
    try:
        payload = pyjwt.decode(
            request.invite_token,
            secret.get_secret_value(),
            algorithms=[algorithm],
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite token has expired",
        ) from None
    except pyjwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invite token",
        ) from None

    # Validate token type
    if payload.get("type") != "invite":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid invite token",
        )

    # Validate email matches invite
    if payload.get("email") != request.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email does not match invite",
        )

    organization_id = OrganizationID(payload["org"])
    role = payload["role"]

    with session.begin():
        # Verify organization exists
        org = org_storage.get(organization_id, session=session)
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization not found",
            )

        # Register user
        result = local_auth.register(
            email=request.email,
            password=request.password,
            name=request.name,
            organization_id=organization_id,
            role=role,
            session=session,
        )

        if not result.success or result.user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or "Registration failed",
            )

    # Create access token
    expires_delta = datetime.timedelta(minutes=expire_minutes)
    expires_at = datetime.datetime.now(datetime.UTC) + expires_delta

    access_token = jwt.create_access_token(
        user_id=result.user.user_id,
        organization_id=organization_id,
        role=role,
        expires_delta=expires_delta,
    )

    return LoginResponse(
        user=UserResponse(
            user_id=result.user.user_id,
            email=result.user.email,
            name=result.user.name,
            organization_id=organization_id,
            role=role,
        ),
        token=TokenResponse(
            access_token=access_token,
            expires_at=expires_at,
        ),
    )


@router.post("/logout", operation_id="logout")
def logout(
    auth: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Logout the current user.

    Note: With JWT tokens, logout is primarily handled client-side
    by discarding the token. This endpoint is provided for API consistency.
    """
    # In a production system, you might want to:
    # - Add token to a blacklist
    # - Invalidate refresh tokens
    # - Log the logout event
    return {"message": "Logged out successfully"}


@router.get("/me", operation_id="get_current_user")
def get_me(
    auth: AuthContext = Depends(get_current_user),
) -> UserResponse:
    """Get the current authenticated user."""
    return UserResponse(
        user_id=auth.user.user_id,
        email=auth.user.email,
        name=auth.user.name,
        organization_id=auth.organization_id,
        role=auth.role,
    )
