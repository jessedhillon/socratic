"""Organization management routes."""

from __future__ import annotations

import datetime

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from socratic.auth import AuthContext, get_current_user, JWTManager, require_educator
from socratic.auth.middleware import get_jwt_manager
from socratic.core import di
from socratic.model import OrganizationID, UserRole
from socratic.storage import organization as org_storage
from socratic.storage import user as user_storage

from ..view.organization import InviteRequest, InviteResponse, OrganizationCreateRequest, OrganizationPublicResponse, \
    OrganizationResponse

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


@router.post("", operation_id="create_organization", status_code=status.HTTP_201_CREATED)
@di.inject
def create_organization(
    request: OrganizationCreateRequest,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> OrganizationResponse:
    """Create a new organization with an initial admin user.

    This is the initial setup endpoint for creating an organization.
    The admin user will be created with the educator role.
    """
    # Check if slug is already taken
    existing = org_storage.get_by_slug(request.slug, session=session)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug already exists",
        )

    # Check if admin email is already registered
    existing_user = user_storage.get_by_email(request.admin_email, session=session)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Admin email already registered",
        )

    # Create organization
    org = org_storage.create(
        {"name": request.name, "slug": request.slug},
        session=session,
    )

    # Create admin user with hashed password
    import bcrypt

    password_hash = bcrypt.hashpw(request.admin_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    admin_user = user_storage.create(
        {
            "email": request.admin_email,
            "name": request.admin_name,
            "password_hash": password_hash,
        },
        session=session,
    )

    # Add admin to organization with educator role
    user_storage.add_to_organization(
        admin_user.user_id,
        org.organization_id,
        UserRole.Educator,
        session=session,
    )

    session.commit()

    return OrganizationResponse(
        organization_id=org.organization_id,
        name=org.name,
        slug=org.slug,
        create_time=org.create_time,
    )


@router.get("/by-slug/{slug}", operation_id="get_organization_by_slug")
@di.inject
def get_organization_by_slug(
    slug: str,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> OrganizationPublicResponse:
    """Get public organization information by slug.

    This endpoint does not require authentication and returns minimal
    organization info for use on login pages.
    """
    with session.begin():
        org = org_storage.get_by_slug(slug, session=session)
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )

        return OrganizationPublicResponse(
            organization_id=org.organization_id,
            name=org.name,
            slug=org.slug,
        )


@router.get("/{organization_id}", operation_id="get_organization")
@di.inject
def get_organization(
    organization_id: OrganizationID,
    auth: AuthContext = Depends(get_current_user),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> OrganizationResponse:
    """Get organization details.

    Users can only view their own organization.
    """
    if auth.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access other organizations",
        )

    org = org_storage.get(organization_id, session=session)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return OrganizationResponse(
        organization_id=org.organization_id,
        name=org.name,
        slug=org.slug,
        create_time=org.create_time,
    )


@router.post("/{organization_id}/invite", operation_id="invite_user")
@di.inject
def invite_user(
    organization_id: OrganizationID,
    request: InviteRequest,
    auth: AuthContext = Depends(require_educator),
    session: Session = Depends(di.Manage["storage.persistent.session"]),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> InviteResponse:
    """Generate an invite token for a new user.

    Only educators can invite users to their organization.
    """
    if auth.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot invite to other organizations",
        )

    # Validate role
    if request.role not in ("educator", "learner"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'educator' or 'learner'",
        )

    # Check if email is already registered
    existing = user_storage.get_by_email(request.email, session=session)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create invite token (valid for 7 days)
    # Note: In production, you might want to store invites in DB for tracking
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=7)
    invite_payload = {
        "type": "invite",
        "email": request.email,
        "org": str(organization_id),
        "role": request.role,
        "inviter": str(auth.user.user_id),
        "exp": int(expires_at.timestamp()),
    }
    invite_token = pyjwt.encode(invite_payload, jwt_manager.secret_key, algorithm=jwt_manager.algorithm)

    return InviteResponse(
        invite_token=invite_token,
        email=request.email,
        organization_id=organization_id,
        role=request.role,
        expires_at=expires_at,
    )
