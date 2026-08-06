from pydantic_settings import BaseSettings, SettingsConfigDict

# Shipped in .env.example and the compose defaults. Startup checks refuse to boot
# a production environment that is still signing tokens with it.
DEFAULT_JWT_SECRET = "dev-secret-change-me"

# Passwords that appear in this repository's own defaults and tutorials.
WEAK_DB_PASSWORDS = frozenset({"orchestra", "postgres", "password", "changeme"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Orchestra API"
    api_v1_prefix: str = "/api/v1"

    # development | production. Controls startup validation strictness and
    # whether rate limiting fails open when Redis is unreachable.
    environment: str = "development"

    database_url: str = "postgresql+psycopg2://orchestra:orchestra@localhost:5432/orchestra"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    cors_origins: str = "http://localhost:3000"
    # Host header allow-list. "*" disables the check — acceptable locally, flagged
    # by startup checks in production.
    allowed_hosts: str = "*"

    # Upper bound on request body size. Generous enough for knowledge base
    # uploads; anything larger is rejected before it reaches a handler.
    max_request_bytes: int = 25 * 1024 * 1024

    # --- Abuse and cost controls -------------------------------------------
    # A public demo with an unmetered chat endpoint is an open funnel to the
    # LLM budget. These three limits cover burst, concurrency, and daily spend.
    rate_limit_enabled: bool = True
    chat_rate_limit_per_minute: int = 10
    chat_max_concurrent_streams: int = 3
    chat_daily_token_budget: int = 200_000
    signup_rate_limit_per_hour: int = 5

    # Email of the shared demo account, if one is seeded. Used only to decide
    # whether the frontend shows its demo banner; it grants no privileges.
    demo_email: str = ""

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

    # Per-request timeout for a single provider call, and how many times a
    # rate-limited call is retried. Worst-case wall time for one call is roughly
    # timeout * (retries + 1) plus backoff, so keep the product bounded: a
    # multi-agent turn makes four of these in sequence.
    llm_request_timeout_seconds: float = 60.0
    llm_max_retries: int = 3

    default_system_prompt: str = (
        "You are an AI Engineering mentor for Orchestra. "
        "Explain concepts clearly, prefer practical examples, "
        "and never fabricate APIs or library behavior."
    )

    upload_dir: str = "uploads"

    # How many recent turns the Redis short-term buffer keeps before older
    # messages are compressed into a summary.
    memory_buffer_size: int = 10

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()] or ["*"]

    @property
    def is_production(self) -> bool:
        return (self.environment or "").strip().lower() == "production"

    @property
    def jwt_secret_is_default(self) -> bool:
        return self.jwt_secret.strip() == DEFAULT_JWT_SECRET

    @property
    def rate_limit_fail_open(self) -> bool:
        """Whether an unreachable Redis should allow requests through.

        Development keeps Redis optional, matching the rest of the app. Production
        fails closed: an unmetered chat endpoint is a spend risk, and the readiness
        probe also checks Redis, so an outage drains the instance anyway.
        """
        return not self.is_production

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
