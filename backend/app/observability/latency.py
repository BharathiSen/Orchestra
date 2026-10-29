"""Request-scoped latency marks for one chat turn.

Durations use ``time.perf_counter``. The timeline is attached to the execution
snapshot and, in summary form, to the existing ``done`` SSE event. Recording
must never break a chat: every public method swallows its own failures.

Nothing stored here includes prompts, answers, tokens, or credentials.
"""

from __future__ import annotations

import threading
import time
from contextvars import ContextVar, Token
from typing import Any

_current: ContextVar[LatencyTimeline | None] = ContextVar(
    "orchestra_latency_timeline",
    default=None,
)


class LatencyTimeline:
    """Monotonic marks and stage durations for a single request."""

    def __init__(self) -> None:
        self._t0 = time.perf_counter()
        self._lock = threading.Lock()
        self.marks_ms: dict[str, int] = {}
        self.durations_ms: dict[str, int] = {}
        self.llm_calls: list[dict[str, Any]] = []
        self.retries = 0
        self.timeouts = 0
        self.errors: list[str] = []
        self.execution_id: int | None = None
        self.provider: str | None = None
        self.model: str | None = None

    def elapsed_ms(self) -> int:
        return max(0, int((time.perf_counter() - self._t0) * 1000))

    def mark(self, name: str) -> None:
        """Record the first time `name` is reached, as ms since request start."""
        try:
            with self._lock:
                if name not in self.marks_ms:
                    self.marks_ms[name] = self.elapsed_ms()
        except Exception:  # noqa: BLE001 — instrumentation must not break chat
            return

    def add_duration(self, name: str, started: float) -> None:
        """Add the elapsed time since `started` (a perf_counter value) to a stage."""
        try:
            ms = max(0, int((time.perf_counter() - started) * 1000))
            with self._lock:
                self.durations_ms[name] = self.durations_ms.get(name, 0) + ms
                if name not in self.marks_ms:
                    self.marks_ms[name] = self.elapsed_ms()
        except Exception:  # noqa: BLE001
            return

    def note_provider_token(self) -> None:
        self.mark("first_provider_token")

    def note_delivered_token(self) -> None:
        self.mark("first_token_delivered")

    def note_llm_call(
        self,
        *,
        model: str,
        latency_ms: int,
        input_tokens: int,
        output_tokens: int,
        stream: bool,
        estimated: bool,
    ) -> None:
        try:
            entry = {
                "model": model,
                "latency_ms": max(0, int(latency_ms)),
                "input_tokens": max(0, int(input_tokens)),
                "output_tokens": max(0, int(output_tokens)),
                "stream": bool(stream),
                "estimated": bool(estimated),
            }
            with self._lock:
                if len(self.llm_calls) < 24:
                    self.llm_calls.append(entry)
                self.durations_ms["llm"] = self.durations_ms.get("llm", 0) + entry["latency_ms"]
        except Exception:  # noqa: BLE001
            return

    def note_retry(self) -> None:
        try:
            with self._lock:
                self.retries += 1
        except Exception:  # noqa: BLE001
            return

    def note_timeout(self) -> None:
        try:
            with self._lock:
                self.timeouts += 1
                if "timeout" not in self.errors:
                    self.errors.append("timeout")
        except Exception:  # noqa: BLE001
            return

    def note_error(self, code: str) -> None:
        """Record a short error class name. Do not pass exception messages."""
        try:
            cleaned = "".join(ch for ch in code if ch.isalnum() or ch == "_")[:64]
            if not cleaned:
                return
            with self._lock:
                if cleaned not in self.errors and len(self.errors) < 8:
                    self.errors.append(cleaned)
        except Exception:  # noqa: BLE001
            return

    def as_dict(self) -> dict[str, Any]:
        try:
            with self._lock:
                durations = dict(self.durations_ms)
                marks = dict(self.marks_ms)
                calls = list(self.llm_calls)
                retries = self.retries
                timeouts = self.timeouts
                errors = list(self.errors)
                execution_id = self.execution_id
                provider = self.provider
                model = self.model
            slowest: dict[str, Any] | None = None
            if durations:
                stage = max(durations, key=lambda key: durations[key])
                slowest = {"stage": stage, "duration_ms": durations[stage]}
            return {
                "execution_id": execution_id,
                "provider": provider,
                "model": model,
                "marks_ms": marks,
                "durations_ms": durations,
                "ttft_provider_ms": marks.get("first_provider_token"),
                "ttft_delivered_ms": marks.get("first_token_delivered"),
                "llm_calls": calls,
                "retries": retries,
                "timeouts": timeouts,
                "errors": errors,
                "slowest_stage": slowest,
            }
        except Exception:  # noqa: BLE001
            return {}


def current_timeline() -> LatencyTimeline | None:
    try:
        return _current.get()
    except Exception:  # noqa: BLE001
        return None


def push_timeline(timeline: LatencyTimeline) -> Token[LatencyTimeline | None]:
    return _current.set(timeline)


def pop_timeline(token: Token[LatencyTimeline | None]) -> None:
    try:
        _current.reset(token)
    except Exception:  # noqa: BLE001
        return
