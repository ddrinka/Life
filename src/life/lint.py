"""Check a state tree against the rules in GUIDE.md."""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import journal as journal_mod
from . import mapgen
from .local import load_local
from .model import DIRECTORIES, Entity, Tree, is_regular_file, load_tree

LINE_LIMITS = {"GUIDE.md": 150, "LOCAL.md": 150, "MAP.md": 150}
FILE_LINE_LIMIT = 120
REQUIRED_FILES = ("GUIDE.md", "LOCAL.md", "MAP.md")
ROOT_FILES = set(REQUIRED_FILES) | {"CLAUDE.md", "README.md", "pyproject.toml", "uv.lock"}
ROOT_DIRECTORIES = set(DIRECTORIES.values()) | {"journal", "archive", "cursors"}
JOURNAL_RE = re.compile(r"^(\d{4})/(\d{2})-(\d{2})\.md$")


@dataclass
class Problem:
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def lint(root: Path, today: dt.date | None = None) -> list[Problem]:
    today = today or dt.date.today()
    tree = load_tree(root, today)
    problems: list[Problem] = []
    problems += _entity_problems(tree)
    problems += _cross_file_problems(tree)
    problems += _archive_problems(tree)
    problems += _layout_problems(root)
    problems += _root_file_problems(root, today)
    problems += _size_problems(root, tree)
    problems += _journal_problems(root, today)
    problems += _cursor_problems(root)
    problems += _immutability_problems(root, today)
    return problems


def _rel(root: Path, path: Path) -> Path:
    return path.relative_to(root)


def _listdir(path: Path) -> list[Path]:
    try:
        return sorted(path.iterdir())
    except OSError:
        return []


def _entity_problems(tree: Tree) -> list[Problem]:
    return [
        Problem(_rel(tree.root, e.path), message)
        for e in tree.entities
        for message in e.problems
    ]


def _cross_file_problems(tree: Tree) -> list[Problem]:
    problems: list[Problem] = []
    seen: dict[str, list[Entity]] = {}
    for e in tree.entities:
        seen.setdefault(e.slug, []).append(e)
    for slug, entities in seen.items():
        if len(entities) > 1:
            paths = ", ".join(str(_rel(tree.root, e.path)) for e in entities)
            problems.append(Problem(_rel(tree.root, entities[0].path), f"slug '{slug}' is used by {paths}"))

    by_slug = tree.by_slug()
    for e in tree.entities:
        for target in dict.fromkeys(e.related):
            other = by_slug.get(target)
            if other is None or not other.is_open:
                problems.append(Problem(_rel(tree.root, e.path), f"related '{target}' is not an open file"))
            elif e.slug not in other.related:
                problems.append(Problem(_rel(tree.root, other.path), f"must list '{e.slug}' in related, because {e.slug} lists it"))
        if e.slug in e.related:
            problems.append(Problem(_rel(tree.root, e.path), "related lists itself"))
        parent = e.parent
        if parent is not None:
            target = by_slug.get(parent)
            if target is None or not target.is_open:
                problems.append(Problem(_rel(tree.root, e.path), f"parent '{parent}' is not an open file"))
            elif e.kind == "project" and target.kind != "area":
                problems.append(Problem(_rel(tree.root, e.path), f"parent '{parent}' must be an area"))
            elif target.kind not in ("project", "area"):
                problems.append(Problem(_rel(tree.root, e.path), f"parent '{parent}' must be a project or an area"))
    return problems


def _archive_problems(tree: Tree) -> list[Problem]:
    """Archived files keep the schema, and every kind but a person has status done.

    Their related lists are empty, and no open file uses the same slug.
    """
    problems: list[Problem] = []
    active = tree.by_slug()
    for e in tree.archived:
        rel = _rel(tree.root, e.path)
        problems += [Problem(rel, m) for m in e.problems]
        if e.slug in active:
            problems.append(Problem(rel, f"slug '{e.slug}' is also active at {_rel(tree.root, active[e.slug].path)}"))
        if e.kind != "person" and e.status != "done":
            problems.append(Problem(rel, "archived files must have status done"))
        if e.related:
            problems.append(Problem(rel, "archived files must have an empty related list"))
    archive = tree.root / "archive"
    if archive.exists() and not archive.is_dir():
        return problems + [Problem(Path("archive"), "must be a directory")]
    allowed = set(DIRECTORIES.values())
    for entry in _listdir(archive):
        if not entry.is_dir() or entry.name not in allowed:
            problems.append(Problem(_rel(tree.root, entry), "archive holds only archive/<projects|areas|tasks|people>/"))
            continue
        for path in _listdir(entry):
            if not path.name.endswith(".md") or not is_regular_file(path):
                problems.append(Problem(_rel(tree.root, path), "archive files live in archive/<kind>/<slug>.md"))
    return problems


def _layout_problems(root: Path) -> list[Problem]:
    """The tree holds only the directories and root files GUIDE.md names.

    Entity directories hold flat *.md files.
    """
    problems: list[Problem] = []
    for path in _listdir(root):
        name = path.name
        if name.startswith("."):
            continue
        if path.is_dir():
            if name not in ROOT_DIRECTORIES:
                problems.append(Problem(Path(name), "directory is not part of the tree layout"))
        elif name not in ROOT_FILES:
            problems.append(Problem(Path(name), "stray file at the root"))
    for name in ("journal", "archive", "cursors", *DIRECTORIES.values()):
        path = root / name
        if path.exists() and not path.is_dir():
            problems.append(Problem(Path(name), "must be a directory"))
    for directory in DIRECTORIES.values():
        for path in _listdir(root / directory):
            if not path.name.endswith(".md") or not is_regular_file(path):
                problems.append(Problem(_rel(root, path), f"{directory}/ holds only <slug>.md files"))
    return problems


