"""Unified memory facade: Redis short-term + Postgres long-term."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.memory.models import (
    MemoryContext,
    MemoryMessage,
    MemoryStatus,
    UserMemory,
    UserMemoryItem,
)
from app.memory.redis import RedisConversationStore
from redis.exceptions import RedisError


class MemoryService:
    def __init__(self, db: Session, store: RedisConversationStore | None = None) -> None:
        self.db = db
        self.store = store or RedisConversationStore()
        self.buffer_limit = settings.memory_buffer_size

    def redis_connected(self) -> bool:
        return self.store.ping()

    def get_status(
        self,
        *,
        user_id: int,
        conversation_id: int | None = None,
    ) -> MemoryStatus:
        connected = self.redis_connected()
        size = 0
        if connected and conversation_id is not None:
            try:
                size = self.store.memory_size(conversation_id)
            except RedisError:
                connected = False
        session = False
        if connected:
            try:
                session = self.store.session_active(user_id)
            except RedisError:
                connected = False
        long_term = self.list_long_term(user_id=user_id)
        return MemoryStatus(
            redis_connected=connected,
            session_active=session,
            conversation_id=conversation_id,
            memory_size=size,
            buffer_limit=self.buffer_limit,
            memory_used=connected and size > 0,
            long_term_count=len(long_term),
        )

    def load_conversation_buffer(
        self,
        *,
        conversation_id: int,
        user_id: int,
        postgres_fallback: list[dict[str, Any]] | None = None,
    ) -> list[MemoryMessage]:
        """Prefer Redis buffer; fall back to last N Postgres messages."""
        try:
            if self.store.ping():
                cached = self.store.get_messages(conversation_id)
                if cached:
                    return cached
                if postgres_fallback:
                    self.store.sync_from_history(
                        conversation_id=conversation_id,
                        user_id=user_id,
                        history=postgres_fallback,
                    )
                    return self.store.get_messages(conversation_id)
        except RedisError:
            pass

        if not postgres_fallback:
            return []
        recent = postgres_fallback[-self.buffer_limit :]
        return [
            MemoryMessage(
                role=str(m.get("role") or "user"),
                content=str(m.get("content") or ""),
                created_at=str(m.get("created_at")) if m.get("created_at") else None,
            )
            for m in recent
            if m.get("role") in {"user", "assistant"} and str(m.get("content") or "").strip()
        ]

    def remember_turn(
        self,
        *,
        conversation_id: int,
        user_id: int,
        user_content: str,
        assistant_content: str,
    ) -> None:
        try:
            if not self.store.ping():
                return
            self.store.append_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="user",
                content=user_content,
            )
            self.store.append_message(
                conversation_id=conversation_id,
                user_id=user_id,
                role="assistant",
                content=assistant_content,
            )
        except RedisError:
            return

    def build_context(
        self,
        *,
        user_id: int,
        conversation_id: int,
        postgres_fallback: list[dict[str, Any]] | None = None,
    ) -> MemoryContext:
        connected = self.redis_connected()
        short_term = self.load_conversation_buffer(
            conversation_id=conversation_id,
            user_id=user_id,
            postgres_fallback=postgres_fallback,
        )
        long_term_rows = self.list_long_term(user_id=user_id)
        long_term = [
            {"category": r.category, "key": r.key, "value": r.value}
            for r in long_term_rows
        ]
        return MemoryContext(
            short_term=short_term,
            long_term=long_term,
            redis_connected=connected,
            memory_size=len(short_term),
            buffer_limit=self.buffer_limit,
        )

    def format_long_term_prompt(self, long_term: list[dict[str, Any]]) -> str:
        if not long_term:
            return ""
        lines = ["Known user preferences / long-term memory:"]
        for item in long_term:
            lines.append(f"- [{item.get('category')}] {item.get('key')}: {item.get('value')}")
        return "\n".join(lines)

    # ----- Long-term (Postgres) -----

    def list_long_term(self, *, user_id: int) -> list[UserMemoryItem]:
        rows = list(
            self.db.scalars(
                select(UserMemory)
                .where(UserMemory.user_id == user_id)
                .order_by(UserMemory.updated_at.desc())
            ).all()
        )
        return [UserMemoryItem.model_validate(r) for r in rows]

    def upsert_long_term(
        self,
        *,
        user_id: int,
        category: str,
        key: str,
        value: str,
    ) -> UserMemoryItem:
        existing = self.db.scalar(
            select(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.category == category,
                UserMemory.key == key,
            )
        )
        if existing is None:
            existing = UserMemory(
                user_id=user_id,
                category=category.strip().lower(),
                key=key.strip(),
                value=value.strip(),
            )
            self.db.add(existing)
        else:
            existing.value = value.strip()
            existing.category = category.strip().lower()
        self.db.commit()
        self.db.refresh(existing)
        return UserMemoryItem.model_validate(existing)

    def delete_long_term(self, *, user_id: int, memory_id: int) -> bool:
        row = self.db.get(UserMemory, memory_id)
        if row is None or row.user_id != user_id:
            return False
        self.db.delete(row)
        self.db.commit()
        return True
