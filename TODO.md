# TODO

Phases and gates are explained in IMPLEMENTATION.md. "human" marks a step Doug does.

## Phase 1: Foundation

- [x] Rename the project in `pyproject.toml`, add the `life` entry point, and pin dependencies
- [x] Write the frontmatter schema and tree loader, then the three commands below in parallel
- [x] Build `life lint`: schema, enums, dates, size limits, symmetric `related`, journal immutability
- [x] Build `life map`: generate MAP.md from frontmatter
- [x] Build `life query`: filter by kind, domain, tier, status, due, review
- [x] Create `fixture/` with projects, areas, tasks, a person, journal days, and cursors
- [x] Write tests for lint, map, and query against the fixture
- [x] Gate (human): Doug reads a generated MAP.md and approves its shape

## Phase 2: State repository

- [x] Finish `src/life/templates/`: add .gitignore and lint LOCAL.md frontmatter (owner, timezone, sms)
- [x] Build `life init`: create a state repository from `src/life/templates/` with the pin
- [x] Build `life upgrade`: bump the pin and rewrite the managed files
- [x] Tag the first release and push it
- [x] Run `life init` in `life-ddrinka` and push the initial commit
- [x] Seed `life-ddrinka` from conversation with Doug and a research pass
- [ ] Gate: an interactive session in `life-ddrinka` reads the map, edits a project, and pushes

## Phase 3: Scheduled runs

- [ ] Write the `daily-brief`, `weekly-review`, and `monthly-sweep` skills under `src/life/templates/.claude/skills/`
- [ ] Build `life brief`: compose the spoken update from MAP.md and the journal since the last brief
- [ ] Define `cursors/runs.json` fields and run a few manual sessions
- [ ] Create Doug's cloud environment with the state repository and network settings (human)
- [ ] Create the daily and weekly routines, each invoking its skill
- [ ] Merge `src/life/templates/auto-mode.settings.json` into the owner's user settings (human)
- [ ] Test whether a routine runs in auto mode, and whether `mcp__*__send*` deny patterns match
- [ ] Test that a planted instruction in a fixture email is logged in the journal and not acted on
- [ ] Gate: a routine run commits a journal entry and a fresh MAP.md unattended

## Phase 4: Ingestion, each item independent

- [ ] Write the GitHub ingestion skill: turn open issues and PRs assigned to the owner into tasks
- [ ] Connect Google Calendar and Gmail connectors to the cloud environment (human)
- [ ] Create a Google user for agents and share the Drive folders that hold project detail (human)
- [ ] Google Drive reading through the connector, for documents named in `links`
- [ ] Write the calendar ingestion skill: put the next seven days into the map and the brief
- [ ] Write the Gmail ingestion skill: put summaries and message IDs into tasks and the journal
- [ ] Build Gmail triage: label and archive one message at a time per LOCAL.md, with journal entries
- [ ] Replace wildcard connector deny patterns with the connectors' real tool names
- [ ] Gate: the brief mentions an item from each source

## Phase 5: Delivery

- [ ] Create a Twilio account and store its API credential on the environment (human)
- [ ] Build `life send`: text the brief to the `sms` number in LOCAL.md, no recipient argument
- [ ] Add voice delivery for the brief with text-to-speech
- [ ] Gate: Doug receives the daily brief as a text

## Phase 6: Later

- [ ] Build an embedding index for ingestion dedupe, as a mini-project
- [ ] Build two-way voice with its own endpoint, as a mini-project
- [ ] Build agent coordination: status, redirect, and hand-off to agents named in a project file
