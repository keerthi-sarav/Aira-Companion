# Aira Companion

AI character companions for businesses (example tenant: Astrotamil). Next.js dashboard (`frontend/`) + FastAPI/Pydantic engine (`backend/`). Build contract: `docs/ARCHITECTURE.md`.

Run locally:
- Backend: `cd backend && python -m pip install -e ".[dev]" && python -m uvicorn app.main:app --reload` (port 8000)
- Frontend: `cd frontend && npm install && npm run dev` (port 3000)
- Tests: `cd backend && python -m pytest -q`
- Session end: `python scripts/second_brain_close.py --write-report` (or `/second-brain-close`)

## How to Work Efficiently (low context — this is the DEFAULT, no need to be told)
- The brain is **queried, not loaded**. Never read whole files or the whole `.agents/` tree "to get context."
- Lookup order for ANY task: (1) the ONE relevant `.agents/` file the task scope points to below, (2) at most 2–3 targeted reads. Full-file reads are the last resort.
- Pull ONLY the `.agents/` file the task scope points to — never preload all of them.
- This runs automatically for every task; the user does NOT have to say "use the second brain."

## Agent Routing Instructions
To prevent context dilution, general invariants and rules are split into modular guides. **Always read these files first based on the scope of your task:**

1.  **Identity, Dev Persona & Code Style Rules**:
    *   Location: `.agents/context/identity.md`
    *   Read when: Starting a new session or reviewing coding style, formatting, and response conventions.
2.  **Invariants, Tech Stack & File Map**:
    *   Location: `.agents/context/stack-and-rules.md`
    *   Read when: Touching tenant-scoped DB queries, the prompt builder / platform rules, the tool-pause flow, or "forget me" deletion.
3.  **Historical Decisions & Migrations**:
    *   Location: `.agents/decisions/log.md`
    *   Read when: Seeking context on why a module was built/dropped, or checking migration history.
4.  **Active Roadmap & Technical Debt**:
    *   Location: `.agents/projects/active-backlog.md`
    *   Read when: Checking current backlog tasks or known tech debt.
5.  **Subsystem Notes & Load-Bearing Gotchas**:
    *   Location: `.agents/context/subsystem-notes.md`
    *   Read when: Editing a specific subsystem — holds the *why* and traps the code/wiki can't.
