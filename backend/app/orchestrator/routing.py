"""Heuristic routing: simple Q&A vs full Orchestra pipeline."""

from __future__ import annotations

import re

SIMPLE_PATTERNS = [
    r"\bwhat(?:'s| is) my name\b",
    r"\bwho am i\b",
    r"\bwhat do you (?:know|remember) about me\b",
    r"\b(hi|hello|hey|thanks|thank you)\b",
    r"\bwhat(?:'s| is) \d+\s*[\+\-\*/]\s*\d+\b",
    r"\bprefer(?:red)? language\b",
]

FULL_PATTERNS = [
    r"\b(write|draft|compose|essay|blog|article|report)\b",
    r"\b(compare|contrast|analyze|analyse|evaluate|critique)\b",
    r"\b(implement|design|architect|refactor)\b",
    r"\b(step[- ]by[- ]step|detailed|comprehensive|in depth)\b",
    r"\b(review|improve|rewrite)\b",
]


def classify_route(question: str) -> str:
    """Return 'simple' or 'full' for Orchestra conditional edges."""
    q = (question or "").strip().lower()
    if not q:
        return "simple"

    for pattern in FULL_PATTERNS:
        if re.search(pattern, q):
            return "full"

    for pattern in SIMPLE_PATTERNS:
        if re.search(pattern, q):
            return "simple"

    # Short factual / preference questions → simple (saves Writer+Reviewer calls)
    words = q.split()
    if len(words) <= 18 and not re.search(r"[?]{2,}", q):
        return "simple"

    return "full"
