"""Day 9 — observability / execution schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExecutionStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sequence: int
    step_name: str
    status: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    tokens: int
    cost_usd: float
    detail: dict[str, Any] | None = None
    started_at: datetime
    completed_at: datetime | None = None


class ExecutionSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    conversation_id: int | None = None
    agent_id: int | None = None
    message_id: int | None = None
    status: str
    pipeline: str
    model_name: str
    prompt: str
    final_response: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    api_calls: int
    total_cost_usd: float
    success: bool
    user_rating: int | None = None
    scores: dict[str, Any] | None = None


class ExecutionDetailOut(ExecutionSummaryOut):
    error_detail: str | None = None
    snapshot: dict[str, Any] | None = None
    steps: list[ExecutionStepOut] = Field(default_factory=list)


class DashboardSummaryOut(BaseModel):
    project_id: int
    window: str
    executions_today: int
    success_rate: float
    average_latency_ms: float
    total_tokens: int
    total_cost_usd: float
    average_tokens: float


class MetricsBreakdownOut(BaseModel):
    project_id: int
    executions: int
    by_pipeline: dict[str, int]
    step_avg_latency_ms: dict[str, float]
    rated_count: int
    average_rating: float


class ExecutionRatingIn(BaseModel):
    rating: int = Field(ge=1, le=5)


class ReplayPayloadOut(BaseModel):
    """Everything needed to re-run or debug an execution."""

    execution_id: int
    project_id: int
    conversation_id: int | None = None
    agent_id: int | None = None
    model_name: str
    prompt: str
    pipeline: str
    enable_orchestra: bool
    enable_tools: bool
    snapshot: dict[str, Any] | None = None
    final_response: str | None = None
    chat_hint: str = (
        "POST /api/v1/chat with the same project/agent/model/message flags to replay."
    )
