# Active Roadmap & Technical Debt

Roadmap follows the flow spec's week labels.

## Backlog
| task | priority | status |
|---|---|---|
| Week 1 core: engine, prompt layers, mood, tool pause, forget, CRUD + test-chat API, dashboard | P0 | in progress (base architecture) |
| Week 2 `companion-chat-api`: public endpoint, secret keys, widget, per-user rate limits, server tool example | P1 | todo |
| Week 2 `companion-memory`: Mem0 Level 2 (self-hosted) behind `MemoryProvider` | P1 | todo |
| Wire real knowledge base behind `KnowledgeProvider` (tag + untagged books) | P1 | todo |
| Week 3 dashboard: chat reader (privacy A) / stats only (privacy B), book management | P2 | todo |
| Week 3 Anril super-admin: clients, plans, usage, AI cost, kill switch (no chat access) | P2 | todo |
| Billing: ₹6,000/month + ~₹2/session, capped ₹15k; token metering (`tenant_token_usage`) | P3 | later |
| Re-check Tele-MANAS 14416 before launch | P1 | todo |

## Known Tech Debt
- `core/auth.py` is dev header auth (`X-Tenant-Id`/`X-User-Id`) — replace with real auth + `settings.manage` permission before any deploy.
- No Alembic migrations — tables are created with `create_all` on startup.
- Postgres RLS (enabled, no policies) not set up; only app-level tenant filtering.
- Global in-process semaphore — won't hold across multiple workers/instances.
