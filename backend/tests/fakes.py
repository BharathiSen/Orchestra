"""In-memory stand-ins for the two external services the app talks to.

Both are deliberately hand-written rather than pulled from a library. The Redis
surface Orchestra actually uses is small, and a fake that implements exactly that
surface documents the dependency: if a future change starts using a new command,
these tests fail loudly instead of silently exercising a different code path.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from app.services.llm_types import ChatCompletionResult


class FakeRedis:
    """Enough of the Redis API for the limiter and the conversation store.

    Supports the string, list, and pipeline commands used by
    `core/limiter.py` and `memory/redis.py`. TTLs are tracked and honoured so a
    test can assert expiry behaviour, but nothing expires on a timer — keys are
    checked lazily on access, which is also how Redis behaves.
    """

    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
        self.expiry: dict[str, float] = {}
        self.fail = False  # flip to simulate an outage

    # -- internals ----------------------------------------------------------

    def _check(self) -> None:
        if self.fail:
            from redis.exceptions import ConnectionError as RedisConnectionError

            raise RedisConnectionError("fake redis is down")

    def _alive(self, key: str) -> bool:
        expires = self.expiry.get(key)
        if expires is not None and expires <= time.time():
            self.store.pop(key, None)
            self.expiry.pop(key, None)
            return False
        return key in self.store

    # -- connection ---------------------------------------------------------

    def ping(self) -> bool:
        self._check()
        return True

    # -- strings ------------------------------------------------------------

    def get(self, key: str) -> Any:
        self._check()
        return self.store.get(key) if self._alive(key) else None

    def set(self, key: str, value: Any, ex: int | None = None) -> bool:
        self._check()
        self.store[key] = value
        if ex:
            self.expiry[key] = time.time() + ex
        return True

    def incr(self, key: str, amount: int = 1) -> int:
        self._check()
        current = int(self.store.get(key, 0)) if self._alive(key) else 0
        current += amount
        self.store[key] = current
        return current

    def incrby(self, key: str, amount: int) -> int:
        return self.incr(key, amount)

    def decr(self, key: str, amount: int = 1) -> int:
        return self.incr(key, -amount)

    def expire(self, key: str, seconds: int) -> bool:
        self._check()
        if key in self.store:
            self.expiry[key] = time.time() + seconds
            return True
        return False

    def exists(self, *keys: str) -> int:
        self._check()
        return sum(1 for key in keys if self._alive(key))

    def delete(self, *keys: str) -> int:
        self._check()
        removed = 0
        for key in keys:
            if self.store.pop(key, None) is not None:
                removed += 1
            self.expiry.pop(key, None)
        return removed

    # -- lists --------------------------------------------------------------

    def rpush(self, key: str, *values: Any) -> int:
        self._check()
        bucket = self.store.setdefault(key, []) if self._alive(key) else self.store.setdefault(key, [])
        if not isinstance(bucket, list):
            bucket = []
            self.store[key] = bucket
        bucket.extend(values)
        return len(bucket)

    def lrange(self, key: str, start: int, end: int) -> list[Any]:
        self._check()
        bucket = self.store.get(key) if self._alive(key) else None
        if not isinstance(bucket, list):
            return []
        if end == -1:
            return bucket[start:]
        return bucket[start : end + 1]

    def ltrim(self, key: str, start: int, end: int) -> bool:
        self._check()
        bucket = self.store.get(key)
        if not isinstance(bucket, list):
            return True
        self.store[key] = bucket[start:] if end == -1 else bucket[start : end + 1]
        return True

    def llen(self, key: str) -> int:
        self._check()
        bucket = self.store.get(key) if self._alive(key) else None
        return len(bucket) if isinstance(bucket, list) else 0

    # -- pipeline -----------------------------------------------------------

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self)


class FakePipeline:
    """Queues commands and replays them on `execute()`, returning each result."""

    def __init__(self, client: FakeRedis) -> None:
        self._client = client
        self._queued: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, name: str):
        def queue(*args, **kwargs):
            self._queued.append((name, args, kwargs))
            return self

        return queue

    def execute(self) -> list[Any]:
        self._client._check()
        results = []
        for name, args, kwargs in self._queued:
            results.append(getattr(self._client, name)(*args, **kwargs))
        self._queued.clear()
        return results


class FakeLLM:
    """Deterministic LLM stub. Records every call for assertions.

    `responses` maps a substring to the reply returned when that substring
    appears anywhere in the flattened prompt. This is how a test pins the model's
    output without a network call — and why an assertion about a *reply* proves
    nothing on its own. What these tests assert instead is the surrounding
    machinery: which messages were built, in what role, and what the pipeline did
    with the result.
    """

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        *,
        default: str | None = None,
        raise_on_call: Exception | None = None,
    ) -> None:
        self.responses = responses or {}
        self.default = default
        self.raise_on_call = raise_on_call
        self.calls: list[list[dict[str, Any]]] = []
        self.stream_calls: list[list[dict[str, Any]]] = []

    # -- helpers for assertions --------------------------------------------

    @property
    def last_messages(self) -> list[dict[str, Any]]:
        combined = self.calls + self.stream_calls
        return combined[-1] if combined else []

    def all_messages(self) -> list[dict[str, Any]]:
        """Every message from every call, flattened."""
        out: list[dict[str, Any]] = []
        for call in self.calls + self.stream_calls:
            out.extend(call)
        return out

    def _answer(self, messages: list[dict[str, Any]]) -> str:
        blob = " ".join(str(m.get("content") or "") for m in messages).lower()
        for needle, answer in self.responses.items():
            if needle.lower() in blob:
                return answer
        if self.default is not None:
            return self.default
        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = str(msg.get("content") or "")
                break
        return f"OK: {last_user[:120]}"

    # -- provider interface -------------------------------------------------

    def complete_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = "auto",
    ) -> ChatCompletionResult:
        if self.raise_on_call:
            raise self.raise_on_call
        self.calls.append(list(messages))
        content = self._answer(messages)
        return ChatCompletionResult(
            content=content,
            finish_reason="stop",
            prompt_tokens=11,
            completion_tokens=7,
            total_tokens=18,
        )

    def stream_chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        tools: list[dict[str, Any]] | None = None,
        usage_sink: dict[str, int] | None = None,
    ) -> Iterator[str]:
        if self.raise_on_call:
            raise self.raise_on_call
        self.stream_calls.append(list(messages))
        content = self._answer(messages)
        # Split into several chunks so a test can tell real streaming from a
        # single-shot emission.
        size = max(1, len(content) // 3)
        for i in range(0, len(content), size):
            yield content[i : i + size]
        if usage_sink is not None:
            usage_sink["prompt_tokens"] = 13
            usage_sink["completion_tokens"] = 5
            usage_sink["total_tokens"] = 18
