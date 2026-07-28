# Orchestra — Product Requirements (PRD)

## Problem

Building production AI agents today is fragmented: prompts in one place, tools elsewhere, no shared project model, weak auth, and little operational scaffolding. Developers need a platform that owns the **full agent lifecycle**, not just a chat box.

## Product vision

Orchestra is an AI-native development platform — similar in role to how GitHub serves repositories — for designing, orchestrating, executing, evaluating, and managing intelligent agents.

## Goals

1. Learn production AI engineering by implementing it.
2. Ship a portfolio-worthy platform with modular, observable architecture.
3. Build incrementally: **platform first**, then AI runtime, knowledge, intelligence, production polish.

## Non-goals (Days 1–2)

- LangChain / LangGraph runtime
- RAG, embeddings, vector DB
- Tool calling, streaming, evaluation
- Multi-agent workflows
- Actual LLM execution (starts Day 3)

## Users

| Persona | Need |
|---------|------|
| AI engineer / learner | Workspace to grow agents over time |
| Portfolio reviewer | Clear architecture and running demo |
| Future team | Extensible API and Docker setup |

## Day 1 scope (done)

Monorepo, Docker, JWT auth, Projects CRUD, Login → Dashboard → Projects.

## Day 2 scope (must have)

| Feature | Requirement |
|---------|-------------|
| Agent model | Belongs to a project; name, prompt, model_name |
| Layered backend | Repository + Service + API |
| Agent CRUD API | POST/GET/PATCH/DELETE `/api/v1/agents` |
| Ownership rules | Only via owned projects; invalid project → error |
| UI | Dashboard project cards → Agent list → Create/Edit dialog |
| Docs | Architecture, Database, API, ADRs, Interview notes updated |

## Day 3 scope (must have)

| Feature | Requirement |
|---------|-------------|
| Conversations / Messages | Persisted under a project |
| OpenAI / Gemini integration | Chat Completions via Gemini |
| Streaming | SSE token stream to UI |
| Model selection | Multiple models selectable |
| System prompt | Default + optional agent prompt |
| Chat UI | Message list, input, history sidebar |
| Graceful errors | Missing/invalid API key handled |

## Success criteria (Day 2)

- User logs in and sees only their projects
- User creates / edits / deletes agents under a project
- Invalid JWT → 401
- Non-existent / foreign project_id → 404
- Invalid input → 422
- Flow: Login → Dashboard → Project → Agent list

## Success criteria (Day 3)

- User starts a conversation and sees streaming replies
- User + assistant messages stored in Postgres
- History reloads correctly
- Model + temperature selectable
- Missing API key returns a clear error (no silent hang)

## Day 4 scope (must have)

| Feature | Requirement |
|---------|-------------|
| Tool interface | name, description, JSON schema, execute |
| Tool registry | register / lookup / execute |
| Built-in tools | calculator (AST), weather (Open-Meteo + mock fallback), search (mock KB) |
| Tool-calling pipeline | LLM may request tools; results fed back; final answer with tools disabled |
| SSE + UI | Show tool name, running/complete status, then answer |
| Toggle | `enable_tools` on chat request / UI checkbox |
| Catalog API | `GET /api/v1/tools` |

## Success criteria (Day 4)

- Math questions invoke calculator and return correct numeric answers
- Weather questions return live Open-Meteo data (or graceful mock fallback)
- Search questions show tool cards then a grounded answer from mock knowledge
- Unknown / invalid tool inputs fail gracefully without crashing chat
- Disabling tools falls back to plain streaming chat
- No “Day N” labels in the product UI (docs only)

## Day 5 scope (done)

LangGraph workflow: planner → tool → reviewer → answer. SSE `graph_step` events + execution panel in chat UI.

## Day 6 scope (must have)

| Feature | Requirement |
|---------|-------------|
| Knowledge bases | CRUD under a project |
| Documents | Upload PDF, DOCX, TXT |
| Extraction | PyMuPDF / python-docx / plain text |
| Chunking | Fixed-size chunks with overlap |
| Embeddings | Local model (fastembed, 384-d) |
| Vector storage | pgvector in PostgreSQL |
| Metadata | Filename, chunk text, status in Postgres |
| UI | Knowledge Base page, upload, status, chunk inspector |
| No RAG yet | Ingestion only — no chat retrieval |

## Success criteria (Day 6)

- User creates a knowledge base and uploads a PDF
- Document moves from `processing` to `processed`
- Chunks and embeddings stored; chunk count visible in UI
- Clicking a document shows chunk previews for debugging
- Invalid file types rejected gracefully

## Out of scope until later days

See root `PLAN.md` (Days 7–10 + v2). Day 7 adds similarity search and RAG in chat.
