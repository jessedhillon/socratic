"""LLM provider abstraction using LangChain."""

from __future__ import annotations

import enum
import typing as t
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import SecretStr


class ProviderType(enum.Enum):
    """Supported LLM providers."""

    OpenAI = "openai"
    Anthropic = "anthropic"


class MessageRole(enum.Enum):
    """Role of a message in a conversation."""

    System = "system"
    User = "user"
    Assistant = "assistant"


@dataclass
class LLMMessage:
    """A message in an LLM conversation."""

    role: MessageRole
    content: str

    def to_langchain(self) -> BaseMessage:
        """Convert to LangChain message format."""
        if self.role == MessageRole.System:
            return SystemMessage(content=self.content)
        elif self.role == MessageRole.User:
            return HumanMessage(content=self.content)
        elif self.role == MessageRole.Assistant:
            return AIMessage(content=self.content)
        else:
            return HumanMessage(content=self.content)


@dataclass
class LLMResponse:
    """Response from an LLM."""

    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ModelConfig:
    """Configuration for a specific model."""

    provider: ProviderType
    model_name: str
    temperature: float = 1.0
    max_tokens: int = 4096
    timeout: float = 60.0
    max_retries: int = 3


def messages_to_langchain(messages: list[LLMMessage]) -> list[BaseMessage]:
    """Convert a list of LLMMessages to LangChain messages."""
    return [m.to_langchain() for m in messages]


def create_chat_model(
    config: ModelConfig,
    *,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
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
            model=config.model_name,
            temperature=config.temperature,
            max_completion_tokens=config.max_tokens,
            timeout=config.timeout,
            max_retries=config.max_retries,
            api_key=SecretStr(openai_api_key),
        )
    elif config.provider == ProviderType.Anthropic:
        from langchain_anthropic import ChatAnthropic

        if anthropic_api_key is None:
            raise ValueError("Anthropic API key required for Anthropic provider")

        return ChatAnthropic(
            model_name=config.model_name,
            temperature=config.temperature,
            max_tokens_to_sample=config.max_tokens,
            timeout=config.timeout,
            max_retries=config.max_retries,
            api_key=SecretStr(anthropic_api_key),
            stop=None,
        )
    else:
        raise ValueError(f"Unsupported provider: {config.provider}")


@dataclass
class TokenUsage:
    """Token usage tracking."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, input_tokens: int, output_tokens: int) -> None:
        """Add token counts."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens


@dataclass
class TokenTracker:
    """Tracks token usage across multiple calls."""

    usage: TokenUsage = field(default_factory=TokenUsage)

    def track_response(self, response: t.Any) -> None:
        """Track tokens from a LangChain response."""
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            metadata = response.usage_metadata
            self.usage.add(
                metadata.get("input_tokens", 0),
                metadata.get("output_tokens", 0),
            )

    def reset(self) -> None:
        """Reset tracking."""
        self.usage = TokenUsage()
