"""LLM configuration settings."""

from __future__ import annotations

import pydantic as p
import pydantic_settings as ps

from .provider import ProviderType


class ModelSettings(ps.BaseSettings):
    """Settings for a specific model."""

    provider: ProviderType = ProviderType.OpenAI
    model: str = "gpt-4o"
    max_tokens: int = 4096
    temperature: float = 1.0
    max_retries: int = 3
    timeout_seconds: float = 60.0


class AssessmentModels(ps.BaseSettings):
    """Model configuration for different assessment tasks."""

    # Model for conducting the Socratic dialogue
    dialogue: ModelSettings = ModelSettings(
        provider=ProviderType.OpenAI,
        model="gpt-4o",
        max_tokens=2048,
        temperature=0.7,
    )

    # Model for evaluating learner responses against rubric
    evaluation: ModelSettings = ModelSettings(
        provider=ProviderType.OpenAI,
        model="gpt-4o",
        max_tokens=4096,
        temperature=0.3,
    )

    # Model for generating feedback summaries
    feedback: ModelSettings = ModelSettings(
        provider=ProviderType.OpenAI,
        model="gpt-4o-mini",
        max_tokens=1024,
        temperature=0.5,
    )


class RateLimitSettings(ps.BaseSettings):
    """Rate limiting configuration."""

    requests_per_minute: int = 500
    tokens_per_minute: int = 150000
    concurrent_requests: int = 25


class CostSettings(ps.BaseSettings):
    """Cost tracking and alerting."""

    enable_tracking: bool = True
    alert_threshold_usd: float = 50.0
    daily_budget_usd: float | None = None


class LLMSettings(ps.BaseSettings):
    """Root LLM configuration."""

    # Default provider for new configurations
    default_provider: ProviderType = ProviderType.OpenAI

    # Task-specific model configurations
    models: AssessmentModels = AssessmentModels()

    # Rate limiting
    rate_limits: RateLimitSettings = RateLimitSettings()

    # Cost management
    cost: CostSettings = CostSettings()


class LLMSecrets(ps.BaseSettings):
    """LLM API secrets."""

    openai_api_key: p.Secret[str] | None = None
    anthropic_api_key: p.Secret[str] | None = None
