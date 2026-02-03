"""LLM container for dependency injection."""

from __future__ import annotations

import pydantic as p
from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Configuration, Provider, Singleton
from langchain_core.language_models import BaseChatModel

from socratic.core.config.secrets import AnthropicSecrets, OpenAISecrets
from socratic.llm import ModelSettings, OpenAISpeechService, ProviderType, SpeechService, TranscriptionService, \
    WhisperTranscriptionService


def create_chat_model(
    config: ModelSettings,
    openai_secrets: OpenAISecrets | None,
    anthropic_secrets: AnthropicSecrets | None,
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

        if openai_secrets is None:
            raise ValueError("OpenAI API key required for OpenAI provider")

        return ChatOpenAI(
            model=config.model,
            temperature=config.temperature,
            max_completion_tokens=config.max_tokens,
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
            api_key=p.SecretStr(openai_secrets.secret_key.get_secret_value()),
        )
    elif config.provider == ProviderType.Anthropic:
        from langchain_anthropic import ChatAnthropic

        if anthropic_secrets is None:
            raise ValueError("Anthropic API key required for Anthropic provider")

        return ChatAnthropic(
            model_name=config.model,
            temperature=config.temperature,
            max_tokens_to_sample=config.max_tokens,
            timeout=config.timeout_seconds,
            max_retries=config.max_retries,
            api_key=p.SecretStr(anthropic_secrets.api_key.get_secret_value()),
            stop=None,
        )
    else:
        raise ValueError(f"Unsupported provider: {config.provider}")


class LLMContainer(DeclarativeContainer):
    """Container for LLM services."""

    config: Configuration = Configuration()
    secrets: Configuration = Configuration()

    dialogue_model: Provider[BaseChatModel] = Singleton(
        create_chat_model,
        config=config.models.dialogue.as_(ModelSettings),
        openai_secrets=secrets.openai.as_(OpenAISecrets),
        anthropic_secrets=secrets.anthropic.as_(AnthropicSecrets),
    )

    evaluation_model: Provider[BaseChatModel] = Singleton(
        create_chat_model,
        config=config.models.evaluation.as_(ModelSettings),
        openai_secrets=secrets.openai.as_(OpenAISecrets),
        anthropic_secrets=secrets.anthropic.as_(AnthropicSecrets),
    )

    feedback_model: Provider[BaseChatModel] = Singleton(
        create_chat_model,
        config=config.models.feedback.as_(ModelSettings),
        openai_secrets=secrets.openai.as_(OpenAISecrets),
        anthropic_secrets=secrets.anthropic.as_(AnthropicSecrets),
    )

    transcription: Provider[TranscriptionService] = Singleton(
        WhisperTranscriptionService,
        openai_secrets=secrets.openai.as_(OpenAISecrets),
        anthropic_secrets=secrets.anthropic.as_(AnthropicSecrets),
    )

    speech: Provider[SpeechService] = Singleton(
        OpenAISpeechService,
        openai_secrets=secrets.openai.as_(OpenAISecrets),
        anthropic_secrets=secrets.anthropic.as_(AnthropicSecrets),
    )
