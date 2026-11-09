#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Licence inventory of every patch in an upstream patch series (ROADMAP L.1).

Priority: `Origin:` / `License:` header lines in the patch; otherwise our audited research row
(`--research`, a TSV: patch, origin, license, evidence); otherwise the patch's row in
`docs/PATCHES.md`, matched against the project/licence table in `CREDITS.md`; otherwise UNKNOWN.
A patch that draws on a project whose licence is not yet confirmed stays UNKNOWN (never guessed);
one whose author publishes no licence at all is NOT STATED.
    py -3 -I tools/legal/patch_licenses.py --tree <upstream tree> --credits CREDITS.md \
        --research tools/legal/patch_origins.tsv --out docs/legal/PATCH_LICENSES.md
Exit status 1 while any patch is UNKNOWN or NOT STATED, or a research row names a patch not in the series.
"""
import argparse
import collections
import re
import sys
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

HEADER_RE = re.compile(r"(?im)^(Origin|Author|License):\s*(.+?)\s*$")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
LONG_DASH_RE = re.compile("[" + chr(0x2013) + chr(0x2014) + "]")
NOT_STATED = "NOT STATED"
BLOCKING = ("UNKNOWN", NOT_STATED)
LICENCE_IDS = {"BSD-2-Clause", "BSD-3-Clause", "MIT", "Apache-2.0", "MPL-2.0", "GPL-2.0-only", "GPL-3.0",
               "LGPL-2.1", "ISC", "Unlicense", "public domain"}
FALLBACKS = (  # used only when no third-party project matched
    (re.compile(r"\bThorium\b"), "Thorium", "BSD-3-Clause"),
    (re.compile(r"(?i)crrev\.com|chromium-review|chromium\.googlesource|\bbackport"), "Chromium", "BSD-3-Clause"),
)


def load_projects(credits_md: str) -> dict[str, dict]:
    projects = {}
    for line in credits_md.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or not cells[1].startswith("http"):
            continue
        name, link, licence = cells
        if re.search(r"(?i)not stated", licence):
            licence = NOT_STATED
        elif re.search(r"(?i)inventory|pending|unknown", licence):
            licence = "UNKNOWN"
        projects[name] = {"link": link.rstrip("/").lower(), "license": licence}
    return projects


def load_research(tsv: str) -> dict[str, dict]:
    """Audited origin rows. Every licence is an allowed id (joined by ' AND ') or NOT STATED."""
    rows = {}
    for number, line in enumerate(tsv.splitlines(), 1):
        if not line.strip() or line.startswith("#") or line.startswith("patch\t"):
            continue
        cells = line.split("\t")
        if len(cells) != 4 or not all(c.strip() for c in cells):
            raise ValueError(f"research line {number}: expected 4 tab-separated cells")
        patch, origin, licence, evidence = (c.strip() for c in cells)
        if LONG_DASH_RE.search(line):
            raise ValueError(f"research line {number}: long dash")
        if licence != NOT_STATED and not all(part in LICENCE_IDS for part in licence.split(" AND ")):
            raise ValueError(f"research line {number}: licence {licence!r} is not an allowed id")
        if patch in rows:
            raise ValueError(f"research line {number}: duplicate row for {patch}")
        rows[patch] = {"patch": patch, "origin": origin, "license": licence, "evidence": evidence}
    return rows


def _row_for(patches_md: str, name: str) -> str | None:
    return next((l for l in patches_md.splitlines() if l.lstrip().startswith("|") and f"`{name}`" in l), None)


def _clean(text: str, limit: int = 160) -> str:
    text = LONG_DASH_RE.sub("-", LINK_RE.sub(r"\1", text)).replace("|", "/").strip()
    return text if len(text) <= limit else text[:limit - 3] + "..."


def classify(patch_text: str, patches_md: str, name: str, projects: dict[str, dict],
             research: dict[str, dict] | None = None) -> dict:
    head = "\n".join(patch_text.splitlines()[:40])
    fields = {k.lower(): v for k, v in HEADER_RE.findall(head)}
    if "license" in fields:
        # a header that agrees with the research or PATCHES.md (for example one written from them by
        # patch_headers.py) keeps their evidence; otherwise the header wins
        without = classify("", patches_md, name, projects, research)
        if without["license"] == fields["license"]:
            return without
        return {"patch": name, "origin": fields.get("origin", "unstated"), "license": fields["license"],
                "evidence": "patch header"}
    if research and name in research:
        found = research[name]
        return {"patch": name, "origin": found["origin"], "license": found["license"],
                "evidence": "research: " + _clean(found["evidence"], 220)}
    row = _row_for(patches_md, name)
    if row is None:
        return {"patch": name, "origin": "unknown", "license": "UNKNOWN", "evidence": "not listed in docs/PATCHES.md"}
    description = "|".join(row.strip().strip("|").split("|")[1:])
    lowered = row.lower()
    matched = []
    for project, info in projects.items():
        core = project.split(" (")[0]
        if info["link"] in lowered or re.search(r"(?i)(?<![\w-])" + re.escape(core) + r"(?![\w-])", row):
            matched.append((project.split(" (")[0], info["license"]))
    if not matched:
        for rx, origin, licence in FALLBACKS:
            if rx.search(row):
                matched.append((origin, licence))
                break
    if not matched:
        return {"patch": name, "origin": "unknown", "license": "UNKNOWN", "evidence": _clean(description)}
    licences = sorted({lic for _, lic in matched})
    blocking = [b for b in BLOCKING if b in licences]
    licence = blocking[0] if blocking else " AND ".join(licences)
    return {"patch": name, "origin": ", ".join(o for o, _ in matched), "license": licence,
            "evidence": _clean(description)}


def render_table(rows: list[dict], source: str = "the upstream patch series") -> str:
    rows = sorted(rows, key=lambda r: (r["license"] not in BLOCKING, r["license"] != "UNKNOWN", r["patch"].lower()))
    counts = collections.Counter(r["license"] for r in rows)
    out = ["# Patch licence inventory", "",
           f"Generated by `tools/legal/patch_licenses.py` from {source}: each patch's header, else our audited",
           "research in `tools/legal/patch_origins.tsv` (method: `docs/legal/PATCH_ORIGINS.md`), else its row in",
           "the upstream `docs/PATCHES.md`, matched against the project licences in `CREDITS.md`. Rows marked",
           "**UNKNOWN** need research and rows marked **NOT STATED** need the author's permission (or a rewrite)",
           "before the first release (ROADMAP **L.1**).", "",
           "Summary: " + ", ".join(f"{lic}: {n}" for lic, n in sorted(counts.items())) + f" (total {len(rows)})", "",
           "| Patch | Origin | Licence | Evidence |", "|---|---|---|---|"]
    out += [f"| `{r['patch']}` | {r['origin']} | {'**' + r['license'] + '**' if r['license'] in BLOCKING else r['license']} | "
            f"{r['evidence']} |" for r in rows]
    return "\n".join(out) + "\n"


def series_patches(tree: Path) -> list[str]:
    """Every patch path in the series, conditional ones included (same parser as the rebase report)."""
    from tools.build.rebase_report import parse_series
    text = (tree / "patch_scripts" / "series" / "series").read_text(encoding="utf-8")
    return [e.patch for e in parse_series(text)]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tree", required=True, type=Path)
    parser.add_argument("--credits", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--source", default="the upstream patch series")
    parser.add_argument("--research", type=Path, help="audited origins TSV (tools/legal/patch_origins.tsv)")
    a = parser.parse_args(argv)
    projects = load_projects(a.credits.read_text(encoding="utf-8"))
    research = load_research(a.research.read_text(encoding="utf-8")) if a.research else {}
    patches_md = (a.tree / "docs" / "PATCHES.md").read_text(encoding="utf-8", errors="replace")
    rows = []
    for rel in series_patches(a.tree):
        path = a.tree / rel
        name = Path(rel).name
        if not path.is_file():
            rows.append({"patch": name, "origin": "unknown", "license": "UNKNOWN", "evidence": "patch file missing"})
            continue
        rows.append(classify(path.read_text(encoding="utf-8", errors="replace"), patches_md, name, projects, research))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(render_table(rows, a.source), encoding="utf-8", newline="\n")
    unknown = [r["patch"] for r in rows if r["license"] == "UNKNOWN"]
    not_stated = [r["patch"] for r in rows if r["license"] == NOT_STATED]
    stale = sorted(set(research) - {r["patch"] for r in rows})
    print(f"{len(rows)} patches; {len(unknown)} UNKNOWN; {len(not_stated)} NOT STATED -> {a.out}")
    for name in stale:
        print(f"stale research row (patch not in the series): {name}")
    return 1 if unknown or not_stated or stale else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
