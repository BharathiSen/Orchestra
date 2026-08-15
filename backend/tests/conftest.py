"""Shared test configuration.

Environment is set **before** any `app` import, because `app.core.config.settings`
is a module-level singleton and `app.core.database` builds its engine from it at
import time. Setting these afterwards would leave the engine pointed at whatever
`.env` happened to be on disk — which is how a test suite ends up writing to a
real database.

Database selection:

* ``TEST_DATABASE_URL`` set  → use it. CI points this at `pgvector/pgvector:pg16`,
  which is the only way to exercise the ``vector`` column and cosine distance.
* unset                     → SQLite in a temp file. Fast, no services needed,
  and every test runs except the ones marked ``requires_pgvector``.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

import pytest

# --- environment, before any app import -------------------------------------

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
_SQLITE_PATH: Path | None = None

if not _TEST_DB_URL:
    _SQLITE_PATH = Path(tempfile.gettempdir()) / "orchestra_test.db"
    _SQLITE_PATH.unlink(missing_ok=True)
    _TEST_DB_URL = f"sqlite:///{_SQLITE_PATH.as_posix()}"

USING_POSTGRES = _TEST_DB_URL.startswith("postgresql")

os.environ["DATABASE_URL"] = _TEST_DB_URL
os.environ["ENVIRONMENT"] = "development"
os.environ["JWT_SECRET"] = "test-secret-not-the-default-and-long-enough-to-pass"
os.environ["GROQ_API_KEY"] = "test-key"
os.environ["LLM_PROVIDER"] = "groq"
os.environ["EMBEDDING_WARMUP_ENABLED"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "true"
os.environ["CHAT_RATE_LIMIT_PER_MINUTE"] = "10"
os.environ["CHAT_MAX_CONCURRENT_STREAMS"] = "3"
os.environ["CHAT_DAILY_TOKEN_BUDGET"] = "200000"
os.environ["SIGNUP_RATE_LIMIT_PER_HOUR"] = "5"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import models  # noqa: E402,F401  — registers ORM classes on Base
from app.core import database  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.core.limiter import RateLimiter, get_rate_limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.memory import models as memory_models  # noqa: E402,F401  — registers UserMemory
from tests.fakes import FakeLLM, FakeRedis  # noqa: E402

if not USING_POSTGRES:
    # Two column types in the schema are Postgres-specific and have no SQLite
    # compiler: `JSONB` (document_chunks.chunk_metadata) and pgvector's `Vector`.
    # Teaching the SQLite dialect to render them as its own loose equivalents
    # lets the whole relational surface be tested without a database server.
    # Nothing here changes production behaviour — the shim only exists when the
    # suite is running against SQLite, and the tests that genuinely need vector
    # semantics are marked `requires_pgvector` and skipped.
    from pgvector.sqlalchemy import Vector
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.ext.compiler import compiles

    @compiles(JSONB, "sqlite")
    def _render_jsonb_as_json(type_, compiler, **kw):  # noqa: ANN001
        return "JSON"

    @compiles(Vector, "sqlite")
    def _render_vector_as_text(type_, compiler, **kw):  # noqa: ANN001
        return "TEXT"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requires_pgvector: needs a real pgvector database (skipped on SQLite)",
    )

    # A skipped test is not a passing test. CI sets REQUIRE_PGVECTOR=1, so if the
    # service container or the vector extension ever stops working the run fails
    # loudly instead of going green with retrieval quietly untested.
    #
    # This is an explicit assertion rather than grepping pytest's output on
    # purpose: `addopts = "-q"` in pyproject.toml combines with a second `-q` on
    # the command line to make `-qq`, which suppresses the summary line entirely.
    # A guard that parses output would have silently stopped guarding.
    if os.environ.get("REQUIRE_PGVECTOR") == "1" and not USING_POSTGRES:
        raise pytest.UsageError(
            "REQUIRE_PGVECTOR=1 but TEST_DATABASE_URL is not a PostgreSQL URL "
            f"(got {_TEST_DB_URL!r}). The pgvector tests would be skipped."
        )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if USING_POSTGRES:
        return
    skip = pytest.mark.skip(reason="needs TEST_DATABASE_URL pointing at pgvector")
    for item in items:
        if "requires_pgvector" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """Create the schema once for the session."""
    if USING_POSTGRES:
        with database.engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=database.engine)
    yield
    # Dispose before dropping. Any connection still checked out would sit `idle
    # in transaction` on PostgreSQL, holding locks that make DROP TABLE block
    # forever — which is exactly how the connection leak fixed in `api/v1/chat.py`
    # first showed itself. Disposing first makes teardown independent of that.
    database.engine.dispose()
    Base.metadata.drop_all(bind=database.engine)
    # Windows will not unlink a file the engine still holds a handle on, so the
    # pool has to be disposed again after the drop reopened it. A leftover temp
    # file is harmless anyway — the next run truncates it — so failure here must
    # not fail the suite.
    database.engine.dispose()
    if _SQLITE_PATH is not None:
        with contextlib.suppress(OSError):
            _SQLITE_PATH.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def clean_tables(_schema):
    """Empty every table between tests.

    Deleting rows rather than dropping tables keeps this fast on Postgres, and
    reversing `sorted_tables` deletes children before parents so foreign keys are
    never violated.
    """
    yield
    with database.engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture(autouse=True)
def _wire_redis(monkeypatch: pytest.MonkeyPatch, fake_redis: FakeRedis):
    """Point every Redis consumer at the in-memory fake.

    Without this the limiter and memory store reach for localhost:6379. That
    would make the suite depend on a running Redis and, worse, make rate-limit
    tests pass for the wrong reason — in development the limiter fails *open*, so
    an unreachable Redis allows every request.
    """
    monkeypatch.setattr("app.core.redis_client.get_redis", lambda: fake_redis)
    monkeypatch.setattr("app.core.limiter.get_redis", lambda: fake_redis)
    monkeypatch.setattr("app.memory.redis.get_redis", lambda: fake_redis)
    monkeypatch.setattr("app.core.limiter._limiter", RateLimiter(client=fake_redis))
    return fake_redis


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture(autouse=True)
def _wire_llm(monkeypatch: pytest.MonkeyPatch, fake_llm: FakeLLM):
    """Swap the provider for a stub so no test can make a network call."""
    monkeypatch.setattr("app.services.chat_service.get_llm_service", lambda: fake_llm)
    return fake_llm


@pytest.fixture
def client(fake_redis: FakeRedis):
    """A TestClient bound to the test database.

    Deliberately *not* entered as a context manager: `with TestClient(app)` runs
    the application lifespan, which would execute startup checks, `create_all`,
    and the embedding warm-up. None of that belongs in a request test — the
    schema is already handled by the `_schema` fixture.

    `get_db` needs no override: `DATABASE_URL` was set before `app.core.database`
    was imported, so its engine is already the test engine. The limiter *does*
    need one, because `get_rate_limiter` returns a process-wide singleton built
    at import time against the real Redis URL.
    """
    app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter(client=fake_redis)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def frozen_window(monkeypatch: pytest.MonkeyPatch):
    """Pin the limiter's clock to the middle of a fixed window.

    The limiter buckets by wall-clock minute. A burst test that happens to
    straddle a minute boundary splits across two windows and passes when it
    should fail — which is not a hypothetical, it is exactly the false alarm
    recorded as Bug 12. Freezing the clock makes the burst tests deterministic;
    the boundary behaviour itself is asserted separately and on purpose.
    """
    from datetime import UTC
    from datetime import datetime as real_datetime

    fixed = real_datetime(2026, 1, 1, 12, 30, 30, tzinfo=UTC)

    class _FrozenDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            return fixed

    monkeypatch.setattr("app.core.limiter.datetime", _FrozenDatetime)
    return fixed


@pytest.fixture
def db_session():
    """A plain session for tests that need to set up or inspect rows directly."""
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()


# --- helpers ----------------------------------------------------------------


def register(client: TestClient, email: str = "user@example.com", password: str = "password123"):
    """Create an account and return (token, user_id)."""
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["access_token"], body["user"]["id"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_project(client: TestClient, token: str, name: str = "Test project") -> int:
    response = client.post(
        "/api/v1/projects",
        json={"name": name, "description": "created by tests"},
        headers=auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def sse_events(raw: str) -> list[dict]:
    """Parse an SSE response body into the list of decoded JSON payloads."""
    import json

    events = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block.startswith("data:"):
            continue
        events.append(json.loads(block[len("data:") :].strip()))
    return events


def event_types(raw: str) -> list[str]:
    return [event.get("type") for event in sse_events(raw)]
