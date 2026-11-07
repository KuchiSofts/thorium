#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Docs and privacy linter — part of the definition of done for every change.

Checks: relative links (inline, reference-style, nested badges, HTML href/src) resolve to files that
exist with exact case, inside the repository and not git-ignored; CHANGELOG has [Unreleased] and
well-formed releases; ROADMAP has its date, legend and unique task IDs; with --private, every text
file we author contains no personal paths, personal e-mails or entries from the owner's
private-strings list (never echoed). A line containing "privacy-check: allow" is skipped (test
fixtures only).
    py -3 -I tools/docs/check_docs.py [--root REPO] [--private]
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

INLINE_LINK_RE = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REFERENCE_DEF_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?([^\s>]+)>?")
HTML_ATTR_RE = re.compile(r"(?i)\b(?:href|src)\s*=\s*[\"']([^\"']+)[\"']")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
EXTERNAL_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|#|//)", re.I)

RELEASE_HEADING_RE = re.compile(r"^## \[(?!Unreleased\])[^\]]+\]")
VALID_RELEASE_RE = re.compile(r"^## \[\d+(?:\.\d+)+[^\]]*\] - \d{4}-\d{2}-\d{2}\s*$")
LAST_UPDATED_RE = re.compile(r"Last updated:?\**\s*\d{4}-\d{2}-\d{2}")
LEGEND_SYMBOLS = ("⬜", "🔄", "✅", "⛔")
TASK_LINE_RE = re.compile(r"^\s*- \[[ xX]\]")
TASK_ID_RE = re.compile(r"^\s*- \[[ xX]\] \*\*((?:P\d+b?|S|Q|D|L|B)\.\d+)\*\*")

ALLOW_MARKER = "privacy-check: allow"
# C:\Users\x, c:/users/x, /c/Users/x (Git Bash), /mnt/c/Users/x (WSL), /Users/x (macOS); not URLs.  privacy-check: allow
USER_PATH_RE = re.compile(r"(?i)(?:\b[a-z]:[\\/]+|/mnt/[a-z]/|(?<![\w.~])/(?:[a-z]/)?)users[\\/]+(?![<%{$])[^\\/\s]+")
HOME_RE = re.compile(r"(?i)(?<![\w.~])/home/([^/\s]+)")  # privacy-check: allow
HOME_ALLOWED = {"user", "alex"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")
EMAIL_ALLOWED_RE = re.compile(
    r"(@users\.noreply\.github\.com|@chromium\.org|@example\.(com|org|net)|^git@github\.com|"
    r"^alex313031@gmail\.com)$", re.I)

# Files we author. Upstream docs are reference material: they legitimately contain upstream
# maintainers' public paths/emails and some pre-existing broken links (tracked in ROADMAP D.3).
OWNED_DOC_GLOBS = ("README.md", "ROADMAP.md", "CHANGELOG.md", "CREDITS.md", "SECURITY.md",
                   "CONTRIBUTING.md", "docs/design/**/*.md", "tools/**/*.md", "branding/**/*.md")
OWNED_PRIVATE_GLOBS = OWNED_DOC_GLOBS + ("NOTICE", ".gitignore", "tools/**/*.py", "branding/**/*.svg",
                                         "branding/**/*.html")
LINK_GLOBS = OWNED_DOC_GLOBS + ("docs/upstream/**/*.md",)


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


def _visible_files(root: Path) -> set[str] | None:
    """Tracked + untracked-but-not-ignored files (git), or None outside a git repository."""
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
                             "--exclude-standard"], capture_output=True)
    if result.returncode != 0:
        return None
    return {p.decode("utf-8", "replace") for p in result.stdout.split(b"\0") if p}


def _exists_exact(root: Path, rel: str) -> bool:
    current = root
    for part in rel.split("/"):
        if part in ("", "."):
            continue
        try:
            if part not in os.listdir(current):
                return False
        except OSError:
            return False
        current = current / part
    return True


def _link_targets(text: str):
    for rx in (INLINE_LINK_RE, REFERENCE_DEF_RE, HTML_ATTR_RE):
        for match in rx.finditer(text):
            yield match.group(1)


def check_links(root: Path, files: list[Path]) -> list[str]:
    root = root.resolve()
    visible = _visible_files(root)
    problems = []
    for path in files:
        for number, text in _prose_lines(path):
            for target in _link_targets(text):
                if EXTERNAL_RE.match(target):
                    continue
                clean = unquote(target.split("#", 1)[0].split("?", 1)[0])
                if not clean:
                    continue
                base = root if clean.startswith("/") else path.resolve().parent
                resolved = os.path.normpath(os.path.join(base, clean.lstrip("/")))
                rel = Path(os.path.relpath(resolved, root)).as_posix()
                if rel == ".." or rel.startswith("../"):
                    ok = False
                elif visible is not None:
                    ok = rel in visible or any(v.startswith(rel.rstrip("/") + "/") for v in visible)
                else:
                    ok = _exists_exact(root, rel)
                if not ok:
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
    raw = private_list.read_bytes()
    text = raw.decode("utf-16") if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else raw.decode("utf-8-sig", "replace")
    return [e.strip().lower() for e in text.splitlines() if e.strip()]


def check_private(root: Path, files: list[Path], private_list: Path | None) -> list[str]:
    secrets = _load_private(private_list)
    problems = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            if ALLOW_MARKER in line:
                continue
            kinds = []
            if USER_PATH_RE.search(line):
                kinds.append("user directory path")
            if any(m.group(1).lower() not in HOME_ALLOWED for m in HOME_RE.finditer(line)):
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
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]),
                        help="repository root (default: the repository containing this script)")
    parser.add_argument("--private", action="store_true", help="also scan files we author for personal data")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not (root / "README.md").is_file():
        print(f"check_docs: {root} has no README.md; pass --root <repository root>")
        return 2

    problems = check_links(root, _glob(root, LINK_GLOBS))
    if (root / "CHANGELOG.md").is_file():
        problems += check_changelog(root / "CHANGELOG.md")
    if (root / "ROADMAP.md").is_file():
        problems += check_roadmap(root / "ROADMAP.md")
    if args.private:
        private_list = Path.home() / ".githooks" / "private-strings.txt"
        if not private_list.is_file():
            print(f"note: no private-strings list at {private_list}; only built-in patterns are checked")
        problems += check_private(root, _glob(root, OWNED_PRIVATE_GLOBS), private_list)

    for problem in problems:
        print(problem)
    print(f"check_docs: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
