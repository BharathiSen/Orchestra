"""Orchestra package — state/routing load eagerly; engine is lazy to avoid agent cycles."""

from __future__ import annotations

from typing import Any

from app.orchestrator.routing import classify_route
from app.orchestrator.state import OrchestraState

__all__ = [
    "OrchestraEngine",
    "OrchestraState",
    "build_orchestra_graph",
    "classify_route",
]


def __getattr__(name: str) -> Any:
    if name in {"OrchestraEngine", "build_orchestra_graph"}:
        from app.orchestrator.engine import OrchestraEngine, build_orchestra_graph

        if name == "OrchestraEngine":
            return OrchestraEngine
        return build_orchestra_graph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
