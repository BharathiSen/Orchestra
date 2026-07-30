"""Redis-backed conversation (short-term / session) memory store."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis_client import get_redis
from app.memory.models import MemoryMessage


class RedisConversationStore:
    """Stores a rolling conversation buffer + optional compressed summary.

    Keys
    ----
    orchestra:conv:{conversation_id}:messages  — JSON list (capped)
    orchestra:conv:{conversation_id}:summary   — compressed older turns
    orchestra:session:{user_id}                — last activity metadata
    """

    CONV_KEY = "orchestra:conv:{conversation_id}:messages"
    SUMMARY_KEY = "orchestra:conv:{conversation_id}:summary"
    SESSION_KEY = "orchestra:session:{user_id}"

    def __init__(
        self,
        client: Redis | None = None,
        *,
        buffer_limit: int | None = None,
        ttl_seconds: int = 60 * 60 * 24 * 7,
    ) -> None:
        self._client = client
        self.buffer_limit = buffer_limit or settings.memory_buffer_size
        self.ttl_seconds = ttl_seconds

    @property
    def client(self) -> Redis:
        if self._client is None:
            self._client = get_redis()
        return self._client

    def ping(self) -> bool:
        try:
            return bool(self.client.ping())
        except RedisError:
            return False

    def _conv_key(self, conversation_id: int) -> str:
        return self.CONV_KEY.format(conversation_id=conversation_id)

    def _summary_key(self, conversation_id: int) -> str:
        return self.SUMMARY_KEY.format(conversation_id=conversation_id)

    def _session_key(self, user_id: int) -> str:
        return self.SESSION_KEY.format(user_id=user_id)

    def append_message(
        self,
        *,
        conversation_id: int,
        user_id: int,
        role: str,
        content: str,
    ) -> int:
        """Append one message and trim to buffer_limit. Returns new length."""
        payload = json.dumps(
            {
                "role": role,
                "content": content,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        key = self._conv_key(conversation_id)
        pipe = self.client.pipeline()
        pipe.rpush(key, payload)
        pipe.ltrim(key, -self.buffer_limit, -1)
        pipe.expire(key, self.ttl_seconds)
        pipe.set(
            self._session_key(user_id),
            json.dumps(
                {
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ),
            ex=self.ttl_seconds,
        )
        pipe.execute()
        return int(self.client.llen(key))

    def peek_overflow(
        self,
        conversation_id: int,
        *,
        incoming: int = 2,
    ) -> list[MemoryMessage]:
        """Return messages that will fall out of the buffer after `incoming` appends."""
        current = self.get_messages(conversation_id)
        projected = len(current) + incoming
        if projected <= self.buffer_limit:
            return []
        drop = projected - self.buffer_limit
        return current[:drop]

    def get_messages(self, conversation_id: int) -> list[MemoryMessage]:
        raw = self.client.lrange(self._conv_key(conversation_id), 0, -1)
        messages: list[MemoryMessage] = []
        for item in raw:
            try:
                data = json.loads(item)
                messages.append(
                    MemoryMessage(
                        role=str(data.get("role") or "user"),
                        content=str(data.get("content") or ""),
                        created_at=data.get("created_at"),
                    )
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return messages

    def get_summary(self, conversation_id: int) -> str | None:
        try:
            value = self.client.get(self._summary_key(conversation_id))
            return str(value) if value else None
        except RedisError:
            return None

    def set_summary(self, conversation_id: int, summary: str) -> None:
        text = (summary or "").strip()
        if not text:
            return
        try:
            self.client.set(
                self._summary_key(conversation_id),
                text[:4000],
                ex=self.ttl_seconds,
            )
        except RedisError:
            return

    def memory_size(self, conversation_id: int) -> int:
        try:
            return int(self.client.llen(self._conv_key(conversation_id)))
        except RedisError:
            return 0

    def session_active(self, user_id: int) -> bool:
        try:
            return bool(self.client.exists(self._session_key(user_id)))
        except RedisError:
            return False

    def clear_conversation(self, conversation_id: int) -> None:
        try:
            self.client.delete(
                self._conv_key(conversation_id),
                self._summary_key(conversation_id),
            )
        except RedisError:
            pass

    def dump_conversation(self, conversation_id: int) -> dict[str, Any]:
        return {
            "conversation_id": conversation_id,
            "buffer_limit": self.buffer_limit,
            "memory_size": self.memory_size(conversation_id),
            "summary": self.get_summary(conversation_id),
            "messages": [m.model_dump() for m in self.get_messages(conversation_id)],
        }

    def sync_from_history(
        self,
        *,
        conversation_id: int,
        user_id: int,
        history: list[dict[str, Any]],
    ) -> int:
        """Replace Redis buffer with the last N history messages (Postgres sync)."""
        key = self._conv_key(conversation_id)
        recent = history[-self.buffer_limit :]
        overflow = history[: -self.buffer_limit] if len(history) > self.buffer_limit else []
        pipe = self.client.pipeline()
        pipe.delete(key)
        for msg in recent:
            pipe.rpush(
                key,
                json.dumps(
                    {
                        "role": msg.get("role"),
                        "content": msg.get("content"),
                        "created_at": msg.get("created_at")
                        or datetime.now(UTC).isoformat(),
                    }
                ),
            )
        if recent:
            pipe.expire(key, self.ttl_seconds)
        pipe.set(
            self._session_key(user_id),
            json.dumps(
                {
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ),
            ex=self.ttl_seconds,
        )
        pipe.execute()
        if overflow:
            lines = [
                f"{m.get('role')}: {str(m.get('content') or '')[:200]}"
                for m in overflow[-20:]
            ]
            self.set_summary(
                conversation_id,
                "Earlier conversation summary:\n" + "\n".join(lines),
            )
        return len(recent)
