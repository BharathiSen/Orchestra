"""Fixed chat cases and percentile math for the latency harness.

The cases exercise pipeline selection. They do not judge answer quality against
a live model: the default runner uses the test stub. A result file must say
which provider produced it.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    category: str
    message: str
    enable_orchestra: bool = False
    enable_tools: bool = False
    # Expected Orchestra route after classification. None for non-orchestra.
    expect_route: str | None = None
    notes: str = ""


# Stable labels. Wording is part of the contract with classify_route.
CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        case_id="direct_chat",
        category="direct",
        message="Hello there",
        notes="Single streaming completion. No tools, no orchestra.",
    ),
    BenchmarkCase(
        case_id="direct_edge_short",
        category="edge",
        message="?",
        notes="Short input that should still complete.",
    ),
    BenchmarkCase(
        case_id="orchestra_simple",
        category="orchestra_simple",
        message="What is my name?",
        enable_orchestra=True,
        expect_route="simple",
        notes="Planner and research, then a streamed fast answer. Writer and reviewer skipped.",
    ),
    BenchmarkCase(
        case_id="orchestra_full",
        category="orchestra_full",
        message="Write a detailed blog comparing Redis and Postgres for session storage.",
        enable_orchestra=True,
        expect_route="full",
        notes="Planner, research, writer, then a streamed reviewer.",
    ),
    BenchmarkCase(
        case_id="tools_arithmetic",
        category="tools",
        message="What is 17 + 25?",
        enable_tools=True,
        notes="Tools graph. The answer node still emits precomputed slices.",
    ),
    BenchmarkCase(
        case_id="rag_personal_skips_kb",
        category="rag",
        message="What is my name?",
        enable_orchestra=True,
        expect_route="simple",
        notes=(
            "Personal questions skip knowledge-base retrieval inside research. "
            "A corpus-backed groundedness check needs pgvector and uploaded chunks; "
            "this case only checks that the personal path still completes."
        ),
    ),
)


def percentile(values: list[float], pct: float) -> float | None:
    """Linear percentile. Returns None for an empty sample."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return float(ordered[low] * (1.0 - weight) + ordered[high] * weight)


def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate one case. `samples` are successful measured turns only."""
    def series(key: str) -> list[float]:
        out: list[float] = []
        for sample in samples:
            value = sample.get(key)
            if isinstance(value, (int, float)):
                out.append(float(value))
        return out

    latency = series("latency_ms")
    ttft = series("ttft_delivered_ms")
    tokens = series("total_tokens")
    cost = series("total_cost_usd")
    return {
        "runs": len(samples),
        "latency_ms": {
            "p50": percentile(latency, 50),
            "p95": percentile(latency, 95),
            "min": min(latency) if latency else None,
            "max": max(latency) if latency else None,
        },
        "ttft_delivered_ms": {
            "p50": percentile(ttft, 50),
            "p95": percentile(ttft, 95),
        },
        "total_tokens": {
            "p50": percentile(tokens, 50),
        },
        "total_cost_usd": {
            "p50": percentile(cost, 50),
            "mean": statistics.fmean(cost) if cost else None,
        },
    }
