# Subsystem Notes & Load-Bearing Gotchas

## Engine (`backend/app/companion/engine.py`)
- `reply()` runs knowledge, memory and history lookups in parallel; a knowledge failure must degrade to `""`, never fail the reply.
- History is filtered by **companion_id AND end_user_id** — characters share the person row, never chats or mood (see flow tab 5).
- Conversations roll over after 24 h of silence; mood carries over to the new conversation.
- LLM failure → `companion.fallback_line`, mood unchanged. Missing `[mood: X]` tag → previous mood kept.
- Test-chat uses external user `owner-test:<user_id>` and is allowed on `draft` companions; real traffic requires `live`.

## Tool pause (`engine.continue_reply`)
- The semaphore slot must be released before returning `status="tool_call"`, otherwise 4 paused turns deadlock the server.
- Expired pending turns are swept on every create **and** every continue. Unknown / expired / other-tenant turn → `TurnExpired` (404).
- Tool results go in as `role="tool"` data messages (rule 8: data, not orders). Missing result → `"tool unavailable"`. Output capped at 4000 chars.

## Prompt (`backend/app/companion/prompt.py`)
- Section fencing is the injection defense: a backstory saying "ignore all rules above" must stay inside the Character box. Don't flatten sections into one string without labels.

## Week-1 seams (deliberate stubs)
- `KnowledgeProvider` → `NullKnowledge` until the real Anril knowledge base is wired (`campaign_tag_id = knowledge_tag_id`).
- `MemoryProvider` → `Level1History` (returns `""`); Mem0 Level 2 is week 2. See [[active-backlog]].
- `core/auth.py` header auth is dev-only. See [[active-backlog]].
