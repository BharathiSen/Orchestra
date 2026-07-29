"""Orchestra multi-agent engine: Planner → Research → Writer → Reviewer."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents import PlannerAgent, ResearchAgent, ReviewerAgent, WriterAgent
from app.orchestrator.state import OrchestraState


AGENT_ORDER = ["planner", "research", "writer", "reviewer"]


def build_orchestra_graph(*, llm: Any, rag: Any | None = None):
    graph = StateGraph(OrchestraState)
    graph.add_node("planner", PlannerAgent(llm))
    graph.add_node("research", ResearchAgent(llm, rag=rag))
    graph.add_node("writer", WriterAgent(llm))
    graph.add_node("reviewer", ReviewerAgent(llm))

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "research")
    graph.add_edge("research", "writer")
    graph.add_edge("writer", "reviewer")
    graph.add_edge("reviewer", END)
    return graph.compile()


class OrchestraEngine:
    """Runs the multi-agent pipeline and yields UI-friendly progress events."""

    def __init__(self, *, llm: Any, rag: Any | None = None) -> None:
        self.llm = llm
        self.rag = rag
        self.graph = build_orchestra_graph(llm=llm, rag=rag)

    def run(self, initial_state: OrchestraState) -> Iterator[dict[str, Any]]:
        """Yield orchestra_step events, then a final result payload."""
        current_idx = 0
        yield {
            "type": "orchestra_step",
            "agent": AGENT_ORDER[0],
            "status": "running",
            "summary": "Planning the task…",
        }

        final_state: dict[str, Any] = dict(initial_state)
        retrieved_emitted = False

        for update in self.graph.stream(initial_state, stream_mode="updates"):
            for agent_name, payload in update.items():
                # Advance running → done markers for skipped intermediates
                while (
                    current_idx < len(AGENT_ORDER)
                    and AGENT_ORDER[current_idx] != agent_name
                ):
                    yield {
                        "type": "orchestra_step",
                        "agent": AGENT_ORDER[current_idx],
                        "status": "done",
                    }
                    current_idx += 1
                    if current_idx < len(AGENT_ORDER):
                        yield {
                            "type": "orchestra_step",
                            "agent": AGENT_ORDER[current_idx],
                            "status": "running",
                        }

                summary = _agent_summary(payload, agent_name)
                status = "error" if _has_error(payload, agent_name) else "done"
                yield {
                    "type": "orchestra_step",
                    "agent": agent_name,
                    "status": status,
                    "summary": summary,
                }

                if (
                    not retrieved_emitted
                    and agent_name == "research"
                    and payload.get("retrieved_docs")
                ):
                    docs = payload["retrieved_docs"]
                    yield {
                        "type": "retrieved_context",
                        "count": len(docs),
                        "chunks": docs,
                    }
                    retrieved_emitted = True

                current_idx += 1
                if current_idx < len(AGENT_ORDER):
                    yield {
                        "type": "orchestra_step",
                        "agent": AGENT_ORDER[current_idx],
                        "status": "running",
                    }

                # Merge into accumulating state
                for key, value in payload.items():
                    if key in {"execution_history", "errors"} and isinstance(value, list):
                        final_state[key] = list(final_state.get(key) or []) + value
                    else:
                        final_state[key] = value

        while current_idx < len(AGENT_ORDER):
            yield {
                "type": "orchestra_step",
                "agent": AGENT_ORDER[current_idx],
                "status": "done",
            }
            current_idx += 1

        answer = str(final_state.get("final_response") or "").strip()
        if not answer:
            answer = str(final_state.get("draft") or "").strip()
        if not answer:
            answer = "(No content returned by Orchestra.)"

        yield {
            "type": "orchestra_result",
            "final_response": answer,
            "plan": final_state.get("plan"),
            "research_notes": final_state.get("research_notes"),
            "review_notes": final_state.get("review_notes"),
            "retrieved_docs": final_state.get("retrieved_docs") or [],
            "execution_history": final_state.get("execution_history") or [],
            "errors": final_state.get("errors") or [],
        }


def _agent_summary(payload: dict[str, Any], agent_name: str) -> str | None:
    for evt in payload.get("execution_history") or []:
        if evt.get("agent") == agent_name:
            return evt.get("summary")
    return None


def _has_error(payload: dict[str, Any], agent_name: str) -> bool:
    for evt in payload.get("execution_history") or []:
        if evt.get("agent") == agent_name and evt.get("status") == "error":
            return True
    return False
