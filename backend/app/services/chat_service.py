import contextlib
import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.limiter import get_rate_limiter
from app.evaluation.tracker import ExecutionTracker, StepRecord
from app.graph import build_agent_graph
from app.memory.service import MemoryService
from app.models import Agent, Conversation, Message, Project, User
from app.observability import TraceService, TrackingLLM
from app.orchestrator import OrchestraEngine
from app.prompts.system import tool_system_addendum
from app.rag.service import RagService
from app.repositories.chat_repository import ConversationRepository, MessageRepository
from app.schemas import ChatRequest, ConversationCreate, ConversationUpdate
from app.services.llm_provider import (
    get_llm_service,
    get_supported_models,
    is_llm_configured,
    missing_provider_message,
)
from app.tools import ensure_default_tools

logger = logging.getLogger(__name__)

TOOL_SYSTEM_ADDENDUM = tool_system_addendum()


class ChatService:
    """Owns conversation/message business rules and LLM orchestration."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.conversations = ConversationRepository(db)
        self.messages = MessageRepository(db)
        self.tools = ensure_default_tools()
        self.rag = RagService(db)
        self.memory = MemoryService(db)

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
        from sqlalchemy.orm import selectinload

        agent = (
            self.db.query(Agent)
            .options(selectinload(Agent.knowledge_bases))
            .filter(Agent.id == agent_id, Agent.project_id == project_id)
            .first()
        )
        if agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        _ = user  # project ownership already validated by caller
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
        # Clearing the Redis buffer is best-effort; the Postgres delete below is
        # what actually removes the conversation.
        with contextlib.suppress(Exception):
            self.memory.store.clear_conversation(conversation_id)
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
        long_term_block: str = "",
        summary_block: str = "",
    ) -> str:
        if payload.system_prompt and payload.system_prompt.strip():
            base = payload.system_prompt.strip()
        elif agent and agent.system_prompt.strip():
            base = agent.system_prompt.strip()
        else:
            base = settings.default_system_prompt
        extras: list[str] = []
        if summary_block:
            extras.append(summary_block)
        if long_term_block:
            extras.append(long_term_block)
        if extras:
            base = f"{base}\n\n" + "\n\n".join(extras)
        if enable_tools:
            return base + TOOL_SYSTEM_ADDENDUM
        return base

    def _ground_with_knowledge(
        self,
        *,
        agent: Agent | None,
        question: str,
        base_system_prompt: str,
        llm_messages: list[dict[str, Any]],
        tracker: ExecutionTracker,
        turn_trace: dict[str, Any],
    ) -> Iterator[str]:
        """Retrieve for an agent's knowledge bases and ground the system prompt.

        Shared by the direct and tools paths, which previously carried identical
        copies of this block. Mutates `llm_messages[0]` in place and yields the
        SSE events the caller should forward, so the retrieval step is recorded
        on the tracker exactly once regardless of which path runs.
        """
        if not (agent and getattr(agent, "knowledge_bases", None)):
            return

        kb_ids = [kb.id for kb in agent.knowledge_bases]
        retrieve_step = tracker.start_step("retrieve")
        try:
            chunks = self.rag.retrieve_chunks_for_question(
                question=question,
                knowledge_base_ids=kb_ids,
                top_k=5,
            )
        except Exception as exc:  # noqa: BLE001
            # Retrieval failing should degrade to an ungrounded answer rather
            # than abort the turn: the model can still respond usefully.
            logger.warning("Knowledge retrieval failed: %s", exc, exc_info=True)
            tracker.end_step(retrieve_step, status="error", detail={"chunks": 0})
            return

        if not chunks:
            tracker.end_step(retrieve_step, status="done", detail={"chunks": 0})
            return

        retrieved_chunks = self.rag.serialize_chunks(chunks)
        llm_messages[0]["content"] = self.rag.build_grounded_prompt(
            base_system_prompt=base_system_prompt,
            retrieved_chunks=chunks,
        )
        turn_trace["retrieved_chunks"] = retrieved_chunks
        tracker.end_step(
            retrieve_step,
            status="done",
            detail={"chunks": len(retrieved_chunks)},
        )
        yield _sse(
            {
                "type": "retrieved_context",
                "count": len(retrieved_chunks),
                "chunks": retrieved_chunks,
            }
        )

    def _record_token_spend(self, *, user_id: int, tracker: ExecutionTracker) -> None:
        """Bill this turn's tokens against the user's daily budget.

        Called on failure as well as success: a pipeline that errored halfway
        still consumed whatever the provider already charged for.
        """
        get_rate_limiter().record_token_usage(
            user_id=user_id,
            tokens=tracker.total_tokens,
        )

    def _title_from_message(self, message: str) -> str:
        cleaned = " ".join(message.strip().split())
        if len(cleaned) <= 60:
            return cleaned or "New conversation"
        return cleaned[:57] + "..."

    def stream_chat(self, *, user: User, payload: ChatRequest) -> Iterator[str]:
        """Yield SSE events for chat and persist the assistant reply."""
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
        postgres_fallback = [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in history
            if msg.role in {"user", "assistant"} and msg.content.strip()
        ]

        # Load the Redis short-term buffer plus long-term facts. Postgres history
        # is passed as a fallback so a cold or evicted Redis still yields context.
        memory_ctx = self.memory.build_context(
            user_id=user.id,
            conversation_id=conversation.id,
            postgres_fallback=postgres_fallback,
        )
        mem_status = self.memory.get_status(
            user_id=user.id,
            conversation_id=conversation.id,
        )
        yield _sse(
            {
                "type": "memory_status",
                "redis_connected": mem_status.redis_connected,
                "session_active": True,
                "conversation_id": conversation.id,
                "memory_size": memory_ctx.memory_size,
                "buffer_limit": memory_ctx.buffer_limit,
                "memory_used": memory_ctx.memory_size > 0
                or bool(memory_ctx.conversation_summary),
                "long_term_count": mem_status.long_term_count,
                "has_summary": bool(memory_ctx.conversation_summary),
            }
        )

        # Auto-extract durable facts from this user turn ("I prefer Python", etc.)
        extracted = self.memory.auto_extract_and_store(
            user_id=user.id,
            text=payload.message,
        )
        if extracted:
            mem_status = self.memory.get_status(
                user_id=user.id,
                conversation_id=conversation.id,
            )
            yield _sse(
                {
                    "type": "memory_status",
                    "redis_connected": mem_status.redis_connected,
                    "session_active": True,
                    "conversation_id": conversation.id,
                    "memory_size": memory_ctx.memory_size,
                    "buffer_limit": memory_ctx.buffer_limit,
                    "memory_used": True,
                    "long_term_count": mem_status.long_term_count,
                    "has_summary": bool(memory_ctx.conversation_summary),
                    "extracted_facts": [
                        {"category": f.category, "key": f.key, "value": f.value}
                        for f in extracted
                    ],
                }
            )

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

        enable_orchestra = bool(payload.enable_orchestra)
        # Orchestra owns the multi-agent path; tools graph is separate.
        enable_tools = bool(payload.enable_tools) and not enable_orchestra
        if enable_orchestra:
            pipeline = "orchestra"  # refined to simple/full after route is known
        elif enable_tools:
            pipeline = "tools"
        else:
            pipeline = "direct"

        # Refresh long-term after auto-extract
        memory_ctx = self.memory.build_context(
            user_id=user.id,
            conversation_id=conversation.id,
            postgres_fallback=postgres_fallback,
        )
        long_term_block = self.memory.format_long_term_prompt(memory_ctx.long_term)
        summary_block = self.memory.format_summary_prompt(memory_ctx.conversation_summary)
        base_system_prompt = self._resolve_system_prompt(
            payload=payload,
            agent=agent,
            enable_tools=enable_tools,
            long_term_block=long_term_block,
            summary_block=summary_block,
        )

        # Build LLM history from Redis buffer (last N), not full Postgres dump
        buffer_messages = [
            {"role": m.role, "content": m.content}
            for m in memory_ctx.short_term
            if m.role in {"user", "assistant"} and m.content.strip()
        ]

        # Open the execution trace before any LLM work so failures are still
        # recorded with a row rather than vanishing.
        traces = TraceService(self.db)
        tracker = ExecutionTracker(model_name=payload.model, pipeline=pipeline)
        execution = traces.start(
            user_id=user.id,
            project_id=payload.project_id,
            conversation_id=conversation.id,
            agent_id=payload.agent_id or (agent.id if agent else None),
            model_name=payload.model,
            pipeline=pipeline,
            prompt=payload.message,
        )
        yield _sse(
            {
                "type": "execution_meta",
                "execution_id": execution.id,
                "pipeline": pipeline,
                "status": "running",
            }
        )

        raw_llm = get_llm_service()
        llm = TrackingLLM(raw_llm, tracker)
        # Keep memory summarization off the chat execution's token ledger
        self.memory.llm = raw_llm
        assistant_chunks: list[str] = []
        turn_trace: dict[str, Any] = {
            "orchestra_steps": [],
            "retrieved_chunks": [],
            "graph_steps": [],
            "tools": [],
            "route": None,
        }
        open_steps: dict[str, StepRecord] = {}
        try:
            if enable_orchestra:
                kb_ids: list[int] = []
                if agent and getattr(agent, "knowledge_bases", None):
                    kb_ids = [kb.id for kb in agent.knowledge_bases]

                engine = OrchestraEngine(llm=llm, rag=self.rag, tools=self.tools)
                initial_state = {
                    "question": payload.message,
                    "system_prompt": base_system_prompt,
                    "model": payload.model,
                    "temperature": payload.temperature,
                    "knowledge_base_ids": kb_ids,
                    "messages": buffer_messages + [{"role": "user", "content": payload.message}],
                    "memory": {
                        "short_term_size": memory_ctx.memory_size,
                        "long_term": memory_ctx.long_term,
                        "redis_connected": memory_ctx.redis_connected,
                        "conversation_summary": memory_ctx.conversation_summary,
                    },
                    "retrieved_docs": [],
                    "current_agent": "",
                    "errors": [],
                    "execution_history": [],
                    "plan": "",
                    "research_notes": "",
                    "draft": "",
                    "review_notes": "",
                    "final_response": "",
                }

                final_answer = ""
                for event in engine.run(initial_state):
                    evt_type = event.get("type")
                    if evt_type == "orchestra_step":
                        agent_name = str(event.get("agent") or "agent")
                        status_name = str(event.get("status") or "done")
                        if status_name == "running":
                            open_steps[agent_name] = tracker.start_step(agent_name)
                        elif agent_name in open_steps:
                            tracker.end_step(
                                open_steps.pop(agent_name),
                                status="error" if status_name == "error" else "done",
                                detail={"summary": event.get("summary")},
                            )
                        turn_trace["orchestra_steps"].append(
                            {
                                "agent": event.get("agent"),
                                "status": event.get("status"),
                                "summary": event.get("summary"),
                                "route": event.get("route"),
                            }
                        )
                        if event.get("route"):
                            turn_trace["route"] = event.get("route")
                            route = str(event.get("route"))
                            tracker.pipeline = (
                                f"orchestra_{route}"
                                if route in {"simple", "full"}
                                else "orchestra"
                            )
                        yield _sse(event)
                    elif evt_type == "retrieved_context":
                        turn_trace["retrieved_chunks"] = event.get("chunks") or []
                        yield _sse(event)
                    elif evt_type == "orchestra_result":
                        final_answer = str(event.get("final_response") or "")
                        turn_trace["route"] = event.get("route") or turn_trace.get("route")
                        if event.get("review_notes"):
                            yield _sse(
                                {
                                    "type": "orchestra_step",
                                    "agent": "reviewer",
                                    "status": "done",
                                    "summary": "Review notes ready.",
                                    "review_notes": event.get("review_notes"),
                                    "route": event.get("route"),
                                }
                            )

                if not final_answer:
                    final_answer = "(No content returned by Orchestra.)"
                for token in _chunk_text(final_answer):
                    assistant_chunks.append(token)
                    yield _sse({"type": "token", "content": token})

            elif enable_tools:
                # Knowledge-base grounding applies on the tools path too, not just
                # the direct path — an agent with KBs retrieves either way.
                llm_messages = self._build_llm_messages(
                    base_system_prompt=base_system_prompt,
                    buffer_messages=buffer_messages,
                    user_message=payload.message,
                )
                yield from self._ground_with_knowledge(
                    agent=agent,
                    question=payload.message,
                    base_system_prompt=base_system_prompt,
                    llm_messages=llm_messages,
                    tracker=tracker,
                    turn_trace=turn_trace,
                )

                openai_tools = self.tools.openai_tools()
                final_answer = ""
                node_order = ["planner", "tool", "reviewer", "answer"]
                current_node_idx = 0
                yield _sse({"type": "graph_step", "node": node_order[0], "status": "running"})
                open_steps[node_order[0]] = tracker.start_step(node_order[0])

                graph = build_agent_graph(llm=llm, registry=self.tools)
                initial_state = {
                    "llm_messages": llm_messages,
                    "model": payload.model,
                    "temperature": payload.temperature,
                    "tools": openai_tools,
                    "enable_tools": True,
                }

                for update in graph.stream(initial_state, stream_mode="updates"):
                    for node_name, node_payload in update.items():
                        summary = _extract_graph_summary(node_payload, node_name)

                        while (
                            current_node_idx < len(node_order)
                            and node_order[current_node_idx] != node_name
                        ):
                            skipped = node_order[current_node_idx]
                            if skipped in open_steps:
                                tracker.end_step(open_steps.pop(skipped), status="done")
                            yield _sse(
                                {
                                    "type": "graph_step",
                                    "node": skipped,
                                    "status": "done",
                                }
                            )
                            current_node_idx += 1
                            if current_node_idx < len(node_order):
                                nxt = node_order[current_node_idx]
                                open_steps[nxt] = tracker.start_step(nxt)
                                yield _sse(
                                    {
                                        "type": "graph_step",
                                        "node": nxt,
                                        "status": "running",
                                    }
                                )

                        if node_name in open_steps:
                            tracker.end_step(
                                open_steps.pop(node_name),
                                status="done",
                                detail={"summary": summary},
                            )
                        yield _sse(
                            {
                                "type": "graph_step",
                                "node": node_name,
                                "status": "done",
                                "summary": summary,
                            }
                        )
                        turn_trace["graph_steps"].append(
                            {
                                "node": node_name,
                                "status": "done",
                                "summary": summary,
                            }
                        )
                        current_node_idx += 1
                        if current_node_idx < len(node_order):
                            nxt = node_order[current_node_idx]
                            open_steps[nxt] = tracker.start_step(nxt)
                            yield _sse(
                                {
                                    "type": "graph_step",
                                    "node": nxt,
                                    "status": "running",
                                }
                            )

                        for evt in node_payload.get("tool_events", []):
                            turn_trace["tools"].append(evt)
                            yield _sse(evt)

                        if node_payload.get("final_answer"):
                            final_answer = str(node_payload["final_answer"])

                for leftover in list(open_steps.values()):
                    tracker.end_step(leftover, status="done")
                open_steps.clear()

                if not final_answer:
                    final_answer = "(No content returned by the graph answer node.)"
                for token in _chunk_text(final_answer):
                    assistant_chunks.append(token)
                    yield _sse({"type": "token", "content": token})
            else:
                # Direct stream path with Redis memory buffer + optional RAG
                llm_messages = self._build_llm_messages(
                    base_system_prompt=base_system_prompt,
                    buffer_messages=buffer_messages,
                    user_message=payload.message,
                )
                yield from self._ground_with_knowledge(
                    agent=agent,
                    question=payload.message,
                    base_system_prompt=base_system_prompt,
                    llm_messages=llm_messages,
                    tracker=tracker,
                    turn_trace=turn_trace,
                )
                generate_step = tracker.start_step("generate")
                for token in llm.stream_chat_completion(
                    messages=llm_messages,
                    model=payload.model,
                    temperature=payload.temperature,
                ):
                    assistant_chunks.append(token)
                    yield _sse({"type": "token", "content": token})
                tracker.end_step(generate_step, status="done")
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail)
            for leftover in list(open_steps.values()):
                tracker.end_step(leftover, status="error")
            open_steps.clear()
            traces.complete(
                execution,
                tracker=tracker,
                final_response="",
                status="error",
                error_detail=detail,
                snapshot={
                    "system_prompt": base_system_prompt,
                    **{k: v for k, v in turn_trace.items() if v not in (None, [], {})},
                },
            )
            self._record_token_spend(user_id=user.id, tracker=tracker)
            yield _sse({"type": "error", "detail": detail})
            return
        except Exception as exc:  # noqa: BLE001
            detail = f"Chat pipeline error: {exc}"
            for leftover in list(open_steps.values()):
                tracker.end_step(leftover, status="error")
            open_steps.clear()
            traces.complete(
                execution,
                tracker=tracker,
                final_response="",
                status="error",
                error_detail=detail,
                snapshot={
                    "system_prompt": base_system_prompt,
                    **{k: v for k, v in turn_trace.items() if v not in (None, [], {})},
                },
            )
            self._record_token_spend(user_id=user.id, tracker=tracker)
            yield _sse({"type": "error", "detail": detail})
            return
        full_reply = "".join(assistant_chunks).strip()
        if not full_reply:
            full_reply = "(No content returned by the model.)"

        # Drop empty trace lists so DB stays lean
        cleaned_trace = {
            key: value
            for key, value in turn_trace.items()
            if value not in (None, [], {})
        } or None

        assistant_message = self.messages.create(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=full_reply,
                trace=cleaned_trace,
            )
        )
        conversation.updated_at = datetime.now(UTC)
        self.db.add(conversation)
        self.db.commit()

        tracker.update_snapshot(
            system_prompt=base_system_prompt,
            retrieved_chunks=turn_trace.get("retrieved_chunks") or [],
            tool_calls=turn_trace.get("tools") or [],
            orchestra_steps=turn_trace.get("orchestra_steps") or [],
            graph_steps=turn_trace.get("graph_steps") or [],
            route=turn_trace.get("route"),
        )
        traces.complete(
            execution,
            tracker=tracker,
            final_response=full_reply,
            message_id=assistant_message.id,
            status="completed",
            snapshot=tracker.snapshot,
        )
        self._record_token_spend(user_id=user.id, tracker=tracker)

        # Persist the completed turn into short-term memory, summarizing any
        # messages pushed out of the buffer.
        self.memory.remember_turn(
            conversation_id=conversation.id,
            user_id=user.id,
            user_content=payload.message,
            assistant_content=full_reply,
            model=payload.model,
        )
        updated_status = self.memory.get_status(
            user_id=user.id,
            conversation_id=conversation.id,
        )
        yield _sse(
            {
                "type": "memory_status",
                "redis_connected": updated_status.redis_connected,
                "session_active": updated_status.session_active,
                "conversation_id": conversation.id,
                "memory_size": updated_status.memory_size,
                "buffer_limit": updated_status.buffer_limit,
                "memory_used": updated_status.memory_used,
                "long_term_count": updated_status.long_term_count,
                "has_summary": updated_status.has_summary,
            }
        )

        yield _sse(
            {
                "type": "done",
                "message_id": assistant_message.id,
                "conversation_id": conversation.id,
                "execution_id": execution.id,
                "latency_ms": execution.latency_ms,
                "total_tokens": execution.total_tokens,
                "total_cost_usd": float(execution.total_cost_usd or 0),
            }
        )
    def _build_llm_messages(
        self,
        *,
        base_system_prompt: str,
        buffer_messages: list[dict[str, Any]],
        user_message: str,
    ) -> list[dict[str, Any]]:
        llm_messages: list[dict[str, Any]] = [
            {"role": "system", "content": base_system_prompt},
        ]
        for msg in buffer_messages:
            if msg.get("role") in {"user", "assistant"} and str(msg.get("content") or "").strip():
                llm_messages.append(
                    {"role": msg["role"], "content": str(msg["content"])}
                )
        llm_messages.append({"role": "user", "content": user_message})
        return llm_messages


def _extract_graph_summary(payload: dict[str, Any], node_name: str) -> str | None:
    events = payload.get("graph_events") or []
    for evt in events:
        if evt.get("node") == node_name:
            return evt.get("summary")
    return None


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
