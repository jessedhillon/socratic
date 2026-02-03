"""LLM container for dependency injection."""

from __future__ import annotations

import pydantic as p
from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration, Provider, Singleton
from langchain_core.language_models import BaseChatModel

from socratic.llm import LLMSecrets, ModelSettings, OpenAISpeechService, ProviderType, SpeechService, \
    TranscriptionService, WhisperTranscriptionService


def create_chat_model(
    config: ModelSettings,
    *,
    openai_api_key: p.Secret[str] | None = None,
    anthropic_api_key: p.Secret[str] | None = None,
) -> BaseChatModel:
    """Create a LangChain chat model from configuration.

    Args:
        config: Model configuration
        openai_api_key: OpenAI API key (required for OpenAI models)
        anthropic_api_key: Anthropic API key (required for Anthropic models)

    Returns:
        Configured LangChain chat model
    """
    if config.provider == ProviderType.OpenAI:
        from langchain_openai import ChatOpenAI

        if openai_api_key is None:
            raise ValueError("OpenAI API key required for OpenAI provider")

        return ChatOpenAI(
            model=config.model,
            temperature=config.temperature,
            max_completion_tokens=config.max_tokens,
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
            api_key=p.SecretStr(openai_api_key.get_secret_value()),
        )
    elif config.provider == ProviderType.Anthropic:
        from langchain_anthropic import ChatAnthropic

        if anthropic_api_key is None:
            raise ValueError("Anthropic API key required for Anthropic provider")

        return ChatAnthropic(
            model_name=config.model,
            temperature=config.temperature,
            max_tokens_to_sample=config.max_tokens,
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
            api_key=p.SecretStr(anthropic_api_key.get_secret_value()),
            stop=None,
        )
    else:
        raise ValueError(f"Unsupported provider: {config.provider}")


def create_model(settings: ModelSettings, secrets: LLMSecrets) -> BaseChatModel:
    """Create a chat model from settings."""
    return create_chat_model(
        settings,
        openai_api_key=secrets.openai_api_key,
        anthropic_api_key=secrets.anthropic_api_key,
    )


class LLMContainer(DeclarativeContainer):
    """Container for LLM services."""

    config: Configuration = Configuration()
    openai_secrets: Configuration = Configuration()
    anthropic_secrets: Configuration = Configuration()

    llm_secrets: Provider[LLMSecrets] = Singleton(
        LLMSecrets,
        openai_api_key=openai_secrets.secret_key,
        anthropic_api_key=anthropic_secrets.api_key,
    )

    dialogue_model: Provider[BaseChatModel] = Singleton(
        create_model, settings=config.models.dialogue.as_(ModelSettings), secrets=llm_secrets
    )

    evaluation_model: Provider[BaseChatModel] = Singleton(
        create_model, settings=config.models.evaluation.as_(ModelSettings), secrets=llm_secrets
    )

    feedback_model: Provider[BaseChatModel] = Singleton(
        create_model, settings=config.models.feedback.as_(ModelSettings), secrets=llm_secrets
    )

    transcription: Provider[TranscriptionService] = Singleton(
        WhisperTranscriptionService,
        api_key=openai_secrets.secret_key,
    )

    speech: Provider[SpeechService] = Singleton(
        OpenAISpeechService,
        api_key=openai_secrets.secret_key,
    )
