from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import enforce_chat_rate_limit, get_current_user
from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.limiter import RateLimiter, get_rate_limiter
from app.models import User
from app.schemas import (
    ChatRequest,
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
    ModelsResponse,
    ToolInfo,
    ToolsResponse,
)
from app.services.chat_service import ChatService, list_supported_models
from app.tools import ensure_default_tools

router = APIRouter(tags=["chat"])


@router.get("/chat/models", response_model=ModelsResponse)
def get_chat_models() -> ModelsResponse:
    data = list_supported_models()
    return ModelsResponse.model_validate(data)


@router.get("/tools", response_model=ToolsResponse)
def list_tools(current_user: User = Depends(get_current_user)) -> ToolsResponse:
    """List every tool in the registry with its JSON schema."""
    _ = current_user
    catalog = ensure_default_tools().public_catalog()
    tools = [ToolInfo.model_validate(item) for item in catalog]
    return ToolsResponse(tools=tools, count=len(tools))


def _stream_with_cleanup(
    events: Iterator[str],
    *,
    limiter: RateLimiter,
    user_id: int,
    db: Session,
) -> Iterator[str]:
    """Yield the chat stream, then release the slot **and** the database session.

    The finally block covers the disconnect case too: closing the generator
    raises GeneratorExit inside it, so a user who navigates away mid-answer does
    not leak a slot and lock themselves out.

    Closing the session here is what makes its release deterministic. See
    `chat_stream` for why it is not a `Depends(get_db)`.
    """
    try:
        yield from events
    finally:
        limiter.release_stream_slot(user_id=user_id)
        db.close()


@router.post("/chat")
def chat_stream(
    payload: ChatRequest,
    current_user: User = Depends(enforce_chat_rate_limit),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> StreamingResponse:
    """Stream a chat turn.

    **Why this route opens its own session instead of `Depends(get_db)`.**
    A dependency with `yield` is torn down as part of the request/response cycle,
    but the body of a `StreamingResponse` is consumed by Starlette *after* the
    handler has returned. The session therefore outlived the dependency's
    teardown and was only released when Python happened to garbage-collect it —
    non-deterministic, and on PostgreSQL those abandoned connections sit `idle in
    transaction` holding locks in the meantime. Measured: eight sequential chat
    requests left five connections checked out of a pool of five.

    Owning the session explicitly and closing it in the generator's `finally`
    ties its lifetime to the stream, which is the thing that actually determines
    when it can be released. This does not change the concurrency ceiling — the
    session is still held for the whole stream, so the pool still bounds
    simultaneous chats — but a *finished* turn now always gives its connection
    back.
    """
    db = SessionLocal()
    try:
        service = ChatService(db)
        # Validate before a StreamingResponse exists. Once one is returned,
        # Starlette sends the 200 status line before it pulls the first event, so
        # anything that raises inside the generator can no longer set a status
        # code.
        service.validate_chat_request(user=current_user, payload=payload)

        # Taken here rather than in a dependency: a slot must be released when
        # the stream ends, and a dependency returns long before that happens.
        slot = limiter.acquire_stream_slot(
            user_id=current_user.id,
            limit=settings.chat_max_concurrent_streams,
        )
        if not slot.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=slot.detail,
                headers=slot.headers,
            )

        events = service.stream_chat(user=current_user, payload=payload)
    except BaseException:
        # Nothing was handed to the generator, so nothing else will close it.
        db.close()
        raise

    return StreamingResponse(
        _stream_with_cleanup(
            events,
            limiter=limiter,
            user_id=current_user.id,
            db=db,
        ),
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
    conversation = ChatService(db).get_conversation(
        user=current_user, conversation_id=conversation_id
    )
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
