#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Generate the README's roadmap and progress section from ROADMAP.md, the single source of truth.

Rewrites only the text between <!-- roadmap:start --> and <!-- roadmap:end --> in README.md.
`check_docs.py` fails when that section is out of date, so every change keeps it current.
    py -3 -I tools/docs/roadmap_progress.py [--root REPO] [--check]
"""
import argparse
import re
import sys
from pathlib import Path

START, END = "<!-- roadmap:start -->", "<!-- roadmap:end -->"
HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$")
TASK_RE = re.compile(r"^\s*- \[([ xX])\] \*\*((?:P\d+b?|S|Q|D|L|B)\.\d+)\*\*\s+(.*)$")
LAST_UPDATED_RE = re.compile(r"Last updated:?\**\s*(\d{4}-\d{2}-\d{2})")
BAR_WIDTH = 20
NEXT_COUNT = 6


def github_slug(heading: str) -> str:
    """GitHub's heading anchor: lowercase, drop punctuation (keep letters, digits, _ and -), spaces -> -."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def parse_roadmap(text: str) -> list[dict]:
    sections, current = [], None
    for line in text.splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            current = {"title": heading.group(2), "slug": github_slug(heading.group(2)), "tasks": []}
            sections.append(current)
            continue
        task = TASK_RE.match(line)
        if task and current is not None:
            rest = task.group(3)
            if task.group(1).lower() == "x":
                state = "done"
            elif "⛔" in rest:
                state = "blocked"
            elif rest.rstrip().endswith("🔄"):
                state = "in progress"
            else:
                state = "todo"
            current["tasks"].append({"id": task.group(2), "title": rest.split(" - *Role:*")[0].strip(),
                                     "state": state})
    return [s for s in sections if s["tasks"]]


def _bar(done: int, total: int) -> str:
    filled = round(BAR_WIDTH * done / total) if total else 0
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def _status(tasks: list[dict]) -> str:
    done = sum(t["state"] == "done" for t in tasks)
    if done == len(tasks):
        return "✅ Done"
    label = "🔄 In progress" if done or any(t["state"] == "in progress" for t in tasks) else "⬜ Not started"
    return label + (" · ⛔ blocked item" if any(t["state"] == "blocked" for t in tasks) else "")


def render(sections: list[dict], last_updated: str) -> str:
    tasks = [t for s in sections for t in s["tasks"]]
    done, total = sum(t["state"] == "done" for t in tasks), len(tasks)
    pct = round(100 * done / total) if total else 0
    out = [f"**Overall:** `{_bar(done, total)}` {done} of {total} tasks done ({pct}%) · roadmap updated {last_updated}",
           "", "| Area | Progress | Done | Status |", "|---|---|---|---|"]
    for s in sections:
        d = sum(t["state"] == "done" for t in s["tasks"])
        out.append(f"| [{s['title']}](ROADMAP.md#{s['slug']}) | `{_bar(d, len(s['tasks']))}` | "
                   f"{d}/{len(s['tasks'])} | {_status(s['tasks'])} |")
    phase_tasks = [t for s in sections if s["title"].startswith("P") for t in s["tasks"]]
    upcoming = [t for t in phase_tasks if t["state"] == "in progress"]
    upcoming += [t for t in phase_tasks if t["state"] in ("todo", "blocked")]
    out += ["", "**What's next**", ""]
    out += [f"- {'🔄' if t['state'] == 'in progress' else '⬜'} **{t['id']}** {t['title']}" for t in upcoming[:NEXT_COUNT]]
    out += ["", "<details>", '<summary><b>Full task list</b> (generated from <a href="ROADMAP.md">ROADMAP.md</a>)</summary>', ""]
    for s in sections:
        out += [f"**{s['title']}**", ""]
        out += [f"- [{'x' if t['state'] == 'done' else ' '}] **{t['id']}** {t['title']}" for t in s["tasks"]]
        out.append("")
    out.append("</details>")
    return "\n".join(out) + "\n"


BADGE_START, BADGE_END = "<!-- progress-badge:start -->", "<!-- progress-badge:end -->"


def render_badge(sections: list[dict]) -> str:
    tasks = [t for s in sections for t in s["tasks"]]
    pct = round(100 * sum(t["state"] == "done" for t in tasks) / len(tasks)) if tasks else 0
    return f"[![Roadmap progress](https://img.shields.io/badge/roadmap-{pct}%25-7B2FF7?style=flat-square)](#roadmap)\n"


def _replace(text: str, start: str, end: str, body: str) -> str:
    i, j = text.find(start), text.find(end)
    if i < 0 or j < 0 or j < i:
        raise ValueError(f"README markers {start} ... {end} not found")
    return text[:i] + start + "\n" + body.rstrip("\n") + "\n" + text[j:]


def update_readme(readme: str, block: str, badge: str | None = None) -> str:
    updated = _replace(readme, START, END, block)
    if badge is not None and BADGE_START in updated:
        # Inline (no line breaks) so the badge stays in the same paragraph as its neighbours.
        i, j = updated.find(BADGE_START), updated.find(BADGE_END)
        if j < i:
            raise ValueError(f"README markers {BADGE_START} ... {BADGE_END} out of order")
        updated = updated[:i] + BADGE_START + badge.strip() + updated[j:]
    return updated


def is_stale(readme: str, block: str, badge: str | None = None) -> bool:
    return update_readme(readme, block, badge) != readme


def _sections(root: Path) -> tuple[list[dict], str]:
    text = (root / "ROADMAP.md").read_text(encoding="utf-8")
    match = LAST_UPDATED_RE.search(text)
    return parse_roadmap(text), match.group(1) if match else "unknown"


def build_block(root: Path) -> str:
    sections, last_updated = _sections(root)
    return render(sections, last_updated)


def build_badge(root: Path) -> str:
    return render_badge(_sections(root)[0])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--check", action="store_true", help="exit 1 if README.md is out of date; write nothing")
    args = parser.parse_args(argv)
    root = Path(args.root)
    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    block, badge = build_block(root), build_badge(root)
    if args.check:
        stale = is_stale(readme, block, badge)
        print("README roadmap section is out of date" if stale else "README roadmap section is current")
        return 1 if stale else 0
    updated = update_readme(readme, block, badge)
    if updated != readme:
        temporary = readme_path.with_suffix(".md.tmp")
        temporary.write_text(updated, encoding="utf-8", newline="\n")
        temporary.replace(readme_path)
        print("README.md roadmap section updated")
    else:
        print("README.md roadmap section already current")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
