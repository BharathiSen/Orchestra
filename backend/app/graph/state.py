from __future__ import annotations

import operator
from typing import Any

from typing_extensions import Annotated, TypedDict


class GraphState(TypedDict, total=False):
    # Inputs
    llm_messages: list[dict[str, Any]]
    model: str
    temperature: float
    tools: list[dict[str, Any]]
    enable_tools: bool

    # Planner outputs
    plan_text: str
    tool_calls: list[dict[str, Any]]

    # Tool/reviewer/answer outputs
    tool_events: Annotated[list[dict[str, Any]], operator.add]
    review_notes: str
    final_answer: str

    # Visualization events for UI
    graph_events: Annotated[list[dict[str, Any]], operator.add]
