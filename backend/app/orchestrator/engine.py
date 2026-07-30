"""Orchestra multi-agent engine with conditional simple/full routing."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.agents import PlannerAgent, ResearchAgent, ReviewerAgent, WriterAgent
from app.agents.fast_answer import FastAnswerAgent
from app.orchestrator.routing import classify_route
from app.orchestrator.state import OrchestraState

RouteName = Literal["simple", "full"]

FULL_ORDER = ["planner", "research", "writer", "reviewer"]
SIMPLE_ORDER = ["planner", "research", "fast_answer"]


def build_orchestra_graph(
    *,
    llm: Any,
    rag: Any | None = None,
    tools: Any | None = None,
):
    graph = StateGraph(OrchestraState)
    graph.add_node("planner", PlannerAgent(llm))
    graph.add_node(
        "research",
        ResearchAgent(llm, rag=rag, tools=tools, enable_web_search=True),
    )
    graph.add_node("writer", WriterAgent(llm))
    graph.add_node("reviewer", ReviewerAgent(llm))
    graph.add_node("fast_answer", FastAnswerAgent(llm))

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "research")

    def after_research(state: OrchestraState) -> str:
        return "fast_answer" if state.get("route") == "simple" else "writer"

    graph.add_conditional_edges(
        "research",
        after_research,
        {"fast_answer": "fast_answer", "writer": "writer"},
    )
    graph.add_edge("writer", "reviewer")
    graph.add_edge("reviewer", END)
    graph.add_edge("fast_answer", END)
    return graph.compile()


class OrchestraEngine:
    """Runs the multi-agent pipeline and yields UI-friendly progress events."""

    def __init__(
        self,
        *,
        llm: Any,
        rag: Any | None = None,
        tools: Any | None = None,
    ) -> None:
        self.llm = llm
        self.rag = rag
        self.tools = tools
        self.graph = build_orchestra_graph(llm=llm, rag=rag, tools=tools)

    def run(self, initial_state: OrchestraState) -> Iterator[dict[str, Any]]:
        state = dict(initial_state)
        route: RouteName = state.get("route") or classify_route(str(state.get("question") or ""))  # type: ignore[assignment]
        if route not in {"simple", "full"}:
            route = "full"
        state["route"] = route

        agent_order = SIMPLE_ORDER if route == "simple" else FULL_ORDER
        current_idx = 0

        yield {
            "type": "orchestra_step",
            "agent": agent_order[0],
            "status": "running",
            "summary": f"Planning ({route} route)…",
            "route": route,
        }

        final_state: dict[str, Any] = dict(state)
        retrieved_emitted = False

        for update in self.graph.stream(state, stream_mode="updates"):
            for agent_name, payload in update.items():
                while (
                    current_idx < len(agent_order)
                    and agent_order[current_idx] != agent_name
                ):
                    skipped = agent_order[current_idx]
                    yield {
                        "type": "orchestra_step",
                        "agent": skipped,
                        "status": "done",
                        "summary": "Skipped",
                        "route": route,
                    }
                    current_idx += 1
                    if current_idx < len(agent_order):
                        yield {
                            "type": "orchestra_step",
                            "agent": agent_order[current_idx],
                            "status": "running",
                            "route": route,
                        }

                summary = _agent_summary(payload, agent_name)
                status = "error" if _has_error(payload, agent_name) else "done"
                yield {
                    "type": "orchestra_step",
                    "agent": agent_name,
                    "status": status,
                    "summary": summary,
                    "route": route,
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
                if current_idx < len(agent_order):
                    yield {
                        "type": "orchestra_step",
                        "agent": agent_order[current_idx],
                        "status": "running",
                        "route": route,
                    }

                for key, value in payload.items():
                    if key in {"execution_history", "errors"} and isinstance(value, list):
                        final_state[key] = list(final_state.get(key) or []) + value
                    else:
                        final_state[key] = value

        while current_idx < len(agent_order):
            yield {
                "type": "orchestra_step",
                "agent": agent_order[current_idx],
                "status": "done",
                "route": route,
            }
            current_idx += 1

        # Mark skipped full-pipeline agents for UI clarity on simple route
        if route == "simple":
            for skipped in ("writer", "reviewer"):
                yield {
                    "type": "orchestra_step",
                    "agent": skipped,
                    "status": "done",
                    "summary": "Skipped (simple route)",
                    "route": route,
                }

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
            "route": route,
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
