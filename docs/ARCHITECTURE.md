# Architecture — Day 1 Foundation

## Principle

**Build the software platform before the AI.** Day 1 has no LLM calls. It establishes auth, tenancy (projects), persistence, and local orchestration via Docker.

## High-level diagram

```text
┌─────────────────┐         REST          ┌─────────────────┐
│  Next.js 15 UI  │ ────────────────────► │  FastAPI /api/v1│
│  :3000          │ ◄──────────────────── │  :8000          │
└─────────────────┘                       └────────┬────────┘
                                                   │
                          ┌────────────────────────┼────────────────────────┐
                          │                        │                        │
                          ▼                        ▼                        ▼
                   ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
                   │ PostgreSQL  │          │    Redis    │          │  (future)   │
                   │ users,      │          │ provisioned │          │ Vector DB   │
                   │ projects    │          │ Day 1       │          │             │
                   └─────────────┘          └─────────────┘          └─────────────┘
```

## Components

| Component | Role on Day 1 |
|-----------|----------------|
| **Frontend** | Login/signup, dashboard, project CRUD UI; JWT in `localStorage` (host port **13000** by default) |
| **Backend** | FastAPI routers under `/api/v1`; JWT auth dependency; SQLAlchemy models (host port **18000**) |
| **PostgreSQL** | Source of truth for users and projects (host **5432**) |
| **Redis** | Connected and health-checked; ready for session/memory on Day 8 (host publish **6380**) |
| **Docker Compose** | Single-command local production-like stack |

## Backend module layout

```text
backend/app/
├── main.py              # FastAPI app, CORS, lifespan (create tables)
├── core/                # config, database, security, redis
├── models/              # User, Project
├── schemas/             # Pydantic request/response models
└── api/
    ├── deps.py          # get_current_user
    └── v1/
        ├── auth.py
        └── projects.py
```

## Auth flow

```text
Signup/Login → bcrypt verify/hash → JWT (sub=user_id) → Bearer on subsequent requests
```

## Project ownership

Every project has `owner_id`. List/get/update/delete only succeed for the authenticated owner (others get 404).

## Future (not Day 1)

LangGraph runtime, WebSockets, pgvector/Qdrant, execution traces — attach under the same project boundary.
