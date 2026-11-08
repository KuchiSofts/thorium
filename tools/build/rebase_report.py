#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Rebase report: how an upstream Thorium patch series fits a newer Chromium (ROADMAP P1.8, P2.1).

Each patch is applied, in series order, to a temporary git index of its repository, so the
checkout's working tree and real index are never touched. Later patches see the effect of earlier
ones, as in a real apply. Status per patch:
    applied          applies exactly;
    fuzz             applies only with reduced context (git apply -C1); needs a refresh;
    already applied  its changes are already in this Chromium;
    rejected         does not apply; needs a rebase;
    missing          the patch file or the directory it applies in does not exist.

    py -3 -I tools/build/rebase_report.py --tree <upstream tree> --src <chromium src>
        --chromium 158.0.8127.30 --out docs/build/M158_REBASE_REPORT.md [--condition raspi]
Exit status 1 if any patch is rejected or missing.
"""
import argparse
import collections
import dataclasses
import os
import subprocess
import sys
import tempfile
from pathlib import Path

STATUS_ORDER = ("applied", "fuzz", "already applied", "rejected", "missing")


@dataclasses.dataclass(frozen=True)
class Entry:
    root: str
    patch: str
    conditions: tuple[str, ...]


def parse_series(text: str) -> list[Entry]:
    """Series lines: `[condition] <apply root>: <patch>` or `<patch>` (applied in src)."""
    entries = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        conditions: list[str] = []
        while line.startswith("[") and "]" in line:
            close = line.index("]")
            conditions += [c.strip().lower() for c in line[1:close].split(",") if c.strip()]
            line = line[close + 1:].strip()
        root, patch = (part.strip() for part in line.split(":", 1)) if ":" in line else (".", line)
        entries.append(Entry(root or ".", patch, tuple(conditions)))
    return entries


def select(entries: list[Entry], enabled: set[str]) -> list[Entry]:
    return [e for e in entries if set(e.conditions).issubset(enabled)]


def _git(args: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _detail(stderr: str, private_prefixes: tuple[str, ...]) -> str:
    errors = [l.strip() for l in stderr.splitlines() if l.strip().startswith("error:")][:2]
    text = "; ".join(errors)
    for prefix in private_prefixes:
        text = text.replace(prefix, "").replace(prefix.replace("\\", "/"), "")
    text = text.replace("|", "/")
    return text if len(text) <= 200 else text[:197] + "..."


def check_series(tree: Path, src: Path, conditions: set[str]) -> list[dict]:
    tree, src = Path(tree).resolve(), Path(src).resolve()
    entries = select(parse_series((tree / "patch_scripts" / "series" / "series").read_text(encoding="utf-8")),
                     {c.lower() for c in conditions})
    private = (str(tree) + os.sep, str(src) + os.sep)
    rows = []
    with tempfile.TemporaryDirectory(prefix="thoron-rebase-") as tmp:
        envs: dict[str, dict] = {}
        for e in entries:
            row = {"patch": e.patch, "root": e.root, "status": "", "detail": ""}
            rows.append(row)
            patch, apply_dir = tree / e.patch, src / e.root
            if not patch.is_file() or not apply_dir.is_dir():
                row["status"] = "missing"
                row["detail"] = "patch file not found" if not patch.is_file() else f"no directory {e.root}"
                continue
            repo_root = _git(["rev-parse", "--show-toplevel"], apply_dir).stdout.strip()
            env = envs.get(repo_root)
            if env is None:
                env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / f"index-{len(envs)}"))
                if _git(["read-tree", "HEAD"], Path(repo_root), env).returncode != 0:
                    raise RuntimeError(f"cannot read HEAD of {e.root}")
                envs[repo_root] = env
            rel = apply_dir.relative_to(Path(repo_root).resolve()).as_posix()
            base = ["apply", "--cached"] + ([f"--directory={rel}"] if rel != "." else [])

            def attempt(*extra: str) -> subprocess.CompletedProcess:
                return _git([*base, *extra, str(patch)], Path(repo_root), env)

            exact = attempt()
            if exact.returncode == 0:
                row["status"] = "applied"
            elif attempt("--check", "--reverse").returncode == 0:
                row["status"] = "already applied"
            elif attempt("-C1").returncode == 0:
                row["status"] = "fuzz"
            else:
                row["status"] = "rejected"
                row["detail"] = _detail(exact.stderr, private)
    return rows


def render(rows: list[dict], title: str, chromium: str) -> str:
    counts = collections.Counter(r["status"] for r in rows)
    summary = ", ".join(f"{s}: {counts[s]}" for s in STATUS_ORDER if counts[s]) + f" (total {len(rows)})"
    out = [f"# Rebase report: {title} on Chromium {chromium}", "",
           "Generated by `tools/build/rebase_report.py`. Every patch is applied in series order to a",
           "temporary git index, so the checkout itself is never changed. **fuzz** means the patch",
           "applies only with reduced context and should be refreshed; **rejected** means it needs a",
           "rebase. This is the starting point for the rebase (ROADMAP **P2.1**).", "",
           f"Summary: {summary}", "",
           "| # | Patch | Applies in | Status | Detail |", "|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        status = f"**{r['status']}**" if r["status"] in ("rejected", "missing") else r["status"]
        out.append(f"| {i} | `{r['patch']}` | `{r['root']}` | {status} | {r['detail']} |")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tree", required=True, type=Path)
    parser.add_argument("--src", required=True, type=Path)
    parser.add_argument("--chromium", required=True, help="Chromium version of --src, for the report title")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--condition", action="append", default=[])
    parser.add_argument("--title", default="upstream Thorium patch series")
    a = parser.parse_args(argv)
    rows = check_series(a.tree, a.src, set(a.condition))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(render(rows, a.title, a.chromium), encoding="utf-8", newline="\n")
    counts = collections.Counter(r["status"] for r in rows)
    print(", ".join(f"{s}: {counts[s]}" for s in STATUS_ORDER if counts[s]) + f" -> {a.out}")
    return 1 if counts["rejected"] or counts["missing"] else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
