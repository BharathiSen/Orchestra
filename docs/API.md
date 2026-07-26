# API Contracts — Day 1

Base URL (Docker Day 1 defaults): `http://localhost:18000`  
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

**Auth required**

**Response 200** — `UserOut`

---

## Projects

All project routes require Bearer JWT. Results are scoped to the current user.

### `POST /api/v1/projects`

```json
{ "name": "Support bots", "description": "Day 1 workspace" }
```

**Response 201** — `ProjectOut`

### `GET /api/v1/projects`

**Response 200** — `ProjectOut[]` (newest first)

### `GET /api/v1/projects/{id}`

**Response 200** — `ProjectOut`  
**404** if missing or not owned

### `PATCH /api/v1/projects/{id}`

```json
{ "name": "Updated name", "description": "Optional" }
```

### `DELETE /api/v1/projects/{id}`

**Response 204** No Content

---

## JWT claims

| Claim | Meaning |
|-------|---------|
| `sub` | User id (string) |
| `email` | User email |
| `exp` | Expiry (UTC) |
