---
name: monthly-sweep
description: Archive done files, prune stale links, enforce the size limits, and leave the tree clean.
---

# Monthly sweep

1. `git pull --rebase`, `uv run life now`, `uv run life journal "run monthly-sweep started"`.
2. Read `GUIDE.md`, `LOCAL.md`, and `MAP.md` in full.
3. `uv run life query --status done --format paths` lists what to archive. For each file:
   clear its `related` list, remove its slug from every other file's `related`, then
   `git mv` it under `archive/<kind>/`. Write one journal entry per file archived.
4. `uv run life lint`. For any file over its line limit, move history into the journal
   and shorten decisions to one line each, then lint again.
5. Every background or someday item without a `review` date gets one, no more than a
   month out.
6. `uv run life cursor last_monthly_sweep --set-now`, then `last_run`.
7. `uv run life map`, `uv run life lint`, commit, push.

Before finishing, confirm: lint passes, the map was regenerated, every archived file has a
journal entry, the cursors are updated, and everything is pushed.
