"""Shared helpers for Orchestra specialist agents."""

from __future__ import annotations

from typing import Any


def llm_text(llm: Any, *, messages: list[dict[str, Any]], model: str, temperature: float) -> str:
    result = llm.complete_chat(
        messages=messages,
        model=model,
        temperature=temperature,
        tools=None,
        tool_choice=None,
    )
    return (result.content or "").strip()


def history_snippet(messages: list[dict[str, Any]], limit: int = 8) -> str:
    lines: list[str] = []
    for msg in messages[-limit:]:
        role = str(msg.get("role") or "")
        content = str(msg.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "(no prior messages)"


def long_term_snippet(memory: dict[str, Any] | None) -> str:
    if not memory:
        return ""
    items = memory.get("long_term") or []
    if not items:
        return ""
    lines = ["User long-term memory:"]
    for item in items:
        lines.append(f"- [{item.get('category')}] {item.get('key')}: {item.get('value')}")
    return "\n".join(lines)
