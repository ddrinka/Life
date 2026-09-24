"""Parse the command line and run the `life` subcommands."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

from . import brief as brief_mod
from . import guard as guard_mod
from . import journal as journal_mod
from . import lint as lint_mod
from . import mapgen
from . import query as query_mod
from . import scaffold
from .model import DOMAINS, KINDS, STATUSES, TIERS


def _datetime(value: str) -> dt.datetime:
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a timestamp like 2026-09-08T07:00:00-06:00") from exc


def _date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{value!r} is not a date like 2026-09-08") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="life", description="Work with a life state tree.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="state tree root, default: current directory")
    parser.add_argument("--today", type=_date, default=None, help="override today's date, for tests")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("lint", help="check the tree against GUIDE.md rules")

    p_map = sub.add_parser("map", help="regenerate MAP.md")
    p_map.add_argument("--stdout", action="store_true", help="print instead of writing MAP.md")

    p_query = sub.add_parser("query", help="list entities matching filters")
    p_query.add_argument("--kind", choices=KINDS)
    p_query.add_argument("--domain", choices=DOMAINS)
    p_query.add_argument("--tier", choices=TIERS)
    p_query.add_argument("--status", choices=STATUSES)
    p_query.add_argument("--parent", help="tasks under this project or area slug")
    p_query.add_argument("--related", help="entities whose related list holds this slug")
    p_query.add_argument("--due-before", type=_date, metavar="DATE", help="tasks due on or before DATE")
    p_query.add_argument("--review-due", action="store_true", help="review date is today or earlier")
    p_query.add_argument("--include-done", action="store_true", help="include status done")
    p_query.add_argument("--format", choices=("table", "json", "paths"), default="table")

    p_journal = sub.add_parser("journal", help="append an entry to today's journal file")
    p_journal.add_argument("text", nargs="?", help="the entry; slugs it touches go in backticks")
    p_journal.add_argument("--denied", action="store_true", help="read a PermissionDenied hook payload from stdin")
    p_journal.add_argument("--now", type=_datetime, default=None, help="override the current time, for tests")

    sub.add_parser("guard", help="PreToolUse hook: journal and deny calls the tree's deny rules block")

    p_init = sub.add_parser("init", help="create a state repository at --root")
    p_init.add_argument("--owner", required=True, help="the person's name")
    p_init.add_argument("--timezone", required=True, help="IANA zone, like America/Denver")
    p_init.add_argument("--sms", default=None, help="E.164 number the brief is sent to")
    p_init.add_argument("--version", default=None, help="tooling tag to pin, default: the installed version")
    p_init.add_argument("--tooling", default=scaffold.TOOLING_URL, help="tooling repository URL")
    p_init.add_argument("--no-lock", action="store_true", help="skip `uv lock`")

    p_up = sub.add_parser("upgrade", help="pin another tooling version and refresh the managed files")
    p_up.add_argument("version", nargs="?", default=None, help="tooling tag, default: the installed version")
    p_up.add_argument("--tooling", default=scaffold.TOOLING_URL, help="tooling repository URL")
    p_up.add_argument("--no-sync", action="store_true", help="rewrite files from the installed tooling without `uv sync`")

    sub.add_parser("sync-files", help="rewrite the managed files from the installed tooling")

    p_brief = sub.add_parser("brief", help="print the material for today's brief")
    p_brief.add_argument("--now", type=_datetime, default=None, help="override the current time, for tests")
    p_brief.add_argument("--path", action="store_true", help="print the path of today's brief file instead")

    p_now = sub.add_parser("now", help="print the current time in the owner's timezone")
    p_now.add_argument("--now", type=_datetime, default=None, help="override the current time, for tests")

    p_cursor = sub.add_parser("cursor", help="read or set a run cursor in cursors/runs.json")
    p_cursor.add_argument("key", nargs="?", choices=brief_mod.CURSOR_KEYS, help="omit to print them all")
    p_cursor.add_argument("value", nargs="?", help="ISO timestamp to store")
    p_cursor.add_argument("--now", type=_datetime, default=None, help="store the current time, or this time")
    p_cursor.add_argument("--set-now", action="store_true", help="store the current time")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    args = build_parser().parse_args(argv)
    root: Path = args.root.resolve()
    if args.command == "init":
        return _init(root, args)
    if not root.is_dir():
        print(f"{root} is not a directory", file=sys.stderr)
        return 2

    if args.command == "upgrade":
        version = args.version or scaffold.installed_version()
        try:
            steps = scaffold.upgrade(root, version, args.tooling, sync=not args.no_sync)
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"upgrade failed: {exc}", file=sys.stderr)
            return 1
        print("\n".join(steps))
        print("Review the changes, then commit and push.")
        return 0

    if args.command == "sync-files":
        for path in scaffold.sync_files(root):
            print(f"wrote {path.relative_to(root)}")
        return 0

    if args.command == "journal":
        return _journal(root, args)
    if args.command == "guard":
        return _guard(root)
    if args.command == "brief":
        if args.path:
            print(brief_mod.brief_path(root, args.now).relative_to(root))
        else:
            sys.stdout.write(brief_mod.build_digest(root, args.now))
        return 0
    if args.command == "now":
        print(journal_mod.now_local(root, args.now).isoformat(timespec="minutes"))
        return 0
    if args.command == "cursor":
        return _cursor(root, args)

    if args.command == "lint":
        problems = lint_mod.lint(root, args.today)
        for problem in problems:
            print(problem)
        if problems:
            print(f"{len(problems)} problem{'s' if len(problems) != 1 else ''}", file=sys.stderr)
            return 1
        print("ok")
        return 0

    if args.command == "map":
        if args.stdout:
            sys.stdout.write(mapgen.build_map(root, args.today))
            return 0
        try:
            path = mapgen.write_map(root, args.today)
        except OSError as exc:
            print(f"cannot write MAP.md: {exc}", file=sys.stderr)
            return 1
        print(f"wrote {path.relative_to(root)}")
        return 0

    if args.command == "query":
        spec = query_mod.Filter(
            kind=args.kind, domain=args.domain, tier=args.tier, status=args.status,
            parent=args.parent, related=args.related, due_before=args.due_before,
            review_due=args.review_due, include_done=args.include_done,
        )
        hits = query_mod.query(root, spec, args.today)
        if args.format == "json":
            print(query_mod.format_json(hits, root))
        elif args.format == "paths":
            if hits:
                print(query_mod.format_paths(hits, root))
        else:
            print(query_mod.format_table(hits))
        return 0

    return 2


def _init(root: Path, args) -> int:
    if root.exists() and any(p for p in root.iterdir() if p.name not in (".git",)):
        print(f"{root} is not empty; init only builds a new tree", file=sys.stderr)
        return 2
    version = args.version or scaffold.installed_version()
    try:
        steps = scaffold.init(root, args.owner, args.timezone, args.sms, version, args.tooling, lock=not args.no_lock)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"init failed: {exc}", file=sys.stderr)
        return 1
    print("\n".join(steps))
    print("Next: edit LOCAL.md, then commit and push.")
    return 0


def _cursor(root: Path, args) -> int:
    if args.key is None:
        print(json.dumps(brief_mod.read_cursors(root), indent=2, sort_keys=True))
        return 0
    if args.value is None and not args.set_now and args.now is None:
        value = brief_mod.read_cursors(root).get(args.key)
        print("" if value is None else value)
        return 0
    value = args.value or journal_mod.now_local(root, args.now).isoformat(timespec="minutes")
    if dt.datetime.fromisoformat(value) is None:
        return 2
    brief_mod.write_cursor(root, args.key, value)
    print(f"{args.key} = {value}")
    return 0


def _guard(root: Path) -> int:
    """Runs from a hook that must not fail; on any error it allows, and settings still deny."""
    try:
        result = guard_mod.check(root, sys.stdin.read())
    except Exception as exc:
        print(f"guard could not check the call: {exc}", file=sys.stderr)
        return 0
    if result is None:
        return 0
    decision, payload = result
    try:
        journal_mod.append(root, journal_mod.denied_entry(payload))
    except Exception as exc:
        print(f"could not write the denial to the journal: {exc}", file=sys.stderr)
    print(json.dumps(decision))
    return 0


def _journal(root: Path, args) -> int:
    """The --denied form runs from a hook that must not fail, so it catches every error."""
    if args.denied:
        try:
            text = journal_mod.denied_entry(sys.stdin.read())
            journal_mod.append(root, text, args.now)
        except Exception as exc:
            print(f"could not write the denial to the journal: {exc}", file=sys.stderr)
        return 0
    if not args.text or not args.text.strip():
        print("journal needs text or --denied", file=sys.stderr)
        return 2
    try:
        path = journal_mod.append(root, args.text, args.now)
    except OSError as exc:
        print(f"cannot write the journal: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
