"""Unified memory facade: Redis short-term + Postgres long-term."""

from __future__ import annotations

from typing import Any

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.memory.facts import extract_facts
from app.memory.models import (
    ConversationMemoryDump,
    MemoryContext,
    MemoryMessage,
    MemoryStatus,
    UserMemory,
    UserMemoryItem,
)
from app.memory.redis import RedisConversationStore


class MemoryService:
    def __init__(
        self,
        db: Session,
        store: RedisConversationStore | None = None,
        llm: Any | None = None,
    ) -> None:
        self.db = db
        self.store = store or RedisConversationStore()
        self.llm = llm
        self.buffer_limit = settings.memory_buffer_size
        self._connected: bool | None = None

    def redis_connected(self) -> bool:
        """Connectivity, resolved once per service instance.

        A single chat turn asks this from build_context, get_status, and
        remember_turn, several times each. Because the service is constructed
        per request, caching for its lifetime removes roughly eight network
        round-trips per turn without ever serving a stale answer across
        requests. Operations that observe a failure call `_mark_disconnected`
        so the cached value cannot outlive a mid-request outage.
        """
        if self._connected is None:
            self._connected = self.store.ping()
        return self._connected

    def _mark_disconnected(self) -> None:
        self._connected = False

    def get_status(
        self,
        *,
        user_id: int,
        conversation_id: int | None = None,
    ) -> MemoryStatus:
        connected = self.redis_connected()
        size = 0
        has_summary = False
        if connected and conversation_id is not None:
            try:
                size = self.store.memory_size(conversation_id)
                has_summary = bool(self.store.get_summary(conversation_id))
            except RedisError:
                connected = False
                self._mark_disconnected()
        session = False
        if connected:
            try:
                session = self.store.session_active(user_id)
            except RedisError:
                connected = False
                self._mark_disconnected()
        long_term = self.list_long_term(user_id=user_id)
        return MemoryStatus(
            redis_connected=connected,
            session_active=session,
            conversation_id=conversation_id,
            memory_size=size,
            buffer_limit=self.buffer_limit,
            memory_used=connected and (size > 0 or has_summary),
            long_term_count=len(long_term),
            has_summary=has_summary,
        )

    def inspect_conversation(
        self,
        *,
        user_id: int,
        conversation_id: int,
    ) -> ConversationMemoryDump:
        connected = self.redis_connected()
        dump = (
            self.store.dump_conversation(conversation_id)
            if connected
            else {
                "conversation_id": conversation_id,
                "buffer_limit": self.buffer_limit,
                "memory_size": 0,
                "summary": None,
                "messages": [],
            }
        )
        return ConversationMemoryDump(
            conversation_id=conversation_id,
            buffer_limit=int(dump.get("buffer_limit") or self.buffer_limit),
            memory_size=int(dump.get("memory_size") or 0),
            summary=dump.get("summary"),
            messages=[
                MemoryMessage.model_validate(m) if not isinstance(m, MemoryMessage) else m
                for m in (dump.get("messages") or [])
            ],
            long_term=self.list_long_term(user_id=user_id),
            redis_connected=connected,
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
            if self.redis_connected():
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
            self._mark_disconnected()

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
        model: str | None = None,
    ) -> None:
        try:
            if not self.redis_connected():
                return
            overflow = self.store.peek_overflow(conversation_id, incoming=2)
            if overflow:
                self._compress_overflow(
                    conversation_id=conversation_id,
                    overflow=overflow,
                    model=model or settings.groq_default_model,
                )
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
            self._mark_disconnected()
            return

    def _compress_overflow(
        self,
        *,
        conversation_id: int,
        overflow: list[MemoryMessage],
        model: str,
    ) -> None:
        existing = self.store.get_summary(conversation_id) or ""
        lines = [f"{m.role}: {m.content[:240]}" for m in overflow if m.content.strip()]
        if not lines:
            return
        blob = "\n".join(lines)
        summary = ""
        if self.llm is not None:
            try:
                result = self.llm.complete_chat(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Compress the conversation excerpt into 3-6 bullet points. "
                                "Keep names, preferences, and decisions. No preamble."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Existing summary:\n{existing or '(none)'}\n\n"
                                f"Overflow turns:\n{blob}"
                            ),
                        },
                    ],
                    model=model,
                    temperature=0.1,
                    tools=None,
                    tool_choice=None,
                )
                summary = (result.content or "").strip()
            except Exception:  # noqa: BLE001
                summary = ""
        if not summary:
            summary = (
                (existing + "\n" if existing else "")
                + "Earlier turns:\n"
                + blob
            )
        self.store.set_summary(conversation_id, summary.strip()[:4000])

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
        summary = None
        if connected:
            try:
                summary = self.store.get_summary(conversation_id)
            except RedisError:
                summary = None
                self._mark_disconnected()
        long_term_rows = self.list_long_term(user_id=user_id)
        long_term = [
            {"category": r.category, "key": r.key, "value": r.value}
            for r in long_term_rows
        ]
        return MemoryContext(
            short_term=short_term,
            long_term=long_term,
            conversation_summary=summary,
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

    def format_summary_prompt(self, summary: str | None) -> str:
        if not summary or not summary.strip():
            return ""
        return f"Compressed earlier conversation:\n{summary.strip()}"

    def auto_extract_and_store(self, *, user_id: int, text: str) -> list[UserMemoryItem]:
        saved: list[UserMemoryItem] = []
        for fact in extract_facts(text):
            saved.append(
                self.upsert_long_term(
                    user_id=user_id,
                    category=fact.category,
                    key=fact.key,
                    value=fact.value,
                )
            )
        return saved

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
