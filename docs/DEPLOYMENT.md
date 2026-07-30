# Deployment

Guide for deploying Orchestra to managed hosting. Local Docker remains the fastest path for development; use this doc when you want a production-style split (frontend CDN + backend API + managed data).

## Recommended topology

| Layer | Suggested host | Notes |
|-------|----------------|-------|
| Frontend | **Vercel** | Next.js app; set `NEXT_PUBLIC_API_URL` to the public API origin |
| Backend | **Railway** or **Render** | FastAPI + Uvicorn; persistent disk optional for uploads |
| Postgres + pgvector | **Neon** | Enable the `vector` / pgvector extension; run `database/init.sql` |
| Redis | **Upstash** | Redis-compatible URL for short-term conversation memory |

Vectors are stored in **Postgres via pgvector**. You do **not** need Qdrant or another vector database.

```text
Browser ──► Vercel (Next.js)
                │
                │  NEXT_PUBLIC_API_URL
                ▼
         Railway / Render (FastAPI)
                │
     ┌──────────┼──────────┐
     ▼          ▼          ▼
   Neon      Upstash    LLM APIs
 (Postgres   (Redis)   (Groq / Gemini)
 + pgvector)
```

---

## 1. Neon (Postgres + pgvector)

1. Create a Neon project.
2. Enable the **pgvector** extension (`CREATE EXTENSION IF NOT EXISTS vector;`).
3. Apply schema from `database/init.sql` (or let the app create tables if you use SQLAlchemy `create_all` in this environment — prefer running `init.sql` for indexes/extensions).
4. Copy the connection string into `DATABASE_URL` using the SQLAlchemy form:

```text
postgresql+psycopg2://USER:PASSWORD@HOST/DB?sslmode=require
```

---

## 2. Upstash (Redis)

1. Create an Upstash Redis database.
2. Copy the Redis URL into `REDIS_URL` (e.g. `rediss://default:...@....upstash.io:6379`).

If Redis is unreachable, chat still works; short-term memory and the memory status panel degrade gracefully.

---

## 3. Backend (Railway or Render)

1. Deploy from the `backend/` directory (Dockerfile or `uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
2. Set environment variables (see below).
3. Add a public HTTPS URL and allow your Vercel origin in `CORS_ORIGINS`.
4. Optionally attach a volume for `UPLOAD_DIR` if you persist knowledge-base files on disk.

Health check: `GET /health` → `{ "status": "ok" }`.

---

## 4. Frontend (Vercel)

1. Import the repo; set **Root Directory** to `frontend`.
2. Build command: `npm run build` (framework preset: Next.js).
3. Environment:

```text
NEXT_PUBLIC_API_URL=https://your-api.example.com
```

4. Redeploy after changing `NEXT_PUBLIC_*` (they are inlined at build time).

---

## Environment variables

### Backend (required / common)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres + pgvector (Neon) |
| `REDIS_URL` | Upstash Redis |
| `JWT_SECRET` | Long random secret for access tokens |
| `CORS_ORIGINS` | Comma-separated frontend origins (Vercel URL) |
| `LLM_PROVIDER` | `groq` \| `gemini` \| `ollama` |
| `GROQ_API_KEY` | Groq (recommended for free cloud testing) |
| `GROQ_DEFAULT_MODEL` | e.g. `llama-3.1-8b-instant` |
| `GEMINI_API_KEY` | Google AI Studio key (production) |
| `GEMINI_DEFAULT_MODEL` | e.g. `gemini-2.0-flash` |
| `UPLOAD_DIR` | Document upload path (default `uploads`) |
| `MEMORY_BUFFER_SIZE` | Redis conversation buffer size (default `10`) |

### Frontend

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | Public FastAPI base URL (no trailing slash) |

### Not required

- **Qdrant** (or any external vector DB) — embeddings live in Postgres + pgvector.
- Ollama is optional and usually local-only; cloud deploys typically use Groq or Gemini.

---

## Checklist

- [ ] Neon has `vector` extension and Orchestra schema
- [ ] Upstash Redis reachable from the backend
- [ ] At least one of `GROQ_API_KEY` or `GEMINI_API_KEY` set
- [ ] `CORS_ORIGINS` includes the Vercel URL
- [ ] `NEXT_PUBLIC_API_URL` points at the deployed API
- [ ] `/health` and `/docs` respond over HTTPS
- [ ] Sign up → create project → chat → Observability shows executions

---

## Local vs cloud

| Concern | Docker Compose | Cloud |
|---------|----------------|-------|
| Postgres | `pgvector/pgvector:pg16` | Neon |
| Redis | `redis:7-alpine` | Upstash |
| API / UI | compose services | Railway/Render + Vercel |
| Secrets | `.env` | Host dashboards |

See the root [README.md](../README.md) for the Docker quick start.
