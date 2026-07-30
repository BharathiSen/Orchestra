"""Extract long-term user facts from free-text chat turns."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedFact:
    category: str
    key: str
    value: str


_PATTERNS: list[tuple[str, str, str]] = [
    # (regex, category, key) — group(1) is the value
    (r"\bmy name is ([A-Za-z][A-Za-z\-']{1,40})\b", "identity", "name"),
    (r"\bi am ([A-Za-z][A-Za-z\-']{1,40})\b", "identity", "name"),
    (r"\bi(?:'m| am) called ([A-Za-z][A-Za-z\-']{1,40})\b", "identity", "name"),
    (
        r"\bi prefer ([A-Za-z0-9][A-Za-z0-9 \-_+.#]{1,80}?)(?:[.!?,]|$)",
        "preference",
        "preferred",
    ),
    (
        r"\bi like ([A-Za-z0-9][A-Za-z0-9 \-_+.#]{1,80}?)(?:[.!?,]|$)",
        "preference",
        "likes",
    ),
    (
        r"\bmy favorite (?:language|model|tool|framework) is "
        r"([A-Za-z0-9][A-Za-z0-9 \-_+.#]{1,80}?)(?:[.!?,]|$)",
        "preference",
        "favorite",
    ),
    (
        r"\bi(?:'d| would) rather use "
        r"([A-Za-z0-9][A-Za-z0-9 \-_+.#]{1,80}?)(?:[.!?,]|$)",
        "preference",
        "preferred",
    ),
]


def extract_facts(text: str) -> list[ExtractedFact]:
    """Detect durable user facts from a single user message."""
    content = (text or "").strip()
    if not content:
        return []

    found: list[ExtractedFact] = []
    seen: set[tuple[str, str]] = set()
    for pattern, category, key in _PATTERNS:
        match = re.search(pattern, content, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip(" .,:;\"'")
        if len(value) < 2:
            continue
        # Normalize preference keys when we know the topic
        fact_key = key
        lowered = content.lower()
        if key in {"preferred", "favorite", "likes"} and "language" in lowered:
            fact_key = "preferred_language"
        elif key in {"preferred", "favorite"} and "model" in lowered:
            fact_key = "favorite_model"

        identity = (category, fact_key)
        if identity in seen:
            continue
        seen.add(identity)
        found.append(ExtractedFact(category=category, key=fact_key, value=value))
    return found
