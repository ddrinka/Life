"""Read the owner's settings from LOCAL.md frontmatter."""

from __future__ import annotations

import re
import zoneinfo
from dataclasses import dataclass
from pathlib import Path

from .model import split_frontmatter

SMS_RE = re.compile(r"^\+[1-9]\d{6,14}$")


@dataclass
class Local:
    owner: str | None
    timezone: str | None
    sms: str | None
    problems: list[str]

    def zone(self) -> zoneinfo.ZoneInfo:
        return zoneinfo.ZoneInfo(self.timezone or "UTC")


def load_local(root: Path) -> Local:
    path = root / "LOCAL.md"
    problems: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return Local(None, None, None, [f"cannot read: {exc}"])
    meta, _, error = split_frontmatter(text)
    if error:
        return Local(None, None, None, [error])
    owner = meta.get("owner")
    timezone = meta.get("timezone")
    sms = meta.get("sms")
    if not isinstance(owner, str) or not owner.strip():
        problems.append("owner is required")
        owner = None
    if not isinstance(timezone, str):
        problems.append("timezone is required, like America/Denver")
        timezone = None
    else:
        try:
            zoneinfo.ZoneInfo(timezone)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError):
            problems.append(f"timezone '{timezone}' is not a known zone")
            timezone = None
    if sms is not None and (not isinstance(sms, str) or not SMS_RE.match(sms)):
        problems.append("sms must be a quoted E.164 number like \"+15555550100\"")
        sms = None
    unknown = sorted(str(k) for k in meta if k not in ("owner", "timezone", "sms"))
    if unknown:
        problems.append(f"unknown frontmatter keys: {', '.join(unknown)}")
    return Local(owner, timezone, sms, problems)
