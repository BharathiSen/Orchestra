"""Offline evaluation runs: the golden set answered by the pipeline, then judged.

One `EvalRun` per invocation of ``scripts/run_eval.py``; one `EvalResult` per
golden question. Runs are system-level benchmark data rather than user data, so
they hang off nothing — every signed-in user can read them.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Stable across databases, so a run exported to JSON and imported elsewhere
    # (e.g. into the hosted demo) is recognised rather than duplicated.
    uid: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    judge_version: Mapped[str] = mapped_column(String(16), nullable=False)
    golden_set_version: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    judge_model: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    judged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_correctness: Mapped[float | None] = mapped_column(Float)
    avg_completeness: Mapped[float | None] = mapped_column(Float)
    avg_relevance: Mapped[float | None] = mapped_column(Float)
    avg_clarity: Mapped[float | None] = mapped_column(Float)
    avg_overall: Mapped[float | None] = mapped_column(Float)
    p50_latency_ms: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    notes: Mapped[str | None] = mapped_column(Text)

    results: Mapped[list[EvalResult]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="EvalResult.position",
    )


class EvalResult(Base):
    __tablename__ = "eval_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("eval_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    question_id: Mapped[str] = mapped_column(String(60), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_route: Mapped[str] = mapped_column(String(20), nullable=False)
    route: Mapped[str | None] = mapped_column(String(20))
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    correctness: Mapped[int | None] = mapped_column(Integer)
    completeness: Mapped[int | None] = mapped_column(Integer)
    relevance: Mapped[int | None] = mapped_column(Integer)
    clarity: Mapped[int | None] = mapped_column(Integer)
    overall: Mapped[float | None] = mapped_column(Float)
    rationale: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    error: Mapped[str | None] = mapped_column(Text)

    run: Mapped[EvalRun] = relationship(back_populates="results")
