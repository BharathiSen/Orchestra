from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.knowledge.embedding import embed_texts
from app.models import Document, DocumentChunk, KnowledgeBase


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document_name: str
    knowledge_base_id: int
    knowledge_base_name: str
    chunk_index: int
    content: str
    score: float


class Retriever:
    def __init__(self, db: Session) -> None:
        self.db = db

    def retrieve(
        self,
        *,
        question: str,
        knowledge_base_ids: list[int],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        if not question.strip() or not knowledge_base_ids:
            return []

        query_embedding = embed_texts([question])[0]
        rows = (
            self.db.query(
                DocumentChunk,
                Document,
                KnowledgeBase,
                DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .join(KnowledgeBase, KnowledgeBase.id == Document.knowledge_base_id)
            .filter(
                KnowledgeBase.id.in_(knowledge_base_ids),  # type: ignore[attr-defined]
                Document.status == "processed",
                Document.embedding_status == "generated",
                DocumentChunk.embedding.isnot(None),
            )
            .order_by("distance")
            .limit(top_k)
            .all()
        )

        results: list[RetrievedChunk] = []
        for chunk, document, kb, distance in rows:
            # Convert cosine distance to similarity-like score for easier UI reading.
            score = max(0.0, 1.0 - float(distance or 0.0))
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    document_name=document.filename,
                    knowledge_base_id=kb.id,
                    knowledge_base_name=kb.name,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    score=score,
                )
            )
        return results
