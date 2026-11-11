"""Offline evaluation: golden set, LLM judge, prompt versioning, runs, and API.

The judge and the pipeline are both stubbed here — these tests prove the
machinery (scoring, aggregation, storage, idempotent import, access control),
not answer quality. Answer quality is what `scripts/run_eval.py` measures with
a live model.
"""

from __future__ import annotations

import json

import pytest

from app.evaluation.eval_runner import run_eval, save_run
from app.evaluation.golden_set import GOLDEN_QUESTIONS, golden_set_version
from app.evaluation.judge import JudgeParseError, judge_version, parse_judgement
from app.evaluation.prompt_version import prompt_version
from app.orchestrator.routing import classify_route
from tests.conftest import auth, register
from tests.fakes import FakeLLM

JUDGE_JSON = json.dumps(
    {"correctness": 5, "completeness": 4, "relevance": 5, "clarity": 4, "rationale": "Solid."}
)


def _stub(judge_reply: str = JUDGE_JSON) -> FakeLLM:
    # The judge's system prompt is the only one containing this phrase, so the
    # stub answers the judge with scores and every pipeline agent with text.
    return FakeLLM({"strict, fair evaluator": judge_reply}, default=None)


# --- golden set --------------------------------------------------------------


def test_golden_question_ids_are_unique():
    ids = [q.id for q in GOLDEN_QUESTIONS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("question", GOLDEN_QUESTIONS, ids=lambda q: q.id)
def test_expected_route_matches_the_router(question):
    """The set must really exercise the path each question claims to."""
    assert classify_route(question.question) == question.expected_route


def test_golden_set_covers_both_pipeline_routes():
    assert {q.expected_route for q in GOLDEN_QUESTIONS} == {"simple", "full"}


def test_golden_set_version_tracks_content():
    assert golden_set_version() == golden_set_version()
    assert golden_set_version(GOLDEN_QUESTIONS[:-1]) != golden_set_version()


# --- judge parsing ------------------------------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        JUDGE_JSON,
        f"```json\n{JUDGE_JSON}\n```",
        f"Here is my assessment:\n{JUDGE_JSON}\nThanks.",
        JUDGE_JSON.replace(": 4,", ": 4.0,"),
    ],
    ids=["plain", "fenced", "prose", "float-integer"],
)
def test_judge_reply_formats_are_parsed(reply):
    verdict = parse_judgement(reply)
    assert (verdict.correctness, verdict.completeness) == (5, 4)
    assert verdict.overall == 4.5
    assert verdict.rationale == "Solid."


@pytest.mark.parametrize(
    "reply",
    [
        "I would give it a 4.",
        JUDGE_JSON.replace('"clarity": 4', '"clarity": 6'),
        JUDGE_JSON.replace('"clarity": 4', '"clarity": 3.5'),
        JUDGE_JSON.replace('"clarity": 4', '"clarity": "4"'),
        JUDGE_JSON.replace('"clarity": 4, ', ""),
    ],
    ids=["no-json", "out-of-range", "fractional", "string", "missing"],
)
def test_invalid_judge_replies_are_rejected_not_guessed(reply):
    with pytest.raises(JudgeParseError):
        parse_judgement(reply)


# --- prompt versioning --------------------------------------------------------


def test_prompt_version_changes_with_prompt_text_only(tmp_path):
    (tmp_path / "__init__.py").write_text("# ignored\n")
    (tmp_path / "writer.py").write_bytes(b"PROMPT = 'one'\n")
    base = prompt_version(tmp_path)

    assert prompt_version(tmp_path) == base
    (tmp_path / "writer.py").write_bytes(b"PROMPT = 'one'\r\n")
    assert prompt_version(tmp_path) == base, "CRLF vs LF must not change the version"
    (tmp_path / "__init__.py").write_text("# still ignored\n")
    assert prompt_version(tmp_path) == base
    (tmp_path / "writer.py").write_bytes(b"PROMPT = 'two'\n")
    assert prompt_version(tmp_path) != base


