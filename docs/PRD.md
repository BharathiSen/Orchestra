# Orchestra — Product Requirements (PRD)

## Problem

Building production AI agents today is fragmented: prompts in one place, tools elsewhere, no shared project model, weak auth, and little operational scaffolding. Developers need a platform that owns the **full agent lifecycle**, not just a chat box.

## Product vision

Orchestra is an AI-native development platform — similar in role to how GitHub serves repositories — for designing, orchestrating, executing, evaluating, and managing intelligent agents.

## Goals

1. Learn production AI engineering by implementing it.
2. Ship a portfolio-worthy platform with modular, observable architecture.
3. Build incrementally: **platform first**, then AI runtime, knowledge, intelligence, production polish.

## Non-goals (Day 1)

- LangChain / LangGraph runtime
- RAG, embeddings, vector DB
- Tool calling, streaming, evaluation
- Multi-agent workflows

## Users

| Persona | Need |
|---------|------|
| AI engineer / learner | Workspace to grow agents over time |
| Portfolio reviewer | Clear architecture and running demo |
| Future team | Extensible API and Docker setup |

## Day 1 scope (must have)

| Feature | Requirement |
|---------|-------------|
| Monorepo | `frontend/`, `backend/`, `docker/`, `docs/`, `database/` |
| Infra | Docker Compose: Postgres, Redis, backend, frontend |
| Auth | Signup, login, JWT, bcrypt password hashing |
| Projects | Authenticated CRUD, owner-scoped |
| UI | Login, Dashboard, Projects pages |
| Docs | PRD, Architecture, Roadmap, Database, API, ADRs |

## Success criteria

- `docker compose up` brings the stack online
- User can sign up / log in and receive a JWT
- User can create, list, and delete their projects
- Flow works end-to-end: Login → Dashboard → Projects

## Out of scope until later days

See `ROADMAP.md` and root `PLAN.md` (Days 2–10 + v2).
