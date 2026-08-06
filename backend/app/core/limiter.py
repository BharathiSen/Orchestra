"""Redis-backed abuse and cost controls for the chat and signup endpoints.

Three limits, because one is not enough:

* **Rate** — requests per minute. Stops a script hammering the endpoint.
* **Concurrency** — simultaneous open streams per user. A single chat turn can
  run for 30 seconds, so a rate limit alone still allows dozens of concurrent
  pipelines from one account.
* **Daily token budget** — the only limit that maps to actual money. A user can
  stay under both limits above and still burn a quota with long prompts.

Counters are fixed-window rather than sliding: one ``INCR`` plus one ``EXPIRE``
per check, no stored timestamps, and the burst it permits at a window boundary
is bounded by the concurrency cap anyway.

When Redis is unreachable nothing can be enforced. ``settings.rate_limit_fail_open``
decides what that means: development keeps Redis optional, production fails
closed rather than serving an unmetered endpoint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

KEY_PREFIX = "orchestra:rl"

# Concurrency slots are released in a finally block, but a hard kill (SIGKILL,
# container eviction) can still strand one. This TTL is the backstop: it is
# longer than any realistic pipeline run, so it never expires a live stream.
STREAM_SLOT_TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class RateLimitDecision:
    """Outcome of a single limit check."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: int
    detail: str = ""

    @property
    def headers(self) -> dict[str, str]:
        """Standard rate-limit headers for the response."""
        values = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
        }
        if not self.allowed and self.retry_after > 0:
            values["Retry-After"] = str(self.retry_after)
        return values


def _allowed(limit: int, remaining: int) -> RateLimitDecision:
    return RateLimitDecision(allowed=True, limit=limit, remaining=remaining, retry_after=0)


class RateLimiter:
    """Counters in Redis. Holds no state of its own beyond the connection."""

    def __init__(self, client: Redis | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Redis:
        if self._client is None:
            self._client = get_redis()
        return self._client

    # -- failure handling ---------------------------------------------------

    def _unavailable(self, limit: int, what: str, exc: Exception) -> RateLimitDecision:
        if settings.rate_limit_fail_open:
            logger.warning("Rate limiting unavailable for %s, allowing request: %s", what, exc)
            return _allowed(limit, remaining=limit)

        logger.error("Rate limiting unavailable for %s, refusing request: %s", what, exc)
        return RateLimitDecision(
            allowed=False,
            limit=limit,
            remaining=0,
            retry_after=30,
            detail=(
                "Rate limiting is temporarily unavailable, so requests cannot be "
                "metered. Try again shortly."
            ),
        )

    # -- fixed-window request rate -----------------------------------------

    def hit(
        self,
        *,
        scope: str,
        identity: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        """Count one request against ``scope``/``identity``."""
        if not settings.rate_limit_enabled or limit <= 0:
            return _allowed(limit, remaining=limit)

        # Bucketing by elapsed windows keeps the key self-expiring and makes the
        # remaining-time calculation exact without storing a timestamp.
        now = int(datetime.now(UTC).timestamp())
        window_start = now - (now % window_seconds)
        key = f"{KEY_PREFIX}:{scope}:{identity}:{window_start}"

        try:
            pipe = self.client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            used = int(pipe.execute()[0])
        except (RedisError, ValueError, OSError) as exc:
            return self._unavailable(limit, f"{scope}:{identity}", exc)

        if used > limit:
            retry_after = max(1, (window_start + window_seconds) - now)
            return RateLimitDecision(
                allowed=False,
                limit=limit,
                remaining=0,
                retry_after=retry_after,
                detail=(
                    f"Rate limit exceeded: {limit} request(s) per "
                    f"{window_seconds} seconds. Retry in {retry_after}s."
                ),
            )
        return _allowed(limit, remaining=limit - used)

    # -- concurrent streams -------------------------------------------------

    def _stream_key(self, user_id: int) -> str:
        return f"{KEY_PREFIX}:streams:{user_id}"

    def acquire_stream_slot(self, *, user_id: int, limit: int) -> RateLimitDecision:
        """Reserve one concurrent-stream slot. Release it in a finally block."""
        if not settings.rate_limit_enabled or limit <= 0:
            return _allowed(limit, remaining=limit)

        key = self._stream_key(user_id)
        try:
            pipe = self.client.pipeline()
            pipe.incr(key)
            pipe.expire(key, STREAM_SLOT_TTL_SECONDS)
            active = int(pipe.execute()[0])
        except (RedisError, ValueError, OSError) as exc:
            return self._unavailable(limit, f"streams:{user_id}", exc)

        if active > limit:
            # Give the slot straight back — this attempt never held one.
            self.release_stream_slot(user_id=user_id)
            return RateLimitDecision(
                allowed=False,
                limit=limit,
                remaining=0,
                retry_after=5,
                detail=(
                    f"You already have {limit} chat stream(s) running. "
                    "Wait for one to finish before starting another."
                ),
            )
        return _allowed(limit, remaining=limit - active)

    def release_stream_slot(self, *, user_id: int) -> None:
        """Free a slot. Never raises: cleanup must not mask the original error."""
        if not settings.rate_limit_enabled:
            return
        key = self._stream_key(user_id)
        try:
            if int(self.client.decr(key)) <= 0:
                self.client.delete(key)
        except (RedisError, ValueError, OSError) as exc:
            logger.warning("Could not release stream slot for user %s: %s", user_id, exc)

    # -- daily token budget -------------------------------------------------

    def _token_key(self, user_id: int) -> str:
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        return f"{KEY_PREFIX}:tokens:{user_id}:{day}"

    def check_token_budget(self, *, user_id: int, budget: int) -> RateLimitDecision:
        """Check spend *before* the LLM call. Reading a counter, not reserving."""
        if not settings.rate_limit_enabled or budget <= 0:
            return _allowed(budget, remaining=budget)

        try:
            raw = self.client.get(self._token_key(user_id))
        except (RedisError, ValueError, OSError) as exc:
            return self._unavailable(budget, f"tokens:{user_id}", exc)

        used = int(raw or 0)
        if used >= budget:
            # Seconds until the UTC day rolls over, so the client is told
            # precisely when the budget resets.
            now = datetime.now(UTC)
            midnight = now.replace(hour=23, minute=59, second=59, microsecond=0)
            retry_after = max(1, int((midnight - now).total_seconds()) + 1)
            return RateLimitDecision(
                allowed=False,
                limit=budget,
                remaining=0,
                retry_after=retry_after,
                detail=(
                    f"Daily token budget of {budget:,} tokens is exhausted "
                    f"({used:,} used). It resets at 00:00 UTC."
                ),
            )
        return _allowed(budget, remaining=budget - used)

    def record_token_usage(self, *, user_id: int, tokens: int) -> None:
        """Add a completed turn's tokens to today's counter."""
        if not settings.rate_limit_enabled or tokens <= 0:
            return
        key = self._token_key(user_id)
        try:
            pipe = self.client.pipeline()
            pipe.incrby(key, tokens)
            # Two days of slack so a turn that starts before midnight and lands
            # after it cannot resurrect an expired key with no TTL.
            pipe.expire(key, 2 * 24 * 60 * 60)
            pipe.execute()
        except (RedisError, ValueError, OSError) as exc:
            logger.warning("Could not record token usage for user %s: %s", user_id, exc)


_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Process-wide limiter. Stateless, so a single instance is safe to share."""
    return _limiter
