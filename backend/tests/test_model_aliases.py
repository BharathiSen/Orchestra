"""Retired provider model IDs must resolve to a live model, not 404 every call."""

from __future__ import annotations

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
