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
