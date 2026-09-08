"""Create a state repository and keep its managed files matched to the installed tooling."""

from __future__ import annotations

import importlib.metadata
import json
import shutil
import subprocess
from pathlib import Path

from . import mapgen
from .model import DIRECTORIES, split_frontmatter

TOOLING_URL = "https://github.com/ddrinka/Life"
MANAGED_FILES = ("GUIDE.md", "CLAUDE.md", ".claude/settings.json")
DIRECTORY_NAMES = (*DIRECTORIES.values(), "journal", "archive", "cursors")


def templates_dir() -> Path:
    return Path(__file__).parent / "templates"


def installed_version() -> str:
    try:
        return "v" + importlib.metadata.version("life")
    except importlib.metadata.PackageNotFoundError:
        return "main"


def sync_files(root: Path) -> list[Path]:
    """Copy the managed files from the installed templates over whatever the tree has."""
    written: list[Path] = []
    for name in MANAGED_FILES:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(templates_dir() / name, target)
        written.append(target)
    return written


def write_pin(root: Path, version: str, url: str = TOOLING_URL) -> Path:
    path = root / "pyproject.toml"
    path.write_text(
        "[project]\n"
        'name = "life-state"\n'
        'version = "0"\n'
        'description = "A life state repository managed by the life tooling."\n'
        'requires-python = ">=3.13"\n'
        f'dependencies = ["life @ git+{url}@{version}"]\n'
        "\n"
        "[tool.uv]\n"
        "package = false\n",
        encoding="utf-8",
    )
    return path


def write_local(root: Path, owner: str, timezone: str, sms: str | None) -> Path:
    """Write LOCAL.md from the template body with this person's frontmatter. Never overwrites."""
    path = root / "LOCAL.md"
    if path.exists():
        return path
    _, body, _ = split_frontmatter((templates_dir() / "LOCAL.md").read_text(encoding="utf-8"))
    lines = ["---", f"owner: {json.dumps(owner)}", f"timezone: {timezone}"]
    if sms:
        lines.append(f"sms: {json.dumps(sms)}")
    lines.append("---")
    path.write_text("\n".join(lines) + "\n" + body, encoding="utf-8")
    return path


def init(root: Path, owner: str, timezone: str, sms: str | None, version: str,
         url: str = TOOLING_URL, lock: bool = True) -> list[str]:
    """Build a state repository at root. Returns the steps taken, for the caller to print."""
    steps: list[str] = []
    root.mkdir(parents=True, exist_ok=True)
    for name in DIRECTORY_NAMES:
        (root / name).mkdir(exist_ok=True)
    steps.append("created the tree directories")
    sync_files(root)
    steps.append("wrote GUIDE.md, CLAUDE.md, and .claude/settings.json")
    write_local(root, owner, timezone, sms)
    steps.append("wrote LOCAL.md")
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        shutil.copyfile(templates_dir() / "gitignore", gitignore)
    runs = root / "cursors" / "runs.json"
    if not runs.exists():
        runs.write_text("{}\n", encoding="utf-8")
    write_pin(root, version, url)
    steps.append(f"pinned the tooling to {version}")
    mapgen.write_map(root)
    steps.append("wrote MAP.md")
    if lock:
        subprocess.run(["uv", "lock"], cwd=root, check=True)
        steps.append("wrote uv.lock")
    return steps


def upgrade(root: Path, version: str, url: str = TOOLING_URL, sync: bool = True) -> list[str]:
    """Move a state repository to another tooling version and refresh its managed files."""
    steps: list[str] = []
    write_pin(root, version, url)
    steps.append(f"pinned the tooling to {version}")
    if sync:
        subprocess.run(["uv", "sync"], cwd=root, check=True)
        steps.append("installed it")
        subprocess.run(["uv", "run", "life", "sync-files"], cwd=root, check=True)
        subprocess.run(["uv", "run", "life", "map"], cwd=root, check=True)
    else:
        sync_files(root)
        mapgen.write_map(root)
    steps.append("rewrote the managed files and MAP.md")
    return steps
