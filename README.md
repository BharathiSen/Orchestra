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

