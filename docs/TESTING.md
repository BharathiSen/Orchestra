# Orchestra — Manual testing (Days 1–2)

Shared checklist for verifying the platform foundation.  
Local scratch notes may live in `manual_testing.md` (gitignored).

## URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:13000 |
| Swagger | http://localhost:18000/docs |
| Health | http://localhost:18000/health |

```bash
cd docker
docker compose --env-file ../.env up -d
docker compose ps
```

**Auth:** no default admin — **Sign up** first, then login.

---

## Day 1

- [ ] Docker starts (all 4 services Up)
- [ ] `GET /health` → `{"status":"ok"}`
- [ ] Signup / login / JWT
- [ ] Invalid password → 401
- [ ] Protected route without token → 401
- [ ] Project create / edit / delete
- [ ] UI: Login → Dashboard → Projects

---

## Day 2

- [ ] User can log in
- [ ] User sees only their own projects (second user cannot open first user’s project → 404)
- [ ] User can create an agent (UI or `POST /api/v1/agents`)
- [ ] User can edit an agent (UI or `PATCH /api/v1/agents/{id}`)
- [ ] User can delete an agent (UI or `DELETE /api/v1/agents/{id}`)
- [ ] Invalid JWT → 401 on `/api/v1/agents`
- [ ] Agent with `project_id: 999999` → 404
- [ ] Agent with `"name": ""` → 422

### Day 2 Swagger map

| Check | Endpoint |
|-------|----------|
| Login | `POST /api/v1/auth/login` |
| Create agent | `POST /api/v1/agents` |
| Edit agent | `PATCH /api/v1/agents/{id}` |
| Delete agent | `DELETE /api/v1/agents/{id}` |
| Bad JWT | `GET /api/v1/agents` (no/bad token) |
| Bad project | `POST /api/v1/agents` with nonexistent `project_id` |
| Validation | `POST /api/v1/agents` with empty `name` |

### UI path

Login → Dashboard (project cards) → open project → Create / Edit / Delete agent
