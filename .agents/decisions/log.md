# Historical Decisions & Migrations

## Migration Index
| date | migration file | what changed |
|---|---|---|
| 2026-11-08 | (none — `create_all` on startup) | Initial 5 tables: companions, companion_end_users, companion_conversations, companion_messages, companion_pending_turns. Alembic is deferred. |

## Decisions
| date | decision | why | rejected |
|---|---|---|---|
| 2026-11-08 | Next.js frontend + FastAPI/Pydantic backend | Owner's chosen stack | — |
| 2026-11-08 | Standalone repo `keerthi-sarav/Aira-Companion`, companion code in its own `companion/` package | Flow spec says it should be able to spin out of Anril later | Building inside the Anril monorepo |
| 2026-11-08 | Knowledge base and memory behind provider protocols with stub implementations | The Anril knowledge service and Mem0 aren't in this repo yet; keep the engine testable | Hard-coding a vector DB now |
| 2026-11-08 | App-side tools via pause/continue (`tool_call` → `continue`) | Client keeps its own tools and secrets; we never call their servers | Storing client tool configs/secrets in our dashboard |
| 2026-11-08 | Platform/industry rules in code, not DB | No tenant setting can weaken safety rules | Configurable rules table |
| 2026-11-08 | `FakeLLM` as default provider | Runs and tests with no API key | Requiring a real key for local dev |
| 2026-11-08 | Build with Haiku subagents, review with Opus | Owner's request | — |
