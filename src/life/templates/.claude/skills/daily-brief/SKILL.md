---
name: daily-brief
description: Produce today's spoken-language brief for the owner from the map and the journal, and record the run.
---

# Daily brief

Read `GUIDE.md`, `LOCAL.md`, and `MAP.md` in full before anything else. This run reads
the always-read layer only; it does not open project files unless a journal entry since
the last brief makes one necessary.

1. `git pull --rebase`, then `uv run life now` to establish the time in the owner's zone.
2. `uv run life journal "run daily-brief started"`.
3. `uv run life brief` prints the material: the time, journal entries since the last
   brief, and the map.
4. Write the brief in spoken language, as `GUIDE.md`'s "Speaking to the owner" section
   says. Cover, in this order and only when there is something to say: anything overdue
   or due within a week, anything blocked or waiting on the owner, what changed since the
   last brief, stale focus items, and open questions on focus items. Say what needs
   saying plainly; never drop a caveat or a decision point to be short. Skip anything the
   owner already knows and nothing has changed on. No headings, no bullets, no slugs:
   it will be read aloud or texted.
5. Save it to the path `uv run life brief --path` prints, creating the directories. Keep
   it under 40 lines.
6. `uv run life cursor last_brief --set-now`, then `uv run life cursor last_run --set-now`.
7. `uv run life journal "run daily-brief: brief written to briefs/..."`.
8. `uv run life map`, then `uv run life lint`, and fix anything it reports.
9. Commit everything and push. If the push is rejected, rebase and push again.

Before finishing, confirm: lint passes, the map was regenerated, the journal has an entry
for every action taken, the cursors are updated, and everything is pushed.
