#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Write BUILDINFO.json: exactly what a Thoron build was made from, with no personal data.

Every path is written relative to the build root (`<build_root>/...`); any path inside a user
directory is replaced by `<redacted>`.
    py -3 -I tools/build/buildinfo.py --root J:\\thoron-build --src J:\\thoron-build\\chromium\\src
        --repo . --upstream-ref "gz83 M156.0.8078.28 de9a1bc6" --variant win-x64-avx2
        --args out\\thoron\\args.gn --toolchain toolchain.json --started EPOCH --finished EPOCH --out BUILDINFO.json
"""
import argparse
import datetime
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

USER_DIR_RE = re.compile(r"(?i)^(?:[a-z]:/+users/|/home/|/users/|/mnt/[a-z]/users/)")


def chromium_version(src: Path) -> str:
    fields = dict(line.split("=", 1) for line in (src / "chrome" / "VERSION").read_text(encoding="utf-8").split()
                  if "=" in line)
    return ".".join(fields[k] for k in ("MAJOR", "MINOR", "BUILD", "PATCH"))


def _strip_comment(line: str) -> str:
    in_string = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_string = not in_string
        elif ch == "#" and not in_string:
            return line[:i]
    return line


def _arg_lines(args_text: str) -> list[str]:
    lines = (" ".join(_strip_comment(l).split()) for l in args_text.splitlines())
    return [l for l in lines if l]


def gn_args_digest(args_text: str) -> str:
    return hashlib.sha256("\n".join(sorted(_arg_lines(args_text))).encode("utf-8")).hexdigest()


def redact(path: str, build_root: str) -> str:
    norm = path.replace("\\", "/")
    root = str(build_root).replace("\\", "/").rstrip("/")
    if norm.lower() == root.lower() or norm.lower().startswith(root.lower() + "/"):
        return "<build_root>" + norm[len(root):]
    if USER_DIR_RE.search(norm):
        return "<redacted>"
    return path


def _git(repo: Path, *args: str) -> str | None:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def _utc(epoch: float) -> str:
    return datetime.datetime.fromtimestamp(epoch, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect(build_root: Path, src: Path, thoron_repo: Path, upstream_ref: str, variant: str, args_text: str,
            toolchain: dict, started: float, finished: float) -> dict:
    depot = Path(build_root) / "depot_tools"
    return {
        "schema": 1,
        "product": "Thoron",
        "variant": variant,
        "chromium_version": chromium_version(Path(src)),
        "thoron_commit": _git(thoron_repo, "rev-parse", "HEAD"),
        "thoron_dirty": bool(_git(thoron_repo, "status", "--porcelain")),
        "upstream_ref": upstream_ref,
        "depot_tools_commit": _git(depot, "rev-parse", "HEAD") if depot.is_dir() else None,
        "gn_args_sha256": gn_args_digest(args_text),
        "gn_args": _arg_lines(args_text),
        "toolchain": {k: redact(v, str(build_root)) if isinstance(v, str) else v for k, v in toolchain.items()},
        "host": {"os": platform.system(), "release": platform.release(), "cpus": os.cpu_count()},
        "started_utc": _utc(started),
        "finished_utc": _utc(finished),
        "duration_s": int(finished - started),
    }


def write(path: Path, info: dict) -> None:
    Path(path).write_text(json.dumps(info, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("--root", "--src", "--repo", "--upstream-ref", "--variant", "--args", "--toolchain", "--out"):
        parser.add_argument(name, required=True)
    parser.add_argument("--started", type=float, required=True)
    parser.add_argument("--finished", type=float, required=True)
    a = parser.parse_args(argv)
    toolchain = json.loads(Path(a.toolchain).read_text(encoding="utf-8"))
    info = collect(Path(a.root), Path(a.src), Path(a.repo), a.upstream_ref, a.variant,
                   Path(a.args).read_text(encoding="utf-8"), toolchain, a.started, a.finished)
    write(Path(a.out), info)
    print(f"wrote {a.out}: {info['product']} {info['chromium_version']} {info['variant']}, {info['duration_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
