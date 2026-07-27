from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, status

from app.tools.base import BaseTool


class ToolRegistry:
    """Single lookup table for all tools.

    Without a registry, chat code grows into:

        if name == "weather": ...
        elif name == "search": ...

    With a registry:

        registry.execute(name, arguments)

    Adding a tool = register once. Chat pipeline never changes.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        key = tool.name.strip()
        if not key:
            raise ValueError("Tool name cannot be empty")
        if key in self._tools:
            raise ValueError(f"Tool already registered: {key}")
        self._tools[key] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def openai_tools(self) -> list[dict[str, Any]]:
        return [tool.to_openai_tool() for tool in self._tools.values()]

    def public_catalog(self) -> list[dict[str, Any]]:
        return [tool.to_public_dict() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any] | str | None = None) -> str:
        tool = self.get(name)
        if tool is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown tool: {name}",
            )

        if arguments is None:
            args: dict[str, Any] = {}
        elif isinstance(arguments, str):
            raw = arguments.strip() or "{}"
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tool '{name}' received invalid JSON arguments: {exc}",
                ) from exc
            if not isinstance(parsed, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tool '{name}' arguments must be a JSON object",
                )
            args = parsed
        else:
            args = arguments

        try:
            result = tool.execute(**args)
        except TypeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tool '{name}' argument error: {exc}",
            ) from exc
        except Exception as exc:  # noqa: BLE001 — surface tool failures to the model
            return f"ERROR executing tool '{name}': {exc}"

        if result is None:
            return ""
        return str(result)


# Process-wide default registry (built-in tools registered at import).
default_registry = ToolRegistry()
