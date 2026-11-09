#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Origin, Author and License lines in every patch of the series (ROADMAP S.7).

`lint` names every patch whose text before the first diff lacks one of the three lines, and every
header whose licence differs from the audited research. `add` writes the lines into patches that have
none, from the research in tools/legal/patch_origins.tsv (via patch_licenses.classify); an existing
header is never changed.
    py -3 -I tools/legal/patch_headers.py lint --tree <upstream tree> --research tools/legal/patch_origins.tsv
    py -3 -I tools/legal/patch_headers.py add --tree <upstream tree> --credits CREDITS.md --research tools/legal/patch_origins.tsv
"""
import argparse
import re
import sys
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.legal import patch_licenses as pl  # noqa: E402

KEYS = ("Origin", "Author", "License")
_FIELD = re.compile(r"(?im)^(Origin|Author|License):[ \t]*(.+?)[ \t]*\r?$")
_DIFF_START = re.compile(r"(?m)^(?:diff --git |--- a/|Index: )")
_SINGLE = re.compile(r"^[^,;()]+\(([^()]+)\)$")   # "Project (people)"


class HeaderError(Exception):
    pass


def _prelude(text: str) -> str:
    m = _DIFF_START.search(text)
    return text[:m.start()] if m else text


def header_fields(text: str) -> dict[str, str]:
    return {k.lower(): v for k, v in _FIELD.findall(_prelude(text))}


def missing(text: str) -> list[str]:
    fields = header_fields(text)
    return [k for k in KEYS if k.lower() not in fields]


def _author(origin: str) -> str:
    m = _SINGLE.match(origin.strip())
    return m.group(1).strip() if m else origin.strip()


def add_header(text: str, row: dict) -> str:
    """Text with Origin/Author/License lines from a research row; unchanged if it has all three."""
    gone = missing(text)
    if not gone:
        return text
    if len(gone) != len(KEYS):
        raise HeaderError(f"partial header (missing {', '.join(gone)}); fix it by hand")
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = [f"Origin: {row['origin']}", f"Author: {_author(row['origin'])}", f"License: {row['license']}",
             "Source and evidence: Thoron's licence research, docs/legal/PATCH_ORIGINS.md", "", ""]
    return nl.join(lines) + text


def lint(tree: Path, research: dict | None = None) -> list[str]:
    problems = []
    for rel in pl.series_patches(tree):
        path = tree / rel
        if not path.is_file():
            problems.append(f"{rel}: missing file")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        gone = missing(text)
        if gone:
            problems.append(f"{rel}: no {', '.join(gone)} line")
            continue
        name = Path(rel).name
        if research and name in research:
            have, want = header_fields(text)["license"], research[name]["license"]
            if have != want:
                problems.append(f"{rel}: header licence {have} differs from the research ({want})")
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("lint", "add"):
        p = sub.add_parser(name)
        p.add_argument("--tree", type=Path, required=True)
        p.add_argument("--research", type=Path, required=True)
        if name == "add":
            p.add_argument("--credits", type=Path, required=True)
    a = parser.parse_args(argv)
    research = pl.load_research(a.research.read_text(encoding="utf-8"))
    if a.cmd == "lint":
        problems = lint(a.tree, research)
        for p in problems:
            print(f"patch_headers: {p}", file=sys.stderr)
        print("patch headers: OK" if not problems else f"patch headers: {len(problems)} problem(s)")
        return 1 if problems else 0
    projects = pl.load_projects(a.credits.read_text(encoding="utf-8"))
    patches_md = (a.tree / "docs" / "PATCHES.md").read_text(encoding="utf-8", errors="replace")
    added = 0
    for rel in pl.series_patches(a.tree):
        path = a.tree / rel
        raw = path.read_bytes().decode("utf-8", errors="surrogateescape")
        if not missing(raw):
            continue
        row = pl.classify(raw, patches_md, path.name, projects, research)
        if row["license"] == "UNKNOWN":
            print(f"patch_headers: {rel}: licence unknown, not changed", file=sys.stderr)
            continue
        path.write_bytes(add_header(raw, row).encode("utf-8", errors="surrogateescape"))
        added += 1
    print(f"patch headers: added to {added} patch(es)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
