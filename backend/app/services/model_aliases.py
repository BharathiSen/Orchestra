"""Retired provider model IDs and their live replacements.

Kept free of imports so both the provider client (which rewrites the model on
each request) and the cost model (which must price the model actually called)
can depend on it without a cycle.
"""

# Groq decommissions models; agents, conversations and env vars created before
# then still name them. Resolve those to a live replacement at call time
# instead of failing every request with a 404 "model_not_found".
GROQ_RETIRED_MODELS: dict[str, str] = {
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "gemma2-9b-it": "openai/gpt-oss-20b",
}


def resolve_model(model: str) -> str:
    """Return the model a request for ``model`` is actually sent to."""
    return GROQ_RETIRED_MODELS.get(model, model)
