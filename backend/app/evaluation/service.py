"""Evaluation service — persist scores onto executions."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.evaluation.scorer import score_execution
from app.models.execution import Execution


class EvaluationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def score_and_attach(self, execution: Execution) -> dict[str, Any]:
        snapshot = execution.snapshot or {}
        scores = score_execution(
            prompt=execution.prompt or "",
            response=execution.final_response or "",
            retrieved_chunks=snapshot.get("retrieved_chunks") or [],
            had_error=execution.status == "error",
            latency_ms=execution.latency_ms or 0,
        )
        execution.scores = scores
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        return scores
