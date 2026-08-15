from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.rag.generator import build_grounded_system_prompt, build_retrieved_context_message
from app.rag.retriever import RetrievedChunk, Retriever


class RagService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.retriever = Retriever(db)

    @contextmanager
    def scoped_copy(self) -> Iterator[RagService]:
        """Yield an equivalent service bound to its own database session.

        A SQLAlchemy ``Session`` is not thread-safe: it holds one connection and
        a mutable identity map, so two threads issuing queries through the same
        instance can interleave and corrupt its state. ``ResearchAgent`` fans
        retrieval out across a thread pool, so each task takes a session of its
        own here rather than borrowing the request's.

        The session is closed on exit. That is safe for retrieval specifically
        because ``RetrievedChunk`` is a plain dataclass of primitives — nothing
        is returned that would need to lazy-load after the session is gone.
        """
        session = SessionLocal()
        try:
            yield RagService(session)
        finally:
            session.close()

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

    def build_context_message(
        self,
        retrieved_chunks: list[RetrievedChunk],
    ) -> dict[str, Any] | None:
        """Retrieved text as a user-role message — see `rag/prompt_builder.py`."""
        return build_retrieved_context_message(retrieved_chunks)

    def serialize_chunks(self, chunks: list[RetrievedChunk]) -> list[dict]:
        return [asdict(item) for item in chunks]
