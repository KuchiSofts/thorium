#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Docs and privacy linter — part of the definition of done for every change.

Checks: relative Markdown links resolve; CHANGELOG has [Unreleased] and well-formed releases;
ROADMAP has its date, legend and unique task IDs; with --private, files we author contain no
personal paths, personal emails or entries from the owner's private-strings list (never echoed).
    py -3 -I tools/docs/check_docs.py [--root .] [--private]
"""
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
EXTERNAL_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|#|//)", re.I)

RELEASE_HEADING_RE = re.compile(r"^## \[(?!Unreleased\])[^\]]+\]")
VALID_RELEASE_RE = re.compile(r"^## \[\d+(?:\.\d+)+[^\]]*\] - \d{4}-\d{2}-\d{2}\s*$")
LAST_UPDATED_RE = re.compile(r"Last updated:?\**\s*\d{4}-\d{2}-\d{2}")
LEGEND_SYMBOLS = ("⬜", "🔄", "✅", "⛔")
TASK_LINE_RE = re.compile(r"^\s*- \[[ xX]\]")
TASK_ID_RE = re.compile(r"^\s*- \[[ xX]\] \*\*((?:P\d+b?|S|Q|D|L|B)\.\d+)\*\*")

WIN_USER_RE = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+(?![<%{$])[^\\/\s]+")
HOME_RE = re.compile(r"/home/([a-z][^/\s]*)")
HOME_ALLOWED = {"user", "alex"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")
EMAIL_ALLOWED_RE = re.compile(
    r"(@users\.noreply\.github\.com|@chromium\.org|@example\.(com|org|net)|^git@github\.com|"
    r"^alex313031@gmail\.com)$", re.I)

# Files we author. Upstream docs are reference material: they legitimately contain upstream
# maintainers' public paths/emails and some pre-existing broken links (tracked in ROADMAP D.x).
OWNED_GLOBS = ("README.md", "ROADMAP.md", "CHANGELOG.md", "CREDITS.md", "SECURITY.md",
               "CONTRIBUTING.md", "NOTICE", "docs/design/**/*.md", "tools/**/*.md", "branding/**/*.md")
LINK_GLOBS = tuple(g for g in OWNED_GLOBS if g.endswith(".md")) + ("docs/upstream/**/*.md",)


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _prose_lines(path: Path):
    """Yield (line_number, text) outside fenced code blocks, with inline code removed."""
    fenced = False
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if not fenced:
            yield number, INLINE_CODE_RE.sub("", line)


def check_links(root: Path, files: list[Path]) -> list[str]:
    problems = []
    for path in files:
        for number, text in _prose_lines(path):
            for match in LINK_RE.finditer(text):
                target = match.group(1)
                if EXTERNAL_RE.match(target):
                    continue
                clean = unquote(target.split("#", 1)[0].split("?", 1)[0])
                if not clean:
                    continue
                resolved = (root / clean.lstrip("/")) if clean.startswith("/") else (path.parent / clean)
                if not resolved.exists():
                    problems.append(f"{_rel(root, path)}:{number}: broken link -> {target}")
    return problems


def check_changelog(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    problems = []
    if not any(line.strip() == "## [Unreleased]" for line in lines):
        problems.append(f"{path.name}: missing '## [Unreleased]' section")
    for number, line in enumerate(lines, 1):
        if RELEASE_HEADING_RE.match(line) and not VALID_RELEASE_RE.match(line):
            problems.append(f"{path.name}:{number}: release heading must be '## [X.Y.Z] - YYYY-MM-DD'")
    return problems


def check_roadmap(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    problems = []
    if not any(LAST_UPDATED_RE.search(line) for line in lines):
        problems.append(f"{path.name}: missing 'Last updated: YYYY-MM-DD'")
    if not any(all(symbol in line for symbol in LEGEND_SYMBOLS) for line in lines):
        problems.append(f"{path.name}: missing status legend line ({' '.join(LEGEND_SYMBOLS)})")
    seen: dict[str, int] = {}
    for number, line in enumerate(lines, 1):
        if not TASK_LINE_RE.match(line):
            continue
        match = TASK_ID_RE.match(line)
        if not match:
            problems.append(f"{path.name}:{number}: task line needs an ID like **P1.2** / **S.3**")
        elif match.group(1) in seen:
            problems.append(f"{path.name}:{number}: duplicate task ID {match.group(1)} (first at line {seen[match.group(1)]})")
        else:
            seen[match.group(1)] = number
    return problems


def _load_private(private_list: Path | None) -> list[str]:
    if not private_list or not private_list.is_file():
        return []
    entries = private_list.read_text(encoding="utf-8", errors="replace").splitlines()
    return [e.strip().lower() for e in entries if e.strip()]


def check_private(root: Path, files: list[Path], private_list: Path | None) -> list[str]:
    secrets = _load_private(private_list)
    problems = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            kinds = []
            if WIN_USER_RE.search(line):
                kinds.append("Windows user path")
            if any(m.group(1) not in HOME_ALLOWED for m in HOME_RE.finditer(line)):
                kinds.append("home directory path")
            if any(not EMAIL_ALLOWED_RE.search(m.group(0)) for m in EMAIL_RE.finditer(line)):
                kinds.append("email address")
            lowered = line.lower()
            if any(s in lowered for s in secrets):
                kinds.append("private-strings entry")
            for kind in kinds:
                problems.append(f"{_rel(root, path)}:{number}: private data ({kind})")
    return problems


def _glob(root: Path, patterns) -> list[Path]:
    found = set()
    for pattern in patterns:
        found.update(p for p in root.glob(pattern) if p.is_file())
    return sorted(found)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".")
    parser.add_argument("--private", action="store_true", help="also scan files we author for personal data")
    args = parser.parse_args(argv)
    root = Path(args.root)

    problems = check_links(root, _glob(root, LINK_GLOBS))
    if (root / "CHANGELOG.md").is_file():
        problems += check_changelog(root / "CHANGELOG.md")
    if (root / "ROADMAP.md").is_file():
        problems += check_roadmap(root / "ROADMAP.md")
    if args.private:
        problems += check_private(root, _glob(root, OWNED_GLOBS),
                                  Path.home() / ".githooks" / "private-strings.txt")

    for problem in problems:
        print(problem)
    print(f"check_docs: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
