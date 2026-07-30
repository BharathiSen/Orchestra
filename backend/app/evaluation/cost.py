"""Model pricing + cost calculation (USD)."""

from __future__ import annotations

from decimal import Decimal

# Approximate public list prices (USD per 1M tokens). Used for observability demos.
# Update when provider pricing changes.
MODEL_PRICING_PER_MILLION: dict[str, dict[str, float]] = {
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "gemma2-9b-it": {"input": 0.20, "output": 0.20},
    "llama3.2": {"input": 0.0, "output": 0.0},  # local
    "mistral": {"input": 0.0, "output": 0.0},
    "gemma2:9b": {"input": 0.0, "output": 0.0},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
}

_DEFAULT = {"input": 0.10, "output": 0.20}


def estimate_tokens(text: str) -> int:
    """Rough token estimate when provider usage is unavailable (~4 chars/token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def price_for_model(model: str) -> dict[str, float]:
    key = (model or "").strip()
    return MODEL_PRICING_PER_MILLION.get(key, _DEFAULT)


def calculate_cost_usd(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    pricing = price_for_model(model)
    cost = (input_tokens / 1_000_000.0) * pricing["input"] + (
        output_tokens / 1_000_000.0
    ) * pricing["output"]
    return Decimal(str(round(cost, 8)))