def test_real_prompts_have_a_version():
    assert len(prompt_version()) == 8
    assert len(judge_version()) == 8


# --- runs ---------------------------------------------------------------------


def test_run_answers_judges_and_summarises():
    stub = _stub()
    data = run_eval(stub, stub, model="m", judge_model="j", label="t", questions=GOLDEN_QUESTIONS[:3])

    assert [r["question_id"] for r in data["results"]] == [q.id for q in GOLDEN_QUESTIONS[:3]]
    summary = data["summary"]
    assert summary["question_count"] == 3
    assert summary["judged_count"] == 3
    assert summary["error_count"] == 0
    assert summary["avg_overall"] == 4.5
    assert summary["total_tokens"] > 0
    assert data["prompt_version"] == prompt_version()
    assert all(r["answer"] for r in data["results"])


def test_unparseable_judge_reply_is_recorded_not_scored():
    stub = _stub(judge_reply="Looks good to me!")
    data = run_eval(stub, stub, model="m", judge_model="j", label="t", questions=GOLDEN_QUESTIONS[:2])

    assert data["summary"]["judged_count"] == 0
    assert data["summary"]["avg_overall"] is None
    assert all(r["error"].startswith("judge:") for r in data["results"])


def test_save_is_idempotent_and_survives_a_json_round_trip(db_session):
    stub = _stub()
    data = run_eval(stub, stub, model="m", judge_model="j", label="t", questions=GOLDEN_QUESTIONS[:2])
    exported = json.loads(json.dumps(data))  # exactly what lands in evals/runs/*.json

    run, created = save_run(db_session, exported)
    assert created
    assert run.avg_overall == 4.5
    assert [r.question_id for r in run.results] == [q.id for q in GOLDEN_QUESTIONS[:2]]

    again, created_again = save_run(db_session, exported)
    assert not created_again
    assert again.id == run.id


# --- API ----------------------------------------------------------------------


def test_eval_runs_require_authentication(client):
    assert client.get("/api/v1/evals/runs").status_code == 401


def test_eval_runs_are_listed_oldest_first_with_detail(client, db_session):
    stub = _stub()
    first = run_eval(stub, stub, model="m", judge_model="j", label="first", questions=GOLDEN_QUESTIONS[:1])
    second = run_eval(stub, stub, model="m", judge_model="j", label="second", questions=GOLDEN_QUESTIONS[:2])
    save_run(db_session, first)
    save_run(db_session, second)
    token, _ = register(client)

    runs = client.get("/api/v1/evals/runs", headers=auth(token)).json()
    assert [r["label"] for r in runs] == ["first", "second"]

    detail = client.get(f"/api/v1/evals/runs/{runs[1]['id']}", headers=auth(token)).json()
    assert len(detail["results"]) == 2
    assert detail["results"][0]["correctness"] == 5

    missing = client.get("/api/v1/evals/runs/999999", headers=auth(token))
    assert missing.status_code == 404


class _FailingPipelineStub(FakeLLM):
    """Every pipeline call fails; only the judge answers."""

    def complete_chat(self, *, messages, **kwargs):
        if any("strict, fair evaluator" in str(m.get("content")) for m in messages):
            return super().complete_chat(messages=messages, **kwargs)
        raise RuntimeError("429 Too Many Requests")


def test_answers_after_agent_failures_are_still_judged():
    """Skipping degraded answers would drop the bad ones and flatter the score."""
    stub = _FailingPipelineStub({"strict, fair evaluator": JUDGE_JSON}, default=None)
    data = run_eval(stub, stub, model="m", judge_model="j", label="t", questions=GOLDEN_QUESTIONS[:1])

    row = data["results"][0]
    assert row["error"].startswith("agent failed:")
    assert "429" in row["error"], "the agents' own error message must be kept"
    assert row["overall"] is not None
    assert data["summary"]["judged_count"] == 1
    assert data["summary"]["error_count"] == 1
