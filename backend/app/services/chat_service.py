import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

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
from app.tools import ensure_default_tools

MAX_TOOL_CALLS_PER_ROUND = 3

TOOL_SYSTEM_ADDENDUM = (
    "\n\nYou have access to tools. Use them when they help answer accurately "
    "(math → calculator, weather → weather, project/AI concepts → search). "
    "After tool results arrive, give a clear final answer to the user. "
    "Do not invent tool results."
)


class ChatService:
    """Owns conversation/message business rules and LLM orchestration."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.conversations = ConversationRepository(db)
        self.messages = MessageRepository(db)
        self.tools = ensure_default_tools()

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

    def _optional_owned_agent(
        self, *, agent_id: int | None, user: User, project_id: int
    ) -> Agent | None:
        if agent_id is None:
            return None
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

    def _resolve_system_prompt(
        self,
        *,
        payload: ChatRequest,
        agent: Agent | None,
        enable_tools: bool,
    ) -> str:
        if payload.system_prompt and payload.system_prompt.strip():
            base = payload.system_prompt.strip()
        elif agent and agent.system_prompt.strip():
            base = agent.system_prompt.strip()
        else:
            base = settings.default_system_prompt
        if enable_tools:
            return base + TOOL_SYSTEM_ADDENDUM
        return base

    def _title_from_message(self, message: str) -> str:
        cleaned = " ".join(message.strip().split())
        if len(cleaned) <= 60:
            return cleaned or "New conversation"
        return cleaned[:57] + "..."

    def stream_chat(self, *, user: User, payload: ChatRequest) -> Iterator[str]:
        """Yield SSE events for chat, optional tool rounds, then persist the assistant reply."""
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

        yield _sse(
            {"type": "meta", "conversation_id": conversation.id, "title": conversation.title}
        )

        history = self.messages.list_for_conversation(conversation.id)
        # Persist user/assistant only (ADR-011). Tool activity is live SSE for the UI.
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

        enable_tools = bool(payload.enable_tools)
        llm_messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": self._resolve_system_prompt(
                    payload=payload,
                    agent=agent,
                    enable_tools=enable_tools,
                ),
            }
        ]
        for msg in history:
            if msg.role in {"user", "assistant"} and msg.content.strip():
                llm_messages.append({"role": msg.role, "content": msg.content})
        llm_messages.append({"role": "user", "content": payload.message})

        llm = get_llm_service()
        openai_tools = self.tools.openai_tools() if enable_tools else None
        assistant_chunks: list[str] = []

        try:
            if enable_tools and openai_tools:
                for event in self._run_with_tools(
                    llm=llm,
                    llm_messages=llm_messages,
                    model=payload.model,
                    temperature=payload.temperature,
                    tools=openai_tools,
                    assistant_chunks=assistant_chunks,
                ):
                    yield event
            else:
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
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "detail": f"Chat pipeline error: {exc}"})
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

    def _run_with_tools(
        self,
        *,
        llm: Any,
        llm_messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        tools: list[dict[str, Any]],
        assistant_chunks: list[str],
    ) -> Iterator[str]:
        """
        Tool-calling pipeline:

        User → LLM (decide) → Tool Call? → Registry.execute → Tool result → LLM → Final answer

        Safety:
        - At most MAX_TOOL_ROUNDS decision rounds
        - At most 3 tool calls executed per round (parallel fan-out cap)
        - After any tool execution, force a final answer pass with tools disabled
          so the model cannot loop forever on the same tool
        """
        tools_were_used = False

        # Decision round — allow tools.
        result = llm.complete_chat(
            messages=llm_messages,
            model=model,
            temperature=temperature,
            tools=tools,
            tool_choice="auto",
        )

        if result.has_tool_calls:
            # Cap parallel tool fan-out from a single model response.
            selected_calls = result.tool_calls[:MAX_TOOL_CALLS_PER_ROUND]
            assistant_msg = {
                "role": "assistant",
                "content": result.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        },
                    }
                    for tc in selected_calls
                ],
            }
            llm_messages.append(assistant_msg)

            for tc in selected_calls:
                yield _sse(
                    {
                        "type": "tool_start",
                        "tool_call_id": tc.id,
                        "tool_name": tc.name,
                        "arguments": tc.arguments,
                        "status": "running",
                    }
                )
                try:
                    tool_output = self.tools.execute(tc.name, tc.arguments)
                    status_label = "complete"
                except HTTPException as exc:
                    tool_output = (
                        exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail)
                    )
                    status_label = "error"

                yield _sse(
                    {
                        "type": "tool_result",
                        "tool_call_id": tc.id,
                        "tool_name": tc.name,
                        "status": status_label,
                        "result": tool_output,
                    }
                )
                llm_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": tool_output,
                    }
                )

            tools_were_used = True

        elif result.content and result.content.strip():
            for token in _chunk_text(result.content):
                assistant_chunks.append(token)
                yield _sse({"type": "token", "content": token})
            return

        # Final answer pass (tools disabled). Always after tools, or if decision was empty.
        if tools_were_used or not assistant_chunks:
            for token in llm.stream_chat_completion(
                messages=llm_messages,
                model=model,
                temperature=temperature,
            ):
                assistant_chunks.append(token)
                yield _sse({"type": "token", "content": token})


def _chunk_text(text: str, size: int = 24) -> Iterator[str]:
    for i in range(0, len(text), size):
        yield text[i : i + size]


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def list_supported_models() -> dict:
    return {
        "models": get_supported_models(),
        "gemini_configured": is_llm_configured(),
        "llm_configured": is_llm_configured(),
        "provider": settings.active_llm_provider,
    }
