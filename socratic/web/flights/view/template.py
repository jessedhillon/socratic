"""View models for prompt templates."""

from __future__ import annotations

import datetime

from socratic.model import BaseModel, PromptTemplate, PromptTemplateID


class TemplateCreateRequest(BaseModel):
    """Request to create or update a template."""

    name: str
    content: str
    description: str | None = None


class TemplateView(BaseModel):
    """View for a single template."""

    template_id: PromptTemplateID
    name: str
    version: int
    content: str
    description: str | None
    is_active: bool
    create_time: datetime.datetime
    update_time: datetime.datetime

    @classmethod
    def from_model(cls, template: PromptTemplate) -> TemplateView:
        return cls(
            template_id=template.template_id,
            name=template.name,
            version=template.version,
            content=template.content,
            description=template.description,
            is_active=template.is_active,
            create_time=template.create_time,
            update_time=template.update_time,
        )


class TemplateListView(BaseModel):
    """Response for listing templates."""

    templates: list[TemplateView]
