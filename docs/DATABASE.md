# Database — Day 1 Schema

## ER diagram

```text
┌──────────────────────────┐         ┌──────────────────────────────┐
│          users           │         │           projects           │
├──────────────────────────┤         ├──────────────────────────────┤
│ id           PK SERIAL   │◄──┐     │ id            PK SERIAL      │
│ email        UNIQUE      │   │     │ name          VARCHAR(255)   │
│ hashed_password          │   └─────│ owner_id      FK → users.id  │
│ full_name    NULLABLE    │         │ description   TEXT NULL      │
│ created_at   TIMESTAMPTZ │         │ created_at    TIMESTAMPTZ    │
└──────────────────────────┘         │ updated_at    TIMESTAMPTZ    │
                                     └──────────────────────────────┘

Relationship: User 1 ──< N Project (cascade delete)
```

## Tables

### `users`

| Column | Type | Notes |
|--------|------|--------|
| id | integer PK | Auto-increment |
| email | varchar(255) | Unique, stored lowercase |
| hashed_password | varchar(255) | bcrypt hash |
| full_name | varchar(255) | Optional |
| created_at | timestamptz | Server default `now()` |

### `projects`

| Column | Type | Notes |
|--------|------|--------|
| id | integer PK | Auto-increment |
| name | varchar(255) | Required |
| description | text | Optional |
| owner_id | integer FK | → `users.id` ON DELETE CASCADE |
| created_at | timestamptz | Server default |
| updated_at | timestamptz | Updated on change |

## Bootstrap

- `database/init.sql` runs on first Postgres container init (`pgcrypto` extension).
- SQLAlchemy `Base.metadata.create_all` runs on FastAPI startup (Day 1 simplicity).
- Alembic is in dependencies for Day 2+ migration discipline.

## Day 2+ (preview)

`agents` table (and later conversations, messages, knowledge bases) will hang off `projects.id`.
