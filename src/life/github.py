"""Compare open GitHub issues and PRs assigned to the owner with the tasks that track them."""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .model import Entity, load_tree

FIELDS = "url,number,title,repository,isPullRequest,updatedAt"
SEARCH_LIMIT = 1000
ISSUE_URL_RE = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+/(?:issues|pull)/\d+/?$")
DEFAULT_DAYS = 30


class GithubError(Exception):
    pass


@dataclass
class Item:
    url: str
    repo: str
    number: int
    title: str
    is_pr: bool
    updated: dt.date

    @property
    def ref(self) -> str:
        return f"{self.repo}#{self.number}"


@dataclass
class New:
    item: Item
    slug: str
    parents: list[str]
    domain: str | None


@dataclass
class Report:
    assigned: int
    recent: int
    days: int
    new: list[New] = field(default_factory=list)
    tracked: list[tuple[str, Item]] = field(default_factory=list)
    gone: list[tuple[str, str]] = field(default_factory=list)


def fetch() -> list[dict]:
    """GitHub search needs is:issue or is:pull-request, so issues and PRs are two searches."""
    records: list[dict] = []
    for kind in ("issues", "prs"):
        cmd = ["gh", "search", kind, "--assignee", "@me", "--state", "open",
               "--limit", str(SEARCH_LIMIT), "--json", FIELDS]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except OSError as exc:
            raise GithubError(f"cannot run gh: {exc}") from exc
        if done.returncode != 0:
            raise GithubError(f"gh search {kind} failed: {done.stderr.strip()}")
        try:
            records.extend(json.loads(done.stdout))
        except json.JSONDecodeError as exc:
            raise GithubError(f"gh search {kind} printed something other than JSON: {exc}") from exc
    return records


def parse(records: list[dict]) -> list[Item]:
    items: dict[str, Item] = {}
    for r in records:
        try:
            url = r["url"].rstrip("/")
            items[url] = Item(
                url=url,
                repo=r["repository"]["nameWithOwner"],
                number=int(r["number"]),
                title=r.get("title") or "",
                is_pr=bool(r.get("isPullRequest")),
                updated=dt.datetime.fromisoformat(r["updatedAt"].replace("Z", "+00:00")).date(),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise GithubError(f"unexpected search record {r!r}: {exc}") from exc
    return list(items.values())


def _repo_of_link(link: str) -> str:
    link = link.strip().lower().removeprefix("https://").removeprefix("github.com/").rstrip("/")
    link = link.split("#", 1)[0]
    return "/".join(link.split("/")[:2])


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _slug_for(item: Item, taken: set[str]) -> str:
    owner, name = item.repo.split("/", 1)
    for candidate in (f"{_slugify(name)}-{item.number}", f"{_slugify(owner)}-{_slugify(name)}-{item.number}"):
        if candidate not in taken:
            return candidate
    n = 2
    while f"{candidate}-{n}" in taken:
        n += 1
    return f"{candidate}-{n}"


def _source(e: Entity) -> str | None:
    value = e.meta.get("source")
    return value.rstrip("/") if isinstance(value, str) else None


def reconcile(root: Path, records: list[dict], today: dt.date | None = None, days: int = DEFAULT_DAYS) -> Report:
    today = today or dt.date.today()
    items = parse(records)
    tree = load_tree(root, today)
    everything = tree.entities + tree.archived
    by_source = {_source(e): e for e in everything if _source(e)}
    taken = {e.slug for e in everything}
    homes = [e for e in tree.entities if e.is_open and e.kind in ("project", "area")]
    cutoff = today - dt.timedelta(days=days)

    recent = [i for i in items if i.updated >= cutoff]
    report = Report(assigned=len(items), recent=len(recent), days=days)
    for item in sorted(items, key=lambda i: (i.repo.lower(), i.number)):
        owner = by_source.get(item.url)
        if owner is not None:
            if owner.is_open:
                report.tracked.append((owner.slug, item))
            continue
        if item.updated < cutoff:
            continue
        slug = _slug_for(item, taken)
        taken.add(slug)
        parents = [h for h in homes if item.repo.lower() in {_repo_of_link(link) for link in h.links}]
        domains = {p.domain for p in parents if p.domain}
        report.new.append(New(item, slug, [p.slug for p in parents], domains.pop() if len(domains) == 1 else None))

    assigned_urls = {i.url for i in items}
    for e in tree.entities:
        source = _source(e)
        if e.is_open and source and ISSUE_URL_RE.match(source) and source not in assigned_urls:
            report.gone.append((e.slug, source))
    return report


def format_text(report: Report) -> str:
    lines = [
        f"{report.assigned} open GitHub issues and PRs are assigned to the owner; "
        f"{report.recent} changed in the last {report.days} days.",
        "",
        f"New, to become tasks ({len(report.new)}):",
    ]
    for n in report.new:
        i = n.item
        lines.append(f"- {i.url}")
        lines.append(f"  {'pr' if i.is_pr else 'issue'} {i.ref}, updated {i.updated.isoformat()}, title: {i.title}")
        lines.append(f"  slug: {n.slug}  parent: {', '.join(n.parents) or '-'}  domain: {n.domain or '-'}")
    lines += ["", f"Tracked and still assigned ({len(report.tracked)}):"]
    lines += [f"- {slug}  {i.ref}, updated {i.updated.isoformat()}" for slug, i in report.tracked]
    lines += ["", f"Tracked but no longer open and assigned ({len(report.gone)}):"]
    lines += [f"- {slug}  {url}" for slug, url in report.gone]
    return "\n".join(lines) + "\n"


def format_json(report: Report) -> str:
    def item(i: Item) -> dict:
        d = asdict(i)
        d["updated"] = i.updated.isoformat()
        return d

    return json.dumps({
        "assigned": report.assigned,
        "recent": report.recent,
        "days": report.days,
        "new": [{"slug": n.slug, "parents": n.parents, "domain": n.domain, **item(n.item)} for n in report.new],
        "tracked": [{"slug": s, **item(i)} for s, i in report.tracked],
        "gone": [{"slug": s, "url": u} for s, u in report.gone],
    }, indent=2) + "\n"
