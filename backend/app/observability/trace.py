"""Execution tracing — create/update Execution + ExecutionStep rows."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.evaluation.scorer import score_execution
from app.evaluation.tracker import ExecutionTracker
from app.models.execution import Execution, ExecutionStep
from app.observability.logger import log_event


class TraceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def start(
        self,
        *,
        user_id: int,
        project_id: int,
        conversation_id: int | None,
        agent_id: int | None,
        model_name: str,
        pipeline: str,
        prompt: str,
    ) -> Execution:
        execution = Execution(
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
            status="running",
            pipeline=pipeline,
            model_name=model_name,
            prompt=prompt,
            started_at=datetime.now(UTC),
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        log_event(
            "execution_started",
            execution_id=execution.id,
            project_id=project_id,
            pipeline=pipeline,
            model=model_name,
        )
        return execution

    def complete(
        self,
        execution: Execution,
        *,
        tracker: ExecutionTracker,
        final_response: str,
        message_id: int | None = None,
        status: str = "completed",
        error_detail: str | None = None,
        snapshot: dict[str, Any] | None = None,
    ) -> Execution:
        merged_snapshot = dict(tracker.snapshot)
        if snapshot:
            merged_snapshot.update(snapshot)

        execution.status = status
        execution.final_response = final_response
        execution.error_detail = error_detail
        execution.completed_at = datetime.now(UTC)
        execution.latency_ms = tracker.latency_ms
        execution.input_tokens = tracker.input_tokens
        execution.output_tokens = tracker.output_tokens
        execution.total_tokens = tracker.total_tokens
        execution.api_calls = tracker.api_calls
        execution.total_cost_usd = tracker.total_cost_usd
        execution.success = status == "completed" and bool((final_response or "").strip())
        execution.message_id = message_id
        execution.pipeline = tracker.pipeline or execution.pipeline
        execution.snapshot = merged_snapshot or None
        execution.scores = score_execution(
            prompt=execution.prompt or "",
            response=final_response or "",
            retrieved_chunks=(merged_snapshot or {}).get("retrieved_chunks") or [],
            had_error=status == "error",
            latency_ms=execution.latency_ms,
        )

        execution.steps.clear()
        self.db.flush()
        for step in tracker.steps:
            execution.steps.append(
                ExecutionStep(
                    sequence=step.sequence,
                    step_name=step.step_name,
                    status=step.status,
                    latency_ms=step.latency_ms,
                    input_tokens=step.input_tokens,
                    output_tokens=step.output_tokens,
                    tokens=step.tokens,
                    cost_usd=step.cost_usd or Decimal("0"),
                    detail=step.detail or None,
                    started_at=step.started_at,
                    completed_at=step.completed_at,
                )
            )

        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        log_event(
            "execution_completed",
            execution_id=execution.id,
            status=status,
            latency_ms=execution.latency_ms,
            total_tokens=execution.total_tokens,
            total_cost_usd=str(execution.total_cost_usd),
            success=execution.success,
        )
        return execution

    def get(self, execution_id: int) -> Execution | None:
        return self.db.scalar(
            select(Execution)
            .where(Execution.id == execution_id)
            .options(selectinload(Execution.steps))
        )
