# Orchestra — Engineering Notebook (Private)

> **PRIVATE — DO NOT PUSH TO GITHUB**  
> This file is listed in `.gitignore`. Use it for interview prep, revision, and personal reference only.  
> Last consolidated: Day 10 (platform + AI runtime + RAG + memory + observability + polish).

---

## Table of contents

1. [Elevator pitch](#1-elevator-pitch)
2. [Problem & product vision](#2-problem--product-vision)
3. [What we built vs did not build](#3-what-we-built-vs-did-not-build)
4. [10-day journey (end-to-end)](#4-10-day-journey-end-to-end)
5. [System architecture](#5-system-architecture)
6. [Tech stack & why](#6-tech-stack--why)
7. [Repository map](#7-repository-map)
8. [Data model](#8-data-model)
9. [Request lifecycles](#9-request-lifecycles)
10. [Module deep dives](#10-module-deep-dives)
11. [API surface (cheat sheet)](#11-api-surface-cheat-sheet)
12. [SSE event contract](#12-sse-event-contract)
13. [Design decisions (ADRs in plain English)](#13-design-decisions-adrs-in-plain-english)
14. [Interview definitions & talking points](#14-interview-definitions--talking-points)
15. [Common interview questions (model answers)](#15-common-interview-questions-model-answers)
16. [How to demo in 5–7 minutes](#16-how-to-demo-in-57-minutes)
17. [Local ops & ports](#17-local-ops--ports)
18. [Deployment mental model](#18-deployment-mental-model)
19. [Known limitations & honest gaps](#19-known-limitations--honest-gaps)
20. [Revision checklist](#20-revision-checklist)

---

## 1. Elevator pitch

**Orchestra** is a production-inspired **AI operating platform**, not a chatbot.

You can:

- Create **projects** and **agents**
- Chat with **streaming** replies
- Call **tools** (calculator, weather, search)
- Run a **LangGraph** tool workflow or a **multi-agent Orchestra** (Planner → Research → Writer → Reviewer)
- Attach **knowledge bases** (upload → chunk → embed → **pgvector** retrieve)
- Keep **Redis** short-term memory + **Postgres** long-term preferences
- **Observe** every run: tokens, cost, latency, steps, scores, **replay**

**One-liner for interviews:**  
*“I built an end-to-end agent platform with FastAPI + Next.js + LangGraph, RAG on Postgres/pgvector, Redis memory, and execution tracing like a lightweight LangSmith.”*

---

## 2. Problem & product vision

### Problem

Building agents is fragmented: prompts in notebooks, tools elsewhere, no ownership model, weak auth, and almost no observability. Chat demos don’t teach production AI engineering.

### Vision

Orchestra is to agents what GitHub is to repos: a workspace for the **full agent lifecycle** — design, execute, ground in knowledge, remember users, evaluate, and debug.

### Goals

1. Learn production AI engineering by implementing it.
2. Ship a portfolio-worthy, modular, observable system.
3. Build **platform first**, then AI runtime, knowledge, memory, observability, polish.

### Non-goals (intentionally deferred)

- LLM-as-a-judge / heavy eval frameworks
- Human feedback pipelines / A/B testing
- Multi-tenant SaaS billing
- Separate Qdrant cluster (we use **pgvector in Postgres**)
- Full prompt-versioning UI (prompts are code library today)

---

## 3. What we built vs did not build

| Capability | Status |
|------------|--------|
| JWT auth, projects, agents | Done |
| Conversations + messages | Done |
| SSE streaming chat | Done |
| Tool registry + calling | Done |
| LangGraph tools graph | Done |
| Multi-agent Orchestra + routing | Done |
| KB ingest + RAG retrieve | Done |
| Redis + long-term memory | Done |
| Executions / steps / cost / tokens / latency | Done |
| Dashboard + search + replay + rating | Done |
| Prompt library (`app/prompts/`) | Done |
| Landing, 404, Docker, deploy docs | Done |
| LLM-as-judge / Qdrant / React Flow studio | Not built (by design for Day 10 scope) |

---

## 4. 10-day journey (end-to-end)

### Day 1 — Platform foundation

- Monorepo: `frontend/`, `backend/`, `docker/`, `docs/`, `database/`
- Docker Compose: Postgres, Redis, FastAPI, Next.js
- JWT signup/login, Users, Projects CRUD
- Login → Dashboard → Projects

**Interview angle:** Separate **product platform** from AI. Auth and tenancy come first.

### Day 2 — Agents

- Agent model under a project (name, system_prompt, model_name)
- Layered backend: API → Service → Repository → Model
- Ownership: only via owned projects
- UI: project → agent list → create/edit

**Interview angle:** Agents are **config + identity**, not the LLM call itself.

### Day 3 — Chat + streaming

- Conversations / Messages in Postgres
- LLM providers (evolved to Groq / Gemini / Ollama)
- SSE token streaming
- System prompt from agent or default

**Interview angle:** SSE vs WebSockets; persist only user/assistant turns.

### Day 4 — Tool calling

- Tool interface: name, description, JSON schema, `execute`
- Registry: calculator (safe AST), weather (Open-Meteo), search (mock → later RAG)
- LLM may emit tool calls → execute → feed results → final answer
- SSE: `tool_start` / `tool_result`
- Toggle: `enable_tools`

**Interview angle:** Tools are **side effects with schemas**; never `eval` for math.

### Day 5 — LangGraph tool workflow

- Graph: **planner → tool → reviewer → answer**
- SSE `graph_step` + execution panel in chat UI

**Interview angle:** LangGraph = explicit state machine for agent control flow.

### Day 6 — Knowledge ingestion

- Upload PDF/DOCX/TXT
- Extract → chunk (~400 tokens, overlap) → embed (**fastembed** BAAI/bge-small-en-v1.5, 384-d)
- Store in `document_chunks.embedding` (**pgvector**)
- No chat retrieval yet on Day 6

**Interview angle:** Ingestion pipeline separate from query/RAG.

### Day 7 — RAG

- Similarity search over chunks
- Grounded system prompt with retrieved excerpts
- Agent ↔ knowledge base linking
- UI: retrieved sources panel
- SSE `retrieved_context`

**Interview angle:** RAG = retrieve then generate; reduce hallucination via grounding.

### Day 8 — Memory + multi-agent Orchestra

- **Redis**: short-term conversation buffer (last N turns), optional summary on overflow
- **Postgres** `user_memories`: long-term preferences/facts
- Auto-extract facts from turns (“I prefer Python”)
- **OrchestraEngine**: Planner → Research → Writer → Reviewer  
  - **Simple route**: Planner → Research → FastAnswer  
  - **Full route**: Planner → Research → Writer → Reviewer
- Research: KB retrieve (+ optional web search), skip KB for personal/name questions
- Message `trace` JSON for UI reload
- SSE: `orchestra_step`, `memory_status`

**Interview angle:** Short-term vs long-term memory; multi-agent = specialized roles + shared state.

### Day 9 — Observability

- Tables: `executions`, `execution_steps`
- `ExecutionTracker` + `TrackingLLM` wrap provider calls
- Tokens (provider usage or estimate), cost (model pricing table), latency per step
- Heuristic scores (not LLM-judge): correctness, relevance, groundedness, hallucination_risk
- Snapshot for replay (prompt, chunks, tools, orchestra steps)
- APIs: dashboard summary/metrics, executions list/detail, rating, replay
- UI: Observability dashboard + execution detail

**Interview angle:** Observability turns a chatbot into an **AI operating platform**.

### Day 10 — Polish & packaging

- Prompt library under `backend/app/prompts/`
- Execution history search (`q`, `status`, `pipeline`)
- Landing page, 404, empty/loading polish
- README + architecture diagram + `docs/DEPLOYMENT.md`
- Docker documented; vectors remain **pgvector** (not Qdrant)

**Interview angle:** Prompt centralization, portfolio packaging, deploy story.

---

## 5. System architecture

```text
                         User
                           │
                    Next.js Frontend
              (Landing · Chat · KB · Observability)
                           │  REST + SSE + JWT
                    FastAPI Backend
                           │
              ┌────────────┼────────────┐
              │            │            │
         Orchestra    Tools Graph    RAG / Memory
         (multi-agent) (LangGraph)   / Tracing
              │            │            │
     ┌────────┴────────────┴────────────┴────────┐
     │                                           │
 PostgreSQL + pgvector                      Redis
 (users, agents, KB chunks,               (short-term
  executions/steps, memories)              conversation)
                     │
              Groq / Gemini / Ollama
```

**Diagram asset (in repo):** `docs/architecture.png` (also embedded in README).

**Critical clarification for interviews:**  
We did **not** add Qdrant. Vector search is **Postgres + pgvector**. Curriculum sometimes mentions Qdrant as an option; this implementation chose one DB for metadata + vectors.

---

## 6. Tech stack & why

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | Next.js 15 + TS + Tailwind | App router, fast UI, portfolio-friendly |
| Backend | FastAPI + SQLAlchemy | Typed APIs, OpenAPI, async-friendly sync for LLM I/O |
| Auth | JWT Bearer | Stateless API auth |
| Primary DB | PostgreSQL | Relational ownership + JSON + pgvector |
| Vectors | pgvector | Same DB as app data; simpler ops than separate vector DB |
| Embeddings | fastembed (bge-small-en-v1.5) | Local, no paid embedding API required |
| Cache / memory | Redis | Fast ephemeral conversation buffer |
| Orchestration | LangGraph | Explicit graphs, conditional edges, debuggable |
| LLM | Groq / Gemini / Ollama | Pluggable; Groq for cheap cloud testing |
| Packaging | Docker Compose | Reproducible local stack |

---

## 7. Repository map

```text
Orchestra/
├── backend/app/
│   ├── api/v1/          # auth, projects, agents, chat, memory, observability
│   ├── agents/          # Planner, Research, Writer, Reviewer, FastAnswer
│   ├── prompts/         # Centralized system prompts (Day 10)
│   ├── orchestrator/    # OrchestraEngine, routing, state
│   ├── graph/           # Tools LangGraph (planner→tool→reviewer→answer)
│   ├── tools/           # Registry + calculator/weather/search
│   ├── knowledge/       # Ingest pipeline
│   ├── rag/             # Retrieve + grounded prompts
│   ├── memory/          # Redis + long-term facts
│   ├── evaluation/      # cost, metrics, tracker, scorer
│   ├── observability/   # TraceService, TrackingLLM, logger
│   ├── dashboard/       # Aggregations for history UI
│   ├── models/          # SQLAlchemy ORM
│   ├── repositories/    # Data access
│   ├── schemas/         # Pydantic
│   └── services/        # ChatService, LLM providers
├── frontend/src/app/    # landing, login, dashboard, projects, chat, KB, observability
├── database/            # init.sql
├── docker/              # docker-compose.yml
├── docs/                # public architecture/API/deploy (+ THIS private notebook)
└── README.md
```

---

## 8. Data model

### Core platform

```text
User 1──<N Project 1──<N Agent
                   │
                   ├──<N Conversation 1──<N Message  (trace JSON optional)
                   │
                   └──<N KnowledgeBase 1──<N Document 1──<N DocumentChunk
                                                              embedding vector(384)
```

### Memory (Day 8)

- Redis keys per conversation (buffer of recent turns; optional summary)
- Postgres `user_memories` (category/key/value preferences & facts)

### Observability (Day 9)

**`executions`:** id, user/project/conversation/agent/message ids, status, pipeline, model, prompt, final_response, started/completed, latency_ms, input/output/total tokens, api_calls, total_cost_usd, success, user_rating, snapshot JSON, scores JSON  

**`execution_steps`:** execution_id, sequence, step_name, status, latency_ms, tokens, cost, detail JSON  

### Agent ↔ KB

Many-to-many via `agent_knowledge_bases`.

### Persistence policy (important)

- Persist **user** + **assistant** messages.
- Tool activity is primarily **live SSE** (not full tool-call tables).
- Day 8+ may store a compact `messages.trace` for UI reload.
- Day 9 stores full execution rows for observability/replay.

---

## 9. Request lifecycles

### A) Direct chat (`enable_orchestra=false`, `enable_tools=false`)

1. Auth + project ownership  
2. Create/load conversation; persist user message  
3. Load Redis buffer (+ long-term prefs into system prompt)  
4. Optional RAG if agent has KBs  
5. Stream LLM tokens via SSE  
6. Persist assistant message; update Redis memory  
7. Day 9: start/complete **Execution** (steps like retrieve/generate)

### B) Tools path (`enable_tools=true`, orchestra off)

1. Same as above through history/RAG  
2. Build LangGraph with tools schemas  
3. Planner may skip tools for pure writing prompts  
4. Tool node executes registry tools; SSE tool events + graph_step  
5. Reviewer + answer nodes; stream final text  
6. Persist + memory + execution (`pipeline=tools`)

### C) Orchestra path (`enable_orchestra=true`)

1. Tools graph disabled (Orchestra owns the multi-agent path)  
2. Route: **simple** vs **full** (`classify_route`)  
3. Agents mutate shared `OrchestraState`  
4. Research may retrieve KB / search; personal Qs skip KB  
5. Final answer streamed as tokens  
6. SSE `orchestra_step`; execution steps named planner/research/…  

### Day 9 wrapping (all paths)

- `TraceService.start` → `execution_meta` SSE  
- `TrackingLLM` records tokens/latency into open step or standalone LLM step  
- On success/error: `TraceService.complete` with snapshot + heuristic scores  
- `done` includes execution_id, latency_ms, total_tokens, total_cost_usd  

---

## 10. Module deep dives

### Prompt library (`app/prompts/`)

Centralizes agent system prompts so they are reusable and maintainable.

| File | Role |
|------|------|
| `planner.py` | Plan 3–6 steps; no final answer |
| `research.py` | Notes from KB / no-KB synthesis |
| `writer.py` | Draft grounded in research + memory |
| `reviewer.py` | NOTES + FINAL sections |
| `fast_answer.py` | Simple route concise answers |
| `system.py` | Tool addendum, graph reviewer, defaults |

**Interview line:** *“Prompt library centralizes prompt management, improves maintainability, enables future versioning, and makes prompts reusable across agents.”*

### Tools

| Tool | Implementation |
|------|----------------|
| calculator | AST-only arithmetic (no `eval`) |
| weather | Open-Meteo geocode + current weather; mock fallback |
| search | Originally mock KB; RAG is the real grounded path via Research/RAG modules |

### RAG

1. Embed question  
2. Cosine / pgvector similarity over chunks filtered by KB ids  
3. Serialize top-k chunks  
4. Inject into grounded system prompt  
5. Emit `retrieved_context` for UI  

### Memory

| Type | Store | Purpose |
|------|-------|---------|
| Short-term | Redis | Last N turns for LLM context |
| Summary | Redis/Postgres path via memory service | Compress overflow |
| Long-term | Postgres | Preferences, name, durable facts |

### Evaluation (lightweight)

- **Cost** = f(model pricing, input_tokens, output_tokens)  
- **Metrics** = success rate, averages, tool success  
- **Scorer** = heuristics only (overlap / groundedness proxies)  
- Explicitly **not** LLM-as-judge for Day 9/10  

### Observability UI

- Project → **Observability** / Execution History  
- Stats: today’s executions, success rate, avg latency, tokens, cost  
- Search: prompt/response/model/pipeline text + status/pipeline filters  
- Detail: steps, scores, prompt, response, retrieved chunks, tools, rating, replay  

---

## 11. API surface (cheat sheet)

Base: `/api/v1` · Auth: `Authorization: Bearer <jwt>` · Docs: `/docs` · Health: `/health`

| Area | Key routes |
|------|------------|
| Auth | `POST /auth/signup`, `/auth/login`, `GET /auth/me` |
| Projects | CRUD `/projects` |
| Agents | CRUD `/agents` |
| Chat | `POST /chat` (SSE), conversations, messages, `GET /chat/models`, `GET /tools` |
| Knowledge | `/knowledge-bases`, documents upload, chunks |
| Memory | `/memory/status`, preferences, conversation dump |
| Dashboard | `/dashboard/summary`, `/dashboard/metrics` |
| Executions | `GET /executions?project_id=&q=&status=&pipeline=&limit=` |
| | `GET /executions/{id}`, `POST .../rating`, `POST .../replay` |

Ownership rule everywhere: resources reachable only if the related **project.owner_id == current user**.

---

## 12. SSE event contract

Typical event types (JSON in `data:` lines):

| type | Meaning |
|------|---------|
| `meta` | conversation_id, title |
| `user_message` | persisted user turn |
| `memory_status` | Redis / long-term status |
| `execution_meta` | execution_id (Day 9) |
| `retrieved_context` | RAG chunks |
| `tool_start` / `tool_result` | tool calling |
| `graph_step` | tools graph node progress |
| `orchestra_step` | multi-agent progress |
| `token` | streamed text |
| `done` | message_id, conversation_id, execution metrics |
| `error` | failure detail |

---

## 13. Design decisions (ADRs in plain English)

1. **Platform before AI** — Auth/projects first so agents have a home.  
2. **Layered backend** — API / service / repository keeps FastAPI thin.  
3. **SSE for chat** — One-way token stream; simpler than WebSockets for this use case.  
4. **Persist user/assistant only** — Tool traces live in SSE (+ optional message.trace / executions).  
5. **pgvector over Qdrant** — One operational database for metadata + vectors.  
6. **Pluggable LLM providers** — Same chat interface for Groq/Gemini/Ollama.  
7. **Orchestra vs tools graph** — Mutually exclusive toggles; Orchestra owns multi-agent path.  
8. **Simple vs full route** — Cheap path for personal/simple Qs; full pipeline for complex asks.  
9. **Heuristic eval first** — Observability without LLM-judge cost/complexity.  
10. **Prompt library in code** — Centralized; UI versioning left for later.  
11. **Private notebook / interview notes gitignored** — Portfolio repo stays clean.

---

## 14. Interview definitions & talking points

**AI agent** — System that uses an LLM plus tools/memory/retrieval to pursue a goal beyond single-turn chat.

**LangGraph** — Graph-based orchestration: nodes mutate shared state; edges (including conditional) define control flow.

**Tool calling** — Model returns structured function calls; host executes tools and returns results for a final answer.

**RAG** — Retrieve relevant documents, then generate an answer grounded in that context.

**pgvector** — Postgres extension for storing/querying embedding vectors (cosine similarity, etc.).

**Agent memory** — Short-term (session/conversation) + long-term (durable user facts/preferences).

**AI evaluation** — Measuring quality, reliability, and efficiency with quantitative/qualitative metrics (here: success, latency, tokens, cost, heuristic scores).

**Observability / tracing** — Assign an Execution ID and record each step’s latency/tokens/cost/status so runs are inspectable.

**Prompt library** — Centralized prompts for maintainability, reuse, and future versioning.

**Why Docker?** — Consistent, reproducible environments; packages app + dependencies for local and deploy.

---

## 15. Common interview questions (model answers)

**Q: Why not just ChatGPT API in a single Next.js route?**  
A: We needed multi-tenant projects/agents, tools, RAG, memory, and traces. That’s platform engineering, not a widget.

**Q: Why LangGraph instead of a for-loop of LLM calls?**  
A: Explicit state, conditional routing (simple/full), reusable nodes, and clearer debugging via step events.

**Q: How do you prevent tool hallucination?**  
A: Schema-constrained tool calls, execute real tools, feed results back, instruct model not to invent tool output; calculator uses AST not eval.

**Q: How does RAG reduce hallucinations?**  
A: Inject retrieved chunks into the system prompt and prefer those facts; UI shows sources; Research agent told not to invent sources.

**Q: Short-term vs long-term memory?**  
A: Redis holds recent turns for immediate context; Postgres stores durable preferences/facts extracted across sessions.

**Q: How do you measure cost?**  
A: Track input/output tokens (provider usage or estimate), multiply by per-model USD rates in `evaluation/cost.py`, aggregate on executions.

**Q: What’s in an Execution?**  
A: Prompt, response, pipeline, model, latency, tokens, cost, success, steps, snapshot (chunks/tools/orchestra), heuristic scores, optional rating.

**Q: What would you add next?**  
A: Prompt versioning UI, stronger eval (optional LLM-judge), guardrails/model routing, hosted demo (Neon/Upstash/Vercel/Railway), human-in-the-loop.

---

## 16. How to demo in 5–7 minutes

1. **Landing** (`/`) — product story  
2. **Login → Dashboard → Project**  
3. **Knowledge** — show a KB / document (if uploaded)  
4. **Chat** — Orchestra ON: ask a multi-step question; show agent steps panel  
5. **Chat** — personal memory: “My name is X” → “What is my name?”  
6. **Chat** — tools OFF Orchestra: math with tools ON (optional)  
7. **Observability** — today’s stats, open an execution, show steps/tokens/cost  
8. **Replay** — open replay into chat  

Ports (Docker defaults on this machine): Frontend **13000**, API **18000**.

---

## 17. Local ops & ports

```bash
cp .env.example .env   # set GROQ_API_KEY or GEMINI_API_KEY
cd docker
docker compose --env-file ../.env up --build
```

| Service | Typical URL |
|---------|-------------|
| Frontend | http://localhost:13000 |
| API docs | http://localhost:18000/docs |
| Health | http://localhost:18000/health |
| Redis host map | localhost:6380 → container 6379 |

Key env: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `CORS_ORIGINS`, `LLM_PROVIDER`, `GROQ_API_KEY` / `GEMINI_API_KEY`, `NEXT_PUBLIC_API_URL`.

---

## 18. Deployment mental model

Documented in `docs/DEPLOYMENT.md` (public):

| Piece | Suggested host |
|-------|----------------|
| Frontend | Vercel |
| Backend | Railway / Render / Fly |
| Postgres + pgvector | Neon |
| Redis | Upstash |
| LLM | Groq or Gemini |

No Qdrant required. Set `CORS_ORIGINS` and `NEXT_PUBLIC_API_URL` correctly.

---

## 19. Known limitations & honest gaps

- Heuristic scores ≠ true correctness; no LLM-as-judge yet.  
- Prompt versions are code-level, not DB/UI versioned.  
- Tool calls aren’t a full normalized tool-trace schema (executions/snapshots cover Day 9).  
- Weather/search quality depends on network/mocks.  
- Redis down ⇒ memory degrades; chat still works.  
- Architecture docs for early days still mention “Redis unused” in old sections — Day 8 superseded that.  
- Screenshots/GIF for README may still need capturing.  
- This notebook and interview notes stay **private**.

---

## 20. Revision checklist

Before an interview, be able to draw/explain:

- [ ] User → Next.js → FastAPI → Orchestra / Tools / RAG  
- [ ] Postgres tables + where vectors live  
- [ ] Redis vs long-term memory  
- [ ] Three chat paths (direct / tools / orchestra)  
- [ ] Execution + step tracing  
- [ ] Why pgvector, why SSE, why JWT  
- [ ] One demo script (section 16)  
- [ ] One “what I’d build next” answer  

---

## Source map (what this notebook consolidates)

| Public / repo docs | Role |
|--------------------|------|
| `README.md` | Portfolio overview |
| `docs/ARCHITECTURE.md` | System diagrams |
| `docs/API.md` | Early API contracts (extend with Day 8–10 routes above) |
| `docs/DATABASE.md` | Schema notes (extend with executions/memory) |
| `docs/PRD.md` | Product goals by day |
| `docs/DEPLOYMENT.md` | Cloud deploy |
| `PLAN.md` | Original 10-day roadmap |
| Code under `backend/app/*` | Source of truth when docs lag |

---

*End of private Engineering Notebook. Keep local. Do not commit.*
