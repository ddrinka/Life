"""Load a state tree into entities and validate their frontmatter."""

from __future__ import annotations

import datetime as dt
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path

import yaml

KINDS = ("project", "area", "task", "person")
DOMAINS = ("personal", "work")
TIERS = ("focus", "background", "someday")
STATUSES = ("active", "waiting", "blocked", "done")
DIRECTORIES = {"project": "projects", "area": "areas", "task": "tasks", "person": "people"}
SECTIONS = ("Goal", "State", "Steps", "Decisions", "Notes")

FRONTMATTER_KEYS = {
    "kind", "title", "domain", "tier", "status", "next", "touched", "review",
    "due", "parent", "related", "source",
}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
HEADING_RE = re.compile(r"^(#+)[ \t]+(.*?)[ \t]*$")
CLOSING_FENCE_RE = re.compile(r"\n---[ \t]*(?:\n|$)")


@dataclass
class Entity:
    path: Path
    slug: str
    kind: str
    meta: dict
    body: str
    problems: list[str] = field(default_factory=list)

    def _str(self, key: str) -> str | None:
        value = self.meta.get(key)
        return value if isinstance(value, str) else None

    @property
    def title(self) -> str:
        return self._str("title") or self.slug

    @property
    def domain(self) -> str | None:
        return self._str("domain")

    @property
    def tier(self) -> str | None:
        return self._str("tier")

    @property
    def status(self) -> str | None:
        return self._str("status")

    @property
    def next(self) -> str | None:
        return self._str("next")

    @property
    def parent(self) -> str | None:
        return self._str("parent")

    @property
    def review(self) -> dt.date | None:
        return _as_date(self.meta.get("review"))

    @property
    def due(self) -> dt.date | None:
        return _as_date(self.meta.get("due"))

    @property
    def touched(self) -> dt.date | None:
        return _as_date(self.meta.get("touched"))

    @property
    def related(self) -> list[str]:
        value = self.meta.get("related")
        if not isinstance(value, list):
            return []
        return [v for v in value if isinstance(v, str)]

    @property
    def is_open(self) -> bool:
        return self.status != "done"


@dataclass
class Tree:
    root: Path
    entities: list[Entity]
    archived: list[Entity] = field(default_factory=list)

    def by_slug(self) -> dict[str, Entity]:
        return {e.slug: e for e in self.entities}

    def of_kind(self, kind: str) -> list[Entity]:
        return [e for e in self.entities if e.kind == kind]


def _as_date(value) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return None


def split_frontmatter(text: str) -> tuple[dict | None, str, str | None]:
    """Return (meta, body, error). meta is None when the block is missing or unreadable."""
    text = text.removeprefix("\ufeff")
    if not text.startswith("---\n"):
        return None, text, "missing frontmatter"
    match = CLOSING_FENCE_RE.search(text, 3)
    if match is None:
        return None, text, "unterminated frontmatter"
    raw = text[4:match.start()]
    body = text[match.end():]
    try:
        meta = yaml.safe_load(raw)
    except Exception as exc:
        return None, body, f"frontmatter is not valid YAML: {exc}"
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        return None, body, "frontmatter is not a mapping"
    return meta, body, None


def load_entity(path: Path, expected_kind: str, today: dt.date | None = None) -> Entity:
    entity = Entity(path=path, slug=path.stem, kind=expected_kind, meta={}, body="")
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        entity.problems.append(f"cannot read: {exc}")
        return entity
    meta, body, error = split_frontmatter(text)
    entity.meta = meta or {}
    entity.body = body
    if error:
        entity.problems.append(error)
        return entity
    entity.problems.extend(validate_meta(meta, expected_kind, path.stem, today))
    entity.problems.extend(validate_body(body))
    return entity


