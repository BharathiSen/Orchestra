"""Retired provider model IDs must resolve to a live model, not 404 every call."""

from __future__ import annotations

from datetime import UTC

from app.services.llm_provider import GROQ_MODELS, GROQ_RETIRED_MODELS
from app.services.openai_compatible_service import OpenAICompatibleService


def _service() -> OpenAICompatibleService:
    return OpenAICompatibleService(
        base_url="https://example.invalid/v1",
        api_key="test-key",
        provider_name="Groq",
        missing_key_hint="unused",
        model_aliases=GROQ_RETIRED_MODELS,
    )


def test_retired_model_is_sent_as_its_replacement():
    payload = _service()._base_payload(
        messages=[], model="llama-3.1-8b-instant", temperature=0.2, stream=False
    )
    assert payload["model"] == "openai/gpt-oss-20b"


def test_current_model_passes_through_unchanged():
    payload = _service()._base_payload(
        messages=[], model="qwen/qwen3.8-27b", temperature=0.2, stream=True
    )
    assert payload["model"] == "qwen/qwen3.8-27b"
    assert "reasoning_effort" not in payload


def test_gpt_oss_requests_low_reasoning_effort():
    payload = _service()._base_payload(
        messages=[], model="openai/gpt-oss-20b", temperature=0.2, stream=True
    )
    assert payload["reasoning_effort"] == "low"


def test_every_alias_targets_a_listed_model():
    listed = {m["id"] for m in GROQ_MODELS}
    assert set(GROQ_RETIRED_MODELS.values()) <= listed
    assert not set(GROQ_RETIRED_MODELS) & listed


def test_retired_model_is_priced_as_its_replacement():
    """An agent saved with a retired ID runs on, and must be billed as, the replacement."""
    from app.evaluation.cost import price_for_model

    assert price_for_model("llama-3.1-8b-instant") == price_for_model("openai/gpt-oss-20b")


def test_every_listed_groq_model_has_a_real_price():
    """A listed model falling through to the default price under-reports cost."""
    from app.evaluation.cost import MODEL_PRICING_PER_MILLION

    missing = {m["id"] for m in GROQ_MODELS} - set(MODEL_PRICING_PER_MILLION)
    assert not missing, f"no pricing for {missing}"


def test_fake_provider_is_refused_in_production(monkeypatch):
    """The e2e stub must be impossible to serve to real users."""
    import pytest

    from app.core.config import Settings
    from app.core.startup_checks import _collect_problems
    from app.services import llm_provider

    prod = Settings(environment="production", llm_provider="fake")
    fatal, _ = _collect_problems(prod)
    assert any("LLM_PROVIDER=fake" in problem for problem in fatal)

    monkeypatch.setattr(llm_provider, "settings", prod)
    with pytest.raises(RuntimeError):
        llm_provider.get_llm_service()


def test_fake_provider_streams_a_deterministic_reply(monkeypatch):
    from app.core.config import Settings
    from app.services import llm_provider

    monkeypatch.setattr(llm_provider, "settings", Settings(llm_provider="fake"))
    service = llm_provider.get_llm_service()
    messages = [{"role": "user", "content": "What is Orchestra?"}]
    usage: dict[str, int] = {}
    streamed = "".join(
        service.stream_chat_completion(
            messages=messages, model="x", temperature=0.2, usage_sink=usage
        )
    )
    assert streamed.strip() == "Deterministic test reply to: What is Orchestra?"
    assert usage["total_tokens"] == 52
    assert llm_provider.is_llm_configured()


def test_streaming_retries_are_counted_on_the_request_timeline(monkeypatch):
    """A rate-limited *streamed* call must show up as a retry in the timeline.

    Streaming is the main chat path. The non-streaming loop already counted its
    retries; the streaming loop retried silently, so every streamed turn reported
    `retries: 0` even after Groq had rate-limited it.
    """
    import httpx

    from app.observability.latency import LatencyTimeline, pop_timeline, push_timeline

    attempts = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        body = 'data: {"choices": [{"delta": {"content": "hi"}}]}\n\ndata: [DONE]\n\n'
        return httpx.Response(200, content=body.encode())

    real_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    timeline = LatencyTimeline()
    ctx = push_timeline(timeline)
    try:
        reply = "".join(
            _service().stream_chat_completion(
                messages=[{"role": "user", "content": "x"}], model="m", temperature=0.0
            )
        )
    finally:
        pop_timeline(ctx)

    assert reply == "hi"
    assert attempts["n"] == 2, "expected one 429 then one success"
    assert timeline.retries == 1


