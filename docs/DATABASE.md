# Database — Days 1–6 Schema

## ER diagram

```text
User 1──<N Project 1──<N Agent
                   │
                   ├──<N Conversation 1──<N Message
                   │
                   └──<N KnowledgeBase 1──<N Document 1──<N DocumentChunk
                                                              (embedding vector)
```

## Day 6 — Knowledge base tables

### `knowledge_bases`

| Column | Type | Notes |
|--------|------|--------|
| id | integer PK | |
| project_id | FK → projects | CASCADE delete |
| name | varchar(255) | |
| description | text | optional |
| created_at / updated_at | timestamptz | |

### `documents`

| Column | Type | Notes |
|--------|------|--------|
| id | integer PK | |
| knowledge_base_id | FK → knowledge_bases | CASCADE delete |
| filename | varchar(512) | original upload name |
| content_type | varchar(128) | optional MIME |
| file_path | varchar(1024) | stored file location |
| status | varchar(32) | `pending`, `processing`, `processed`, `failed` |
| chunk_count | integer | set after ingestion |
| embedding_status | varchar(32) | `pending`, `generated`, `failed` |
| error_message | text | set on failure |
| created_at / updated_at | timestamptz | |

### `document_chunks`

| Column | Type | Notes |
|--------|------|--------|
| id | integer PK | |
| document_id | FK → documents | CASCADE delete |
| chunk_index | integer | order within document |
| content | text | chunk text |
| chunk_metadata | jsonb | char offsets, page hints, etc. |
| embedding | vector(384) | pgvector — `BAAI/bge-small-en-v1.5` |
| created_at | timestamptz | |

Postgres uses the **pgvector** extension (`CREATE EXTENSION vector`). Docker image: `pgvector/pgvector:pg16`.

## Day 4 note

**No tool tables.** Tools live in process memory via `ToolRegistry`.  
Tool calls are shown live over SSE; only `user` / `assistant` messages are persisted (ADR-011 / ADR-013).

## Tables (Day 3)

### `conversations`

| Column | Type | Notes |
|--------|------|--------|
| id | integer PK | |
| project_id | FK → projects | CASCADE delete |
| agent_id | FK → agents | SET NULL, optional |
| title | varchar(255) | Auto from first user message |
| model_name | varchar(100) | Last selected model |
| created_at / updated_at | timestamptz | |

### `messages`

| Column | Type | Notes |
|--------|------|--------|
| id | integer PK | |
| conversation_id | FK → conversations | CASCADE delete |
| role | varchar(32) | `user` or `assistant` (system injected at request time) |
| content | text | |
| created_at | timestamptz | |

## Why separate conversations and messages?

One conversation has many turns. Storing a blob of text is messy and hard to query/replay.  
Normalized messages scale to evaluation, cost tracking, and RAG citations later.

## Earlier tables

Unchanged: `users`, `projects`, `agents` (Days 1–2).

## Future (Day 7+)

RAG retrieval queries over `document_chunks.embedding`. Day 9 may add execution / tool-trace tables for observability.
