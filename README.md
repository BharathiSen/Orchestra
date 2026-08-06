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

## Development checks

```bash
cd backend
pytest tests/                 # deterministic LLM stub — no API keys, no network

cd ../frontend
npm run lint                  # ESLint (flat config, next/core-web-vitals)
npm run typecheck             # tsc --noEmit
npm run build                 # production build
```

CI runs all of the above plus both Docker image builds, and asserts that the
backend refuses to start in production with a default signing key.

> If `npm install` silently drops devDependencies, check for a global
> `NODE_ENV=production` — npm omits dev packages when it is set.

---

## Deployment

### Topology

Four processes, two data stores. Only the backend talks to Postgres and Redis.

```text
  Browser ──HTTPS──► Next.js frontend ──REST + SSE──► FastAPI backend ──┬──► Postgres 16 + pgvector
                                                                        ├──► Redis 7
                                                                        └──► Groq / Gemini / Ollama
```

| Piece | Suggested host | Notes |
|-------|----------------|-------|
| Frontend | Vercel | Root directory `frontend/`; zero config for Next.js 15 |
| Backend | Railway · Render · Fly.io | Needs a persistent disk only if you keep uploaded originals |
| Postgres + pgvector | Neon | Enable the `vector` extension on the database |
| Redis | Upstash | The TLS `rediss://` URL works directly |
| LLM | Groq or Gemini | Groq's free tier is enough for a demo |

`DATABASE_URL` must use the `postgresql+psycopg2://` scheme — managed providers hand you a `postgres://` URL, which SQLAlchemy cannot resolve a driver for.

### Self-hosting

```bash
cp .env.example .env      # then set the required values below
cd docker
docker compose -f docker-compose.prod.yml --env-file ../.env up -d --build
```

The production compose file builds real images: a compiled Next.js bundle rather than a dev server, both containers running as non-root, no bind mounts, healthchecks and restart policies, and no published Postgres or Redis ports.

### Required configuration

`ENVIRONMENT=production` makes the backend validate its own configuration at startup and **refuse to boot** rather than run in a known-unsafe state:

| Refuses to start when | Because |
|---|---|
| `JWT_SECRET` is the value from `.env.example` | Anyone who read this repository could forge tokens for any account |
| `JWT_SECRET` is under 32 characters | Brute-forceable |
| `DATABASE_URL` uses a well-known password (`orchestra`, `postgres`, …) | Ships as a default in this repo and every tutorial |
| The selected `LLM_PROVIDER` has no API key | Chat would 503 on every request |

Generate a signing key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Also set `CORS_ORIGINS` and `NEXT_PUBLIC_API_URL` to real origins, and `ALLOWED_HOSTS` to your backend hostname. `CORS_ORIGINS` is compared literally — no wildcards, no trailing slashes. A mismatch shows up as a browser CORS error on every authenticated call while `/health` still answers from a terminal; that asymmetry is the signature.

### Health checks

| Endpoint | Purpose |
|---|---|
| `/health/live` | Liveness. Checks nothing external — a database outage should not restart the app container |
| `/health/ready` | Readiness. Runs `SELECT 1` and pings Redis, returning **503** when a dependency is down so the platform drains traffic instead of routing it into failures |

### Rate limiting

The chat endpoint is metered on three axes, because any one alone leaves a hole:

| Limit | Default | Stops |
|---|---|---|
| Requests per minute, per user | 10 | Scripted hammering |
| Concurrent streams, per user | 3 | Many simultaneous 30-second pipelines from one account |
| Daily token budget, per user | 200,000 | The actual spend, which the other two do not bound |

Signup is capped at 5 per hour per IP. Counters live in Redis. In production, an unreachable Redis makes chat fail **closed** — an unmetered LLM endpoint is a bigger problem than a brief outage, and `/health/ready` reports the instance as unready anyway. Locally it fails open, so Redis stays optional.

Exceeded limits return `429` with `Retry-After`.

### Demo workspace

```bash
cd backend
python scripts/seed_demo.py
```

Creates a shared account with a project, two agents, a small knowledge base, and 20 executions spread across pipelines — so the dashboard and observability screens have real data. Idempotent; `--reset` rebuilds, `--skip-embeddings` avoids the model download.

Set `DEMO_EMAIL` on the backend and `NEXT_PUBLIC_DEMO_EMAIL` / `NEXT_PUBLIC_DEMO_PASSWORD` on the frontend to surface a "Try the demo" button on the landing page and a banner while signed in as that account. Leave them blank and every demo affordance disappears. Those frontend values are compiled into the public bundle by design — only ever point them at a throwaway account.

---

## License

MIT.
