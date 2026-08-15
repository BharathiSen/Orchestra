<div align="center">

# Orchestra

### Build AI agents you can actually debug.

Design multi-agent pipelines, ground them in your own documents, give them memory —
then inspect every run down to the token, the cost, and the millisecond, and replay it.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-1C3C3C)](https://langchain-ai.github.io/langgraph/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20+%20pgvector-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)

**[Live demo](https://orchestra.bharathis-ece2023.workers.dev/)** · [Quick start](#-installation) · [Architecture](#-architecture) · [Roadmap](#-future-roadmap)

</div>

---

## Overview

Most agent projects stop at *"the LLM replied."* The hard part starts after that:

> Why did it reply that way? Which documents did it actually retrieve? How much did
> that cost? Which stage was slow? Does the answer get worse when I edit a prompt?

Orchestra treats an agent run as a **first-class, inspectable object**. Every chat
turn produces an `Execution` with timed steps, token counts, cost, retrieved
chunks, and the exact prompt that was sent — persisted, searchable, and replayable.

It is a full-stack platform, not a notebook: JWT auth, projects, agents, knowledge
bases, streaming chat, and an observability surface, running on FastAPI and
Next.js.

### Try it without installing anything

The [live demo](https://orchestra.bharathis-ece2023.workers.dev/) has a shared
account with a seeded workspace — two agents, a knowledge base, and 20 traced
executions across four pipelines.

```
email:    demo@orchestra.dev
password: orchestra-demo
```

> Shared workspace. Anything you create is visible to others and may be reset.

---

## ✨ Key Features

| | Feature | What it actually does |
|---|---|---|
| 🕸️ | **Two LangGraph workflows** | A tools graph (`planner → tool → reviewer → answer`) and a multi-agent pipeline (`planner → research → writer → reviewer`), selected per request |
| 🔀 | **Conditional routing** | Short factual questions take a `fast_answer` branch that skips two LLM calls; comparison and writing tasks take the full pipeline |
| 🔧 | **Schema-driven tools** | A registry with a safe AST calculator (never `eval`), live weather via Open-Meteo, and a built-in reference index |
| 📚 | **RAG on pgvector** | Upload PDF/DOCX/TXT → extract → chunk → embed (BGE-small, 384-d) → retrieve, all inside PostgreSQL |
| 🧠 | **Two-tier memory** | Redis rolling conversation buffer with summarization on overflow, plus durable user facts in Postgres that persist across conversations |
| 🔬 | **Execution tracing** | Per-step latency, tokens, and cost for every run — searchable, filterable, with a snapshot for replay |
| ⏪ | **Replay** | Re-run a stored prompt with its original pipeline flags to compare behaviour |
| 🚦 | **Three-axis rate limiting** | Requests per minute, concurrent streams, and a daily token budget — because none of the three bounds the others |
| 📡 | **SSE streaming** | Real provider token streaming on the direct and both Orchestra routes, with live agent-step events, rendered as Markdown with tables and syntax-highlighted code *(the tools path buffers — see [roadmap](#-future-roadmap))* |
| 🧪 | **Tested behaviour** | 90 backend integration tests covering auth, ownership isolation, the SSE contract, all three pipelines, every rate limit, and the pgvector query — run in CI against real Postgres and Redis |

---

## 🤔 Why Orchestra?

Most agent frameworks give you orchestration. Most chat UIs give you a text box.
Orchestra is built around the part that is usually missing: **knowing what your
agent actually did.**

<table>
<tr><th align="left">Typical agent demo</th><th align="left">Orchestra</th></tr>
<tr><td>A reply appears</td><td>A reply appears <em>and</em> a row is written recording every stage that produced it</td></tr>
<tr><td>"It used RAG"</td><td>The exact chunks, their similarity scores, and the source document are attached to the turn</td></tr>
<tr><td>Cost is a monthly invoice</td><td>Cost is attributed per step, per turn, per project</td></tr>
<tr><td>Prompt changes are vibes</td><td>Every run is stored with its prompt and can be replayed against a new one</td></tr>
<tr><td>One code path</td><td>Three pipelines — direct, tools, multi-agent — chosen per request and labelled on every execution</td></tr>
</table>

### Design principles

- **The LLM client is wrapped, not the call sites.** `TrackingLLM` decorates
  whichever provider is active, so every call anywhere in the pipeline is
  measured. Instrumentation cannot be forgotten at a new call site.
- **One database for relational data and vectors.** Embeddings live in
  `document_chunks.embedding` as a `vector(384)` column. One system to operate,
  and retrieval joins directly against document metadata.
- **Prompts are a library, not inline strings.** Every system prompt lives in
  `app/prompts/`, one module per role.
- **Degrade, don't die.** Redis down means memory degrades, not that chat fails.
  Retrieval failure means an ungrounded answer, not a 500.

---

## 🏗 Architecture

![Orchestra architecture](docs/architecture.png)

```
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

<details>
<summary><b>Backend layering</b></summary>

```
API router  →  Service  →  Repository  →  Model
```

| Layer | Responsibility | Example |
|---|---|---|
| API | Validate, delegate, serialize. No business rules. | `api/v1/chat.py` |
| Service | Business rules, ownership, orchestration | `services/chat_service.py` |
| Repository | Data access | `repositories/chat_repository.py` |
| Model | SQLAlchemy ORM | `models/execution.py` |
| Schema | Request/response contracts | `schemas/chat.py` |

Ownership is enforced in the service layer: a resource is reachable only through
a project whose `owner_id` matches the authenticated user.

</details>

<details>
<summary><b>Data model</b></summary>

```
User 1──<N Project 1──<N Agent
                  │            └──<N>── KnowledgeBase   (many-to-many)
                  │
                  ├──<N Conversation 1──<N Message      (optional trace JSON)
                  │
                  ├──<N KnowledgeBase 1──<N Document 1──<N DocumentChunk
                  │                                          embedding vector(384)
                  │
                  └──<N Execution 1──<N ExecutionStep
```

Long-term user facts hang off `User` rather than a project — preferences follow
the person across projects.

</details>

---

## 🛠 Tech Stack

<table>
<tr><td valign="top">

**Backend**
- Python 3.12
- FastAPI 0.115 + Uvicorn
- SQLAlchemy 2.0
- LangGraph 0.2
- Pydantic 2.10 / pydantic-settings
- fastembed 0.5 (BAAI/bge-small-en-v1.5)
- PyMuPDF · python-docx

</td><td valign="top">

**Frontend**
- Next.js 15 (App Router)
- React 19 · TypeScript 5.7
- Tailwind CSS 3.4
- react-markdown 9 + remark-gfm
- GSAP (landing animation)

</td><td valign="top">

**Data & Infra**
- PostgreSQL 16 + pgvector
- Redis 7
- Docker Compose
- Cloudflare Workers (OpenNext)
- Render · Neon · Upstash

</td></tr>
</table>

**LLM providers:** Groq, Google Gemini, or Ollama — selected with one env var, all
behind a single `complete_chat` interface.

---

## 📁 Folder Structure

<details>
<summary><b>Expand</b></summary>

```
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
│   ├── core/            config · database · redis · limiter · middleware
│   ├── repositories/    data access
│   ├── models/          SQLAlchemy ORM
│   ├── schemas/         Pydantic contracts
│   └── services/        ChatService, pluggable LLM providers
├── backend/scripts/     seed_demo.py
├── frontend/src/app/    landing · login · dashboard · projects · chat · KB · observability
├── database/            init.sql (extensions)
├── docker/              docker-compose.yml · docker-compose.prod.yml
└── docs/                architecture diagram
```

</details>

---

## 🧠 AI Workflow

Two graphs run behind the same `POST /chat` endpoint, selected per request.
`enable_orchestra` wins when both flags are set.

### Tools graph

```
planner ──► tool ──► reviewer ──► answer
```

| Node | Behaviour |
|---|---|
| `planner` | Decides whether tools are warranted. A heuristic gate short-circuits generic writing prompts so they skip low-value tool calls. |
| `tool` | Executes each requested call against the registry, capped at three per turn. |
| `reviewer` | Reviews tool output. Skipped when no tools ran. |
| `answer` | Produces the final answer. Falls back to general knowledge when search returns nothing. |

### Orchestra pipeline

```
                        ┌─► writer ──► reviewer ──► END      (full route)
planner ──► research ───┤
                        └─► fast_answer ──────────► END      (simple route)
```

The branch after `research` is a conditional edge driven by `classify_route`.
Agents share a single `OrchestraState`; each returns a partial update plus an
`execution_history` entry, which becomes both a live `orchestra_step` event and a
timed row on the execution record.

<details>
<summary><b>SSE event contract</b></summary>

| Event | Meaning |
|---|---|
| `meta` | Conversation id and title |
| `user_message` | The persisted user turn |
| `memory_status` | Redis connectivity, buffer size, long-term fact count |
| `execution_meta` | Execution id, assigned before work begins |
| `retrieved_context` | Retrieved chunks with scores and source documents |
| `tool_start` / `tool_result` | Tool invocation and output |
| `graph_step` | Tools graph node progress |
| `orchestra_step` | Multi-agent progress, including the chosen route |
| `token` | A fragment of the answer |
| `done` | Message id, execution id, latency, tokens, cost |
| `error` | Failure detail |

</details>

---

## 🚀 Installation

### Prerequisites

Docker and Docker Compose, plus a free [Groq API key](https://console.groq.com/keys).
Or run entirely offline with [Ollama](https://ollama.com).

### Quick start

```bash
git clone https://github.com/BharathiSen/Orchestra.git
cd Orchestra
cp .env.example .env          # add GROQ_API_KEY
cd docker
docker compose --env-file ../.env up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:13000 |
| API docs | http://localhost:18000/docs |
| Health | http://localhost:18000/health/ready |

Ports default to `13000`/`18000` so they don't collide with anything on `3000`/`8000`.

<details>
<summary><b>Running without Docker</b></summary>

Requires Python 3.12, Node 20+, PostgreSQL with pgvector, and Redis.

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

Point `NEXT_PUBLIC_API_URL` at your backend origin.

> If `npm install` silently drops devDependencies, check for a global
> `NODE_ENV=production` — npm omits dev packages when it is set.

</details>

<details>
<summary><b>Seed a demo workspace</b></summary>

```bash
cd backend
python scripts/seed_demo.py
```

Creates a shared account with a project, two agents, a knowledge base with real
embeddings, and 20 executions across four pipelines — so the dashboard and
observability screens have data. Idempotent; `--reset` rebuilds,
`--skip-embeddings` avoids the model download.

</details>

---

## ⚙️ Environment Variables

| Variable | Used by | Notes |
|---|---|---|
| `ENVIRONMENT` | Backend | `development` \| `production`. Production makes config problems fatal at boot |
| `DATABASE_URL` | Backend | `postgresql+psycopg2://…` on a pgvector-enabled database |
| `REDIS_URL` | Backend | Short-term memory and rate-limit counters |
| `JWT_SECRET` | Backend | Signing key — **change before deploying** |
| `CORS_ORIGINS` | Backend | Comma-separated frontend origins, compared literally |
| `ALLOWED_HOSTS` | Backend | Host header allow-list; `*` disables the check |
| `LLM_PROVIDER` | Backend | `groq` \| `gemini` \| `ollama` |
| `GROQ_API_KEY` / `GEMINI_API_KEY` | Backend | Provider credentials |
| `NEXT_PUBLIC_API_URL` | Frontend | Backend origin. **Inlined at build time** |
| `NEXT_PUBLIC_SITE_URL` | Frontend | Public frontend origin |

<details>
<summary><b>Tuning and limits</b></summary>

| Variable | Default | Purpose |
|---|---|---|
| `MEMORY_BUFFER_SIZE` | `10` | Turns kept before summarization |
| `RATE_LIMIT_ENABLED` | `true` | Master switch for all limits |
| `CHAT_RATE_LIMIT_PER_MINUTE` | `10` | Per-user request rate |
| `CHAT_MAX_CONCURRENT_STREAMS` | `3` | Simultaneous streams per user |
| `CHAT_DAILY_TOKEN_BUDGET` | `200000` | Per-user daily spend bound |
| `SIGNUP_RATE_LIMIT_PER_HOUR` | `5` | Per IP |
| `MAX_REQUEST_BYTES` | `26214400` | Request body cap (25 MB) |
| `LLM_REQUEST_TIMEOUT_SECONDS` | `60` | Per provider call |
| `LLM_MAX_RETRIES` | `3` | Retry budget on rate-limit responses |
| `EMBEDDING_WARMUP_ENABLED` | `true` | Load the embedding model at startup |
| `UPLOAD_DIR` | `/data/uploads` | Outside `/app` so the dev bind mount can't shadow it |

Full list with commentary: [.env.example](.env.example).

</details>

---

## 🐳 Running with Docker

Two compose files, with different intent.

```bash
# Development — source bind-mounted, both servers in watch mode
cd docker
docker compose --env-file ../.env up --build

# Production shape — compiled frontend, no bind mounts, non-root, healthchecks
docker compose -f docker-compose.prod.yml --env-file ../.env up -d --build
```

<details>
<summary><b>What the production compose changes</b></summary>

- Frontend serves a compiled Next.js standalone bundle, not a dev server
- No bind mounts — images are immutable build artifacts
- Postgres and Redis publish **no host ports**; reachable only on the compose network
- `ENVIRONMENT=production`, so startup validation is fatal and rate limiting fails closed
- `restart: unless-stopped` and memory limits
- `${VAR:?}` guards refuse to start without real configuration

Both images are multi-stage and run as an unprivileged user (uid 1001). The
development stack binds Postgres to `127.0.0.1:15432` — loopback only, and off
the default port so it cannot collide with another Postgres.

</details>

---

## ☁️ Deployment

Four processes, two data stores. Only the backend talks to Postgres and Redis.

```
Browser ──HTTPS──► Next.js frontend ──REST + SSE──► FastAPI backend ──┬──► Postgres 16 + pgvector
                                                                      ├──► Redis 7
                                                                      └──► Groq / Gemini / Ollama
```

| Piece | Host used | Notes |
|---|---|---|
| Frontend | Cloudflare Workers (OpenNext) | `npm run deploy` |
| Backend | Render | Auto-deploys from `main` |
| Postgres + pgvector | Neon | Enable the `vector` extension |
| Redis | Upstash | The TLS `rediss://` URL works directly |

<details>
<summary><b>Production configuration gotchas</b></summary>

**`DATABASE_URL` must use `postgresql+psycopg2://`.** Managed providers hand you a
`postgres://` URL, which SQLAlchemy cannot resolve a driver for.

**`NEXT_PUBLIC_*` is inlined at build time.** Changing one requires a rebuild, not
a restart.

**`CORS_ORIGINS` is compared literally** — no wildcards, no trailing slashes. A
mismatch shows up as a browser CORS error on every authenticated call while
`/health` still answers from a terminal.

**If a reverse proxy buffers responses, chat appears frozen.** The backend already
sends `X-Accel-Buffering: no`; disable buffering for the chat endpoint.

**`ENVIRONMENT=production` refuses to boot** with the default signing key, a key
under 32 characters, a well-known database password, or a missing LLM key.

</details>

<details>
<summary><b>Health endpoints</b></summary>

| Endpoint | Purpose |
|---|---|
| `/health/live` | Liveness. Checks nothing external — a database outage should not restart the app container |
| `/health/ready` | Readiness. Runs `SELECT 1` and pings Redis, returning **503** when a dependency is down so the platform drains traffic |

</details>

---

## 🧩 Engineering Decisions

<details open>
<summary><b>pgvector instead of a dedicated vector database</b></summary>

One database holds relational data and embeddings. Retrieval joins directly
against document and knowledge-base metadata, there is one system to back up, and
there is no second consistency boundary. Revisit only when scale demands it.

</details>

<details>
<summary><b>Server-sent events instead of WebSockets</b></summary>

Chat is a one-way stream of tokens and progress events from server to browser.
SSE provides that over plain HTTP with automatic reconnection and no additional
protocol. A bidirectional channel would be unused complexity.

</details>

<details>
<summary><b>Rate limiting as dependencies, not middleware</b></summary>

Middleware runs before routing and authentication, so it cannot see the current
user without decoding the JWT a second time. FastAPI dependencies compose with
`get_current_user` and get the user for free.

The concurrency slot is acquired in the route rather than a dependency, because
it must be released when the *stream* ends — long after a dependency returns.
It is released in a `finally`, which also catches `GeneratorExit`, so a user who
navigates away mid-answer does not leak a slot.

</details>

<details>
<summary><b>Rate limiting fails closed in production, open in development</b></summary>

If Redis is unreachable nothing can be metered. An unmetered LLM endpoint on a
public URL is worse than a brief outage — and it is coherent with the readiness
probe, which also checks Redis, so the instance is drained anyway. Locally it
fails open, keeping Redis optional.

</details>

<details>
<summary><b>Selective gzip — the SSE path is excluded</b></summary>

Compressing `text/event-stream` makes the compressor hold bytes back waiting for
a worthwhile block, which is indistinguishable from a hung request. Small JSON
responses are where compression pays; the streaming route opts out entirely.

</details>

<details>
<summary><b>Embedding model warm-up at startup</b></summary>

`fastembed` loads lazily on first use. On a host that spins down when idle, that
means a visitor's first grounded question pays the full download-and-initialize
cost. The lifespan loads the model **and issues one throwaway embed**, because
constructing `TextEmbedding` does not build the ONNX inference session.

</details>

<details>
<summary><b>Dynamic viewport units for mobile</b></summary>

`100vh` on iOS Safari and Chrome Android measures the viewport *including* the
collapsing URL bar, so anything pinned to the bottom sits below the fold. The
layout uses `dvh`, with `vh` retained as the fallback line beneath it.

</details>

---

## 🔒 Production Features

| Area | Implementation |
|---|---|
| **Startup validation** | Production refuses to boot with a default or short `JWT_SECRET`, a well-known database password, or a missing LLM key |
| **Rate limiting** | Per-minute requests, concurrent streams, daily token budget, and signup-per-IP — Redis-backed |
| **Security headers** | HSTS, CSP, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` on both origins |
| **Request limits** | Body-size cap checked by `Content-Length` and by counting streamed bytes |
| **Host validation** | `TrustedHostMiddleware` when `ALLOWED_HOSTS` is configured |
| **Ownership** | Every project-scoped resource is reachable only by its owner; unauthorized access returns 404, not 403 |
| **Health probes** | Split liveness and readiness, with 503 on dependency failure |
| **Containers** | Multi-stage builds, non-root user, `HEALTHCHECK`, secrets excluded from build context |
| **Testing** | 90 backend integration tests against real Postgres + Redis service containers, with a stubbed LLM so no test makes a network call. Ownership, rate limits, the SSE event contract, all three pipelines, the retrieval trust boundary, and the pgvector query |
| **CI** | Ruff, `compileall`, pytest (incl. pgvector, and a guard that fails if those tests are skipped), a startup-validation assertion, ESLint, `tsc`, `next build`, and both Docker image builds |
| **Graceful degradation** | Redis down degrades memory; retrieval failure yields an ungrounded answer; neither returns a 500 |

---

## ⚡ Performance

Measured against the deployed instance (Groq `llama-3.1-8b-instant`, Neon,
Upstash). Numbers are indicative, not a benchmark.

| Path | Latency | Tokens | Cost/turn |
|---|---|---|---|
| Direct chat | 0.4 – 0.9 s | ~45 | ~$0.000003 |
| Orchestra — simple route | ~1.6 s | ~500 | ~$0.00003 |
| Orchestra — full route | 3.0 – 4.9 s | 3.2k – 5.2k | ~$0.0002 |
| RAG retrieval (warm) | ~2.3 s | ~270 | ~$0.00001 |
| `/health/ready` | ~120 ms | — | — |
| Frontend TTFB | ~390 ms | — | — |

**Embedding warm-up** takes ~20 s at startup and removes a cold-start penalty that
previously exceeded four minutes on the first grounded question. After warm-up
the first RAG query completes in ~0.6 s — indistinguishable from a warm one.

**Rate limiting**, verified with 10 parallel chat requests: exactly 3 succeeded
(the concurrency cap) and 7 returned `429` with `Retry-After`.

---

## 🗺 Future Roadmap

Ordered by impact. These are known gaps, stated plainly.

- [ ] **Real evaluation harness.** Scores today are lexical heuristics — token
      overlap between question and answer, labelled as such in the UI. A golden
      dataset with rubric-scored LLM judging, wired into CI as a regression gate,
      is the single highest-value addition. (Note: the test suite covers
      *correctness of the machinery*, not *quality of the answers* — different
      problems, and only the first one is solved.)
- [ ] **Genuine token streaming on the tools path.** Direct and both Orchestra
      routes now stream from the provider. The tools path still computes a
      complete answer and emits it in slices, because its answer node inspects
      the finished text to detect a refusal after an empty search and regenerate —
      a decision that cannot be made mid-stream.
- [ ] **Alembic migrations.** Schema currently comes from `create_all` at startup
      plus idempotent `ALTER TABLE`, which races across replicas.
- [ ] **Async handlers under concurrency.** The chat handler is a sync `def` and
      holds its database session for the whole SSE stream, so the pool still
      bounds simultaneous chats at roughly 15. (Sessions are now released
      deterministically when a stream ends — they previously lingered until
      garbage collection.)
- [ ] **HNSW index on `document_chunks.embedding`.** Retrieval is currently an
      exact scan — fine at demo scale, wrong at a real corpus.
- [ ] **Hybrid retrieval and reranking.** Fuse pgvector similarity with Postgres
      full-text ranking, then rerank with a cross-encoder.
- [ ] **A real web-search tool.** The built-in `search` covers Orchestra's own
      architecture only; it is labelled accordingly rather than presented as web search.
- [ ] **Sliding-window rate limiting.** The fixed window lets a sequential burst
      straddle a boundary; concurrency is what currently bounds it.
- [ ] **Structured logging with request IDs**, and prompt versioning with A/B runs.

---

## 📚 Lessons Learned

**Observability has to be designed in, not bolted on.** Wrapping the LLM client
rather than instrumenting call sites was the decision that made per-step cost
tracking possible at all. Every later feature inherited measurement for free.

**"It works" and "it works in production" are different claims.** The deployed
frontend was unreachable in Docker for weeks because compose published container
port 3000 while the dev server listened on 13000 — invisible locally, because
local development ran outside the container.

**CI that doesn't build the thing isn't CI.** The frontend failed type-checking
under React 19 for some time. Because CI only ran a single pytest file, nothing
caught it — and it silently blocked the production image, which runs `npm run build`.

**Cold starts are a product problem, not an infrastructure detail.** A lazily
loaded embedding model meant the first grounded question on a spun-down instance
took over four minutes. Everything about that request was "correct." It was still
unusable.

**Rate limiting an LLM endpoint is not one number.** Requests per minute does not
bound concurrency, and neither bounds spend. It took three independent limits to
actually protect the API budget.

**A streaming response defers everything past the point where it can still fail
properly.** `StreamingResponse` sends its status line before the first event is
pulled, so validation living inside the generator ran *after* a 200 had already
gone out — an unauthorized request got 200 and a truncated body instead of 404.
For the same reason, a `Depends(get_db)` session outlived its own teardown and
was released only at garbage collection. Both were found by the first integration
tests written against that endpoint, and neither was visible from the UI.

**Honest labels beat impressive ones.** The scorer reports
`"Heuristic scores (no LLM judge)"` rather than calling itself accuracy. Naming a
limitation costs less than being caught by it.

---

## 🤝 Contributing

Issues and pull requests are welcome.

```bash
cd backend  && pytest tests/          # deterministic LLM stub — no API keys needed
cd frontend && npm run lint && npm run typecheck && npm run build
```

The backend suite runs against SQLite by default, so it needs no services. Point
it at a pgvector database to additionally run the vector-similarity tests, which
are skipped otherwise:

```bash
TEST_DATABASE_URL=postgresql+psycopg2://orchestra:orchestra@localhost:5432/orchestra_test pytest tests/
```

Layering is `API → service → repository → model`. Routers stay thin. Prompts
belong in `backend/app/prompts/`, not inlined at a call site. Comments explain
*why*, not *what*.

---

## 📄 License

[MIT](LICENSE)

<div align="center">
<sub>Built to learn production AI engineering by doing it.</sub>
</div>
