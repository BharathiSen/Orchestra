"""Read-only access to offline evaluation runs.

Runs are produced by ``scripts/run_eval.py`` — never over HTTP — so there is no
endpoint that can trigger paid model calls. They are system-level benchmark
data, readable by any signed-in user.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.models.eval_run import EvalRun
from app.schemas.evals import EvalRunDetailOut, EvalRunSummaryOut

router = APIRouter(prefix="/evals", tags=["evaluations"])


@router.get("/runs", response_model=list[EvalRunSummaryOut])
def list_eval_runs(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[EvalRun]:
    # Oldest first: the UI charts runs left to right in the order they happened.
    return list(db.scalars(select(EvalRun).order_by(EvalRun.created_at, EvalRun.id)))


@router.get("/runs/{run_id}", response_model=EvalRunDetailOut)
def get_eval_run(
    run_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> EvalRun:
    run = db.scalar(
        select(EvalRun).where(EvalRun.id == run_id).options(selectinload(EvalRun.results))
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval run not found")
    return run
