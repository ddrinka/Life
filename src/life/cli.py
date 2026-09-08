"""Parse the command line and run the `life` subcommands."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from . import journal as journal_mod
from . import lint as lint_mod
from . import mapgen
from . import query as query_mod
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
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    args = build_parser().parse_args(argv)
    root: Path = args.root.resolve()
    if not root.is_dir():
        print(f"{root} is not a directory", file=sys.stderr)
        return 2

    if args.command == "journal":
        return _journal(root, args)

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
