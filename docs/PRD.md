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

## Out of scope until later days

See `ROADMAP.md` and root `PLAN.md` (Days 3–10 + v2).
