from __future__ import annotations

from app.rag.prompt_builder import build_system_prompt
from app.rag.retriever import RetrievedChunk


def build_grounded_system_prompt(
    *,
    base_system_prompt: str,
    retrieved_chunks: list[RetrievedChunk],
) -> str:
    return build_system_prompt(
        base_system_prompt=base_system_prompt,
        chunks=retrieved_chunks,
    )
