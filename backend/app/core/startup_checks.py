"""Configuration validation run once at application startup.

The point of failing here is that every alternative is worse. A production
deployment signing JWTs with the secret committed to this repository looks
completely healthy — it serves traffic, passes health checks, and quietly lets
anyone who has read the source mint a valid token for any account. Refusing to
boot turns a silent compromise into a loud, obvious deploy failure.

Development is deliberately lenient: the same problems are reported as warnings
so local work is never blocked.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from app.core.config import WEAK_DB_PASSWORDS, Settings

logger = logging.getLogger(__name__)


class StartupCheckError(RuntimeError):
    """Raised when configuration is unsafe for the current environment."""


def _database_password(database_url: str) -> str | None:
    try:
        return urlsplit(database_url).password
    except ValueError:
        # A malformed URL is the connection layer's problem to report, not ours.
        return None


def _collect_problems(settings: Settings) -> tuple[list[str], list[str]]:
    """Return (fatal, warnings) for the given settings."""
    fatal: list[str] = []
    warnings: list[str] = []

    if settings.jwt_secret_is_default:
        fatal.append(
            "JWT_SECRET is still the default value shipped in .env.example. "
            "Anyone with access to this repository can forge access tokens. "
            'Generate one with: python -c "import secrets; '
            'print(secrets.token_urlsafe(64))"'
        )
    elif len(settings.jwt_secret.strip()) < 32:
        fatal.append(
            f"JWT_SECRET is only {len(settings.jwt_secret.strip())} characters. "
            "Use at least 32 characters of random data."
        )

    password = _database_password(settings.database_url)
    if password and password.lower() in WEAK_DB_PASSWORDS:
        fatal.append(
            f"DATABASE_URL uses the well-known password '{password}'. "
            "Set a real password on the database and update the connection string."
        )

    provider = settings.active_llm_provider
    if provider == "groq" and not settings.groq_configured:
        fatal.append("LLM_PROVIDER=groq but GROQ_API_KEY is empty — chat cannot serve traffic.")
    elif provider == "gemini" and not settings.gemini_configured:
        fatal.append("LLM_PROVIDER=gemini but GEMINI_API_KEY is empty — chat cannot serve traffic.")
    elif provider == "ollama":
        warnings.append(
            "LLM_PROVIDER=ollama expects a reachable Ollama host. Prefer groq or "
            "gemini for a hosted deployment."
        )

    if "*" in settings.allowed_host_list:
        warnings.append(
            "ALLOWED_HOSTS is '*', so Host headers are not validated. Set it to "
            "your real domain(s) to reject Host-header spoofing."
        )

    localhost_origins = [
        origin
        for origin in settings.cors_origin_list
        if "localhost" in origin or "127.0.0.1" in origin
    ]
    if localhost_origins:
        warnings.append(
            f"CORS_ORIGINS still contains local origins: {', '.join(localhost_origins)}."
        )

    if not settings.rate_limit_enabled:
        warnings.append(
            "RATE_LIMIT_ENABLED is false — the chat endpoint is unmetered and can "
            "drain the configured LLM quota."
        )

    return fatal, warnings


def run_startup_checks(settings: Settings) -> None:
    """Validate configuration, raising in production and warning elsewhere."""
    fatal, warnings = _collect_problems(settings)

    for warning in warnings:
        logger.warning("Configuration warning: %s", warning)

    if not fatal:
        return

    if not settings.is_production:
        for problem in fatal:
            logger.warning(
                "Configuration problem (fatal when ENVIRONMENT=production): %s", problem
            )
        return

    detail = "\n".join(f"  - {problem}" for problem in fatal)
    raise StartupCheckError(
        f"Refusing to start with ENVIRONMENT=production.\n{detail}\n"
        "Fix the values above, or set ENVIRONMENT=development to run anyway."
    )
