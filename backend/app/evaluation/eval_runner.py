"""Run the golden set through the real Orchestra pipeline, judge it, store it.

A run is built as a plain dict — the same shape as its JSON export — and
``save_run`` persists either a fresh run or an imported file. One code path, so
a run reviewed in the repository and the same run in the database cannot drift.
"""

from __future__ import annotations

import statistics
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evaluation.golden_set import GOLDEN_QUESTIONS, GoldenQuestion, golden_set_version
from app.evaluation.judge import CRITERIA, JudgeParseError, judge_answer, judge_version
from app.evaluation.prompt_version import prompt_version
from app.evaluation.tracker import ExecutionTracker
from app.models.eval_run import EvalResult, EvalRun
from app.observability.tracking_llm import TrackingLLM
from app.orchestrator import OrchestraEngine
from app.prompts.system import default_assistant_prompt
from app.tools import ensure_default_tools

ProgressFn = Callable[[int, int, GoldenQuestion, dict[str, Any]], None]


def _initial_state(question: str, model: str) -> dict[str, Any]:
    # Mirrors what chat sends for an Orchestra turn on a fresh conversation,
    # minus memory and knowledge bases, so the eval measures the prompts alone.
    return {
        "question": question,
        "system_prompt": default_assistant_prompt(),
        "model": model,
        "temperature": 0.2,
        "knowledge_base_ids": [],
        "messages": [{"role": "user", "content": question}],
        "memory": {},
        "retrieved_docs": [],
        "current_agent": "",
        "errors": [],
        "execution_history": [],
        "plan": "",
        "research_notes": "",
        "draft": "",
        "review_notes": "",
        "final_response": "",
        # Not streamed: the answer is collected whole, exactly as the user
        # would end up seeing it.
        "stream_final": False,
    }


def answer_question(llm: Any, *, model: str, question: GoldenQuestion, tools: Any) -> dict[str, Any]:
    """Run one question through Orchestra. Never raises; failures are recorded."""
    tracker = ExecutionTracker(model_name=model, pipeline="eval")
    engine = OrchestraEngine(llm=TrackingLLM(llm, tracker), rag=None, tools=tools)
    started = time.perf_counter()
    outcome: dict[str, Any] = {"route": None, "answer": "", "error": None}
    failed_agents: list[str] = []
    agent_errors: list[str] = []
    try:
        for event in engine.run(_initial_state(question.question, model)):
            if event.get("type") == "orchestra_step" and event.get("status") == "error":
                failed_agents.append(str(event.get("agent")))
            elif event.get("type") == "orchestra_result":
                outcome["route"] = event.get("route")
                outcome["answer"] = str(event.get("final_response") or "")
                agent_errors = [str(e) for e in event.get("errors") or []]
    except Exception as exc:  # noqa: BLE001 - one bad question must not end the run
        outcome["error"] = f"{type(exc).__name__}: {exc}"
    if failed_agents and not outcome["error"]:
        # Keep the agents' own messages: "agent failed" alone cannot tell a
        # rate limit from a parsing bug from a provider outage.
        detail = f" — {agent_errors[0][:300]}" if agent_errors else ""
        outcome["error"] = "agent failed: " + ", ".join(dict.fromkeys(failed_agents)) + detail
    outcome["latency_ms"] = int((time.perf_counter() - started) * 1000)
    outcome["tokens"] = tracker.total_tokens
    outcome["cost_usd"] = str(tracker.total_cost_usd)
    return outcome


def _join_errors(first: str | None, second: str) -> str:
    return f"{first}; {second}" if first else second


def _summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    judged = [r for r in results if r.get("overall") is not None]

    def avg(key: str) -> float | None:
        return round(statistics.fmean(r[key] for r in judged), 3) if judged else None

    latencies = [r["latency_ms"] for r in results if not r.get("error")]
    return {
        "question_count": len(results),
        "judged_count": len(judged),
        "error_count": sum(1 for r in results if r.get("error")),
        **{f"avg_{c}": avg(c) for c in CRITERIA},
        "avg_overall": avg("overall"),
        "p50_latency_ms": int(statistics.median(latencies)) if latencies else None,
        "total_tokens": sum(int(r["tokens"]) for r in results),
        "total_cost_usd": str(sum((Decimal(r["cost_usd"]) for r in results), Decimal("0"))),
    }


