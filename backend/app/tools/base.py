from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Contract every Orchestra tool must satisfy.

    Why this exists:
    - The LLM only sees *name*, *description*, and *JSON schema* (parameters).
    - Our backend owns *execution* (side effects, validation, safety).
    - A shared interface lets the registry treat 3 tools or 300 the same way.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool id used in function-calling payloads (snake_case)."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human + model readable: when should this tool be chosen?"""

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for the tool arguments (OpenAI / Groq compatible)."""

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """Run the tool and return a string result the LLM can read."""

    def to_openai_tool(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible tools[] entry."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_public_dict(self) -> dict[str, Any]:
        """Safe metadata for API / UI (no secrets)."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
