"""Dashboard aggregations for observability UI."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.evaluation.metrics import average, success_rate, sum_decimal_as_float
from app.models import Project, User
from app.models.execution import Execution, ExecutionStep


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _owned_project(self, *, project_id: int, user: User) -> Project:
        project = self.db.get(Project, project_id)
        if project is None or project.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project

    def _owned_execution(self, *, execution_id: int, user: User) -> Execution:
        execution = self.db.scalar(
            select(Execution)
            .where(Execution.id == execution_id)
            .options(selectinload(Execution.steps))
        )
        if execution is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        project = self.db.get(Project, execution.project_id)
        if project is None or project.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        return execution

    def summary(self, *, user: User, project_id: int) -> dict[str, Any]:
        self._owned_project(project_id=project_id, user=user)
        start = datetime.now(UTC) - timedelta(hours=24)
        rows = list(
            self.db.scalars(
                select(Execution).where(
                    Execution.project_id == project_id,
                    Execution.started_at >= start,
                )
            ).all()
        )
        total = len(rows)
        successes = sum(1 for r in rows if r.success)
        return {
            "project_id": project_id,
            "window": "24h",
            "executions_today": total,
            "success_rate": success_rate(total, successes),
            "average_latency_ms": average([r.latency_ms for r in rows]),
            "total_tokens": sum(r.total_tokens for r in rows),
            "total_cost_usd": sum_decimal_as_float([r.total_cost_usd for r in rows]),
            "average_tokens": average([r.total_tokens for r in rows]),
        }

    def list_executions(
        self,
        *,
        user: User,
        project_id: int,
        limit: int = 50,
    ) -> list[Execution]:
        self._owned_project(project_id=project_id, user=user)
        return list(
            self.db.scalars(
                select(Execution)
                .where(Execution.project_id == project_id)
                .order_by(Execution.started_at.desc())
                .limit(min(limit, 200))
            ).all()
        )

    def get_execution(self, *, user: User, execution_id: int) -> Execution:
        return self._owned_execution(execution_id=execution_id, user=user)

    def set_rating(self, *, user: User, execution_id: int, rating: int) -> Execution:
        if rating < 1 or rating > 5:
            raise HTTPException(status_code=400, detail="rating must be 1-5")
        execution = self._owned_execution(execution_id=execution_id, user=user)
        execution.user_rating = rating
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        return execution

    def metrics_breakdown(self, *, user: User, project_id: int) -> dict[str, Any]:
        self._owned_project(project_id=project_id, user=user)
        start = datetime.now(UTC) - timedelta(hours=24)
        rows = list(
            self.db.scalars(
                select(Execution).where(
                    Execution.project_id == project_id,
                    Execution.started_at >= start,
                )
            ).all()
        )
        by_pipeline: dict[str, int] = {}
        for r in rows:
            by_pipeline[r.pipeline] = by_pipeline.get(r.pipeline, 0) + 1

        step_latencies: dict[str, list[int]] = {}
        steps = list(
            self.db.scalars(
                select(ExecutionStep)
                .join(Execution)
                .where(
                    Execution.project_id == project_id,
                    Execution.started_at >= start,
                )
            ).all()
        )
        for s in steps:
            step_latencies.setdefault(s.step_name, []).append(s.latency_ms)

        return {
            "project_id": project_id,
            "executions": len(rows),
            "by_pipeline": by_pipeline,
            "step_avg_latency_ms": {
                name: average(vals) for name, vals in step_latencies.items()
            },
            "rated_count": sum(1 for r in rows if r.user_rating is not None),
            "average_rating": average(
                [r.user_rating for r in rows if r.user_rating is not None]
            ),
        }
