from __future__ import annotations

from typing import Any

from app.tools.base import BaseTool

# Mock knowledge snippets — stand-in for a real search / RAG index (Days 6–7).
_KNOWLEDGE: list[dict[str, str]] = [
    {
        "title": "JWT Authentication",
        "snippet": (
            "JSON Web Tokens (JWT) are compact, signed tokens often used as Bearer "
            "credentials. Typical claims include sub (subject), exp (expiry), and email. "
            "Orchestra verifies JWTs on protected FastAPI routes."
        ),
        "tags": "jwt auth token bearer fastapi",
    },
    {
        "title": "Server-Sent Events (SSE)",
        "snippet": (
            "SSE lets a server push a unidirectional event stream over HTTP. "
            "Orchestra uses text/event-stream for chat so tokens appear incrementally."
        ),
        "tags": "sse streaming http events chat",
    },
    {
        "title": "Tool Calling",
        "snippet": (
            "Tool calling (function calling) lets an LLM request structured tool "
            "invocations via JSON schema. The app executes the tool and returns results "
            "so the model can produce a grounded final answer."
        ),
        "tags": "tools function calling registry calculator weather",
    },
    {
        "title": "LangGraph",
        "snippet": (
            "LangGraph models agent workflows as graphs with nodes, edges, and state. "
            "Orchestra Day 5 will use planner → tool → reviewer → answer patterns."
        ),
        "tags": "langgraph agents workflow planner",
    },
    {
        "title": "PostgreSQL in Orchestra",
        "snippet": (
            "Orchestra stores users, projects, agents, conversations, and messages in "
            "PostgreSQL via SQLAlchemy. Ownership is enforced through project.owner_id."
        ),
        "tags": "postgres database sqlalchemy conversations messages",
    },
]


class SearchTool(BaseTool):
    """Mock search over Orchestra knowledge — replace later with real search/RAG."""

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return (
            "Search Orchestra's knowledge base for short factual snippets. "
            "Use for questions about JWT, SSE, tool calling, LangGraph, Postgres, "
            "or other AI-engineering topics in this project. "
            "Returns top matching snippets (mock for Day 4)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query text.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (1-5).",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 3,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        }

    def execute(self, **kwargs: Any) -> str:
        query = str(kwargs.get("query", "")).strip().lower()
        if not query:
            raise ValueError("query is required")

        limit = kwargs.get("limit", 3)
        try:
            limit_i = max(1, min(5, int(limit)))
        except (TypeError, ValueError):
            limit_i = 3

        tokens = [t for t in query.replace(",", " ").split() if t]
        scored: list[tuple[int, dict[str, str]]] = []
        for doc in _KNOWLEDGE:
            hay = f"{doc['title']} {doc['snippet']} {doc['tags']}".lower()
            score = sum(1 for t in tokens if t in hay)
            if score > 0:
                scored.append((score, doc))

        scored.sort(key=lambda item: item[0], reverse=True)
        top = [doc for _, doc in scored[:limit_i]]

        if not top:
            return (
                f"No knowledge hits for '{query}'. "
                "Try queries like JWT, SSE, tool calling, LangGraph, or PostgreSQL. [source: mock]"
            )

        lines = [f"Search results for '{query}' [source: mock]:"]
        for idx, doc in enumerate(top, start=1):
            lines.append(f"{idx}. {doc['title']}: {doc['snippet']}")
        return "\n".join(lines)
