"""Reviewer agent — quality-checks the draft and produces the final response."""

from __future__ import annotations

from typing import Any

from app.agents.base import llm_text
from app.orchestrator.state import OrchestraState
from app.prompts.reviewer import reviewer_prompt


class ReviewerAgent:
    name = "reviewer"

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def __call__(self, state: OrchestraState) -> OrchestraState:
        question = state.get("question") or ""
        draft = state.get("draft") or ""
        research = state.get("research_notes") or ""

        system = reviewer_prompt()
        user = (
            f"Question:\n{question}\n\n"
            f"Research notes:\n{research}\n\n"
            f"Draft:\n{draft}"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        if state.get("stream_final"):
            # The engine makes this call as a stream. The `final_marker` filter
            # holds tokens back until `FINAL:` appears, so the user never sees
            # the review notes — they are recovered from the same buffer and
            # still reported as review_notes.
            return {
                "current_agent": self.name,
                "final_messages": messages,
                "final_temperature": 0.1,
                "final_filter": "final_marker",
                "execution_history": [
                    {
                        "agent": self.name,
                        "status": "done",
                        "summary": "Reviewed draft; final answer streamed.",
                    }
                ],
            }

        try:
            raw = llm_text(
                self.llm,
                messages=messages,
                model=state["model"],
                temperature=0.1,
            )
            notes, final = self._split(raw, draft)
            return {
                "current_agent": self.name,
                "review_notes": notes,
                "final_response": final,
                "execution_history": [
                    {
                        "agent": self.name,
                        "status": "done",
                        "summary": "Reviewed draft and produced final answer.",
                    }
                ],
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "current_agent": self.name,
                "review_notes": f"Reviewer skipped due to error: {exc}",
                "final_response": draft or "No answer available.",
                "errors": [f"reviewer: {exc}"],
                "execution_history": [
                    {
                        "agent": self.name,
                        "status": "error",
                        "summary": f"Reviewer error; returning draft. ({exc})",
                    }
                ],
            }

    def _split(self, raw: str, draft: str) -> tuple[str, str]:
        text = (raw or "").strip()
        if not text:
            return "No review notes.", draft

        upper = text.upper()
        if "FINAL:" in upper:
            idx = upper.index("FINAL:")
            notes_part = text[:idx]
            final_part = text[idx + len("FINAL:") :].strip()
            notes = notes_part
            if notes.upper().startswith("NOTES:"):
                notes = notes[len("NOTES:") :].strip()
            notes = notes.strip() or "Looks good."
            final = final_part or draft
            return notes, final

        return "Model returned a single block; treated as final answer.", text
