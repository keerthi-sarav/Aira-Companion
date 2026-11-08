# Identity, Dev Persona & Code Style

## Who is working on this
- Owner: keerthi-sarav (GitHub) — building Aira Companion, a new product under Anril.
- Dev on Windows 11 (PowerShell + Git Bash). Use `python` (3.13), not `python3` (that's the MS Store stub). No `make` installed.
- Leans on the agent for scaffolding and builds; uses a multi-model flow: **Haiku builds, Opus reviews**.

## Response Conventions
- Short, plain status updates. Recommend, don't survey options.
- Reference code as clickable `path:line`.
- Ask before pushing to GitHub or doing anything outward-facing that isn't already authorized.

## Code Style Rules
- Backend: Python 3.11+, type hints everywhere, Pydantic v2 for every request/response, async SQLAlchemy 2.0. Domain errors are exceptions in `companion/errors.py` mapped to `{"error","message"}` JSON — never raise bare `HTTPException` from engine/store code.
- Frontend: TypeScript strict, Next.js App Router, Tailwind. API calls only through `src/lib/api.ts`; types mirror backend schemas in `src/lib/types.ts`.
- Names in `docs/ARCHITECTURE.md` (tables, functions, error codes, routes) are a contract — don't rename without updating the doc and [[decisions/log]].
