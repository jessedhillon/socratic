"""LLM provider types."""

from __future__ import annotations

import enum


class ProviderType(enum.Enum):
    """Supported LLM providers."""

    OpenAI = "openai"
    Anthropic = "anthropic"
