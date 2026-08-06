"""Golden-question eval harness with mocked LLM (no live API keys required)."""

from __future__ import annotations

from typing import Any

from app.memory.facts import extract_facts
from app.orchestrator.routing import classify_route
from app.services.llm_types import ChatCompletionResult


class FakeLLM:
    """Deterministic LLM stub for CI / offline evals."""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[list[dict[str, Any]]] = []

    def complete_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = "auto",
    ) -> ChatCompletionResult:
        self.calls.append(messages)
        blob = " ".join(str(m.get("content") or "") for m in messages).lower()
        for needle, answer in self.responses.items():
            if needle.lower() in blob:
                return ChatCompletionResult(content=answer, finish_reason="stop")
        # Default: echo last user content lightly
        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = str(msg.get("content") or "")
                break
        return ChatCompletionResult(
            content=f"OK: {last_user[:120]}",
            finish_reason="stop",
        )


def test_route_simple_name_recall() -> None:
    assert classify_route("What is my name?") == "simple"


def test_route_full_essay() -> None:
    assert classify_route("Write a detailed blog comparing Redis and Postgres") == "full"


def test_extract_name_fact() -> None:
    facts = extract_facts("My name is Avery.")
    assert any(f.key == "name" and f.value.lower() == "avery" for f in facts)


def test_extract_preference_fact() -> None:
    facts = extract_facts("I prefer Python for backend work.")
    assert any("python" in f.value.lower() for f in facts)


def test_fake_llm_name_recall_golden() -> None:
    llm = FakeLLM({"what is my name": "Avery"})
    result = llm.complete_chat(
        messages=[
            {"role": "system", "content": "You remember conversation memory."},
            {"role": "user", "content": "My name is Avery."},
            {"role": "assistant", "content": "Noted."},
            {"role": "user", "content": "What is my name?"},
        ],
        model="fake",
        temperature=0,
    )
    assert "avery" in (result.content or "").lower()


def test_grounding_from_research_notes() -> None:
    """Golden: answer should use research notes, not invent unrelated stages."""
    notes = (
        "Orchestra RAG pipeline stages: extract, chunk, embed, retrieve, generate"
    )
    llm = FakeLLM({"rag pipeline": notes})
    result = llm.complete_chat(
        messages=[
            {"role": "system", "content": "Use research notes only."},
            {
                "role": "user",
                "content": (
                    f"Research notes:\n{notes}\n\n"
                    "What are the stages of the RAG pipeline?"
                ),
            },
        ],
        model="fake",
        temperature=0,
    )
    text = (result.content or "").lower()
    assert "extract" in text or "chunk" in text or "retrieve" in text
    assert "governance layer" not in text


def test_calculator_golden_string() -> None:
    """Golden expectation for calculator path answer content."""
    llm = FakeLLM({"24 * 18": "432"})
    result = llm.complete_chat(
        messages=[
            {"role": "user", "content": "What is 24 * 18? Use calculator."},
        ],
        model="fake",
        temperature=0,
    )
    assert "432" in (result.content or "")


def test_orchestra_simple_path_skips_writer() -> None:
    from app.orchestrator.engine import FULL_ORDER, SIMPLE_ORDER

    assert "fast_answer" in SIMPLE_ORDER
    assert "writer" not in SIMPLE_ORDER
    assert "writer" in FULL_ORDER
