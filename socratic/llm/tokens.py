"""Token counting and cost estimation utilities."""

from __future__ import annotations

import decimal
from dataclasses import dataclass

# Pricing per 1M tokens (as of 2024)
MODEL_PRICING: dict[str, tuple[decimal.Decimal, decimal.Decimal]] = {
    # (input_price, output_price) per 1M tokens
    # OpenAI models
    "gpt-4o": (decimal.Decimal("2.50"), decimal.Decimal("10.00")),
    "gpt-4o-mini": (decimal.Decimal("0.15"), decimal.Decimal("0.60")),
    "gpt-4-turbo": (decimal.Decimal("10.00"), decimal.Decimal("30.00")),
    "gpt-4": (decimal.Decimal("30.00"), decimal.Decimal("60.00")),
    "gpt-3.5-turbo": (decimal.Decimal("0.50"), decimal.Decimal("1.50")),
    # Anthropic models
    "claude-3-5-sonnet-20241022": (decimal.Decimal("3.00"), decimal.Decimal("15.00")),
    "claude-3-5-haiku-20241022": (decimal.Decimal("1.00"), decimal.Decimal("5.00")),
    "claude-3-opus-20240229": (decimal.Decimal("15.00"), decimal.Decimal("75.00")),
    "claude-3-sonnet-20240229": (decimal.Decimal("3.00"), decimal.Decimal("15.00")),
    "claude-3-haiku-20240307": (decimal.Decimal("0.25"), decimal.Decimal("1.25")),
}


@dataclass
class CostEstimate:
    """Cost estimate for token usage."""

    input_tokens: int
    output_tokens: int
    model: str
    input_cost: decimal.Decimal
    output_cost: decimal.Decimal

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def total_cost(self) -> decimal.Decimal:
        return self.input_cost + self.output_cost


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> CostEstimate:
    """Estimate cost for token usage.

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost estimate with breakdown
    """
    if model not in MODEL_PRICING:
        # Unknown model, return zero cost
        return CostEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            input_cost=decimal.Decimal("0"),
            output_cost=decimal.Decimal("0"),
        )

    input_price, output_price = MODEL_PRICING[model]
    input_cost = (decimal.Decimal(input_tokens) / 1_000_000) * input_price
    output_cost = (decimal.Decimal(output_tokens) / 1_000_000) * output_price

    return CostEstimate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model,
        input_cost=input_cost,
        output_cost=output_cost,
    )


def estimate_tokens(text: str) -> int:
    """Rough token estimation without API call.

    Uses the approximation of ~4 characters per token for English text.
    This is a rough estimate and should not be used for precise calculations.
    """
    return len(text) // 4 + 1
