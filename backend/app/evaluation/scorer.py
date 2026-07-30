"""Lightweight heuristic scorers — NOT LLM-as-a-judge."""

from __future__ import annotations

import re
from typing import Any


def score_execution(
    *,
    prompt: str,
    response: str,
    retrieved_chunks: list[dict[str, Any]] | None = None,
    had_error: bool = False,
    latency_ms: int = 0,
) -> dict[str, Any]:
    """Return simple quantitative/qualitative scores for the dashboard."""
    answer = (response or "").strip()
    question = (prompt or "").strip()
    chunks = retrieved_chunks or []

    if had_error or not answer:
        return {
            "correctness": 0.0,
            "relevance": 0.0,
            "groundedness": 0.0,
            "hallucination_risk": 1.0 if not had_error else 0.5,
            "latency_ok": latency_ms < 15000,
            "notes": "Empty or failed response",
        }

    q_tokens = set(_tokens(question))
    a_tokens = set(_tokens(answer))
    overlap = len(q_tokens & a_tokens) / max(1, len(q_tokens))
    relevance = min(1.0, 0.35 + overlap)

    groundedness = 0.5
    hallucination_risk = 0.4
    if chunks:
        chunk_text = " ".join(str(c.get("content") or "") for c in chunks).lower()
        chunk_tokens = set(_tokens(chunk_text))
        share = len(a_tokens & chunk_tokens) / max(1, len(a_tokens))
        groundedness = min(1.0, 0.4 + share)
        hallucination_risk = max(0.05, 1.0 - groundedness)
    else:
        # No retrieval — groundedness N/A; mild hallucination risk for long assertive answers
        groundedness = 0.0
        hallucination_risk = 0.25 if len(answer) < 400 else 0.45

    correctness = round((relevance * 0.55 + (1.0 - hallucination_risk) * 0.45), 3)
    return {
        "correctness": correctness,
        "relevance": round(relevance, 3),
        "groundedness": round(groundedness, 3),
        "hallucination_risk": round(hallucination_risk, 3),
        "latency_ok": latency_ms < 15000,
        "notes": "Heuristic scores (no LLM judge)",
    }


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]{3,}", (text or "").lower())