def _root_file_problems(root: Path, today: dt.date) -> list[Problem]:
    problems: list[Problem] = []
    for name in REQUIRED_FILES:
        if not is_regular_file(root / name):
            problems.append(Problem(Path(name), "missing; every tree has GUIDE.md, LOCAL.md, and MAP.md"))
    if is_regular_file(root / "LOCAL.md"):
        problems += [Problem(Path("LOCAL.md"), m) for m in load_local(root).problems]
    if is_regular_file(root / "MAP.md"):
        try:
            current = (root / "MAP.md").read_text(encoding="utf-8")
        except OSError as exc:
            current = None
            problems.append(Problem(Path("MAP.md"), f"cannot read: {exc}"))
        if current is not None and current != mapgen.build_map(root, today):
            problems.append(Problem(Path("MAP.md"), "out of date; run `life map`"))
    return problems


def _line_count(path: Path) -> int | None:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except (OSError, ValueError):
        return None


def _size_problems(root: Path, tree: Tree) -> list[Problem]:
    problems: list[Problem] = []
    for name, limit in LINE_LIMITS.items():
        path = root / name
        if is_regular_file(path) and (n := _line_count(path)) is not None and n > limit:
            problems.append(Problem(Path(name), f"{n} lines, limit {limit}"))
    paths = [e.path for e in tree.entities] + _journal_files(root)
    for path in paths:
        if (n := _line_count(path)) is not None and n > FILE_LINE_LIMIT:
            problems.append(Problem(_rel(root, path), f"{n} lines, limit {FILE_LINE_LIMIT}"))
    return problems


def _journal_files(root: Path) -> list[Path]:
    journal = root / "journal"
    if not journal.is_dir():
        return []
    found: list[Path] = []
    for year in _listdir(journal):
        if year.is_dir():
            found += [p for p in _listdir(year) if not p.is_dir()]
        else:
            found.append(year)
    return found


def _journal_problems(root: Path, today: dt.date) -> list[Problem]:
    problems: list[Problem] = []
    journal = root / "journal"
    for path in _journal_files(root):
        rel = path.relative_to(journal).as_posix()
        match = JOURNAL_RE.match(rel)
        if not match or not is_regular_file(path):
            problems.append(Problem(_rel(root, path), "journal files are named journal/YYYY/MM-DD.md"))
            continue
        try:
            day = dt.date(*map(int, match.groups()))
        except ValueError:
            problems.append(Problem(_rel(root, path), "journal file name is not a real date"))
            continue
        if day > today:
            problems.append(Problem(_rel(root, path), "journal entry is dated in the future"))
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            problems.append(Problem(_rel(root, path), f"cannot read: {exc}"))
            continue
        problems += [Problem(_rel(root, path), m) for m in journal_mod.entry_problems(text)]
    return problems


def _cursor_problems(root: Path) -> list[Problem]:
    problems: list[Problem] = []
    cursors = root / "cursors"
    runs = cursors / "runs.json"
    if not is_regular_file(runs):
        return [Problem(Path("cursors/runs.json"), "missing; every tree records its runs here")]
    for path in _listdir(cursors):
        rel = _rel(root, path)
        if path.suffix != ".json" or not is_regular_file(path):
            problems.append(Problem(rel, "cursors/ holds only .json files"))
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            problems.append(Problem(rel, f"not valid JSON: {exc}"))
            continue
        if not isinstance(data, dict):
            problems.append(Problem(rel, "must be a JSON object"))
        elif path == runs:
            for key in ("last_run", "last_brief"):
                value = data.get(key)
                if value is None:
                    continue
                try:
                    dt.datetime.fromisoformat(str(value))
                except ValueError:
                    problems.append(Problem(rel, f"{key} must be an ISO 8601 timestamp"))
    return problems


def _git_status(root: Path) -> list[tuple[str, Path]] | None:
    """Return (status, path relative to root) for tracked changes under journal/ and archive/.

    A rename or copy produces two entries: the destination, then the original as a deletion.
    """
    try:
        prefix = subprocess.run(
            ["git", "rev-parse", "--show-prefix"], cwd=root, capture_output=True, text=True, check=True,
        ).stdout.strip()
        raw = subprocess.run(
            ["git", "status", "--porcelain", "-z", "--untracked-files=no", "--", "journal", "archive"],
            cwd=root, capture_output=True, check=True,
        ).stdout.decode("utf-8", errors="surrogateescape")
    except (OSError, subprocess.CalledProcessError):
        return None
    entries = raw.split("\0")
    changes: list[tuple[str, Path]] = []
    i = 0
    while i < len(entries) and entries[i]:
        status, repo_path = entries[i][:2], entries[i][3:]
        paths = [(status, repo_path)]
        i += 1
        if status[0] in "RC" and i < len(entries):
            paths.append(("D ", entries[i]))
            i += 1
        for st, rp in paths:
            if rp.startswith(prefix):
                changes.append((st, Path(rp[len(prefix):])))
    return changes


def _immutability_problems(root: Path, today: dt.date) -> list[Problem]:
    """Tracked journal entries for past days and tracked archive files must not change."""
    changes = _git_status(root)
    if changes is None:
        return []
    problems: list[Problem] = []
    for status, path in changes:
        if status[0] == "A" or not path.parts:
            continue
        if path.parts[0] == "archive":
            problems.append(Problem(path, "archived files are never edited"))
        elif path.parts[0] == "journal":
            match = JOURNAL_RE.match(path.relative_to("journal").as_posix())
            if match and dt.date(*map(int, match.groups())) < today:
                problems.append(Problem(path, "past journal entries are never edited"))
    return problems
