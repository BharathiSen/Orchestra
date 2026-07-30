"""LLM wrapper that records token/latency metrics into an ExecutionTracker."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from app.evaluation.cost import estimate_tokens
from app.evaluation.tracker import ExecutionTracker
from app.services.llm_types import ChatCompletionResult


class TrackingLLM:
    """Delegates to a real LLM while capturing usage for Day 9 observability."""

    def __init__(self, llm: Any, tracker: ExecutionTracker, *, step_prefix: str = "llm") -> None:
        self._llm = llm
        self.tracker = tracker
        self.step_prefix = step_prefix

    def complete_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = "auto",
    ) -> ChatCompletionResult:
        t0 = time.perf_counter()
        result = self._llm.complete_chat(
            messages=messages,
            model=model,
            temperature=temperature,
            tools=tools,
            tool_choice=tool_choice,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)

        prompt_text = " ".join(str(m.get("content") or "") for m in messages)
        completion_text = result.content or ""
        input_tokens = result.prompt_tokens or estimate_tokens(prompt_text)
        output_tokens = result.completion_tokens or estimate_tokens(completion_text)

        self.tracker.record_llm_usage(
            step_name=self.step_prefix,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            detail={"model": model, "has_tools": bool(tools)},
        )
        return result

    def stream_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
    ) -> Iterator[str]:
        t0 = time.perf_counter()
        chunks: list[str] = []
        for token in self._llm.stream_chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            tools=tools,
        ):
            chunks.append(token)
            yield token
        latency_ms = int((time.perf_counter() - t0) * 1000)
        prompt_text = " ".join(str(m.get("content") or "") for m in messages)
        completion_text = "".join(chunks)
        self.tracker.record_llm_usage(
            step_name=f"{self.step_prefix}_stream",
            input_tokens=estimate_tokens(prompt_text),
            output_tokens=estimate_tokens(completion_text),
            latency_ms=latency_ms,
            detail={"model": model, "estimated": True, "stream": True},
        )
