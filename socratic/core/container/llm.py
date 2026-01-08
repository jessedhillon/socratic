"""LLM container for dependency injection."""

from __future__ import annotations

from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration, Factory, Provider, Singleton

from socratic.llm import LLMSecrets, LLMSettings, ModelFactory


class LLMContainer(DeclarativeContainer):
    """Container for LLM services."""

    config: Configuration = Configuration()
    secrets: Configuration = Configuration()

    settings: Provider[LLMSettings] = Singleton(
        LLMSettings,
    )

    llm_secrets: Provider[LLMSecrets] = Singleton(
        LLMSecrets,
        openai_api_key=secrets.openai_api_key,
        anthropic_api_key=secrets.anthropic_api_key,
    )

    model_factory: Provider[ModelFactory] = Factory(
        ModelFactory,
        settings=settings,
        secrets=llm_secrets,
    )
