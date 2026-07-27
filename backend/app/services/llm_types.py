from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallRequest:
    """A single function call requested by the model."""

    id: str
    name: str
    arguments: str  # JSON string (OpenAI-compatible)


@dataclass
class ChatCompletionResult:
    """Non-streaming completion that may include tool calls and/or text."""

    content: str | None = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str | None = None
    raw_assistant_message: dict[str, Any] | None = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)
