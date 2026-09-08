# Python 3.13 Agentic Template

This repository is a GitHub template for Python 3.13 projects built with Claude Code and
an agent team. The dev container comes from
[ddrinka/DevContainer](https://github.com/ddrinka/DevContainer). Before the container
builds, `.devcontainer/devcontainer.json` clones that repository into
`.devcontainer/base`. The base supplies the image, Claude Code, the agent definitions,
and the shared `AGENTS.md` conventions. This repository adds only two things:
`on_update.sh`, which runs `uv sync`, and the Docker-in-Docker feature.

Dependencies go through `uv` and are pinned in `pyproject.toml` and `uv.lock`.

Work is tracked in [TODO.md](TODO.md) and explained in [IMPLEMENTATION.md](IMPLEMENTATION.md).
Repository-specific agent conventions live in [AGENTS.md](AGENTS.md).

## Starting a project from this template

1. Create a repository from the template and open it with **Clone Repository in Container Volume**.
2. Rename the project in `pyproject.toml` and run `uv lock`.
3. Replace this README, and fill in `TODO.md` and `IMPLEMENTATION.md`.
