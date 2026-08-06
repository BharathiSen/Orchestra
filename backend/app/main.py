import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import models  # noqa: F401
from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.middleware import MaxBodySizeMiddleware, SelectiveGZipMiddleware
from app.core.redis_client import get_redis
from app.core.startup_checks import run_startup_checks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _ensure_vector_extension() -> None:
    """Create the pgvector extension if this role is allowed to.

    Managed Postgres (Neon, Supabase, RDS) usually ships the extension already
    installed and does not grant CREATE EXTENSION to the application role. That
    is a healthy configuration, so a permission error here is logged rather than
    treated as a boot failure. If the extension genuinely is absent, table
    creation fails immediately afterwards with a clear error.
    """
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except SQLAlchemyError as exc:
        logger.warning(
            "Could not create the pgvector extension (usually a permissions "
            "restriction on managed Postgres, and harmless when it is already "
            "installed): %s",
            exc,
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    run_startup_checks(settings)

    _ensure_vector_extension()
    # Fresh DBs (e.g. Neon) have no tables yet — create first, then backfill columns.
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        # create_all does not add new columns to existing tables
        conn.execute(
            text("ALTER TABLE IF EXISTS messages ADD COLUMN IF NOT EXISTS trace JSON")
        )
    try:
        get_redis().ping()
    except Exception as exc:  # noqa: BLE001
        # Redis powers memory/sessions; bad/missing URL must not block API boot.
        # Readiness reports the degradation, and rate limiting fails closed in
        # production so an outage cannot leave the chat endpoint unmetered.
        logger.warning("Redis is not reachable at startup: %s", exc)

    logger.info(
        "Orchestra API ready (environment=%s, provider=%s, rate_limiting=%s)",
        settings.environment,
        settings.active_llm_provider,
        "on" if settings.rate_limit_enabled else "off",
    )
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Order matters: the body-size guard runs outermost so an oversized upload is
# rejected before any other middleware allocates work for it.
app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_request_bytes)

if "*" not in settings.allowed_host_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)

app.add_middleware(
    SelectiveGZipMiddleware,
    minimum_size=1024,
    exclude_paths=(f"{settings.api_v1_prefix}/chat",),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
        "api": settings.api_v1_prefix,
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness. Kept for backwards compatibility with existing probes."""
    return {"status": "ok"}


@app.get("/health/live")
def health_live() -> dict[str, str]:
    """Liveness: is the process running at all?

    Deliberately checks nothing external. A dependency outage should restart
    dependencies, not this container.
    """
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready(response: Response) -> dict[str, object]:
    """Readiness: can this instance actually serve a request?

    Returns 503 when a hard dependency is down so an orchestrator drains traffic
    instead of routing it into failures. Postgres is required. Redis degrades
    memory and, in production, disables chat because the limiter fails closed —
    so it counts as required there and as informational locally.
    """
    checks: dict[str, str] = {}
    ready = True

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except SQLAlchemyError as exc:
        logger.error("Readiness check failed for database: %s", exc)
        checks["database"] = "unavailable"
        ready = False

    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.error("Readiness check failed for redis: %s", exc)
        checks["redis"] = "unavailable"
        if not settings.rate_limit_fail_open:
            ready = False

    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": "ready" if ready else "not_ready", "checks": checks}