def validate_meta(meta: dict, expected_kind: str, slug: str, today: dt.date | None = None) -> list[str]:
    today = today or dt.date.today()
    problems: list[str] = []
    if not SLUG_RE.match(slug):
        problems.append(f"slug '{slug}' must be lowercase letters, digits, and hyphens")
    unknown = sorted(str(k) for k in meta if k not in FRONTMATTER_KEYS)
    if unknown:
        problems.append(f"unknown frontmatter keys: {', '.join(unknown)}")

    kind = meta.get("kind")
    if kind != expected_kind:
        problems.append(f"kind is {kind!r} but the directory says {expected_kind!r}")
    if not isinstance(meta.get("title"), str) or not meta["title"].strip():
        problems.append("title is required")
    if meta.get("domain") not in DOMAINS:
        problems.append(f"domain must be one of {', '.join(DOMAINS)}")

    if expected_kind == "person":
        for key in ("tier", "status", "due", "parent"):
            if key in meta:
                problems.append(f"{key} does not apply to a person")
    else:
        if meta.get("tier") not in TIERS:
            problems.append(f"tier must be one of {', '.join(TIERS)}")
        if meta.get("status") not in STATUSES:
            problems.append(f"status must be one of {', '.join(STATUSES)}")
        if meta.get("tier") == "focus" and meta.get("status") != "done":
            if not isinstance(meta.get("next"), str) or not meta["next"].strip():
                problems.append("next is required for an open focus item")
        if meta.get("status") == "done" and meta.get("related"):
            problems.append("a done file must have an empty related list")
        if expected_kind != "task":
            for key in ("due", "parent"):
                if key in meta:
                    problems.append(f"{key} applies only to tasks")

    for key in ("touched", "review", "due"):
        if key in meta and _as_date(meta[key]) is None:
            problems.append(f"{key} must be a date like 2026-09-08")
    if "touched" not in meta:
        problems.append("touched is required")
    elif (touched := _as_date(meta["touched"])) and touched > today:
        problems.append("touched is in the future")

    related = meta.get("related")
    if related is not None:
        if not isinstance(related, list) or not all(isinstance(r, str) for r in related):
            problems.append("related must be a list of slugs")
        elif len(set(related)) != len(related):
            problems.append("related has duplicate entries")
    for key in ("next", "source", "parent"):
        if key in meta and not isinstance(meta[key], str):
            problems.append(f"{key} must be a string")
    return problems


def headings(body: str) -> list[tuple[str, str]]:
    """Return (hashes, name) for each heading outside fenced code blocks."""
    found: list[tuple[str, str]] = []
    fence: str | None = None
    for line in body.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is None and (match := HEADING_RE.match(line)):
            found.append((match.group(1), match.group(2)))
    return found


def validate_body(body: str) -> list[str]:
    """Body headings must come from SECTIONS, in that order, at level two."""
    problems: list[str] = []
    seen: list[str] = []
    for hashes, name in headings(body):
        if len(hashes) != 2:
            problems.append(f"heading '{name}' must be level two")
            continue
        if name not in SECTIONS:
            problems.append(f"heading '{name}' is not one of {', '.join(SECTIONS)}")
            continue
        if name in seen:
            problems.append(f"heading '{name}' appears twice")
        elif seen and SECTIONS.index(name) < SECTIONS.index(seen[-1]):
            problems.append(f"heading '{name}' must come before '{seen[-1]}'")
        seen.append(name)
    return problems


def load_tree(root: Path, today: dt.date | None = None) -> Tree:
    tree = Tree(root=root, entities=[])
    for kind, directory in DIRECTORIES.items():
        for path in entity_files(root / directory):
            tree.entities.append(load_entity(path, kind, today))
        for path in entity_files(root / "archive" / directory):
            tree.archived.append(load_entity(path, kind, today))
    return tree


def entity_files(folder: Path) -> list[Path]:
    """Return the regular *.md files directly under folder. Anything else is a layout problem."""
    try:
        return sorted(p for p in folder.glob("*.md") if is_regular_file(p))
    except OSError:
        return []


def is_regular_file(path: Path) -> bool:
    try:
        return path.is_file() and stat.S_ISREG(path.stat().st_mode)
    except OSError:
        return False
