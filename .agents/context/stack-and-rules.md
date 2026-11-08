# Invariants, Tech Stack & File Map

Full contract: `docs/ARCHITECTURE.md`. This file is the short list of things that must not break.

## Tech Stack
- Frontend: Next.js (App Router) + TypeScript + Tailwind — `frontend/`
- Backend: FastAPI + Pydantic v2 + pydantic-settings + SQLAlchemy 2.0 async — `backend/`
- DB: SQLite (`aiosqlite`) in dev, Postgres (`asyncpg`) in prod via `DATABASE_URL`
- LLM: OpenAI-compatible chat API via `httpx` (Groq/Gemini/Sarvam); `FakeLLM` (`LLM_PROVIDER=fake`) for dev/tests
- Repo: https://github.com/keerthi-sarav/Aira-Companion

## Hard Invariants
1. **Tenant isolation**: every companion query filters `tenant_id`. Another tenant's id → 404 (not 403).
2. **Platform + industry rules live in code only** (`companion/platform_rules.py`), never in the DB, and always come first in the prompt. Business/user text is fenced inside its own section.
3. **Prompt layer order is fixed**: platform → industry → character → mood → output → knowledge → about-user → history → new message.
4. **Tool outputs are never persisted** — `companion_messages.tool_calls` stores names + args only.
5. **No message text in logs.** Anril staff/operator views never expose companion chats or memories.
6. **Forget me** hard-deletes messages, conversations and pending turns across all characters of that tenant, nulls `display_name`, stamps `forgotten_at`. Never crosses tenants.
7. Concurrency: max `COMPANION_MAX_CONCURRENT` (4) replies at once, 5 s wait → 503. Slot is released while a turn is paused for a tool.
8. Tool pause: pending turn expires after 2 min; max 3 rounds; round 3 is sent without tools.

## File Map
- `backend/app/main.py` — app, CORS, lifespan, `/health`
- `backend/app/core/` — `config.py`, `db.py`, `auth.py` (dev header auth `X-Tenant-Id`/`X-User-Id`)
- `backend/app/companion/` — self-contained module: `models`, `schemas`, `errors`, `platform_rules`, `prompt`, `mood`, `memory`, `knowledge`, `llm`, `store`, `engine`, `router`
- `backend/tests/` — pytest (uses FakeLLM)
- `frontend/src/lib/` — `api.ts`, `types.ts`
- `frontend/src/app/` — `/` list, `/companions/new`, `/companions/[id]` (edit + test chat)
- `frontend/src/components/` — `CharacterForm`, `TestChat`, `MoodBadge`
