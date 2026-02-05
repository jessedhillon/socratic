"""Prompt template routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from socratic.core import di
from socratic.model import PromptTemplateID
from socratic.storage import flight as flight_storage

from ..view import TemplateCreateRequest, TemplateListView, TemplateView

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", operation_id="list_templates")
@di.inject
def list_templates(
    name: str | None = None,
    is_active: bool | None = None,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> TemplateListView:
    """List prompt templates.

    Optionally filter by name or active status.
    """
    with session.begin():
        templates = flight_storage.find_templates(
            name=name,
            is_active=is_active,
            session=session,
        )
        return TemplateListView.from_model(templates)


@router.get("/{template_id}", operation_id="get_template")
@di.inject
def get_template(
    template_id: PromptTemplateID,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> TemplateView:
    """Get a specific template by ID."""
    with session.begin():
        template = flight_storage.get_template(template_id, session=session)
        if template is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            )
        return TemplateView.from_model(template)


@router.post("", operation_id="create_template", status_code=status.HTTP_201_CREATED)
@di.inject
def create_template(
    request: TemplateCreateRequest,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> TemplateView:
    """Create a new template.

    If a template with the same name exists, creates a new version.
    """
    with session.begin():
        template = flight_storage.create_template(
            name=request.name,
            content=request.content,
            description=request.description,
            session=session,
        )
        return TemplateView.from_model(template)


@router.patch("/{template_id}", operation_id="update_template")
@di.inject
def update_template(
    template_id: PromptTemplateID,
    description: str | None = None,
    is_active: bool | None = None,
    session: Session = Depends(di.Manage["storage.persistent.session"]),
) -> TemplateView:
    """Update a template's metadata.

    Note: Content changes require creating a new version via POST.
    """
    with session.begin():
        try:
            flight_storage.update_template(
                template_id,
                description=description if description is not None else flight_storage.NotSet(),
                is_active=is_active if is_active is not None else flight_storage.NotSet(),
                session=session,
            )
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found",
            ) from None

        template = flight_storage.get_template(template_id, session=session)
        assert template is not None
        return TemplateView.from_model(template)
