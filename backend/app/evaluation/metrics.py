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
