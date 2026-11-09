#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Release notes for a Thoron release (ROADMAP P2.13, design section 8).

Sections, in this order: highlights (optional, written by hand), the Chromium version change and its
security fixes, Thoron's changes grouped by commit prefix (CONTRIBUTING.md), upstream Thorium commits
credited by author, patches added, removed and refreshed, fixed issues, downloads with SHA-256, credits.
Everything comes from git and local files; nothing is fetched. Author names are used, never emails.
    py -3 -I tools/release/changelog.py --version 158.0.8127.3000 --chromium-old 156.0.8078.80
        --chromium-new 158.0.8127.30 --repo . --since <last release tag>
        [--upstream <upstream tree> --upstream-since <commit>] [--series-old <tree> --series-new <tree>]
        [--security security.json] [--sha256sums SHA256SUMS] [--highlights highlights.md] --out NOTES.md
security.json is a list of {"cve", "severity", "title"} taken from the Chrome Releases post.
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

PREFIXES = {"sec": "Security", "perf": "Performance", "fix": "Fixes", "ui": "User interface",
            "build": "Build", "docs": "Documentation"}
CATEGORIES = ["Security", "Performance", "Fixes", "User interface", "Build", "Documentation", "Other changes"]
SEVERITIES = ["Critical", "High", "Medium", "Low"]
_PREFIX = re.compile(r"^(\w+):\s*(.+)$")
_MERGE = re.compile(r"^Merge (pull request|branch|remote-tracking branch)\b")
_ISSUE = re.compile(r"(?i)\b(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?)\s+#(\d+)")
_LONG_DASH = re.compile("[" + chr(0x2013) + chr(0x2014) + "]")
CHROME_RELEASES = "https://chromereleases.googleblog.com/"


class NotesError(Exception):
    pass


def _clean(text: str) -> str:
    return _LONG_DASH.sub("-", text).strip()


