"""Research agent — retrieves KB context and summarizes findings."""

from __future__ import annotations

from typing import Any

from app.agents.base import history_snippet, llm_text, long_term_snippet
from app.orchestrator.state import OrchestraState


class ResearchAgent:
    name = "research"

    def __init__(self, llm: Any, rag: Any | None = None) -> None:
        self.llm = llm
        self.rag = rag

    def __call__(self, state: OrchestraState) -> OrchestraState:
        question = state.get("question") or ""
        kb_ids = list(state.get("knowledge_base_ids") or [])
        retrieved: list[dict[str, Any]] = []
        notes_parts: list[str] = []

        if self.rag is not None and kb_ids:
            try:
                chunks = self.rag.retrieve_chunks_for_question(
                    question=question,
                    knowledge_base_ids=kb_ids,
                    top_k=5,
                )
                if chunks:
                    retrieved = self.rag.serialize_chunks(chunks)
                    notes_parts.append("Retrieved knowledge base excerpts:")
                    for item in retrieved[:5]:
                        notes_parts.append(
                            f"- [{item.get('document_name')}] "
                            f"(chunk {item.get('chunk_index')}, score={item.get('score')}): "
                            f"{item.get('content')}"
                        )
            except Exception as exc:  # noqa: BLE001
                return {
                    "current_agent": self.name,
                    "retrieved_docs": [],
                    "research_notes": f"Retrieval failed: {exc}",
                    "errors": [f"research: {exc}"],
                    "execution_history": [
                        {
                            "agent": self.name,
                            "status": "error",
                            "summary": f"Retrieval error: {exc}",
                        }
                    ],
                }

        memory_block = long_term_snippet(state.get("memory"))
        history = history_snippet(state.get("messages") or [])
        plan = state.get("plan") or ""

        if not notes_parts:
            # No KB hits — ask LLM to outline what it knows / what is missing
            system = (
                "You are the Research agent in Orchestra. "
                "No knowledge-base hits were available. Summarize what is already known "
                "from conversation/memory and list open questions. Do NOT write the final answer."
            )
            user = (
                f"Plan:\n{plan}\n\n"
                f"Conversation:\n{history}\n\n"
                f"{memory_block}\n\n"
                f"Question:\n{question}"
            )
            try:
                synthesis = llm_text(
                    self.llm,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    model=state["model"],
                    temperature=0.2,
                )
                notes_parts.append(synthesis or "No external research available.")
            except Exception as exc:  # noqa: BLE001
                notes_parts.append(f"Research synthesis failed: {exc}")
                return {
                    "current_agent": self.name,
                    "retrieved_docs": retrieved,
                    "research_notes": "\n".join(notes_parts),
                    "errors": [f"research: {exc}"],
                    "execution_history": [
                        {
                            "agent": self.name,
                            "status": "error",
                            "summary": "Research synthesis failed.",
                        }
                    ],
                }
        else:
            # Condense retrieved chunks into research notes
            system = (
                "You are the Research agent in Orchestra. "
                "Condense the retrieved excerpts into clear research notes for the Writer. "
                "Prefer facts from the excerpts. Do NOT invent sources."
            )
            user = (
                f"Plan:\n{plan}\n\n"
                f"Question:\n{question}\n\n"
                f"Excerpts:\n" + "\n".join(notes_parts)
            )
            try:
                synthesis = llm_text(
                    self.llm,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    model=state["model"],
                    temperature=0.1,
                )
                if synthesis:
                    notes_parts = [synthesis]
            except Exception:
                # keep raw excerpts
                pass

        summary = (
            f"Retrieved {len(retrieved)} chunk(s)."
            if retrieved
            else "No KB chunks; used conversation/memory only."
        )
        return {
            "current_agent": self.name,
            "retrieved_docs": retrieved,
            "research_notes": "\n".join(notes_parts).strip(),
            "execution_history": [
                {"agent": self.name, "status": "done", "summary": summary}
            ],
        }
