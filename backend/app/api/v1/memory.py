"""Memory API — status + long-term user preferences."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.memory.models import (
    MemoryStatus,
    UserMemoryItem,
    UserMemoryListResponse,
    UserMemoryUpsert,
)
from app.memory.service import MemoryService
from app.models import User
from app.repositories.chat_repository import ConversationRepository

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/status", response_model=MemoryStatus)
def memory_status(
    conversation_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryStatus:
    if conversation_id is not None:
        conversation = ConversationRepository(db).get(conversation_id)
        if conversation is None or conversation.project.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
    return MemoryService(db).get_status(
        user_id=current_user.id,
        conversation_id=conversation_id,
    )


@router.get("/preferences", response_model=UserMemoryListResponse)
def list_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserMemoryListResponse:
    items = MemoryService(db).list_long_term(user_id=current_user.id)
    return UserMemoryListResponse(items=items, count=len(items))


@router.put("/preferences", response_model=UserMemoryItem)
def upsert_preference(
    payload: UserMemoryUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserMemoryItem:
    return MemoryService(db).upsert_long_term(
        user_id=current_user.id,
        category=payload.category,
        key=payload.key,
        value=payload.value,
    )


@router.delete(
    "/preferences/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_preference(
    memory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ok = MemoryService(db).delete_long_term(user_id=current_user.id, memory_id=memory_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
