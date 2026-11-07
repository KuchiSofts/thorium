#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Temporarily raise WSL memory/swap for a Linux build, then restore the owner's exact .wslconfig.

Works on raw bytes: comments (any language), line endings and unknown keys are preserved, and
`restore` puts back the original file byte for byte. This tool NEVER restarts WSL itself: applying
a change needs `wsl --shutdown`, which stops every distro (services, Docker), so it only prints the
command for the owner to approve.
    py -3 -I tools/build/wslconfig.py raise   [--path FILE]
    py -3 -I tools/build/wslconfig.py restore BACKUP [--path FILE]
    py -3 -I tools/build/wslconfig.py show    [--path FILE]
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

# WSL expects doubled backslashes in Windows paths inside .wslconfig.
DEFAULT_SWAP_FILE = "\\\\".join(["J:", "thoron-build", "wsl", "swap.vhdx"])
SHUTDOWN_NOTE = ("To apply, the owner must approve running:  wsl --shutdown\n"
                 "(this stops every WSL distro, including running services and Docker, for a moment)")


def _newline(data: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in data else b"\n"


def _section_bounds(lines: list[bytes], name: bytes) -> tuple[int, int] | None:
    start = next((i for i, l in enumerate(lines) if l.strip().lower() == b"[" + name + b"]"), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith(b"[")), len(lines))
    return start, end


def _set_keys(data: bytes, values: dict[str, str]) -> bytes:
    nl = _newline(data) if data else b"\r\n"
    lines = data.splitlines(keepends=True)
    if lines and not lines[-1].endswith((b"\n", b"\r")):
        lines[-1] += nl
    bounds = _section_bounds(lines, b"wsl2")
    if bounds is None:
        header = [b"[wsl2]" + nl] + [f"{k}={v}".encode("utf-8") + nl for k, v in values.items()]
        return b"".join(header + ([nl] if lines else []) + lines)
    start, end = bounds
    missing = dict(values)
    for i in range(start + 1, end):
        m = re.match(rb"\s*([A-Za-z]+)\s*=", lines[i])
        if m:
            key = next((k for k in missing if k.lower() == m.group(1).decode("ascii", "replace").lower()), None)
            if key:
                ending = lines[i][len(lines[i].rstrip(b"\r\n")):] or nl
                lines[i] = f"{key}={missing.pop(key)}".encode("utf-8") + ending
    insert = [f"{k}={v}".encode("utf-8") + nl for k, v in missing.items()]
    return b"".join(lines[:start + 1] + insert + lines[start + 1:])


def raise_limits(path: Path, memory: str = "48GB", swap: str = "32GB",
                 swap_file: str | None = DEFAULT_SWAP_FILE) -> Path:
    path = Path(path)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    if path.exists():
        original = path.read_bytes()
        backup = path.with_name(f"{path.name}.thoron-backup-{stamp}")
        backup.write_bytes(original)
        if backup.read_bytes() != original:
            raise OSError(f"backup verification failed: {backup}")
    else:
        original = b""
        backup = path.with_name(f"{path.name}.thoron-backup-{stamp}.absent")
        backup.write_bytes(b"")
    values = {"memory": memory, "swap": swap}
    if swap_file:
        values["swapFile"] = swap_file
    path.write_bytes(_set_keys(original, values))
    return backup


def restore(path: Path, backup: Path) -> None:
    path, backup = Path(path), Path(backup)
    if backup.name.endswith(".absent"):
        path.unlink(missing_ok=True)
    else:
        original = backup.read_bytes()
        path.write_bytes(original)
        if path.read_bytes() != original:
            raise OSError(f"restore verification failed: {path} (backup kept at {backup})")
    backup.unlink()


def current_limits(path: Path) -> dict[str, str]:
    path = Path(path)
    if not path.exists():
        return {}
    lines = path.read_bytes().splitlines()
    bounds = _section_bounds([l + b"\n" for l in lines], b"wsl2")
    if bounds is None:
        return {}
    result = {}
    for line in lines[bounds[0] + 1:bounds[1]]:
        m = re.match(rb"\s*([A-Za-z]+)\s*=\s*(.*?)\s*$", line)
        if m:
            result[m.group(1).decode("utf-8", "replace")] = m.group(2).decode("utf-8", "replace")
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["raise", "restore", "show"])
    parser.add_argument("backup", nargs="?")
    parser.add_argument("--path", default=str(Path.home() / ".wslconfig"))
    a = parser.parse_args(argv)
    path = Path(a.path)
    if a.command == "show":
        print(current_limits(path))
        return 0
    if a.command == "raise":
        backup = raise_limits(path)
        print(f"raised: {current_limits(path)}\nbackup of the original: {backup}\n{SHUTDOWN_NOTE}")
        return 0
    if not a.backup:
        print("restore needs the backup path printed by 'raise'", file=sys.stderr)
        return 2
    restore(path, Path(a.backup))
    print(f"restored original: {current_limits(path)}\n{SHUTDOWN_NOTE}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
