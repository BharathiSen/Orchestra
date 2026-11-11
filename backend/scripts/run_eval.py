"""Run the golden set through Orchestra with a live model and judge the answers.

    python scripts/run_eval.py --label "baseline"
    python scripts/run_eval.py --label "tighter reviewer" --limit 3
    python scripts/run_eval.py import evals/runs/*.json   # load into this database

Every run is written to ``evals/runs/<timestamp>-<prompt version>.json`` (commit
these: they are the evidence behind the chart) and, unless ``--no-db``, saved
to the configured database, where the Evaluations page reads it. ``import`` is
idempotent, so re-importing the same files into the hosted demo is safe.

This makes real, billed model calls — roughly 5 per question plus one judge
call. It is never run in CI; the machinery is covered by tests/test_evals.py
with a stub model.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from app.core.config import settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.evaluation.eval_runner import run_eval, save_run  # noqa: E402
from app.evaluation.golden_set import GOLDEN_QUESTIONS  # noqa: E402
from app.services.llm_provider import get_default_model, get_llm_service  # noqa: E402

RUNS_DIR = BACKEND / "evals" / "runs"
DEFAULT_JUDGE_MODEL = "openai/gpt-oss-120b"


def _save_to_db(data: dict) -> None:
    import app.models  # noqa: F401  (register every table)

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        run, created = save_run(db, data)
        print(f"  database: run #{run.id} {'saved' if created else 'already present'}")


def cmd_run(args: argparse.Namespace) -> int:
    questions = GOLDEN_QUESTIONS[: args.limit] if args.limit else GOLDEN_QUESTIONS
    model = args.model or get_default_model()
    llm = get_llm_service()
    print(
        f"Evaluating {len(questions)} questions · provider={settings.active_llm_provider} "
        f"· model={model} · judge={args.judge_model}"
    )

    def progress(done: int, total: int, question, row: dict) -> None:
        score = f"{row['overall']:.2f}" if row.get("overall") is not None else "  — "
        flag = f"  ! {row['error'][:70]}" if row.get("error") else ""
        print(f"  [{done:2d}/{total}] {score}  {question.id:<18} route={row.get('route')}{flag}")

    data = run_eval(
        llm,
        llm,
        model=model,
        judge_model=args.judge_model,
        label=args.label,
        questions=questions,
        notes=args.notes,
        pause_s=args.pause,
        progress=progress,
    )

    summary = data["summary"]
    print(
        f"\nprompt version {data['prompt_version']} · overall {summary['avg_overall']} · "
        f"judged {summary['judged_count']}/{summary['question_count']} · "
        f"cost ${summary['total_cost_usd']}"
    )

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.fromisoformat(data["created_at"]).strftime("%Y%m%d-%H%M%S")
    out = RUNS_DIR / f"{stamp}-{data['prompt_version']}.json"
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"  written: {out.relative_to(BACKEND)}")

    if not args.no_db:
        _save_to_db(data)
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    for path in args.files:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        print(f"{path}: {data['label']} ({data['prompt_version']})")
        _save_to_db(data)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command")

    imp = sub.add_parser("import", help="load exported runs into the database")
    imp.add_argument("files", nargs="+")

    parser.add_argument("--label", default="eval", help="name shown on the chart")
    parser.add_argument("--notes", help="what changed since the last run")
    parser.add_argument("--model", help="pipeline model (default: provider default)")
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    parser.add_argument("--limit", type=int, help="only the first N questions")
    parser.add_argument("--pause", type=float, default=0.0, help="seconds between questions")
    parser.add_argument("--no-db", action="store_true", help="write JSON only")

    args = parser.parse_args()
    if args.command == "import":
        return cmd_import(args)
    return cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
