#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Build pipeline helpers: preflight checks, upstream setup with reject detection, BUILDINFO.

    py -3 -I tools/build/pipeline.py preflight --root C:\\thoron-build --need-gb 250 [--require-wsl-memory-gb 44]
    py -3 -I tools/build/pipeline.py apply --tree C:\\thoron-build\\upstream-M156 --src C:\\thoron-build\\chromium\\src --profile avx2 [--log FILE]
    py -3 -I tools/build/pipeline.py buildinfo <buildinfo.py arguments>
"""
import argparse
import ctypes
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):  # running as a script under `py -3 -I`: make `tools` importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

GB = 1024 ** 3
CLOUD_PATH_RE = re.compile(r"(?i)google ?drive|my ?drive|dropbox|onedrive|icloud|[\\/]box[\\/]|[\\/]mega[\\/]")
CLOUD_LABEL_RE = re.compile(r"(?i)google|dropbox|onedrive|icloud|cloud")
SKIP_DIRS = {"out", ".git"}


def _drive_root(path: Path) -> Path:
    return Path(Path(path).resolve().anchor or "/")


def _volume_label(path: Path) -> str | None:
    if os.name != "nt":
        return None
    buf = ctypes.create_unicode_buffer(261)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(str(_drive_root(path)), buf, 261, None, None, None, None, 0)
    return buf.value if ok else None


def _existing_ancestor(path: Path) -> Path:
    path = Path(path).resolve()
    while not path.exists() and path.parent != path:
        path = path.parent
    return path


def _mem_total_gb() -> float | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) / (1024 ** 2)
    except OSError:
        return None
    return None


def preflight(build_root: Path, need_free_gb: int, require_wsl_limits: dict | None = None) -> list[str]:
    root = Path(build_root)
    text = str(root)
    problems = []
    cloud_roots = [os.environ.get(v) for v in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial")]
    if CLOUD_PATH_RE.search(text) or any(c and text.lower().startswith(c.lower()) for c in cloud_roots):
        problems.append(f"build root is in a cloud-synced location: {text}")
    label = _volume_label(root)
    if label and CLOUD_LABEL_RE.search(label):
        problems.append(f"build drive is labelled '{label}' (a cloud sync drive)")
    if " " in text:
        problems.append("build root contains spaces; Chromium tooling needs a path without spaces")
    free_gb = shutil.disk_usage(_existing_ancestor(root)).free / GB
    if free_gb < need_free_gb:
        problems.append(f"only {free_gb:.0f} GB free on the build drive; need at least {need_free_gb} GB")
    if require_wsl_limits:
        mem = _mem_total_gb()
        if mem is None or mem < require_wsl_limits["memory_gb"]:
            problems.append(f"WSL memory is {mem if mem is None else round(mem, 1)} GB; raise it to at least "
                            f"{require_wsl_limits['memory_gb']} GB first (tools/build/wslconfig.py raise)")
    if (_drive_root(root) / ".bzvol").exists():
        problems.append("warning: this drive is backed up by Backblaze (.bzvol); add a Backblaze exclusion "
                        "for the build root so build files are not uploaded")
    return problems


def find_rejects(src: Path) -> list[str]:
    src = Path(src)
    found = []
    for path in src.rglob("*.rej"):
        rel = path.relative_to(src)
        if rel.parts and rel.parts[0] in SKIP_DIRS:
            continue
        found.append(rel.as_posix())
    return sorted(found)


def apply_upstream(thorium_tree: Path, src: Path, profile: str, log: Path | None = None) -> None:
    """Run upstream setup.py; raise on a non-zero exit or any rejected hunk. `log` keeps the full output."""
    tree = Path(thorium_tree)
    cmd = [sys.executable, "-I", str(tree / "setup.py"), "--chromium-src", str(src), "--thorium-root", str(tree),
           f"--{profile}"]
    proc = subprocess.run(cmd, cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                          encoding="utf-8", errors="replace")
    output = proc.stdout or ""
    if log is not None:
        log = Path(log)
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(f"$ {subprocess.list2cmdline(cmd)}\n{output}\nexit: {proc.returncode}\n",
                       encoding="utf-8", newline="\n")
    rejects = find_rejects(Path(src))
    if proc.returncode != 0 or rejects:
        tail = "\n".join(output.strip().splitlines()[-15:])
        raise RuntimeError(f"upstream setup failed (exit {proc.returncode}); rejected: {rejects or 'none'}\n{tail}")


def main(argv: list[str]) -> int:
    if argv[:1] == ["buildinfo"]:
        from tools.build import buildinfo
        return buildinfo.main(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--root", required=True)
    pre.add_argument("--need-gb", type=int, default=250)
    pre.add_argument("--require-wsl-memory-gb", type=int)
    app = sub.add_parser("apply")
    app.add_argument("--tree", required=True)
    app.add_argument("--src", required=True)
    app.add_argument("--profile", required=True)
    app.add_argument("--log", help="write the full setup output to this file")
    a = parser.parse_args(argv)
    if a.cmd == "preflight":
        limits = {"memory_gb": a.require_wsl_memory_gb} if a.require_wsl_memory_gb else None
        problems = preflight(Path(a.root), a.need_gb, limits)
        for p in problems:
            print(p)
        blocking = [p for p in problems if not p.startswith("warning:")]
        print("preflight: OK" if not blocking else f"preflight: {len(blocking)} blocking problem(s)")
        return 1 if blocking else 0
    try:
        apply_upstream(Path(a.tree), Path(a.src), a.profile, Path(a.log) if a.log else None)
    except RuntimeError as exc:
        print(exc)
        return 1
    print("upstream overlay and patch series applied: 0 rejects")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