def group_commits(subjects: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    for s in subjects:
        s = s.strip()
        if not s or _MERGE.match(s):
            continue
        m = _PREFIX.match(s)
        if m and m.group(1).lower() in PREFIXES:
            groups[PREFIXES[m.group(1).lower()]].append(_clean(m.group(2)))
        else:
            groups["Other changes"].append(_clean(s))
    return groups


def issues(messages: list[str]) -> list[int]:
    return sorted({int(n) for m in messages for n in _ISSUE.findall(m)})


def series_changes(old: dict[str, str], new: dict[str, str]) -> dict[str, list[str]]:
    name = lambda p: Path(p).name
    return {"added": sorted(name(p) for p in new if p not in old),
            "removed": sorted(name(p) for p in old if p not in new),
            "refreshed": sorted(name(p) for p in new if p in old and old[p] != new[p])}


def sort_security(fixes: list[dict]) -> list[dict]:
    for f in fixes:
        if f.get("severity") not in SEVERITIES:
            raise NotesError(f"unknown severity {f.get('severity')!r} for {f.get('cve')}")
    return sorted(fixes, key=lambda f: (SEVERITIES.index(f["severity"]), f["cve"]))


def _log(repo: Path, since: str) -> list[dict]:
    out = subprocess.run(["git", "-C", str(repo), "log", "--no-merges", "--reverse",
                          "--format=%an%x1f%s%x1f%b%x1e", f"{since}..HEAD"],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    entries = []
    for rec in out.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        author, subject, body = (rec.split("\x1f") + ["", ""])[:3]
        entries.append({"author": author.strip(), "subject": subject.strip(), "body": body.strip()})
    return entries


def series_files(tree: Path) -> dict[str, str]:
    from tools.legal.patch_licenses import series_patches
    return {rel: (tree / rel).read_text(encoding="utf-8", errors="replace") for rel in series_patches(tree)
            if (tree / rel).is_file()}


def render(version: str, chromium_old: str, chromium_new: str, repo: Path, since: str,
           upstream: Path | None = None, upstream_since: str | None = None,
           series: dict | None = None, security: list | None = None, artifacts: list | None = None,
           highlights: str | None = None) -> str:
    out = [f"# Thoron {version}", "",
           f"Thoron {version} is based on Chromium {chromium_new} and the Thorium patch series.", ""]
    if highlights:
        out += ["## Highlights", "", _clean(highlights), ""]
    out += ["## Chromium", ""]
    if chromium_old == chromium_new:
        out.append(f"Chromium {chromium_new}, unchanged since the last release.")
    else:
        out.append(f"Chromium {chromium_old} to {chromium_new}. Details: [Chrome Releases]({CHROME_RELEASES}).")
    if security:
        out += ["", "### Security fixes", ""]
        out += [f"- {f['cve']} ({f['severity']}): {_clean(f['title'])}" for f in sort_security(security)]
    entries = _log(repo, since)
    groups = group_commits([e["subject"] for e in entries])
    out += ["", "## Thoron changes"]
    for cat in CATEGORIES:
        if groups[cat]:
            out += ["", f"### {cat}", ""] + [f"- {s}" for s in groups[cat]]
    if not any(groups.values()):
        out += ["", "No changes of our own."]
    out += ["", "## Upstream Thorium", ""]
    if upstream and upstream_since:
        up = [e for e in _log(upstream, upstream_since) if not _MERGE.match(e["subject"])]
        if up:
            out += [f"- {_clean(e['subject'])} ({e['author']})" for e in up]
            counts = Counter(e["author"] for e in up)
            thanks = ", ".join(f"{a} ({n} commit{'s' if n != 1 else ''})" for a, n in counts.most_common())
            out += ["", f"Thanks to: {thanks}."]
        else:
            out.append("No new upstream commits.")
    else:
        out.append("No new upstream commits.")
    out += ["", "## Patches", ""]
    series = series or {"added": [], "removed": [], "refreshed": []}
    for key, title in (("added", "Added"), ("removed", "Removed"), ("refreshed", "Refreshed")):
        names = series.get(key) or []
        out.append(f"- {title}: " + (", ".join(f"`{n}`" for n in names) if names else "none"))
    fixed = issues([e["subject"] + "\n" + e["body"] for e in entries])
    out += ["", "## Fixed issues", "", ", ".join(f"#{n}" for n in fixed) if fixed else "None reported."]
    out += ["", "## Downloads", ""]
    lines = [l.split(None, 1) for l in (artifacts or []) if l.strip()]
    if lines:
        out += ["| File | SHA-256 |", "|---|---|"] + [f"| `{n.strip().lstrip('*')}` | `{h}` |" for h, n in lines]
        out += ["", "Check the files against `SHA256SUMS` and its signature, as described in the README"
                    " (Verifying downloads)."]
    else:
        out.append("The files are attached to this release with `SHA256SUMS` and its signature.")
    out += ["", "## Credits", "",
            "Thoron is based on [Thorium](https://github.com/Alex313031/thorium) by Alex313031 and gz83, and on"
            " Chromium by The Chromium Authors. Every contributor and patch source is credited in"
            " [CREDITS.md](CREDITS.md).", ""]
    text = "\n".join(out)
    if _LONG_DASH.search(text):
        raise NotesError("long dash left in the notes")
    return text


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", required=True)
    p.add_argument("--chromium-old", required=True)
    p.add_argument("--chromium-new", required=True)
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--since", required=True)
    p.add_argument("--upstream", type=Path)
    p.add_argument("--upstream-since")
    p.add_argument("--series-old", type=Path)
    p.add_argument("--series-new", type=Path)
    p.add_argument("--security", type=Path)
    p.add_argument("--sha256sums", type=Path)
    p.add_argument("--highlights", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        series = (series_changes(series_files(a.series_old), series_files(a.series_new))
                  if a.series_old and a.series_new else None)
        text = render(a.version, a.chromium_old, a.chromium_new, a.repo, a.since, a.upstream, a.upstream_since,
                      series,
                      json.loads(a.security.read_text(encoding="utf-8")) if a.security else None,
                      a.sha256sums.read_text(encoding="utf-8").splitlines() if a.sha256sums else None,
                      a.highlights.read_text(encoding="utf-8") if a.highlights else None)
    except (NotesError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"changelog: {exc}", file=sys.stderr)
        return 2
    a.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
