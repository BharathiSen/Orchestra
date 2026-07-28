"""Split extracted text into overlapping chunks."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    metadata: dict


def chunk_text(
    text: str,
    *,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[TextChunk]:
    normalized = " ".join(text.split())
    if not normalized:
        return []

    if len(normalized) <= chunk_size:
        return [TextChunk(index=0, content=normalized, metadata={"char_start": 0, "char_end": len(normalized)})]

    chunks: list[TextChunk] = []
    start = 0
    index = 0

    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
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