def run_eval(
    llm: Any,
    judge_llm: Any,
    *,
    model: str,
    judge_model: str,
    label: str,
    questions: tuple[GoldenQuestion, ...] = GOLDEN_QUESTIONS,
    notes: str | None = None,
    pause_s: float = 0.0,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    """Answer and judge every question. Returns the run as an export-ready dict."""
    tools = ensure_default_tools()
    results: list[dict[str, Any]] = []
    for index, question in enumerate(questions):
        outcome = answer_question(llm, model=model, question=question, tools=tools)
        row: dict[str, Any] = {
            "question_id": question.id,
            "category": question.category,
            "question": question.question,
            "expected_route": question.expected_route,
            **outcome,
            **dict.fromkeys(CRITERIA),
            "overall": None,
            "rationale": None,
        }
        # Judge whatever answer the user would have seen — including a fallback
        # after an agent failed. Skipping those would drop exactly the bad
        # answers from the average and flatter the score.
        if outcome["answer"]:
            try:
                verdict = judge_answer(
                    judge_llm,
                    model=judge_model,
                    question=question.question,
                    key_points=question.key_points,
                    answer=outcome["answer"],
                )
                row.update({c: getattr(verdict, c) for c in CRITERIA})
                row["overall"] = verdict.overall
                row["rationale"] = verdict.rationale
            except JudgeParseError as exc:
                row["error"] = _join_errors(row["error"], f"judge: {exc}")
            except Exception as exc:  # noqa: BLE001 - provider error on the judge call
                row["error"] = _join_errors(row["error"], f"judge: {type(exc).__name__}: {exc}")
        results.append(row)
        if progress:
            progress(index + 1, len(questions), question, row)
        if pause_s and index < len(questions) - 1:
            time.sleep(pause_s)

    return {
        "uid": str(uuid.uuid4()),
        "label": label,
        "created_at": datetime.now(UTC).isoformat(),
        "prompt_version": prompt_version(),
        "judge_version": judge_version(),
        "golden_set_version": golden_set_version(questions),
        "model": model,
        "judge_model": judge_model,
        "notes": notes,
        "summary": _summarise(results),
        "results": results,
    }


def save_run(db: Session, data: dict[str, Any]) -> tuple[EvalRun, bool]:
    """Persist a run dict. Idempotent on ``uid``: returns (run, created)."""
    existing = db.scalar(select(EvalRun).where(EvalRun.uid == data["uid"]))
    if existing is not None:
        return existing, False

    summary = data["summary"]
    run = EvalRun(
        uid=data["uid"],
        label=data["label"],
        prompt_version=data["prompt_version"],
        judge_version=data["judge_version"],
        golden_set_version=data["golden_set_version"],
        model=data["model"],
        judge_model=data["judge_model"],
        created_at=datetime.fromisoformat(data["created_at"]),
        notes=data.get("notes"),
        question_count=summary["question_count"],
        judged_count=summary["judged_count"],
        error_count=summary["error_count"],
        avg_correctness=summary["avg_correctness"],
        avg_completeness=summary["avg_completeness"],
        avg_relevance=summary["avg_relevance"],
        avg_clarity=summary["avg_clarity"],
        avg_overall=summary["avg_overall"],
        p50_latency_ms=summary["p50_latency_ms"],
        total_tokens=summary["total_tokens"],
        total_cost_usd=Decimal(summary["total_cost_usd"]),
    )
    for position, row in enumerate(data["results"]):
        run.results.append(
            EvalResult(
                position=position,
                question_id=row["question_id"],
                category=row["category"],
                question=row["question"],
                expected_route=row["expected_route"],
                route=row.get("route"),
                answer=row.get("answer") or "",
                correctness=row.get("correctness"),
                completeness=row.get("completeness"),
                relevance=row.get("relevance"),
                clarity=row.get("clarity"),
                overall=row.get("overall"),
                rationale=row.get("rationale"),
                latency_ms=int(row.get("latency_ms") or 0),
                tokens=int(row.get("tokens") or 0),
                cost_usd=Decimal(str(row.get("cost_usd") or "0")),
                error=row.get("error"),
            )
        )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run, True
