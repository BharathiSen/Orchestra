# Architecture — Days 1–3

## Principle

Days 1–2 built the platform (auth, projects, agents).  
**Day 3 introduces the first LLM runtime:** chat completions, streaming, and persisted conversation history.

## Day 3 architecture

```text
                User
                  │
          Next.js Chat UI
                  │
            POST /api/v1/chat
                  │
               FastAPI
        ┌─────────┴─────────┐
        ▼                   ▼
 Save Conversation      Gemini API
        │                   │
 PostgreSQL          Gemini Model (stream)
        │                   │
        └─────────┬─────────┘
                  ▼
          SSE token stream
                  │
          Next.js updates UI
```

## Layers (unchanged pattern)

| Layer | Day 3 pieces |
|-------|----------------|
| API | `api/v1/chat.py` — `/chat`, `/conversations`, `/chat/models` |
| Service | `chat_service.py` (ownership + orchestration), `gemini_service.py` (LLM client) |
| Repository | `chat_repository.py` — conversations + messages SQL |
| Models | `Conversation`, `Message` |

## Chat data flow

1. User sends a message from the Chat UI  
2. FastAPI verifies JWT and project ownership  
3. Create or load `Conversation`  
4. Persist **user** `Message`  
5. Build Gemini payload: system instruction + history (`user`/`model` roles)  
6. Stream tokens via **SSE** (`text/event-stream`)  
7. Persist **assistant** `Message`  
8. Frontend reloads history from Postgres  

## System prompt resolution (priority)

1. Request `system_prompt` override  
2. Selected Agent’s `system_prompt`  
3. Platform default (`DEFAULT_SYSTEM_PROMPT` / settings)

## Streaming protocol (SSE)

```text
data: {"type":"meta","conversation_id":1,"title":"..."}
data: {"type":"user_message",...}
data: {"type":"token","content":"Hel"}
data: {"type":"token","content":"lo"}
data: {"type":"done","message_id":2,"conversation_id":1}
data: {"type":"error","detail":"..."}   # on failure
```

## What Day 3 does **not** change

- Auth, projects, agents CRUD remain as Day 1–2  
- Redis still unused for chat (memory comes later)
