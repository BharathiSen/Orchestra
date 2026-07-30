# ORCHESTRA

> A production-inspired AI Engineering Platform for designing, building, executing, evaluating, and debugging LangGraph-powered AI agents.

![Status](https://img.shields.io/badge/status-active-success)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![Next.js](https://img.shields.io/badge/Next.js-15-black)

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

- LLM Integration (Gemini/Groq/Ollama)
- Tool Calling
- LangGraph agent workflow
- Multi-agent Orchestra (Planner → Research → Writer → Reviewer)
- Redis conversation memory + Postgres long-term preferences
- Knowledge Base ingestion — upload, chunk, embed, pgvector
- Streaming Responses
- RAG grounded answers with retrieved sources panel
- Execution observability — tokens, cost, latency, traces, replay
---

## Knowledge Layer

- Document Upload (PDF, DOCX, TXT)
- Text extraction (PyMuPDF / python-docx)
- Chunking with overlap
- Embeddings (fastembed — BAAI/bge-small-en-v1.5)
- Vector storage (pgvector in PostgreSQL)
- Chunk inspector UI for debugging

---

## AI Operations

- Execution History (`executions` + `execution_steps`)
- Token Tracking (input / output / total)
- Cost Tracking (model pricing → USD)
- Latency Monitoring (per-step + total)
- Execution Tracing (Execution ID → Planner → Research → … → Response)
- Heuristic Evaluation scores (correctness / relevance / groundedness)
- Execution Replay (stored prompt + context → re-run in Chat)
- Observability Dashboard (24h summary + recent executions)

---

## Observability Architecture

```
User Request
     │
     ▼
ChatService.stream_chat
     │
     ├─ TraceService.start → Execution (status=running)
     ├─ TrackingLLM wraps provider calls → tokens / latency / cost
     ├─ Pipeline steps (planner, research, writer, …) timed into ExecutionStep
     ├─ Snapshot stores prompt, retrieved chunks, tool calls, orchestra steps
     └─ TraceService.complete → scores + aggregates
           │
           ▼
    Observability API + UI
    /dashboard/summary · /executions · /executions/{id} · /replay
```

### Evaluation Metrics

Heuristic only (no LLM-as-a-judge): correctness, relevance, groundedness, hallucination_risk, latency_ok. Aggregates: success rate, average latency, total tokens, total cost, step latency breakdown.

### Token Tracking

Every LLM `complete_chat` / stream records prompt + completion tokens (provider usage when available, else ~4 chars/token estimate). Stored on `executions` and each `execution_steps` row.

### Cost Tracking

`evaluation/cost.py` maps model → USD per 1M input/output tokens. Cost = f(input_tokens, output_tokens, model). Surfaced on the dashboard and execution detail.

### Tracing

Each chat turn gets an Execution ID. Steps mirror the live UI (Orchestra agents or tools graph nodes). SSE emits `execution_meta` with `execution_id`; `done` includes latency/tokens/cost.

### Replay

`POST /api/v1/executions/{id}/replay` returns the stored prompt, pipeline flags, and snapshot. The UI opens Chat with those params prefilled so you can re-run and compare.

### Dashboard

Project → **Observability**: today’s executions, success rate, average latency, total tokens, total cost, recent list, and per-execution detail with steps / scores / rating.

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
                       REST
                       │
                FastAPI Backend
                       │
     ┌─────────────────┼─────────────────┐
     │                 │
 PostgreSQL         Redis
     │                 │
     └─────────────────┼─────────────────┘
                       │
                  LangGraph Runtime
                       │
      Planner → Tools → Reviewer → Answer
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

---

## Backend

- FastAPI
- Python
- SQLAlchemy
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

