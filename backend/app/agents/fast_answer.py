"""Fast-answer agent for the simple Orchestra route (skips Writer+Reviewer)."""

from __future__ import annotations

from typing import Any

from app.agents.base import history_snippet, llm_text, long_term_snippet
from app.orchestrator.state import OrchestraState


class FastAnswerAgent:
    name = "fast_answer"

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def __call__(self, state: OrchestraState) -> OrchestraState:
        question = state.get("question") or ""
        base_system = state.get("system_prompt") or "You are a helpful AI assistant."
        research = state.get("research_notes") or ""
        memory_block = long_term_snippet(state.get("memory"))
        history = history_snippet(state.get("messages") or [])

        system = (
            f"{base_system}\n\n"
            "You are answering on the Orchestra simple route. "
            "Be concise and accurate. Prefer research notes and memory when present."
        )
        user = (
            f"Conversation:\n{history}\n\n"
            f"{memory_block}\n\n"
            f"Research notes:\n{research}\n\n"
            f"User question:\n{question}"
        )
        try:
            answer = llm_text(
                self.llm,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                model=state["model"],
                temperature=float(state.get("temperature") or 0.2),
            )
            if not answer:
                answer = research or "I do not have enough context to answer yet."
            return {
                "current_agent": self.name,
                "final_response": answer,
                "draft": answer,
                "review_notes": "Skipped (simple route).",
                "execution_history": [
                    {
                        "agent": self.name,
                        "status": "done",
                        "summary": "Simple route answer (Writer/Reviewer skipped).",
                    }
                ],
            }
        except Exception as exc:  # noqa: BLE001
            fallback = research or f"Fast answer failed: {exc}"
            return {
                "current_agent": self.name,
                "final_response": fallback,
                "draft": fallback,
                "errors": [f"fast_answer: {exc}"],
                "execution_history": [
                    {
                        "agent": self.name,
                        "status": "error",
                        "summary": f"Fast answer error: {exc}",
                    }
                ],
            }
