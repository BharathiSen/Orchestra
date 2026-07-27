# Architecture — Days 1–2 Platform Foundation

## Principle

**Build the software platform before the AI.** Days 1–2 have no LLM calls. They establish auth, projects, agents (definitions only), persistence, and layered API design.

## High-level diagram (Day 2)

```text
             Browser
                │
        Next.js Dashboard
                │
          REST API Calls
                │
            FastAPI
      ┌─────────┴─────────┐
      ▼                   ▼
 Authentication      Agent Service
      │                   │
      └─────────┬─────────┘
                ▼
           PostgreSQL
```

Redis remains provisioned for Day 8 memory — not used in agent CRUD.

## Request layers (why repository + service?)

```text
API (agents.py)        → HTTP in/out, status codes, Depends(JWT)
Service (agent_service) → Business rules (ownership, project exists)
Repository (agent_repo) → SQLAlchemy queries only
Model (Agent)           → Table mapping
```

| Layer | Responsibility |
|-------|----------------|
| **Repository** | Database operations only (`create`, `get`, `list`, `update`, `delete`) |
| **Service** | Business logic (agent belongs to user via project; reject bad project ids) |
| **API** | HTTP request/response handling |

This keeps the codebase maintainable as Orchestra grows into tools, RAG, and LangGraph.

## Components

| Component | Role |
|-----------|------|
| **Frontend** | Login, dashboard project cards, project detail + agent list, create/edit dialog |
| **Backend** | FastAPI `/api/v1` — auth, projects, agents |
| **PostgreSQL** | `users`, `projects`, `agents` |
| **Redis** | Online; unused for CRUD |
| **Docker Compose** | Local stack |

## Backend module layout (Day 2)

```text
backend/app/
├── api/v1/
│   ├── auth.py
│   ├── projects.py
│   └── agents.py
├── models/
│   ├── user.py
│   ├── project.py
│   └── agent.py
├── schemas/
│   ├── user.py
│   ├── project.py
│   └── agent.py
├── services/
│   └── agent_service.py
├── repositories/
│   └── agent_repository.py
└── core/
```

## Create-agent data flow

```text
Frontend
  → POST /api/v1/agents
  → JWT verification
  → Validate request (Pydantic)
  → Service: project exists + owned by user
  → Repository: insert into PostgreSQL
  → Return AgentResponse
  → Frontend updates UI
```

## Ownership model

- User owns Projects (`projects.owner_id`)
- Project owns Agents (`agents.project_id`)
- Agent access is authorized by walking Agent → Project → owner_id == current user
