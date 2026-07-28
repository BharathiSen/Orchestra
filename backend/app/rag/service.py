from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.orm import Session

from app.rag.generator import build_grounded_system_prompt
from app.rag.retriever import RetrievedChunk, Retriever


class RagService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.retriever = Retriever(db)

    def retrieve_chunks_for_question(
        self,
        *,
        question: str,
        knowledge_base_ids: list[int],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        return self.retriever.retrieve(
            question=question,
            knowledge_base_ids=knowledge_base_ids,
            top_k=top_k,
        )

    def build_grounded_prompt(
        self,
        *,
        base_system_prompt: str,
        retrieved_chunks: list[RetrievedChunk],
    ) -> str:
        return build_grounded_system_prompt(
            base_system_prompt=base_system_prompt,
            retrieved_chunks=retrieved_chunks,
        )

    def serialize_chunks(self, chunks: list[RetrievedChunk]) -> list[dict]:
        return [asdict(item) for item in chunks]
