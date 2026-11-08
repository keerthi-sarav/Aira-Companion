# Aira Companion dashboard

Next.js 14 (App Router), TypeScript and Tailwind. It manages companion characters and test-chats them against the FastAPI backend in `../backend`. The API contract is `../docs/ARCHITECTURE.md`.

## Run

```bash
cp .env.example .env.local   # optional, the defaults match the backend dev setup
npm install
npm run dev                  # http://localhost:3000
```

The backend must be running at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL |
| `NEXT_PUBLIC_TENANT_ID` | `astrotamil` | Sent as `X-Tenant-Id` |
| `NEXT_PUBLIC_DEV_USER_ID` | `owner-1` | Sent as `X-User-Id`; test chat uses `owner-test:<id>` |

## Layout

- `src/lib/api.ts` is the only place that calls the backend. It throws `ApiError` with `status`, `error` and `message`.
- `src/lib/types.ts` mirrors the backend Pydantic schemas.
- `src/app/` holds the pages: the character list, `companions/new`, and `companions/[id]` (edit, status, delete, test chat).
- `src/components/` holds `CharacterForm`, `TestChat`, `MoodBadge` and `StatusBadge`.

## Scripts

- `npm run dev` starts the dev server.
- `npm run build` creates a production build.
- `npm run lint` runs ESLint.
- `npx tsc --noEmit` type-checks the project.
