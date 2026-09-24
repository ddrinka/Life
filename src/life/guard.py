"""Check a tool call against the tree's deny rules, for a PreToolUse hook that journals blocks.

Deny rules in `.claude/settings.json` block a call before any hook that reports denials
runs, so a blocked call would leave no trace. This module runs first, from PreToolUse,
applies the same rules, and returns a deny decision the caller journals. The deny rules
stay in settings as the backstop if this hook fails.
"""

from __future__ import annotations

import fnmatch
import json
import re
import shlex
from pathlib import Path

RULE_RE = re.compile(r"^([A-Za-z0-9_*-]+)(?:\((.*)\))?$", re.S)
SEPARATOR_CHARS = set("();|&\n")


def deny_rules(root: Path) -> list[str]:
    """The `permissions.deny` list from the tree's settings, or nothing if unreadable."""
    try:
        data = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        rules = data["permissions"]["deny"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    return [rule for rule in rules if isinstance(rule, str)] if isinstance(rules, list) else []


def segments(command: str) -> list[str]:
    """Split a shell command into the simple commands joined by ;, &&, ||, |, or newlines."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return [command.strip()]
    parts: list[str] = []
    current: list[str] = []
    for token in tokens:
        if token and set(token) <= SEPARATOR_CHARS:
            if current:
                parts.append(" ".join(current))
            current = []
        else:
            current.append(token)
    if current:
        parts.append(" ".join(current))
    return parts


def matching_rule(rules: list[str], tool: str, tool_input: object) -> str | None:
    """The first deny rule that matches this call, if any."""
    for rule in rules:
        found = RULE_RE.match(rule.strip())
        if not found:
            continue
        name, spec = found.groups()
        if not fnmatch.fnmatchcase(tool, name):
            continue
        if spec is None:
            return rule
        if tool == "Bash" and isinstance(tool_input, dict):
            command = str(tool_input.get("command", ""))
            if any(fnmatch.fnmatchcase(part, spec) for part in segments(command)):
                return rule
    return None


def check(root: Path, payload: str) -> tuple[dict, str] | None:
    """For a PreToolUse payload, the deny decision and its journal line, or None to allow."""
    data = json.loads(payload)
    if not isinstance(data, dict):
        return None
    tool = data.get("tool_name")
    if not isinstance(tool, str):
        return None
    rule = matching_rule(deny_rules(root), tool, data.get("tool_input"))
    if rule is None:
        return None
    reason = f"the deny rule {rule} in .claude/settings.json"
    decision = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Blocked by {reason}.",
        }
    }
    return decision, json.dumps({**data, "reason": reason})
