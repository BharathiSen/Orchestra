from __future__ import annotations

from typing import Any

from app.tools.base import BaseTool

# A small curated index describing Orchestra's own architecture. This is not a
# web search: it answers "how does this platform work?" questions without an
# external provider. User-supplied documents are served by the RAG pipeline
# (app/rag/), which is a separate and far larger corpus.
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
            "Orchestra runs two graphs: a tools graph (planner → tool → reviewer → "
            "answer) and the multi-agent Orchestra pipeline (planner → research → "
            "writer → reviewer, with a fast-answer branch for simple questions)."
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
    """Keyword search over a curated index of Orchestra's own architecture."""

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return (
            "Search Orchestra's built-in reference index for short factual "
            "snippets about how this platform is built — JWT auth, SSE streaming, "
            "tool calling, LangGraph, and PostgreSQL. "
            "This index covers Orchestra itself only. It is not a web search and "
            "does not cover current events, external products, or general world "
            "knowledge; answer those from your own knowledge instead. "
            "Uploaded user documents are not here either — those are retrieved "
            "automatically when the agent has a knowledge base attached."
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

        # The literal phrase "No knowledge hits" is matched by the graph answer
        # node to detect an empty search and fall back to general knowledge.
        if not top:
            return (
                f"No knowledge hits for '{query}'. "
                "This index only covers Orchestra's own architecture — try JWT, SSE, "
                "tool calling, LangGraph, or PostgreSQL, or answer from general "
                "knowledge. [source: Orchestra reference index]"
            )

        lines = [f"Results for '{query}' [source: Orchestra reference index]:"]
        for idx, doc in enumerate(top, start=1):
            lines.append(f"{idx}. {doc['title']}: {doc['snippet']}")
        return "\n".join(lines)
