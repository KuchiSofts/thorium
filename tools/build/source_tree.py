#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""The browser's source as an overlay on one pinned upstream commit (ROADMAP P2.25).

Thoron's changes to the browser are a patch series on top of Thorium's. `main` keeps them as

    source/UPSTREAM.json   the upstream repository, the pinned commit, the Chromium version, and the
                           git tree hash of the finished build tree
    source/overlay/        every file Thoron adds or changes on top of that commit, byte for byte
    source/REMOVED.txt     the upstream files Thoron leaves out, one path per line

so the repository holds everything a release is built from without copying upstream's files into it.

    export       write those three from a work tree whose HEAD is the build tree (nothing uncommitted)
    verify       put the overlay on the pinned commit in memory and compare the tree hash on record
    materialize  verify, then write the build tree into a new, empty folder

    py -3 -I tools/build/source_tree.py export --tree <work tree> --base <upstream commit> --out source \\
        --chromium 158.0.8127.30 --repository https://github.com/<owner>/<repo>
    py -3 -I tools/build/source_tree.py verify --upstream <clone of upstream> --source source
    py -3 -I tools/build/source_tree.py materialize --upstream <clone of upstream> --source source --out <folder>

A file of ours that must not be published (it holds credentials that are not Thoron's) can be withheld:
`export --withhold <path>` leaves it out of the overlay and records only its git blob hash, so the tree
hash still verifies. `materialize` then works only where that content exists (the build machine) and
says which file is missing anywhere else.

`verify` and `materialize` need a clone that has the pinned commit. They use a private index file and
leave that clone's own index, HEAD and files alone. Files are compared and written as raw bytes: no line
ending is converted. A path that is absolute or leaves the tree is refused.
Exit status: 0 done, 1 the source does not verify or cannot be used.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

OVERLAY, REMOVED, UPSTREAM = "overlay", "REMOVED.txt", "UPSTREAM.json"


class SourceError(RuntimeError):
    pass


def _git(repo: Path, *args: str, env: dict | None = None, data: bytes | None = None) -> bytes:
    done = subprocess.run(["git", "-C", str(repo), "-c", "core.autocrlf=false", "-c", "core.fileMode=false", *args],
                          capture_output=True, input=data, env={**os.environ, **(env or {})})
    if done.returncode:
        raise SourceError(f"git {' '.join(args[:2])} failed: {done.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return done.stdout


def _text(repo: Path, *args: str, env: dict | None = None) -> str:
    return _git(repo, *args, env=env).decode("utf-8", "replace").strip()


def _safe(path: str) -> str:
    """A path inside the tree, in git's form; anything else is refused."""
    pure = PurePosixPath(path)
    if (not path or path != pure.as_posix() or pure.is_absolute() or ".." in pure.parts or ":" in pure.parts[0]
            or "\\" in path):
        raise SourceError(f"not a path inside the tree: {path!r}")
    return path


def export(tree: Path, base: str, out: Path, chromium: str, repository: str,
           withhold: list[str] | None = None) -> dict:
    """Write the overlay, the list of removed files and UPSTREAM.json from the work tree's HEAD."""
    tree, out = Path(tree), Path(out)
    if _text(tree, "status", "--porcelain"):
        raise SourceError(f"{tree} has uncommitted changes; commit them first, the overlay is made from HEAD")
    commit = _text(tree, "rev-parse", "--verify", f"{base}^{{commit}}")
    changed = _git(tree, "diff", "--no-renames", "--name-status", "-z", commit, "HEAD").decode("utf-8").split("\0")
    ours, removed = [], []
    for status, path in zip(changed[0::2], changed[1::2]):
        (removed if status == "D" else ours).append(_safe(path))
    modes = {}
    for entry in _git(tree, "ls-tree", "-r", "-z", "HEAD").decode("utf-8").split("\0"):
        if entry:
            meta, path = entry.split("\t", 1)
            modes[path] = meta.split()[0]
    withheld = {}
    for path in sorted(withhold or []):
        if path not in ours:
            raise SourceError(f"{path} cannot be withheld: it is not a file we add or change")
        withheld[path] = _text(tree, "rev-parse", f"HEAD:{path}")
    overlay = out / OVERLAY
    wanted = {p for p in ours if p not in withheld}
    if overlay.exists():                    # drop what is no longer ours, file by file
        for old in sorted(overlay.rglob("*"), reverse=True):
            if old.is_file() and old.relative_to(overlay).as_posix() not in wanted:
                old.unlink()
            elif old.is_dir():
                try:
                    old.rmdir()             # only when empty; a folder still in use stays
                except OSError:
                    pass
    for path in ours:
        if path in withheld:
            continue                        # never written: only its hash goes on record
        if modes[path] not in ("100644", "100755"):
            raise SourceError(f"{path}: only plain files can be in the overlay (mode {modes[path]})")
        target = overlay.joinpath(*path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_git(tree, "cat-file", "blob", f"HEAD:{path}"))
    (out / REMOVED).write_bytes(("".join(p + "\n" for p in sorted(removed))).encode("utf-8"))
    info = {"repository": repository, "commit": commit, "chromium": chromium,
            "tree": _text(tree, "rev-parse", "HEAD^{tree}"),
            "executable": sorted(p for p in ours if modes[p] == "100755"),
            "withheld": withheld, "changed": len(ours), "removed": len(removed)}
    (out / UPSTREAM).write_bytes((json.dumps(info, indent=2) + "\n").encode("utf-8"))
    return info


def _read(source: Path) -> tuple[dict, list[str], list[str]]:
    source = Path(source)
    try:
        info = json.loads((source / UPSTREAM).read_text(encoding="utf-8"))
        removed = [_safe(line.strip()) for line in (source / REMOVED).read_text(encoding="utf-8").splitlines()
                   if line.strip()]
    except (OSError, ValueError) as exc:
        raise SourceError(f"{source} is not a source folder: {exc}") from exc
    overlay = source / OVERLAY
    ours = sorted(_safe(p.relative_to(overlay).as_posix()) for p in overlay.rglob("*") if p.is_file())
    for key in ("commit", "tree", "executable"):
        if key not in info:
            raise SourceError(f"{source / UPSTREAM} has no '{key}'")
    for path in info["executable"]:
        _safe(path)
    info.setdefault("withheld", {})
    for path, blob in info["withheld"].items():
        if len(blob) != 40 or any(c not in "0123456789abcdef" for c in blob):
            raise SourceError(f"{source / UPSTREAM}: the hash on record for {_safe(path)} is not a git blob hash")
        if path in ours:
            raise SourceError(f"{path} is withheld and must not be in the overlay")
    return info, ours, removed


def _build_index(upstream: Path, source: Path, index: Path) -> tuple[dict, str]:
    """Put the pinned commit plus the overlay into a private index; returns the record and the tree hash."""
    info, ours, removed = _read(source)
    env = {"GIT_INDEX_FILE": str(index)}
    try:
        _git(upstream, "cat-file", "-e", f"{info['commit']}^{{commit}}")
    except SourceError as exc:
        raise SourceError(f"{upstream} does not have the pinned upstream commit {info['commit'][:12]}; "
                          f"fetch it from {info.get('repository', 'the upstream repository')}") from exc
    _git(upstream, "read-tree", info["commit"], env=env)
    for path in removed:
        _git(upstream, "update-index", "--force-remove", "--", path, env=env)
    executable = set(info["executable"])
    for path in ours:
        blob = _git(upstream, "hash-object", "-w", "--no-filters", "--stdin",
                    data=(Path(source) / OVERLAY).joinpath(*path.split("/")).read_bytes()).decode().strip()
        mode = "100755" if path in executable else "100644"
        _git(upstream, "update-index", "--add", "--cacheinfo", f"{mode},{blob},{path}", env=env)
    for path, blob in info["withheld"].items():      # known by hash only; the content may not be here
        mode = "100755" if path in executable else "100644"
        _git(upstream, "update-index", "--add", "--cacheinfo", f"{mode},{blob},{path}", env=env)
    return info, _text(upstream, "write-tree", "--missing-ok", env=env)


def verify(upstream: Path, source: Path) -> str:
    """The tree hash of pinned commit + overlay, checked against the one on record."""
    with tempfile.TemporaryDirectory(prefix="thoron-index-") as scratch:
        info, tree = _build_index(Path(upstream), Path(source), Path(scratch) / "index")
    if tree != info["tree"]:
        raise SourceError(f"the source does not match its record: it makes tree {tree}, "
                          f"{UPSTREAM} says {info['tree']}")
    return tree


def materialize(upstream: Path, source: Path, out: Path) -> str:
    """Verify, then write the build tree into `out`, which must be new or empty."""
    upstream, out = Path(upstream), Path(out)
    if out.exists() and any(out.iterdir()):
        raise SourceError(f"{out} is not empty; the build tree is only written into a new or empty folder")
    with tempfile.TemporaryDirectory(prefix="thoron-index-") as scratch:
        index = Path(scratch) / "index"
        info, tree = _build_index(upstream, Path(source), index)
        if tree != info["tree"]:
            raise SourceError(f"the source does not match its record: it makes tree {tree}, "
                              f"{UPSTREAM} says {info['tree']}; nothing was written")
        missing = [path for path, blob in sorted(info["withheld"].items())
                   if subprocess.run(["git", "-C", str(upstream), "cat-file", "-e", blob], capture_output=True).returncode]
        if missing:
            raise SourceError(f"the content of {len(missing)} withheld file(s) is not in {upstream}: "
                              f"{', '.join(missing)}; nothing was written")
        out.mkdir(parents=True, exist_ok=True)
        _git(upstream, f"--work-tree={out}", "checkout-index", "--all", "--force", f"--prefix={out.as_posix()}/",
             env={"GIT_INDEX_FILE": str(index)})
    return tree


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--tree", required=True, type=Path)
    e.add_argument("--base", required=True, help="the upstream commit the work tree is built on")
    e.add_argument("--out", required=True, type=Path)
    e.add_argument("--chromium", required=True)
    e.add_argument("--repository", required=True, help="where the upstream commit can be fetched from")
    e.add_argument("--withhold", action="append", default=[], metavar="PATH",
                   help="a file of ours that is recorded by hash only and never written (repeatable)")
    for name in ("verify", "materialize"):
        c = sub.add_parser(name)
        c.add_argument("--upstream", required=True, type=Path, help="a clone that has the pinned commit")
        c.add_argument("--source", required=True, type=Path)
        if name == "materialize":
            c.add_argument("--out", required=True, type=Path)
    a = parser.parse_args(argv)
    try:
        if a.cmd == "export":
            info = export(a.tree, a.base, a.out, a.chromium, a.repository, a.withhold)
            print(f"source tree: {info['changed']} files of ours ({len(info['withheld'])} withheld), "
                  f"{info['removed']} removed, on upstream {info['commit'][:12]}; tree {info['tree']}")
        elif a.cmd == "verify":
            print(f"source tree: verified, tree {verify(a.upstream, a.source)}")
        else:
            print(f"source tree: written to {a.out}, tree {materialize(a.upstream, a.source, a.out)}")
    except SourceError as exc:
        print(f"source tree: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
