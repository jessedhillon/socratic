"""View models for prompt templates."""

from __future__ import annotations

import datetime

from socratic.model import BaseModel, PromptTemplateID


class TemplateCreateRequest(BaseModel):
    """Request to create or update a template."""

    name: str
    content: str
    description: str | None = None


class TemplateResponse(BaseModel):
    """Response for a single template."""

    template_id: PromptTemplateID
    name: str
    version: int
    content: str
    description: str | None
    is_active: bool
    create_time: datetime.datetime
    update_time: datetime.datetime


class TemplateListResponse(BaseModel):
    """Response for listing templates."""

    templates: list[TemplateResponse]
