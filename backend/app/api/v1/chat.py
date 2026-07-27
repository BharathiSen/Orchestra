from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas import (
    ChatRequest,
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
    ModelsResponse,
)
from app.services.chat_service import ChatService, list_supported_models

router = APIRouter(tags=["chat"])


@router.get("/chat/models", response_model=ModelsResponse)
def get_chat_models() -> ModelsResponse:
    data = list_supported_models()
    return ModelsResponse.model_validate(data)


@router.post("/chat")
def chat_stream(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    service = ChatService(db)
    return StreamingResponse(
        service.stream_chat(user=current_user, payload=payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    conversation = ChatService(db).create_conversation(user=current_user, payload=payload)
    return ConversationResponse.model_validate(conversation)


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(
    project_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConversationResponse]:
    conversations = ChatService(db).list_conversations(user=current_user, project_id=project_id)
    return [ConversationResponse.model_validate(item) for item in conversations]


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    conversation = ChatService(db).get_conversation(user=current_user, conversation_id=conversation_id)
    return ConversationResponse.model_validate(conversation)


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    conversation = ChatService(db).update_conversation(
        user=current_user,
        conversation_id=conversation_id,
        payload=payload,
    )
    return ConversationResponse.model_validate(conversation)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ChatService(db).delete_conversation(user=current_user, conversation_id=conversation_id)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
def list_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MessageResponse]:
    messages = ChatService(db).list_messages(user=current_user, conversation_id=conversation_id)
    return [MessageResponse.model_validate(item) for item in messages]
