# Roadmap

Aligned with root `PLAN.md` — Orchestra v1.0 (10-day plan).

## Phase 1 — Platform Foundation (Days 1–2)

| Day | Focus | Status |
|-----|--------|--------|
| **1** | Monorepo, Docker, FastAPI, JWT auth, Users/Projects, Login→Dashboard→Projects | **Complete** |
| **2** | API design, Agent CRUD, repository/service layers, Dashboard→Projects→Agent list | **Complete** |

## Phase 2 — AI Runtime (Days 3–5)

| Day | Focus |
|-----|--------|
| 3 | LLM chat, streaming, conversations/messages |
| 4 | Tool calling (calculator, weather, search, custom) |
| 5 | LangGraph planner → tool → reviewer → answer |

## Phase 3 — Knowledge Layer (Days 6–7)

| Day | Focus |
|-----|--------|
| 6 | Embeddings, chunking, vector DB, knowledge base upload |
| 7 | RAG: retrieve → inject context → grounded answer |

## Phase 4 — Agent Intelligence (Days 8–9)

| Day | Focus |
|-----|--------|
| 8 | Memory (Redis sessions), multi-agent pipelines |
| 9 | Evaluation, latency/tokens/cost, execution history |

## Phase 5 — Production AI (Day 10)

Prompt library, Docker polish, README/architecture, landing page, deployment.

## Version 2 (post-applications)

Prompt versioning → Model router → Guardrails → MCP → React Flow workflow builder → Experiment platform.

## Day 1 milestone checklist

- [x] Repository structure
- [x] Docker Compose (frontend, backend, Postgres, Redis)
- [x] FastAPI `/api/v1` with auth + projects
- [x] JWT signup/login + password hashing
- [x] Projects CRUD
- [x] Frontend Login, Dashboard, Projects
- [x] Docs updated from PLAN.md

## Day 2 milestone checklist

- [x] Agent model + schemas
- [x] Agent repository + service layers
- [x] Agent CRUD REST endpoints
- [x] Dashboard project cards
- [x] Project agent list + create/edit dialog
- [x] Docs + interview notes for API/DB design
