"""Writer agent — drafts the user-facing answer from research."""

from __future__ import annotations

from typing import Any

from app.agents.base import history_snippet, llm_text, long_term_snippet
from app.orchestrator.state import OrchestraState
from app.prompts.writer import writer_prompt


class WriterAgent:
    name = "writer"

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def __call__(self, state: OrchestraState) -> OrchestraState:
        question = state.get("question") or ""
        memory_block = long_term_snippet(state.get("memory"))
        history = history_snippet(state.get("messages") or [])
        plan = state.get("plan") or ""
        research = state.get("research_notes") or ""

        system = writer_prompt(base_system=state.get("system_prompt"))
        user = (
            f"Conversation:\n{history}\n\n"
            f"{memory_block}\n\n"
            f"Plan:\n{plan}\n\n"
            f"Research notes:\n{research}\n\n"
            f"User question:\n{question}\n\n"
            "Write the draft answer now."
        )
        try:
            draft = llm_text(
                self.llm,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                model=state["model"],
                temperature=float(state.get("temperature") or 0.2),
            )
            if not draft:
                draft = research or "I could not draft an answer from the available context."
            return {
                "current_agent": self.name,
                "draft": draft,
                "execution_history": [
                    {
                        "agent": self.name,
                        "status": "done",
                        "summary": f"Drafted {len(draft.split())} words.",
                    }
                ],
            }
        except Exception as exc:  # noqa: BLE001
            fallback = research or "Writer failed to produce a draft."
            return {
                "current_agent": self.name,
                "draft": fallback,
                "errors": [f"writer: {exc}"],
                "execution_history": [
                    {
                        "agent": self.name,
                        "status": "error",
                        "summary": f"Writer error: {exc}",
                    }
                ],
            }
