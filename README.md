# Aira Companion

AI character companions that businesses configure and embed in their own apps. The example tenant is **Astrotamil**, with **Jothidar AI** (a Vedic astrologer who speaks Tanglish) and **Vastu Guru** (a vastu expert who speaks Tamil).

- **frontend/**: a Next.js dashboard for creating characters, editing their cards, and test-chatting them, including the tool-pause flow
- **backend/**: a FastAPI + Pydantic engine that handles tenant checks, books and history, a layered safety prompt, the LLM call, mood tracking, app-side tool pause/continue, and "forget me"

The architecture and build contract are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

```bash
# backend (http://localhost:8000, docs at /docs)
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"     # macOS/Linux: .venv/bin/python
cp .env.example .env                                 # LLM_PROVIDER=fake works with no API key
.venv/Scripts/python -m uvicorn app.main:app --reload

# frontend (http://localhost:3000)
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

To use a real model, set `LLM_PROVIDER=openai_compat` along with `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` in `backend/.env`. Any OpenAI-compatible endpoint works (Groq, Gemini, Sarvam, and so on).

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest -q
```

## Status

This is the week-1 base: the engine, CRUD, and the test-chat dashboard. The public widget API, Mem0 memory, the real knowledge base, and the admin screens are on the roadmap in `.agents/projects/active-backlog.md`.
