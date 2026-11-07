#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Regenerate the upstream-contributor list in CREDITS.md from GitHub.

Rewrites only the text between <!-- contributors:start --> and <!-- contributors:end -->.
Anonymous contributors are credited by name only (their e-mail is never written). Bots are excluded.
    py -3 -I tools/credits/contributors.py --repo Alex313031/thorium --file CREDITS.md [--from-json FILE]
"""
import argparse
import json
import os
import re
import subprocess
import sys

START = "<!-- contributors:start -->"
END = "<!-- contributors:end -->"


def _display_name(entry: dict) -> str:
    return entry.get("login") or entry.get("name") or "Unknown contributor"


BOT_NAME_RE = re.compile(r"(?i)\[bot\]$|^ci$|^github-actions|[\s_-]bot$")


def _is_bot(entry: dict) -> bool:
    if entry.get("type") == "Bot" or str(entry.get("login", "")).endswith("[bot]"):
        return True
    return entry.get("type") == "Anonymous" and bool(BOT_NAME_RE.search(str(entry.get("name", ""))))


def render_contributors(contribs: list[dict]) -> str:
    people = [c for c in contribs if not _is_bot(c)]
    people.sort(key=lambda c: (-int(c.get("contributions", 0)), _display_name(c).lower()))
    lines = []
    for c in people:
        count = int(c.get("contributions", 0))
        unit = "commit" if count == 1 else "commits"
        if c.get("type") == "User" and c.get("login"):
            lines.append(f"- [@{c['login']}](https://github.com/{c['login']}) ({count} {unit})")
        else:
            lines.append(f"- {_display_name(c)} ({count} {unit})")
    return "\n".join(lines) + "\n"


def replace_section(text: str, body: str, start: str = START, end: str = END) -> str:
    i, j = text.find(start), text.find(end)
    if i < 0 or j < 0 or j < i:
        raise ValueError(f"markers {start} ... {end} not found")
    return text[:i] + start + "\n" + body.rstrip("\n") + "\n" + text[j:]


def fetch(repo: str) -> list[dict]:
    out = subprocess.run(["gh", "api", "--paginate", f"repos/{repo}/contributors?anon=1&per_page=100"],
                         check=True, capture_output=True, text=True, encoding="utf-8").stdout
    decoder, pos, items = json.JSONDecoder(), 0, []
    while pos < len(out):
        while pos < len(out) and out[pos].isspace():
            pos += 1
        if pos >= len(out):
            break
        page, pos = decoder.raw_decode(out, pos)
        items.extend(page)
    return items


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default="Alex313031/thorium")
    parser.add_argument("--file", default="CREDITS.md")
    parser.add_argument("--from-json", help="use a saved contributors JSON instead of calling GitHub")
    args = parser.parse_args(argv)
    if args.from_json:
        with open(args.from_json, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = fetch(args.repo)
    with open(args.file, encoding="utf-8") as f:
        text = f.read()
    body = render_contributors(data)
    updated = replace_section(text, body)  # raises before anything is written
    temporary = f"{args.file}.tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as f:
        f.write(updated)
    os.replace(temporary, args.file)  # atomic: the file is either old or new, never partial
    print(f"{args.file}: {len(body.strip().splitlines())} contributor entries written")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
