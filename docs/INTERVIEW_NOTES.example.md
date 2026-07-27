# Interview Notes Template (Do Not Put Secrets)

This file is the public template for local interview prep notes.

## How to use

1. Copy this file to `docs/INTERVIEW_NOTES.md` locally.
2. Keep `docs/INTERVIEW_NOTES.md` gitignored.
3. Record architecture rationale, debugging stories, and tradeoffs.

## Suggested sections

- Day-wise implementation summary
- Why specific architecture decisions were made
- Failure cases and how they were fixed
- Testing evidence (API + UI)
- Security and production hardening follow-ups

## Example prompts to prepare

- Explain JWT auth flow from frontend to backend.
- Why use repository/service layers in FastAPI?
- How does SSE streaming improve chat UX?
- How are conversations/messages modeled and persisted?
- How does provider abstraction (Gemini/Groq/Ollama) reduce vendor lock-in?
