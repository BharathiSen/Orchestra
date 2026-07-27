# ORCHESTRA

> A production-inspired AI Engineering Platform for designing, building, executing, evaluating, and debugging LangGraph-powered AI agents.

![Status](https://img.shields.io/badge/status-active-success)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![Next.js](https://img.shields.io/badge/Next.js-15-black)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## 📖 Overview

Orchestra is a full-stack AI engineering platform inspired by tools such as LangSmith, LangGraph Studio, Flowise, and enterprise AI development platforms.

Orchestra acts as a centralized workspace where developers can:

- Create AI agents
- Build multi-agent workflows
- Attach tools
- Connect knowledge bases
- Execute LangGraph pipelines
- Observe execution traces
- Evaluate responses
- Manage prompts
- Compare models
- Debug agent behavior

The objective is to learn modern AI Engineering by building a production-ready platform from scratch.

---

# 🚀 Quick start

```bash
cp .env.example .env
cd docker
docker compose --env-file ../.env up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:13000 |
| API docs | http://localhost:18000/docs |
| Health | http://localhost:18000/health |

**Login:** there is **no default admin**. Use **Sign up** on the login page to create your own account (password min 8 characters), then sign in with those credentials.

**Progress so far**
- Day 1: Auth (JWT), Projects, Docker stack
- Day 2: Agent CRUD, dashboard project cards, repository/service layers
- Day 3: Gemini chat, streaming SSE, conversations/messages, chat UI

**Gemini / Groq / Ollama (Day 3+):**  
- Free testing: `LLM_PROVIDER=groq` + `GROQ_API_KEY` from https://console.groq.com/keys  
- Fully local free: `LLM_PROVIDER=ollama` (install Ollama, `ollama pull llama3.2`)  
- Production: `LLM_PROVIDER=gemini` + `GEMINI_API_KEY`  
Then restart the backend. Chat: `/projects/{id}/chat`.

Private study notes (`docs/INTERVIEW_NOTES.md`) and local test scratch (`docs/manual_testing.md`) are gitignored — use `docs/TESTING.md` for the shared checklist.

---

# ✨ Core Features

## Platform

- User Authentication
- Project Workspace
- Agent Management
- Role-based Architecture
- REST API
- Docker Deployment

---

## AI Engineering

- OpenAI Integration → Gemini chat (Day 3)
- LangChain
- LangGraph
- Multi-Agent Workflows
- Tool Calling
- Structured Outputs
- Streaming Responses
- Conversation Memory

---

## Knowledge Layer

- Document Upload
- Embeddings
- Vector Database
- Semantic Search
- Retrieval-Augmented Generation (RAG)

---

## AI Operations

- Execution History
- Prompt Versioning
- Evaluation Dashboard
- Cost Tracking
- Token Analytics
- Latency Monitoring
- Observability

---

## Advanced Features

- Model Routing
- Guardrails
- MCP Integration
- Workflow Templates
- Human-in-the-loop
- Agent Marketplace (Future)

---

# 🏗️ Architecture

```
                Next.js Frontend
                       │
                 REST / WebSocket
                       │
                FastAPI Backend
                       │
     ┌─────────────────┼──────────────────┐
     │                 │                  │
 PostgreSQL         Redis           Vector DB
     │                 │                  │
     └─────────────────┼──────────────────┘
                       │
                  LangGraph Runtime
                       │
      Planner → Tools → Memory → Reviewer
                       │
                   LLM Providers
```

---

# 🛠 Tech Stack

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- React Flow

---

## Backend

- FastAPI
- Python
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis

---

## AI

- Gemini / Groq / Ollama
- LangChain
- LangGraph
- pgvector
- Embeddings
- RAG

---

## Infrastructure

- Docker
- Docker Compose
- GitHub Actions

---

# 📅 Development Roadmap

## Phase 1

- Authentication (JWT)
- Projects
- Agents (CRUD)
- Dashboard + project cards
- Docker
- Repository / service layers

---

## Phase 2

- LLM Integration
- Streaming chat
- Conversations / messages
- Tool Calling
- LangGraph

---

## Phase 3

- Vector Database
- Embeddings
- Knowledge Base
- RAG

---

## Phase 4

- Multi-Agent
- Memory
- Evaluation
- Metrics

---

## Phase 5

- Prompt Versioning
- MCP
- Model Routing
- Guardrails
- Workflow Builder

---

# 🎯 Learning Objectives

This project is designed to master:

- Production AI Engineering
- Agentic AI
- LangGraph
- Modern Backend Development
- LLM Application Development
- AI Infrastructure
- System Design
- Docker Deployment

---

# 📚 Inspiration

- LangGraph Studio
- LangSmith
- Flowise
- LangFlow
- n8n
- Gemini / Groq / Ollama
- CrewAI

---

