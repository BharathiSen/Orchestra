"""The fixed question set every evaluation run answers.

Fixed on purpose: scores are only comparable across prompt versions if every
run answers the same questions. Each question lists the key points a correct
answer must cover — the judge grades against these, not against its own
opinion of the topic.

Routing is deterministic from the question text, so ``expected_route`` is not
a score: it guarantees the set exercises both pipeline paths, and a test keeps
it in step with the router.

Three groups:
- ``grounded``: about Orchestra itself, answerable from the built-in reference
  index the Research agent can search. Tests whether answers stay grounded.
- ``engineering``: comparisons and explanations that take the full route
  (planner → research → writer → reviewer).
- ``factual``: short questions that take the simple route (fast answer).

Change this file deliberately: editing a question breaks comparability with
every earlier run, which is why the set's own hash is stored on each run.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class GoldenQuestion:
    id: str
    category: str
    question: str
    expected_route: str
    key_points: tuple[str, ...]


GOLDEN_QUESTIONS: tuple[GoldenQuestion, ...] = (
    GoldenQuestion(
        id="auth",
        category="grounded",
        question="How does Orchestra authenticate API requests?",
        expected_route="simple",
        key_points=(
            "Uses JSON Web Tokens (JWT) sent as Bearer credentials",
            "Tokens are verified on protected FastAPI routes",
            "Tokens carry claims such as the subject and an expiry",
        ),
    ),
    GoldenQuestion(
        id="streaming",
        category="grounded",
        question="How does Orchestra stream chat answers to the browser?",
        expected_route="simple",
        key_points=(
            "Server-Sent Events (SSE) over HTTP, content type text/event-stream",
            "A one-way stream from server to browser",
            "Tokens appear incrementally rather than all at once",
        ),
    ),
    GoldenQuestion(
        id="pipeline",
        category="grounded",
        question="Give a detailed description of the stages of Orchestra's multi-agent pipeline.",
        expected_route="full",
        key_points=(
            "Planner, then Research, then Writer, then Reviewer",
            "A fast-answer branch skips Writer and Reviewer for simple questions",
            "Built as a LangGraph graph with shared state",
        ),
    ),
    GoldenQuestion(
        id="storage",
        category="grounded",
        question="Where does Orchestra store conversations, and how is ownership enforced?",
        expected_route="simple",
        key_points=(
            "PostgreSQL, accessed through SQLAlchemy",
            "Stores users, projects, agents, conversations, and messages",
            "Ownership is enforced through the project's owner_id",
        ),
    ),
    GoldenQuestion(
        id="tool-calling",
        category="grounded",
        question="What is tool calling, and how does Orchestra use it?",
        expected_route="simple",
        key_points=(
            "The model requests structured tool invocations described by JSON schema",
            "The application executes the tool and returns the result to the model",
            "The model then produces a final answer grounded in the tool result",
        ),
    ),
    GoldenQuestion(
        id="redis-vs-postgres",
        category="engineering",
        question="Compare Redis and PostgreSQL for storing short-term chat memory.",
        expected_route="full",
        key_points=(
            "Redis is in-memory and very low latency, with TTL-based expiry",
            "PostgreSQL is durable and transactional, and history can be queried",
            "Redis suits an ephemeral rolling buffer; Postgres suits durable history",
            "The trade-off is speed and simplicity versus persistence",
        ),
    ),
    GoldenQuestion(
        id="sse-vs-websockets",
        category="engineering",
        question="Compare Server-Sent Events and WebSockets, and explain when to choose each.",
        expected_route="full",
        key_points=(
            "SSE is one-way, server to client, over plain HTTP with automatic reconnection",
            "WebSockets are bidirectional and use a separate protocol after an upgrade",
            "Choose SSE for streaming tokens or notifications; WebSockets for two-way interaction",
        ),
    ),
    GoldenQuestion(
        id="rag",
        category="engineering",
        question=(
            "Give a detailed explanation of retrieval-augmented generation "
            "and its main failure modes."
        ),
        expected_route="full",
        key_points=(
            "Retrieve relevant documents and add them to the prompt as context",
            "Grounding in retrieved text reduces hallucination",
            "Failure modes include irrelevant or missed retrieval and poor chunking",
            "The model can ignore or misread the retrieved context",
        ),
    ),
    GoldenQuestion(
        id="rate-limiting",
        category="engineering",
        question="Write a short checklist for rate limiting an LLM API endpoint.",
        expected_route="full",
        key_points=(
            "Limit requests per user per time window",
            "Limit concurrent requests or streams per user",
            "Cap spend with a token or cost budget",
            "Reject with HTTP 429 and a Retry-After header",
        ),
    ),
    GoldenQuestion(
        id="power-of-two",
        category="factual",
        question="What is 2 to the power of 10?",
        expected_route="simple",
        key_points=("The answer is 1024",),
    ),
    GoldenQuestion(
        id="http-429",
        category="factual",
        question="What does HTTP status code 429 mean?",
        expected_route="simple",
        key_points=(
            "Too Many Requests",
            "The client is being rate limited and should retry later, e.g. after Retry-After",
        ),
    ),
    GoldenQuestion(
        id="acid",
        category="factual",
        question="What does ACID stand for in databases?",
        expected_route="simple",
        key_points=("Atomicity, Consistency, Isolation, Durability",),
    ),
)


def golden_set_version(questions: tuple[GoldenQuestion, ...] = GOLDEN_QUESTIONS) -> str:
    """Short hash of the question set, so runs on different sets are never compared."""
    payload = json.dumps([asdict(q) for q in questions], sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]
