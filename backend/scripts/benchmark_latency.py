"""Reproducible latency benchmark against the in-process test stack.

This measures Orchestra's own overhead with FakeLLM. It does not call Groq,
Gemini, or Ollama. Hosted numbers in the README are a different measurement
and are not updated by this script.

From the backend directory:

    python scripts/benchmark_latency.py

Writes backend/benchmarks/latency_harness.json
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import tests.conftest as harness  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.core.limiter import RateLimiter, get_rate_limiter  # noqa: E402
from app.evaluation.latency_benchmark import CASES, summarize_samples  # noqa: E402
from app.main import app  # noqa: E402
from tests.conftest import auth, make_project, register, sse_events  # noqa: E402
from tests.fakes import FakeLLM, FakeRedis  # noqa: E402

REPEATS = 5
WARMUP = 1
OUT = BACKEND / "benchmarks" / "latency_harness.json"


def main() -> None:
    settings.chat_rate_limit_per_minute = 500
    settings.chat_daily_token_budget = 2_000_000
    Base.metadata.create_all(bind=harness.database.engine)
    fake_redis = FakeRedis()
    fake_llm = FakeLLM()
    import app.core.limiter as limiter_mod
    import app.core.redis_client as redis_mod
    import app.memory.redis as memory_redis
    import app.services.chat_service as chat_service

    redis_mod.get_redis = lambda: fake_redis
    limiter_mod.get_redis = lambda: fake_redis
    memory_redis.get_redis = lambda: fake_redis
    chat_service.get_llm_service = lambda: fake_llm
    limiter_mod._limiter = RateLimiter(client=fake_redis)

    app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter(client=fake_redis)
    client = TestClient(app)
    token, _ = register(client, email="benchmark@example.com")
    project_id = make_project(client, token)

    cases_out = []
    for case in CASES:
        samples = []
        errors = 0
        for index in range(WARMUP + REPEATS):
            response = client.post(
                "/api/v1/chat",
                json={
                    "project_id": project_id,
                    "message": case.message,
                    "model": "llama-3.1-8b-instant",
                    "enable_tools": case.enable_tools,
                    "enable_orchestra": case.enable_orchestra,
                },
                headers=auth(token),
            )
            if response.status_code != 200:
                errors += 1
                continue
            done = sse_events(response.text)[-1]
            if done.get("type") != "done":
                errors += 1
                continue
            if index < WARMUP:
                continue
            samples.append(
                {
                    "latency_ms": done.get("latency_ms"),
                    "ttft_provider_ms": done.get("ttft_provider_ms"),
                    "ttft_delivered_ms": done.get("ttft_delivered_ms"),
                    "total_tokens": done.get("total_tokens"),
                    "total_cost_usd": done.get("total_cost_usd"),
                }
            )
        summary = summarize_samples(samples)
        cases_out.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "message": case.message,
                "notes": case.notes,
                "expect_route": case.expect_route,
                "errors": errors,
                "error_rate": errors / (WARMUP + REPEATS),
                **summary,
            }
        )

    report = {
        "measured_at": datetime.now(UTC).isoformat(),
        "provider": "fake",
        "model": "llama-3.1-8b-instant",
        "label": (
            "In-process harness overhead with FakeLLM and SQLite or the "
            "configured test database. Not a live provider benchmark."
        ),
        "warmup_discarded": WARMUP,
        "repeats": REPEATS,
        "cases": cases_out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    for item in cases_out:
        latency = item["latency_ms"]
        ttft = item["ttft_delivered_ms"]
        print(
            f"{item['case_id']}: p50 {latency['p50']:.1f} ms, "
            f"p95 {latency['p95']:.1f} ms, "
            f"ttft p50 {ttft['p50']:.1f} ms, errors {item['errors']}"
        )


if __name__ == "__main__":
    main()
