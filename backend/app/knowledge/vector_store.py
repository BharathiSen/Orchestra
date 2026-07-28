"""Persist chunk embeddings in PostgreSQL via pgvector."""

from sqlalchemy.orm import Session

from app.models import DocumentChunk


def store_chunks(
    db: Session,
    *,
    document_id: int,
    chunks: list[tuple[int, str, dict | None, list[float]]],
) -> int:
    """Insert chunks with embeddings. Each tuple is (index, content, metadata, embedding)."""
    for chunk_index, content, metadata, embedding in chunks:
        db.add(
            DocumentChunk(
                document_id=document_id,
                chunk_index=chunk_index,
                content=content,
                chunk_metadata=metadata,
                embedding=embedding,
            )
        )
    db.commit()
    return len(chunks)
