from __future__ import annotations

from app.rag.retriever import RetrievedChunk

RAG_ADDENDUM = (
    "You are given retrieved knowledge chunks from the agent's attached knowledge bases. "
    "Ground your answer in this context when relevant. "
    "If context is weak or partially relevant, say so briefly and then answer using your general knowledge. "
    "Do not fabricate citations."
)


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return ""
    lines = ["Retrieved context:"]
    for item in chunks:
        lines.append(
            f"- [chunk_id:{item.chunk_id}] [kb:{item.knowledge_base_name}] "
            f"[doc:{item.document_name}] [chunk:{item.chunk_index}] {item.content}"
        )
    return "\n".join(lines)


def build_system_prompt(*, base_system_prompt: str, chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return base_system_prompt
    context = build_context_block(chunks)
    return f"{base_system_prompt}\n\n{RAG_ADDENDUM}\n\n{context}"
