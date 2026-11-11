from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class EvalRunSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uid: str
    label: str
    prompt_version: str
    judge_version: str
    golden_set_version: str
    model: str
    judge_model: str
    created_at: datetime
    question_count: int
    judged_count: int
    error_count: int
    avg_correctness: float | None
    avg_completeness: float | None
    avg_relevance: float | None
    avg_clarity: float | None
    avg_overall: float | None
    p50_latency_ms: int | None
    total_tokens: int
    total_cost_usd: Decimal
    notes: str | None


class EvalResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: str
    category: str
    question: str
    expected_route: str
    route: str | None
    answer: str
    correctness: int | None
    completeness: int | None
    relevance: int | None
    clarity: int | None
    overall: float | None
    rationale: str | None
    latency_ms: int
    tokens: int
    cost_usd: Decimal
    error: str | None


class EvalRunDetailOut(EvalRunSummaryOut):
    results: list[EvalResultOut]
