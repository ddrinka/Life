"""Filter entities by frontmatter fields."""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

from .model import Entity, load_tree


@dataclass
class Filter:
    kind: str | None = None
    domain: str | None = None
    tier: str | None = None
    status: str | None = None
    parent: str | None = None
    related: str | None = None
    due_before: dt.date | None = None
    review_due: bool = False
    include_done: bool = False

    def matches(self, e: Entity, today: dt.date) -> bool:
        if self.kind and e.kind != self.kind:
            return False
        if self.domain and e.domain != self.domain:
            return False
        if self.tier and e.tier != self.tier:
            return False
        if self.status and e.status != self.status:
            return False
        if not self.status and not self.include_done and e.status == "done":
            return False
        if self.parent and e.parent != self.parent:
            return False
        if self.related and self.related not in e.related:
            return False
        if self.due_before and (e.kind != "task" or e.due is None or e.due > self.due_before):
            return False
        if self.review_due and (e.review is None or e.review > today):
            return False
        return True


def query(root: Path, spec: Filter, today: dt.date | None = None) -> list[Entity]:
    today = today or dt.date.today()
    tree = load_tree(root, today)
    hits = [e for e in tree.entities if spec.matches(e, today)]
    return sorted(hits, key=lambda e: (e.kind, e.domain or "", e.title.lower()))


def format_table(entities: list[Entity]) -> str:
    rows = [("slug", "kind", "domain", "tier", "status", "due", "review", "title")]
    for e in entities:
        rows.append((
            e.slug, e.kind, e.domain or "", e.tier or "", e.status or "",
            e.due.isoformat() if e.due else "", e.review.isoformat() if e.review else "", e.title,
        ))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]) - 1)]
    lines = []
    for row in rows:
        cells = [row[i].ljust(widths[i]) for i in range(len(widths))] + [row[-1]]
        lines.append("  ".join(cells).rstrip())
    return "\n".join(lines)


MAX_JSON_DEPTH = 4


def _plain(value, depth: int = 0):
    """Reduce frontmatter to JSON-safe data."""
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if depth >= MAX_JSON_DEPTH:
        return str(value)
    if isinstance(value, dict):
        return {str(k): _plain(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v, depth + 1) for v in value]
    return str(value)


def format_json(entities: list[Entity], root: Path) -> str:
    records = [
        {"slug": e.slug, "path": str(e.path.relative_to(root)), **_plain(e.meta)}
        for e in entities
    ]
    return json.dumps(records, indent=2)


def format_paths(entities: list[Entity], root: Path) -> str:
    return "\n".join(str(e.path.relative_to(root)) for e in entities)
