"""Fixtures for LLM tests."""

from __future__ import annotations

import jinja2
import pytest

from socratic.core import SocraticContainer


@pytest.fixture(scope="session")
def llm_env(container: SocraticContainer) -> jinja2.Environment:
    """Provide the LLM Jinja2 environment from the DI container."""
    return container.template().llm()
