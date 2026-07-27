# Database — Days 1–4 Schema

## ER diagram

```text
User 1──<N Project 1──<N Agent
                   │
                   └──<N Conversation 1──<N Message
```

## Day 4 note

**No new tables.** Tools live in process memory via `ToolRegistry`.  
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

## Future (not Day 4)

Day 9 may add execution / tool-trace tables for observability.
