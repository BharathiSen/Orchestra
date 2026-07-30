"""In-memory execution tracker used during a single chat turn."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.evaluation.cost import calculate_cost_usd, estimate_tokens


@dataclass
class StepRecord:
    step_name: str
    sequence: int
    status: str = "running"
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tokens: int = 0
    cost_usd: Decimal = field(default_factory=lambda: Decimal("0"))
    detail: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    _t0: float = field(default_factory=time.perf_counter, repr=False)


@dataclass
class ExecutionTracker:
    """Accumulates latency / tokens / cost for one request."""

    model_name: str
    pipeline: str = "direct"
    steps: list[StepRecord] = field(default_factory=list)
    api_calls: int = 0
    started_perf: float = field(default_factory=time.perf_counter)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    snapshot: dict[str, Any] = field(default_factory=dict)
    _open_step: StepRecord | None = field(default=None, repr=False)

    def start_step(self, step_name: str, *, detail: dict[str, Any] | None = None) -> StepRecord:
        step = StepRecord(
            step_name=step_name,
            sequence=len(self.steps),
            detail=detail or {},
        )
        self.steps.append(step)
        self._open_step = step
        return step

    def end_step(
        self,
        step: StepRecord,
        *,
        status: str = "done",
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        step.status = status
        step.completed_at = datetime.now(UTC)
        step.latency_ms = max(0, int((time.perf_counter() - step._t0) * 1000))
        if input_tokens is not None:
            step.input_tokens = max(0, input_tokens)
        if output_tokens is not None:
            step.output_tokens = max(0, output_tokens)
        step.tokens = step.input_tokens + step.output_tokens
        step.cost_usd = calculate_cost_usd(
            model=self.model_name,
            input_tokens=step.input_tokens,
            output_tokens=step.output_tokens,
        )
        if detail:
            step.detail.update(detail)
        if self._open_step is step:
            self._open_step = None

    def record_llm_usage(
        self,
        *,
        step_name: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        status: str = "done",
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Attach usage to the open pipeline step, or create a standalone LLM step."""
        self.api_calls += 1
        inp = max(0, input_tokens)
        out = max(0, output_tokens)

        if self._open_step is not None:
            step = self._open_step
            step.input_tokens += inp
            step.output_tokens += out
            step.tokens = step.input_tokens + step.output_tokens
            step.cost_usd = calculate_cost_usd(
                model=self.model_name,
                input_tokens=step.input_tokens,
                output_tokens=step.output_tokens,
            )
            step.detail["llm_calls"] = int(step.detail.get("llm_calls") or 0) + 1
            if detail:
                calls = step.detail.setdefault("llm_details", [])
                if isinstance(calls, list):
                    calls.append(detail)
            return

        step = self.start_step(step_name, detail=detail)
        step._t0 = time.perf_counter() - (latency_ms / 1000.0)
        self.end_step(
            step,
            status=status,
            input_tokens=inp,
            output_tokens=out,
            detail=detail,
        )

    def add_tokens_estimate(self, *, prompt: str, completion: str, step_name: str = "llm") -> None:
        self.record_llm_usage(
            step_name=step_name,
            input_tokens=estimate_tokens(prompt),
            output_tokens=estimate_tokens(completion),
            latency_ms=0,
            detail={"estimated": True},
        )

    @property
    def input_tokens(self) -> int:
        return sum(s.input_tokens for s in self.steps)

    @property
    def output_tokens(self) -> int:
        return sum(s.output_tokens for s in self.steps)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def total_cost_usd(self) -> Decimal:
        return calculate_cost_usd(
            model=self.model_name,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )

    @property
    def latency_ms(self) -> int:
        return max(0, int((time.perf_counter() - self.started_perf) * 1000))

    def update_snapshot(self, **kwargs: Any) -> None:
        self.snapshot.update(kwargs)
