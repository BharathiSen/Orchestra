import json
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Agent, Conversation, Message, Project, User
from app.repositories.chat_repository import ConversationRepository, MessageRepository
from app.schemas import ChatRequest, ConversationCreate, ConversationUpdate
from app.services.llm_provider import (
    get_llm_service,
    get_supported_models,
    is_llm_configured,
    missing_provider_message,
)


class ChatService:
    """Owns conversation/message business rules and LLM orchestration."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.conversations = ConversationRepository(db)
        self.messages = MessageRepository(db)

    def _owned_project(self, *, project_id: int, user: User) -> Project:
        project = self.db.get(Project, project_id)
        if project is None or project.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project

    def _owned_conversation(self, *, conversation_id: int, user: User) -> Conversation:
        conversation = self.conversations.get(conversation_id)
        if conversation is None or conversation.project.owner_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        return conversation

    def _optional_owned_agent(self, *, agent_id: int | None, user: User, project_id: int) -> Agent | None:
        if agent_id is None:
            return None
        # Project ownership already enforced by caller; agent must belong to that project.
        agent = self.db.get(Agent, agent_id)
        if agent is None or agent.project_id != project_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        return agent

    def create_conversation(self, *, user: User, payload: ConversationCreate) -> Conversation:
        self._owned_project(project_id=payload.project_id, user=user)
        self._optional_owned_agent(
            agent_id=payload.agent_id,
            user=user,
            project_id=payload.project_id,
        )
        conversation = Conversation(
            project_id=payload.project_id,
            agent_id=payload.agent_id,
            title=payload.title,
            model_name=payload.model_name,
        )
        return self.conversations.create(conversation)

    def list_conversations(self, *, user: User, project_id: int) -> list[Conversation]:
        self._owned_project(project_id=project_id, user=user)
        return self.conversations.list_for_project(project_id)

    def get_conversation(self, *, user: User, conversation_id: int) -> Conversation:
        return self._owned_conversation(conversation_id=conversation_id, user=user)

    def update_conversation(
        self,
        *,
        user: User,
        conversation_id: int,
        payload: ConversationUpdate,
    ) -> Conversation:
        conversation = self._owned_conversation(conversation_id=conversation_id, user=user)
        data = payload.model_dump(exclude_unset=True)
        if "agent_id" in data and data["agent_id"] is not None:
            self._optional_owned_agent(
                agent_id=data["agent_id"],
                user=user,
                project_id=conversation.project_id,
            )
        return self.conversations.update(conversation, data)

    def delete_conversation(self, *, user: User, conversation_id: int) -> None:
        conversation = self._owned_conversation(conversation_id=conversation_id, user=user)
        self.conversations.delete(conversation)

    def list_messages(self, *, user: User, conversation_id: int) -> list[Message]:
        self._owned_conversation(conversation_id=conversation_id, user=user)
        return self.messages.list_for_conversation(conversation_id)

    def _resolve_system_prompt(self, *, payload: ChatRequest, agent: Agent | None) -> str:
        if payload.system_prompt and payload.system_prompt.strip():
            return payload.system_prompt.strip()
        if agent and agent.system_prompt.strip():
            return agent.system_prompt.strip()
        return settings.default_system_prompt

    def _title_from_message(self, message: str) -> str:
        cleaned = " ".join(message.strip().split())
        if len(cleaned) <= 60:
            return cleaned or "New conversation"
        return cleaned[:57] + "..."

    def stream_chat(self, *, user: User, payload: ChatRequest) -> Iterator[str]:
        """Yield SSE lines while calling Gemini and persisting messages."""
        # Fail fast before mutating DB if the LLM is not configured.
        if not is_llm_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=missing_provider_message(),
            )

        self._owned_project(project_id=payload.project_id, user=user)
        agent = self._optional_owned_agent(
            agent_id=payload.agent_id,
            user=user,
            project_id=payload.project_id,
        )

        if payload.conversation_id is None:
            conversation = self.conversations.create(
                Conversation(
                    project_id=payload.project_id,
                    agent_id=payload.agent_id,
                    title=self._title_from_message(payload.message),
                    model_name=payload.model,
                )
            )
        else:
            conversation = self._owned_conversation(
                conversation_id=payload.conversation_id,
                user=user,
            )
            if conversation.project_id != payload.project_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="conversation_id does not belong to project_id",
                )
            conversation.model_name = payload.model
            if payload.agent_id is not None:
                conversation.agent_id = payload.agent_id
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)

        yield _sse({"type": "meta", "conversation_id": conversation.id, "title": conversation.title})

        history = self.messages.list_for_conversation(conversation.id)
        # Only persist user/assistant turns in DB history for the UI.
        # System prompt is injected at request time (not stored every turn).
        user_message = self.messages.create(
            Message(
                conversation_id=conversation.id,
                role="user",
                content=payload.message,
            )
        )
        yield _sse(
            {
                "type": "user_message",
                "id": user_message.id,
                "role": user_message.role,
                "content": user_message.content,
            }
        )

        llm_messages: list[dict[str, str]] = [
            {"role": "system", "content": self._resolve_system_prompt(payload=payload, agent=agent)}
        ]
        for msg in history:
            if msg.role in {"user", "assistant"} and msg.content.strip():
                llm_messages.append({"role": msg.role, "content": msg.content})
        llm_messages.append({"role": "user", "content": payload.message})

        llm = get_llm_service()
        assistant_chunks: list[str] = []

        try:
            for token in llm.stream_chat_completion(
                messages=llm_messages,
                model=payload.model,
                temperature=payload.temperature,
            ):
                assistant_chunks.append(token)
                yield _sse({"type": "token", "content": token})
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail)
            yield _sse({"type": "error", "detail": detail})
            return

        full_reply = "".join(assistant_chunks).strip()
        if not full_reply:
            full_reply = "(No content returned by the model.)"

        assistant_message = self.messages.create(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=full_reply,
            )
        )
        conversation.updated_at = datetime.now(UTC)
        self.db.add(conversation)
        self.db.commit()
        yield _sse(
            {
                "type": "done",
                "message_id": assistant_message.id,
                "conversation_id": conversation.id,
            }
        )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def list_supported_models() -> dict:
    return {
        "models": get_supported_models(),
        "gemini_configured": is_llm_configured(),  # kept for UI compatibility
        "llm_configured": is_llm_configured(),
        "provider": settings.active_llm_provider,
    }
