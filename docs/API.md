# API Contracts — Days 1–2

Base URL (Docker defaults on this machine): `http://localhost:18000`  
API prefix: `/api/v1`  
Interactive docs: `/docs`

Auth header for protected routes:

```http
Authorization: Bearer <access_token>
```

---

## Health

### `GET /health`

**Response 200**

```json
{ "status": "ok" }
```

---

## Auth

### `POST /api/v1/auth/signup`

**Body**

```json
{
  "email": "ada@example.com",
  "password": "password123",
  "full_name": "Ada Lovelace"
}
```

**Response 201**

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "ada@example.com",
    "full_name": "Ada Lovelace",
    "created_at": "2026-07-26T12:00:00Z"
  }
}
```

### `POST /api/v1/auth/login`

**Body**

```json
{ "email": "ada@example.com", "password": "password123" }
```

**Response 200** — same shape as signup.

**Errors**: `401` invalid credentials; `400` email already registered (signup).

### `GET /api/v1/auth/me`

**Auth required** — **Response 200** `UserOut`

---

## Projects

All project routes require Bearer JWT. Scoped to current user.

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/v1/projects` | Create |
| GET | `/api/v1/projects` | List own |
| GET | `/api/v1/projects/{id}` | Get one |
| PATCH | `/api/v1/projects/{id}` | Update |
| DELETE | `/api/v1/projects/{id}` | Delete (204) |

**POST body**

```json
{ "name": "Support bots", "description": "Workspace" }
```

---

## Agents (Day 2)

All agent routes require Bearer JWT. Access is authorized via project ownership.

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/v1/agents` | Create |
| GET | `/api/v1/agents` | List (optional `?project_id=`) |
| GET | `/api/v1/agents/{id}` | Get one |
| PATCH | `/api/v1/agents/{id}` | Update |
| DELETE | `/api/v1/agents/{id}` | Delete (204) |

### `POST /api/v1/agents`

```json
{
  "name": "Research assistant",
  "project_id": 1,
  "description": "Finds sources",
  "system_prompt": "You are a careful researcher.",
  "model_name": "gpt-4o-mini"
}
```

**Response 201** — `AgentResponse`

**Errors**
- `401` missing/invalid JWT
- `404` project not found or not owned
- `422` validation (missing name, invalid types)

### `GET /api/v1/agents?project_id=1`

Filter to one project. Without query — all agents across the user’s projects.

### `PATCH /api/v1/agents/{id}`

```json
{
  "name": "Updated name",
  "system_prompt": "New instructions",
  "model_name": "gpt-4o-mini"
}
```

### `DELETE /api/v1/agents/{id}`

**204** No Content

---

## JWT claims

| Claim | Meaning |
|-------|---------|
| `sub` | User id (string) |
| `email` | User email |
| `exp` | Expiry (UTC) |
