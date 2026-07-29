"""Orchestra shared multi-agent state (single source of truth)."""

from __future__ import annotations

import operator
from typing import Any

from typing_extensions import Annotated, TypedDict


class OrchestraState(TypedDict, total=False):
    # Inputs
    question: str
    system_prompt: str
    model: str
    temperature: float
    knowledge_base_ids: list[int]

    # Shared memory context
    messages: list[dict[str, Any]]  # conversation buffer for LLM
    memory: dict[str, Any]  # short-term meta + long-term prefs
    retrieved_docs: list[dict[str, Any]]

    # Orchestration tracking
    current_agent: str
    errors: Annotated[list[str], operator.add]
    execution_history: Annotated[list[dict[str, Any]], operator.add]

    # Agent outputs
    plan: str
    research_notes: str
    draft: str
    review_notes: str
    final_response: str
