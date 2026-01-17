"""LLM container for dependency injection."""

from __future__ import annotations

from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration, Factory, Provider, Singleton
from langchain_core.language_models import BaseChatModel

from socratic.llm import LLMSecrets, LLMSettings, ModelFactory, TranscriptionService, WhisperTranscriptionService


def provide_dialogue_model(factory: ModelFactory) -> BaseChatModel:
    """Create the dialogue model using the factory."""
    return factory.create_dialogue_model()


class LLMContainer(DeclarativeContainer):
    """Container for LLM services."""

    config: Configuration = Configuration()
    secrets: Configuration = Configuration()

    settings: Provider[LLMSettings] = Singleton(
        LLMSettings,
    )

    llm_secrets: Provider[LLMSecrets] = Singleton(
        LLMSecrets,
        openai_api_key=secrets.secret_key,
        anthropic_api_key=None,
    )

    model_factory: Provider[ModelFactory] = Factory(
        ModelFactory,
        settings=settings,
        secrets=llm_secrets,
    )

    dialogue_model: Provider[BaseChatModel] = Singleton(
        provide_dialogue_model,
        factory=model_factory,
    )

    transcription_service: Provider[TranscriptionService] = Singleton(
        WhisperTranscriptionService,
        api_key=secrets.secret_key,
    )
