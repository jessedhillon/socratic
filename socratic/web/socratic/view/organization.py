"""View models for organization endpoints."""

from __future__ import annotations

import datetime

from pydantic import EmailStr

from socratic.model import BaseModel, OrganizationID


class OrganizationCreateRequest(BaseModel):
    """Request body for creating an organization."""

    name: str
    slug: str
    admin_email: EmailStr
    admin_password: str
    admin_name: str


class OrganizationResponse(BaseModel):
    """Response containing organization information."""

    organization_id: OrganizationID
    name: str
    slug: str
    create_time: datetime.datetime


class OrganizationPublicResponse(BaseModel):
    """Public response containing minimal organization information.

    Used for unauthenticated endpoints like login page validation.
    """

    organization_id: OrganizationID
    name: str
    slug: str


class InviteRequest(BaseModel):
    """Request body for inviting a user to an organization."""

    email: EmailStr
    role: str  # "educator" or "learner"


class InviteResponse(BaseModel):
    """Response containing invite token."""

    invite_token: str
    email: EmailStr
    organization_id: OrganizationID
    role: str
    expires_at: datetime.datetime
