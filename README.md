# Life

Life is tooling that keeps Doug's life organized through agents. Agents read email,
calendars, and GitHub. They keep projects moving, track priorities, and report
back in a few sentences by text or voice. The system runs in the cloud on a schedule.

This repository holds the tooling only. Each person keeps their data in a private state
repository, created from `templates/` and pinned to a release of this tooling.

- `templates/` is the starting point for a state repository. The rules agents follow
  inside a state repository are in [templates/GUIDE.md](templates/GUIDE.md).
- `src/` holds the `life` CLI that lints a tree, builds the map, composes briefs, and
  upgrades a state repository to a new tooling release.
- `fixture/` is a small state tree that tests run against.

Work on the tooling is tracked in [TODO.md](TODO.md) and explained in
[IMPLEMENTATION.md](IMPLEMENTATION.md). Repository-specific agent conventions are in
[AGENTS.md](AGENTS.md).

Dependencies go through `uv` and are pinned in `pyproject.toml` and `uv.lock`. The dev
container comes from [ddrinka/DevContainer](https://github.com/ddrinka/DevContainer).
