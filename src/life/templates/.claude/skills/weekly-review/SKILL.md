---
name: weekly-review
description: Read every focus item and area in full, fix what topic work missed, and re-tier the background work.
---

# Weekly review

This run exists to see the whole picture. Topic work reads one file at a time and misses
what crosses files; this run reads them all.

1. `git switch main` if the checkout is on a detached HEAD, `git pull --rebase`, `uv run life now`, `uv run life journal "run weekly-review started"`.
2. Read `GUIDE.md`, `LOCAL.md`, and `MAP.md` in full.
3. Read every focus project, task, and area in full: `uv run life query --tier focus --format paths`
   and `uv run life query --kind area --format paths`. Read every item whose review date
   has arrived: `uv run life query --review-due --format paths`.
4. For each file read, rewrite State from its `links` where they are cheap to check (an
   issue's status, a repo's last commit), not from the old State. Make `next` the single
   best next action. Add `related` links where two files clearly touch the same work, in
   both directions. Move a focus item to background with a `review` date if nothing can
   happen on it this week, and a background item to focus if its moment has come. Set
   `touched` to today on every file whose content changed.
5. Write one journal entry per file changed, naming the slug and what changed.
6. `uv run life cursor last_weekly_review --set-now`, then `last_run`.
7. `uv run life map`, `uv run life lint`, fix what it reports, commit, push.

Before finishing, confirm: lint passes, the map was regenerated, every changed file has a
journal entry, `next` is current on every focus item, the cursors are updated, and
everything is pushed.
