"""Split extracted text into overlapping chunks for retrieval."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    metadata: dict


def chunk_text(
    text: str,
    *,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> list[TextChunk]:
    """
    Chunk by character windows, preferring paragraph/sentence boundaries.

    ~1000 chars (~150–250 tokens) with overlap is a solid Day-6 default:
    small enough for precise retrieval, large enough to keep context.
    A 6-page paper should typically produce dozens of chunks, not 2.
    """
    normalized = " ".join(text.split())
    if not normalized:
        return []

    if len(normalized) <= chunk_size:
        return [
            TextChunk(
                index=0,
                content=normalized,
                metadata={"char_start": 0, "char_end": len(normalized)},
            )
        ]

    chunks: list[TextChunk] = []
    start = 0
    index = 0

    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))

        # Prefer breaking near a sentence boundary in the last 20% of the window.
        if end < len(normalized):
            window = normalized[start:end]
            search_from = int(len(window) * 0.8)
            boundary = -1
            for sep in (". ", "? ", "! ", "; "):
                pos = window.rfind(sep, search_from)
                if pos > boundary:
                    boundary = pos + len(sep)
            if boundary > 0:
                end = start + boundary

        piece = normalized[start:end].strip()
        if piece:
            chunks.append(
                TextChunk(
                    index=index,
                    content=piece,
                    metadata={"char_start": start, "char_end": end},
                )
            )
            index += 1

        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)

    return chunks
