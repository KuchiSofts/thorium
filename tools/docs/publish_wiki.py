#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Publish the project wiki from `docs/wiki/` (ROADMAP D.9).

The wiki's pages live in the repository, so they are reviewed, linted and versioned with everything else.
This copies them to the wiki of the GitHub repository: every `*.md` directly in `docs/wiki/` becomes a
page, and a page that is gone from there is removed. It is a step of every release.

    py -3 -I tools/docs/publish_wiki.py --repo <owner>/<name> [--source docs/wiki] [--dry-run]

It clones the wiki into a temporary folder, copies, commits with time stamps in UTC and pushes. GitHub
creates a wiki's repository only when its first page is saved on the website; until then this says so.
Exit status: 0 published or nothing to do, 1 it could not publish.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


class WikiError(RuntimeError):
    pass


def sync(source: Path, clone: Path) -> list[str]:
    """Make the clone's pages equal to the source's. Returns the names that were added, changed or removed."""
    source, clone = Path(source), Path(clone)
    pages = {p.name: p for p in source.glob("*.md") if p.is_file()}
    if "Home.md" not in pages:
        raise WikiError(f"{source} has no Home.md; a wiki needs its home page")
    touched = []
    for old in clone.glob("*.md"):
        if old.name not in pages:
            old.unlink()
            touched.append(old.name)
    for name, page in pages.items():
        data = page.read_bytes().replace(b"\r\n", b"\n")     # a Windows checkout may hold CRLF; the wiki gets LF
        target = clone / name
        if not target.is_file() or target.read_bytes() != data:
            target.write_bytes(data)
            touched.append(name)
    return sorted(touched)


def _git(folder: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(folder), "-c", "core.autocrlf=false", *args], capture_output=True, text=True,
                          env={**os.environ, "TZ": "UTC0"})


def publish(repo: str, source: Path, dry_run: bool = False, url: str | None = None,
            identity: tuple[str, str] | None = None) -> list[str]:
    url = url or f"https://github.com/{repo}.wiki.git"
    scratch = Path(tempfile.mkdtemp(prefix="thoron-wiki-"))
    try:
        clone = scratch / "wiki"
        # no line ending conversion: pages are compared and stored byte for byte
        got = subprocess.run(["git", "clone", "-q", "-c", "core.autocrlf=false", url, str(clone)],
                             capture_output=True, text=True)
        if got.returncode:
            raise WikiError(f"the wiki of {repo} cannot be cloned. If it has no page yet, save a first page once on "
                            f"the website (Wiki tab), then run this again. git said: {got.stderr.strip()[:200]}")
        touched = sync(source, clone)
        if not touched or dry_run:
            return touched
        name, mail = identity or tuple(
            subprocess.run(["git", "config", key], capture_output=True, text=True).stdout.strip()
            for key in ("user.name", "user.email"))
        if not mail.endswith("@users.noreply.github.com"):
            raise WikiError("the commit identity is not a GitHub noreply address; nothing was published")
        steps = (("add", "-A"),
                 ("-c", f"user.name={name}", "-c", f"user.email={mail}", "commit", "-q", "-m",
                  "Update the wiki from docs/wiki"),
                 ("push", "-q", "origin", "HEAD"))
        for step in steps:
            done = _git(clone, *step)
            if done.returncode:
                raise WikiError(f"git {step[-3] if step[0] == '-c' else step[0]} failed: {done.stderr.strip()[:200]}")
        return touched
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True, help="<owner>/<name> on GitHub")
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2] / "docs" / "wiki")
    parser.add_argument("--dry-run", action="store_true", help="show what would change; publish nothing")
    a = parser.parse_args(argv)
    try:
        touched = publish(a.repo, a.source, a.dry_run)
    except WikiError as exc:
        print(f"wiki: {exc}")
        return 1
    print(f"wiki: {'would change' if a.dry_run else 'published'} {len(touched)} page(s)"
          + (": " + ", ".join(touched) if touched else " (already current)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
