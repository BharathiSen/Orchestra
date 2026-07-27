# Database — Days 1–2 Schema

## ER diagram

```text
┌──────────────────────────┐
│          users           │
├──────────────────────────┤
│ id           PK          │
│ email        UNIQUE      │
│ hashed_password          │
│ full_name                │
│ created_at               │
└────────────┬─────────────┘
             │ 1
             │
             │ N
┌────────────▼─────────────┐         ┌──────────────────────────────┐
│         projects         │         │            agents            │
├──────────────────────────┤         ├──────────────────────────────┤
│ id           PK          │◄──┐     │ id            PK             │
│ name                     │   │     │ name                         │
│ description              │   └─────│ project_id    FK → projects  │
│ owner_id     FK → users  │         │ description                  │
│ created_at               │         │ system_prompt                │
│ updated_at               │         │ model_name                   │
└──────────────────────────┘         │ created_at                   │
                                     │ updated_at                   │
                                     └──────────────────────────────┘

User 1 ──< N Project 1 ──< N Agent
(cascade delete on both FKs)
```

## Tables

### `users`

| Column | Type | Notes |
|--------|------|--------|
| id | integer PK | Auto-increment |
| email | varchar(255) | Unique, lowercase |
| hashed_password | varchar(255) | bcrypt |
| full_name | varchar(255) | Optional |
| created_at | timestamptz | Server default |

### `projects`

| Column | Type | Notes |
|--------|------|--------|
| id | integer PK | |
| name | varchar(255) | Required |
| description | text | Optional |
| owner_id | integer FK | → `users.id` ON DELETE CASCADE |
| created_at / updated_at | timestamptz | |

### `agents` (Day 2)

| Column | Type | Notes |
|--------|------|--------|
| id | integer PK | |
| name | varchar(255) | Required |
| description | text | Optional |
| system_prompt | text | Default `""` — used from Day 3+ |
| model_name | varchar(100) | Default `gpt-4o-mini` — selection later |
| project_id | integer FK | → `projects.id` ON DELETE CASCADE |
| created_at / updated_at | timestamptz | |

## Bootstrap

- `database/init.sql` on first Postgres init
- SQLAlchemy `create_all` on FastAPI startup creates/updates missing tables
- Day 2 agents table appears automatically on backend restart

## Day 3+ preview

`conversations`, `messages` hang off agents/projects for chat + streaming.
