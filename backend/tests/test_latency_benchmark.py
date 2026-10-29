"""Latency timeline contract and a small reproducible benchmark.

Numbers produced here are harness overhead against FakeLLM. They are not
provider latency and must not be compared with the hosted figures in the README.
"""

from __future__ import annotations

import time

from app.core.config import settings
from app.evaluation.latency_benchmark import CASES, summarize_samples
from app.memory.service import MemoryService
from app.observability.latency import (
    LatencyTimeline,
    current_timeline,
    pop_timeline,
    push_timeline,
)
from tests.conftest import auth, make_project, register, sse_events


def _chat(client, token, project_id, case):
    return client.post(
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


def test_timeline_durations_are_monotonic_and_recording_fails_open(monkeypatch):
    timeline = LatencyTimeline()
    started = time.perf_counter()
    time.sleep(0.01)
    timeline.add_duration("memory_lookup", started)
    assert timeline.durations_ms["memory_lookup"] >= 0
    timeline.add_duration("memory_lookup", time.perf_counter())
    assert timeline.durations_ms["memory_lookup"] >= 0

    def explode():
        raise RuntimeError("clock failed")

    monkeypatch.setattr(timeline, "elapsed_ms", explode)
    timeline.mark("should_not_raise")
    assert timeline.as_dict()["durations_ms"]["memory_lookup"] >= 0

    token = push_timeline(timeline)
    assert current_timeline() is timeline
    pop_timeline(token)
    assert current_timeline() is None


def test_direct_chat_records_ttft_and_stage_marks(client):
    token, _ = register(client, email="latency@example.com")
    project_id = make_project(client, token)
    case = next(item for item in CASES if item.case_id == "direct_chat")

    response = _chat(client, token, project_id, case)
    assert response.status_code == 200
    done = sse_events(response.text)[-1]
    assert done["type"] == "done"
    assert done["ttft_delivered_ms"] is not None
    assert done["ttft_provider_ms"] is not None
    assert done["ttft_provider_ms"] <= done["ttft_delivered_ms"]
    assert done["latency_ms"] >= done["ttft_delivered_ms"]

    execution = client.get(
        f"/api/v1/executions/{done['execution_id']}",
        headers=auth(token),
    ).json()
    latency = execution["snapshot"]["latency"]
    marks = latency["marks_ms"]
    for name in (
        "request_received",
        "auth_complete",
        "memory_lookup",
        "routing",
        "generation_start",
        "first_provider_token",
        "first_token_delivered",
        "complete",
    ):
        assert name in marks, name
    assert marks["request_received"] <= marks["auth_complete"] <= marks["first_token_delivered"]
    assert latency["execution_id"] == execution["id"]
    assert latency["llm_calls"]
    assert "content" not in latency
    assert latency["errors"] == []


def test_provider_delay_is_visible_in_ttft(client, fake_llm):
    fake_llm.first_chunk_delay_s = 0.05
    token, _ = register(client, email="ttft@example.com")
    project_id = make_project(client, token)
    case = next(item for item in CASES if item.case_id == "direct_chat")

    response = _chat(client, token, project_id, case)
    done = sse_events(response.text)[-1]
    assert done["ttft_provider_ms"] >= 40
    assert done["ttft_delivered_ms"] >= done["ttft_provider_ms"]


def test_memory_context_reloads_only_after_a_stored_fact(client, monkeypatch, fake_llm):
    """Skipping the second load is safe only when this turn stored nothing.

    A new fact still has to reach the same turn's system prompt. The reload
    exists for that case; the skip exists for every other message.
    """
    calls = {"n": 0}
    original = MemoryService.build_context

    def wrapped(self, **kwargs):
        calls["n"] += 1
        return original(self, **kwargs)

    monkeypatch.setattr(MemoryService, "build_context", wrapped)
    token, _ = register(client, email="memory-once@example.com")
    project_id = make_project(client, token)
    hello = next(item for item in CASES if item.case_id == "direct_chat")
    _chat(client, token, project_id, hello)
    assert calls["n"] == 1

    calls["n"] = 0
    fake_llm.stream_calls.clear()
    named = type(hello)(
        case_id="fact",
        category="edge",
        message="My name is Avery.",
    )
    _chat(client, token, project_id, named)
    assert calls["n"] == 2
    system = next(
        message["content"]
        for message in fake_llm.stream_calls[-1]
        if message["role"] == "system"
    )
    assert "avery" in system.lower()

    calls["n"] = 0
    fake_llm.stream_calls.clear()
    renamed = type(hello)(
        case_id="fact-update",
        category="edge",
        message="My name is Blair.",
    )
    _chat(client, token, project_id, renamed)
    assert calls["n"] == 2
    system = next(
        message["content"]
        for message in fake_llm.stream_calls[-1]
        if message["role"] == "system"
    )
    assert "blair" in system.lower()


def test_pipeline_failure_records_an_error_code_without_the_message(client, fake_llm):
    fake_llm.raise_on_call = RuntimeError("secret prompt leaked")
    token, _ = register(client, email="boom@example.com")
    project_id = make_project(client, token)
    case = next(item for item in CASES if item.case_id == "direct_chat")

    response = _chat(client, token, project_id, case)
    events = sse_events(response.text)
    assert events[-1]["type"] == "error"
    execution_id = next(event["execution_id"] for event in events if event["type"] == "execution_meta")
    execution = client.get(
        f"/api/v1/executions/{execution_id}",
        headers=auth(token),
    ).json()
    assert execution["status"] == "error"
    assert execution["snapshot"]["latency"]["errors"] == ["RuntimeError"]
    assert "secret" not in str(execution["snapshot"]["latency"])


def test_labelled_cases_complete_and_summarize(client, monkeypatch):
    monkeypatch.setattr(settings, "chat_rate_limit_per_minute", 500)
    token, _ = register(client, email="bench@example.com")
    project_id = make_project(client, token)

    report_cases = []
    for case in CASES:
        samples = []
        errors = 0
        # One discarded warm-up, then three measured runs.
        for index in range(4):
            response = _chat(client, token, project_id, case)
            assert response.status_code == 200, response.text
            events = sse_events(response.text)
            done = events[-1]
            if done.get("type") == "error":
                errors += 1
                continue
            assert done["type"] == "done"
            if index == 0:
                continue
            execution = client.get(
                f"/api/v1/executions/{done['execution_id']}",
                headers=auth(token),
            ).json()
            route = (execution.get("snapshot") or {}).get("route")
            if case.expect_route is not None:
                assert route == case.expect_route
                assert execution["pipeline"] == f"orchestra_{case.expect_route}"
            samples.append(
                {
                    "latency_ms": done["latency_ms"],
                    "ttft_delivered_ms": done.get("ttft_delivered_ms"),
                    "total_tokens": done["total_tokens"],
                    "total_cost_usd": done["total_cost_usd"],
                }
            )
        summary = summarize_samples(samples)
        assert summary["runs"] == 3
        assert errors == 0
        assert summary["latency_ms"]["p50"] is not None
        assert summary["latency_ms"]["p50"] <= summary["latency_ms"]["p95"]
        report_cases.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "errors": errors,
                **summary,
            }
        )

    assert {item["case_id"] for item in report_cases} == {case.case_id for case in CASES}
