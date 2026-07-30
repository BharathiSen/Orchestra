"""Memory data models.

Short-term / session memory live in Redis (see redis.py).
Long-term user facts live in Postgres via UserMemory.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserMemory(Base):
    """Persistent per-user facts (preferences, favorites, pinned KBs, etc.)."""

    __tablename__ = "user_memories"
    __table_args__ = (
        UniqueConstraint("user_id", "category", "key", name="uq_user_memory_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[Any] = relationship("User", back_populates="memories")


class MemoryMessage(BaseModel):
    role: str
    content: str
    created_at: str | None = None


class MemoryStatus(BaseModel):
    redis_connected: bool
    session_active: bool
    conversation_id: int | None = None
    memory_size: int = 0
    buffer_limit: int = 10
    memory_used: bool = False
    long_term_count: int = 0
    has_summary: bool = False


class UserMemoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    key: str
    value: str
    created_at: datetime
    updated_at: datetime


class UserMemoryUpsert(BaseModel):
    category: str = Field(
        min_length=1,
        max_length=64,
        description="preference | favorite_model | pinned_kb | frequent_agent",
    )
    key: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=4000)


class UserMemoryListResponse(BaseModel):
    items: list[UserMemoryItem]
    count: int


class MemoryContext(BaseModel):
    """Bundle passed into the orchestra / prompt builder."""

    short_term: list[MemoryMessage] = Field(default_factory=list)
    long_term: list[dict[str, Any]] = Field(default_factory=list)
    conversation_summary: str | None = None
    redis_connected: bool = False
    memory_size: int = 0
    buffer_limit: int = 10


class ConversationMemoryDump(BaseModel):
    conversation_id: int
    buffer_limit: int
    memory_size: int
    summary: str | None = None
    messages: list[MemoryMessage]
    long_term: list[UserMemoryItem] = Field(default_factory=list)
    redis_connected: bool = False
