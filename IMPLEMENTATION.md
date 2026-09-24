# Implementation

This repository is the tooling. It holds the `life` CLI, the guide that agents follow, and
the skills that scheduled runs invoke. It holds no personal data. Each person who uses it
keeps a private state repository, created from the template in `src/life/templates/`. That
repository holds their projects, tasks, journal, and a pin to a released version of this
tooling. Doug's state repository is
[ddrinka/life-ddrinka](https://github.com/ddrinka/life-ddrinka).

- A state repository starts from `src/life/templates/`, and `life upgrade` refreshes those files.
  The rules agents follow inside a state repository are in
  [src/life/templates/GUIDE.md](src/life/templates/GUIDE.md).
- `src/`, `tests/`, and `fixture/` are the tooling. `fixture/` is a small state tree that
  tests run against.
- [TODO.md](TODO.md) and this file track tooling work. A bounded piece of work gets its
  own mini-project directory with its own `TODO.md` and `IMPLEMENTATION.md`, listed under
  Mini-projects below.

The dev container is documented in
[ddrinka/DevContainer](https://github.com/ddrinka/DevContainer).

## Goals

- Doug interacts only through agents. He brings work in conversation and receives short
  updates on a schedule, first as text messages and later as voice calls. He does not
  edit files, open issues, or read Markdown.
- The system runs in the cloud on a schedule. It must not need a dedicated machine.
- The tree holds roughly ten focus projects at a time. It also holds over a hundred
  background projects and tasks, each getting an hour of attention now and then.
- An agent arriving with no memory can pick up the whole picture in one short read.
- Other people can run the same tooling on their own data without seeing Doug's.

## The problem being solved

`TODO.md` and `IMPLEMENTATION.md` work for a project that runs a few weeks. On a longer
project, agents stop reading `IMPLEMENTATION.md` in full. They search for their topic and
miss both the big picture and the work that intersects their topic. Splitting into
mini-projects helped in other repositories because it kept each `IMPLEMENTATION.md`
within an agent's reading length. This repository applies the same idea to open-ended
life tracking.

## Design

### Layers with a reading budget

The tree separates content by how often it changes and how often it must be read.

| Layer | Files | Read when | Size rule |
|---|---|---|---|
| Rules | `GUIDE.md` and `LOCAL.md` | every session | 150 lines |
| Map | `MAP.md`, generated | every session | 150 lines |
| Recent | journal entries since the last run | every session | one file per day |
| Entity | one file per project, area, task, person | when working on it | 120 lines |
| History | journal, archive | on search | unbounded, append-only |

The first three layers are the always-read set. The size rules keep that set inside what
an agent will read in full. `life lint` enforces the limits so the set cannot drift past
the budget.

### Big picture on a schedule

Topic-focused reading is fine for topic-focused work. Seeing intersections is a separate
job, so it gets a separate scheduled run. The weekly review run reads every focus file and
every area, checks that `related` links reflect what it sees, and rewrites `next` lines and
tiers. A daily run never has to hold the whole picture, because the weekly run does.

### Generated map instead of a hand-written dashboard

`life map` builds `MAP.md` from frontmatter. It lists focus projects with their `next`
line, background items whose `review` date has arrived, blocked and waiting items,
overdue tasks, and clusters of `related` items that span domains. A generated file cannot
drift from the entity files and cannot accumulate stale prose.

### One file per entity

Projects, areas, tasks, and people each get one file with frontmatter. Reasons:

- A file is the unit of reading, searching, moving, and archiving. Archiving one is a
  `git mv`.
- Frontmatter gives structured queries without a database.
- Every file has the same shape, so an agent knows where to look and where to write.

Project steps that carry no date and no source stay as a checklist inside the project
file. A step with a due date or a source link becomes a task file, as does anything that
stands on its own. This keeps the file count near the number of things worth tracking
separately.

### Pointers, not copies

A project file holds what an agent needs to act and nothing else. Its `links` list names
where the detail lives: repositories, issues, documents, accounts. An agent reads those
for depth and rewrites State from them, so status is re-derived from the source each run
instead of remembered. Dated facts go in the journal, which cannot go stale because every
line says when it was true. Stable background stays in the linked repositories. There is
no research notes file, because that is the file that rots.

A project's `parent` is an area, and a task's parent is a project or an area, so the tree
is at most three levels deep with no directory nesting. The map groups focus items by
area.

### Questions as the collaboration loop

The owner brings notes, not background. When an agent researches a project and hits
something only the owner knows, it writes a bullet under that file's Questions heading.
The map lists every open question and the brief reads them out. The owner answers in
conversation, and the agent records the answer where it belongs and removes the bullet.

### Files, not GitHub Issues

Files are the source of truth. Issues were rejected as the primary store because bulk
reads go through a paginated API, edits are not versioned in the working tree, and
semantic indexing would export them to files anyway. Nothing enters through Issues,
because Doug enters everything through conversation.

### Two repositories: tooling and state

The tooling is shared; the data is not. Splitting them lets another person run the same
system on a private repository of their own, and keeps a tooling change from landing in
someone's life history.

A state repository contains the tree described in `GUIDE.md` plus four managed pieces:

- `GUIDE.md` itself.
- `.claude/`, holding the skills and a SessionStart hook.
- `pyproject.toml`, which pins this tooling to an exact git tag.
- `CLAUDE.md`, which points agents at `GUIDE.md` and `LOCAL.md` with `@path` imports.
  Those imports resolve in cloud sessions.

`LOCAL.md` holds the person's own rules and facts, and the tooling never overwrites it.
`life upgrade` bumps the pin and rewrites the managed pieces in one commit, so a state
repository stays internally consistent and versioned.

The SessionStart hook runs `uv sync`, so every session and every scheduled run has the
pinned CLI on the path. The routine attaches only the state repository; the tooling
arrives through the pin. Attaching the tooling repository as a second repository would
give the run the default branch rather than a release, so the routine does not do that.

The dev container ignores `CLAUDE.md` through `.git/info/exclude` because it generates
the root one, so `src/life/templates/CLAUDE.md` was added with `git add -f` and stays tracked.

For developing the tooling, this repository carries `fixture/`, a small state tree that
tests run against. For trying changes against live data, clone a state repository into
`state/`, which is ignored.

### Agent-owned tree

The owner never edits the state repository. That removes the merge-conflict problem
between a human editor and a cloud agent. An interactive session and a scheduled run can
still overlap, and the commit protocol in `GUIDE.md` handles that: small commits, rebase
before write, push right away, and regenerate `MAP.md` on conflict.

### Tracking work in this repository

The tooling keeps `TODO.md` and `IMPLEMENTATION.md` at the root. A bounded piece of work
becomes a mini-project with its own pair of files. That practice kept `IMPLEMENTATION.md`
readable in other repositories.

### Delivery

Doug hears each update as spoken language rather than reading a document. `life brief`
composes the message from `MAP.md` and the journal since the last brief. The rule for
length is in `GUIDE.md`: say what needs saying plainly, never drop a caveat or a decision
point for brevity, and leave depth for Doug to ask for. Delivery starts with SMS, then
voice calls with text-to-speech, then two-way voice. The delivery channel is separate
from the brief so the same text can go anywhere.

### Runtime: Claude Code routines

Scheduled runs are Claude Code routines. A routine runs a Claude Code session against the
state repository in a cloud environment on a cron schedule. These facts from the
documentation shape the design:

- A routine clones the attached repositories from their default branch and can run a
  setup script and the repository's SessionStart hooks. `uv` is preinstalled.
  `devcontainer.json` is ignored, so the state repository does not carry one.
- Environment variables belong to a cloud environment and are visible to anyone using it,
  so they hold configuration rather than secrets. API credentials are stored on the
  environment and injected by a proxy for named hosts, so the key never enters the
  session. That feature is on Pro and Max plans and not yet on Team or Enterprise.
- A run can use connected MCP connectors, such as Gmail and Google Calendar. Read-only
  connectors therefore need no OAuth flow built here.
- Commits and pushes carry Doug's GitHub identity. A push to `main` is allowed when the
  branch is unprotected and carries no one else's commits. A state repository is private
  and single-author, so this holds.
- Scheduled triggers run at most hourly. An API trigger with a bearer token can fire a
  routine from outside, which is how an inbound text or call will reach it.
- The prompt lives in the routine definition, not the repository. Each routine's prompt
  is one line that invokes a skill committed under `.claude/skills/`, so the logic is
  versioned and upgraded with the pin.
- Network access defaults to an allowlist. Delivery to Twilio needs either an API
  credential for that host or a custom allowlist.

Each person creates their own cloud environment with their own credentials and
connectors, and their own routines pointing at their state repository. The daily brief
and weekly review are separate routines with separate prompts because they read
different layers of the tree.

Anything that must answer a webhook itself, such as two-way voice, needs a service with
an endpoint. That is a later mini-project, and Fargate is the likely home. A routine's
API trigger covers the simple case of an inbound message that waits for the next run.

### The `life` CLI

`src/life/` holds the package. `model.py` loads a tree into entities and validates
frontmatter against the schema in `GUIDE.md`. `lint.py`, `mapgen.py`, and `query.py` each
implement one command, and `cli.py` wires them together with `argparse`. Every command
takes `--root` for the tree and `--today` to fix the date, so tests are deterministic.

```
uv run life --root fixture --today 2026-09-08 lint
uv run life --root fixture --today 2026-09-08 map --stdout
uv run life --root fixture query --tier focus
uv run life --root fixture query --kind task --due-before 2026-09-15 --format json
uv run pytest -q
```

`life lint` exits 1 and prints one line per problem. Beyond the schema it checks body
heading names and order, slug uniqueness across kinds and against the archive, symmetric
`related` links to open files, `parent` targets, line limits, the tree layout, journal
file names and dates, archived files being done with no links, and `cursors/runs.json`.
When the tree is inside a git checkout, it also checks that no tracked past journal entry
or archive file is modified. Every unreadable or malformed file becomes a lint problem
rather than an exception, and `life map` and `life query` run on a dirty tree without
crashing.

`life map` writes `MAP.md` with these sections:

- Focus items grouped by domain, then by area, each with its `next` line, a stale flag
  when untouched for over a week, and a count of open questions.
- Items of any kind whose `review` date has arrived.
- Blocked and waiting items outside focus.
- Tasks due within seven days.
- Threads, meaning connected groups in the `related` graph that span more than one
  project or area.
- Every open question from every file's Questions section, so the brief can ask them.
- Counts.

Done items are left out.

`life init` builds a state repository in an empty directory: the tree directories, the
managed files, a `LOCAL.md` with this person's frontmatter, an empty `cursors/runs.json`,
a `pyproject.toml` that pins the tooling to a git tag, a generated `MAP.md`, and
`uv.lock`. `life upgrade [VERSION]` rewrites the pin, runs `uv sync` so the new tooling
is installed, then runs `life sync-files` and `life map` from that new install, so the
managed files always come from the version the pin names. `life sync-files` alone
rewrites the managed files from whatever tooling is installed. The templates ship
inside the package under `src/life/templates/`, which is why the package can build a
state repository from a plain install. `LOCAL.md` is never rewritten.

```
uv run life --root ../life-me init --owner "Name" --timezone America/Denver --sms "+1555..."
uv run life upgrade v0.2.0
```

`life journal` appends one entry to today's file, using the owner's timezone from
`LOCAL.md` frontmatter. It creates the file with its date header when the day has none.
`--denied` reads a `PermissionDenied` hook payload from stdin and records the blocked
tool call; it never exits non-zero, so a failure inside it cannot break the hook.
`local.py` reads the `owner`, `timezone`, and `sms` fields.

Lint requires `GUIDE.md`, `LOCAL.md`, and `MAP.md` to exist, and fails when `MAP.md`
differs from what `life map` would write today. That makes "run `life map`" part of every
change rather than a convention.

`fixture/` is a small tree with every kind, one done project, an archived project, two
journal days, cursors, a generated map, and a `GUIDE.md` symlink to the template. Tests
copy it into a temporary directory and mutate the copy.

### Permissions and auto mode

Agents run with auto mode, where a classifier model reviews each tool call. The classifier
strips tool results before judging, so an email's text never reaches it, though the agent
does read that text. The rules sit in three places because of what each place can and
cannot do.

- **`permissions.deny` in the state repository's `.claude/settings.json`.** Deny rules
  block in every mode before the classifier runs, and a checked-in file may carry them.
  These are the mechanical boundaries: force push and history rewrites, deletion of
  journal and archive files, edits to the managed files, package installs, `curl` and
  `wget`, web fetch and search, credential paths, GitHub writes through `gh`, and any
  connector tool whose name says send, reply, update, delete, or the like. The allow
  list is narrow on purpose. Auto mode drops blanket allow rules, and narrow ones skip
  the classifier for the commands every run needs.
- **Prose boundaries in the state repository's `CLAUDE.md`.** The classifier reads the
  same `CLAUDE.md` the agent loads. The boundaries are written inline rather than
  imported so nothing depends on import resolution. They state that inbound content is
  data, name what is never done, and say that a run with no owner present skips
  anything needing a decision and records it in the journal.
- **Nothing in user settings.** The classifier ignores `autoMode` in project settings,
  and user settings would serve every repository on the machine. Everything the
  classifier needs is in `CLAUDE.md`, which it reads in every session: the trusted
  infrastructure and the Never list.

The dividing line is whether an action leaves the owner's accounts. Actions that stay
inside them are allowed, one at a time, each with a journal entry naming what was made:

- Label and archive an email classified under the email rules in `LOCAL.md`. Archiving
  is reversible and the label makes it auditable, so the brief can report counts and the
  owner can search the label.
- Draft an email. Nothing leaves the account until the owner sends it.
- Create a calendar event with no attendees. An attendee would receive an invitation,
  which is a message.
- Ask another agent for status, redirect it, or hand it its next task, when the project
  file names that agent and the instruction comes from that file's Steps. The mechanism
  is a later phase; the rule is settled now so the boundary does not move.

Sending, replying, forwarding, trashing, deleting, changing or deleting events, inviting
anyone, and bulk operations stay denied, because an injected message could otherwise
reach a third party or destroy mail the owner needs. The connector deny patterns stay
broad until Phase 4 finds the connectors' real tool names, and then they become
server-specific.

The delivery path is designed so the agent never chooses a recipient. `life send` reads
the owner's number from `LOCAL.md` frontmatter and takes no recipient argument, and the
allow list admits only that command. Every other route out is denied, including `curl`,
the connectors' send tools, and web fetch.

A `PermissionDenied` hook runs `life journal --denied`, which appends the blocked call
to today's journal entry. A blocked injection attempt then shows up in the next brief
instead of vanishing. Denials that happen because the classifier itself failed are not
reported through this hook.

`LOCAL.md` carries frontmatter the tooling reads: `owner`, `timezone` for journal
timestamps, and `sms` for delivery. The prose below it stays free-form.

One fact is not documented and needs a test in Phase 3: whether `permissions.deny`
patterns match connector tools with a wildcard in the server position. A cloud session
on 2026-09-08 reported that its attempt to attach a second repository "was denied by
the permission classifier", so the classifier is active in cloud sessions.

### Findings from the first cloud session, 2026-09-08

A cloud session against `life-ddrinka` could not run `uv sync`. Its GitHub access is
scoped to the attached repository, so fetching the pinned tooling from the private
`ddrinka/Life` repository failed with "could not read Username for https://github.com".
A plain `git ls-remote` against Life failed the same way while one against life-ddrinka
succeeded. Until this is fixed no `life` command runs in the cloud, so no routine can.
Options, in the order to try:

1. Store a fine-grained GitHub token with read access to Life as an API credential on
   the cloud environment for host `github.com`. The proxy injects it and the repository
   stays private. Unknown whether the injection covers git over HTTPS as well as the API.
2. Attach Life as a second repository and have the session-start hook check out the
   pinned tag in that clone and point `uv` at it through `[tool.uv.sources]`. Keeps the
   pin, at the cost of a hook that knows where the cloud puts a second repository.
3. Make Life public. It holds no personal data, and the local-rules template carries a
   placeholder number, but its agent conventions mention Doug and his repositories.

The claude.ai connectors allow one Gmail connection per user, and Doug has two accounts:
`ddrinka@gmail.com` for personal mail and `ddrinka@ergoncapitalmanagement.com` for work.
Both are reached through `gmail-mcp-relay` in
[ddrinka/Infrastructure](https://github.com/ddrinka/Infrastructure), a Cloudflare Worker
that fronts Google's Gmail MCP server with one path and one bearer token per account and
holds the Google refresh tokens itself. A session adds it as a plain HTTP MCP server; on
the web the cloud environment's API credential carries the bearer, and locally a header
does. The environment attaches one credential per host, so both accounts' relay tokens
hold the same value and one credential reaches both paths. The relay is deployed, and
both accounts passed live tool calls on 2026-09-15. Consumer configuration and the
remaining steps are in that repository's `gmail-mcp-relay/IMPLEMENTATION.md`. The
claude.ai Gmail connector stays off in sessions that use the relay.

### Scheduled runs and the brief

Three skills ship as managed files under `.claude/skills/` in every state repository:
`daily-brief`, `weekly-review`, and `monthly-sweep`. A routine's prompt is the skill's
name. Each skill follows the reading protocol for its layer, journals as it goes, updates
its cursor, regenerates the map, lints, commits, and pushes, and ends with the fixed
checklist.

`life brief` prints the material for the brief and nothing more: the current time in the
owner's zone, every journal entry since the `last_brief` cursor, and the map. The agent
writes the spoken text, because plain speech that keeps every caveat is a language task,
and the material is deterministic so the tooling can be tested. The daily skill saves the
text under `briefs/YYYY/MM-DD.md`, under 40 lines, and `life send` will later text that
file. Keeping the brief in the tree lets the next run see what the owner was already told.

`cursors/runs.json` holds four timestamps: `last_run`, `last_brief`, `last_weekly_review`,
and `last_monthly_sweep`. `life cursor` reads and sets them, `life now` prints the time in
the owner's zone, and lint rejects any other key.

### Semantic index

The semantic index is deferred. Frontmatter queries and `grep` cover the first few hundred
files. When ingestion needs "is this email about something already tracked", add an
embedding index through Voyage AI in sqlite-vec, keyed by file hash and rebuilt
incrementally each run. The index is a build product and is not committed.

## Rejected alternatives

- **GitHub Issues as the store.** See above.
- **A single `LIFE.md`.** It recreates the problem this design solves.
- **One directory per project holding many files.** That is more structure than a
  120-line ceiling needs. A project that needs it gets its own repository.
- **Separate `decisions/` directory for life decisions.** Decisions belong to the project
  they concern and travel with it to the archive. Each one is a single line in the
  project file.
- **Human-facing generated views.** Doug does not read Markdown, so views exist only for
  agents and `MAP.md` is the only one.
- **One repository for tooling and data.** One repository is simpler to clone, but the
  tooling could not be shared without the data, and tooling commits would interleave with
  life history.
- **Attaching the tooling repository to the routine.** That gives the run the default
  branch, not a pinned release. The `uv` pin gives a release.
- **`bypassPermissions` for routines.** It removes the classifier, and the classifier is
  the only check that never reads inbound content.
- **Letting the agent pass a recipient to the delivery tool.** An injected address could
  then be passed straight through. The recipient lives in `LOCAL.md` and nowhere else.

## Phases

Work runs in phases with a gate at the end of each. Items marked "human" need Doug. Items
in the same phase without a stated order can run in parallel.

1. **Foundation.** Build the CLI, the schema, and a fixture tree. Gate: `life lint` passes
   on the fixture, `life map` output reads well to Doug, tests pass.
2. **State repository.** Build `life init` and `life upgrade`, tag the first release, and
   seed Doug's repository from conversation. Gate: an interactive session in
   `life-ddrinka` reads the map, changes a project, and pushes.
3. **Scheduled runs.** Write the daily, weekly, and monthly skills and `life brief`, then
   create Doug's cloud environment and the routines. Gate: a routine run commits a journal
   entry and a fresh map on its own.
4. **Ingestion.** Ingest from GitHub, Calendar, and Gmail, each independent. Gate: the
   brief mentions an item that came from each source.
5. **Delivery.** Deliver by SMS, then by voice. Gate: Doug receives the daily brief as a
   text.
6. **Later.** Build the embedding index, two-way voice, and agent coordination, each a
   mini-project. Agent coordination lets a run check on, redirect, or hand a task to
   another cloud session working on a component of a project.

### Lessons from long-running assistants

Several rules in `GUIDE.md` come from trouble reported around OpenClaw and similar
personal assistants.

- Journal entries are written after each action, because memory written at the end of a
  session is lost when the session dies or compacts.
- The map flags stale focus items, because agents do not update memory unless the
  structure prompts them.
- The size budget on the always-read layer exists because loading many workspace files
  every turn degraded those assistants.
- Runs are daily and weekly with no polling routine, because frequent heartbeats were a
  cost trap.
- Inbound text is treated as data, because an assistant that reads email and holds tools
  is a prompt-injection target.
- Each run establishes the time in the owner's timezone, because cloud runs are in UTC.
- Each skill ends with a fixed checklist, which keeps the goal in view late in a long
  context.

## Mini-projects

There are none yet.

## Known limitations

- The immutability check reads `git status` only, so it cannot see an edit that has
  already been committed to a past journal day or an archived file. When the tree is not
  inside a git checkout, the check is skipped without notice.
- Lint does not check the size of archived files, which stay frozen as they were.
- Lint does not check that a `Decisions` line is dated, or that today's journal file was
  only appended to.
- Duplicate YAML keys in frontmatter are accepted, and the last value wins.
- The cloud documentation does not state a maximum run duration or the daily run cap.
- Two-way voice is far off and will need its own mini-project.
