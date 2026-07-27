# Architecture — Days 1–4

## Principle

Days 1–2 built the platform (auth, projects, agents).  
Day 3 introduced LLM chat + SSE streaming.  
**Day 4 adds tool calling:** the model can request structured tool runs via a registry, then produce a grounded final answer.

## Day 4 architecture

```text
                User
                  │
           Next.js Chat
                  │
            POST /chat
                  │
               FastAPI
                  │
         LLM Chat Completions
                  │
        ┌─────────┴─────────┐
        │                   │
   Normal Response      Tool Call
                            │
                    Tool Registry
                            │
       ┌────────┬────────┬────────┐
       ▼        ▼        ▼
 Calculator  Weather   Search
   (AST)    (Open-Meteo) (mock KB)
       │
       ▼
 Tool Result → LLM (tools off) → Final Answer (SSE)
```

## Layers

| Layer | Day 4 pieces |
|-------|----------------|
| API | `api/v1/chat.py` — `/chat`, `/tools`, conversations |
| Service | `chat_service.py` tool loop; `openai_compatible_service.py` / `gemini_service.py` |
| Tools | `tools/base.py`, `registry.py`, `calculator.py`, `weather.py`, `search.py` |
| Repository | unchanged conversations/messages |
| Models | still `Conversation` / `Message` (user + assistant only) |

## Tool-calling data flow

1. User sends a message (`enable_tools=true` by default)  
2. FastAPI verifies JWT + project ownership  
3. Persist user message  
4. Build LLM payload: system (+ tool guidance) + history + `tools[]` schemas  
5. Non-streaming **decision round**: model returns text **or** `tool_calls`  
6. For each tool call (capped) → SSE `tool_start` → `ToolRegistry.execute` → SSE `tool_result`  
7. Append assistant tool-call + tool result messages to the in-memory transcript  
8. **Final answer pass with tools disabled** (stream tokens) — prevents infinite tool loops  
9. Persist assistant message; SSE `done`

## Built-in tools

| Tool | Implementation |
|------|----------------|
| `calculator` | Safe AST arithmetic (no `eval`) |
| `weather` | Live **Open-Meteo** (geocode city → lat/lon → current weather); mock fallback if offline |
| `search` | Mock Orchestra knowledge snippets (stand-in until RAG Days 6–7) |

## Why a Tool Registry?

Without it, chat code becomes `if tool == "weather"` forever.  
With it: register once, look up by name, execute. Adding a tool never changes the chat pipeline.

## SSE events (Day 4)

```text
meta | user_message | tool_start | tool_result | token | done | error
```

## What Day 4 does **not** change

- Auth / projects / agents CRUD  
- Conversation + message persistence model (ADR-011 still holds)  
- No new DB tables for tools (ADR-013: live SSE only)  
- Redis still unused for memory (Day 8)  
- Frontend UI does not show “Day N” labels (product copy only)
