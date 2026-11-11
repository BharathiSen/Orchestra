"""Deterministic LLM for browser end-to-end tests (LLM_PROVIDER=fake).

The Playwright suite drives the real frontend against the real backend, and it
must not depend on a paid provider, a network, or a model's mood. This client
answers instantly and predictably, through the same interface as the real
providers, so everything around the model — routing, streaming, tracing,
persistence — is exercised for real.

It is refused in production twice: by startup validation and by
`get_llm_service()`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.services.llm_types import ChatCompletionResult

FAKE_MODEL_ID = "openai/gpt-oss-20b"


def _last_user_message(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content") or "")
    return ""


def _reply(messages: list[dict[str, Any]]) -> str:
    question = " ".join(_last_user_message(messages).split())[:160]
    return f"Deterministic test reply to: {question}"


class FakeLLMService:
    provider_name = "fake"

    def complete_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = "auto",
    ) -> ChatCompletionResult:
        content = _reply(messages)
        return ChatCompletionResult(
            content=content,
            finish_reason="stop",
            prompt_tokens=40,
            completion_tokens=12,
            total_tokens=52,
        )

    def stream_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
        usage_sink: dict[str, int] | None = None,
    ) -> Iterator[str]:
        content = _reply(messages)
        # Several chunks, so the UI's incremental rendering is exercised.
        for word in content.split(" "):
            yield word + " "
        if usage_sink is not None:
            usage_sink["prompt_tokens"] = 40
            usage_sink["completion_tokens"] = 12
            usage_sink["total_tokens"] = 52