def _rate_limited_then_ok(monkeypatch, retry_after: str | None):
    """Route httpx through a provider that 429s once, then answers.

    Returns (attempts, sleeps) so a test can see how the client backed off.
    """
    import httpx

    attempts = {"n": 0}
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            headers = {"retry-after": retry_after} if retry_after else {}
            return httpx.Response(
                429, headers=headers, json={"error": {"message": "rate limited"}}
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "hi"}}], "usage": {}}
        )

    real_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
    )
    monkeypatch.setattr("time.sleep", sleeps.append)
    return attempts, sleeps


def _complete():
    return _service().complete_chat(
        messages=[{"role": "user", "content": "x"}], model="m", temperature=0.0
    )


def test_provider_retry_after_is_honoured_over_a_shorter_backoff(monkeypatch):
    """The first backoff is ~1s; a provider asking for 6s must get 6s.

    Retrying sooner than the provider allows just earns another 429, which is
    how demo turns used to burn all their retries and end up degraded.
    """
    attempts, sleeps = _rate_limited_then_ok(monkeypatch, "6")

    assert _complete().content == "hi"
    assert attempts["n"] == 2
    assert len(sleeps) == 1 and 6.0 <= sleeps[0] < 7.0


def test_retry_after_beyond_the_cap_fails_fast_instead_of_stalling(monkeypatch):
    import pytest
    from fastapi import HTTPException

    attempts, sleeps = _rate_limited_then_ok(monkeypatch, "60")

    with pytest.raises(HTTPException) as caught:
        _complete()
    assert caught.value.status_code == 429
    assert caught.value.headers == {"Retry-After": "60"}
    assert attempts["n"] == 1 and sleeps == [], "no point waiting out a 60s limit"


def test_no_retry_once_the_turn_budget_is_spent(monkeypatch):
    """Several LLM calls per turn must not each stack their own waits."""
    import pytest
    from fastapi import HTTPException

    from app.observability.latency import LatencyTimeline, pop_timeline, push_timeline
    from app.services import openai_compatible_service as svc

    attempts, sleeps = _rate_limited_then_ok(monkeypatch, "2")
    timeline = LatencyTimeline()
    monkeypatch.setattr(
        timeline, "elapsed_ms", lambda: int(svc.TURN_RETRY_BUDGET_SECONDS * 1000)
    )
    ctx = push_timeline(timeline)
    try:
        with pytest.raises(HTTPException):
            _complete()
    finally:
        pop_timeline(ctx)
    assert attempts["n"] == 1 and sleeps == []


def test_retry_after_accepts_seconds_and_http_dates():
    from datetime import datetime, timedelta
    from email.utils import format_datetime

    from app.services.openai_compatible_service import _parse_retry_after

    assert _parse_retry_after("3") == 3.0
    assert _parse_retry_after("0.5") == 0.5
    assert _parse_retry_after(None) is None
    assert _parse_retry_after("soon") is None
    later = datetime.now(UTC) + timedelta(seconds=30)
    assert 25 <= _parse_retry_after(format_datetime(later, usegmt=True)) <= 31
    assert _parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0


def test_reseeding_moves_demo_agents_off_retired_models(db_session):
    """Re-running the seed must repair agents created before a model retired.

    The seed used to create agents only when missing, so an agent seeded with
    llama-3.1-8b-instant kept it forever. The chat picker now follows the
    agent's model, so that stale ID would reach the live demo.
    """
    import importlib.util
    from pathlib import Path

    from app.models import Agent, KnowledgeBase, Project, User

    path = Path(__file__).resolve().parent.parent / "scripts" / "seed_demo.py"
    spec = importlib.util.spec_from_file_location("seed_demo", path)
    seed_demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed_demo)

    user = User(email="seed@example.com", hashed_password="x", full_name="Seed")
    db_session.add(user)
    db_session.flush()
    project = Project(name="Demo", owner_id=user.id)
    db_session.add(project)
    db_session.flush()
    kb = KnowledgeBase(project_id=project.id, name="Handbook")
    db_session.add(kb)
    first = seed_demo.AGENTS[0]
    db_session.add(
        Agent(
            project_id=project.id,
            name=first["name"],
            system_prompt=first["system_prompt"],
            model_name="llama-3.1-8b-instant",
        )
    )
    db_session.flush()

    agents = seed_demo._seed_agents(db_session, project=project, kb=kb)

    assert {a.model_name for a in agents} == {seed_demo.DEFAULT_MODEL}
    assert seed_demo.DEFAULT_MODEL in {m["id"] for m in GROQ_MODELS}
