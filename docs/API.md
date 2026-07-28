# API Contracts — Days 1–6

Base URL (Docker defaults on this machine): `http://localhost:18000`  
API prefix: `/api/v1`  
Interactive docs: `/docs`

Auth header for protected routes:

```http
Authorization: Bearer <access_token>
```

---

## Health

### `GET /health`

**Response 200**

```json
{ "status": "ok" }
```

---

## Auth

### `POST /api/v1/auth/signup`

**Body**

```json
{
  "email": "ada@example.com",
  "password": "password123",
  "full_name": "Ada Lovelace"
}
```

**Response 201**

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "ada@example.com",
    "full_name": "Ada Lovelace",
    "created_at": "2026-07-26T12:00:00Z"
  }
}
```

### `POST /api/v1/auth/login`

**Body**

```json
{ "email": "ada@example.com", "password": "password123" }
```

**Response 200** — same shape as signup.

**Errors**: `401` invalid credentials; `400` email already registered (signup).

### `GET /api/v1/auth/me`

**Auth required** — **Response 200** `UserOut`

---

## Projects

All project routes require Bearer JWT. Scoped to current user.

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/v1/projects` | Create |
| GET | `/api/v1/projects` | List own |
| GET | `/api/v1/projects/{id}` | Get one |
| PATCH | `/api/v1/projects/{id}` | Update |
| DELETE | `/api/v1/projects/{id}` | Delete (204) |

**POST body**

```json
{ "name": "Support bots", "description": "Workspace" }
```

---

## Agents (Day 2)

All agent routes require Bearer JWT. Access is authorized via project ownership.

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/v1/agents` | Create |
| GET | `/api/v1/agents` | List (optional `?project_id=`) |
| GET | `/api/v1/agents/{id}` | Get one |
| PATCH | `/api/v1/agents/{id}` | Update |
| DELETE | `/api/v1/agents/{id}` | Delete (204) |

### `POST /api/v1/agents`

```json
{
  "name": "Research assistant",
  "project_id": 1,
  "description": "Finds sources",
  "system_prompt": "You are a careful researcher.",
  "model_name": "llama-3.1-8b-instant"
}
```

**Response 201** — `AgentResponse`

**Errors**
- `401` missing/invalid JWT
- `404` project not found or not owned
- `422` validation (missing name, invalid types)

### `GET /api/v1/agents?project_id=1`

Filter to one project. Without query — all agents across the user’s projects.

### `PATCH /api/v1/agents/{id}`

```json
{
  "name": "Updated name",
  "system_prompt": "New instructions",
  "model_name": "llama-3.1-8b-instant"
}
```

### `DELETE /api/v1/agents/{id}`

**204** No Content

---

## Chat & Conversations (Day 3+)

### `GET /api/v1/chat/models`

Returns supported models for the active provider and whether it is configured.

```json
{
  "models": [
    { "id": "llama-3.1-8b-instant", "label": "Llama 3.1 8B (Groq)", "description": "..." }
  ],
  "gemini_configured": true,
  "llm_configured": true,
  "provider": "groq"
}
```

### `POST /api/v1/chat` (streaming)

**Auth required.** Returns `text/event-stream` (SSE).

**Body**

```json
{
  "project_id": 1,
  "message": "What is 24 * 18?",
  "conversation_id": null,
  "agent_id": null,
  "model": "llama-3.1-8b-instant",
  "temperature": 0.2,
  "system_prompt": null,
  "enable_tools": true
}
```

**SSE event types:** `meta`, `user_message`, `tool_start`, `tool_result`, `graph_step`, `token`, `done`, `error`

Example tool events:

```json
{ "type": "tool_start", "tool_call_id": "call_abc", "tool_name": "calculator", "arguments": "{\"expression\":\"24*18\"}", "status": "running" }
{ "type": "tool_result", "tool_call_id": "call_abc", "tool_name": "calculator", "status": "complete", "result": "432" }
```

Example LangGraph event:

```json
{ "type": "graph_step", "node": "planner", "status": "done", "summary": "Planned 1 tool call(s)." }
```

---

## Tools (Day 4)

### `GET /api/v1/tools`

**Auth required.** Lists the Tool Registry catalog.

```json
{
  "count": 3,
  "tools": [
    {
      "name": "calculator",
      "description": "...",
      "parameters": {
        "type": "object",
        "properties": { "expression": { "type": "string" } }
      }
    }
  ]
}
```

Built-in tools:

| Name | Behavior |
|------|----------|
| `calculator` | Safe AST math |
| `weather` | Open-Meteo live weather (geocode + current); mock fallback offline |
| `search` | Mock Orchestra knowledge snippets |

### Conversations

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/v1/conversations` | Create empty conversation |
| GET | `/api/v1/conversations?project_id=` | List for project |
| GET | `/api/v1/conversations/{id}` | Get one |
| PATCH | `/api/v1/conversations/{id}` | Update title/model/agent |
| DELETE | `/api/v1/conversations/{id}` | Delete (204) |
| GET | `/api/v1/conversations/{id}/messages` | Message history |

**Errors**
- `401` invalid JWT
- `404` project/conversation not owned
- `503` provider credentials missing
- Provider auth/quota / tool errors surfaced in SSE `error` or `tool_result`

---

## Knowledge Base (Day 6)

Ingestion only — upload, extract, chunk, embed, store. **No RAG query yet.**

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/v1/knowledge-bases?project_id=` | List knowledge bases |
| POST | `/api/v1/knowledge-bases` | Create |
| GET | `/api/v1/knowledge-bases/{id}` | Get one |
| PATCH | `/api/v1/knowledge-bases/{id}` | Update name/description |
| DELETE | `/api/v1/knowledge-bases/{id}` | Delete (204) |
| GET | `/api/v1/knowledge-bases/{id}/documents` | List documents |
| POST | `/api/v1/knowledge-bases/{id}/documents` | Upload file (multipart) |
| GET | `/api/v1/documents/{id}` | Get document status |
| GET | `/api/v1/documents/{id}/chunks` | List chunks (debug UI) |
| DELETE | `/api/v1/documents/{id}` | Delete document (204) |

### `POST /api/v1/knowledge-bases`

```json
{
  "project_id": 1,
  "name": "Research Papers",
  "description": "AI and systems papers"
}
```

### `POST /api/v1/knowledge-bases/{id}/documents`

**Content-Type:** `multipart/form-data`  
**Field:** `file` — PDF, DOCX, or TXT (max 20 MB)

**Response 201** — `DocumentResponse`

```json
{
  "id": 1,
  "knowledge_base_id": 1,
  "filename": "AI.pdf",
  "content_type": "application/pdf",
  "status": "processing",
  "chunk_count": 0,
  "embedding_status": "pending",
  "error_message": null,
  "created_at": "2026-07-28T12:00:00Z",
  "updated_at": "2026-07-28T12:00:00Z"
}
```

Processing runs in the background. Poll `GET /documents/{id}` or list documents until `status` is `processed` or `failed`.

### `GET /api/v1/documents/{id}/chunks`

```json
[
  {
    "id": 1,
    "document_id": 1,
    "chunk_index": 0,
    "content": "First chunk text...",
    "metadata": { "unit_start": 0, "unit_end": 5, "token_count": 392 },
    "created_at": "2026-07-28T12:00:05Z"
  }
]
```

**Errors**
- `400` unsupported file type or file too large
- `401` invalid JWT
- `404` project/knowledge base/document not owned

---

## JWT claims

| Claim | Meaning |
|-------|---------|
| `sub` | User id (string) |
| `email` | User email |
| `exp` | Expiry (UTC) |
