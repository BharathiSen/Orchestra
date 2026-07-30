"""Production-oriented metric helpers (aggregations + rates)."""

from __future__ import annotations

from typing import Any


def success_rate(total: int, successes: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * successes / total, 2)


def average(values: list[float | int]) -> float:
    if not values:
        return 0.0
    return round(sum(float(v) for v in values) / len(values), 2)


def sum_decimal_as_float(values: list[Any]) -> float:
    total = 0.0
    for v in values:
        total += float(v or 0)
    return round(total, 6)


def tool_success_rate(tool_events: list[dict[str, Any]]) -> float | None:
    results = [e for e in tool_events if e.get("type") == "tool_result"]
    if not results:
        return None
    ok = sum(1 for e in results if e.get("status") != "error")
    return success_rate(len(results), ok)
