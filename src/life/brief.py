"""Gather what the daily brief needs: the time, what happened since the last brief, and the map."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from .journal import ENTRY_RE, now_local
from .lint import JOURNAL_RE

CURSOR_KEYS = ("last_run", "last_brief", "last_weekly_review", "last_monthly_sweep")


def read_cursors(root: Path) -> dict:
    path = root / "cursors" / "runs.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_cursor(root: Path, key: str, value: str) -> Path:
    path = root / "cursors" / "runs.json"
    data = read_cursors(root)
    data[key] = value
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _parse(value) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed


def entries_since(root: Path, since: dt.datetime | None, now: dt.datetime) -> list[str]:
    """Journal lines after `since`, oldest first, each prefixed with its date."""
    zone = now.tzinfo
    found: list[str] = []
    journal = root / "journal"
    if not journal.is_dir():
        return found
    for path in sorted(p for p in journal.rglob("*.md") if p.is_file()):
        match = JOURNAL_RE.match(path.relative_to(journal).as_posix())
        if not match:
            continue
        try:
            day = dt.date(*map(int, match.groups()))
        except ValueError:
            continue
        if since and day < since.astimezone(zone).date():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line in lines:
            if not ENTRY_RE.match(line):
                continue
            hour, minute = int(line[2:4]), int(line[5:7])
            moment = dt.datetime.combine(day, dt.time(hour, minute), tzinfo=zone)
            if since is None or moment > since:
                found.append(f"{day.isoformat()} {line[2:]}")
    return found


def build_digest(root: Path, now: dt.datetime | None = None) -> str:
    moment = now_local(root, now)
    cursors = read_cursors(root)
    last_brief = _parse(cursors.get("last_brief"))
    lines = [
        "# Brief material",
        "",
        f"Now: {moment.strftime('%A %Y-%m-%d %H:%M %Z')}.",
        f"Last brief: {last_brief.astimezone(moment.tzinfo).strftime('%A %Y-%m-%d %H:%M') if last_brief else 'never'}.",
        "",
        "## Since the last brief",
        "",
    ]
    since = entries_since(root, last_brief, moment)
    lines += [f"- {e}" for e in since] or ["Nothing new in the journal."]
    lines += ["", "## Map", ""]
    map_path = root / "MAP.md"
    try:
        body = map_path.read_text(encoding="utf-8")
        body = re.sub(r"^# Map\n\nGenerated .*\n\n", "", body)
        lines.append(body.rstrip("\n"))
    except OSError:
        lines.append("MAP.md is missing; run `life map`.")
    return "\n".join(lines) + "\n"


def brief_path(root: Path, now: dt.datetime | None = None) -> Path:
    moment = now_local(root, now)
    return root / "briefs" / f"{moment:%Y}" / f"{moment:%m-%d}.md"
