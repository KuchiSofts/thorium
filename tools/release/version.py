#!/usr/bin/env python3
# Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
"""Thoron's version numbers (ROADMAP P2.14).

A Thoron version is Chromium's four numbers with the last one widened:
    PATCH = Chromium patch * 100 + rebuild      (rebuild 0-99)
so Thoron 158.0.8127.3000 is the first build of Chromium 158.0.8127.30, 158.0.8127.3001 its first
rebuild, and a newer Chromium (158.0.8127.4500) always sorts above every rebuild of an older one. Each
part stays within the Windows version resource limit (65535), so the installer and the updater compare
versions as usual. The older plain numbers (Thoron 156.0.8078.28) sort below the new ones.
    py -3 -I tools/release/version.py set --src <chromium src> --rebuild 0
    py -3 -I tools/release/version.py check --new 158.0.8127.3001 --previous 158.0.8127.3000
"""
import argparse
import re
import sys
from pathlib import Path

MAX_PART = 65535
REBUILDS = 100
_VERSION = re.compile(r"^(\d{1,5})\.(\d{1,5})\.(\d{1,5})\.(\d{1,5})$")


class VersionError(Exception):
    pass


def key(version: str) -> tuple[int, int, int, int]:
    m = _VERSION.match(version or "")
    if not m:
        raise VersionError(f"not a four-part version: {version!r}")
    parts = tuple(int(x) for x in m.groups())
    if any(p > MAX_PART for p in parts):
        raise VersionError(f"{version}: each part must be at most {MAX_PART}")
    return parts


def thoron_version(chromium: str, rebuild: int) -> str:
    major, minor, build, patch = key(chromium)
    if not 0 <= rebuild < REBUILDS:
        raise VersionError(f"rebuild must be 0-{REBUILDS - 1}, got {rebuild}")
    wide = patch * REBUILDS + rebuild
    if wide > MAX_PART:
        raise VersionError(f"Chromium patch {patch} is too high: {wide} exceeds {MAX_PART}")
    return f"{major}.{minor}.{build}.{wide}"


def split(thoron: str) -> tuple[str, int]:
    """(Chromium version, rebuild) of a Thoron version."""
    major, minor, build, wide = key(thoron)
    return f"{major}.{minor}.{build}.{wide // REBUILDS}", wide % REBUILDS


def check_new(new: str, previous: str) -> list[str]:
    """Problems with releasing `new` after `previous` (empty when it is fine)."""
    try:
        if key(new) <= key(previous):
            return [f"{new} is not higher than the previous release {previous}"]
    except VersionError as exc:
        return [str(exc)]
    return []


def set_version_file(text: str, rebuild: int) -> str:
    """Rewrite chrome/VERSION for a Thoron build; refuses a file that is already converted."""
    nl = "\r\n" if "\r\n" in text else "\n"
    values = dict(l.split("=", 1) for l in text.splitlines() if "=" in l)
    if "THORON_REBUILD" in values:
        raise VersionError("chrome/VERSION already carries a Thoron version (THORON_REBUILD is set)")
    try:
        chromium = ".".join(values[k] for k in ("MAJOR", "MINOR", "BUILD", "PATCH"))
    except KeyError as exc:
        raise VersionError(f"chrome/VERSION has no {exc.args[0]}") from None
    wide = thoron_version(chromium, rebuild).rsplit(".", 1)[1]
    lines = [f"PATCH={wide}" if l.startswith("PATCH=") else l for l in text.splitlines()]
    lines.append(f"THORON_REBUILD={rebuild}")
    return nl.join(lines) + nl


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set", help="convert chrome/VERSION of a Chromium tree to the Thoron version")
    s.add_argument("--src", type=Path, required=True)
    s.add_argument("--rebuild", type=int, required=True)
    c = sub.add_parser("check", help="a new release must be higher than the previous one")
    c.add_argument("--new", required=True)
    c.add_argument("--previous", required=True)
    a = parser.parse_args(argv)
    try:
        if a.cmd == "set":
            path = a.src / "chrome" / "VERSION"
            text = path.read_bytes().decode("utf-8")
            new = set_version_file(text, a.rebuild)
            path.write_bytes(new.encode("utf-8"))
            values = dict(l.split("=", 1) for l in new.splitlines() if "=" in l)
            print("Thoron " + ".".join(values[k] for k in ("MAJOR", "MINOR", "BUILD", "PATCH")))
            return 0
        problems = check_new(a.new, a.previous)
    except (VersionError, OSError) as exc:
        print(f"version: {exc}", file=sys.stderr)
        return 2
    for p in problems:
        print(f"version: {p}", file=sys.stderr)
    print("version: OK" if not problems else "version: refused")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
