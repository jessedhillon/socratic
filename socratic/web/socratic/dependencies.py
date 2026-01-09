"""FastAPI dependency providers for the Socratic web application."""

from __future__ import annotations

import jinja2
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from socratic.core import di


@di.inject
def get_session(
    session: Session = di.Provide["storage.persistent.session"],
) -> Session:
    """Get database session from DI container."""
    return session


@di.inject
def get_dialogue_model(
    model: BaseChatModel = di.Provide["llm.dialogue_model"],
) -> BaseChatModel:
    """Get the dialogue LLM model from DI container."""
    return model


@di.inject
def get_llm_env(
    env: jinja2.Environment = di.Provide["template.llm"],
) -> jinja2.Environment:
    """Get the Jinja2 environment for LLM templates from DI container."""
    return env
