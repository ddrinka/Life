"""Build MAP.md, the summary of a state tree that every session reads."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from .model import Entity, Tree, load_tree

DUE_SOON_DAYS = 7
STALE_DAYS = 7


def build_map(root: Path, today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    tree = load_tree(root, today)
    open_items = [e for e in tree.entities if e.is_open]
    lines = [
        "# Map",
        "",
        f"Generated {today.isoformat()} by `life map`. Do not edit; change the files it reads.",
        "",
    ]
    lines += _focus_section(open_items, today)
    lines += _review_section(open_items, today)
    lines += _stuck_section(open_items)
    lines += _tasks_section(open_items, today)
    lines += _threads_section(open_items)
    lines += _counts_section(tree)
    return "\n".join(lines).rstrip("\n") + "\n"


def write_map(root: Path, today: dt.date | None = None) -> Path:
    path = root / "MAP.md"
    path.write_text(build_map(root, today), encoding="utf-8")
    return path


def _item(e: Entity, *tags: str, show_next: bool = True) -> str:
    extra = ", ".join(t for t in tags if t)
    head = f"- **{e.title}** (`{e.slug}`{', ' + extra if extra else ''})"
    if show_next and e.next:
        return f"{head}: {e.next}"
    return head


def _sorted(items: list[Entity]) -> list[Entity]:
    return sorted(items, key=lambda e: (e.domain or "", e.title.lower()))


def _domains(items: list[Entity]) -> list[str]:
    known = ["work", "personal"]
    others = sorted({e.domain or "unknown" for e in items} - set(known))
    return known + others


def _focus_section(items: list[Entity], today: dt.date) -> list[str]:
    focus = [e for e in items if e.tier == "focus"]
    lines = ["## Focus", ""]
    if not focus:
        return lines + ["Nothing is in focus.", ""]
    for domain in _domains(focus):
        group = _sorted([e for e in focus if (e.domain or "unknown") == domain])
        if not group:
            continue
        lines.append(f"### {domain.capitalize()}")
        lines.append("")
        for e in group:
            status = e.status if e.status != "active" else ""
            parent = f"in {e.parent}" if e.parent else ""
            stale = ""
            if e.touched and (today - e.touched).days > STALE_DAYS:
                stale = f"stale since {e.touched.isoformat()}"
            lines.append(_item(e, e.kind if e.kind != "project" else "", parent, status, stale))
        lines.append("")
    return lines


def _review_section(items: list[Entity], today: dt.date) -> list[str]:
    due = _sorted([e for e in items if e.review and e.review <= today])
    lines = ["## Due for review", ""]
    if not due:
        return lines + ["Nothing is due for review.", ""]
    for e in due:
        lines.append(_item(e, e.kind, e.tier or "", f"review {e.review.isoformat()}"))
    return lines + [""]


def _stuck_section(items: list[Entity]) -> list[str]:
    stuck = _sorted([e for e in items if e.tier != "focus" and e.status in ("blocked", "waiting")])
    lines = ["## Blocked and waiting outside focus", ""]
    if not stuck:
        return lines + ["Nothing outside focus is blocked or waiting.", ""]
    for e in stuck:
        lines.append(_item(e, e.kind, e.status))
    return lines + [""]


def _tasks_section(items: list[Entity], today: dt.date) -> list[str]:
    try:
        horizon = today + dt.timedelta(days=DUE_SOON_DAYS)
    except OverflowError:
        horizon = dt.date.max
    tasks = sorted(
        [e for e in items if e.kind == "task" and e.due and e.due <= horizon],
        key=lambda e: (e.due, e.title.lower()),
    )
    lines = [f"## Tasks due within {DUE_SOON_DAYS} days", ""]
    if not tasks:
        return lines + ["No tasks are due.", ""]
    for e in tasks:
        overdue = "overdue" if e.due < today else ""
        parent = f"in {e.parent}" if e.parent else ""
        lines.append(f"- {e.due.isoformat()} " + _item(e, overdue, parent, show_next=False)[2:])
    return lines + [""]


def _threads_section(items: list[Entity]) -> list[str]:
    """List connected groups in the related graph that span more than one project or area."""
    by_slug = {e.slug: e for e in items}
    seen: set[str] = set()
    threads: list[list[str]] = []
    for e in items:
        if e.slug in seen:
            continue
        component: list[str] = []
        stack = [e.slug]
        while stack:
            slug = stack.pop()
            if slug in seen or slug not in by_slug:
                continue
            seen.add(slug)
            component.append(slug)
            stack.extend(by_slug[slug].related)
        anchors = [s for s in component if by_slug[s].kind in ("project", "area")]
        if len(anchors) >= 2:
            threads.append(sorted(component))
    lines = ["## Threads across projects", ""]
    if not threads:
        return lines + ["No related links span more than one project or area.", ""]
    for component in sorted(threads):
        lines.append("- " + ", ".join(f"`{s}`" for s in component))
    return lines + [""]


def _counts_section(tree: Tree) -> list[str]:
    open_items = [e for e in tree.entities if e.is_open]
    def count(kind: str, tier: str | None = None) -> int:
        return sum(1 for e in open_items if e.kind == kind and (tier is None or e.tier == tier))

    return [
        "## Counts",
        "",
        f"Projects: {count('project', 'focus')} focus, {count('project', 'background')} background, "
        f"{count('project', 'someday')} someday. Areas: {count('area')}. Open tasks: {count('task')}. "
        f"People: {len(tree.of_kind('person'))}.",
        "",
    ]
