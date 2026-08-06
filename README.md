# Orchestra

**An AI engineering platform for building agents you can actually debug.** Design multi-agent pipelines, ground them in your own documents, give them memory — then inspect every run down to the token, the cost, and the millisecond, and replay it.

![Status](https://img.shields.io/badge/status-active-success)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688)
![Next.js](https://img.shields.io/badge/Next.js-15-black)
![Postgres](https://img.shields.io/badge/Postgres-pgvector-336791)

![Orchestra architecture](docs/architecture.png)

---

## Why it exists

Most agent projects stop at "the LLM replied." The hard part starts after that: *why* did it reply that way, which documents did it actually retrieve, how much did that cost, which stage was slow, and does the answer get worse when you edit a prompt?

Orchestra treats an agent run as a **first-class, inspectable object**. Every chat turn produces an `Execution` with timed steps, token counts, cost, retrieved chunks, and the exact prompt that was sent — persisted, searchable, and replayable.

---

## What it does

| Area | Capability |
|------|------------|
| **Multi-agent** | LangGraph pipeline — Planner → Research → Writer → Reviewer, with a fast-answer branch for simple questions |
| **Tool calling** | Schema-driven tool registry with a safe AST calculator, live weather, and a built-in reference index |
| **RAG** | Upload PDF/DOCX/TXT → extract → chunk → embed → retrieve from Postgres + pgvector |
| **Memory** | Redis short-term conversation buffer + durable user facts in Postgres |
| **Observability** | Per-step latency, tokens, and cost; searchable execution history; snapshot replay |
| **Platform** | JWT auth, projects, agents, knowledge bases, SSE streaming, Docker Compose |

### Two graphs, one endpoint

Orchestra runs two distinct LangGraph workflows behind the same chat API, selected per request:

- **Tools graph** — `planner → tool → reviewer → answer`. The planner decides whether a tool is warranted; the tool node executes against the registry.
- **Orchestra pipeline** — `planner → research → writer → reviewer`, with a conditional edge that routes short factual questions to a `fast_answer` node instead, skipping two LLM calls.

The routing decision, the agents that ran, and the ones that were skipped all appear live in the chat UI and are stored on the execution.

---

## Quick start

```bash
cp .env.example .env        # add GROQ_API_KEY (free) or GEMINI_API_KEY
cd docker
docker compose --env-file ../.env up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:13000 |
| API docs | http://localhost:18000/docs |
| Health | http://localhost:18000/health |

Ports default to `13000`/`18000` so they don't collide with anything already on `3000`/`8000`. Change them with `FRONTEND_PORT` / `BACKEND_PORT`.

Get a free Groq key at [console.groq.com/keys](https://console.groq.com/keys), or run fully offline with [Ollama](https://ollama.com) by setting `LLM_PROVIDER=ollama`.

<details>
<summary><b>Running without Docker</b></summary>

**Backend** — needs Python 3.12, Postgres with pgvector, and Redis.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend** — needs Node 20+.

```bash
cd frontend
npm install
npm run dev
```

Point `NEXT_PUBLIC_API_URL` at your backend origin.
</details>

---

## Architecture

```text
                          Next.js frontend
              landing · chat · knowledge · observability
                                 │
                         REST + SSE, JWT bearer
                                 │
                          FastAPI backend
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
   Orchestra pipeline      Tools graph            RAG + memory
   (multi-agent)           (LangGraph)            + tracing
          │                      │                      │
          └──────────┬───────────┴───────────┬──────────┘
                     │                       │
         Postgres + pgvector               Redis
    users · agents · chunks+embeddings   short-term
    executions · steps · memories        conversation buffer
                     │
           Groq · Gemini · Ollama
```

Vectors live in **Postgres via pgvector** — one database for relational data and embeddings, no separate vector store to operate.

The backend is layered `API router → service → repository → model`. Routers stay thin; business rules and ownership checks live in services. Ownership is enforced everywhere: a resource is reachable only through a project whose `owner_id` matches the authenticated user.

### Repository layout

```text
Orchestra/
├── backend/app/
│   ├── api/v1/          auth · projects · agents · chat · memory · observability
│   ├── agents/          Planner · Research · Writer · Reviewer · FastAnswer
│   ├── orchestrator/    OrchestraEngine, conditional routing, shared state
│   ├── graph/           tools LangGraph (planner → tool → reviewer → answer)
│   ├── prompts/         centralized system prompts, one module per role
│   ├── tools/           registry + calculator, weather, reference index
│   ├── knowledge/       upload → extract → chunk → embed → pgvector
│   ├── rag/             retrieval and grounded prompt construction
│   ├── memory/          Redis buffer + long-term fact extraction
│   ├── observability/   ExecutionLogger · TraceBuilder · TrackingLLM
│   ├── evaluation/      cost model, metrics, execution tracker, scorers
│   ├── repositories/    data access
│   ├── models/          SQLAlchemy ORM
│   ├── schemas/         Pydantic request/response contracts
│   └── services/        ChatService, pluggable LLM providers
├── frontend/src/app/    landing · login · dashboard · projects · chat · KB · observability
├── database/            init.sql (extensions)
├── docker/              docker-compose.yml
└── docs/                architecture diagram
```

---

## Configuration

| Variable | Used by | Notes |
|----------|---------|-------|
| `DATABASE_URL` | Backend | `postgresql+psycopg2://…` on a pgvector-enabled database |
| `REDIS_URL` | Backend | Short-term conversation memory |
| `JWT_SECRET` | Backend | Access-token signing key — **change this before deploying** |
| `CORS_ORIGINS` | Backend | Comma-separated frontend origins |
| `LLM_PROVIDER` | Backend | `groq` · `gemini` · `ollama` |
| `GROQ_API_KEY` | Backend | Free cloud inference |
| `GEMINI_API_KEY` | Backend | Google Gemini |
| `MEMORY_BUFFER_SIZE` | Backend | Turns kept before summarization (default 10) |
| `UPLOAD_DIR` | Backend | Knowledge base upload directory |
| `NEXT_PUBLIC_API_URL` | Frontend | Backend origin |
| `NEXT_PUBLIC_SITE_URL` | Frontend | Public frontend origin, for canonical URLs and link previews |

Complete list with comments: [.env.example](.env.example).

---

## API

Base path `/api/v1`. Authenticate with `Authorization: Bearer <token>`. Interactive docs at `/docs`.

| Area | Endpoints |
|------|-----------|
| Auth | `POST /auth/signup` · `POST /auth/login` · `GET /auth/me` |
| Projects & agents | CRUD under `/projects` and `/agents` |
| Chat | `POST /chat` (SSE) · conversations · messages · `GET /chat/models` · `GET /tools` |
| Knowledge | `/knowledge-bases` · document upload · chunks |
| Memory | `/memory/status` · preferences · conversation dump |
| Dashboard | `/dashboard/summary` · `/dashboard/metrics` |
| Executions | `GET /executions?project_id=&q=&status=&pipeline=&limit=` |
| Detail & replay | `GET /executions/{id}` · `POST /executions/{id}/rating` · `POST /executions/{id}/replay` |

### Streaming events

`POST /chat` returns `text/event-stream`. Event types:

`meta` · `user_message` · `memory_status` · `execution_meta` · `retrieved_context` · `tool_start` · `tool_result` · `graph_step` · `orchestra_step` · `token` · `done` · `error`

---

## Prompts

Agent system prompts are centralized under `backend/app/prompts/`, one module per role — `planner`, `research`, `writer`, `reviewer`, `fast_answer`, and a shared `system` module for the tool addendum and defaults. Behavior can be tuned there without touching graph wiring.

---

## Testing

```bash
cd backend
pytest tests/
```

The suite uses a deterministic LLM stub, so it runs with no API keys and no network.

---

## License

MIT.
