from app.core.config import settings
from app.services.fake_llm_service import FAKE_MODEL_ID, FakeLLMService
from app.services.gemini_service import SUPPORTED_MODELS as GEMINI_MODELS
from app.services.gemini_service import GeminiService
from app.services.model_aliases import GROQ_RETIRED_MODELS
from app.services.openai_compatible_service import OpenAICompatibleService

__all__ = ["GROQ_MODELS", "GROQ_RETIRED_MODELS"]

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
        "label": "Qwen3.8 27B (Groq, preview)",
        # Groq lists this as a preview model, "for evaluation purposes only".
        "description": "Preview model; about 10x the gpt-oss-20b price",
    },
]

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
    if provider == "fake":
        return [
            {
                "id": FAKE_MODEL_ID,
                "label": "Deterministic test model",
                "description": "LLM_PROVIDER=fake — end-to-end tests only",
            }
        ]
    return GEMINI_MODELS


def is_llm_configured() -> bool:
    provider = settings.active_llm_provider
    if provider == "groq":
        return settings.groq_configured
    if provider in {"ollama", "fake"}:
        return True  # no cloud key; Ollama connectivity is checked per request
    return settings.gemini_configured


def get_default_model() -> str:
    provider = settings.active_llm_provider
    if provider == "groq":
        model = settings.groq_default_model
        return GROQ_RETIRED_MODELS.get(model, model)
    if provider == "ollama":
        return settings.ollama_default_model
    if provider == "fake":
        return FAKE_MODEL_ID
    return settings.gemini_default_model


def get_llm_service():
    """Return the active LLM client based on LLM_PROVIDER."""
    provider = settings.active_llm_provider
    if provider == "fake":
        # Second guard after startup validation: never answer real users with
        # the test stub, even if startup checks were bypassed.
        if settings.is_production:
            raise RuntimeError("LLM_PROVIDER=fake is refused when ENVIRONMENT=production")
        return FakeLLMService()
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
