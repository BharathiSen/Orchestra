from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Orchestra API"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg2://orchestra:orchestra@localhost:5432/orchestra"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    cors_origins: str = "http://localhost:3000"

    # gemini | groq | ollama
    # Use groq/ollama for free local testing; gemini for production.
    llm_provider: str = "groq"

    gemini_api_key: str = ""
    gemini_default_model: str = "gemini-2.0-flash"

    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_default_model: str = "llama-3.1-8b-instant"

    # From Docker on Windows/Mac, host machine Ollama is usually host.docker.internal
    ollama_base_url: str = "http://host.docker.internal:11434/v1"
    ollama_default_model: str = "llama3.2"

    default_system_prompt: str = (
        "You are an AI Engineering mentor for Orchestra. "
        "Explain concepts clearly, prefer practical examples, "
        "and never fabricate APIs or library behavior."
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key.strip())

    @property
    def active_llm_provider(self) -> str:
        value = (self.llm_provider or "groq").strip().lower()
        if value not in {"gemini", "groq", "ollama"}:
            return "groq"
        return value


settings = Settings()
