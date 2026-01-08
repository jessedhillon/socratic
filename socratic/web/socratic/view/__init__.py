"""View models for the Socratic web application."""

__all__ = [
    # Auth views
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "UserResponse",
    "TokenResponse",
    # Organization views
    "OrganizationResponse",
    "OrganizationCreateRequest",
    "InviteRequest",
    "InviteResponse",
]

from .auth import LoginRequest, LoginResponse, RegisterRequest, TokenResponse, UserResponse
from .organization import InviteRequest, InviteResponse, OrganizationCreateRequest, OrganizationResponse
