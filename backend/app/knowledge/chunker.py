"""Boundary-aware chunking for retrieval."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    metadata: dict


def chunk_text(
    text: str,
    *,
    chunk_size: int = 400,
    overlap: int = 80,
) -> list[TextChunk]:
    """
    Chunk by paragraph/sentence units, then merge into token-sized windows.

    Defaults target the user-requested range:
    - chunk_size: ~400 tokens
    - overlap: ~80 tokens
    Chunks are emitted on unit boundaries so they do not split words.
    """
    if not text or not text.strip():
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    units = _build_sentence_units(text)
    if not units:
        return []

    unit_token_counts = [_token_count(unit) for unit in units]
    chunks: list[TextChunk] = []

    start_idx = 0
    index = 0
    while start_idx < len(units):
        end_idx = _max_end_for_chunk(
            start_idx=start_idx,
            token_budget=chunk_size,
            unit_token_counts=unit_token_counts,
        )
        chunk_units = units[start_idx:end_idx]
        chunk_text_value = " ".join(chunk_units).strip()
        if not chunk_text_value:
            break

        token_count = _token_count(chunk_text_value)
        chunks.append(
            TextChunk(
                index=index,
                content=chunk_text_value,
                metadata={
                    "unit_start": start_idx,
                    "unit_end": end_idx - 1,
                    "token_count": token_count,
                },
            )
        )
        index += 1

        if end_idx >= len(units):
            break

        start_idx = _start_with_overlap(
            end_idx=end_idx,
            overlap_tokens=overlap,
            unit_token_counts=unit_token_counts,
        )
        if start_idx >= end_idx:
            start_idx = end_idx - 1

    return chunks


def _build_sentence_units(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    units: list[str] = []
    for paragraph in paragraphs:
        normalized = re.sub(r"\s+", " ", paragraph).strip()
        if not normalized:
            continue

        # Split on sentence boundaries while preserving punctuation.
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalized) if s.strip()]
        if not sentences:
            continue
        units.extend(sentences)
    return units


def _token_count(text: str) -> int:
    # Approximate token count with word-ish splits; stable and dependency-free.
    return max(1, len(re.findall(r"\S+", text)))


def _max_end_for_chunk(
    *,
    start_idx: int,
    token_budget: int,
    unit_token_counts: list[int],
) -> int:
    tokens = 0
    end_idx = start_idx
    while end_idx < len(unit_token_counts):
        next_tokens = unit_token_counts[end_idx]
        if tokens > 0 and tokens + next_tokens > token_budget:
            break
        tokens += next_tokens
        end_idx += 1
    # Always include at least one unit.
    return max(start_idx + 1, end_idx)


def _start_with_overlap(
    *,
    end_idx: int,
    overlap_tokens: int,
    unit_token_counts: list[int],
) -> int:
    if overlap_tokens <= 0:
        return end_idx
    tokens = 0
    start_idx = end_idx
    while start_idx > 0 and tokens < overlap_tokens:
        start_idx -= 1
        tokens += unit_token_counts[start_idx]
    return start_idx
