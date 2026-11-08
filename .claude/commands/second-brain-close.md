---
name: second-brain-close
description: Session-end second-brain check — routes new knowledge, verifies the brain is healthy
---

Run `python scripts/second_brain_close.py --write-report` (Windows: no `make`, and `python3` is the MS Store stub)
and report its findings. Then, from this session's conversation:

1. Route new knowledge (do NOT dump everything into one place):
   - Settled project facts (decisions, architecture, fixes, migrations) -> `.agents/decisions/log.md`
   - Load-bearing gotchas / how-a-subsystem-works -> `.agents/context/subsystem-notes.md`
   - Open items / tech debt -> `.agents/projects/active-backlog.md`
   - Personal working-style preferences (not project facts) -> personal/global memory, if one exists
2. If the script reported dead links, stale claims, or credential matches: fix or flag each
   one explicitly — do not silently ignore findings.
3. If code changed this session, run this project's wiki/graph refresh target now.
4. Show `git status` / `git diff --stat` and ask before committing or deleting anything.
