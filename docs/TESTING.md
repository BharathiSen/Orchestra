# Shared Testing Checklist (Days 1-3)

Use this checklist before creating a PR.

## Day 1 - Platform Foundation

- [ ] Docker services start (`frontend`, `backend`, `postgres`, `redis`)
- [ ] `GET /health` returns `{ "status": "ok" }`
- [ ] Signup works (`POST /api/v1/auth/signup`)
- [ ] Login works (`POST /api/v1/auth/login`)
- [ ] Invalid password returns `401`
- [ ] Protected route rejects invalid JWT with `401`
- [ ] Projects CRUD works end to end

## Day 2 - Agents

- [ ] Create agent under owned project
- [ ] List agents (all + by `project_id`)
- [ ] Update agent fields (`name`, `system_prompt`, `model_name`)
- [ ] Delete agent returns `204`
- [ ] Agent creation on non-owned/non-existent project fails (`404`)

## Day 3 - Chat, Streaming, Conversations

- [ ] `GET /api/v1/chat/models` returns `models`, `provider`, and `llm_configured`
- [ ] `POST /api/v1/chat` streams SSE events (`meta`, `user_message`, `token`, `done`)
- [ ] User and assistant messages persist in DB
- [ ] Conversation list reloads correctly
- [ ] Agent/system prompt changes response behavior
- [ ] Invalid provider credentials produce clear error handling

## Notes

- Detailed manual step-by-step checks live in local-only `docs/manual_testing.md`.
- Private engineering notes stay in local-only `docs/INTERVIEW_NOTES.md`.
