"""Append entries to the journal, one file per day in the owner's timezone."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from .local import load_local

ENTRY_RE = re.compile(r"^- \d{2}:\d{2} \S")
DENIED_INPUT_LIMIT = 200


def now_local(root: Path, now: dt.datetime | None = None) -> dt.datetime:
    zone = load_local(root).zone()
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=zone)
    return now.astimezone(zone)


def append(root: Path, text: str, now: dt.datetime | None = None) -> Path:
    """Add one entry to today's file, creating the file with its date header."""
    moment = now_local(root, now)
    path = root / "journal" / f"{moment:%Y}" / f"{moment:%m-%d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"- {moment:%H:%M} {' '.join(text.split())}\n"
    if not path.exists():
        path.write_text(f"# {moment:%Y-%m-%d}\n\n{line}", encoding="utf-8")
    else:
        existing = path.read_text(encoding="utf-8")
        sep = "" if existing.endswith("\n") else "\n"
        path.write_text(existing + sep + line, encoding="utf-8")
    return path


def denied_entry(payload: str) -> str:
    """Turn a PermissionDenied hook payload into one journal line."""
    try:
        data = json.loads(payload)
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    tool = data.get("tool_name") or "unknown tool"
    detail = json.dumps(data.get("tool_input"), default=str, sort_keys=True)
    if len(detail) > DENIED_INPUT_LIMIT:
        detail = detail[:DENIED_INPUT_LIMIT] + "..."
    reason = data.get("reason") or data.get("message")
    suffix = f" because {reason}" if isinstance(reason, str) and reason.strip() else ""
    return f"denied: {tool} {detail}{suffix}"


def entry_problems(text: str) -> list[str]:
    """Every non-blank line after the header is an entry starting with a time."""
    problems: list[str] = []
    lines = text.splitlines()
    if not lines or not re.match(r"^# \d{4}-\d{2}-\d{2}$", lines[0]):
        problems.append("first line must be the date header, like # 2026-09-08")
    for number, line in enumerate(lines[1:], start=2):
        if line.strip() and not ENTRY_RE.match(line):
            problems.append(f"line {number} must start with '- HH:MM '")
    return problems
