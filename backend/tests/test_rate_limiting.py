"""The three abuse limits, plus the signup limit.

Each limit closes a hole the others do not: requests/minute stops hammering,
concurrency stops many simultaneous 30-second pipelines from one account, and the
token budget is the only one that maps to money.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.limiter import RateLimiter
from tests.conftest import auth, make_project, register


def _chat(client, token, project_id, message="hi"):
    return client.post(
        "/api/v1/chat",
        json={
            "project_id": project_id,
            "message": message,
            "enable_tools": False,
            "enable_orchestra": False,
        },
        headers=auth(token),
    )


def test_requests_per_minute_limit_returns_429_with_retry_after(client, frozen_window):
    token, _ = register(client)
    project_id = make_project(client, token)

    for i in range(settings.chat_rate_limit_per_minute):
        assert _chat(client, token, project_id).status_code == 200, f"request {i} blocked early"

    blocked = _chat(client, token, project_id)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    assert blocked.headers["X-RateLimit-Remaining"] == "0"
    assert "Rate limit exceeded" in blocked.json()["detail"]


def test_rate_limit_is_scoped_per_user(client, frozen_window):
    first_token, _ = register(client, email="first@example.com")
    second_token, _ = register(client, email="second@example.com")
    first_project = make_project(client, first_token)
    second_project = make_project(client, second_token)

    for _ in range(settings.chat_rate_limit_per_minute):
        _chat(client, first_token, first_project)
    assert _chat(client, first_token, first_project).status_code == 429

    # The second user is unaffected.
    assert _chat(client, second_token, second_project).status_code == 200


def test_concurrency_cap_rejects_an_extra_stream(client, fake_redis):
    token, user_id = register(client)
    project_id = make_project(client, token)

    # Hold every slot, as if that many streams were already open.
    limiter = RateLimiter(client=fake_redis)
    for _ in range(settings.chat_max_concurrent_streams):
        assert limiter.acquire_stream_slot(
            user_id=user_id, limit=settings.chat_max_concurrent_streams
        ).allowed

    blocked = _chat(client, token, project_id)
    assert blocked.status_code == 429
    assert "already have" in blocked.json()["detail"]


def test_stream_slot_is_released_after_the_response_completes(client, fake_redis):
    """A finished stream must give its slot back, or a user locks themselves out."""
    token, user_id = register(client)
    project_id = make_project(client, token)

    for _ in range(settings.chat_max_concurrent_streams + 2):
        assert _chat(client, token, project_id).status_code == 200

    assert fake_redis.get(f"orchestra:rl:streams:{user_id}") in (None, 0, "0")


def test_daily_token_budget_blocks_when_exhausted(client, fake_redis, frozen_window):
    token, user_id = register(client)
    project_id = make_project(client, token)

    # The key is derived from the limiter's clock, which `frozen_window` pins.
    day = frozen_window.strftime("%Y-%m-%d")
    fake_redis.set(f"orchestra:rl:tokens:{user_id}:{day}", settings.chat_daily_token_budget)

    blocked = _chat(client, token, project_id)
    assert blocked.status_code == 429
    assert "budget" in blocked.json()["detail"].lower()


def test_completed_turn_records_token_spend(client, fake_redis, frozen_window):
    token, user_id = register(client)
    project_id = make_project(client, token)
    _chat(client, token, project_id)

    day = frozen_window.strftime("%Y-%m-%d")
    used = fake_redis.get(f"orchestra:rl:tokens:{user_id}:{day}")
    assert int(used) > 0


def test_signup_is_rate_limited_per_ip(client):
    for i in range(settings.signup_rate_limit_per_hour):
        response = client.post(
            "/api/v1/auth/signup",
            json={"email": f"burst{i}@example.com", "password": "password123"},
        )
        assert response.status_code == 201

    blocked = client.post(
        "/api/v1/auth/signup",
        json={"email": "one-too-many@example.com", "password": "password123"},
    )
    assert blocked.status_code == 429


def test_limiter_fails_open_in_development_when_redis_is_down(client, fake_redis):
    """Development keeps Redis optional; production fails closed instead."""
    token, _ = register(client)
    project_id = make_project(client, token)

    fake_redis.fail = True
    assert settings.rate_limit_fail_open is True
    assert _chat(client, token, project_id).status_code == 200


def test_fixed_window_is_lenient_across_a_boundary(fake_redis, monkeypatch):
    """Document the known weakness rather than pretend it is not there.

    A fixed window resets on a wall-clock boundary, so a burst spanning one is
    counted as two separate windows and can exceed the nominal limit. This is
    why 14 sequential requests once passed a 10/minute limit — not a bug in the
    limiter, a property of the algorithm. Concurrency is what actually bounds
    the damage today; a sliding window is the real fix.
    """
    from datetime import UTC
    from datetime import datetime as real_datetime

    from app.core.limiter import RateLimiter

    clock = {"now": real_datetime(2026, 1, 1, 12, 30, 59, tzinfo=UTC)}

    class _MovingDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            return clock["now"]

    monkeypatch.setattr("app.core.limiter.datetime", _MovingDatetime)
    limiter = RateLimiter(client=fake_redis)

    def hit():
        return limiter.hit(scope="chat", identity="7", limit=10, window_seconds=60)

    for _ in range(10):
        assert hit().allowed
    assert not hit().allowed, "the 11th request in this window is refused"

    # One second later a new window starts and the budget is fresh.
    clock["now"] = real_datetime(2026, 1, 1, 12, 31, 0, tzinfo=UTC)
    for _ in range(10):
        assert hit().allowed, "a new fixed window grants a full fresh allowance"


def test_limiter_fails_closed_when_configured_to(fake_redis, monkeypatch):
    """The production posture: unmetered is worse than briefly unavailable."""
    monkeypatch.setattr(
        type(settings), "rate_limit_fail_open", property(lambda self: False)
    )
    fake_redis.fail = True
    limiter = RateLimiter(client=fake_redis)

    decision = limiter.hit(scope="chat", identity="1", limit=10, window_seconds=60)
    assert decision.allowed is False
    assert "unavailable" in decision.detail
