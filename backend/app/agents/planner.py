"""Planner agent — breaks the user task into clear steps."""

from __future__ import annotations

from typing import Any

from app.agents.base import history_snippet, llm_text, long_term_snippet
from app.orchestrator.state import OrchestraState
from app.prompts.planner import planner_fallback_plan, planner_prompt


class PlannerAgent:
    name = "planner"

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def __call__(self, state: OrchestraState) -> OrchestraState:
        question = state.get("question") or ""
        memory_block = long_term_snippet(state.get("memory"))
        history = history_snippet(state.get("messages") or [])

        system = planner_prompt()
        user = (
            f"Conversation history:\n{history}\n\n"
            f"{memory_block}\n\n"
            f"User question:\n{question}\n\n"
            "Return a numbered plan only."
        )
        try:
            plan = llm_text(
                self.llm,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                model=state["model"],
                temperature=min(float(state.get("temperature") or 0.2), 0.4),
            )
            if not plan:
                plan = planner_fallback_plan()
            return {
                "current_agent": self.name,
                "plan": plan,
                "execution_history": [
                    {
                        "agent": self.name,
                        "status": "done",
                        "summary": f"Planned {plan.count(chr(10)) + 1} step(s).",
                    }
                ],
            }
        except Exception as exc:  # noqa: BLE001
            fallback = planner_fallback_plan()
            return {
                "current_agent": self.name,
                "plan": fallback,
                "errors": [f"planner: {exc}"],
                "execution_history": [
                    {
                        "agent": self.name,
                        "status": "error",
                        "summary": f"Planner failed; using default plan. ({exc})",
                    }
                ],
            }
