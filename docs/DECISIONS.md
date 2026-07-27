# Architecture Decision Records (ADRs)

## ADR-001: Monorepo layout

**Status**: Accepted (Day 1)  
**Context**: Need a beginner-friendly but production-shaped layout for frontend, backend, infra, and docs.  
**Decision**: Single repo with `frontend/`, `backend/`, `docker/`, `database/`, `docs/`.  
**Consequences**: Simple local Docker Compose; clear ownership of layers; docs travel with code.

## ADR-002: FastAPI + SQLAlchemy for the API

**Status**: Accepted  
**Context**: PLAN.md mandates FastAPI, PostgreSQL, SQLAlchemy, Alembic.  
**Decision**: Sync SQLAlchemy 2.0 sessions for Day 1; create tables on startup; Alembic available for later.  
**Consequences**: Fast to ship Day 1; migrate to Alembic-only schema changes from Day 2+.

## ADR-003: JWT bearer authentication

**Status**: Accepted  
**Context**: Need stateless auth suitable for SPA + API.  
**Decision**: Signup/login return HS256 JWT; passwords hashed with bcrypt; `Authorization: Bearer` dependency.  
**Consequences**: Easy frontend storage; refresh tokens / rotation deferred; secret via env `JWT_SECRET`.

## ADR-004: Projects as the tenancy boundary

**Status**: Accepted  
**Context**: Agents, tools, and knowledge will need a workspace.  
**Decision**: `projects` owned by `users`; all future resources nest under a project.  
**Consequences**: Ownership checks are simple; multi-user project sharing is out of scope for v1 Day 1.

## ADR-005: Redis provisioned early

**Status**: Accepted  
**Context**: PLAN.md uses Redis for memory/sessions on Day 8.  
**Decision**: Run Redis in Compose from Day 1; backend pings it but auth/projects do not depend on it.  
**Consequences**: Infra ready; no premature caching complexity.

## ADR-006: Next.js App Router UI without shadcn yet

**Status**: Accepted (Day 1)  
**Context**: Deliver Login → Dashboard → Projects quickly.  
**Decision**: Next.js 15 + Tailwind with hand-built forms; shadcn/ui and React Flow deferred until UI density grows.  
**Consequences**: Fewer deps Day 1; can adopt shadcn on Day 2+ without rewriting routes.

## ADR-007: Private interview notes stay local

**Status**: Accepted  
**Context**: Engineering study notes should not be public.  
**Decision**: `docs/INTERVIEW_NOTES.md` is gitignored; commit `INTERVIEW_NOTES.example.md` as a template only.  
**Consequences**: Personal Q&A and debug logs never push to remote.

## ADR-008: Repository + Service layers for Agents (Day 2)

**Status**: Accepted  
**Context**: Agent CRUD needs clear ownership rules and will grow into tools/RAG/execution. Fat route handlers become unmaintainable.  
**Decision**: Split into `repositories/` (SQL only), `services/` (business rules), `api/v1/` (HTTP).  
**Consequences**: Slightly more files Day 2; much easier to test and extend on Days 3–10.

## ADR-009: Agents nest under Projects

**Status**: Accepted  
**Context**: PLAN.md Day 2 introduces Agents under the project workspace.  
**Decision**: `agents.project_id` FK; authorize by `project.owner_id == current_user.id`. No direct `owner_id` on agents.  
**Consequences**: Deleting a project cascades agents; moving agents between projects is a PATCH of `project_id` with ownership checks.

## ADR-010: SSE streaming for chat (Day 3)

**Status**: Accepted  
**Context**: ChatGPT-like UX needs token-by-token delivery; waiting for full completion feels broken for long answers.  
**Decision**: `POST /api/v1/chat` returns `text/event-stream` with typed JSON events (`meta`, `token`, `done`, `error`).  
**Consequences**: Frontend uses `fetch` + `ReadableStream`; reverse proxies must disable response buffering (`X-Accel-Buffering: no`).

## ADR-011: Persist user/assistant only; inject system at request time

**Status**: Accepted  
**Context**: System prompts change as agents evolve; duplicating system rows every turn pollutes history.  
**Decision**: Store `user`/`assistant` messages; prepend system instruction when calling Gemini.
**Consequences**: Prompt edits apply to future turns without rewriting history; evaluation later can still log the effective system prompt if needed.
