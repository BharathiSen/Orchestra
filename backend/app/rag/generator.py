from __future__ import annotations

from typing import Any

from app.rag.prompt_builder import build_context_message, build_system_prompt
from app.rag.retriever import RetrievedChunk


def build_grounded_system_prompt(
    *,
    base_system_prompt: str,
    retrieved_chunks: list[RetrievedChunk],
) -> str:
    """System prompt plus the grounding rules — never the chunk text itself."""
    return build_system_prompt(
        base_system_prompt=base_system_prompt,
        chunks=retrieved_chunks,
    )


def build_retrieved_context_message(
    retrieved_chunks: list[RetrievedChunk],
) -> dict[str, Any] | None:
    """The user-role message that carries the retrieved text as data."""
    return build_context_message(retrieved_chunks)
