"""Observability API — dashboard, executions, replay, ratings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.dashboard.service import DashboardService
from app.models import User
from app.models.execution import Execution
from app.schemas.execution import (
    DashboardSummaryOut,
    ExecutionDetailOut,
    ExecutionRatingIn,
    ExecutionStepOut,
    ExecutionSummaryOut,
    MetricsBreakdownOut,
    ReplayPayloadOut,
)

router = APIRouter(tags=["observability"])


def _step_out(step) -> ExecutionStepOut:
    return ExecutionStepOut(
        id=step.id,
        sequence=step.sequence,
        step_name=step.step_name,
        status=step.status,
        latency_ms=step.latency_ms,
        input_tokens=step.input_tokens,
        output_tokens=step.output_tokens,
        tokens=step.tokens,
        cost_usd=float(step.cost_usd or 0),
        detail=step.detail,
        started_at=step.started_at,
        completed_at=step.completed_at,
    )


def _summary_out(ex: Execution) -> ExecutionSummaryOut:
    return ExecutionSummaryOut(
        id=ex.id,
        project_id=ex.project_id,
        conversation_id=ex.conversation_id,
        agent_id=ex.agent_id,
        message_id=ex.message_id,
        status=ex.status,
        pipeline=ex.pipeline,
        model_name=ex.model_name,
        prompt=ex.prompt,
        final_response=ex.final_response,
        started_at=ex.started_at,
        completed_at=ex.completed_at,
        latency_ms=ex.latency_ms,
        input_tokens=ex.input_tokens,
        output_tokens=ex.output_tokens,
        total_tokens=ex.total_tokens,
        api_calls=ex.api_calls,
        total_cost_usd=float(ex.total_cost_usd or 0),
        success=ex.success,
        user_rating=ex.user_rating,
        scores=ex.scores,
    )


def _detail_out(ex: Execution) -> ExecutionDetailOut:
    base = _summary_out(ex)
    return ExecutionDetailOut(
        **base.model_dump(),
        error_detail=ex.error_detail,
        snapshot=ex.snapshot,
        steps=[_step_out(s) for s in (ex.steps or [])],
    )


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def dashboard_summary(
    project_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardSummaryOut:
    data = DashboardService(db).summary(user=current_user, project_id=project_id)
    return DashboardSummaryOut(**data)


@router.get("/dashboard/metrics", response_model=MetricsBreakdownOut)
def dashboard_metrics(
    project_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MetricsBreakdownOut:
    data = DashboardService(db).metrics_breakdown(user=current_user, project_id=project_id)
    return MetricsBreakdownOut(**data)


@router.get("/executions", response_model=list[ExecutionSummaryOut])
def list_executions(
    project_id: int = Query(...),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ExecutionSummaryOut]:
    rows = DashboardService(db).list_executions(
        user=current_user, project_id=project_id, limit=limit
    )
    return [_summary_out(r) for r in rows]


@router.get("/executions/{execution_id}", response_model=ExecutionDetailOut)
def get_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExecutionDetailOut:
    ex = DashboardService(db).get_execution(user=current_user, execution_id=execution_id)
    return _detail_out(ex)


@router.post("/executions/{execution_id}/rating", response_model=ExecutionSummaryOut)
def rate_execution(
    execution_id: int,
    payload: ExecutionRatingIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExecutionSummaryOut:
    ex = DashboardService(db).set_rating(
        user=current_user, execution_id=execution_id, rating=payload.rating
    )
    return _summary_out(ex)


@router.post("/executions/{execution_id}/replay", response_model=ReplayPayloadOut)
def replay_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReplayPayloadOut:
    """Return the stored prompt + context so the client can re-run the turn."""
    ex = DashboardService(db).get_execution(user=current_user, execution_id=execution_id)
    pipeline = ex.pipeline or "direct"
    return ReplayPayloadOut(
        execution_id=ex.id,
        project_id=ex.project_id,
        conversation_id=ex.conversation_id,
        agent_id=ex.agent_id,
        model_name=ex.model_name,
        prompt=ex.prompt,
        pipeline=pipeline,
        enable_orchestra=pipeline.startswith("orchestra"),
        enable_tools=pipeline == "tools",
        snapshot=ex.snapshot,
        final_response=ex.final_response,
    )
