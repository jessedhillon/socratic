"""View models for authentication endpoints."""

from __future__ import annotations

import datetime

from pydantic import EmailStr

from socratic.model import BaseModel, OrganizationID, UserID


class LoginRequest(BaseModel):
    """Request body for login."""

    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Request body for registration."""

    email: EmailStr
    password: str
    name: str
    invite_token: str  # Token from organization invite


class TokenResponse(BaseModel):
    """Response containing access token."""

    access_token: str
    token_type: str = "bearer"
    expires_at: datetime.datetime


class UserResponse(BaseModel):
    """Response containing user information."""

    user_id: UserID
    email: EmailStr
    name: str
    organization_id: OrganizationID
    role: str


class LoginResponse(BaseModel):
    """Response for successful login."""

    user: UserResponse
    token: TokenResponse
