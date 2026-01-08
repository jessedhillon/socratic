"""Model factory for creating LLM instances."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .config import LLMSecrets, LLMSettings, ModelSettings
from .provider import create_chat_model, ModelConfig, ProviderType


class ModelFactory:
    """Factory for creating configured LLM instances."""

    def __init__(self, settings: LLMSettings, secrets: LLMSecrets) -> None:
        self._settings = settings
        self._secrets = secrets

    def _get_api_key(self, provider: ProviderType) -> str:
        """Get the API key for a provider."""
        if provider == ProviderType.OpenAI:
            if self._secrets.openai_api_key is None:
                raise ValueError("OpenAI API key not configured")
            return self._secrets.openai_api_key.get_secret_value()
        elif provider == ProviderType.Anthropic:
            if self._secrets.anthropic_api_key is None:
                raise ValueError("Anthropic API key not configured")
            return self._secrets.anthropic_api_key.get_secret_value()
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _model_settings_to_config(self, settings: ModelSettings) -> ModelConfig:
        """Convert ModelSettings to ModelConfig."""
        return ModelConfig(
            provider=settings.provider,
            model_name=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout=settings.timeout_seconds,
            max_retries=settings.max_retries,
        )

    def create_model(self, settings: ModelSettings) -> BaseChatModel:
        """Create a chat model from settings."""
        config = self._model_settings_to_config(settings)

        openai_key = None
        anthropic_key = None

        if config.provider == ProviderType.OpenAI:
            openai_key = self._get_api_key(ProviderType.OpenAI)
        elif config.provider == ProviderType.Anthropic:
            anthropic_key = self._get_api_key(ProviderType.Anthropic)

        return create_chat_model(
            config,
            openai_api_key=openai_key,
            anthropic_api_key=anthropic_key,
        )

    def create_dialogue_model(self) -> BaseChatModel:
        """Create the model for Socratic dialogue."""
        return self.create_model(self._settings.models.dialogue)

    def create_evaluation_model(self) -> BaseChatModel:
        """Create the model for rubric evaluation."""
        return self.create_model(self._settings.models.evaluation)

    def create_feedback_model(self) -> BaseChatModel:
        """Create the model for feedback generation."""
        return self.create_model(self._settings.models.feedback)

    @property
    def dialogue_settings(self) -> ModelSettings:
        """Get dialogue model settings."""
        return self._settings.models.dialogue

    @property
    def evaluation_settings(self) -> ModelSettings:
        """Get evaluation model settings."""
        return self._settings.models.evaluation

    @property
    def feedback_settings(self) -> ModelSettings:
        """Get feedback model settings."""
        return self._settings.models.feedback
