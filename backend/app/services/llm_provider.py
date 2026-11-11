from app.core.config import settings
from app.services.gemini_service import SUPPORTED_MODELS as GEMINI_MODELS
from app.services.gemini_service import GeminiService
from app.services.openai_compatible_service import OpenAICompatibleService

GROQ_MODELS = [
    {
        "id": "openai/gpt-oss-20b",
        "label": "GPT-OSS 20B (Groq)",
        "description": "Fast and free-tier friendly — the default",
    },
    {
        "id": "openai/gpt-oss-120b",
        "label": "GPT-OSS 120B (Groq)",
        "description": "Stronger Groq model (higher free-tier usage)",
    },
    {
        "id": "qwen/qwen3.8-27b",
        "label": "Qwen3.8 27B (Groq)",
        "description": "Qwen on Groq",
    },
]

# Groq decommissions models; agents, conversations and env vars created before
# then still name them. Resolve those to a live replacement at call time
# instead of failing every request with a 404 "model_not_found".
GROQ_RETIRED_MODELS = {
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "gemma2-9b-it": "openai/gpt-oss-20b",
}

OLLAMA_MODELS = [
    {
        "id": "llama3.2",
        "label": "Llama 3.2 (Ollama local)",
        "description": "Fully free local model — requires Ollama installed",
    },
    {
        "id": "mistral",
        "label": "Mistral (Ollama local)",
        "description": "Local Mistral — pull with: ollama pull mistral",
    },
    {
        "id": "gemma2:9b",
        "label": "Gemma2 9B (Ollama local)",
        "description": "Local Gemma — pull with: ollama pull gemma2:9b",
    },
]


def get_supported_models() -> list[dict]:
    provider = settings.active_llm_provider
    if provider == "groq":
        return GROQ_MODELS
    if provider == "ollama":
        return OLLAMA_MODELS
    return GEMINI_MODELS


def is_llm_configured() -> bool:
    provider = settings.active_llm_provider
    if provider == "groq":
        return settings.groq_configured
    if provider == "ollama":
        return True  # no cloud key; connectivity checked at request time
    return settings.gemini_configured


def get_default_model() -> str:
    provider = settings.active_llm_provider
    if provider == "groq":
        model = settings.groq_default_model
        return GROQ_RETIRED_MODELS.get(model, model)
    if provider == "ollama":
        return settings.ollama_default_model
    return settings.gemini_default_model


def get_llm_service():
    """Return the active LLM client based on LLM_PROVIDER."""
    provider = settings.active_llm_provider
    if provider == "groq":
        return OpenAICompatibleService(
            base_url=settings.groq_base_url,
            api_key=settings.groq_api_key,
            provider_name="Groq",
            model_aliases=GROQ_RETIRED_MODELS,
            missing_key_hint=(
                "Groq API key is not configured. "
                "Set GROQ_API_KEY in .env (https://console.groq.com/keys) "
                "or switch LLM_PROVIDER=ollama|gemini."
            ),
        )
    if provider == "ollama":
        return OpenAICompatibleService(
            base_url=settings.ollama_base_url,
            api_key="ollama",
            provider_name="Ollama",
            missing_key_hint="Ollama is not reachable. Start Ollama locally.",
        )
    return GeminiService()


def missing_provider_message() -> str:
    provider = settings.active_llm_provider
    if provider == "groq":
        return (
            "Groq is not configured. Set GROQ_API_KEY in .env "
            "(free key: https://console.groq.com/keys) and restart the backend."
        )
    if provider == "ollama":
        return (
            "Ollama provider selected. Ensure Ollama is running and a model is pulled "
            f"(e.g. `ollama pull {settings.ollama_default_model}`)."
        )
    return (
        "Gemini API key is not configured. "
        "Set GEMINI_API_KEY in your .env and restart the backend."
    )
